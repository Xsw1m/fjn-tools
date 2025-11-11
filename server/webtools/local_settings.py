from pathlib import Path
from .settings import BASE_DIR, INSTALLED_APPS, MIDDLEWARE

# Enable CORS and register sumtool app
INSTALLED_APPS += [
    'corsheaders',
    'sumtool',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
] + MIDDLEWARE

ALLOWED_HOSTS = ['*']

STATIC_ROOT = BASE_DIR / 'staticfiles'

# CORS: allow all during local development
CORS_ALLOW_ALL_ORIGINS = True