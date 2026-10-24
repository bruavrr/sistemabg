import uuid
from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import *
from .services import complete_sale, cancel_sale, store
from .workflows import *
from .operations_forms import ServiceNewForm


class OperationsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('gestor', password='Teste!Local991', is_staff=True)
        self.seller = get_user_model().objects.create_user('operador', password='Teste!Local992')
        self.person = Person.objects.create(name='Contato QA operações')
        self.device = Device.objects.create(model='Aparelho QA', storage='128 GB', color='Preto', condition='used', origin=self.person, price=D('2000'), acquisition_cost=D('1000'), extra_cost=D('50'))
        Identifier.objects.create(device=self.device, slot=1, value='555555555555555')
        self.acc = Accessory.objects.create(name='Cabo QA', category='Cabo', supplier=self.person, cost=D('20'), price=D('50'), quantity=3)
        self.part = ServicePart.objects.create(name='Peça QA', supplier=self.person, cost=D('30'), price=D('80'), quantity=2)
        self.rate = CardRate.objects.create(machine='Taxa QA', installments=3, percent=D('3.125'))
        self.client.force_login(self.admin)

    def sale_args(self, **overrides):
        data = dict(customer=self.person, devices=[self.device], accessories=[], discount=D('0'), payment_rows=[{'method': 'cash', 'amount': D('2000')}], actor=self.seller, request_key=uuid.uuid4())
        data.update(overrides)
        return data

    def quote(self, **overrides):
        data = dict(customer=self.person, devices=[self.device], accessories=[], discount=D('0'), valid_until=timezone.localdate() + timedelta(days=7), notes='Proposta QA', actor=self.seller, request_key=uuid.uuid4())
        data.update(overrides)
        return create_quote(**data)

    def order(self, **overrides):
        data = dict(customer=self.person, device_description='Aparelho do cliente QA', imei='666666666666666', labor_price=D('100'), labor_cost=D('40'), actor=self.admin, request_key=uuid.uuid4(), complaint='Falha relatada', approval_note='Autorização registrada em atendimento presencial', approved_limit=D('300'))
        data.update(overrides)
        return ServiceOrder.objects.create(**data)

    def approve(self, order):
        for status in ('diagnosing', 'awaiting', 'approved'):
            transition_service(order.pk, status, 'Registro QA', self.admin)

    def test_quote_does_not_move_stock_or_finance_and_replays_once(self):
        key = uuid.uuid4()
        q = self.quote(request_key=key)
        self.assertEqual(q.total, D('2000'))
        self.assertEqual(self.quote(request_key=key).pk, q.pk)
        self.assertFalse(Ledger.objects.exists())
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'available')

    def test_quote_conversion_exactly_once(self):
        q = self.quote()
        sale = sell_quote(q.pk, **self.sale_args())
        self.assertEqual(sell_quote(q.pk, **self.sale_args()).pk, sale.pk)
        self.assertEqual(Sale.objects.count(), 1)
        q.refresh_from_db()
        self.assertEqual(q.status, 'converted')
        self.assertEqual(q.sale_id, sale.pk)

    def test_quote_price_change_or_expiry_does_not_silently_change_sale(self):
        q = self.quote()
        self.device.price = D('2100')
        self.device.save()
        with self.assertRaises(ValidationError):
            sell_quote(q.pk, **self.sale_args())
        self.assertFalse(Sale.objects.exists())
        q.valid_until = timezone.localdate() - timedelta(days=1)
        q.save()
        with self.assertRaises(ValidationError):
            sell_quote(q.pk, **self.sale_args())

    def test_quote_product_or_customer_tampering_rejected(self):
        q = self.quote(accessories=[(self.acc, 1)])
        with self.assertRaises(ValidationError):
            sell_quote(q.pk, **self.sale_args())
        self.assertFalse(Sale.objects.exists())

    def test_quote_conversion_via_http_prefills_and_completes(self):
        q = self.quote(accessories=[(self.acc, 1)])
        proposal_page = self.client.get('/orcamentos/novo/')
        self.assertContains(proposal_page, (timezone.localdate() + timedelta(days=7)).isoformat())
        response = self.client.get(f'/vendas/nova/?quote={q.pk}')
        self.assertEqual(response.context['form'].initial['quote'], q.pk)
        data = {'quote': q.pk, 'customer': self.person.pk, 'devices': [self.device.pk], 'discount': '0', 'request_key': str(uuid.uuid4()), 'acc-TOTAL_FORMS': '1', 'acc-INITIAL_FORMS': '0', 'acc-0-accessory': self.acc.pk, 'acc-0-quantity': '1', 'pay-TOTAL_FORMS': '1', 'pay-INITIAL_FORMS': '0', 'pay-0-method': 'pix', 'pay-0-amount': '2050'}
        self.assertEqual(self.client.post('/vendas/nova/', data).status_code, 302)
        q.refresh_from_db()
        self.assertIsNotNone(q.sale_id)

    def test_card_simulator_gross_net_and_residue(self):
        result = simulate_card(D('1000'), self.rate, 'gross')
        self.assertEqual(result['fee'], D('31.25'))
        self.assertEqual(result['net'], D('968.75'))
        self.assertEqual(sum(result['installments']), D('1000'))
        result = simulate_card(D('1000'), self.rate, 'net')
        self.assertGreaterEqual(result['net'], D('1000'))
        previous = result['gross'] - D('.01')
        self.assertLess(previous - money(previous * self.rate.percent / 100), D('1000'))
        self.rate.percent = 100
        with self.assertRaises(ValidationError):
            simulate_card(D('1'), self.rate, 'net')

    def test_manual_valuation_preserves_rule_snapshot_and_floors_zero(self):
        rule = ValuationRule.objects.create(model='QA', storage='128 GB', maximum=D('500'), battery_discount=D('100'), screen_discount=D('300'), wear_discount=D('200'))
        v = save_valuation(dict(rule=rule, battery_issue=True, screen_issue=True, wear_issue=True, person=self.person), self.seller)
        self.assertEqual(v.suggested, D('0'))
        rule.maximum = D('1000')
        rule.save()
        v.refresh_from_db()
        self.assertEqual(v.snapshot['maximum'], '500')
        self.assertFalse(StockMove.objects.exists())
        self.assertFalse(Ledger.objects.exists())

    def test_valuation_prefills_trade_but_does_not_create_inventory(self):
        rule = ValuationRule.objects.create(model='QA modelo', storage='128 GB', maximum=D('700'))
        v = save_valuation(dict(rule=rule, person=self.person), self.seller)
        response = self.client.get(f'/vendas/nova/?valuation={v.pk}')
        self.assertTrue(response.context['wants_trade'])
        self.assertEqual(response.context['trade_form'].initial['acquisition_cost'], D('700'))
        self.assertEqual(Device.objects.count(), 1)

    def test_service_lifecycle_parts_finance_once(self):
        order = self.order()
        self.approve(order)
        consume_part(order.pk, self.part.pk, 1, self.admin)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 1)
        transition_service(order.pk, 'repair', 'Iniciou', self.admin)
        update_service(order.pk, {'work_done': 'Reparo realizado'}, self.admin)
        transition_service(order.pk, 'ready', 'Concluído', self.admin)
        transition_service(order.pk, 'delivered', 'Cliente retirou', self.admin)
        transition_service(order.pk, 'delivered', 'Repetição', self.admin)
        order.refresh_from_db()
        self.assertEqual(order.total, D('180'))
        self.assertEqual(order.cost, D('70'))
        self.assertEqual(order.result, D('110'))
        self.assertFalse(order.active)
        self.assertEqual(order.ledger.count(), 2)
        self.assertEqual(order.ledger.get(amount__gt=0).amount, D('180'))
        self.assertEqual(order.ledger.get(amount__lt=0).amount, D('-40'))
        self.assertFalse(order.ledger.filter(settled_date__isnull=False).exists())

    def test_service_approval_and_limit_enforced_without_stock_loss(self):
        order = self.order(approval_note='', approved_limit=D('0'))
        with self.assertRaises(ValidationError):
            consume_part(order.pk, self.part.pk, 1, self.admin)
        transition_service(order.pk, 'diagnosing', 'Diagnóstico', self.admin)
        transition_service(order.pk, 'awaiting', 'Aprovar', self.admin)
        with self.assertRaises(ValidationError):
            transition_service(order.pk, 'approved', 'Sem prova', self.admin)
        update_service(order.pk, {'approval_note': 'Autorização cliente', 'approved_limit': D('150')}, self.admin)
        transition_service(order.pk, 'approved', 'Autorizado', self.admin)
        with self.assertRaises(ValidationError):
            consume_part(order.pk, self.part.pk, 1, self.admin)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 2)
        self.assertFalse(PartUse.objects.exists())

    def test_cancel_service_requires_confirmed_physical_return(self):
        order = self.order()
        self.approve(order)
        consume_part(order.pk, self.part.pk, 1, self.admin)
        with self.assertRaises(ValidationError):
            transition_service(order.pk, 'cancelled', 'Cancelamento', self.admin)
        transition_service(order.pk, 'cancelled', 'Retorno conferido', self.admin, confirm_return=True)
        transition_service(order.pk, 'cancelled', 'Repetição', self.admin, confirm_return=True)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 2)
        self.assertFalse(Ledger.objects.exists())

    def test_internal_repair_adds_cost_to_device_without_fictional_revenue(self):
        data = dict(customer=self.person.pk, device_description='Aparelho interno', inventory_device=self.device.pk, complaint='Manutenção interna', labor_price='0', labor_cost='40', request_key=str(uuid.uuid4()))
        form = ServiceNewForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        order = create_service(form, self.admin)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'maintenance')
        update_service(order.pk, {'approval_note': 'Autorizado responsável BG', 'approved_limit': D('100')}, self.admin)
        self.approve(order)
        consume_part(order.pk, self.part.pk, 1, self.admin)
        transition_service(order.pk, 'repair', 'Reparo', self.admin)
        update_service(order.pk, {'work_done': 'Reparo executado'}, self.admin)
        transition_service(order.pk, 'ready', 'Pronto', self.admin)
        transition_service(order.pk, 'delivered', 'Voltou ao estoque', self.admin)
        self.device.refresh_from_db()
        self.assertEqual(self.device.extra_cost, D('120'))
        self.assertEqual(self.device.status, 'available')
        self.assertFalse(order.ledger.filter(amount__gt=0).exists())
        self.assertEqual(order.ledger.get().amount, D('-40'))
        sale = complete_sale(**self.sale_args())
        self.assertEqual(sale.costs, D('1120'))

    def test_active_service_prevents_manual_stock_release(self):
        order = self.order(inventory_device=self.device, imei=self.device.imei1)
        self.device.status = 'maintenance'
        self.device.save()
        self.client.post(f'/aparelhos/{self.device.pk}/status/', {'status': 'available'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, 'maintenance')

    def test_part_restock_weighted_cost_and_payable(self):
        restock_part(self.part.pk, 2, D('50'), 'Reposição QA', self.admin)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 4)
        self.assertEqual(self.part.cost, D('40'))
        self.assertEqual(Ledger.objects.get().amount, D('-100'))
        with self.assertRaises(ValidationError):
            restock_part(self.part.pk, -5, D('0'), 'Ajuste', self.admin)

    def test_cash_counts_cash_only_and_transfers_net_zero(self):
        session = open_cash(D('100'), self.admin)
        with self.assertRaises(ValidationError):
            open_cash(D('0'), self.admin)
        sale = complete_sale(**self.sale_args(payment_rows=[{'method': 'cash', 'amount': D('500')}, {'method': 'pix', 'amount': D('1500')}]))
        self.assertEqual(session.expected, D('600'))
        cash_transfer(session.pk, 'withdraw', D('100'), 'Depósito real', self.admin)
        self.assertEqual(session.expected, D('500'))
        self.assertEqual(sum(Ledger.objects.filter(transfer_key__isnull=False).values_list('amount', flat=True)), D('0'))
        metrics = dict(self.client.get('/').context['metrics'])
        self.assertEqual(metrics['Despesas operacionais pagas'], D('0'))
        close_cash(session.pk, D('490'), 'Diferença registrada', self.admin)
        session.refresh_from_db()
        self.assertEqual(session.difference, D('-10'))
        with self.assertRaises(ValidationError):
            cash_transfer(session.pk, 'withdraw', D('1'), 'Encerrado', self.admin)
        next_session = open_cash(D('490'), self.admin)
        self.assertEqual(next_session.expected, D('490'))
        self.assertEqual(session.expected, D('500'))

    def test_refund_enters_cash_only_when_actually_paid(self):
        session = open_cash(D('100'), self.admin)
        sale = complete_sale(**self.sale_args())
        cancel_sale(sale.pk, 'Desistência', self.admin)
        self.assertEqual(session.expected, D('2100'))
        refund = Ledger.objects.get(reverses__isnull=False)
        settle_ledger(refund.pk, 'cash', self.admin)
        self.assertEqual(session.expected, D('100'))
        with self.assertRaises(ValidationError):
            settle_ledger(refund.pk, 'cash', self.admin)

    def test_cash_sangria_cannot_exceed_physical_amount(self):
        session = open_cash(D('10'), self.admin)
        with self.assertRaises(ValidationError):
            cash_transfer(session.pk, 'withdraw', D('11'), 'Excesso', self.admin)
        self.assertFalse(Ledger.objects.exists())

    def test_followup_local_task_created_once_and_cancelled_with_sale(self):
        st = store()
        st.followup_days = 7
        st.save()
        args = self.sale_args()
        sale = complete_sale(**args)
        complete_sale(**args)
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(timezone.localdate(task.when), timezone.localdate() + timedelta(days=7))
        cancel_sale(sale.pk, 'Cancelamento', self.admin)
        task.refresh_from_db()
        self.assertTrue(task.cancelled)

    def test_tasks_require_completion_note_and_link_correct_customer(self):
        task = Task.objects.create(title='Pós-venda QA', kind='after_sale', person=self.person, when=timezone.now(), actor=self.seller)
        self.client.post(f'/agenda/{task.pk}/concluir/', {'note': ''})
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)
        self.client.post(f'/agenda/{task.pk}/concluir/', {'note': 'Contato realizado pela loja'})
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)
        self.client.post(f'/agenda/{task.pk}/concluir/', {'note': 'Não sobrescrever'})
        task.refresh_from_db()
        self.assertEqual(task.completion_note, 'Contato realizado pela loja')

    def test_device_price_edit_does_not_change_completed_sale(self):
        quote = self.quote()
        response = self.client.post(f'/aparelhos/{self.device.pk}/editar/', {'price': '2100', 'battery': '90', 'physical': 'Bom', 'replaced_parts': '', 'notes': '', 'reason': 'Preço atualizado'})
        self.assertEqual(response.status_code, 302)
        self.device.refresh_from_db()
        self.assertEqual(self.device.price, D('2100'))
        self.assertEqual(quote.total, D('2000'))
        sale = complete_sale(**self.sale_args(payment_rows=[{'method': 'pix', 'amount': D('2100')}]))
        self.client.post(f'/aparelhos/{self.device.pk}/editar/', {'price': '2200', 'reason': 'Tentativa'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.price, D('2100'))
        self.assertEqual(sale.total, D('2100'))

    def test_new_pages_documents_and_all_reports_render(self):
        quote = self.quote()
        order = self.order()
        session = open_cash(D('0'), self.admin)
        paths = ['/orcamentos/', '/orcamentos/novo/', f'/orcamentos/{quote.pk}/', '/ferramentas/', '/ferramentas/cartao/', '/ferramentas/regra/', '/ferramentas/avaliar/', '/assistencia/', '/assistencia/?view=kanban', '/assistencia/nova/', f'/assistencia/os/{order.pk}/', '/assistencia/pecas/', '/assistencia/pecas/nova/', '/agenda/', '/agenda/nova/', '/caixa/', f'/caixa/{session.pk}/', f'/contatos/{self.person.pk}/editar/', f'/aparelhos/{self.device.pk}/editar/']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        for kind in ('sales', 'stock', 'payments', 'customers', 'services', 'finance'):
            self.assertEqual(self.client.get(f'/relatorios/?kind={kind}').status_code, 200)
            self.assertEqual(self.client.get(f'/relatorios/?kind={kind}&format=csv').status_code, 200)
        for kind, obj in [('quote', quote), ('service', order), ('label', self.device)]:
            response = self.client.get(f'/imprimir/{kind}/{obj.pk}/')
            self.assertContains(response, 'nota fiscal', html=False)

    def test_reports_use_real_sales_exclude_cancellations_and_escape_csv(self):
        self.person.name = '=HYPERLINK("falso")'
        self.person.save()
        sale = complete_sale(**self.sale_args())
        response = self.client.get('/relatorios/?kind=customers&format=csv')
        self.assertIn(b"'=HYPERLINK", response.content)
        self.assertEqual(dict(self.client.get('/relatorios/').context['metrics'])['Faturamento de vendas'], D('2000'))
        cancel_sale(sale.pk, 'Teste', self.admin)
        self.assertEqual(dict(self.client.get('/relatorios/').context['metrics'])['Faturamento de vendas'], D('0'))

    def test_seller_cannot_write_new_admin_endpoints(self):
        quote = self.quote()
        order = self.order()
        session = open_cash(D('0'), self.admin)
        self.client.force_login(self.seller)
        paths = ['/caixa/', f'/caixa/{session.pk}/fechar/', f'/caixa/{session.pk}/movimento/', '/relatorios/', '/ferramentas/regra/', '/assistencia/pecas/nova/', f'/assistencia/pecas/{self.part.pk}/movimento/', f'/assistencia/os/{order.pk}/etapa/', f'/assistencia/os/{order.pk}/peca/', f'/contatos/{self.person.pk}/editar/', f'/aparelhos/{self.device.pk}/editar/']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {}).status_code, 403)
        self.assertEqual(self.client.post(f'/assistencia/os/{order.pk}/', {}).status_code, 403)
        self.assertEqual(self.client.get('/orcamentos/').status_code, 200)
