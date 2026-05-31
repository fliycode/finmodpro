"""
Django 项目配置文件（SpringBoot 类比: application.yml）

此文件集中管理所有 Django 配置项，相当于 SpringBoot 的 application.yml / application.properties。
Django settings 是一个 Python 模块，每个配置项是一个模块级大写变量，框架自动读取。

主要配置板块:
  - 数据库连接 (DATABASES) — 类似 spring.datasource.*
  - 中间件 (MIDDLEWARE) — 类似 Spring Security Filter Chain
  - 安装应用 (INSTALLED_APPS) — 类似 Maven/Gradle 的模块依赖
  - REST Framework — 类似 @RestController 的全局配置
  - Celery — 异步任务队列
  - JWT / Auth — 认证令牌配置
  - RAG / 知识库 / 风险提取 — 业务配置
  - 日志 — Logback/log4j 等价
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from kombu import Queue

from config.env import get_bool_env, get_env, get_int_env, get_list_env

# 项目根目录路径（backend/ 目录）
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== Django 基础配置 ====================
SECRET_KEY = get_env("DJANGO_SECRET_KEY", "dev-only-placeholder-secret-key")
DEBUG = get_bool_env("DJANGO_DEBUG", True)
APP_ENV = get_env("APP_ENV", "development")

# 允许访问的域名列表（生产环境需限制）
ALLOWED_HOSTS = get_list_env("DJANGO_ALLOWED_HOSTS", ["*"])
# CSRF 可信源（AJAX 请求需要）
CSRF_TRUSTED_ORIGINS = get_list_env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["http://47.85.103.76:5173",],
)
# CORS 跨域配置（允许前端跨域访问后端 API）
CORS_ALLOWED_ORIGINS = get_list_env(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    ["http://47.85.103.76:5173",],
)
CORS_ALLOW_CREDENTIALS = get_bool_env("DJANGO_CORS_ALLOW_CREDENTIALS", True)

# 文件上传 / 媒体文件存储配置
MEDIA_URL = get_env("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(get_env("MEDIA_ROOT", str(BASE_DIR / "media")))
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MB 上传限制
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024   # 50 MB 文件限制

# ==================== 数据库配置 ====================
# SpringBoot 类比: spring.datasource.*
DB_ENGINE = get_env("DB_ENGINE", "mysql")
DB_NAME = get_env("DB_NAME", "finmodpro")
DB_HOST = get_env("DB_HOST", "127.0.0.1")
DB_PORT = get_int_env("DB_PORT", 3306)
DB_USER = get_env("DB_USER", "root")
DB_PASSWORD = get_env("DB_PASSWORD", "")
DB_CONN_MAX_AGE = get_int_env("DB_CONN_MAX_AGE", 600)

if DB_ENGINE != "mysql":
    raise ImproperlyConfigured("Only MySQL is supported.")

# ==================== 基础设施（Redis / Milvus） ====================
REDIS_ENABLED = get_bool_env("REDIS_ENABLED", False)
REDIS_HOST = get_env("REDIS_HOST", "127.0.0.1")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_DB = get_int_env("REDIS_DB", 0)
REDIS_PASSWORD = get_env("REDIS_PASSWORD", "")

# Milvus 向量数据库配置（文档检索用）
MILVUS_URI = get_env("MILVUS_URI", str(BASE_DIR / "milvus.db"))
MILVUS_TOKEN = get_env("MILVUS_TOKEN", "")
MILVUS_DB_NAME = get_env("MILVUS_DB_NAME", "")
MILVUS_COLLECTION_NAME = get_env(
    "MILVUS_COLLECTION_NAME", "knowledgebase_document_chunks",
)

# ==================== 知识库配置 ====================
# 文本切片大小和重叠量
KB_CHUNK_SIZE = get_int_env("KB_CHUNK_SIZE", 400)
KB_CHUNK_OVERLAP = get_int_env("KB_CHUNK_OVERLAP", 50)
KB_EMBEDDING_DIMENSION = get_int_env("KB_EMBEDDING_DIMENSION", 1024)
KB_EMBEDDING_BATCH_SIZE = get_int_env("KB_EMBEDDING_BATCH_SIZE", 10)

# 句子窗口检索配置（增强上下文）
KB_SENTENCE_WINDOW_ENABLED = get_bool_env("KB_SENTENCE_WINDOW_ENABLED", False)
KB_SENTENCE_WINDOW_SIZE = get_int_env("KB_SENTENCE_WINDOW_SIZE", 3)

# 层级分块配置（大文档自动切分）
KB_HIERARCHICAL_TEXT_THRESHOLD = get_int_env("KB_HIERARCHICAL_TEXT_THRESHOLD", 500000)
KB_HIERARCHICAL_CHUNK_THRESHOLD = get_int_env("KB_HIERARCHICAL_CHUNK_THRESHOLD", 3000)
KB_SECTION_CHUNK_SIZE = get_int_env("KB_SECTION_CHUNK_SIZE", 2000)
KB_SECTION_CHUNK_OVERLAP = get_int_env("KB_SECTION_CHUNK_OVERLAP", 200)

# ==================== RAG 检索配置 ====================
RAG_RETRIEVAL_CANDIDATE_MULTIPLIER = get_int_env("RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", 5)
RAG_RETRIEVAL_CANDIDATE_FLOOR = get_int_env("RAG_RETRIEVAL_CANDIDATE_FLOOR", 20)
RAG_RRF_K = get_int_env("RAG_RRF_K", 60)  # 融合检索的 RRF 参数
RAG_HYBRID_SEARCH_ENABLED = get_bool_env("RAG_HYBRID_SEARCH_ENABLED", False)
RAG_MULTI_QUERY_VARIANT_COUNT = get_int_env("RAG_MULTI_QUERY_VARIANT_COUNT", 3)
RAG_SCORE_FILTER_THRESHOLD = float(os.getenv("RAG_SCORE_FILTER_THRESHOLD", "0.12"))
RAG_MYSQL_FULLTEXT_ENABLED = get_bool_env("RAG_MYSQL_FULLTEXT_ENABLED", True)
RAG_BM25_ENABLED = get_bool_env("RAG_BM25_ENABLED", True)
RAG_BM25_LANGUAGE = get_env("RAG_BM25_LANGUAGE", "zh")
RAG_BM25_CACHE_TTL = get_int_env("RAG_BM25_CACHE_TTL", 600)
CHAT_RAG_KEYWORD_FALLBACK_ENABLED = get_bool_env("CHAT_RAG_KEYWORD_FALLBACK_ENABLED", False)

# ==================== 风险提取配置 ====================
RISK_EXTRACTION_CHUNK_TOP_K = get_int_env("RISK_EXTRACTION_CHUNK_TOP_K", 20)
RISK_EXTRACTION_MAX_ROUNDS = get_int_env("RISK_EXTRACTION_MAX_ROUNDS", 2)
RISK_EXTRACTION_SMALL_DOC_THRESHOLD = get_int_env("RISK_EXTRACTION_SMALL_DOC_THRESHOLD", 10)
RISK_EXTRACTION_MIN_FILTERED_CHUNKS = get_int_env("RISK_EXTRACTION_MIN_FILTERED_CHUNKS", 3)
RISK_EXTRACTION_CONTEXT_MAX_CHUNKS = get_int_env("RISK_EXTRACTION_CONTEXT_MAX_CHUNKS", 8)
RISK_EXTRACTION_CONTEXT_MAX_CHARS = get_int_env("RISK_EXTRACTION_CONTEXT_MAX_CHARS", 6000)
RISK_EXTRACTION_STALE_SECONDS = get_int_env("RISK_EXTRACTION_STALE_SECONDS", 900)
RISK_EXTRACTION_QUEUE = get_env("RISK_EXTRACTION_QUEUE", "risk")
RISK_EXTRACTION_TASK_SOFT_TIME_LIMIT = get_int_env("RISK_EXTRACTION_TASK_SOFT_TIME_LIMIT", 90)
RISK_EXTRACTION_TASK_TIME_LIMIT = get_int_env("RISK_EXTRACTION_TASK_TIME_LIMIT", 105)
RISK_EXTRACTION_BATCH_TASK_SOFT_TIME_LIMIT = get_int_env("RISK_EXTRACTION_BATCH_TASK_SOFT_TIME_LIMIT", 180)
RISK_EXTRACTION_BATCH_TASK_TIME_LIMIT = get_int_env("RISK_EXTRACTION_BATCH_TASK_TIME_LIMIT", 210)
RISK_EXTRACTION_QUEUE_TIMEOUT_SECONDS = get_int_env("RISK_EXTRACTION_QUEUE_TIMEOUT_SECONDS", 180)
RISK_EXTRACTION_STAGE_TIMEOUT_SECONDS = get_int_env("RISK_EXTRACTION_STAGE_TIMEOUT_SECONDS", 75)
RISK_EXTRACTION_SUBMISSION_LIMIT = get_int_env("RISK_EXTRACTION_SUBMISSION_LIMIT", 2)
RISK_EXTRACTION_LLM_TIMEOUT_SECONDS = get_int_env("RISK_EXTRACTION_LLM_TIMEOUT_SECONDS", 25)
RISK_EXTRACTION_RETRIEVAL_TIMEOUT_SECONDS = get_int_env("RISK_EXTRACTION_RETRIEVAL_TIMEOUT_SECONDS", 20)

CHAT_RAG_QUERY_VARIANT_COUNT = get_int_env("CHAT_RAG_QUERY_VARIANT_COUNT", 1)
CHAT_RAG_RETRIEVAL_TOP_K_MULTIPLIER = get_int_env("CHAT_RAG_RETRIEVAL_TOP_K_MULTIPLIER", 2)
CHAT_RAG_RETRIEVAL_TOP_K_FLOOR = get_int_env("CHAT_RAG_RETRIEVAL_TOP_K_FLOOR", 8)

# ==================== 微调 / LLM 模型配置 ====================
PDF_FALLBACK_ENABLED = get_bool_env("PDF_FALLBACK_ENABLED", False)
FINE_TUNE_EXPORT_ROOT = Path(
    get_env("FINE_TUNE_EXPORT_ROOT", str(BASE_DIR / "exports" / "fine-tune-runs"))
)
FINE_TUNE_EXPORT_BASE_URL = get_env("FINE_TUNE_EXPORT_BASE_URL", "")
FINE_TUNE_CALLBACK_SECRET = get_env("FINE_TUNE_CALLBACK_SECRET", SECRET_KEY)

# ==================== Celery 异步任务配置 ====================
# SpringBoot 类比: spring.task.* 或 @EnableAsync 配置
CELERY_BROKER_URL = get_env("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = get_env("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = get_bool_env("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = get_bool_env("CELERY_TASK_EAGER_PROPAGATES", True)
CELERY_TASK_STORE_EAGER_RESULT = get_bool_env("CELERY_TASK_STORE_EAGER_RESULT", False)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE = "Asia/Shanghai"

# 任务队列分配 — 风险提取有独立队列，避免阻塞通用任务
CELERY_TASK_DEFAULT_QUEUE = "celery"
CELERY_TASK_QUEUES = (
    Queue("celery"),
    Queue(RISK_EXTRACTION_QUEUE),
)
CELERY_TASK_ROUTES = {
    "risk.extract_document_task": {"queue": RISK_EXTRACTION_QUEUE},
    "risk.batch_extract_document_task": {"queue": RISK_EXTRACTION_QUEUE},
}

# ==================== 聊天 / 记忆配置 ====================
CHAT_CONTEXT_RECENT_MESSAGES = get_int_env("CHAT_CONTEXT_RECENT_MESSAGES", 8)
CHAT_MEMORY_RESULT_LIMIT = get_int_env("CHAT_MEMORY_RESULT_LIMIT", 5)
CHAT_SUMMARY_TRIGGER_MESSAGES = get_int_env("CHAT_SUMMARY_TRIGGER_MESSAGES", 6)

# ==================== 日志配置 ====================
APP_LOG_LEVEL = get_env("APP_LOG_LEVEL", "INFO").upper()
KNOWLEDGEBASE_LOG_LEVEL = get_env("KNOWLEDGEBASE_LOG_LEVEL", APP_LOG_LEVEL).upper()
RISK_LOG_LEVEL = get_env("RISK_LOG_LEVEL", APP_LOG_LEVEL).upper()
RAG_LOG_LEVEL = get_env("RAG_LOG_LEVEL", APP_LOG_LEVEL).upper()

# 数据清洗质量阈值
KB_CLEANING_MIN_QUALITY_SCORE = float(os.getenv("KB_CLEANING_MIN_QUALITY_SCORE", "60"))
KB_CLEANING_WARN_QUALITY_SCORE = float(os.getenv("KB_CLEANING_WARN_QUALITY_SCORE", "80"))
KB_CLEANING_BLOCK_BELOW_THRESHOLD = get_bool_env(
    "KB_CLEANING_BLOCK_BELOW_THRESHOLD", False,
)

# ==================== JWT 认证配置 ====================
# SpringBoot 类比: spring.security.oauth2.resourceserver.jwt.*
JWT_SECRET_KEY = get_env("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = get_int_env("JWT_ACCESS_TOKEN_LIFETIME_SECONDS", 900)  # 15分钟
JWT_REMEMBER_ME_LIFETIME_SECONDS = get_int_env("JWT_REMEMBER_ME_LIFETIME_SECONDS", 7 * 24 * 60 * 60)  # 7天

# Refresh Token 配置（存于 HTTP-only Cookie 中，更安全）
AUTH_REFRESH_TOKEN_LIFETIME_SECONDS = get_int_env("AUTH_REFRESH_TOKEN_LIFETIME_SECONDS", 24 * 60 * 60)
AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS = get_int_env(
    "AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS", 7 * 24 * 60 * 60,
)
AUTH_REFRESH_COOKIE_NAME = get_env("AUTH_REFRESH_COOKIE_NAME", "finmodpro_refresh")
AUTH_REFRESH_COOKIE_PATH = get_env("AUTH_REFRESH_COOKIE_PATH", "/api/auth")
AUTH_REFRESH_COOKIE_SAMESITE = get_env("AUTH_REFRESH_COOKIE_SAMESITE", "Lax")
AUTH_REFRESH_COOKIE_SECURE = get_bool_env("AUTH_REFRESH_COOKIE_SECURE", False)
AUTH_REFRESH_COOKIE_DOMAIN = get_env("AUTH_REFRESH_COOKIE_DOMAIN", "")
AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS = get_int_env(
    "AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS", 30 * 60,
)

# ==================== 应用注册 ====================
# SpringBoot 类比: Maven/Gradle 多模块项目中的各个子模块
# 每个 app 是一个独立的功能模块，有自己的 models/views/urls
INSTALLED_APPS = [
    # Django 内置应用
    "django.contrib.admin",         # 管理后台 (/admin)
    "django.contrib.auth",          # 用户认证框架（类似 Spring Security）
    "django.contrib.contenttypes",  # 内容类型框架
    "django.contrib.sessions",      # 会话管理
    "django.contrib.messages",      # 消息框架
    "django.contrib.staticfiles",   # 静态文件管理
    # 第三方应用
    "corsheaders",                  # CORS 跨域支持
    "rest_framework",               # DRF — Django REST API 框架（类似 Spring MVC @RestController）
    # 本项目应用
    "authentication",               # 用户认证
    "rbac",                         # 角色权限管理
    "knowledgebase",                # 知识库 / 文档管理
    "llm",                          # LLM 模型管理
    "rag",                          # RAG 检索增强生成
    "chat",                         # 对话系统
    "risk",                         # 风险分析与提取
    "systemcheck",                  # 系统健康检查
    "django_celery_beat",           # 定时任务调度
    "ops",                          # 运维监控
    "eval",                         # 模型评估与测试
]

# ==================== 中间件配置 ====================
# SpringBoot 类比: Filter Chain（过滤链）
# 每个请求按 MIDDLEWARE 列表顺序依次经过这些中间件
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",       # 安全头
    "corsheaders.middleware.CorsMiddleware",               # CORS 处理
    "django.contrib.sessions.middleware.SessionMiddleware", # 会话管理
    "django.middleware.common.CommonMiddleware",            # 通用中间件（URL 规范化等）
    "django.middleware.csrf.CsrfViewMiddleware",            # CSRF 防护
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # 用户认证
    "django.contrib.messages.middleware.MessageMiddleware",    # 消息
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # 防点击劫持
]

ROOT_URLCONF = "config.urls"  # 根 URL 路由配置文件

# 模板引擎配置（本项目后端主要返回 JSON，模板仅用于管理后台）
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

# ==================== 数据库连接 ====================
# SpringBoot 类比: spring.datasource.url / username / password
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

# ==================== 缓存配置 ====================
# SpringBoot 类比: spring.cache.type=redis
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

# ==================== Django REST Framework 配置 ====================
# SpringBoot 类比: @RestController 全局配置 + Spring Security 配置
REST_FRAMEWORK = {
    # 默认认证方式：JWT Token 从 Authorization header 获取
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "authentication.drf_authentication.JWTAuthentication",
    ],
    # 默认权限：所有 API 需要登录（类似 @PreAuthorize("isAuthenticated()")）
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # 自定义异常处理器 — 统一 API 响应格式
    "EXCEPTION_HANDLER": "common.drf_exception_handler.custom_exception_handler",
}

# Django 国际化配置
LANGUAGE_CODE = "zh-hans"  # 简体中文
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# ==================== 日志配置 ====================
# SpringBoot 类比: logback-spring.xml
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "common.logging.StructuredKeyValueFormatter",  # 结构化 JSON 日志
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": APP_LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
        "knowledgebase": {
            "handlers": ["console"],
            "level": KNOWLEDGEBASE_LOG_LEVEL,
            "propagate": False,
        },
        "risk": {
            "handlers": ["console"],
            "level": RISK_LOG_LEVEL,
            "propagate": False,
        },
        "rag": {
            "handlers": ["console"],
            "level": RAG_LOG_LEVEL,
            "propagate": False,
        },
        "common.observability": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
