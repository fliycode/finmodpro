from django.conf import settings
from django.db import connections
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.api_response import success_response


def _check_db():
    try:
        cursor = connections["default"].cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True
    except Exception:
        return False


def _check_redis():
    try:
        from django.core.cache import cache
        cache.set("__health_check__", 1, 5)
        return cache.get("__health_check__") == 1
    except Exception:
        return False


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
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
