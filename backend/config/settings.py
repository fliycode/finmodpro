import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

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
CORS_ALLOW_CREDENTIALS = get_bool_env("DJANGO_CORS_ALLOW_CREDENTIALS", True)
MEDIA_URL = get_env("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(get_env("MEDIA_ROOT", str(BASE_DIR / "media")))

DB_ENGINE = get_env("DB_ENGINE", "mysql")
DB_NAME = get_env("DB_NAME", "finmodpro")
DB_HOST = get_env("DB_HOST", "127.0.0.1")
DB_PORT = get_int_env("DB_PORT", 3306)
DB_USER = get_env("DB_USER", "root")
DB_PASSWORD = get_env("DB_PASSWORD", "")
DB_CONN_MAX_AGE = get_int_env("DB_CONN_MAX_AGE", 60)

if DB_ENGINE != "mysql":
    raise ImproperlyConfigured("Only MySQL is supported.")

REDIS_ENABLED = get_bool_env("REDIS_ENABLED", False)
REDIS_HOST = get_env("REDIS_HOST", "127.0.0.1")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_DB = get_int_env("REDIS_DB", 0)
REDIS_PASSWORD = get_env("REDIS_PASSWORD", "")
MILVUS_URI = get_env("MILVUS_URI", str(BASE_DIR / "milvus.db"))
MILVUS_TOKEN = get_env("MILVUS_TOKEN", "")
MILVUS_DB_NAME = get_env("MILVUS_DB_NAME", "")
MILVUS_COLLECTION_NAME = get_env(
    "MILVUS_COLLECTION_NAME",
    "knowledgebase_document_chunks",
)
KB_CHUNK_SIZE = get_int_env("KB_CHUNK_SIZE", 400)
KB_CHUNK_OVERLAP = get_int_env("KB_CHUNK_OVERLAP", 50)
KB_EMBEDDING_DIMENSION = get_int_env("KB_EMBEDDING_DIMENSION", 64)

UNSTRUCTURED_API_URL = get_env("UNSTRUCTURED_API_URL", "http://unstructured-api:8000")
UNSTRUCTURED_API_URL_CONFIGURED = bool(os.getenv("UNSTRUCTURED_API_URL", "").strip())
UNSTRUCTURED_API_KEY = get_env("UNSTRUCTURED_API_KEY", "")
UNSTRUCTURED_TIMEOUT_SECONDS = get_int_env("UNSTRUCTURED_TIMEOUT_SECONDS", 30)
UNSTRUCTURED_PDF_STRATEGY = get_env("UNSTRUCTURED_PDF_STRATEGY", "auto")
UNSTRUCTURED_DOCX_STRATEGY = get_env("UNSTRUCTURED_DOCX_STRATEGY", "auto")
UNSTRUCTURED_PDF_FALLBACK_ENABLED = get_bool_env("UNSTRUCTURED_PDF_FALLBACK_ENABLED", True)
FINE_TUNE_EXPORT_ROOT = Path(
    get_env("FINE_TUNE_EXPORT_ROOT", str(BASE_DIR / "exports" / "fine-tune-runs"))
)
FINE_TUNE_EXPORT_BASE_URL = get_env("FINE_TUNE_EXPORT_BASE_URL", "")
FINE_TUNE_CALLBACK_SECRET = get_env("FINE_TUNE_CALLBACK_SECRET", SECRET_KEY)
LANGFUSE_HOST = get_env("LANGFUSE_HOST", "")
LANGFUSE_PUBLIC_KEY = get_env("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = get_env("LANGFUSE_SECRET_KEY", "")
LITELLM_GENERATED_CONFIG_ROOT = Path(
    get_env(
        "LITELLM_GENERATED_CONFIG_ROOT",
        str(BASE_DIR.parent / "deploy" / "litellm" / "generated"),
    )
)
LITELLM_BASE_CONFIG_PATH = get_env(
    "LITELLM_BASE_CONFIG_PATH",
    str(BASE_DIR.parent / "deploy" / "litellm" / "litellm_config.yaml"),
)
LITELLM_RENDERED_CONFIG_PATH = get_env(
    "LITELLM_RENDERED_CONFIG_PATH",
    str(BASE_DIR.parent / "deploy" / "litellm" / "litellm_config_rendered.yaml"),
)

CELERY_BROKER_URL = get_env("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = get_env("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = get_bool_env("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = get_bool_env("CELERY_TASK_EAGER_PROPAGATES", True)
CELERY_TASK_STORE_EAGER_RESULT = get_bool_env("CELERY_TASK_STORE_EAGER_RESULT", False)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE = "Asia/Shanghai"

CHAT_CONTEXT_RECENT_MESSAGES = get_int_env("CHAT_CONTEXT_RECENT_MESSAGES", 8)
CHAT_MEMORY_RESULT_LIMIT = get_int_env("CHAT_MEMORY_RESULT_LIMIT", 5)
CHAT_SUMMARY_TRIGGER_MESSAGES = get_int_env("CHAT_SUMMARY_TRIGGER_MESSAGES", 6)

JWT_SECRET_KEY = get_env("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = get_int_env(
    "JWT_ACCESS_TOKEN_LIFETIME_SECONDS",
    900,
)
JWT_REMEMBER_ME_LIFETIME_SECONDS = get_int_env(
    "JWT_REMEMBER_ME_LIFETIME_SECONDS",
    7 * 24 * 60 * 60,
)
AUTH_REFRESH_TOKEN_LIFETIME_SECONDS = get_int_env(
    "AUTH_REFRESH_TOKEN_LIFETIME_SECONDS",
    24 * 60 * 60,
)
AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS = get_int_env(
    "AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS",
    7 * 24 * 60 * 60,
)
AUTH_REFRESH_COOKIE_NAME = get_env("AUTH_REFRESH_COOKIE_NAME", "finmodpro_refresh")
AUTH_REFRESH_COOKIE_PATH = get_env("AUTH_REFRESH_COOKIE_PATH", "/api/auth")
AUTH_REFRESH_COOKIE_SAMESITE = get_env("AUTH_REFRESH_COOKIE_SAMESITE", "Lax")
AUTH_REFRESH_COOKIE_SECURE = get_bool_env("AUTH_REFRESH_COOKIE_SECURE", False)
AUTH_REFRESH_COOKIE_DOMAIN = get_env("AUTH_REFRESH_COOKIE_DOMAIN", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "authentication",
    "rbac",
    "knowledgebase",
    "llm",
    "rag",
    "chat",
    "risk",
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
        }
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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "authentication.drf_authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "common.drf_exception_handler.custom_exception_handler",
}

LANGUAGE_CODE = "zh-hans"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
