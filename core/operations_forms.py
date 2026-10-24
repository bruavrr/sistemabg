import uuid
from django import forms
from django.utils import timezone
from .models import *
from .forms import BaseModelForm, SaleForm


class QuoteForm(SaleForm):
    valid_until = forms.DateField(label='Válido até', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ('trade', 'quote', 'channel'):
            self.fields.pop(key, None)
    def clean_valid_until(self):
        value = self.cleaned_data['valid_until']
        if value < timezone.localdate():
            raise forms.ValidationError('Validade anterior a hoje.')
        return value


class ValuationRuleForm(BaseModelForm):
    class Meta:
        model = ValuationRule
        fields = ['model', 'storage', 'maximum', 'battery_discount', 'screen_discount', 'wear_discount', 'active']


class ValuationForm(BaseModelForm):
    rule = forms.ModelChoiceField(ValuationRule.objects.filter(active=True), label='Tabela cadastrada pela loja')
    battery_issue = forms.BooleanField(label='Aplicar desconto de bateria', required=False)
    screen_issue = forms.BooleanField(label='Aplicar desconto de tela', required=False)
    wear_issue = forms.BooleanField(label='Aplicar desconto por marcas/detalhes', required=False)
    class Meta:
        model = Valuation
        fields = ['rule', 'person', 'notes']


class CardSimulatorForm(forms.Form):
    amount = forms.DecimalField(label='Valor (R$)', max_digits=14, decimal_places=2, min_value=Decimal('.01'))
    rate = forms.ModelChoiceField(CardRate.objects.filter(active=True), label='Maquininha e taxa contratada')
    mode = forms.ChoiceField(label='Objetivo', choices=[('gross', 'Calcular líquido a partir do valor cobrado'), ('net', 'Calcular cobrança para receber o líquido desejado')])


class ServiceNewForm(BaseModelForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    imei = forms.RegexField(r'^[0-9]{15}$', label='IMEI (opcional)', required=False)
    class Meta:
        model = ServiceOrder
        fields = ['customer', 'device_description', 'imei', 'serial', 'inventory_device', 'complaint', 'received_condition', 'technician', 'promised_date', 'labor_price', 'labor_cost', 'request_key']
        widgets = {'complaint': forms.Textarea(attrs={'rows': 3}), 'received_condition': forms.Textarea(attrs={'rows': 3})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inventory_device'].label = 'Manutenção interna: aparelho da loja (opcional; não gera cobrança)'
        self.fields['inventory_device'].queryset = Device.objects.filter(status__in=['available', 'maintenance']).exclude(serviceorder__active=True)


class ServiceUpdateForm(BaseModelForm):
    class Meta:
        model = ServiceOrder
        fields = ['diagnosis', 'work_done', 'technician', 'approval_note', 'approved_limit', 'promised_date', 'labor_price', 'labor_cost']
        widgets = {k: forms.Textarea(attrs={'rows': 3}) for k in ['diagnosis', 'work_done', 'approval_note']}


class PartUseForm(forms.Form):
    part = forms.ModelChoiceField(ServicePart.objects.all(), label='Peça do estoque')
    quantity = forms.IntegerField(label='Quantidade aplicada', min_value=1)


class ServicePartForm(BaseModelForm):
    class Meta:
        model = ServicePart
        fields = ['name', 'compatibility', 'supplier', 'cost', 'price', 'quantity', 'minimum']


class StockMoveForm(forms.Form):
    quantity = forms.IntegerField(label='Quantidade (negativa para baixa)')
    unit_cost = forms.DecimalField(label='Custo unitário da entrada', max_digits=14, decimal_places=2, min_value=0, initial=0)
    reason = forms.CharField(label='Motivo', max_length=180)


class TaskForm(BaseModelForm):
    class Meta:
        model = Task
        fields = ['title', 'kind', 'person', 'sale', 'service_order', 'when', 'notes']
        widgets = {'when': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}), 'notes': forms.Textarea(attrs={'rows': 3})}
    def clean(self):
        data = super().clean()
        person, sale, order = data.get('person'), data.get('sale'), data.get('service_order')
        if person and ((sale and sale.customer_id != person.pk) or (order and order.customer_id != person.pk)):
            raise forms.ValidationError('O contato deve ser o cliente da venda/OS vinculada.')
        if sale and order and sale.customer_id != order.customer_id:
            raise forms.ValidationError('Venda e OS pertencem a clientes diferentes.')
        return data


class OpenCashForm(forms.Form):
    opening = forms.DecimalField(label='Dinheiro físico contado na abertura (R$)', max_digits=14, decimal_places=2, min_value=0)


class CloseCashForm(forms.Form):
    counted = forms.DecimalField(label='Dinheiro físico contado no fechamento (R$)', max_digits=14, decimal_places=2, min_value=0)
    notes = forms.CharField(label='Observações / justificativa da diferença', widget=forms.Textarea(attrs={'rows': 2}), required=False, max_length=5000)


class CashTransferForm(forms.Form):
    direction = forms.ChoiceField(label='Movimento', choices=[('withdraw', 'Sangria: caixa → banco'), ('deposit', 'Reforço: banco → caixa')])
    amount = forms.DecimalField(label='Valor (R$)', max_digits=14, decimal_places=2, min_value=Decimal('.01'))
    reason = forms.CharField(label='Motivo / referência', max_length=160)


class DeviceCommercialForm(BaseModelForm):
    reason = forms.CharField(label='Motivo da alteração', max_length=300)
    class Meta:
        model = Device
        fields = ['price', 'physical', 'battery', 'replaced_parts', 'notes']
        widgets = {k: forms.Textarea(attrs={'rows': 2}) for k in ['physical', 'replaced_parts', 'notes']}
