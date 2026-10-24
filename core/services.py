import calendar
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import *

CENT = Decimal('0.01')
def money(value): return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
def add_months(day, months):
    m = day.month - 1 + months
    y = day.year + m // 12
    m = m % 12 + 1
    return day.replace(year=y,month=m,day=min(day.day, calendar.monthrange(y,m)[1]))
def audit(actor, action, obj, details=None):
    Audit.objects.create(actor=actor, action=action, entity=obj.__class__.__name__, entity_id=obj.pk, details=details or {})
def store(): return Store.objects.first() or Store.objects.create()

def entry_ledger(device):
    if device.source == 'purchase' and device.acquisition_cost:
        Ledger.objects.create(label=f'Aquisição #{device.pk} {device.model}',category='Compra de estoque',amount=-device.acquisition_cost,person=device.origin,device=device,due_date=device.entry_date)
    if device.extra_cost:
        Ledger.objects.create(label=f'Despesas de entrada #{device.pk}',category='Despesa vinculada ao estoque',amount=-device.extra_cost,person=device.origin,device=device,due_date=device.entry_date)

@transaction.atomic
def create_device(form, actor, trade=False):
    d = form.save(commit=False)
    d.source = 'trade' if trade else 'purchase'
    d.status = 'available'
    d.checklist = {key:form.cleaned_data[key] for key in form.check_fields}
    d.save()
    for slot in (1,2):
        value = form.cleaned_data.get(f'imei{slot}')
        if value: Identifier.objects.create(device=d,slot=slot,value=value)
    photo = form.cleaned_data.get('photo')
    if photo: DevicePhoto.objects.create(device=d,image=photo)
    StockMove.objects.create(device=d,quantity=1,reason='Entrada por troca' if trade else 'Entrada por compra',actor=actor)
    entry_ledger(d)
    audit(actor,'Entrada',d,{'custo':str(d.cost),'origem':d.origin_id})
    return d

@transaction.atomic
def complete_sale(*, customer, devices, accessories, discount, payment_rows, actor, request_key, trade_form=None):
    existing = Sale.objects.filter(request_key=request_key).first()
    if existing: return existing
    device_ids = [d.pk for d in devices]
    if len(device_ids) != len(set(device_ids)): raise ValidationError('Aparelho repetido.')
    selected = list(Device.objects.select_for_update().filter(pk__in=device_ids))
    if not selected and not accessories: raise ValidationError('Selecione pelo menos um item.')
    if any(d.status not in ('available','reserved') for d in selected): raise ValidationError('Aparelho indisponível ou já vendido.')
    ids = [a.pk for a,q in accessories]
    if len(ids) != len(set(ids)): raise ValidationError('Acessório repetido: consolide a quantidade em uma linha.')
    gross = sum((d.price for d in selected), ZERO)
    costs = sum((d.cost for d in selected), ZERO)
    locked_accessories = []
    for a,qty in accessories:
        a = Accessory.objects.select_for_update().get(pk=a.pk)
        if qty <= 0 or a.quantity < qty: raise ValidationError(f'Estoque insuficiente: {a.name}.')
        gross += a.price * qty
        costs += a.cost * qty
        locked_accessories.append((a,qty))
    discount = money(discount)
    if discount < 0 or discount > gross: raise ValidationError('Desconto inválido.')
    total = gross - discount
    trade_value = trade_form.cleaned_data['acquisition_cost'] if trade_form else ZERO
    if trade_value > total: raise ValidationError('A avaliação da troca não pode superar o total da venda nesta versão.')
    if trade_form and trade_form.cleaned_data['origin'] != customer: raise ValidationError('A origem do aparelho da troca deve ser o cliente da venda.')
    if sum((p['amount'] for p in payment_rows), ZERO) != total - trade_value:
        raise ValidationError('A soma dos pagamentos deve ser igual ao total menos a avaliação da troca.')
    prepared = []
    for row in payment_rows:
        amount = money(row['amount'])
        if amount <= 0: raise ValidationError('Pagamento precisa ter valor positivo.')
        rate = row.get('card_rate') if row['method'] == 'card' else None
        if row['method'] == 'card' and (not rate or not rate.active): raise ValidationError('Configure e selecione a taxa da maquininha.')
        fee = money(amount * rate.percent / 100) if rate else ZERO
        prepared.append((row,rate,fee))
    st = store()
    trade = create_device(trade_form,actor,trade=True) if trade_form else None
    sale = Sale.objects.create(customer=customer,seller=actor,gross=gross,discount=discount,costs=costs,fees=sum((p[2] for p in prepared),ZERO),trade_device=trade,trade_value=trade_value,request_key=request_key,terms_snapshot=st.warranty_terms,store_snapshot={'name':st.name,'document':st.document,'address':st.address,'phone':st.phone,'logo':st.logo.name},customer_snapshot={'name':customer.name,'document':customer.document,'phone':customer.phone,'address':customer.address})
    for d in selected:
        updated = Device.objects.filter(pk=d.pk,status__in=['available','reserved']).update(status='sold')
        if not updated: raise ValidationError('Aparelho vendido por outra operação. Recarregue a página.')
        item = SaleItem.objects.create(sale=sale,device=d,description=f'{d.model} / {d.storage} / {d.color} / {d.get_condition_display()} / IMEI {d.imei1} / IMEI 2 {d.imei2} / Série {d.serial}',price=d.price,cost=d.cost)
        date = timezone.localdate(sale.created_at)
        Warranty.objects.create(item=item,provider='store' if d.condition == 'used' else 'apple',start=date,end=add_months(date,9) if d.condition == 'used' else None)
        StockMove.objects.create(device=d,quantity=-1,reason='Venda',sale=sale,actor=actor)
    for a,qty in locked_accessories:
        if not Accessory.objects.filter(pk=a.pk,quantity__gte=qty).update(quantity=F('quantity')-qty): raise ValidationError('Estoque alterado por outra operação.')
        SaleItem.objects.create(sale=sale,accessory=a,description=a.name,quantity=qty,price=a.price,cost=a.cost)
        StockMove.objects.create(accessory=a,quantity=-qty,reason='Venda',sale=sale,actor=actor)
    today = timezone.localdate()
    for row,rate,fee in prepared:
        pay = Payment.objects.create(sale=sale,method=row['method'],gross=row['amount'],fee=fee,net=row['amount']-fee,machine=rate.machine if rate else '',installments=rate.installments if rate else 1,rate=rate.percent if rate else 0)
        count = pay.installments
        installment = money(pay.net / count)
        for i in range(1,count+1):
            value = installment if i < count else pay.net - installment * (count-1)
            Ledger.objects.create(sale=sale,person=customer,label=f'Venda #{sale.pk} • {pay.get_method_display()} {pay.machine} • {i}/{count}',category='Recebimento de venda',amount=value,due_date=today+timedelta(days=rate.days*i) if rate else today,settled_date=None if rate else today)
    audit(actor,'Venda concluída',sale,{'total':str(sale.total),'resultado':str(sale.profit)})
    return sale

@transaction.atomic
def cancel_sale(sale_id, reason, actor):
    if not reason.strip(): raise ValidationError('Informe o motivo do cancelamento.')
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.status == 'cancelled': return sale
    if sale.trade_device:
        trade = Device.objects.select_for_update().get(pk=sale.trade_device_id)
        if trade.status != 'available' or trade.sale_items.filter(active=True).exists(): raise ValidationError('Aparelho da troca já movimentado. Regularize sua situação antes de cancelar.')
        trade.status='returned'; trade.save(update_fields=['status'])
        StockMove.objects.create(device=trade,quantity=-1,reason='Devolução da troca no cancelamento',sale=sale,actor=actor)
    for item in sale.items.select_related('device','accessory'):
        if item.device:
            Device.objects.filter(pk=item.device_id).update(status='available')
        if item.accessory:
            Accessory.objects.filter(pk=item.accessory_id).update(quantity=F('quantity')+item.quantity)
        StockMove.objects.create(device=item.device,accessory=item.accessory,quantity=item.quantity,reason='Cancelamento de venda',sale=sale,actor=actor)
        item.active=False; item.save(update_fields=['active'])
    today=timezone.localdate()
    for line in sale.ledger.all():
        if line.settled_date:
            Ledger.objects.create(label=f'Estorno: {line.label}',category='Estorno',amount=-line.amount,due_date=today,settled_date=None,person=line.person,sale=sale,reverses=line)
        else:
            line.voided=True; line.save(update_fields=['voided'])
    sale.status='cancelled'; sale.cancelled_at=timezone.now(); sale.cancel_reason=reason; sale.save(update_fields=['status','cancelled_at','cancel_reason'])
    audit(actor,'Venda cancelada',sale,{'motivo':reason})
    return sale
