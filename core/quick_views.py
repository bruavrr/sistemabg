"""Cadastros persistentes feitos no PDV, sem recarregar o formulário de venda."""
import uuid
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .models import Person, Device, Accessory, QuickCreation, StockMove, Ledger, Store
from .quick_forms import QuickCustomerForm, QuickDeviceForm, QuickAccessoryForm, LogoForm
from .services import create_device, audit, store

FORMS = {'customer': (QuickCustomerForm, 'quick-customer', Person),
         'device': (QuickDeviceForm, 'quick-device', Device),
         'accessory': (QuickAccessoryForm, 'quick-accessory', Accessory)}


def payload(kind, obj, origin=None):
    data = {'kind': kind, 'id': obj.pk, 'label': str(obj)}
    if kind == 'customer':
        data.update(discovery_source=obj.discovery_source, discovery_label=obj.get_discovery_source_display(),
                    document=obj.document, email=obj.email, phone=obj.phone)
    else:
        data.update(price=int(obj.price * 100))
        if kind == 'device':
            data.update(label=f'{obj} · IMEI {obj.imei1}', available=obj.status == 'available')
        else:
            data.update(label=obj.name, quantity=obj.quantity, available=obj.quantity > 0)
    if origin:
        data['origin'] = {'id': origin.pk, 'label': origin.name}
    return data


def replay(key, actor, kind):
    record = QuickCreation.objects.filter(request_key=key).first()
    if record:
        if record.actor_id != actor.pk or record.kind != kind:
            raise PermissionDenied
        obj = get_object_or_404(FORMS[kind][2], pk=record.object_id)
        origin = obj.origin if kind == 'device' else (obj.supplier if kind == 'accessory' else None)
        return JsonResponse({'ok': True, 'replayed': True, 'next_request_key': str(uuid.uuid4()), 'object': payload(kind, obj, origin)})


@login_required
@require_POST
def quick_create(request, kind):
    if kind not in FORMS:
        return JsonResponse({'ok': False, 'message': 'Tipo de cadastro inválido.'}, status=400)
    if kind == 'accessory' and not request.user.is_staff:
        raise PermissionDenied
    form_class, prefix, model = FORMS[kind]
    try:
        key = uuid.UUID(request.POST.get(f'{prefix}-request_key', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'ok': False, 'message': 'Código da solicitação ausente. Reabra o cadastro.'}, status=400)
    previous = replay(key, request.user, kind)
    if previous:
        return previous
    form = form_class(request.POST, request.FILES, prefix=prefix)
    if not form.is_valid():
        data = {'ok': False, 'message': 'Revise os campos destacados.', 'errors': form.errors.get_json_data()}
        if kind == 'customer' and form.cleaned_data.get('document'):
            existing = Person.objects.filter(document=form.cleaned_data['document']).first()
            if existing:
                data['existing'] = payload('customer', existing)
                data['message'] = 'Este documento já tem cadastro. Você pode selecionar o contato existente sem duplicá-lo.'
        return JsonResponse(data, status=422)
    try:
        with transaction.atomic():
            previous = replay(key, request.user, kind)
            if previous:
                return previous
            origin = None
            if kind == 'customer':
                obj = form.save(commit=False)
                obj.kind = 'customer'
                obj.save()
                audit(request.user, 'Cliente cadastrado no PDV', obj, {'origem': obj.discovery_source})
            else:
                field = form.origin_field
                origin = form.cleaned_data.get(field)
                if not origin:
                    origin = Person.objects.create(name=form.cleaned_data['origin_name'], kind='supplier')
                    audit(request.user, 'Fornecedor cadastrado no PDV', origin)
                form.cleaned_data[field] = origin
                setattr(form.instance, field, origin)
                if kind == 'device':
                    obj = create_device(form, request.user)
                else:
                    obj = form.save()
                    StockMove.objects.create(accessory=obj, quantity=obj.quantity, reason='Entrada pelo cadastro no PDV', actor=request.user)
                    if obj.cost:
                        Ledger.objects.create(label=f'Compra inicial {obj.name}', category='Compra de estoque', amount=-obj.cost * obj.quantity, person=origin)
                    audit(request.user, 'Acessório cadastrado no PDV', obj, {'quantidade': obj.quantity})
            QuickCreation.objects.create(request_key=key, actor=request.user, kind=kind, object_id=obj.pk)
        return JsonResponse({'ok': True, 'next_request_key': str(uuid.uuid4()), 'object': payload(kind, obj, origin)}, status=201)
    except IntegrityError:
        previous = replay(key, request.user, kind)
        if previous:
            return previous
        return JsonResponse({'ok': False, 'message': 'Cadastro em conflito: confira CPF/CNPJ, IMEI, série ou nome do acessório. Nenhum registro parcial foi confirmado.'}, status=409)
    except OperationalError:
        return JsonResponse({'ok': False, 'message': 'O banco está ocupado. Aguarde e tente salvar novamente sem fechar esta janela.'}, status=503)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'message': ' '.join(exc.messages)}, status=422)


@login_required
@require_POST
def logo_upload(request):
    if not request.user.is_staff:
        raise PermissionDenied
    form = LogoForm(request.POST, request.FILES, instance=store())
    if not form.is_valid():
        return JsonResponse({'ok': False, 'message': 'Selecione uma imagem válida de até 8 MB.', 'errors': form.errors.get_json_data()}, status=422)
    with transaction.atomic():
        obj = form.save()
        audit(request.user, 'Logo atualizada', obj)
    return JsonResponse({'ok': True, 'logo_url': obj.logo.url})


def brand_logo(request):
    """Só a marca da loja é pública; os demais anexos continuam exigindo login."""
    from pathlib import Path
    from django.conf import settings
    from django.http import FileResponse, Http404
    from PIL import Image
    obj = Store.objects.first()
    if not obj or not obj.logo:
        raise Http404
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / obj.logo.name).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise Http404
    with Image.open(target) as image:
        content_type = Image.MIME.get(image.format, 'application/octet-stream')
    response = FileResponse(target.open('rb'), content_type=content_type)
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
