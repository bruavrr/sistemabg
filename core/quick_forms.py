import uuid
from django import forms
from .forms import PersonForm, DeviceForm, AccessoryForm, validate_upload, BaseModelForm
from .models import Person, Store


class QuickCustomerForm(PersonForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    class Meta(PersonForm.Meta):
        fields = ['name', 'document', 'email', 'phone', 'discovery_source', 'discovery_details']
        labels = {'name': 'Nome do cliente'}
        widgets = {'name': forms.TextInput(attrs={'autocomplete': 'name'}),
                   'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
                   'phone': forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel'}),
                   'document': forms.TextInput(attrs={'inputmode': 'numeric'})}


class OriginMixin:
    def configure_origin(self, field):
        self.fields[field].required = False
        self.fields[field].label = 'Origem já cadastrada (cliente ou fornecedor)'
        self.fields[field].empty_label = 'Selecionar origem existente'

    def clean(self):
        data = super().clean()
        field = self.origin_field
        if not data.get(field) and not data.get('origin_name'):
            self.add_error(field, 'Selecione a origem ou informe o nome do novo fornecedor abaixo.')
        if data.get(field) and data.get('origin_name'):
            self.add_error('origin_name', 'Use uma origem existente ou um novo fornecedor; não os dois.')
        if data.get('origin_name') and Person.objects.filter(name__iexact=data['origin_name']).exists():
            self.add_error('origin_name', 'Já existe contato com este nome. Selecione-o como origem para evitar duplicidade.')
        return data


class QuickDeviceForm(OriginMixin, DeviceForm):
    origin_field = 'origin'
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    origin_name = forms.CharField(label='Ou cadastrar novo fornecedor pelo nome', max_length=150, required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_origin('origin')


class QuickAccessoryForm(OriginMixin, AccessoryForm):
    origin_field = 'supplier'
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    origin_name = forms.CharField(label='Ou cadastrar novo fornecedor pelo nome', max_length=150, required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_origin('supplier')
        self.fields['quantity'].min_value = 1
    def clean_quantity(self):
        value = self.cleaned_data['quantity']
        if value < 1:
            raise forms.ValidationError('Para cadastrar e incluir na venda, informe pelo menos uma unidade disponível.')
        return value


class LogoForm(BaseModelForm):
    class Meta:
        model = Store
        fields = ['logo']
    def clean_logo(self):
        value = validate_upload(self.cleaned_data.get('logo'))
        if not value:
            raise forms.ValidationError('Selecione a imagem da logo em PNG ou JPG.')
        return value
