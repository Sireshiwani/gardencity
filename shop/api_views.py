"""JSON API for the Next.js marketing site (booking)."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from django.conf import settings

from .forms import PublicBookingForm
from .models import Service, User


def _cors(response, request=None):
    origin = ""
    if request is not None and hasattr(request, "headers"):
        origin = request.headers.get("Origin", "") or ""
    allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", None) or []
    if origin and origin in allowed:
        response["Access-Control-Allow-Origin"] = origin
    elif allowed:
        pass
    else:
        response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@require_GET
def public_home(request):
    services = [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "category_display": s.get_category_display(),
            "description": s.description,
            "price": str(s.price),
            "duration_minutes": s.duration_minutes,
            "photo_url": s.photo_url,
        }
        for s in Service.objects.filter(is_active=True).order_by("category", "name")[:12]
    ]
    team = [
        {
            "id": u.id,
            "name": u.full_name,
            "photo_url": u.photo_url,
            "specialty": u.specialty,
            "commission_rate": str(u.commission_rate),
        }
        for u in User.public_barbers()
    ]
    return _cors(JsonResponse({"services": services, "team": team}), request)


@require_GET
def booking_options(request):
    services = [
        {
            "id": s.id,
            "name": s.name,
            "price": str(s.price),
            "duration_minutes": s.duration_minutes,
            "category": s.category,
        }
        for s in Service.objects.filter(is_active=True).order_by("category", "name")
    ]
    staff = [
        {"id": u.id, "name": u.full_name}
        for u in User.objects.filter(role=User.Roles.STAFF, is_active=True).order_by("full_name")
    ]
    return _cors(JsonResponse({"services": services, "staff": staff}), request)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def booking_create(request):
    if request.method == "OPTIONS":
        return _cors(JsonResponse({}), request)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _cors(
            JsonResponse({"ok": False, "errors": {"__all__": ["Invalid JSON body."]}}, status=400),
            request,
        )

    staff_val = data.get("staff")
    post_data = {
        "customer_name": (data.get("customer_name") or "").strip(),
        "customer_email": (data.get("customer_email") or "").strip(),
        "customer_phone": (data.get("customer_phone") or "").strip(),
        "service": str(data.get("service") or ""),
        "appointment_at": data.get("appointment_at") or "",
        "notes": (data.get("notes") or "").strip(),
        "referral_code": (data.get("referral_code") or "").strip(),
    }
    if staff_val not in (None, "", "any", "Any Available"):
        post_data["staff"] = str(staff_val)

    form = PublicBookingForm(post_data)
    if form.is_valid():
        form.save()
        return _cors(
            JsonResponse(
                {
                    "ok": True,
                    "message": "Your appointment request has been submitted.",
                }
            ),
            request,
        )

    errors = {field: [str(msg) for msg in msgs] for field, msgs in form.errors.items()}
    return _cors(JsonResponse({"ok": False, "errors": errors}, status=400), request)
