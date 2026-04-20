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
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")
        if period_start and period_end and period_start > period_end:
            raise serializers.ValidationError({"message": "period_start 不能晚于 period_end。"})
        return attrs


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
            raise serializers.ValidationError({"message": "period_start 不能晚于 period_end。"})
        return attrs


class TimeRangeRiskReportCreateSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs):
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError({"message": "period_start 不能晚于 period_end。"})
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
    normalized_content = str(raw_content or "").strip()
    if normalized_content.startswith("```"):
        lines = normalized_content.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized_content = "\n".join(lines).strip()

    try:
        payload = json.loads(normalized_content)
    except json.JSONDecodeError as exc:
        raise ValueError("风险抽取结果不是合法 JSON。") from exc

    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        payload["events"] = [
            item
            for item in payload["events"]
            if not (
                isinstance(item, dict)
                and not str(item.get("company_name") or "").strip()
            )
        ]

    serializer = RiskExtractionSchemaSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["events"]
