import io
import tempfile
import uuid
from decimal import Decimal as D
from PIL import Image
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Person, Device, Identifier, Accessory, Ledger, StockMove, Audit, QuickCreation, Sale, Store


class QuickSaleTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('gestor-rapido', password='Teste!Local991', is_staff=True)
        self.seller = get_user_model().objects.create_user('vendedor-rapido', password='Teste!Local992')
        self.origin = Person.objects.create(name='Fornecedor QA rápido', kind='supplier')
        self.client.force_login(self.admin)
        self.temp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.override.disable)

    def post(self, kind, data, key=None):
        prefix = f'quick-{kind}'
        values = {f'{prefix}-{name}': value for name, value in data.items()}
        values[f'{prefix}-request_key'] = str(key or uuid.uuid4())
        return self.client.post(f'/vendas/cadastro/{kind}/', values)

    def device_data(self, **overrides):
        from .forms import DeviceForm
        values = {'model': 'iPhone QA rápido', 'storage': '128 GB', 'color': 'Preto', 'condition': 'used', 'imei1': '999999999999999', 'origin': self.origin.pk, 'entry_date': '2026-10-24', 'acquisition_cost': '1000', 'extra_cost': '50', 'price': '2000', 'serial': 'SERIE-QA-RAPIDO'}
        values.update({k: 'unchecked' for k in DeviceForm.check_fields})
        values.update(overrides)
        return values

    def accessory_data(self, **overrides):
        values = {'name': 'Cabo QA rápido', 'category': 'Cabos', 'supplier': self.origin.pk, 'cost': '20', 'price': '50', 'quantity': '3', 'minimum': '1'}
        values.update(overrides)
        return values

    def test_customer_created_with_discovery_and_replayed_without_duplicates(self):
        key = uuid.uuid4()
        data = {'name': 'Cliente QA rápido', 'document': '529.982.247-25', 'email': 'qa@example.test', 'phone': '11999990000', 'discovery_source': 'referral', 'discovery_details': 'Indicação registrada no teste'}
        response = self.post('customer', data, key)
        self.assertEqual(response.status_code, 201, response.content)
        person = Person.objects.get(pk=response.json()['object']['id'])
        self.assertEqual(person.document, '52998224725')
        self.assertEqual(person.kind, 'customer')
        self.assertEqual(person.discovery_source, 'referral')
        self.assertEqual(person.email, 'qa@example.test')
        self.assertNotEqual(response.json()['next_request_key'], str(key))
        retry = self.post('customer', data, key)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['replayed'])
        self.assertEqual(Person.objects.filter(document='52998224725').count(), 1)
        self.assertEqual(QuickCreation.objects.count(), 1)

    def test_duplicate_document_offers_existing_contact_without_overwriting(self):
        existing = Person.objects.create(name='Contato existente QA', document='52998224725', email='original@example.test')
        response = self.post('customer', {'name': 'Nome diferente', 'document': '529.982.247-25', 'email': 'outro@example.test'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['existing']['id'], existing.pk)
        existing.refresh_from_db()
        self.assertEqual(existing.email, 'original@example.test')
        self.assertFalse(QuickCreation.objects.exists())

    def test_invalid_customer_data_does_not_persist(self):
        count = Person.objects.count()
        response = self.post('customer', {'name': 'QA', 'document': '11111111111', 'email': 'email-invalido'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('document', response.json()['errors'])
        self.assertIn('email', response.json()['errors'])
        self.assertEqual(Person.objects.count(), count)

    def test_device_entry_stock_payable_and_retry_once(self):
        key = uuid.uuid4()
        response = self.post('device', self.device_data(), key)
        self.assertEqual(response.status_code, 201, response.content)
        device = Device.objects.get()
        self.assertEqual(device.status, 'available')
        self.assertEqual(device.cost, D('1050'))
        self.assertEqual(response.json()['object']['price'], 200000)
        self.assertEqual(response.json()['object']['origin']['id'], self.origin.pk)
        self.assertEqual(StockMove.objects.get(device=device).quantity, 1)
        self.assertEqual(sum(Ledger.objects.values_list('amount', flat=True)), D('-1050'))
        self.assertFalse(Ledger.objects.filter(settled_date__isnull=False).exists())
        retry = self.post('device', self.device_data(), key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Ledger.objects.count(), 2)

    def test_new_supplier_is_created_in_same_device_transaction(self):
        data = self.device_data(origin='', origin_name='Fornecedor novo QA')
        response = self.post('device', data)
        self.assertEqual(response.status_code, 201, response.content)
        supplier = Person.objects.get(name='Fornecedor novo QA')
        self.assertEqual(supplier.kind, 'supplier')
        self.assertEqual(Device.objects.get().origin, supplier)

    def test_duplicate_imei_or_serial_does_not_create_supplier_or_ledger(self):
        self.assertEqual(self.post('device', self.device_data()).status_code, 201)
        counts = (Person.objects.count(), Ledger.objects.count(), StockMove.objects.count())
        response = self.post('device', self.device_data(origin='', origin_name='Não criar QA', serial='OUTRA-SERIE'))
        self.assertEqual(response.status_code, 422)
        self.assertEqual((Person.objects.count(), Ledger.objects.count(), StockMove.objects.count()), counts)
        response = self.post('device', self.device_data(imei1='123456789123456'))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Device.objects.count(), 1)

    def test_origin_required_and_existing_supplier_name_not_duplicated(self):
        response = self.post('device', self.device_data(origin=''))
        self.assertEqual(response.status_code, 422)
        response = self.post('device', self.device_data(origin='', origin_name=self.origin.name))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Person.objects.count(), 1)

    def test_accessory_stock_and_cost_registered_once(self):
        key = uuid.uuid4()
        response = self.post('accessory', self.accessory_data(), key)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['object']['price'], 5000)
        self.assertEqual(Accessory.objects.get().quantity, 3)
        self.assertEqual(Ledger.objects.get().amount, D('-60'))
        self.post('accessory', self.accessory_data(), key)
        self.assertEqual(Accessory.objects.count(), 1)
        self.assertEqual(StockMove.objects.get().quantity, 3)
        self.assertEqual(Ledger.objects.count(), 1)

    def test_accessory_zero_stock_is_rejected_without_partial_supplier(self):
        response = self.post('accessory', self.accessory_data(quantity='0', supplier='', origin_name='Não criar QA'))
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Accessory.objects.exists())
        self.assertFalse(Person.objects.filter(name='Não criar QA').exists())

    def test_registration_then_sale_uses_new_records_and_snapshots_discovery(self):
        customer_id = self.post('customer', {'name': 'Cliente venda QA', 'discovery_source': 'instagram'}).json()['object']['id']
        device_id = self.post('device', self.device_data()).json()['object']['id']
        data = {'customer': customer_id, 'devices': [device_id], 'discount': '0', 'request_key': str(uuid.uuid4()), 'acc-TOTAL_FORMS': '0', 'acc-INITIAL_FORMS': '0', 'pay-TOTAL_FORMS': '1', 'pay-INITIAL_FORMS': '0', 'pay-0-method': 'pix', 'pay-0-amount': '2000'}
        response = self.client.post('/vendas/nova/', data)
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get()
        self.assertEqual(sale.customer_snapshot['discovery_source'], 'instagram')
        self.assertEqual(sale.items.get().device_id, device_id)
        self.assertEqual(sale.profit, D('950'))

    def test_saved_registrations_remain_on_invalid_sale(self):
        person_id = self.post('customer', {'name': 'Cadastro persistente QA'}).json()['object']['id']
        device_id = self.post('device', self.device_data()).json()['object']['id']
        response = self.client.post('/vendas/nova/', {'customer': person_id, 'devices': [device_id], 'discount': '0', 'request_key': str(uuid.uuid4()), 'notes': 'Manter esta observação', 'acc-TOTAL_FORMS': '0', 'acc-INITIAL_FORMS': '0', 'pay-TOTAL_FORMS': '0', 'pay-INITIAL_FORMS': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manter esta observação')
        self.assertEqual(Person.objects.filter(pk=person_id).count(), 1)
        self.assertEqual(Device.objects.get().status, 'available')
        self.assertFalse(Sale.objects.exists())

    def test_permissions_csrf_and_request_key_ownership(self):
        key = uuid.uuid4()
        self.post('customer', {'name': 'Cliente de outro autor QA'}, key)
        self.client.force_login(self.seller)
        self.assertEqual(self.post('customer', {'name': 'Novo'}, key).status_code, 403)
        self.assertEqual(self.post('accessory', self.accessory_data()).status_code, 403)
        self.assertEqual(self.post('device', self.device_data()).status_code, 201)
        self.assertEqual(self.post('customer', {'name': 'Cliente vendedor QA'}).status_code, 201)
        self.assertEqual(self.client.post('/configuracoes/logo/', {}).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post('/vendas/cadastro/customer/', {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post('/vendas/cadastro/customer/', {}).status_code, 302)

    def test_sales_page_has_inline_dialogs_checkbox_picker_and_discovery(self):
        page = self.client.get('/vendas/nova/')
        for label in ['Cadastrar cliente', 'Cadastrar aparelho', 'Cadastrar acessório', 'Como conheceu a BG Store?', 'id="quick-customer-dialog"', 'id="sale-form"']:
            self.assertContains(page, label)
        self.assertNotContains(page, 'Ctrl/Cmd')
        self.assertEqual(self.client.get('/vendas/cadastro/customer/').status_code, 405)
        self.assertEqual(self.client.post('/vendas/cadastro/customer/', {}).status_code, 400)

    def image_file(self):
        buffer = io.BytesIO()
        Image.new('RGB', (12, 12), '#be9f60').save(buffer, format='PNG')
        return SimpleUploadedFile('logo-qa.png', buffer.getvalue(), content_type='image/png')

    def test_logo_upload_public_brand_but_private_other_attachments(self):
        response = self.client.post('/configuracoes/logo/', {'logo': self.image_file()})
        self.assertEqual(response.status_code, 200, response.content)
        store = Store.objects.get()
        self.assertTrue(store.logo.name)
        self.client.logout()
        response = self.client.get('/marca/logo/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        response.close()
        self.assertContains(self.client.get('/entrar/'), '/marca/logo/?v=')
        self.assertEqual(self.client.get('/arquivos/invoices/qualquer.pdf').status_code, 302)
        self.assertTrue(Audit.objects.filter(action='Logo atualizada').exists())

    def test_bad_logo_does_not_replace_existing_brand(self):
        self.client.post('/configuracoes/logo/', {'logo': self.image_file()})
        name = Store.objects.get().logo.name
        response = self.client.post('/configuracoes/logo/', {'logo': SimpleUploadedFile('falso.png', b'nao e imagem', content_type='image/png')})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Store.objects.get().logo.name, name)
