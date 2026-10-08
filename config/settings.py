"""
Django settings for the blog.

Everything that differs between your laptop and production is read from environment
variables. Locally these come from a `.env` file (see `.env.example`); on the server
they are set in the hosting dashboard.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core security -------------------------------------------------------------------

# Off unless explicitly turned on, so a misconfigured server never leaks debug pages.
DEBUG = os.environ.get("DJANGO_DEBUG", "") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY (or DJANGO_DEBUG=1 for local development).")
    SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Needed for logins/forms over HTTPS on your domain, e.g. "https://myblog.com".
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


# --- Application definition ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Local apps
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves CSS/JS efficiently in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "blog.context_processors.blog_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database --------------------------------------------------------------------------
# DATABASE_URL looks like postgres://user:password@host:5432/dbname.
# Without it we fall back to the local SQLite file.

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,  # reuse connections for 10 minutes instead of reconnecting per request
        conn_health_checks=True,
    )
}


# --- Passwords -------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internationalization --------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# --- Blog identity ---------------------------------------------------------------------

BLOG_TITLE = os.environ.get("BLOG_TITLE", "My Blog")
BLOG_DESCRIPTION = os.environ.get("BLOG_DESCRIPTION", "Thoughts, notes, and things I'm learning.")


# --- Static files (CSS) and media (uploads) --------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # where `collectstatic` gathers everything for production

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            # Adds a content hash to filenames (style.3f2a1c.css) so browsers can cache forever.
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# Store uploads in S3-compatible object storage (AWS S3, Cloudflare R2, ...) when configured.
# Most hosts wipe the local disk on every deploy, so uploads must live elsewhere.
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["AWS_STORAGE_BUCKET_NAME"],
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL"),  # needed for R2, not AWS
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN"),  # public URL host for files
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "auto"),
            "file_overwrite": False,
            "querystring_auth": False,  # public URLs without expiring signatures
            "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
        },
    }


# --- HTTPS hardening (production only) -------------------------------------------------

if not DEBUG:
    # Hosting platforms terminate HTTPS at a proxy and tell Django via this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Tell browsers to only ever use HTTPS for this site. Start small; raise once confident.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False


# --- Logging: send errors to the console so the host's log viewer shows them ----------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
