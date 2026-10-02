"""
Django settings for TabsForge School OS backend.
"""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOW_ALL_ORIGINS=(bool, False),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    EMAIL_USE_TLS=(bool, False),
    EMAIL_USE_SSL=(bool, False),
    EMAIL_PORT=(int, 25),
)

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='change-me-in-production')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_ALL_ORIGINS = env('CORS_ALLOW_ALL_ORIGINS')

# Email configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env('EMAIL_USE_TLS')
EMAIL_USE_SSL = env('EMAIL_USE_SSL')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@tabsforge.com')

# Payment providers (paystack / flutterwave / manual). The gateway endpoints
# answer 503 until the secret keys below are configured.
PAYMENT_PROVIDER = env('PAYMENT_PROVIDER', default='manual')
PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = env('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_BASE_URL = env('PAYSTACK_BASE_URL', default='https://api.paystack.co')
FLUTTERWAVE_SECRET_KEY = env('FLUTTERWAVE_SECRET_KEY', default='')
FLUTTERWAVE_PUBLIC_KEY = env('FLUTTERWAVE_PUBLIC_KEY', default='')
FLUTTERWAVE_BASE_URL = env('FLUTTERWAVE_BASE_URL', default='https://api.flutterwave.com')
FLUTTERWAVE_SECRET_HASH = env('FLUTTERWAVE_SECRET_HASH', default='')

# SMS provider (termii / africastalking / twilio / stub)
SMS_PROVIDER = env('SMS_PROVIDER', default='stub')
SMS_API_KEY = env('SMS_API_KEY', default='')
SMS_SENDER_ID = env('SMS_SENDER_ID', default='TabsForge')
# Termii — the Nigerian-standard gateway
TERMII_API_KEY = env('TERMII_API_KEY', default='')
TERMII_SENDER_ID = env('TERMII_SENDER_ID', default='TabsForge')
TERMII_BASE_URL = env('TERMII_BASE_URL', default='https://v3.api.termii.com')
TERMII_CHANNEL = env('TERMII_CHANNEL', default='generic')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'channels',
    'corsheaders',
    'drf_spectacular',
    'whitenoise.runserver_nostatic',
    # Project apps
    'core',
    'accounts',
    'schools',
    'academics',
    'students',
    'staff',
    'attendance',
    'gradebook',
    'finance',
    'communications',
    'library',
    'transport',
    'hostel',
    'notifications',
    'billing',
    'admissions',
    'messaging',
    'homework',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.TenantMiddleware',
    'core.middleware.SubdomainTenantMiddleware',  # Part 9
]

# WhatsApp Business Cloud API (Part 2) — set in .env
WHATSAPP_TOKEN = env('WHATSAPP_TOKEN', default='')
WHATSAPP_PHONE_ID = env('WHATSAPP_PHONE_ID', default='')
WHATSAPP_APP_SECRET = env('WHATSAPP_APP_SECRET', default='')
WHATSAPP_VERIFY_TOKEN = env('WHATSAPP_VERIFY_TOKEN', default='tabsforge_verify_token')
WHATSAPP_VERSION = env('WHATSAPP_VERSION', default='v20.0')
WHATSAPP_DEFAULT_SCHOOL = env('WHATSAPP_DEFAULT_SCHOOL', default='modelschool')

# Frontend base URL for registration links
FRONTEND_URL = env('FRONTEND_URL', default='https://tabsforge.com')

ROOT_URLCONF = 'project.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'
ASGI_APPLICATION = 'project.asgi.application'

# Real-time layer for messaging/notifications (Part 4a).
# Redis on localhost; falls back to in-memory for tests/dev without Redis.
_redis_url = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
try:  # pragma: no cover - environment dependent
    import redis as _redis_mod
    _redis_mod.from_url(_redis_url, socket_connect_timeout=0.3).ping()
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_redis_url]},
        }
    }
except Exception:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3'),
}

# Keep connections alive briefly to reduce overhead on low-traffic VPS.
DATABASES['default']['CONN_MAX_AGE'] = env.int('CONN_MAX_AGE', default=60)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE', default='Africa/Lagos')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Ensure directories exist for collectstatic and uploads
os.makedirs(STATIC_ROOT, exist_ok=True)
os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.TenantTokenAuthentication',
        'core.authentication.TenantSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'api.permissions.IsSchoolActive',  # block suspended-school sessions
        'api.permissions.ReadOnlyForGuest',  # Part 8: block writes for guest accounts
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'TabsForge School OS API',
    'DESCRIPTION': 'Tenant-aware school management system API.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

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
        'level': env('LOG_LEVEL', default='INFO'),
    },
}

SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT')
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE')
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
# Apache terminates TLS; daphne is told the real scheme via X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'DENY'

# Business rules
TIER_LIBRARY_MIN = 'Bloom'
TIER_TRANSPORT_MIN = 'Summit'
TIER_HOSTEL_MIN = 'Summit'

# AI providers — tried in order; a provider is skipped when its key is unset.
# Set AI_PROVIDERS to reorder, e.g. "grok,gemini". Claude activates once
# ANTHROPIC_API_KEY is provided.
AI_PROVIDERS = env.list('AI_PROVIDERS', default=['gemini', 'grok', 'anthropic'])
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_MODEL = env('GEMINI_MODEL', default='gemini-3.5-flash')
GROK_API_KEY = env('GROK_API_KEY', default='')
GROK_MODEL = env('GROK_MODEL', default='grok-3-mini')
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')
ANTHROPIC_MODEL = env('ANTHROPIC_MODEL', default='claude-haiku-4-5')

# Messaging: how many seconds between poll cycles on frontend
MESSAGE_POLL_INTERVAL = 3
