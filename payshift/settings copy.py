"""
Django settings for payshift project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'channels',
    'django_fsm',
    'django_q',
    # 'django_q2',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    
    # Local apps
    'accounts',
    'core',
    'disputes',
    'adminaccess',
    # 'chatapp',
    'jobs',
    'payment',
    'notifications',
    'rating',
    'gamification',
    'userlocation',
    'jobchat',
    'godmode',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'payshift.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'payshift.wsgi.application'

# Database configuration
# Try to use smart database config, fallback to environment variables
FORCE_SQLITE = os.getenv('FORCE_SQLITE', 'False').lower() == 'true'
if FORCE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.getenv('SQLITE_DB_PATH', 'db.sqlite3'),
            'OPTIONS': {'timeout': 20},
        }
    }
else:
    try:
        from smart_db_config import get_database_settings
        DATABASES = {
            'default': get_database_settings()
        }
    except ImportError:
        print("⚠️  smart_db_config not available, using SQLite fallback")
        # Fallback to SQLite with proper configuration
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
                'OPTIONS': {
                    'timeout': 20,
                },
            }
        }

# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    # BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.CustomUser'

# CORS settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://localhost:8000').split(',')

# Email configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'onlypayshift@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Payshift <onlypayshift@gmail.com>')

# Disable caching as requested
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'False').lower() == 'true'
REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'False').lower() == 'true'

# Caches (disabled)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
# ======= Merged from backup settings.py =======
# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "AIzaSyCiCDANDMScIcsm-d0QMDaAXFS8M-0GdLU")

# External URLs
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# Godmode API Token
GODMODE_API_TOKEN = os.getenv("GODMODE_API_TOKEN", "godmode-secret-token-change-in-production")

# Cache Consistency Settings
CACHE_CONSISTENCY_CHECK_PROBABILITY = float(os.getenv("CACHE_CONSISTENCY_CHECK_PROBABILITY", "0.01"))  # 1% chance
CACHE_CONSISTENCY_CHECK_INTERVAL = int(os.getenv("CACHE_CONSISTENCY_CHECK_INTERVAL", "3600"))  # 1 hour
CACHE_CONSISTENCY_THRESHOLD = float(os.getenv("CACHE_CONSISTENCY_THRESHOLD", "0.9"))  # 90% consistency required
CACHE_AUTO_RECONCILE_THRESHOLD = float(os.getenv("CACHE_AUTO_RECONCILE_THRESHOLD", "0.7"))  # Auto-reconcile if below 70%
CACHE_CONSISTENCY_SAMPLE_SIZE = int(os.getenv("CACHE_CONSISTENCY_SAMPLE_SIZE", "50"))  # Check 50 instances

# Chat App Settings
CHAT_ENABLE_WEBSOCKETS = True
CHAT_MESSAGE_RETENTION_DAYS = 30
CHAT_MAX_FILE_SIZE = 5242880  # 5MB in bytes
# CHAT_ALLOWED_FILE_TYPES = os.getenv(
#     "CHAT_ALLOWED_FILE_TYPES",
#     "image/jpg,image/jpeg,image/png,image/gif,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# ).split(",")
CHAT_ALLOWED_FILE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
]
CHAT_NOTIFICATION_ENABLED = True
WEBSOCKET_TIMEOUT = 3600  # 1 hour

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


Q_CLUSTER = {
    "name": "DjangoQ",
    "workers": 4,
    "timeout": 60,   # time limit for a task
    "retry": 90,     # retry should be > timeout
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}
