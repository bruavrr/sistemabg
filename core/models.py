from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.conf import settings
from django.utils import timezone

ZERO = Decimal('0.00')
MONEY = dict(max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
def today(): return timezone.localdate()

class Store(models.Model):
    name = models.CharField('Nome', max_length=120, default='BG Store')
    document = models.CharField('CPF/CNPJ da loja', max_length=20, blank=True)
    address = models.CharField('Endereço', max_length=250, blank=True)
    phone = models.CharField('Telefone', max_length=30, blank=True)
    logo = models.ImageField('Logo', upload_to='brand/', blank=True)
    followup_days = models.PositiveSmallIntegerField('Dias para lembrete local de pós-venda (0 desativa)', default=0, validators=[MaxValueValidator(365)])
    warranty_terms = models.TextField('Minuta dos termos de garantia', default='MINUTA PARA REVISÃO ANTES DO USO. A BG Store oferece nove meses de garantia para aparelhos seminovos, contados da data da venda. Para aparelhos lacrados, a garantia de um ano é oferecida pelo fabricante Apple, sujeita à verificação da cobertura e de suas datas. A cobertura Apple não foi confirmada por este sistema. Este documento não afasta os direitos legais do consumidor. Descreva aqui, após revisão profissional, o procedimento de atendimento e as condições aplicáveis.')

class Person(models.Model):
    DISCOVERY = [('instagram','Instagram'),('whatsapp','WhatsApp'),('google','Google'),('referral','Indicação'),('walk_in','Passou pela loja'),('returning','Já era cliente'),('other','Outro')]
    discovery_source = models.CharField('Como conheceu a BG Store?', max_length=20, choices=DISCOVERY, blank=True)
    discovery_details = models.CharField('Detalhes da indicação / outro canal', max_length=200, blank=True)
    name = models.CharField('Nome', max_length=150)
    kind = models.CharField('Tipo', max_length=12, choices=[('customer','Cliente'),('supplier','Fornecedor'),('both','Ambos')], default='customer')
    document = models.CharField('CPF/CNPJ (opcional)', max_length=14, blank=True)
    phone = models.CharField('Telefone', max_length=30, blank=True)
    email = models.EmailField('E-mail', blank=True)
    birth_date = models.DateField('Data de nascimento (opcional)', null=True, blank=True)
    address = models.CharField('Endereço', max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['document'], condition=~Q(document=''), name='unique_person_document')]
    def __str__(self): return self.name

class Device(models.Model):
    CONDITIONS = [('sealed','Lacrado'),('used','Seminovo')]
    STATUSES = [('available','Disponível'),('reserved','Reservado'),('sold','Vendido'),('maintenance','Em manutenção'),('returned','Devolvido')]
    model = models.CharField('Modelo', max_length=100)
    storage = models.CharField('Armazenamento', max_length=30)
    color = models.CharField('Cor', max_length=50)
    condition = models.CharField('Condição', max_length=10, choices=CONDITIONS)
    serial = models.CharField('Número de série', max_length=80, blank=True)
    battery = models.PositiveSmallIntegerField('Saúde da bateria (%)', null=True, blank=True, validators=[MaxValueValidator(100)])
    physical = models.TextField('Estado de conservação', blank=True)
    replaced_parts = models.TextField('Peças substituídas', blank=True)
    notes = models.TextField('Observações', blank=True)
    origin = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Fornecedor/cliente de origem')
    entry_date = models.DateField('Data de entrada', default=today)
    acquisition_cost = models.DecimalField('Custo de aquisição / avaliação da troca', **MONEY)
    extra_cost = models.DecimalField('Despesas adicionais', **MONEY)
    price = models.DecimalField('Preço de venda', **MONEY)
    status = models.CharField('Status', max_length=15, choices=STATUSES, default='available')
    source = models.CharField('Origem', max_length=10, choices=[('purchase','Compra'),('trade','Troca/upgrade')], default='purchase')
    invoice = models.FileField('Nota fiscal de origem (PDF ou imagem)', upload_to='invoices/', blank=True, validators=[FileExtensionValidator(['pdf','jpg','jpeg','png'])])
    checklist = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-id']
        constraints = [models.UniqueConstraint(fields=['serial'], condition=~Q(serial=''), name='unique_serial')]
    def __str__(self): return f'{self.model} • {self.storage} • #{self.pk}'
    @property
    def cost(self): return self.acquisition_cost + self.extra_cost
    @property
    def imei1(self): return self.identifiers.filter(slot=1).values_list('value',flat=True).first() or ''
    @property
    def imei2(self): return self.identifiers.filter(slot=2).values_list('value',flat=True).first() or ''

class Identifier(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='identifiers')
    slot = models.PositiveSmallIntegerField()
    value = models.CharField(max_length=15, unique=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device','slot'], name='unique_imei_slot')]

class DevicePhoto(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='photos')
    image = models.ImageField('Foto', upload_to='devices/')

class Accessory(models.Model):
    name = models.CharField('Produto', max_length=100, unique=True)
    category = models.CharField('Categoria', max_length=60)
    compatibility = models.CharField('Compatibilidade', max_length=200, blank=True)
    supplier = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Fornecedor')
    cost = models.DecimalField('Custo unitário', **MONEY)
    price = models.DecimalField('Preço unitário', **MONEY)
    quantity = models.PositiveIntegerField('Quantidade', default=0)
    minimum = models.PositiveIntegerField('Estoque mínimo', default=0)
    def __str__(self): return f'{self.name} ({self.quantity} un.)'

class Sale(models.Model):
    CHANNELS = [('store', 'Loja física'), ('whatsapp', 'WhatsApp (origem informada)'), ('instagram', 'Instagram (origem informada)'), ('other', 'Outro')]
    channel = models.CharField('Canal de origem', max_length=15, choices=CHANNELS, default='store')
    notes = models.TextField('Observações', blank=True)
    customer = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Cliente')
    created_at = models.DateTimeField(default=timezone.now)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    gross = models.DecimalField(**MONEY)
    discount = models.DecimalField(**MONEY)
    costs = models.DecimalField(**MONEY)
    fees = models.DecimalField(**MONEY)
    trade_device = models.OneToOneField(Device, null=True, blank=True, on_delete=models.PROTECT, related_name='trade_sale')
    trade_value = models.DecimalField(**MONEY)
    status = models.CharField(max_length=10, default='completed', choices=[('completed','Concluída'),('cancelled','Cancelada')])
    cancelled_at = models.DateTimeField(null=True)
    cancel_reason = models.TextField(blank=True)
    terms_snapshot = models.TextField()
    store_snapshot = models.JSONField(default=dict)
    customer_snapshot = models.JSONField(default=dict)
    request_key = models.UUIDField(unique=True)
    class Meta: ordering = ['-id']
    @property
    def total(self): return self.gross - self.discount
    @property
    def profit(self): return self.total - self.costs - self.fees
    @property
    def balance_paid(self): return self.total - self.trade_value

class SaleItem(models.Model):
    active = models.BooleanField(default=True)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='items')
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.PROTECT, related_name='sale_items')
    accessory = models.ForeignKey(Accessory, null=True, blank=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=220)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(**MONEY)
    cost = models.DecimalField(**MONEY)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device'], condition=Q(device__isnull=False,active=True), name='device_sale_history_unique') ]

class CardRate(models.Model):
    machine = models.CharField('Maquininha', max_length=80)
    installments = models.PositiveSmallIntegerField('Parcelas', validators=[MinValueValidator(1),MaxValueValidator(36)])
    percent = models.DecimalField('Taxa (%)', max_digits=6, decimal_places=3, validators=[MinValueValidator(0),MaxValueValidator(100)])
    days = models.PositiveIntegerField('Dias até recebimento (por parcela)', default=30)
    active = models.BooleanField('Ativa', default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['machine','installments'],name='unique_machine_installments')]
    def __str__(self): return f'{self.machine} • {self.installments}x • {self.percent}%'

class Payment(models.Model):
    sale = models.ForeignKey(Sale,on_delete=models.PROTECT,related_name='payments')
    method = models.CharField(max_length=10,choices=[('pix','Pix'),('cash','Dinheiro'),('card','Cartão')])
    gross = models.DecimalField(**MONEY)
    fee = models.DecimalField(**MONEY)
    net = models.DecimalField(**MONEY)
    machine = models.CharField(max_length=80, blank=True)
    installments = models.PositiveSmallIntegerField(default=1)
    rate = models.DecimalField(max_digits=6,decimal_places=3,default=0)

class Ledger(models.Model):
    METHODS = [('cash', 'Dinheiro físico'), ('pix', 'Pix'), ('card', 'Cartão / operadora'), ('bank', 'Banco / transferência'), ('other', 'Não informado')]
    method = models.CharField('Meio efetivo', max_length=10, choices=METHODS, default='other')
    cash_session = models.ForeignKey('CashSession', on_delete=models.PROTECT, null=True, blank=True, related_name='entries')
    service_order = models.ForeignKey('ServiceOrder', on_delete=models.PROTECT, null=True, blank=True, related_name='ledger')
    transfer_key = models.UUIDField(null=True, blank=True)
    label = models.CharField('Descrição', max_length=200)
    category = models.CharField('Categoria', max_length=80)
    amount = models.DecimalField(max_digits=14,decimal_places=2)
    due_date = models.DateField('Vencimento',default=today)
    settled_date = models.DateField('Data de quitação',null=True,blank=True)
    person = models.ForeignKey(Person,on_delete=models.PROTECT,null=True,blank=True,verbose_name='Cliente/fornecedor')
    sale = models.ForeignKey(Sale,on_delete=models.PROTECT,null=True,blank=True,related_name='ledger')
    device = models.ForeignKey(Device,on_delete=models.PROTECT,null=True,blank=True)
    reverses = models.OneToOneField('self',on_delete=models.PROTECT,null=True,blank=True)
    voided = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-id']

class StockMove(models.Model):
    device = models.ForeignKey(Device,on_delete=models.PROTECT,null=True,blank=True)
    accessory = models.ForeignKey(Accessory,on_delete=models.PROTECT,null=True,blank=True)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=200)
    sale = models.ForeignKey(Sale,on_delete=models.PROTECT,null=True,blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class Warranty(models.Model):
    item = models.OneToOneField(SaleItem,on_delete=models.PROTECT,related_name='warranty')
    provider = models.CharField(max_length=10,choices=[('store','BG Store'),('apple','Apple')])
    start = models.DateField()
    end = models.DateField(null=True,blank=True)
    activation = models.DateField('Ativação conhecida',null=True,blank=True)
    confirmed_end = models.DateField('Vencimento Apple confirmado',null=True,blank=True)
    confirmation = models.CharField('Fonte da confirmação Apple',max_length=250,blank=True)
    signed_document = models.FileField('Termo assinado (PDF)',upload_to='signed/',blank=True,validators=[FileExtensionValidator(['pdf'])])
    @property
    def expiry(self): return self.end if self.provider == 'store' else self.confirmed_end

class ServiceRecord(models.Model):
    warranty = models.ForeignKey(Warranty,on_delete=models.PROTECT,related_name='services')
    description = models.TextField('Relato / atendimento')
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class Audit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    entity_id = models.PositiveIntegerField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-id']

class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    updated = models.DateTimeField(default=timezone.now)

class Quote(models.Model):
    STATUSES = [('draft', 'Rascunho'), ('sent', 'Entregue ao cliente'), ('approved', 'Aprovado'), ('converted', 'Convertido em venda'), ('cancelled', 'Cancelado')]
    customer = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Cliente')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    valid_until = models.DateField('Válido até')
    status = models.CharField(max_length=12, choices=STATUSES, default='draft')
    items = models.JSONField(default=list)
    discount = models.DecimalField('Desconto', **MONEY)
    notes = models.TextField('Observações', blank=True)
    customer_snapshot = models.JSONField(default=dict)
    store_snapshot = models.JSONField(default=dict)
    sale = models.OneToOneField(Sale, null=True, blank=True, on_delete=models.PROTECT)
    request_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    @property
    def gross(self):
        return sum((Decimal(i['price']) * i['quantity'] for i in self.items), ZERO)

    @property
    def total(self):
        return self.gross - self.discount

    @property
    def expired(self):
        return self.valid_until < today()


class ValuationRule(models.Model):
    model = models.CharField('Modelo', max_length=100)
    storage = models.CharField('Armazenamento', max_length=30)
    maximum = models.DecimalField('Avaliação máxima (R$)', **MONEY)
    battery_discount = models.DecimalField('Desconto por bateria (R$)', **MONEY)
    screen_discount = models.DecimalField('Desconto por tela (R$)', **MONEY)
    wear_discount = models.DecimalField('Desconto por marcas/detalhes (R$)', **MONEY)
    active = models.BooleanField('Ativa', default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['model', 'storage'], name='unique_valuation_model_storage')]

    def __str__(self):
        return f'{self.model} • {self.storage}'


class Valuation(models.Model):
    rule = models.ForeignKey(ValuationRule, on_delete=models.PROTECT)
    person = models.ForeignKey(Person, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Cliente (opcional)')
    criteria = models.JSONField(default=dict)
    snapshot = models.JSONField(default=dict)
    suggested = models.DecimalField(**MONEY)
    notes = models.TextField('Observações da avaliação manual', blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']


class ServicePart(models.Model):
    name = models.CharField('Peça', max_length=120, unique=True)
    compatibility = models.CharField('Compatibilidade', max_length=200, blank=True)
    supplier = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Fornecedor')
    cost = models.DecimalField('Custo médio unitário (R$)', **MONEY)
    price = models.DecimalField('Preço unitário (R$)', **MONEY)
    quantity = models.PositiveIntegerField('Quantidade', default=0)
    minimum = models.PositiveIntegerField('Estoque mínimo', default=0)

    def __str__(self):
        return f'{self.name} ({self.quantity} un.)'


class ServiceOrder(models.Model):
    STATUSES = [('received', 'Recebida'), ('diagnosing', 'Em diagnóstico'), ('awaiting', 'Aguardando aprovação'), ('approved', 'Aprovada'), ('repair', 'Em reparo'), ('ready', 'Pronta'), ('delivered', 'Entregue'), ('cancelled', 'Cancelada')]
    customer = models.ForeignKey(Person, on_delete=models.PROTECT, verbose_name='Cliente')
    device_description = models.CharField('Aparelho / modelo / cor', max_length=200)
    imei = models.CharField('IMEI (opcional)', max_length=15, blank=True)
    serial = models.CharField('Série (opcional)', max_length=80, blank=True)
    inventory_device = models.ForeignKey(Device, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Vincular aparelho do estoque (opcional)')
    complaint = models.TextField('Relato do cliente')
    received_condition = models.TextField('Conservação e acessórios recebidos', blank=True)
    diagnosis = models.TextField('Diagnóstico', blank=True)
    work_done = models.TextField('Serviços realizados', blank=True)
    technician = models.CharField('Técnico responsável', max_length=120, blank=True)
    approved_limit = models.DecimalField('Limite autorizado pelo cliente (R$)', **MONEY)
    approval_note = models.TextField('Registro da autorização do cliente (data, meio e escopo)', blank=True)
    promised_date = models.DateField('Previsão de entrega', null=True, blank=True)
    labor_price = models.DecimalField('Mão de obra cobrada (R$)', **MONEY)
    labor_cost = models.DecimalField('Custo de mão de obra (R$)', **MONEY)
    status = models.CharField(max_length=12, choices=STATUSES, default='received')
    active = models.BooleanField(default=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.UUIDField(unique=True)
    customer_snapshot = models.JSONField(default=dict)
    store_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-id']
        constraints = [models.UniqueConstraint(fields=['imei'], condition=Q(active=True) & ~Q(imei=''), name='one_active_service_per_imei'), models.UniqueConstraint(fields=['inventory_device'], condition=Q(active=True, inventory_device__isnull=False), name='one_active_service_per_stock_device')]

    @property
    def total(self):
        if self.inventory_device_id:
            return self.cost
        return self.labor_price + sum((p.price * p.quantity for p in self.part_uses.filter(returned=False)), ZERO)

    @property
    def cost(self):
        return self.labor_cost + sum((p.cost * p.quantity for p in self.part_uses.filter(returned=False)), ZERO)

    @property
    def result(self):
        return ZERO if self.inventory_device_id else self.total - self.cost


class PartUse(models.Model):
    order = models.ForeignKey(ServiceOrder, on_delete=models.PROTECT, related_name='part_uses')
    part = models.ForeignKey(ServicePart, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    cost = models.DecimalField(**MONEY)
    price = models.DecimalField(**MONEY)
    returned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class PartMove(models.Model):
    part = models.ForeignKey(ServicePart, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=200)
    order = models.ForeignKey(ServiceOrder, on_delete=models.PROTECT, null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ServiceEvent(models.Model):
    order = models.ForeignKey(ServiceOrder, on_delete=models.PROTECT, related_name='events')
    description = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Task(models.Model):
    KINDS = [('appointment', 'Agendamento'), ('after_sale', 'Pós-venda'), ('service', 'Assistência'), ('other', 'Outro')]
    title = models.CharField('Título', max_length=160)
    kind = models.CharField('Tipo', max_length=15, choices=KINDS, default='appointment')
    person = models.ForeignKey(Person, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Contato')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Venda vinculada')
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.PROTECT, null=True, blank=True, verbose_name='OS vinculada')
    when = models.DateTimeField('Data e hora (São Paulo)')
    notes = models.TextField('Observações', blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(blank=True)
    cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['when', 'id']


class CashSession(models.Model):
    opened_at = models.DateTimeField(default=timezone.now)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='opened_cash_sessions')
    opening = models.DecimalField('Dinheiro contado na abertura (R$)', **MONEY)
    open_slot = models.PositiveSmallIntegerField(null=True, unique=True, default=1)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='closed_cash_sessions')
    counted = models.DecimalField('Dinheiro contado no fechamento (R$)', max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO)])
    expected_snapshot = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    notes = models.TextField('Observações', blank=True)

    class Meta:
        ordering = ['-id']

    @property
    def expected(self):
        if self.closed_at:
            return self.expected_snapshot
        return self.opening + sum((l.amount for l in self.entries.filter(voided=False, settled_date__isnull=False)), ZERO)

    @property
    def difference(self):
        return self.counted - self.expected if self.counted is not None else None


class QuickCreation(models.Model):
    """Impede duplicar um cadastro rápido quando a mesma solicitação é repetida."""
    request_key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=15)
    object_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
