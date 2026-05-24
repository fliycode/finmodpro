"""
Chat 控制器层（Controller Layer）包初始化。

类比 SpringBoot：
  - controllers/ 目录相当于 SpringBoot 中的 controller 包，存放 @RestController 类。
  - 本文件将子模块中的所有控制器视图统一导出，便于其他模块（如 urls.py）集中引用。
  - __all__ 列表定义了此包的公开 API 接口，相当于 Java 中的 public 导出。

导出的控制器：
  - chat_ask_view / chat_ask_stream_view：问答接口（函数视图）。
  - ChatMemoryListView / ChatMemoryEvidenceView / ChatMemoryPinView / ChatMemoryDeleteView：记忆管理接口（类视图）。
  - ChatSessionCreateView / ChatSessionDetailView / ChatSessionExportView：会话管理接口（类视图）。
"""

from chat.controllers.ask_controller import chat_ask_stream_view, chat_ask_view
from chat.controllers.memory_controller import (
    ChatMemoryDeleteView,
    ChatMemoryEvidenceView,
    ChatMemoryListView,
    ChatMemoryPinView,
)
from chat.controllers.session_controller import (
    ChatSessionCreateView,
    ChatSessionDetailView,
    ChatSessionExportView,
)

__all__ = [
    "chat_ask_view",
    "chat_ask_stream_view",
    "ChatMemoryDeleteView",
    "ChatMemoryEvidenceView",
    "ChatMemoryListView",
    "ChatMemoryPinView",
    "ChatSessionCreateView",
    "ChatSessionDetailView",
    "ChatSessionExportView",
]
