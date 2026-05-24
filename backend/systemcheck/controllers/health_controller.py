"""
系统健康检查控制器 —— 提供数据库和 Redis 连通性的探测端点。

类比 SpringBoot: 相当于 Spring Actuator 的 /health 端点，
不需要认证即可访问，用于负载均衡器或监控系统的存活检查。
"""

from django.conf import settings
from django.db import connections
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.api_response import success_response


def _check_db():
    """
    检测数据库连接是否正常（执行 SELECT 1）。

    类比 SpringBoot: 相当于 HealthIndicator 的 health() 方法。

    返回:
        bool: 数据库连接正常返回 True，否则返回 False。
    """
    try:
        cursor = connections["default"].cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True
    except Exception:
        return False


def _check_redis():
    """
    检测 Redis 连接是否正常（通过 set + get 操作）。

    类比 SpringBoot: 相当于 RedisHealthIndicator 的实现。

    返回:
        bool: Redis 连接正常返回 True，否则返回 False。
    """
    try:
        from django.core.cache import cache
        cache.set("__health_check__", 1, 5)
        return cache.get("__health_check__") == 1
    except Exception:
        return False


class HealthView(APIView):
    """
    系统健康检查视图 —— GET /api/systemcheck/health

    无需认证，公开可访问。返回数据库和 Redis 的连通性状态。

    类比 SpringBoot: 相当于 @GetMapping("/health") + permitAll()。
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """
        执行健康检查。

        参数:
            request: Django HttpRequest（无需认证 Token）。

        返回:
            JsonResponse: {
                "status": "ok" | "degraded",
                "service": "finmodpro-backend",
                "environment": "(APP_ENV)",
                "timestamp": "(ISO 时间戳)",
                "checks": {"database": "ok"/"error", "redis": "ok"/"error"},
            }
        """
        db_ok = _check_db()
        redis_ok = _check_redis()
        all_ok = db_ok and redis_ok

        return success_response(
            data={
                "status": "ok" if all_ok else "degraded",
                "service": "finmodpro-backend",
                "environment": settings.APP_ENV,
                "timestamp": timezone.now().isoformat(),
                "checks": {
                    "database": "ok" if db_ok else "error",
                    "redis": "ok" if redis_ok else "error",
                },
            }
        )
