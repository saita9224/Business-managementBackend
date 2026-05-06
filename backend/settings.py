# backend/settings.py

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = 'django-insecure-$#rn4hc+=6_s&28^&&xyg72^0*tex6zi-uw+#7bg@--un(j!_z'

DEBUG = True

ALLOWED_HOSTS = ["*"]


# ======================================================
# MULTI-TENANCY — APP SPLIT
# django-tenants requires INSTALLED_APPS to be composed
# from SHARED_APPS + TENANT_APPS.
#
# SHARED_APPS  → live in the 'public' PostgreSQL schema.
#                One copy for the whole platform.
# TENANT_APPS  → cloned into every tenant's own schema.
#                Each Business gets isolated tables.
# ======================================================

SHARED_APPS = [
    # django-tenants MUST be first in SHARED_APPS
    'django_tenants',

    # Your tenant registry (Business + Domain models)
    'tenants',

    # Django core — shared because admin, sessions, etc.
    # need a single home and are not per-tenant.
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'corsheaders',
    'strawberry_django',
]

TENANT_APPS = [
    # Every app whose data must be isolated per business.
    # django-tenants will create these tables in each
    # tenant's PostgreSQL schema automatically.
    'django.contrib.contenttypes',  # needed per-tenant for generic relations

    'employees',       # Employee, Role, Permission — fully per-tenant
    'authentication',  # no models, but listed so migrations are applied
    'expenses',
    'inventory',
    'POS',
    'hr',
    'reports',
]

# INSTALLED_APPS must be the union; shared apps come first.
# List comprehension deduplicates apps that appear in both
# (e.g. django.contrib.contenttypes).
INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]


# ======================================================
# TENANT CONFIG
# ======================================================

# The model that represents a tenant (has schema_name field)
TENANT_MODEL = "tenants.Business"

# The model that maps domains/subdomains → tenants
TENANT_DOMAIN_MODEL = "tenants.Domain"

# When True: requests to the public schema URL (e.g. bare
# localhost without a subdomain) are still served, useful
# during local development. Set False in production.
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True


# ======================================================
# MIDDLEWARE
# ======================================================
# TenantMainMiddleware MUST be first. It reads the incoming
# subdomain, looks up the matching Domain record, and sets
# the PostgreSQL search_path before any other middleware
# or view code runs. Your JWTMiddleware (SchemaExtension)
# then runs correctly inside the already-scoped schema.
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',  # ← MUST be first
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
# django-tenants routes requests based on whether the
# incoming host matches a tenant domain or the public schema.
#
# ROOT_URLCONF          → used for all tenant requests
# PUBLIC_SCHEMA_URLCONF → used when the request hits the
#                         public schema (bare localhost,
#                         Google auth, SaaS landing)
ROOT_URLCONF = 'backend.urls'
PUBLIC_SCHEMA_URLCONF = 'backend.public_urls'


# ======================================================
# TEMPLATES
# ======================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_ATTRS': True,
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
# ENGINE must be django_tenants.postgresql_backend — this
# is a thin wrapper around psycopg2 that injects
# SET search_path = <schema>, public; on every connection
# checkout. Everything else stays the same as before.
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'business_management',
        'USER': 'postgres',
        'PASSWORD': 'Uabatias',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Required router — tells Django which models belong to
# shared vs tenant schemas so migrate_schemas works correctly.
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
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


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
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRES_SECONDS = 3600  # 1 hour


# ======================================================
# GOOGLE OAUTH
# ======================================================
# Web client ID from Google Cloud Console.
# APIs & Services → Credentials → OAuth 2.0 Client IDs
# → "Hoppers Backend" (Web application type).
#
# Django uses this to verify the id_token sent by the
# mobile app. The token's 'aud' field must match this value.
#
# The Android client ID (used only by the mobile app)
# is NOT stored here — it lives in the React Native project.
GOOGLE_CLIENT_ID = "536023790932-enm7mluq01p6qh5obncdl8jibtvpd6i9.apps.googleusercontent.com"