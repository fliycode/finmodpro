import json
import logging


_STRUCTURED_LOG_KEYS = (
    "document_id",
    "dataset_id",
    "task_id",
    "step",
    "status",
    "duration_ms",
    "quality_score",
    "quality_gate_status",
    "error_code",
    "file_name",
    "span_name",
)


class StructuredKeyValueFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in _STRUCTURED_LOG_KEYS:
            value = getattr(record, key, None)
            if value in (None, ""):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def build_log_extra(
    *,
    document_id=None,
    dataset_id=None,
    task_id=None,
    step="",
    status="",
    duration_ms=None,
    quality_score=None,
    quality_gate_status="",
    error_code="",
    file_name="",
):
    return {
        "document_id": document_id,
        "dataset_id": dataset_id,
        "task_id": task_id,
        "step": step,
        "status": status,
        "duration_ms": duration_ms,
        "quality_score": quality_score,
        "quality_gate_status": quality_gate_status,
        "error_code": error_code,
        "file_name": file_name,
    }
