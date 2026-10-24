import re, uuid
from decimal import Decimal
from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from .models import *

class DateInput(forms.DateInput): input_type='date'
class BaseModelForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            if isinstance(field,forms.DateField): field.widget=DateInput(format='%Y-%m-%d')
            if isinstance(field,forms.DecimalField): field.localize=False

def validate_upload(f):
    if f and f.size > 8*1024*1024: raise ValidationError('Arquivo limitado a 8 MB.')
    return f

class PersonForm(BaseModelForm):
    class Meta:
        model=Person
        fields=['name','kind','document','phone','email','address']
    def clean_document(self):
        value=re.sub(r'\D','',self.cleaned_data['document'])
        if not value: return ''
        if len(value) not in (11,14) or len(set(value))==1: raise ValidationError('CPF/CNPJ inválido.')
        nums=list(map(int,value))
        def digit(base,weights):
            r=sum(n*w for n,w in zip(base,weights))%11
            return 0 if r<2 else 11-r
        if len(nums)==11:
            valid=nums[9]==digit(nums[:9],range(10,1,-1)) and nums[10]==digit(nums[:10],range(11,1,-1))
        else:
            valid=nums[12]==digit(nums[:12],[5,4,3,2,9,8,7,6,5,4,3,2]) and nums[13]==digit(nums[:13],[6,5,4,3,2,9,8,7,6,5,4,3,2])
        if not valid: raise ValidationError('Dígitos verificadores do CPF/CNPJ inválidos.')
        return value

CHECKS={'screen':'Tela','touch':'Toque','cameras':'Câmeras','biometrics':'Face ID / Touch ID','microphone':'Microfone','speakers':'Alto-falantes','charging':'Carregamento','connectivity':'Conectividade','buttons':'Botões','battery_test':'Teste da bateria','physical_test':'Estado físico','icloud':'iCloud / Buscar','provenance':'Procedência e restrições (verificação manual)'}
class DeviceForm(BaseModelForm):
    imei1=forms.RegexField(r'^[0-9]{15}$',label='IMEI 1 (15 dígitos)')
    imei2=forms.RegexField(r'^[0-9]{15}$',label='IMEI 2 (opcional)',required=False)
    photo=forms.ImageField(label='Foto inicial (até 8 MB)',required=False)
    check_fields=list(CHECKS)
    class Meta:
        model=Device
        fields=['model','storage','color','condition','serial','battery','physical','replaced_parts','notes','origin','entry_date','acquisition_cost','extra_cost','price','invoice']
        widgets={k:forms.Textarea(attrs={'rows':2}) for k in ['physical','replaced_parts','notes']}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for key,label in CHECKS.items(): self.fields[key]=forms.ChoiceField(label=label,choices=[('unchecked','Não verificado'),('ok','Verificado / aprovado'),('issue','Problema / restrição'),('na','Não se aplica')])
    def clean(self):
        data=super().clean()
        values=[data.get('imei1'),data.get('imei2')]
        if values[0] and values[0]==values[1]: self.add_error('imei2','IMEIs devem ser diferentes.')
        for key in ['imei1','imei2']:
            if data.get(key) and Identifier.objects.filter(value=data[key]).exists(): self.add_error(key,'IMEI já cadastrado, inclusive em outro slot.')
        return data
    def clean_serial(self): return self.cleaned_data.get('serial','').strip().upper()
    clean_photo=lambda self: validate_upload(self.cleaned_data.get('photo'))
    clean_invoice=lambda self: validate_upload(self.cleaned_data.get('invoice'))

class AccessoryForm(BaseModelForm):
    class Meta:
        model=Accessory
        fields=['name','category','compatibility','supplier','cost','price','quantity','minimum']
class SaleForm(forms.Form):
    customer=forms.ModelChoiceField(Person.objects.all(),label='Cliente')
    devices=forms.ModelMultipleChoiceField(Device.objects.filter(status__in=['available','reserved']),required=False,label='Aparelhos (Ctrl/Cmd para selecionar vários)')
    discount=forms.DecimalField(label='Desconto total (R$)',max_digits=14,decimal_places=2,min_value=0,initial=0)
    trade=forms.BooleanField(label='Esta venda inclui aparelho recebido em troca',required=False)
    request_key=forms.UUIDField(widget=forms.HiddenInput)
class AccessoryLine(forms.Form):
    accessory=forms.ModelChoiceField(Accessory.objects.all(),label='Acessório',required=False)
    quantity=forms.IntegerField(label='Quantidade',min_value=1,required=False)
    def clean(self):
        d=super().clean()
        if d.get('accessory') and not d.get('quantity'): self.add_error('quantity','Informe a quantidade.')
        if d.get('quantity') and not d.get('accessory'): self.add_error('accessory','Selecione o produto.')
        return d
class PaymentLine(forms.Form):
    method=forms.ChoiceField(label='Forma de pagamento',choices=[('','Não usar esta linha'),('pix','Pix'),('cash','Dinheiro'),('card','Cartão')],required=False)
    amount=forms.DecimalField(label='Valor bruto (R$)',max_digits=14,decimal_places=2,min_value=Decimal('0.01'),required=False)
    card_rate=forms.ModelChoiceField(CardRate.objects.filter(active=True),label='Maquininha / parcelas / taxa configurada',required=False)
    def clean(self):
        d=super().clean()
        if d.get('method') and not d.get('amount'): self.add_error('amount','Informe o valor.')
        if d.get('amount') and not d.get('method'): self.add_error('method','Informe o meio de pagamento.')
        if d.get('method')=='card' and not d.get('card_rate'): self.add_error('card_rate','Configure uma taxa antes de vender no cartão.')
        return d
AccessoryLines=formset_factory(AccessoryLine,extra=4,max_num=20,validate_max=True)
PaymentLines=formset_factory(PaymentLine,extra=4,max_num=20,validate_max=True)
class LedgerForm(BaseModelForm):
    direction=forms.ChoiceField(label='Tipo',choices=[('out','Despesa / conta a pagar'),('in','Outra entrada / conta a receber')])
    class Meta:
        model=Ledger
        fields=['label','category','amount','due_date','person']
        labels={'amount':'Valor positivo (R$)'}
    def clean_amount(self):
        a=self.cleaned_data['amount']
        if a<=0: raise ValidationError('Informe um valor positivo.')
        return a
class CardRateForm(BaseModelForm):
    class Meta:
        model=CardRate
        fields=['machine','installments','percent','days','active']
class StoreForm(BaseModelForm):
    class Meta:
        model=Store
        fields=['name','document','address','phone','logo','warranty_terms']
        widgets={'warranty_terms':forms.Textarea(attrs={'rows':7})}
    clean_logo=lambda self:validate_upload(self.cleaned_data.get('logo'))
class WarrantyForm(BaseModelForm):
    class Meta:
        model=Warranty
        fields=['activation','confirmed_end','confirmation','signed_document']
    def clean(self):
        d=super().clean()
        if d.get('confirmed_end') and not d.get('confirmation'): self.add_error('confirmation','Identifique a fonte real da confirmação de cobertura.')
        return d
    clean_signed_document=lambda self:validate_upload(self.cleaned_data.get('signed_document'))
class PhotoForm(BaseModelForm):
    class Meta:
        model=DevicePhoto
        fields=['image']
    clean_image=lambda self:validate_upload(self.cleaned_data.get('image'))
