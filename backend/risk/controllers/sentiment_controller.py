from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user
from risk.services.sentiment_service import analyze_sentiment_for_documents


class SentimentAnalyzeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)

        try:
            payload = analyze_sentiment_for_documents(
                user=user,
                dataset_id=request.data.get("dataset_id"),
                document_ids=request.data.get("document_ids"),
            )
        except ValueError as exc:
            return error_response(code=400, message=str(exc), status_code=400)

        return success_response(message="舆情分析完成。", data=payload)
