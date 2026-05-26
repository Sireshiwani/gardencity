"""Public marketing site URL helpers (Next.js front)."""
from django.conf import settings


def public_site_url(path: str = "") -> str:
    base = getattr(settings, "PUBLIC_SITE_URL", "").strip().rstrip("/")
    if not base:
        return ""
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def redirect_to_public_site(path: str = ""):
    from django.shortcuts import redirect

    url = public_site_url(path)
    if not url:
        return None
    return redirect(url)
