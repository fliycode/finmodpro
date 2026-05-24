"""
可观测性工具 — 分布式追踪 Span 的占位实现

当前是一个轻量占位实现，所有 trace_span 调用返回无操作的 NullObservation。
未来可替换为 OpenTelemetry / Langfuse 等真实的追踪后端。

SpringBoot 类比: Micrometer Observation / @Observed 注解 + ObservationRegistry。
"""

import logging
from contextlib import contextmanager, nullcontext

logger = logging.getLogger(__name__)


class _NullObservation:
    """空追踪观察器 — 不执行任何实际追踪操作。

    update() 方法接收任意关键字参数并忽略它们。
    """
    def update(self, **kwargs):
        return None


@contextmanager
def trace_span(name, metadata=None, input_data=None, user_id=None, session_id=None):
    """创建追踪 Span 的上下文管理器。

    当前为占位实现，不产生任何追踪数据。使用 contextmanager 模式，
    在 with 块中 yield 一个 observation 对象（可通过 .update() 附加元数据）。

    使用示例:
        with trace_span("文档解析", metadata={"doc_id": "123"}) as span:
            result = parse_document()
            span.update(status="done")

    参数:
        name: Span 名称（如 "文档解析", "风险提取"）
        metadata: 附加元数据
        input_data: 输入数据
        user_id: 用户 ID
        session_id: 会话 ID
    """
    observation = _NullObservation()
    with nullcontext(observation):
        yield observation
