"""
Django settings for Vitauls Signals.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def csv_env(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-vitauls-local-dev-key')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise ValueError('Set DJANGO_SECRET_KEY before deploying with DJANGO_DEBUG=false.')

PRODUCTION_FRONTEND = 'https://virtual-signals-frontend.vercel.app'
PRODUCTION_API_HOST = 'virtual-signals-backend.onrender.com'
PRODUCTION_API = f'https://{PRODUCTION_API_HOST}'


def merge_unique(*groups):
    seen = []
    for group in groups:
        for item in group:
            value = (item or '').strip().rstrip('/')
            if value and value not in seen:
                seen.append(value)
    return seen


ALLOWED_HOSTS = merge_unique(
    csv_env('ALLOWED_HOSTS', 'localhost,127.0.0.1'),
    [PRODUCTION_API_HOST],
    [os.getenv('RAILWAY_PUBLIC_DOMAIN', ''), os.getenv('RENDER_EXTERNAL_HOSTNAME', '')],
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
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
WSGI_APPLICATION = 'config.wsgi.application'

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

import re

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL:
    if os.getenv('RENDER'):
        DATABASE_URL = re.sub(r'@(dpg-[a-z0-9-]+)\.[^/]+', r'@\1', DATABASE_URL)
    else:
        DATABASE_URL = re.sub(
            r'@(dpg-[a-z0-9-]+)(?=[/?])',
            r'@\1.oregon-postgres.render.com',
            DATABASE_URL,
        )

if DATABASE_URL:
    import dj_database_url
    if 'sslmode=' not in DATABASE_URL and 'localhost' not in DATABASE_URL and '127.0.0.1' not in DATABASE_URL:
        DATABASE_URL += ('&' if '?' in DATABASE_URL else '?') + 'sslmode=require'
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
elif os.getenv('RENDER') or not DEBUG:
    raise ValueError(
        'DATABASE_URL is required on Render. Set it to the Internal Postgres URL '
        '(host like dpg-xxxxx-a, not SQLite).'
    )
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

FRONTEND_ORIGIN = os.getenv(
    'FRONTEND_ORIGIN',
    'http://localhost:3000' if DEBUG else PRODUCTION_FRONTEND,
).rstrip('/')
CORS_ALLOWED_ORIGINS = merge_unique(
    csv_env('CORS_ALLOWED_ORIGINS'),
    [FRONTEND_ORIGIN, PRODUCTION_FRONTEND, 'http://localhost:3000', 'http://127.0.0.1:3000'],
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = merge_unique(
    csv_env('CSRF_TRUSTED_ORIGINS'),
    CORS_ALLOWED_ORIGINS,
    [PRODUCTION_API],
)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

PACKAGE_DIAMONDS = 200
PREDICTION_COST = 50
OPEN_ACCESS = os.getenv('OPEN_ACCESS', 'false').lower() == 'true'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
