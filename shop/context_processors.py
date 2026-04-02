from django.conf import settings


def currency(request):
    return {"CURRENCY": getattr(settings, "SITE_CURRENCY", "Kshs")}
