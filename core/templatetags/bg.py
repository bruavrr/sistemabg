from decimal import Decimal
from django import template
register=template.Library()
@register.filter
def brl(value):
    try: return 'R$ '+f'{Decimal(value):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
    except Exception: return '—'
@register.filter
def times(a,b): return a*b
@register.filter
def check_label(value):
    return {'unchecked':'Não verificado','ok':'Verificado / aprovado','issue':'Problema / restrição','na':'Não se aplica'}.get(value,value)

@register.filter
def as_decimal(value):
    try:
        return Decimal(value)
    except Exception:
        return Decimal('0')
