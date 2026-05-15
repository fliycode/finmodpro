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
    why_it_matters = serializers.CharField(required=False, allow_blank=True, default="")
    impact_scope = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    watchpoints = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    citations = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )


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
    document_filename = serializers.CharField(source="document.filename", read_only=True, allow_null=True, default=None)
    document_file_size = serializers.IntegerField(source="document.file_size", read_only=True, allow_null=True, default=0)
    document_source_date = serializers.DateField(source="document.source_date", read_only=True, allow_null=True, default=None)
    document_title = serializers.CharField(source="document.title", read_only=True, allow_null=True, default=None)
    extraction_metadata = serializers.SerializerMethodField()
    taxonomy_code = serializers.SerializerMethodField()
    citations = serializers.SerializerMethodField()
    materiality_score = serializers.SerializerMethodField()
    likelihood_score = serializers.SerializerMethodField()
    impact_scope = serializers.SerializerMethodField()
    why_it_matters = serializers.SerializerMethodField()
    watchpoints = serializers.SerializerMethodField()
    requires_human_review = serializers.SerializerMethodField()
    review_priority = serializers.SerializerMethodField()

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
            "document_filename",
            "document_file_size",
            "document_source_date",
            "document_title",
            "taxonomy_code",
            "citations",
            "materiality_score",
            "likelihood_score",
            "impact_scope",
            "why_it_matters",
            "watchpoints",
            "requires_human_review",
            "review_priority",
            "extraction_metadata",
            "created_at",
            "updated_at",
        ]

    def _get_meta(self, obj):
        return obj.metadata or {}

    def get_extraction_metadata(self, obj):
        meta = self._get_meta(obj)
        pipeline = meta.get("extraction_pipeline")
        if not pipeline:
            return None
        return {
            "rounds_completed": pipeline.get("rounds_completed", 1),
            "verification_passed": pipeline.get("verification_passed", True),
            "total_llm_calls": pipeline.get("total_llm_calls", 1),
            "human_review_count": pipeline.get("human_review_count", 0),
            "filtered_chunks": pipeline.get("chunk_filter", {}).get("filtered_chunks"),
            "total_chunks": pipeline.get("chunk_filter", {}).get("total_chunks"),
            "version": pipeline.get("schema_version") or meta.get("extraction_version", "v1"),
        }

    def get_taxonomy_code(self, obj):
        return self._get_meta(obj).get("taxonomy_code") or obj.risk_type

    def get_citations(self, obj):
        citations = self._get_meta(obj).get("citations")
        return citations if isinstance(citations, list) else []

    def get_materiality_score(self, obj):
        return self._get_meta(obj).get("materiality_score")

    def get_likelihood_score(self, obj):
        return self._get_meta(obj).get("likelihood_score")

    def get_impact_scope(self, obj):
        impact_scope = self._get_meta(obj).get("impact_scope")
        return impact_scope if isinstance(impact_scope, list) else []

    def get_why_it_matters(self, obj):
        return self._get_meta(obj).get("why_it_matters") or ""

    def get_watchpoints(self, obj):
        watchpoints = self._get_meta(obj).get("watchpoints")
        return watchpoints if isinstance(watchpoints, list) else []

    def get_requires_human_review(self, obj):
        return bool(self._get_meta(obj).get("requires_human_review", False))

    def get_review_priority(self, obj):
        return self._get_meta(obj).get("review_priority")


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
