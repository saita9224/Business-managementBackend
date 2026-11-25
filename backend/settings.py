# backend/settings.py

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

# In development: ALLOWED_HOSTS=localhost,127.0.0.1,[::1]
# In production:  ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,[::1]',
    cast=Csv(),
)


# ======================================================
# MULTI-TENANCY — APP SPLIT
# ======================================================

SHARED_APPS = [
    'django_extensions',
    'django_tenants',
    'tenants',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'corsheaders',
    'strawberry_django',

    'authentication',
]

TENANT_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'employees',
    'authentication',
    'expenses',
    'inventory',
    'POS',
    'hr',
    'reports',
    'sync',
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]


# ======================================================
# TENANT CONFIG
# ======================================================
TENANT_MODEL        = "tenants.Business"
TENANT_DOMAIN_MODEL = "tenants.Domain"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True
ENABLE_X_TENANT_HEADER = config(
    'ENABLE_X_TENANT_HEADER',
    default=DEBUG,
    cast=bool,
)

# CHANGE (#1): suffix used when a new tenant's Domain row is created
# during registration/Google sign-up.
# Dev  (.env): TENANT_DOMAIN_SUFFIX=localhost
# Prod (.env): TENANT_DOMAIN_SUFFIX=api.yourdomain.com
TENANT_DOMAIN_SUFFIX = config('TENANT_DOMAIN_SUFFIX', default='localhost')


# ======================================================
# MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'backend.tenant_middleware.XTenantMiddleware',  
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ======================================================
# URL ROUTING
# ======================================================
ROOT_URLCONF          = 'backend.urls'
PUBLIC_SCHEMA_URLCONF = 'backend.public_urls'


# ======================================================
# TEMPLATES
# ======================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'


# ======================================================
# DATABASE
# ======================================================
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST', default='localhost'),
        'PORT':     config('DB_PORT', default='5432'),
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']


# ======================================================
# AUTH
# ======================================================
AUTH_USER_MODEL = "employees.Employee"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ======================================================
# INTERNATIONALISATION
# ======================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True


# ======================================================
# STATIC FILES
# ======================================================
STATIC_URL  = config('STATIC_URL', default='static/')
STATIC_ROOT = Path(config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles')))

# ======================================================
# MEDIA FILES (user uploads)
# ======================================================
MEDIA_URL  = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))
MAX_BUSINESS_LOGO_BYTES = config(
    'MAX_BUSINESS_LOGO_BYTES',
    default=2 * 1024 * 1024,
    cast=int,
)


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ======================================================
# CORS / API SURFACE
# ======================================================
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS
GRAPHQL_IDE_ENABLED = config('GRAPHQL_IDE_ENABLED', default=DEBUG, cast=bool)

# ======================================================
# SECURITY HEADERS / COOKIE FLAGS
# Active automatically when DEBUG=False. If TLS terminates
# at a proxy, ensure it forwards X-Forwarded-Proto and set
# SECURE_PROXY_SSL_HEADER accordingly.
# ======================================================
SECURE_SSL_REDIRECT            = not DEBUG
SECURE_HSTS_SECONDS            = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD            = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF    = True
SECURE_BROWSER_XSS_FILTER      = True
X_FRAME_OPTIONS                = 'DENY'
SESSION_COOKIE_SECURE          = not DEBUG
CSRF_COOKIE_SECURE             = not DEBUG
SESSION_COOKIE_HTTPONLY        = True
CSRF_COOKIE_SAMESITE           = 'Lax'
SESSION_COOKIE_SAMESITE        = 'Lax'

# Max GraphQL selection depth (see backend/extensions.py)
GRAPHQL_MAX_DEPTH = config('GRAPHQL_MAX_DEPTH', default=12, cast=int)


# ======================================================
# JWT
# ======================================================
JWT_ALGORITHM             = "HS256"
JWT_ACCESS_EXPIRES_SECONDS = 3600  # 1 hour
AUTH_PIN_MAX_ATTEMPTS = config('AUTH_PIN_MAX_ATTEMPTS', default=5, cast=int)


# ======================================================
# GOOGLE OAUTH
# ======================================================
GOOGLE_CLIENT_ID         = config('GOOGLE_CLIENT_ID')
GOOGLE_ANDROID_CLIENT_ID = config('GOOGLE_ANDROID_CLIENT_ID', default='')


# ======================================================
# EMAIL — SMTP
# ======================================================
EMAIL_BACKEND   = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST          = config('EMAIL_HOST',     default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',     default=587,  cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',  default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='BizzMan <noreply@example.com>')
