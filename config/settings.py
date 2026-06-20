import os
from pathlib import Path
from urllib.parse import quote_plus

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-2e2ko6a343tb3%==f70+6)8&nev#^5rj1-_)@&+63%vxarx*=^",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

_allowed = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
if _allowed:
    ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
if _csrf:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(",") if o.strip()]
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.currency',
                'shop.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


def _env_clean(key: str) -> str:
    """Strip whitespace; treat unresolved DO bindables (literal ${...}) as unset."""
    raw = (os.environ.get(key) or '').strip()
    if not raw or ('${' in raw and '}' in raw):
        return ''
    return raw


def _password_from_env() -> str:
    """Read DB password; skip literal unresolved bindables like ``${db.PASSWORD}``."""
    for key in ('POSTGRES_PASSWORD', 'PGPASSWORD'):
        raw = (os.environ.get(key) or '').strip()
        if not raw:
            continue
        if '${' in raw and '}' in raw:
            continue
        return raw
    return ''


def _resolve_database_url() -> str:
    """Resolve Postgres URL from env. See .env.example for DigitalOcean bindable variables."""
    for key in ('DATABASE_URL', 'DJANGO_DATABASE_URL'):
        raw = _env_clean(key)
        if raw:
            return raw
    user = _env_clean('POSTGRES_USER') or _env_clean('PGUSER')
    host = _env_clean('POSTGRES_HOST') or _env_clean('PGHOST')
    port = _env_clean('POSTGRES_PORT') or _env_clean('PGPORT') or '5432'
    dbname = _env_clean('POSTGRES_DB') or _env_clean('PGDATABASE')
    pwd_raw = _password_from_env()
    if user and host and dbname:
        q = quote_plus(user, safe='')
        pq = quote_plus(pwd_raw, safe='')
        ssl = (os.environ.get('POSTGRES_SSLMODE') or 'require').strip()
        if '${' in ssl:
            ssl = 'require'
        # postgres:// matches DigitalOcean / Heroku-style validators; dj-database-url accepts it.
        return f'postgres://{q}:{pq}@{host}:{port}/{dbname}?sslmode={ssl}'
    return ''


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
_database_url = _resolve_database_url()
if _database_url:
    ssl_required = os.environ.get('DATABASE_SSL_REQUIRE', 'true').lower() in ('1', 'true', 'yes')
    try:
        DATABASES['default'] = dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=ssl_required,
        )
    except ValueError as exc:
        raise ImproperlyConfigured(
            'Invalid DATABASE_URL. Use postgres://user:pass@host:port/dbname?sslmode=require. '
            'On App Platform, if the value is the literal text ${db.DATABASE_URL}, the bindable '
            'did not resolve — fix the database component name and scope (RUN_AND_BUILD_TIME), '
            'or paste the full URL as an encrypted variable, or use discrete POSTGRES_* bindables.'
        ) from exc

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

# Official public site (Next.js). When set, GET / redirects here instead of Django home.html.
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "").strip().rstrip("/")
# Where to send users after logout (named URL route, not PUBLIC_SITE_URL).
LOGOUT_REDIRECT_URL = os.environ.get("LOGOUT_REDIRECT_URL", "login").strip() or "login"

# Comma-separated origins for browser → Django API (optional; Next proxy avoids most CORS).
_cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    CSRF_COOKIE_SECURE = os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "true").lower() in (
        "1",
        "true",
        "yes",
    )
AUTH_USER_MODEL = 'shop.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Display prefix for money amounts in templates (Kenyan Shillings).
SITE_CURRENCY = "Kshs"
SALE_MANAGER_EDIT_WINDOW_HOURS = 72

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@gardencityfinecuts.local")
# Password-reset links stay valid for this many seconds (default: 3 days).
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", str(3 * 24 * 60 * 60)))

# --- SMS (pluggable) ---
# Set SMS_BACKEND to any importable class path; subclass shop.services.sms_backends.BaseSMSBackend.
# Defaults to console logging only (no external provider).
SMS_BACKEND = "shop.services.sms_backends.ConsoleSMSBackend"
# Optional dict passed as **kwargs to your backend class (for custom providers).
SMS_BACKEND_OPTIONS = {}

# Twilio — only used if SMS_BACKEND = "shop.services.sms_backends.TwilioSMSBackend"
# (install optional dependency: pip install twilio)
TWILIO_ACCOUNT_SID = ""
TWILIO_AUTH_TOKEN = ""
TWILIO_FROM_NUMBER = ""

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
