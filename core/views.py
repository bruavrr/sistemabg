import hashlib, uuid, json
from datetime import timedelta, date
from decimal import Decimal
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.db.models import Q, F
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .forms import *
from .services import complete_sale, cancel_sale, create_device, audit, store as get_store

def admin_required(fn):
    @login_required
    @wraps(fn)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_staff: raise PermissionDenied
        return fn(request,*args,**kwargs)
    return wrapped

class LoginView(auth_views.LoginView):
    template_name='registration/login.html'
    def dispatch(self,request,*args,**kwargs):
        self.key=hashlib.sha256(request.POST.get('username','').strip().lower().encode()).hexdigest()
        if request.method=='POST':
            a=LoginAttempt.objects.filter(key=self.key).first()
            if a and a.failures>=5 and a.updated>timezone.now()-timedelta(minutes=15):
                return render(request,self.template_name,{'locked':True},status=429)
        return super().dispatch(request,*args,**kwargs)
    def form_invalid(self,form):
        a,_=LoginAttempt.objects.get_or_create(key=self.key)
        if a.updated<timezone.now()-timedelta(minutes=15): a.failures=0
        a.failures+=1; a.updated=timezone.now(); a.save()
        return super().form_invalid(form)
    def form_valid(self,form):
        LoginAttempt.objects.filter(key=self.key).delete()
        response=super().form_valid(form)
        audit(self.request.user,'Login',self.request.user)
        return response

@login_required
def dashboard(request):
    today=timezone.localdate()
    try:
        start=date.fromisoformat(request.GET.get('start',today.replace(day=1).isoformat()))
        end=date.fromisoformat(request.GET.get('end',today.isoformat()))
        if start>end: raise ValueError()
    except ValueError:
        messages.error(request,'Período inválido; exibindo o mês atual.'); start=today.replace(day=1); end=today
    sales=list(Sale.objects.filter(status='completed',created_at__date__gte=start,created_at__date__lte=end))
    stock=list(Device.objects.filter(status__in=['available','reserved','maintenance']))
    accessories=list(Accessory.objects.all())
    parts=list(ServicePart.objects.all())
    ledgers=list(Ledger.objects.filter(voided=False))
    settled=[l for l in ledgers if l.settled_date and start<=l.settled_date<=end]
    pending=[l for l in ledgers if not l.settled_date]
    cash=sum((l.amount for l in ledgers if l.settled_date and l.settled_date<=today),ZERO)
    excluded=['Compra de estoque','Estorno','Despesa vinculada ao estoque','Transferência interna','Custo de mão de obra']
    expenses=-sum((l.amount for l in settled if l.amount<0 and l.category not in excluded),ZERO)
    expenses-=sum((l.amount for l in settled if l.reverses_id and l.amount>0 and l.reverses.amount<0 and l.reverses.category not in excluded),ZERO)
    metrics=[('Faturamento no período',sum((s.total for s in sales),ZERO)),('Resultado das vendas',sum((s.profit for s in sales),ZERO)),('Despesas operacionais pagas',expenses),('Saldo de caixa atual',cash),('Contas a receber • total',sum((l.amount for l in pending if l.amount>0),ZERO)),('Contas a pagar • total',-sum((l.amount for l in pending if l.amount<0),ZERO)),('Custo do estoque atual',sum((d.cost for d in stock),ZERO)+sum((a.cost*a.quantity for a in accessories),ZERO)+sum((p.cost*p.quantity for p in parts),ZERO)),('Fluxo de caixa no período',sum((l.amount for l in settled),ZERO))]
    delivered=list(ServiceOrder.objects.filter(status='delivered',inventory_device__isnull=True,delivered_at__date__gte=start,delivered_at__date__lte=end))
    metrics += [('Serviços entregues no período',sum((o.total for o in delivered),ZERO)),('Resultado dos serviços',sum((o.result for o in delivered),ZERO))]
    warranties=[w for w in Warranty.objects.filter(item__sale__status='completed').select_related('item__device','item__sale') if w.expiry and today<=w.expiry<=today+timedelta(days=30)]
    return render(request,'core/dashboard.html',{'metrics':metrics,'count':len(sales),'stock_count':len(stock),'stale':[d for d in stock if d.entry_date<=today-timedelta(days=60)],'low':[a for a in accessories if a.quantity<=a.minimum],'warranties':warranties,'recent':sales[:6],'start':start,'end':end})

@login_required
def people(request):
    q=request.GET.get('q','')
    items=Person.objects.filter(Q(name__icontains=q)|Q(document__icontains=q)|Q(phone__icontains=q))[:200]
    return render(request,'core/people.html',{'items':items,'q':q})
@login_required
def person_new(request):
    form=PersonForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            p=form.save(); audit(request.user,'Cadastro',p)
        messages.success(request,'Contato cadastrado.'); return redirect('person',p.pk)
    return render(request,'core/form.html',{'form':form,'title':'Novo cliente ou fornecedor'})
@login_required
def person_detail(request,pk):
    p=get_object_or_404(Person,pk=pk)
    return render(request,'core/person.html',{'person':p,'sales':Sale.objects.filter(customer=p),'devices':Device.objects.filter(origin=p),'quotes':Quote.objects.filter(customer=p),'orders':ServiceOrder.objects.filter(customer=p),'tasks':Task.objects.filter(person=p),'services':ServiceRecord.objects.filter(warranty__item__sale__customer=p).select_related('warranty__item__sale')})

@login_required
def devices(request):
    q=request.GET.get('q',''); status=request.GET.get('status','')
    items=Device.objects.filter(Q(model__icontains=q)|Q(identifiers__value__icontains=q)|Q(serial__icontains=q)).distinct().select_related('origin')
    if status: items=items.filter(status=status)
    return render(request,'core/devices.html',{'items':items[:200],'q':q,'statuses':Device.STATUSES,'status':status})
@login_required
def device_new(request):
    form=DeviceForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        try:
            d=create_device(form,request.user)
            messages.success(request,'Entrada registrada. A compra foi lançada como conta a pagar; quite-a no financeiro quando houver pagamento.')
            return redirect('device',d.pk)
        except IntegrityError: form.add_error(None,'IMEI ou série já utilizado. Recarregue e revise os dados.')
    return render(request,'core/form.html',{'form':form,'title':'Entrada de aparelho','hint':'Compra de fornecedor: gera conta a pagar. Para troca/upgrade, use Nova venda. O checklist é manual; não fazemos consultas externas de IMEI.'})
@login_required
def device_detail(request,pk):
    d=get_object_or_404(Device,pk=pk)
    photo=PhotoForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and photo.is_valid():
        with transaction.atomic():
            p=photo.save(commit=False); p.device=d; p.save(); audit(request.user,'Foto anexada',d)
        return redirect('device',pk)
    return render(request,'core/device.html',{'device':d,'form':photo,'checklist':[(CHECKS.get(k,k),dict([('unchecked','Não verificado'),('ok','Verificado / aprovado'),('issue','Problema / restrição'),('na','Não se aplica')]).get(v,v)) for k,v in d.checklist.items()],'moves':StockMove.objects.filter(device=d),'statuses':[(v,l) for v,l in Device.STATUSES if v in ('available','reserved','maintenance')]})
@login_required
@require_POST
def device_status(request,pk):
    with transaction.atomic():
        d=get_object_or_404(Device.objects.select_for_update(),pk=pk)
        if ServiceOrder.objects.filter(inventory_device=d,active=True).exists():
            messages.error(request,'Encerre a OS vinculada antes de alterar o status deste aparelho.')
            return redirect('device',pk)
        new=request.POST.get('status')
        if d.status not in ('available','reserved','maintenance') or new not in ('available','reserved','maintenance'): raise PermissionDenied
        old=d.status; d.status=new; d.save(update_fields=['status'])
        StockMove.objects.create(device=d,quantity=0,reason=f'Status: {old} → {new}',actor=request.user)
        audit(request.user,'Status alterado',d,{'antes':old,'depois':new})
    return redirect('device',pk)

@login_required
def accessories(request):
    return render(request,'core/accessories.html',{'items':Accessory.objects.all()})
@admin_required
def accessory_new(request):
    form=AccessoryForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            a=form.save(); StockMove.objects.create(accessory=a,quantity=a.quantity,reason='Estoque inicial',actor=request.user); audit(request.user,'Cadastro',a)
            if a.quantity and a.cost: Ledger.objects.create(label=f'Compra inicial {a.name}',category='Compra de estoque',amount=-a.cost*a.quantity,person=a.supplier)
        return redirect('accessories')
    return render(request,'core/form.html',{'form':form,'title':'Cadastrar acessório'})
@admin_required
@require_POST
def accessory_move(request,pk):
    try:
        qty=int(request.POST.get('quantity','0')); reason=request.POST.get('reason','').strip()
        unit=Decimal(request.POST.get('unit_cost','0'))
        if qty==0 or not reason or not unit.is_finite() or unit<0 or unit.as_tuple().exponent < -2: raise ValueError()
        with transaction.atomic():
            a=get_object_or_404(Accessory.objects.select_for_update(),pk=pk)
            if a.quantity+qty<0: raise ValueError()
            if qty>0:
                a.cost=((a.cost*a.quantity+unit*qty)/(a.quantity+qty)).quantize(Decimal('.01'))
                if unit: Ledger.objects.create(label=f'Reposição {a.name}',category='Compra de estoque',amount=-unit*qty,person=a.supplier)
            a.quantity+=qty; a.save(update_fields=['quantity','cost'])
            StockMove.objects.create(accessory=a,quantity=qty,reason=reason,actor=request.user); audit(request.user,'Movimentação de estoque',a,{'quantidade':qty,'motivo':reason,'custo_unitario':str(unit)})
    except (ValueError,ArithmeticError): messages.error(request,'Movimentação inválida. Informe quantidade inteira, motivo, custo com até duas casas e mantenha estoque não negativo.')
    return redirect('accessories')

@login_required
def sales(request): return render(request,'core/sales.html',{'items':Sale.objects.select_related('customer','seller')[:200]})
@login_required
def sale_new(request):
    initial={'request_key':uuid.uuid4()}
    accessory_initial=[]
    trade_initial={}
    quote=None
    if request.method=='GET' and request.GET.get('quote','').isdigit():
        quote=get_object_or_404(Quote,pk=request.GET['quote'])
        if quote.sale_id: return redirect('sale',quote.sale_id)
        if quote.expired or quote.status=='cancelled':
            messages.error(request,'Orçamento vencido ou cancelado. Gere uma nova proposta.')
            return redirect('quote',quote.pk)
        initial.update(customer=quote.customer_id,quote=quote.pk,discount=quote.discount,notes=quote.notes,devices=[i['id'] for i in quote.items if i['kind']=='device'])
        accessory_initial=[{'accessory':i['id'],'quantity':i['quantity']} for i in quote.items if i['kind']=='accessory']
    if request.method=='GET' and request.GET.get('valuation','').isdigit():
        valuation=get_object_or_404(Valuation,pk=request.GET['valuation'])
        initial['trade']=True
        if valuation.person_id: initial['customer']=valuation.person_id
        trade_initial={'model':valuation.snapshot['model'],'storage':valuation.snapshot['storage'],'acquisition_cost':valuation.suggested,'origin':valuation.person_id,'condition':'used','notes':f'Avaliação manual #{valuation.pk}. '+valuation.notes}
    form=SaleForm(request.POST or None,initial=initial)
    lines=AccessoryLines(request.POST or None,prefix='acc',initial=accessory_initial)
    lines.extra=1
    payments=PaymentLines(request.POST or None,prefix='pay')
    payments.extra=2
    wants_trade=request.POST.get('trade')=='on' if request.method=='POST' else bool(initial.get('trade'))
    trade_form=DeviceForm(request.POST if request.method=='POST' and wants_trade else None,request.FILES if wants_trade else None,prefix='trade',initial=trade_initial)
    if request.method=='POST':
        valid=form.is_valid(); valid_lines=lines.is_valid(); valid_pay=payments.is_valid(); valid_trade=trade_form.is_valid() if wants_trade else True
        if valid and valid_lines and valid_pay and valid_trade:
            try:
                args=dict(customer=form.cleaned_data['customer'],devices=list(form.cleaned_data['devices']),accessories=[(f.cleaned_data['accessory'],f.cleaned_data['quantity']) for f in lines if f.cleaned_data.get('accessory')],discount=form.cleaned_data['discount'],payment_rows=[f.cleaned_data for f in payments if f.cleaned_data.get('method')],actor=request.user,request_key=form.cleaned_data['request_key'],trade_form=trade_form if wants_trade else None,channel=form.cleaned_data.get('channel') or 'store',notes=form.cleaned_data.get('notes',''))
                if form.cleaned_data.get('quote'):
                    from .workflows import sell_quote
                    sale=sell_quote(form.cleaned_data['quote'].pk,**args)
                else:
                    sale=complete_sale(**args)
                messages.success(request,'Venda concluída. Estoque, garantia e financeiro atualizados juntos.'); return redirect('sale',sale.pk)
            except ValidationError as e: form.add_error(None,e)
            except (IntegrityError,OperationalError): form.add_error(None,'Conflito de estoque, duplicidade ou operação simultânea. Recarregue e confira o histórico antes de tentar de novo.')
    price_data={'devices':{str(d.pk):{'label':f'{d} · IMEI {d.imei1}','price':int(d.price*100)} for d in Device.objects.filter(status__in=['available','reserved'])},'accessories':{str(a.pk):{'label':a.name,'price':int(a.price*100)} for a in Accessory.objects.all()},'rates':{str(r.pk):int(r.percent*1000) for r in CardRate.objects.filter(active=True)}}
    from .quick_forms import QuickCustomerForm, QuickDeviceForm, QuickAccessoryForm
    quick_forms={'quick_customer':QuickCustomerForm(prefix='quick-customer'),'quick_device':QuickDeviceForm(prefix='quick-device'),'quick_accessory':QuickAccessoryForm(prefix='quick-accessory')}
    return render(request,'core/sale_form.html',{'form':form,'lines':lines,'payments':payments,'trade_form':trade_form,'wants_trade':wants_trade,'catalog':Device.objects.filter(status__in=['available','reserved']),'acc_catalog':Accessory.objects.all(),'price_data':price_data,'quote':quote,'customer_data':{str(p.pk):{'document':p.document,'email':p.email,'phone':p.phone,'discovery_label':p.get_discovery_source_display()} for p in Person.objects.all()},**quick_forms})
@login_required
def sale_detail(request,pk):
    return render(request,'core/sale.html',{'sale':get_object_or_404(Sale.objects.select_related('customer','seller'),pk=pk)})
@admin_required
@require_POST
def sale_cancel(request,pk):
    try:
        cancel_sale(pk,request.POST.get('reason',''),request.user)
        messages.success(request,'Venda cancelada. Estornos de valores já recebidos ficam a pagar até a devolução efetiva; contas ainda não recebidas foram anuladas.')
    except ValidationError as e: messages.error(request,' '.join(e.messages))
    return redirect('sale',pk)

@admin_required
def finance(request):
    items=Ledger.objects.select_related('person','sale','service_order','cash_session')
    direction=request.GET.get('direction','')
    status=request.GET.get('status','')
    q=request.GET.get('q','').strip()
    if direction=='in': items=items.filter(amount__gt=0)
    if direction=='out': items=items.filter(amount__lt=0)
    if status=='pending': items=items.filter(settled_date__isnull=True,voided=False)
    if status=='settled': items=items.filter(settled_date__isnull=False,voided=False)
    if status=='voided': items=items.filter(voided=True)
    if q: items=items.filter(Q(label__icontains=q)|Q(person__name__icontains=q)|Q(category__icontains=q))
    return render(request,'core/finance.html',{'items':items[:300],'methods':Ledger.METHODS,'direction':direction,'status':status,'q':q})
@admin_required
def ledger_new(request):
    form=LedgerForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            line=form.save(commit=False)
            if form.cleaned_data['direction']=='out': line.amount=-line.amount
            line.save(); audit(request.user,'Lançamento financeiro',line,{'valor':str(line.amount),'categoria':line.category})
        return redirect('finance')
    return render(request,'core/form.html',{'form':form,'title':'Novo lançamento financeiro','hint':'Para compras de estoque já registradas, quite o lançamento existente; não crie uma segunda despesa.'})
@admin_required
@require_POST
def ledger_settle(request,pk):
    from .workflows import settle_ledger
    line=get_object_or_404(Ledger,pk=pk)
    try:
        settle_ledger(pk,request.POST.get('method') or line.method,request.user)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
    return redirect('finance')
@admin_required
@require_POST
def ledger_reverse(request,pk):
    reason=request.POST.get('reason','').strip()
    with transaction.atomic():
        line=get_object_or_404(Ledger.objects.select_for_update(),pk=pk)
        if line.sale_id or line.device_id or line.service_order_id or line.transfer_key or line.reverses_id or line.category=='Compra de estoque':
            messages.error(request,'Lançamento vinculado: use o cancelamento da venda; compras de estoque exigem conciliação manual por lançamento identificado.')
        elif not reason or line.voided or Ledger.objects.filter(reverses=line).exists(): messages.error(request,'Informe o motivo; este lançamento não pode ter sido anulado ou estornado.')
        else:
            if line.settled_date: Ledger.objects.create(label=f'Estorno: {line.label} — {reason}',category='Estorno',amount=-line.amount,reverses=line)
            else: line.voided=True; line.save(update_fields=['voided'])
            audit(request.user,'Estorno/anulação',line,{'motivo':reason})
    return redirect('finance')

@login_required
def warranties(request):
    return render(request,'core/warranties.html',{'items':Warranty.objects.filter(item__sale__status='completed').select_related('item__device','item__sale__customer')})
@login_required
def warranty_detail(request,pk):
    w=get_object_or_404(Warranty.objects.select_related('item__sale','item__device'),pk=pk)
    form=WarrantyForm(request.POST or None,request.FILES or None,instance=w)
    if request.method=='POST':
        if not request.user.is_staff: raise PermissionDenied
        if form.is_valid():
            with transaction.atomic():
                form.save(); audit(request.user,'Garantia atualizada',w,{'ativacao':str(w.activation),'vencimento_confirmado':str(w.confirmed_end),'fonte':w.confirmation})
            return redirect('warranty',pk)
    return render(request,'core/warranty.html',{'warranty':w,'form':form})
@login_required
@require_POST
def warranty_service(request,pk):
    w=get_object_or_404(Warranty,pk=pk)
    description=request.POST.get('description','').strip()
    if not description or len(description)>10000: messages.error(request,'Descreva o atendimento em até 10 mil caracteres.')
    else:
        with transaction.atomic():
            s=ServiceRecord.objects.create(warranty=w,description=description,actor=request.user); audit(request.user,'Atendimento registrado',s)
    return redirect('warranty',pk)

@admin_required
def settings_view(request):
    form=StoreForm(request.POST or None,request.FILES or None,instance=get_store())
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(); audit(request.user,'Configurações atualizadas',obj,{'campos':form.changed_data})
        messages.success(request,'Configurações salvas.'); return redirect('settings')
    return render(request,'core/settings.html',{'form':form,'rates':CardRate.objects.all()})
@admin_required
def rate_new(request,pk=None):
    instance=get_object_or_404(CardRate,pk=pk) if pk else None
    form=CardRateForm(request.POST or None,instance=instance)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic(): obj=form.save(); audit(request.user,'Taxa configurada',obj,{'percentual':str(obj.percent),'parcelas':obj.installments,'maquininha':obj.machine})
        return redirect('settings')
    return render(request,'core/form.html',{'form':form,'title':'Configurar taxa de cartão','hint':'Use a taxa real contratada. A previsão considera parcelas com intervalo de dias informado; confirme as datas com sua operadora.'})
@login_required
def modules(request): return render(request,'core/modules.html')
@admin_required
def audit_view(request): return render(request,'core/audit.html',{'items':Audit.objects.select_related('actor')[:300],'moves':StockMove.objects.select_related('actor','device','accessory')[:100]})
@admin_required
def export_data(request):
    classes=[Store,Person,Device,Identifier,DevicePhoto,Accessory,Sale,SaleItem,CardRate,Payment,Ledger,StockMove,Warranty,ServiceRecord,Audit,Quote,ValuationRule,Valuation,ServicePart,ServiceOrder,PartUse,PartMove,ServiceEvent,Task,CashSession]
    payload={m.__name__:json.loads(serializers.serialize('json',m.objects.all())) for m in classes}
    audit(request.user,'Exportação dos dados',request.user)
    response=HttpResponse(json.dumps(payload,ensure_ascii=False,indent=2),content_type='application/json')
    response['Content-Disposition']='attachment; filename="bgstore-export.json"'
    return response
@login_required
def private_file(request,path):
    root=Path(settings.MEDIA_ROOT).resolve(); target=(root/path).resolve()
    if not target.is_relative_to(root) or not target.is_file(): raise Http404
    response=FileResponse(target.open('rb'),as_attachment=True,filename=target.name)
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store'
    return response
@login_required
def document(request,kind,pk):
    if kind=='entry': return render(request,'core/document.html',{'kind':kind,'device':get_object_or_404(Device,pk=pk),'check_labels':CHECKS})
    if kind not in ('sale','warranty'): raise Http404
    return render(request,'core/document.html',{'kind':kind,'sale':get_object_or_404(Sale,pk=pk)})
