# backend/settings.py

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

# In development: ALLOWED_HOSTS=* in .env
# In production:  ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())


# ======================================================
# MULTI-TENANCY — APP SPLIT
# ======================================================

SHARED_APPS = [
    'django_tenants',
    'tenants',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'corsheaders',
    'strawberry_django',
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


# ======================================================
# MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
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
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ======================================================
# CORS
# ======================================================
CORS_ALLOW_ALL_ORIGINS = True


# ======================================================
# JWT
# ======================================================
JWT_ALGORITHM             = "HS256"
JWT_ACCESS_EXPIRES_SECONDS = 3600  # 1 hour


# ======================================================
# GOOGLE OAUTH
# ======================================================
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID')


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