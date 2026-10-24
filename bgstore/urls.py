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

from core import operations_views as op
urlpatterns += [
    path('orcamentos/', op.quotes, name='quotes'),
    path('orcamentos/novo/', op.quote_new, name='quote_new'),
    path('orcamentos/<int:pk>/', op.quote_detail, name='quote'),
    path('orcamentos/<int:pk>/status/', op.quote_status, name='quote_status'),
    path('ferramentas/', op.tools, name='tools'),
    path('ferramentas/cartao/', op.card_simulator, name='card_simulator'),
    path('ferramentas/regra/', op.valuation_rule, name='valuation_rule_new'),
    path('ferramentas/regra/<int:pk>/', op.valuation_rule, name='valuation_rule'),
    path('ferramentas/avaliar/', op.valuation_new, name='valuation_new'),
    path('ferramentas/avaliacao/<int:pk>/', op.valuation_detail, name='valuation'),
    path('assistencia/', op.service_orders, name='service_orders'),
    path('assistencia/nova/', op.service_new, name='service_new'),
    path('assistencia/os/<int:pk>/', op.service_detail, name='service'),
    path('assistencia/os/<int:pk>/etapa/', op.service_transition, name='service_transition'),
    path('assistencia/os/<int:pk>/peca/', op.service_part_use, name='service_part_use'),
    path('assistencia/pecas/', op.parts, name='parts'),
    path('assistencia/pecas/nova/', op.part_new, name='part_new'),
    path('assistencia/pecas/<int:pk>/movimento/', op.part_move, name='part_move'),
    path('agenda/', op.agenda, name='agenda'),
    path('agenda/nova/', op.task_new, name='task_new'),
    path('agenda/<int:pk>/concluir/', op.task_complete, name='task_complete'),
    path('caixa/', op.cash_sessions, name='cash_sessions'),
    path('caixa/<int:pk>/', op.cash_detail, name='cash'),
    path('caixa/<int:pk>/fechar/', op.cash_close, name='cash_close'),
    path('caixa/<int:pk>/movimento/', op.cash_move, name='cash_move'),
    path('relatorios/', op.reports, name='reports'),
    path('contatos/<int:pk>/editar/', op.person_edit, name='person_edit'),
    path('aparelhos/<int:pk>/editar/', op.device_edit, name='device_edit'),
    path('imprimir/<str:kind>/<int:pk>/', op.operations_document, name='operations_document'),
]
