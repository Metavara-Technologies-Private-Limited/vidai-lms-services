"""
Django settings for django_rest_main project.
"""

# ================================
#  IMPORTS (FIXED)
# ================================
from pathlib import Path
import os   # ADDED (needed for logging + general use)

# ================================
#  BASE DIR (FIXED – ONLY ONCE)
# ================================
BASE_DIR = Path(__file__).resolve().parent.parent
#  REMOVED duplicate BASE_DIR definitions at bottom


# ================================
# SECURITY
# ================================
SECRET_KEY = 'django-insecure-b#--p%6fpdr-ub523h198vs!#-2%fvtv+at(_@tzr#kaazchp='
DEBUG = True

#  IMPORTANT FOR SERVER ACCESS
ALLOWED_HOSTS = ["0.0.0.0", "127.0.0.1", "72.62.227.137","localhost","backend.metavaratechnologies.com"]  #  ADDED VPS IP


# ================================
# APPLICATION DEFINITION
# ================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',
    'drf_yasg',

    # Local apps
    'restapi',
]

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/25767405/ucb1mwo/"

MIDDLEWARE = [
    'restapi.middleware.RequestIDMiddleware',   # Custom middleware
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lms_main.urls'

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

WSGI_APPLICATION = 'lms_main.wsgi.application'


# ================================
# DATABASE (UNCHANGED + PORT ADDED)
# ================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'stage2_db',
        'USER': 'postgres',
        'PASSWORD': 'saimohan',
        'HOST': 'host.docker.internal',
        'PORT': '5432',   # ✅ ADDED (important)
    }
}


# ================================
# PASSWORD VALIDATION
# ================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ================================
# INTERNATIONALIZATION
# ================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ================================
#  STATIC FILES (FIXED — MAIN ISSUE)
# ================================
STATIC_URL = '/static/'                      # ← UPDATED
STATIC_ROOT = BASE_DIR / 'static'           # ← ADDED (IMPORTANT)           #  ADDED (REQUIRED for collectstatic)

#  REMOVED old STATIC_ROOT using os.path.join
#  REMOVED missing STATIC_ROOT error cause


# ================================
# DEFAULT PK FIELD
# ================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ================================
# CORS
# ================================
CORS_ALLOW_ALL_ORIGINS = True


# ================================
# DRF
# ================================
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'restapi.exception_handler.custom_exception_handler'
}


# ================================
# LOGGING (CLEANED, BASE_DIR SAFE)
# ================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "detailed": {
            "format": "[{levelname}] {asctime} {name}:{lineno} — {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },

    "handlers": {
        "api_file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "restapi/log/api.log",
            "formatter": "detailed",
        },
    },

    "loggers": {
        "restapi": {
            "handlers": ["api_file"],
            "level": "ERROR",
            "propagate": True,
        },
        "django": {
            "handlers": ["api_file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}


# ================================
# SWAGGER
# ================================
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Format: Bearer <JWT token>",
        }
    }
}

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")

FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")

FRONTEND_URL = os.getenv("FRONTEND_URL")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL")
