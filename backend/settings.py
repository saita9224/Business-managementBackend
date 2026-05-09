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
#
# The rule for deciding which list an app belongs to:
#
# SHARED_APPS  → tables that must exist ONCE in the public
#                schema and nowhere else. Only infrastructure
#                that has zero dependency on the Employee model.
#
# TENANT_APPS  → tables that must be isolated per business.
#                Because AUTH_USER_MODEL = "employees.Employee",
#                anything that references the user model
#                (admin, auth, sessions) must live here so
#                the Employee table exists in the same schema.
# ======================================================

SHARED_APPS = [
    # django-tenants MUST be first
    'django_tenants',

    # Tenant registry — Business, Domain, SuperAdmin
    'tenants',

    # These two have NO foreign keys to Employee and are
    # safe to live in the public schema only.
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',

    # Third-party — no DB tables
    'corsheaders',
    'strawberry_django',
]

TENANT_APPS = [
    # AUTH_USER_MODEL = "employees.Employee" means the Employee
    # table must exist in the same schema as anything that
    # references it. admin, auth, sessions, and messages all
    # reference the user model, so they MUST be tenant apps.
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',

    # Core business apps
    'employees',
    'authentication',
    'expenses',
    'inventory',
    'POS',
    'hr',
    'reports',
]

# INSTALLED_APPS is the union — shared first, then tenant
# apps that aren't already in shared.
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
        'NAME': 'business_management',
        'USER': 'postgres',
        'PASSWORD': 'Uabatias',
        'HOST': 'localhost',
        'PORT': '5432',
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
GOOGLE_CLIENT_ID = "536023790932-enm7mluq01p6qh5obncdl8jibtvpd6i9.apps.googleusercontent.com"


# ======================================================
# EMAIL — SMTP
# ======================================================
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST          = 'smtp.gmail.com'
# EMAIL_PORT          = 587
# EMAIL_USE_TLS       = True
# EMAIL_HOST_USER     = 'saitacollinsgmail@gmail.com'
# EMAIL_HOST_PASSWORD = 'itezbkdujzusvlwx'
DEFAULT_FROM_EMAIL  = 'BizzMan <saitacollinsgmail@gmail.com>'

# Uncomment during local development to print emails to
# the terminal instead of sending them:
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'