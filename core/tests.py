import uuid
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.utils import timezone
from .models import *
from .forms import DeviceForm, PersonForm
from .services import *

class WorkflowTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user('admin',password='UmaSenha!Teste732',is_staff=True,is_superuser=True)
        self.seller=get_user_model().objects.create_user('seller',password='UmaSenha!Teste732')
        self.person=Person.objects.create(name='Contato de teste')
        self.device=Device.objects.create(model='iPhone teste',storage='128 GB',color='Preto',condition='used',origin=self.person,acquisition_cost=D('1000.00'),extra_cost=D('50.00'),price=D('2000.00'))
        Identifier.objects.create(device=self.device,slot=1,value='123456789012345')
        self.accessory=Accessory.objects.create(name='Cabo teste',category='Cabos',supplier=self.person,cost=D('20.00'),price=D('50.00'),quantity=3)
        self.rate=CardRate.objects.create(machine='Contrato teste',installments=3,percent=D('3.125'),days=30)
    def sell(self,**kwargs):
        args=dict(customer=self.person,devices=[self.device],accessories=[],discount=D('0'),payment_rows=[{'method':'pix','amount':D('2000')}],actor=self.seller,request_key=uuid.uuid4())
        args.update(kwargs); return complete_sale(**args)
    def entry_form(self,**kwargs):
        data=dict(model='iPhone recebido',storage='64 GB',color='Branco',condition='used',serial='SERIE-TROCA',origin=self.person.pk,entry_date='2026-01-31',acquisition_cost='500.00',extra_cost='0',price='900',imei1='222222222222222',imei2='333333333333333')
        data.update({k:'unchecked' for k in DeviceForm.check_fields});data.update(kwargs)
        f=DeviceForm(data); self.assertTrue(f.is_valid(),f.errors);return f
    def test_entry_generates_unique_identifiers_stock_audit_and_payable(self):
        device=create_device(self.entry_form(extra_cost='20'),self.admin)
        self.assertEqual(device.identifiers.count(),2)
        self.assertEqual(sum((l.amount for l in Ledger.objects.filter(device=device)),ZERO),D('-520'))
        self.assertEqual(StockMove.objects.get(device=device).quantity,1)
        self.assertTrue(Audit.objects.filter(entity='Device',entity_id=device.pk).exists())
    def test_imei_duplicate_across_slots_and_same_form(self):
        f=self.entry_form()
        data=dict(f.data); data['imei2']='123456789012345'; f=DeviceForm(data)
        self.assertFalse(f.is_valid())
        f=self.entry_form(); data=dict(f.data); data['imei2']=data['imei1']; self.assertFalse(DeviceForm(data).is_valid())
        with self.assertRaises(IntegrityError),transaction.atomic(): Identifier.objects.create(device=self.device,slot=2,value=self.device.imei1)
    def test_sale_mixed_items_discount_and_card_rounding(self):
        sale=self.sell(accessories=[(self.accessory,2)],discount=D('100'),payment_rows=[{'method':'cash','amount':D('1000')},{'method':'card','amount':D('1000'),'card_rate':self.rate}])
        self.assertEqual(sale.total,D('2000')); self.assertEqual(sale.fees,D('31.25'));self.assertEqual(sale.profit,D('878.75'))
        self.device.refresh_from_db();self.accessory.refresh_from_db()
        self.assertEqual(self.device.status,'sold'); self.assertEqual(self.accessory.quantity,1)
        self.assertEqual(sum((l.amount for l in sale.ledger.all()),ZERO),D('1968.75'))
        self.assertEqual(sale.ledger.filter(settled_date__isnull=True).count(),3)
    def test_duplicate_sale_rejected_and_same_request_idempotent(self):
        key=uuid.uuid4(); sale=self.sell(request_key=key)
        self.assertEqual(self.sell(request_key=key).pk,sale.pk)
        with self.assertRaises(ValidationError):self.sell()
        self.assertEqual(Sale.objects.count(),1)
    def test_payment_mismatch_rolls_back(self):
        with self.assertRaises(ValidationError): self.sell(payment_rows=[{'method':'cash','amount':D('1999.99')}])
        self.device.refresh_from_db(); self.assertEqual(self.device.status,'available');self.assertEqual(Sale.objects.count(),0)
    def test_card_requires_actual_configured_rate(self):
        with self.assertRaises(ValidationError):self.sell(payment_rows=[{'method':'card','amount':D('2000')}])
        self.assertFalse(Payment.objects.exists())
    def test_upgrade_atomic_and_cancel_return(self):
        f=self.entry_form();sale=self.sell(trade_form=f,payment_rows=[{'method':'pix','amount':D('1500')}])
        self.assertEqual(sale.trade_value,D('500'));self.assertEqual(sale.trade_device.source,'trade')
        self.assertFalse(Ledger.objects.filter(device=sale.trade_device).exists())
        self.assertEqual(sale.ledger.get().amount,D('1500'))
        cancel_sale(sale.pk,'Cliente desistiu',self.admin)
        sale.trade_device.refresh_from_db();self.assertEqual(sale.trade_device.status,'returned')
        self.assertEqual(Ledger.objects.filter(reverses__isnull=False).get().amount,D('-1500'))
    def test_upgrade_wrong_origin_no_partial_records(self):
        another=Person.objects.create(name='Outro cliente')
        f=self.entry_form(origin=another.pk)
        with self.assertRaises(ValidationError):self.sell(trade_form=f,payment_rows=[{'method':'cash','amount':D('1500')}])
        self.assertEqual(Device.objects.count(),1);self.assertFalse(Sale.objects.exists())
    def test_cannot_cancel_trade_after_its_resale(self):
        sale=self.sell(trade_form=self.entry_form(),payment_rows=[{'method':'pix','amount':D('1500')}])
        self.sell(devices=[sale.trade_device],payment_rows=[{'method':'pix','amount':D('900')}])
        with self.assertRaises(ValidationError):cancel_sale(sale.pk,'Desistência',self.admin)
        sale.refresh_from_db();self.assertEqual(sale.status,'completed')
    def test_warranty_nine_calendar_months_and_apple_unconfirmed(self):
        self.assertEqual(add_months(date(2024,5,31),9),date(2025,2,28))
        sale=self.sell();w=Warranty.objects.get(item__sale=sale)
        self.assertEqual(w.provider,'store');self.assertEqual(w.end,add_months(timezone.localdate(),9))
        cancel_sale(sale.pk,'Teste',self.admin)
        self.device.refresh_from_db();self.device.condition='sealed';self.device.save()
        sale=self.sell();w=Warranty.objects.get(item__sale=sale)
        self.assertEqual(w.provider,'apple');self.assertIsNone(w.expiry);self.assertIsNone(w.end)
    def test_cancel_pending_card_voids_and_restores_accessory_once(self):
        sale=self.sell(accessories=[(self.accessory,1)],payment_rows=[{'method':'card','amount':D('2050'),'card_rate':self.rate}])
        cancel_sale(sale.pk,'Teste',self.admin); cancel_sale(sale.pk,'Repetido',self.admin)
        self.device.refresh_from_db();self.accessory.refresh_from_db()
        self.assertEqual(self.device.status,'available');self.assertEqual(self.accessory.quantity,3)
        self.assertEqual(sale.ledger.filter(voided=True).count(),3);self.assertFalse(Ledger.objects.filter(reverses__isnull=False).exists())
        resale=self.sell();self.assertEqual(resale.status,'completed')
    def test_insufficient_stock_rolls_back_everything(self):
        with self.assertRaises(ValidationError):self.sell(accessories=[(self.accessory,4)],payment_rows=[{'method':'pix','amount':D('2200')}])
        self.assertFalse(Sale.objects.exists());self.device.refresh_from_db();self.assertEqual(self.device.status,'available')
    def test_documents_and_all_main_pages(self):
        sale=self.sell(); self.client.force_login(self.admin)
        paths=['/','/contatos/','/contatos/novo/',f'/contatos/{self.person.pk}/','/aparelhos/','/aparelhos/novo/',f'/aparelhos/{self.device.pk}/','/acessorios/','/acessorios/novo/','/vendas/','/vendas/nova/',f'/vendas/{sale.pk}/','/financeiro/','/financeiro/novo/','/garantias/',f'/garantias/{Warranty.objects.first().pk}/','/configuracoes/','/configuracoes/taxa/','/modulos/','/historico/','/exportar/','/senha/']
        for p in paths:
            with self.subTest(path=p):self.assertEqual(self.client.get(p).status_code,200)
        for kind in ['entry','sale','warranty']:
            response=self.client.get(f'/documento/{kind}/{self.device.pk if kind=="entry" else sale.pk}/')
            self.assertContains(response,'NÃO É NOTA FISCAL');self.assertContains(response,'123456789012345')
    def test_server_permissions_on_get_and_post(self):
        self.assertEqual(self.client.get('/').status_code,302)
        self.client.force_login(self.seller)
        for p in ['/financeiro/','/financeiro/novo/','/configuracoes/','/historico/','/exportar/','/acessorios/novo/']:
            self.assertEqual(self.client.get(p).status_code,403)
            self.assertEqual(self.client.post(p,{}).status_code,403)
        sale=self.sell()
        self.assertEqual(self.client.post(f'/vendas/{sale.pk}/cancelar/',{'reason':'Teste'}).status_code,403)
        self.assertEqual(self.client.post('/financeiro/1/quitar/').status_code,403)
    def test_csrf_protection(self):
        client=Client(enforce_csrf_checks=True); client.force_login(self.seller)
        self.assertEqual(client.post('/contatos/novo/',{'name':'Sem CSRF'}).status_code,403)
    def test_finance_settlement_does_not_duplicate_and_cancel_creates_pending_refund(self):
        sale=self.sell(); self.client.force_login(self.admin)
        cancel_sale(sale.pk,'Reembolso devido',self.admin)
        refund=Ledger.objects.get(reverses__isnull=False)
        self.assertIsNone(refund.settled_date)
        self.client.post(f'/financeiro/{refund.pk}/quitar/');self.client.post(f'/financeiro/{refund.pk}/quitar/')
        self.assertEqual(sum((l.amount for l in Ledger.objects.filter(settled_date__isnull=False)),ZERO),ZERO)
        self.assertEqual(Ledger.objects.count(),2)
    def test_login_throttle(self):
        for _ in range(5): self.client.post('/entrar/',{'username':'seller','password':'errada'})
        self.assertEqual(self.client.post('/entrar/',{'username':'seller','password':'UmaSenha!Teste732'}).status_code,429)
    def test_person_document_validation(self):
        f=PersonForm({'name':'Contato','kind':'customer','document':'111.111.111-11'})
        self.assertFalse(f.is_valid())
    def test_file_authentication_and_path_traversal(self):
        self.assertEqual(self.client.get('/arquivos/invoices/test.pdf').status_code,302)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get('/arquivos/../manage.py').status_code,404)
    def test_financial_snapshot_immutable_after_settings_change(self):
        st=store();st.name='BG Store original';st.save();sale=self.sell()
        st.name='Nome alterado';st.warranty_terms='Outros termos';st.save()
        self.client.force_login(self.admin)
        response=self.client.get(f'/documento/sale/{sale.pk}/')
        self.assertContains(response,'BG Store original');self.assertNotContains(response,'Nome alterado')
    def test_accessory_adjustments_negative_blocked_and_restock_cost(self):
        self.client.force_login(self.admin)
        self.client.post(f'/acessorios/{self.accessory.pk}/movimento/',{'quantity':'-10','reason':'Ajuste','unit_cost':'0'})
        self.accessory.refresh_from_db();self.assertEqual(self.accessory.quantity,3)
        self.client.post(f'/acessorios/{self.accessory.pk}/movimento/',{'quantity':'1','reason':'Compra','unit_cost':'40'})
        self.accessory.refresh_from_db();self.assertEqual(self.accessory.quantity,4);self.assertEqual(self.accessory.cost,D('25'))
    def test_trade_sale_via_http(self):
        self.client.force_login(self.seller)
        form=self.entry_form()
        data={f'trade-{k}':v for k,v in form.data.items()}
        data.update({'customer':self.person.pk,'devices':[self.device.pk],'discount':'0','trade':'on','request_key':str(uuid.uuid4()),'acc-TOTAL_FORMS':'0','acc-INITIAL_FORMS':'0','pay-TOTAL_FORMS':'1','pay-INITIAL_FORMS':'0','pay-0-method':'pix','pay-0-amount':'1500'})
        response=self.client.post('/vendas/nova/',data)
        self.assertEqual(response.status_code,302)
        self.assertEqual(Sale.objects.get().trade_value,D('500'))

    def test_dashboard_operating_expenses_net_of_settled_refunds(self):
        line=Ledger.objects.create(label='Despesa teste',category='Operacional',amount=D('-100'),settled_date=timezone.localdate())
        self.client.force_login(self.admin)
        self.assertEqual(dict(self.client.get('/').context['metrics'])['Despesas operacionais pagas'],D('100'))
        self.client.post(f'/financeiro/{line.pk}/estornar/',{'reason':'Pagamento devolvido'})
        refund=Ledger.objects.get(reverses=line)
        self.client.post(f'/financeiro/{refund.pk}/quitar/')
        metrics=dict(self.client.get('/').context['metrics'])
        self.assertEqual(metrics['Despesas operacionais pagas'],ZERO)
        self.assertEqual(metrics['Saldo de caixa atual'],ZERO)

    def test_createuser_profiles_and_password_validation(self):
        from unittest.mock import patch
        from django.core.management.base import CommandError
        with patch('core.management.commands.createuser.getpass.getpass',side_effect=['SenhaTeste!9938','SenhaTeste!9938']):
            call_command('createuser','operador-teste',role='seller',verbosity=0)
        u=get_user_model().objects.get(username='operador-teste')
        self.assertFalse(u.is_staff);self.assertTrue(u.check_password('SenhaTeste!9938'))
        with patch('core.management.commands.createuser.getpass.getpass',side_effect=['123','123']):
            with self.assertRaises(CommandError):call_command('createuser','inseguro-teste',role='admin')
        self.assertFalse(get_user_model().objects.filter(username='inseguro-teste').exists())
