from django import template

register = template.Library()

@register.filter
def in_list(value, csv):
    items = [s.strip() for s in str(csv).split(",") if s.strip()]
    return value in items
