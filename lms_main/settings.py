"""
Django settings for django_rest_main project.
"""

# ================================
#  IMPORTS
# ================================
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import os

# ================================
#  BASE DIR
# ================================
BASE_DIR = Path(__file__).resolve().parent.parent


# ================================
# SECURITY
# ================================
SECRET_KEY = 'django-insecure-b#--p%6fpdr-ub523h198vs!#-2%fvtv+at(_@tzr#kaazchp='
DEBUG = True

ALLOWED_HOSTS = ['*']  # ✅ FIXED - allows Cloudflare tunnel + all hosts


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
    'django_extensions',

    # Third-party
    'rest_framework',
    'corsheaders',
    'drf_yasg',

    # Local apps
    'restapi',
]

# ================================
# ZAPIER WEBHOOKS
# ================================

# General webhook — lead events, campaign events, social media campaigns
# (unchanged — keep as is)
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/25767405/uxrz9r3/"

# ✅ SINGLE unified Mailchimp Zap URL.
# Previously 2 separate Mailchimp Zaps:
#   OLD Zap 1 — ZAPIER_WEBHOOK_EMAIL_URL              → ucb1mwo → event: email_campaign_created
#   OLD Zap 2 — ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL → uxi208v → event: mailchimp_insights_requested
#
# NOW merged into 1 Zap that handles both events using "Paths by Zapier":
#   Path A: event = "email_campaign_created"        → Send email campaign actions
#   Path B: event = "mailchimp_insights_requested"  → Log/notify insights actions
#
# ⚠️ After creating the new merged Zap in Zapier,
#    replace the URL below with the new webhook URL.
ZAPIER_WEBHOOK_MAILCHIMP_URL = os.getenv(
    "ZAPIER_WEBHOOK_MAILCHIMP_URL",
    "https://hooks.zapier.com/hooks/catch/25767405/uxkfmnd/"  # ← Replace with new merged Zap URL
)

MIDDLEWARE = [
    'restapi.middleware.RequestIDMiddleware',
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lms_main.wsgi.application'


# ================================
# DATABASE
# ================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'PSB_db',
        'USER': 'postgres',
        'PASSWORD': 'admin123',
        'HOST': 'localhost',   # ✅ only IP
        'PORT': '5432',            # ✅ PostgreSQL port
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
# STATIC FILES
# ================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'


# ================================
# MEDIA FILES
# ================================
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


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
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", "480")
)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = int(
    os.getenv("JWT_REFRESH_TOKEN_LIFETIME_DAYS", "30")
)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'restapi.utils.jwt_authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'EXCEPTION_HANDLER': 'restapi.exception_handler.custom_exception_handler'
}


# ================================
# LOGGING
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
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "detailed",
        },
        "api_file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "restapi/log/api.log",
            "formatter": "detailed",
        },
    },

    "loggers": {
        "restapi": {
            "handlers": ["console", "api_file"],
            "level": "INFO",
            "propagate": False,
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


# LINKEDIN
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")

# TWILIO
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# MAILCHIMP
MAILCHIMP_API_KEY = os.getenv("MAILCHIMP_API_KEY", "")

# FACEBOOK
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN", "")
FB_AD_ACCOUNT_ID = os.getenv("FB_AD_ACCOUNT_ID", "")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET", "")

# GOOGLE
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")

# EMAIL
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")