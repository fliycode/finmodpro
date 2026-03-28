import json

from rest_framework import serializers

from risk.models import RiskEvent, RiskReport


class RiskExtractionEventSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    risk_type = serializers.CharField(max_length=128)
    risk_level = serializers.ChoiceField(choices=RiskEvent.LEVEL_CHOICES)
    event_time = serializers.DateTimeField(required=False, allow_null=True)
    summary = serializers.CharField()
    evidence_text = serializers.CharField()
    confidence_score = serializers.DecimalField(max_digits=4, decimal_places=3)
    chunk_id = serializers.IntegerField(required=False, allow_null=True)


class RiskExtractionSchemaSerializer(serializers.Serializer):
    events = RiskExtractionEventSerializer(many=True)


class RiskBatchExtractionRequestSerializer(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class RiskEventListQuerySerializer(serializers.Serializer):
    company_name = serializers.CharField(required=False, allow_blank=False)
    risk_type = serializers.CharField(required=False, allow_blank=False)
    review_status = serializers.ChoiceField(required=False, choices=RiskEvent.STATUS_CHOICES)
    risk_level = serializers.ChoiceField(required=False, choices=RiskEvent.LEVEL_CHOICES)
    document_id = serializers.IntegerField(required=False, min_value=1)


class RiskEventReviewSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(
        choices=(
            (RiskEvent.STATUS_APPROVED, "Approved"),
            (RiskEvent.STATUS_REJECTED, "Rejected"),
        )
    )


class CompanyRiskReportCreateSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")
        if period_start and period_end and period_start > period_end:
            raise serializers.ValidationError("period_start 不能晚于 period_end。")
        return attrs


class RiskEventSummarySerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(source="document.id", read_only=True, allow_null=True)
    chunk_id = serializers.IntegerField(source="chunk.id", read_only=True, allow_null=True)

    class Meta:
        model = RiskEvent
        fields = [
            "id",
            "company_name",
            "risk_type",
            "risk_level",
            "event_time",
            "summary",
            "evidence_text",
            "confidence_score",
            "review_status",
            "document_id",
            "chunk_id",
            "created_at",
            "updated_at",
        ]


class RiskReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskReport
        fields = [
            "id",
            "scope_type",
            "title",
            "company_name",
            "period_start",
            "period_end",
            "summary",
            "content",
            "source_metadata",
            "created_at",
            "updated_at",
        ]


def parse_risk_extraction_payload(raw_content):
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("风险抽取结果不是合法 JSON。") from exc

    serializer = RiskExtractionSchemaSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["events"]
