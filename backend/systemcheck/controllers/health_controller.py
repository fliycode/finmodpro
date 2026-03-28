from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.api_response import success_response


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return success_response(
            data={
                "status": "ok",
                "service": "finmodpro-backend",
                "environment": settings.APP_ENV,
                "timestamp": timezone.now().isoformat(),
            }
        )
