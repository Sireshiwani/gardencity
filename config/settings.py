import os
from pathlib import Path

import dj_database_url

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# Production: set DATABASE_URL in the host (e.g. DigitalOcean links Managed Postgres and injects it).
# Local: optional .env file (see .env.example); never commit real credentials.
_database_url = (os.environ.get('DATABASE_URL') or '').strip()
if _database_url:
    ssl_required = os.environ.get('DATABASE_SSL_REQUIRE', 'true').lower() in ('1', 'true', 'yes')
    DATABASES['default'] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=ssl_required,
    )

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

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
AUTH_USER_MODEL = 'shop.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Display prefix for money amounts in templates (Kenyan Shillings).
SITE_CURRENCY = "Kshs"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@gardencityfinecuts.local"

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
