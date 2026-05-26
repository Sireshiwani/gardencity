from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

SERVICE_CARD_IMAGES = [
    "https://images.unsplash.com/photo-1621605815971-fbc98d665033?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1622296089863-eb7fc530daa8?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1517832606299-7ae9b720a186?auto=format&fit=crop&w=1200&q=80",
]


@register.filter
def format_ksh(value):
    if value in (None, ""):
        return "0"
    try:
        n = Decimal(str(value))
        if n == n.to_integral_value():
            return f"{int(n):,}"
        return f"{n:,.2f}"
    except (InvalidOperation, ValueError):
        return str(value)


@register.filter
def service_card_image(index):
    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    return SERVICE_CARD_IMAGES[i % len(SERVICE_CARD_IMAGES)]
