"""Loopback development settings. Production operators must supply a secret."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get(
    "MERIDIAN_SECRET_KEY", "local-synthetic-demo-only-not-for-public-deployment"
)
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ROOT_URLCONF = "pp_meridian.config.urls"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "pp_meridian.persistence",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
url = urlparse(
    os.environ.get("MERIDIAN_DATABASE_URL", "postgresql://meridian@127.0.0.1:5432/meridian")
)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": url.path.lstrip("/"),
        "USER": unquote(url.username or ""),
        "PASSWORD": unquote(url.password or ""),
        "HOST": url.hostname or "127.0.0.1",
        "PORT": url.port or 5432,
        "CONN_MAX_AGE": 0,
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

schema = os.environ.get("MERIDIAN_SCHEMA")
if schema:
    import re

    if not re.fullmatch(r"meridian_demo_[a-f0-9]{24}", schema):
        raise ValueError("invalid Meridian demo schema")
    DATABASES["default"]["OPTIONS"] = {"options": f"-c search_path={schema}"}

if os.environ.get("MERIDIAN_TEST_DB_NAME"):
    DATABASES["default"]["TEST"] = {"NAME": os.environ["MERIDIAN_TEST_DB_NAME"]}
