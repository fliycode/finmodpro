"""
结构化日志格式器

使用 JSON 格式输出日志，便于日志采集系统（如 ELK、Loki）解析和检索。
所有日志行都是单行 JSON，包含 timestamp、level、logger、message 及可选的结构化字段。

SpringBoot 类比: logback-spring.xml 中的 JSON encoder / LogstashEncoder。
"""

import json
import logging


# 支持的结构化日志字段（仅对知识库、风险等业务日志有效）
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
    """JSON 结构化日志格式器。

    将日志记录格式化为单行 JSON，自动附加 _STRUCTURED_LOG_KEYS 中的扩展字段。
    """

    def format(self, record):
        """将日志记录格式化为 JSON 字符串。

        参数:
            record: Python logging.LogRecord 对象
        返回:
            JSON 字符串
        """
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 附加业务相关的扩展字段（如 document_id, task_id 等）
        for key in _STRUCTURED_LOG_KEYS:
            value = getattr(record, key, None)
            if value in (None, ""):
                continue
            payload[key] = value

        # 如有异常堆栈，附加到 JSON 中
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
    """构建日志扩展字段字典，供 logger.info(..., extra=...) 使用。

    示例:
        logger.info("保存完成", extra=build_log_extra(document_id="123", step="save"))

    参数:
        各字段均为可选的业务元数据，仅非空值会被记录到结构化日志中。
    """
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
