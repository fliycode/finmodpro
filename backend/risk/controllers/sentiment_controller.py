"""
舆情分析控制器 —— POST /api/risk/sentiment/analyze
类比 SpringBoot: 相当于 @RestController 中的 @PostMapping 方法，
对指定数据集或文档集合进行情绪分析和风险倾向评估。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user
from risk.services.sentiment_service import analyze_sentiment_for_documents


class SentimentAnalyzeView(APIView):
    """
    舆情分析视图 —— 对文档进行情绪 + 风险倾向双维度分析。

    类比 SpringBoot: 相当于 @PostMapping("/sentiment/analyze")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        发起舆情分析。

        参数:
            request: Django HttpRequest，body 包含:
                     - dataset_id   (int, 可选): 数据集 ID，全部文档时不传
                     - document_ids (list[int], 可选): 文档 ID 列表

        返回:
            JsonResponse: 包含 summary（总体情绪/风险倾向）、distribution（分布）、
                         source_groups（各文档详情）和 items（逐文档分析结果）的数据。
        """
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
