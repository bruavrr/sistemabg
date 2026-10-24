from django.contrib import admin
from django.contrib.auth.views import LogoutView, PasswordChangeView, PasswordChangeDoneView
from django.urls import path
from core import views as v
urlpatterns=[
 path('admin/login/',v.LoginView.as_view()),path('admin/',admin.site.urls),path('entrar/',v.LoginView.as_view(),name='login'),path('sair/',LogoutView.as_view(),name='logout'),
 path('senha/',PasswordChangeView.as_view(template_name='core/form.html',success_url='/senha/ok/'),name='password_change'),path('senha/ok/',PasswordChangeDoneView.as_view(template_name='core/password_done.html'),name='password_change_done'),
 path('',v.dashboard,name='dashboard'),path('contatos/',v.people,name='people'),path('contatos/novo/',v.person_new,name='person_new'),path('contatos/<int:pk>/',v.person_detail,name='person'),
 path('aparelhos/',v.devices,name='devices'),path('aparelhos/novo/',v.device_new,name='device_new'),path('aparelhos/<int:pk>/',v.device_detail,name='device'),path('aparelhos/<int:pk>/status/',v.device_status,name='device_status'),
 path('acessorios/',v.accessories,name='accessories'),path('acessorios/novo/',v.accessory_new,name='accessory_new'),path('acessorios/<int:pk>/movimento/',v.accessory_move,name='accessory_move'),
 path('vendas/',v.sales,name='sales'),path('vendas/nova/',v.sale_new,name='sale_new'),path('vendas/<int:pk>/',v.sale_detail,name='sale'),path('vendas/<int:pk>/cancelar/',v.sale_cancel,name='sale_cancel'),
 path('financeiro/',v.finance,name='finance'),path('financeiro/novo/',v.ledger_new,name='ledger_new'),path('financeiro/<int:pk>/quitar/',v.ledger_settle,name='ledger_settle'),path('financeiro/<int:pk>/estornar/',v.ledger_reverse,name='ledger_reverse'),
 path('garantias/',v.warranties,name='warranties'),path('garantias/<int:pk>/',v.warranty_detail,name='warranty'),path('garantias/<int:pk>/atendimento/',v.warranty_service,name='warranty_service'),
 path('configuracoes/',v.settings_view,name='settings'),path('configuracoes/taxa/',v.rate_new,name='rate_new'),path('configuracoes/taxa/<int:pk>/',v.rate_new,name='rate_edit'),path('modulos/',v.modules,name='modules'),path('historico/',v.audit_view,name='audit'),path('exportar/',v.export_data,name='export'),
 path('arquivos/<path:path>',v.private_file,name='private_file'),path('documento/<str:kind>/<int:pk>/',v.document,name='document'),
]
