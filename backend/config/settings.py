from pathlib import Path

from config.env import get_bool_env, get_env, get_int_env, get_list_env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = get_env("DJANGO_SECRET_KEY", "dev-only-placeholder-secret-key")
DEBUG = get_bool_env("DJANGO_DEBUG", True)
APP_ENV = get_env("APP_ENV", "development")

ALLOWED_HOSTS = get_list_env("DJANGO_ALLOWED_HOSTS", ["*"])
CSRF_TRUSTED_ORIGINS = get_list_env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    [
        "http://47.85.103.76:5173",
    ],
)
CORS_ALLOWED_ORIGINS = get_list_env(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    [
        "http://47.85.103.76:5173",
    ],
)

DB_ENGINE = get_env("DB_ENGINE", "sqlite")
DB_NAME = get_env("DB_NAME", str(BASE_DIR / "db.sqlite3"))
DB_HOST = get_env("DB_HOST", "127.0.0.1")
DB_PORT = get_int_env("DB_PORT", 3306)
DB_USER = get_env("DB_USER", "root")
DB_PASSWORD = get_env("DB_PASSWORD", "")
DB_CONN_MAX_AGE = get_int_env("DB_CONN_MAX_AGE", 60)

REDIS_ENABLED = get_bool_env("REDIS_ENABLED", False)
REDIS_HOST = get_env("REDIS_HOST", "127.0.0.1")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_DB = get_int_env("REDIS_DB", 0)
REDIS_PASSWORD = get_env("REDIS_PASSWORD", "")

CELERY_BROKER_URL = get_env("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = get_env("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = get_bool_env("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = get_bool_env("CELERY_TASK_EAGER_PROPAGATES", True)
CELERY_TASK_STORE_EAGER_RESULT = get_bool_env("CELERY_TASK_STORE_EAGER_RESULT", False)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE = "Asia/Shanghai"

JWT_SECRET_KEY = get_env("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = get_int_env(
    "JWT_ACCESS_TOKEN_LIFETIME_SECONDS",
    7200,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "authentication",
    "rbac",
    "knowledgebase",
    "rag",
    "chat",
    "systemcheck",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_NAME,
        }
    }

if REDIS_ENABLED:
    redis_auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    redis_location = f"redis://{redis_auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_location,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "finmodpro-backend-local",
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "zh-hans"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
