"""Telas dos fluxos locais observados na referência em vídeo."""
import csv
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .forms import AccessoryLines, PersonForm
from .operations_forms import *
from .services import audit
from .workflows import *
from .views import admin_required


def form_page(request, form, title, hint=''):
    return render(request, 'core/form.html', {'form': form, 'title': title, 'hint': hint})


def show_error(request, exc):
    messages.error(request, ' '.join(exc.messages))


@login_required
def quotes(request):
    return render(request, 'core/quotes.html', {'items': Quote.objects.select_related('customer', 'seller', 'sale')[:200]})


@login_required
def quote_new(request):
    initial = {'request_key': uuid.uuid4(), 'valid_until': timezone.localdate() + timedelta(days=7)}
    form = QuoteForm(request.POST or None, initial=initial)
    lines = AccessoryLines(request.POST or None, prefix='acc')
    if request.method == 'POST':
        valid = form.is_valid()
        valid_lines = lines.is_valid()
        if valid and valid_lines:
            try:
                quote = create_quote(customer=form.cleaned_data['customer'], devices=list(form.cleaned_data['devices']), accessories=[(f.cleaned_data['accessory'], f.cleaned_data['quantity']) for f in lines if f.cleaned_data.get('accessory')], discount=form.cleaned_data['discount'], valid_until=form.cleaned_data['valid_until'], notes=form.cleaned_data['notes'], actor=request.user, request_key=form.cleaned_data['request_key'])
                return redirect('quote', quote.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
            except IntegrityError:
                form.add_error(None, 'Esta solicitação já foi registrada. Consulte os orçamentos.')
    return render(request, 'core/quote_form.html', {'form': form, 'lines': lines})


@login_required
def quote_detail(request, pk):
    return render(request, 'core/quote.html', {'quote': get_object_or_404(Quote.objects.select_related('customer', 'sale'), pk=pk)})


@login_required
@require_POST
def quote_status(request, pk):
    with transaction.atomic():
        quote = get_object_or_404(Quote.objects.select_for_update(), pk=pk)
        target = request.POST.get('status')
        allowed = {'draft': ('sent', 'approved', 'cancelled'), 'sent': ('approved', 'cancelled'), 'approved': ('cancelled',)}
        if target not in allowed.get(quote.status, ()):
            messages.error(request, 'Mudança de status inválida.')
        elif quote.expired and target != 'cancelled':
            messages.error(request, 'Orçamento vencido; cadastre uma proposta atualizada.')
        else:
            old = quote.status
            quote.status = target
            quote.save(update_fields=['status'])
            audit(request.user, 'Status de orçamento', quote, {'antes': old, 'depois': target})
    return redirect('quote', pk)


@login_required
def tools(request):
    return render(request, 'core/tools.html', {'rules': ValuationRule.objects.all(), 'valuations': Valuation.objects.select_related('person', 'actor')[:50]})


@login_required
def card_simulator(request):
    form = CardSimulatorForm(request.POST or None)
    result = None
    if request.method == 'POST' and form.is_valid():
        try:
            result = simulate_card(form.cleaned_data['amount'], form.cleaned_data['rate'], form.cleaned_data['mode'])
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'core/card_simulator.html', {'form': form, 'result': result})


@admin_required
def valuation_rule(request, pk=None):
    instance = get_object_or_404(ValuationRule, pk=pk) if pk else None
    form = ValuationRuleForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request.user, 'Regra de avaliação configurada', obj, {k: str(v) for k, v in form.cleaned_data.items()})
        return redirect('tools')
    return form_page(request, form, 'Tabela de avaliação de aparelhos', 'Use os valores reais definidos pela BG Store. A tabela não consulta preço de mercado, IMEI ou procedência.')


@login_required
def valuation_new(request):
    form = ValuationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            obj = save_valuation(form.cleaned_data, request.user)
            return redirect('valuation', obj.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(request, form, 'Avaliar aparelho recebido em troca', 'Avaliação manual com descontos cadastrados pela loja. Marque apenas os descontos aplicáveis após inspecionar o aparelho. Não faz consulta externa nem registra entrada no estoque.')


@login_required
def valuation_detail(request, pk):
    return render(request, 'core/valuation.html', {'valuation': get_object_or_404(Valuation.objects.select_related('person', 'actor'), pk=pk)})


@login_required
def service_orders(request):
    status = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()
    orders = ServiceOrder.objects.select_related('customer').filter(Q(customer__name__icontains=query) | Q(device_description__icontains=query) | Q(imei__icontains=query))
    if status:
        orders = orders.filter(status=status)
    cards = list(orders[:200])
    columns = [(value, label, [o for o in cards if o.status == value]) for value, label in ServiceOrder.STATUSES if value not in ('delivered', 'cancelled')]
    return render(request, 'core/service_orders.html', {'items': cards, 'columns': columns, 'statuses': ServiceOrder.STATUSES, 'status': status, 'q': query, 'kanban': request.GET.get('view') == 'kanban', 'delivered': ServiceOrder.objects.filter(status='delivered').count(), 'active_count': ServiceOrder.objects.filter(active=True).count()})


@login_required
def service_new(request):
    form = ServiceNewForm(request.POST or None, initial={'request_key': uuid.uuid4()})
    if request.method == 'POST' and form.is_valid():
        try:
            obj = create_service(form, request.user)
            return redirect('service', obj.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, 'Já existe OS ativa para este IMEI/aparelho ou esta solicitação já foi registrada.')
    return form_page(request, form, 'Receber ordem de serviço', 'Registre o relato e os itens recebidos. Não informe senhas de desbloqueio ou credenciais do cliente. Aparelho vinculado ao estoque ficará em manutenção até encerrar a OS.')


@login_required
def service_detail(request, pk):
    order = get_object_or_404(ServiceOrder.objects.select_related('customer'), pk=pk)
    form = ServiceUpdateForm(request.POST or None, instance=order)
    if request.method == 'POST':
        if not request.user.is_staff:
            raise PermissionDenied
        if form.is_valid():
            try:
                update_service(pk, form.cleaned_data, request.user)
                messages.success(request, 'Informações da OS atualizadas.')
                return redirect('service', pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    # ModelForm atualiza a instância em memória; recarregar evita exibir valores não salvos como definitivos.
    order.refresh_from_db()
    transitions = [(value, dict(ServiceOrder.STATUSES)[value]) for value in SERVICE_TRANSITIONS[order.status]]
    return render(request, 'core/service.html', {'order': order, 'form': form, 'part_form': PartUseForm(), 'transitions': transitions})


@admin_required
@require_POST
def service_transition(request, pk):
    try:
        transition_service(pk, request.POST.get('status', ''), request.POST.get('reason', '').strip()[:5000], request.user, request.POST.get('confirm_return') == 'on')
        messages.success(request, 'Etapa registrada. Na entrega, cobrança e custo de mão de obra ficam pendentes para conciliação no financeiro.')
    except ValidationError as exc:
        show_error(request, exc)
    return redirect('service', pk)


@admin_required
@require_POST
def service_part_use(request, pk):
    form = PartUseForm(request.POST)
    if form.is_valid():
        try:
            consume_part(pk, form.cleaned_data['part'].pk, form.cleaned_data['quantity'], request.user)
            messages.success(request, 'Peça aplicada e estoque atualizado.')
        except ValidationError as exc:
            show_error(request, exc)
    else:
        messages.error(request, 'Selecione a peça e uma quantidade inteira positiva.')
    return redirect('service', pk)


@login_required
def parts(request):
    return render(request, 'core/parts.html', {'items': ServicePart.objects.select_related('supplier'), 'moves': PartMove.objects.select_related('part', 'actor', 'order').order_by('-id')[:100], 'move_form': StockMoveForm()})


@admin_required
def part_new(request):
    form = ServicePartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            part = form.save()
            PartMove.objects.create(part=part, quantity=part.quantity, reason='Estoque inicial de peças', actor=request.user)
            if part.cost and part.quantity:
                Ledger.objects.create(label=f'Compra inicial de peças: {part.name}', category='Compra de estoque', amount=-part.cost * part.quantity, person=part.supplier)
            audit(request.user, 'Peça cadastrada', part)
        return redirect('parts')
    return form_page(request, form, 'Cadastrar peça de assistência', 'Este estoque é separado dos acessórios de venda. A compra gera uma conta a pagar pelo custo informado.')


@admin_required
@require_POST
def part_move(request, pk):
    form = StockMoveForm(request.POST)
    if form.is_valid():
        try:
            restock_part(pk, form.cleaned_data['quantity'], form.cleaned_data['unit_cost'], form.cleaned_data['reason'], request.user)
        except ValidationError as exc:
            show_error(request, exc)
    else:
        messages.error(request, 'Revise quantidade, custo e motivo da movimentação.')
    return redirect('parts')


@login_required
def agenda(request):
    today = timezone.localdate()
    try:
        anchor = date.fromisoformat(request.GET.get('date', today.isoformat()))
    except ValueError:
        anchor = today
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    tasks = list(Task.objects.filter(when__date__gte=monday, when__date__lte=sunday).select_related('person', 'sale', 'service_order'))
    days = [(monday + timedelta(days=i), [t for t in tasks if timezone.localdate(t.when) == monday + timedelta(days=i)]) for i in range(7)]
    overdue = Task.objects.filter(when__lt=timezone.now(), completed_at__isnull=True, cancelled=False).select_related('person')[:100]
    birthdays = Person.objects.filter(birth_date__month=anchor.month).order_by('birth_date__day', 'name')
    return render(request, 'core/agenda.html', {'days': days, 'anchor': anchor, 'previous': monday - timedelta(days=7), 'next': monday + timedelta(days=7), 'overdue': overdue, 'birthdays': birthdays, 'today': today})


@login_required
def task_new(request):
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.actor = request.user
            if not task.person_id:
                task.person = task.sale.customer if task.sale_id else (task.service_order.customer if task.service_order_id else None)
            task.save()
            audit(request.user, 'Tarefa agendada', task, {'quando': task.when.isoformat(), 'tipo': task.kind})
        return redirect('agenda')
    return form_page(request, form, 'Novo agendamento ou pós-venda', 'Agenda local no fuso de São Paulo. Não envia mensagens por WhatsApp, Instagram ou e-mail.')


@login_required
@require_POST
def task_complete(request, pk):
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        note = request.POST.get('note', '').strip()[:5000]
        if not note:
            messages.error(request, 'Registre o resultado do atendimento para concluir a tarefa.')
        elif not task.completed_at and not task.cancelled:
            task.completed_at = timezone.now()
            task.completion_note = note
            task.save(update_fields=['completed_at', 'completion_note'])
            audit(request.user, 'Tarefa concluída', task, {'resultado': note})
    return redirect('agenda')


@admin_required
def cash_sessions(request):
    form = OpenCashForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            session = open_cash(form.cleaned_data['opening'], request.user)
            return redirect('cash', session.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, 'Um caixa foi aberto por outra operação. Recarregue a lista.')
    return render(request, 'core/cash_sessions.html', {'items': CashSession.objects.select_related('opened_by', 'closed_by')[:100], 'active': CashSession.objects.filter(open_slot=1).first(), 'form': form})


@admin_required
def cash_detail(request, pk):
    session = get_object_or_404(CashSession, pk=pk)
    return render(request, 'core/cash.html', {'session': session, 'close_form': CloseCashForm(), 'transfer_form': CashTransferForm()})


@admin_required
@require_POST
def cash_close(request, pk):
    form = CloseCashForm(request.POST)
    if form.is_valid():
        try:
            close_cash(pk, form.cleaned_data['counted'], form.cleaned_data['notes'], request.user)
            messages.success(request, 'Fechamento preservado no histórico.')
        except ValidationError as exc:
            show_error(request, exc)
    else:
        messages.error(request, 'Informe a contagem válida e observações com até 5 mil caracteres.')
    return redirect('cash', pk)


@admin_required
@require_POST
def cash_move(request, pk):
    form = CashTransferForm(request.POST)
    if form.is_valid():
        try:
            cash_transfer(pk, form.cleaned_data['direction'], form.cleaned_data['amount'], form.cleaned_data['reason'], request.user)
        except ValidationError as exc:
            show_error(request, exc)
    else:
        messages.error(request, 'Transferência inválida.')
    return redirect('cash', pk)


@admin_required
def person_edit(request, pk):
    person = get_object_or_404(Person, pk=pk)
    form = PersonForm(request.POST or None, instance=person)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request.user, 'Contato atualizado', obj, {'campos': form.changed_data})
        return redirect('person', pk)
    return form_page(request, form, 'Editar contato', 'Documentos de vendas e propostas existentes preservam os dados registrados na emissão.')


@admin_required
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.status in ('sold', 'returned'):
        messages.error(request, 'Aparelho vendido ou devolvido não pode ser editado neste fluxo.')
        return redirect('device', pk)
    form = DeviceCommercialForm(request.POST or None, instance=device)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            current = Device.objects.select_for_update().get(pk=pk)
            if current.status in ('sold', 'returned'):
                messages.error(request, 'O aparelho foi vendido ou devolvido por outra operação.')
                return redirect('device', pk)
            changes = {}
            for key in ('price', 'physical', 'battery', 'replaced_parts', 'notes'):
                if getattr(current, key) != form.cleaned_data[key]:
                    changes[key] = {'antes': str(getattr(current, key)), 'depois': str(form.cleaned_data[key])}
                    setattr(current, key, form.cleaned_data[key])
            current.save(update_fields=['price', 'physical', 'battery', 'replaced_parts', 'notes'])
            audit(request.user, 'Aparelho atualizado', current, {'motivo': form.cleaned_data['reason'], 'alterações': changes})
        return redirect('device', pk)
    return form_page(request, form, 'Atualizar aparelho', 'Preço e informações da inspeção. IMEIs, origem e custos de entrada permanecem preservados para rastreabilidade.')


@login_required
def operations_document(request, kind, pk):
    classes = {'quote': Quote, 'service': ServiceOrder, 'label': Device}
    if kind not in classes:
        from django.http import Http404
        raise Http404
    obj = get_object_or_404(classes[kind], pk=pk)
    return render(request, 'core/operations_document.html', {'kind': kind, 'obj': obj})


def report_period(request):
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get('start', today.replace(day=1).isoformat()))
        end = date.fromisoformat(request.GET.get('end', today.isoformat()))
        if start > end:
            raise ValueError
    except ValueError:
        start, end = today.replace(day=1), today
        messages.error(request, 'Período inválido. Exibindo o mês atual.')
    return start, end


REPORTS = {'sales': 'Vendas e resultado', 'stock': 'Estoque detalhado', 'payments': 'Formas de pagamento e taxas', 'customers': 'Ranking de clientes', 'services': 'Ordens de serviço', 'finance': 'Movimentações financeiras'}


@admin_required
def reports(request):
    kind = request.GET.get('kind', 'sales')
    if kind not in REPORTS:
        kind = 'sales'
    start, end = report_period(request)
    sales = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=end).select_related('customer', 'seller')
    if request.GET.get('customer', '').isdigit():
        sales = sales.filter(customer_id=request.GET['customer'])
    if request.GET.get('seller', '').isdigit():
        sales = sales.filter(seller_id=request.GET['seller'])
    if request.GET.get('channel') in dict(Sale.CHANNELS):
        sales = sales.filter(channel=request.GET['channel'])
    active_sales = list(sales.filter(status='completed'))
    metrics = [('Faturamento de vendas', sum((s.total for s in active_sales), ZERO)), ('Resultado de vendas', sum((s.profit for s in active_sales), ZERO)), ('Ticket médio', money(sum((s.total for s in active_sales), ZERO) / len(active_sales)) if active_sales else ZERO), ('Taxas de cartão', sum((s.fees for s in active_sales), ZERO))]
    if kind == 'sales':
        headings = ['Venda', 'Data', 'Cliente', 'Vendedor', 'Canal', 'Status', 'Total R$', 'Custo R$', 'Taxas R$', 'Resultado R$']
        rows = [[s.pk, timezone.localtime(s.created_at).strftime('%d/%m/%Y %H:%M'), s.customer.name, s.seller.username, s.get_channel_display(), s.get_status_display(), s.total, s.costs, s.fees, s.profit if s.status == 'completed' else ZERO] for s in sales]
    elif kind == 'stock':
        headings = ['Tipo', 'Identificação', 'Modelo / produto', 'Armazenamento', 'Status', 'Quantidade', 'Custo unitário R$', 'Custo total R$', 'Preço unitário R$', 'Entrada']
        rows = [[d.get_condition_display(), d.imei1, d.model, d.storage, d.get_status_display(), 1, d.cost, d.cost, d.price, d.entry_date] for d in Device.objects.filter(status__in=['available', 'reserved', 'maintenance'])]
        rows += [['Acessório', a.pk, a.name, '', '', a.quantity, a.cost, a.cost * a.quantity, a.price, ''] for a in Accessory.objects.all()]
        rows += [['Peça de assistência', a.pk, a.name, '', '', a.quantity, a.cost, a.cost * a.quantity, a.price, ''] for a in ServicePart.objects.all()]
        metrics = [('Custo do estoque atual', sum((r[7] for r in rows), ZERO)), ('Valor potencial de venda', sum((r[8] * r[5] for r in rows), ZERO))]
    elif kind == 'payments':
        headings = ['Venda', 'Forma', 'Maquininha', 'Parcelas', 'Taxa %', 'Bruto R$', 'Taxas R$', 'Líquido R$']
        rows = [[p.sale_id, p.get_method_display(), p.machine, p.installments, p.rate, p.gross, p.fee, p.net] for p in Payment.objects.filter(sale__in=[s.pk for s in active_sales])]
        metrics = [('Bruto dos pagamentos', sum((r[5] for r in rows), ZERO)), ('Taxas', sum((r[6] for r in rows), ZERO)), ('Líquido previsto/recebido', sum((r[7] for r in rows), ZERO))]
    elif kind == 'customers':
        ranking = defaultdict(lambda: {'name': '', 'count': 0, 'total': ZERO})
        for sale in active_sales:
            entry = ranking[sale.customer_id]
            entry['name'] = sale.customer.name
            entry['count'] += 1
            entry['total'] += sale.total
        headings = ['Cliente', 'Quantidade de vendas', 'Total comprado R$', 'Ticket médio R$']
        rows = [[r['name'], r['count'], r['total'], money(r['total'] / r['count'])] for r in sorted(ranking.values(), key=lambda r: r['total'], reverse=True)]
    elif kind == 'services':
        orders = ServiceOrder.objects.filter(created_at__date__gte=start, created_at__date__lte=end).select_related('customer')
        if request.GET.get('customer', '').isdigit():
            orders = orders.filter(customer_id=request.GET['customer'])
        headings = ['OS', 'Cliente', 'Aparelho', 'Etapa', 'Total R$', 'Custos R$', 'Resultado R$', 'Previsão']
        rows = [[o.pk, o.customer.name, o.device_description, o.get_status_display(), o.total, o.cost, o.result if o.status == 'delivered' else ZERO, o.promised_date or ''] for o in orders]
        delivered = ServiceOrder.objects.filter(status='delivered', inventory_device__isnull=True, delivered_at__date__gte=start, delivered_at__date__lte=end)
        if request.GET.get('customer', '').isdigit():
            delivered = delivered.filter(customer_id=request.GET['customer'])
        delivered = list(delivered)
        metrics = [('Serviços entregues no período', sum((o.total for o in delivered), ZERO)), ('Resultado dos serviços entregues', sum((o.result for o in delivered), ZERO))]
    else:
        ledgers = Ledger.objects.filter(due_date__gte=start, due_date__lte=end).select_related('person')
        if request.GET.get('customer', '').isdigit():
            ledgers = ledgers.filter(person_id=request.GET['customer'])
        headings = ['Registro', 'Descrição', 'Categoria', 'Pessoa', 'Vencimento', 'Quitação', 'Meio', 'Valor R$', 'Situação']
        rows = [[l.pk, l.label, l.category, l.person.name if l.person else '', l.due_date, l.settled_date or '', l.get_method_display(), l.amount, 'Anulado' if l.voided else ('Quitado' if l.settled_date else 'Pendente')] for l in ledgers]
        settled = Ledger.objects.filter(voided=False, settled_date__gte=start, settled_date__lte=end)
        if request.GET.get('customer', '').isdigit():
            settled = settled.filter(person_id=request.GET['customer'])
        values = list(settled.values_list('amount', flat=True))
        metrics = [('Fluxo financeiro quitado no período', sum(values, ZERO))]
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="bgstore-{kind}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        def safe(value):
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                return "'" + value
            return value
        writer.writerow(headings)
        for row in rows:
            writer.writerow([safe(v) for v in row])
        audit(request.user, 'Relatório exportado', request.user, {'tipo': kind, 'inicio': str(start), 'fim': str(end), 'linhas': len(rows)})
        return response
    from django.contrib.auth import get_user_model
    query = request.GET.copy()
    query['format'] = 'csv'
    return render(request, 'core/reports.html', {'kind': kind, 'report_name': REPORTS[kind], 'reports': REPORTS, 'start': start, 'end': end, 'headings': headings, 'rows': rows, 'metrics': metrics, 'customers': Person.objects.all(), 'sellers': get_user_model().objects.filter(is_active=True), 'channels': Sale.CHANNELS, 'csv_query': query.urlencode()})
