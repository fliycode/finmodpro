from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def health_view(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "finmodpro-backend",
            "environment": settings.APP_ENV,
            "timestamp": timezone.now().isoformat(),
        }
    )
