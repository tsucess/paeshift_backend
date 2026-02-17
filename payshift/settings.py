"""
Django settings for payshift project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Python 3.14 compatibility fix for Django template context
try:
    import django_python314_fix  # noqa: F401
except ImportError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# URL configuration
APPEND_SLASH = False  # Prevent automatic trailing slash redirects

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    # 'drf_spectacular',  # TODO: Install when needed for API documentation
    'corsheaders',
    'channels',
    'django_fsm',
    # 'django_q',  # TODO: Fix migration compatibility issue
    # 'django_q2',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # 'debug_toolbar',  # Phase 2.2d: Performance Testing - Disabled due to auto-reload issues
    
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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',  # Phase 2.2d: Performance Testing - Disabled due to auto-reload issues
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Error handling middleware
    'core.error_handler.ErrorHandlingMiddleware',
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
            'OPTIONS': {
                'timeout': 20,
            },
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

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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
CSRF_USE_SESSIONS = True  # Store CSRF token in session instead of cookie for better security

# Session configuration for cross-origin requests
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow session cookies in cross-origin requests
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript from accessing the session cookie
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session alive after browser closes

# Email configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'taofeeq.muhammad22@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'pakfoxzlpiihcyxi')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'taofeeq.muhammad22@gmail.com')
EMAIL_FILE_PATH = os.getenv('EMAIL_FILE_PATH', os.path.join(BASE_DIR, 'emails'))

# Caching configuration - Phase 2.2c
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'True').lower() == 'true'
REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'True').lower() == 'true'

# Redis Cache Configuration
if CACHE_ENABLED and REDIS_ENABLED:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_CACHE_URL', 'redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                'IGNORE_EXCEPTIONS': True,
                'PARSER_CLASS': 'redis.connection.HiredisParser',
            }
        }
    }
else:
    # Fallback to dummy cache if Redis is disabled
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }

# Cache TTL Settings (in seconds)
CACHE_TTL_PROFILE = int(os.getenv('CACHE_TTL_PROFILE', '3600'))  # 1 hour
CACHE_TTL_REVIEWS = int(os.getenv('CACHE_TTL_REVIEWS', '1800'))  # 30 minutes
CACHE_TTL_PAYMENTS = int(os.getenv('CACHE_TTL_PAYMENTS', '300'))  # 5 minutes
CACHE_TTL_JOBS = int(os.getenv('CACHE_TTL_JOBS', '1800'))  # 30 minutes
CACHE_TTL_APPLICATIONS = int(os.getenv('CACHE_TTL_APPLICATIONS', '300'))  # 5 minutes

# ======= Merged from backup settings.py =======
# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# External URLs
FRONTEND_URL = os.getenv("FRONTEND_URL")
BASE_URL = os.getenv("BASE_URL")


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
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# DRF Spectacular configuration for API documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'Paeshift API',
    'DESCRIPTION': 'Gig Economy Platform API - Connect job seekers with job posters',
    'VERSION': '1.0.0',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development'},
        {'url': 'https://api.paeshift.com', 'description': 'Production'},
    ],
    'CONTACT': {
        'name': 'Paeshift Support',
        'email': 'support@paeshift.com',
    },
    'LICENSE': {
        'name': 'MIT',
    },
    'TAGS': [
        {'name': 'Auth', 'description': 'Authentication endpoints'},
        {'name': 'Jobs', 'description': 'Job management endpoints'},
        {'name': 'Applications', 'description': 'Job application endpoints'},
        {'name': 'Payments', 'description': 'Payment processing endpoints'},
        {'name': 'Ratings', 'description': 'Rating and feedback endpoints'},
        {'name': 'Notifications', 'description': 'Notification endpoints'},
        {'name': 'Chat', 'description': 'Real-time chat endpoints'},
        {'name': 'Gamification', 'description': 'Gamification endpoints'},
        {'name': 'Disputes', 'description': 'Dispute resolution endpoints'},
        {'name': 'Location', 'description': 'Location services endpoints'},
    ],
}

# Logging configuration - Import from core.logging_config
from core.logging_config import get_logging_config
LOGGING = get_logging_config(debug=DEBUG, log_dir=os.path.join(BASE_DIR, 'logs'))


Q_CLUSTER = {
    "name": "DjangoQ",
    "workers": 4,
    "timeout": 60,   # time limit for a task
    "retry": 90,     # retry should be > timeout
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}



# =
# 💰 PAYMENT GATEWAYS
# =
PAYSTACK_PUBLIC_KEY = os.getenv(
    "PAYSTACK_PUBLIC_KEY", "pk_test_01db91d9678ee0d25483a7d0bc9783951938b45d"
)
FLUTTERWAVE_SECRET_KEY = os.getenv(
    "FLUTTERWAVE_SECRET_KEY", "FLWSECK_TEST-5cfee76ec023b25f6e002bad2bfc1d95-X"
)
FLUTTERWAVE_PUBLIC_KEY = os.getenv(
    "FLUTTERWAVE_PUBLIC_KEY", "FLWPUBK_TEST-c9b0667be3b2500fb3ee42a46a8ae054-X"
)
FLUTTERWAVE_WEBHOOK_HASH = os.getenv(
    "FLUTTERWAVE_WEBHOOK_HASH", "test_hash_for_development"
)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_ef9e10ac4bf5dcd69617a61636d21c88528afb1d")

# ==
# 📌 Django Debug Toolbar Configuration (Phase 2.2d)
# ==
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda r: DEBUG,
    'SHOW_TEMPLATE_CONTEXT': True,
    'ENABLE_STACKTRACES': True,
    'SQL_WARNING_THRESHOLD': 500,  # ms
}

