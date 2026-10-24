from urllib.parse import quote
from .models import Store
from .quick_forms import LogoForm

def store_context(request):
    store = Store.objects.first()
    is_admin = request.user.is_authenticated and request.user.is_staff
    return {'store': store, 'is_admin': is_admin,
            'brand_logo_url': '/marca/logo/?v='+quote(store.logo.name) if store and store.logo else '',
            'brand_logo_form': LogoForm(instance=store) if is_admin else None}
