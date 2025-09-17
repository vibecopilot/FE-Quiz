

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-=r8eyu05d64!peth(0f!3j*n66=b$jcq50f4+mp80$1*#0n=i@'

DEBUG = True

ALLOWED_HOSTS = ["*","192.168.29.107",'10.234.27.35',"192.168.29.239","192.168.29.63","192.168.1.17"]


from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))



INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "common",
    "accounts",
    "learning",
    "django_extensions",
    "corsheaders",
    "rest_framework",
    "django_filters",

    "exams.apps.ExamsConfig",  
]


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'vasisayed09421@gmail.com'
EMAIL_HOST_PASSWORD = 'txjxrdgjarvcgtkh'
EMAIL_TIMEOUT = 20

DEFAULT_FROM_EMAIL = 'FM Admin <vasisayed09421@gmail.com>'

FRONTEND_URL = env.str("FRONTEND_URL", default="http://127.0.0.1:5173").rstrip("/")

CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,               
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.29.107:5173",
    "http://10.234.27.35:5173",
    "http://10.234.27.35:3000",
    "http://192.168.29.107:3000",
    "http://192.168.29.63:3000",
     "http://192.168.29.107:8000", 
      "http://192.168.1.17:8000",
       "http://192.168.1.17:3000",
        "http://192.168.1.17:5173", 
]



CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
        "http://192.168.29.63:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.29.107:5173",
    "http://192.168.29.107:3000",
    "http://10.234.27.35:5173",
    "http://10.234.27.35:3000",
    "http://192.168.29.107:8000", 
     
     "http://192.168.1.17:8000",
       "http://192.168.1.17:3000",
        "http://192.168.1.17:5173", # Add this line
]

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"          # collected static (e.g., for prod)
STATICFILES_DIRS = [BASE_DIR / "static"]        # your local app assets (optional folder)

# Media uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"



QUIZ_ALLOW_SECOND_START_DEV = False

ANTICHEAT_DISABLED = False


AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
}

from datetime import timedelta
TIME_ZONE = "Asia/Kolkata"   
USE_TZ = True


# core/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "quiz-rollover-every-minute": {
        "task": "exams.tasks.rollover_quizzes_and_stages",
        "schedule": 60.0,
    },
}




SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'


USE_I18N = True

USE_TZ = True

# ─── Celery config ─────────────────────────────────────────────────────────────
import os
try:
    from celery.schedules import crontab
except Exception:
    crontab = None  # lets Django start even if Celery isn't installed yet



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
