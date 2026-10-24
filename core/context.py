from .models import Store
def store_context(request):
    return {'store':Store.objects.first(),'is_admin':request.user.is_authenticated and request.user.is_staff}
