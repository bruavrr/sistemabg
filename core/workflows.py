"""Fluxos locais adicionais. Nenhuma chamada a serviços externos é simulada."""
import uuid
from decimal import Decimal, ROUND_CEILING
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import (
    ZERO, Person, Device, Accessory, Quote, Valuation, ServiceOrder,
    ServicePart, PartUse, PartMove, ServiceEvent, Ledger, CashSession,
)
from .services import audit, store, money, complete_sale


def snapshots(customer):
    st = store()
    return (
        {'name': customer.name, 'document': customer.document, 'phone': customer.phone, 'address': customer.address, 'discovery_source': customer.discovery_source, 'discovery_details': customer.discovery_details},
        {'name': st.name, 'document': st.document, 'phone': st.phone, 'address': st.address, 'logo': st.logo.name},
    )


@transaction.atomic
def create_quote(customer, devices, accessories, discount, valid_until, notes, actor, request_key):
    existing = Quote.objects.filter(request_key=request_key).first()
    if existing:
        return existing
    if valid_until < timezone.localdate():
        raise ValidationError('A validade não pode estar no passado.')
    items = []
    seen = set()
    for device in devices:
        if device.pk in seen or device.status not in ('available', 'reserved'):
            raise ValidationError('Aparelho repetido ou indisponível.')
        seen.add(device.pk)
        items.append({'kind': 'device', 'id': device.pk, 'description': f'{device} / IMEI {device.imei1}', 'quantity': 1, 'price': str(device.price)})
    seen = set()
    for accessory, quantity in accessories:
        if accessory.pk in seen or quantity < 1 or quantity > accessory.quantity:
            raise ValidationError('Acessório repetido ou quantidade indisponível.')
        seen.add(accessory.pk)
        items.append({'kind': 'accessory', 'id': accessory.pk, 'description': accessory.name, 'quantity': quantity, 'price': str(accessory.price)})
    gross = sum((Decimal(i['price']) * i['quantity'] for i in items), ZERO)
    discount = money(discount)
    if not items or discount < 0 or discount > gross:
        raise ValidationError('Selecione itens e um desconto entre zero e o valor dos produtos.')
    customer_data, store_data = snapshots(customer)
    quote = Quote.objects.create(customer=customer, seller=actor, items=items, discount=discount, valid_until=valid_until, notes=notes, request_key=request_key, customer_snapshot=customer_data, store_snapshot=store_data)
    audit(actor, 'Orçamento criado', quote, {'total': str(quote.total)})
    return quote


@transaction.atomic
def sell_quote(quote_id, **sale_args):
    quote = Quote.objects.select_for_update().get(pk=quote_id)
    if quote.sale_id:
        return quote.sale
    if quote.status == 'cancelled' or quote.expired:
        raise ValidationError('Orçamento cancelado ou vencido. Cadastre uma proposta atualizada.')
    expected_devices = {i['id'] for i in quote.items if i['kind'] == 'device'}
    expected_accessories = {i['id']: i['quantity'] for i in quote.items if i['kind'] == 'accessory'}
    if (quote.customer_id != sale_args['customer'].pk or expected_devices != {d.pk for d in sale_args['devices']} or expected_accessories != {a.pk: q for a, q in sale_args['accessories']} or quote.discount != sale_args['discount']):
        raise ValidationError('Os produtos, cliente e desconto devem corresponder ao orçamento. Para outra proposta, crie um novo orçamento.')
    # A mudança de preço não é silenciosamente repassada ao cliente.
    for item in quote.items:
        model = Device if item['kind'] == 'device' else Accessory
        current = model.objects.select_for_update().get(pk=item['id'])
        if current.price != Decimal(item['price']):
            raise ValidationError('Um preço mudou após o orçamento. Gere e revise uma nova proposta antes da venda.')
    sale = complete_sale(**sale_args)
    quote.sale = sale
    quote.status = 'converted'
    quote.save(update_fields=['sale', 'status'])
    audit(sale_args['actor'], 'Orçamento convertido', quote, {'venda': sale.pk})
    return sale


def simulate_card(amount, rate, mode):
    amount = money(amount)
    if amount <= 0 or not rate.active or rate.percent >= 100:
        raise ValidationError('Use um valor positivo e uma taxa ativa inferior a 100%.')
    if mode == 'net':
        gross = (amount / (1 - rate.percent / 100)).quantize(Decimal('.01'), rounding=ROUND_CEILING)
        while gross - money(gross * rate.percent / 100) < amount:
            gross += Decimal('.01')
        while gross > 0 and gross - Decimal('.01') - money((gross - Decimal('.01')) * rate.percent / 100) >= amount:
            gross -= Decimal('.01')
    else:
        gross = amount
    fee = money(gross * rate.percent / 100)
    installment = money(gross / rate.installments)
    return {'gross': gross, 'fee': fee, 'net': gross - fee, 'installments': [installment] * (rate.installments - 1) + [gross - installment * (rate.installments - 1)], 'rate': rate}


@transaction.atomic
def save_valuation(cleaned, actor):
    rule = cleaned['rule']
    if not rule.active:
        raise ValidationError('Regra de avaliação inativa.')
    criteria = {key: cleaned.get(key, False) for key in ('battery_issue', 'screen_issue', 'wear_issue')}
    deductions = sum((getattr(rule, field) for key, field in [('battery_issue', 'battery_discount'), ('screen_issue', 'screen_discount'), ('wear_issue', 'wear_discount')] if criteria[key]), ZERO)
    obj = Valuation.objects.create(rule=rule, person=cleaned.get('person'), criteria=criteria, snapshot={key: str(getattr(rule, key)) for key in ('model', 'storage', 'maximum', 'battery_discount', 'screen_discount', 'wear_discount')}, suggested=max(ZERO, rule.maximum - deductions), notes=cleaned.get('notes', ''), actor=actor)
    audit(actor, 'Avaliação manual registrada', obj, {'sugerido': str(obj.suggested), 'critérios': criteria})
    return obj


SERVICE_TRANSITIONS = {
    'received': ('diagnosing', 'cancelled'),
    'diagnosing': ('awaiting', 'cancelled'),
    'awaiting': ('approved', 'cancelled'),
    'approved': ('repair', 'cancelled'),
    'repair': ('ready', 'cancelled'),
    'ready': ('delivered', 'repair', 'cancelled'),
    'delivered': (), 'cancelled': (),
}


@transaction.atomic
def create_service(form, actor):
    existing = ServiceOrder.objects.filter(request_key=form.cleaned_data['request_key']).first()
    if existing:
        return existing
    order = form.save(commit=False)
    if order.inventory_device_id:
        device = Device.objects.select_for_update().get(pk=order.inventory_device_id)
        if device.status not in ('available', 'maintenance') or ServiceOrder.objects.filter(inventory_device=device, active=True).exists():
            raise ValidationError('Aparelho já vinculado a uma OS ativa ou indisponível.')
        if order.imei and order.imei not in (device.imei1, device.imei2):
            raise ValidationError('IMEI não corresponde ao aparelho do estoque.')
        order.imei = device.imei1
        Device.objects.filter(pk=device.pk).update(status='maintenance')
    order.actor = actor
    order.customer_snapshot, order.store_snapshot = snapshots(order.customer)
    order.save()
    ServiceEvent.objects.create(order=order, actor=actor, description='Ordem de serviço recebida.')
    audit(actor, 'OS recebida', order)
    return order


@transaction.atomic
def update_service(order_id, form_data, actor):
    order = ServiceOrder.objects.select_for_update().get(pk=order_id)
    if order.status in ('delivered', 'cancelled'):
        raise ValidationError('OS encerrada não pode ser alterada.')
    changed = {}
    for key in ('diagnosis', 'work_done', 'technician', 'approval_note', 'approved_limit', 'promised_date', 'labor_price', 'labor_cost'):
        if key in form_data and getattr(order, key) != form_data[key]:
            changed[key] = {'antes': str(getattr(order, key)), 'depois': str(form_data[key])}
            setattr(order, key, form_data[key])
    if order.status in ('approved', 'repair', 'ready') and order.total > order.approved_limit:
        raise ValidationError('Valor supera o limite autorizado pelo cliente. Registre nova autorização e limite.')
    if order.status in ('approved', 'repair', 'ready') and not order.approval_note.strip():
        raise ValidationError('Preserve o registro da autorização do cliente.')
    order.save()
    if changed:
        ServiceEvent.objects.create(order=order, actor=actor, description='Informações atualizadas: ' + ', '.join(changed))
        audit(actor, 'OS atualizada', order, changed)
    return order


@transaction.atomic
def consume_part(order_id, part_id, quantity, actor):
    order = ServiceOrder.objects.select_for_update().get(pk=order_id)
    part = ServicePart.objects.select_for_update().get(pk=part_id)
    if order.status not in ('approved', 'repair'):
        raise ValidationError('Só é possível aplicar peças em OS aprovada ou em reparo.')
    if quantity < 1 or part.quantity < quantity:
        raise ValidationError('Quantidade inválida ou estoque insuficiente.')
    if order.total + (part.cost if order.inventory_device_id else part.price) * quantity > order.approved_limit:
        raise ValidationError('Peças ultrapassam o limite autorizado. Registre nova autorização antes de aplicar.')
    if not ServicePart.objects.filter(pk=part.pk, quantity__gte=quantity).update(quantity=F('quantity') - quantity):
        raise ValidationError('Estoque alterado por outra operação.')
    use = PartUse.objects.create(order=order, part=part, quantity=quantity, cost=part.cost, price=part.price)
    PartMove.objects.create(part=part, quantity=-quantity, order=order, reason='Peça aplicada em OS', actor=actor)
    ServiceEvent.objects.create(order=order, actor=actor, description=f'Aplicada peça: {part.name} ({quantity} un.).')
    audit(actor, 'Peça aplicada', use, {'os': order.pk, 'quantidade': quantity})
    return use


@transaction.atomic
def transition_service(order_id, target, reason, actor, confirm_return=False):
    order = ServiceOrder.objects.select_for_update().get(pk=order_id)
    if target == order.status:
        return order
    if target not in SERVICE_TRANSITIONS[order.status] or not reason.strip():
        raise ValidationError('Transição inválida ou motivo ausente.')
    if target == 'approved' and (not order.approval_note.strip() or order.approved_limit < order.total):
        raise ValidationError('Registre a autorização do cliente e o limite aprovado antes de aprovar a OS.')
    if target == 'ready' and not order.work_done.strip():
        raise ValidationError('Descreva os serviços realizados antes de marcar como pronta.')
    if target == 'cancelled':
        uses = list(order.part_uses.filter(returned=False))
        if uses and not confirm_return:
            raise ValidationError('Confirme o retorno físico das peças ao estoque. Peças usadas ou danificadas exigem regularização antes de cancelar.')
        for use in uses:
            ServicePart.objects.filter(pk=use.part_id).update(quantity=F('quantity') + use.quantity)
            use.returned = True
            use.save(update_fields=['returned'])
            PartMove.objects.create(part=use.part, quantity=use.quantity, order=order, reason='Retorno físico confirmado no cancelamento', actor=actor)
    if target == 'delivered':
        if order.total > order.approved_limit:
            raise ValidationError('Total superior ao limite autorizado.')
        today = timezone.localdate()
        if order.inventory_device_id:
            Device.objects.filter(pk=order.inventory_device_id).update(extra_cost=F('extra_cost') + order.cost)
        elif order.total:
            Ledger.objects.create(service_order=order, person=order.customer, label=f'OS #{order.pk} • Serviço entregue', category='Recebimento de serviço', amount=order.total, due_date=today)
        if order.labor_cost:
            Ledger.objects.create(service_order=order, label=f'OS #{order.pk} • Custo de mão de obra', category='Custo de mão de obra', amount=-order.labor_cost, due_date=today)
        order.delivered_at = timezone.now()
    if target in ('delivered', 'cancelled'):
        order.active = False
        if order.inventory_device_id:
            Device.objects.filter(pk=order.inventory_device_id, status='maintenance').update(status='available')
    old = order.status
    order.status = target
    order.save()
    ServiceEvent.objects.create(order=order, actor=actor, description=f'{dict(ServiceOrder.STATUSES)[old]} → {order.get_status_display()}: {reason}')
    audit(actor, 'Status de OS', order, {'antes': old, 'depois': target, 'motivo': reason})
    return order


@transaction.atomic
def restock_part(part_id, quantity, unit_cost, reason, actor):
    part = ServicePart.objects.select_for_update().get(pk=part_id)
    unit_cost = money(unit_cost)
    if not quantity or part.quantity + quantity < 0 or not reason.strip() or unit_cost < 0:
        raise ValidationError('Revise a quantidade, custo e motivo do movimento.')
    if quantity > 0:
        part.cost = money((part.quantity * part.cost + quantity * unit_cost) / (part.quantity + quantity))
        if unit_cost:
            Ledger.objects.create(label=f'Compra de peças: {part.name}', category='Compra de estoque', amount=-unit_cost * quantity, person=part.supplier)
    part.quantity += quantity
    part.save(update_fields=['quantity', 'cost'])
    PartMove.objects.create(part=part, quantity=quantity, reason=reason, actor=actor)
    audit(actor, 'Movimento de peças', part, {'quantidade': quantity, 'custo': str(unit_cost), 'motivo': reason})
    return part


@transaction.atomic
def open_cash(opening, actor):
    if CashSession.objects.filter(open_slot=1).exists() or opening < 0:
        raise ValidationError('Já existe um caixa aberto ou o valor é inválido.')
    session = CashSession.objects.create(opening=money(opening), opened_by=actor)
    audit(actor, 'Abertura de caixa físico', session, {'fundo': str(opening)})
    return session


@transaction.atomic
def close_cash(session_id, counted, notes, actor):
    session = CashSession.objects.select_for_update().get(pk=session_id)
    if session.closed_at:
        return session
    if counted < 0:
        raise ValidationError('A contagem não pode ser negativa.')
    session.expected_snapshot = session.expected
    session.counted = money(counted)
    session.notes = notes
    session.closed_at = timezone.now()
    session.closed_by = actor
    session.open_slot = None
    session.save()
    audit(actor, 'Fechamento de caixa físico', session, {'esperado': str(session.expected_snapshot), 'contado': str(counted), 'diferença': str(session.difference)})
    return session


def attach_cash(line):
    if line.method == 'cash' and line.settled_date:
        session = CashSession.objects.select_for_update().filter(open_slot=1).first()
        if session:
            line.cash_session = session
    return line


@transaction.atomic
def settle_ledger(line_id, method, actor):
    line = Ledger.objects.select_for_update().get(pk=line_id)
    if line.settled_date or line.voided:
        raise ValidationError('Lançamento já quitado ou anulado.')
    if method not in dict(Ledger.METHODS):
        raise ValidationError('Meio efetivo inválido.')
    # Um estorno não recebido não pode ser quitado pelo fluxo do original.
    line.method = method
    line.settled_date = timezone.localdate()
    attach_cash(line)
    line.save(update_fields=['method', 'settled_date', 'cash_session'])
    audit(actor, 'Quitação', line, {'valor': str(line.amount), 'meio': method})
    return line


@transaction.atomic
def cash_transfer(session_id, direction, amount, reason, actor):
    session = CashSession.objects.select_for_update().get(pk=session_id)
    amount = money(amount)
    if session.closed_at or amount <= 0 or direction not in ('withdraw', 'deposit') or not reason.strip():
        raise ValidationError('Transferência inválida ou caixa encerrado.')
    if direction == 'withdraw' and amount > session.expected:
        raise ValidationError('Sangria superior ao dinheiro esperado no caixa.')
    cash_amount = -amount if direction == 'withdraw' else amount
    key = uuid.uuid4()
    for method, value, cash in [('cash', cash_amount, session), ('bank', -cash_amount, None)]:
        Ledger.objects.create(label=f'{"Sangria" if direction == "withdraw" else "Reforço"} caixa #{session.pk} • {reason}', category='Transferência interna', amount=value, method=method, cash_session=cash, transfer_key=key, settled_date=timezone.localdate())
    audit(actor, 'Transferência interna de caixa', session, {'tipo': direction, 'valor': str(amount), 'motivo': reason})
