"""
Chat 应用 URL 路由配置。

类比 SpringBoot：
  - urlpatterns 相当于 @RequestMapping 注解的集合。
  - path("ask", ...) 类比 @PostMapping("/ask")。
  - path("sessions/...") 类比 @GetMapping("/sessions/{id}")。
  - Django URL 分发器类似于 Spring MVC 的 DispatcherServlet 路由机制。
  - 在 Django 项目中，根 URL 配置文件通过 include() 引入本模块的 urlpatterns，
    类似于 SpringBoot 中多个 @RestController 的自动注册。

路由列表：
  - /ask              -> chat_ask_view（同步问答接口）
  - /ask/stream       -> chat_ask_stream_view（流式问答接口，SSE）
  - /memories         -> ChatMemoryListView（记忆列表查询）
  - /memories/<id>    -> ChatMemoryDeleteView（删除记忆）
  - /memories/<id>/evidence -> ChatMemoryEvidenceView（查看记忆证据）
  - /memories/<id>/pin -> ChatMemoryPinView（置顶/取消置顶）
  - /sessions         -> ChatSessionCreateView（创建/列出会话）
  - /sessions/<id>    -> ChatSessionDetailView（查看/删除会话详情）
  - /sessions/<id>/export -> ChatSessionExportView（导出会话）
"""

from django.urls import path

from chat.controllers import (
    ChatMemoryDeleteView,
    ChatMemoryEvidenceView,
    ChatMemoryListView,
    ChatMemoryPinView,
    ChatSessionCreateView,
    ChatSessionDetailView,
    ChatSessionExportView,
    chat_ask_stream_view,
    chat_ask_view,
)

urlpatterns = [
    path("ask", chat_ask_view, name="chat-ask"),
    path("ask/stream", chat_ask_stream_view, name="chat-ask-stream"),
    path("memories", ChatMemoryListView.as_view(), name="chat-memory-list"),
    path("memories/<int:memory_id>", ChatMemoryDeleteView.as_view(), name="chat-memory-delete"),
    path("memories/<int:memory_id>/evidence", ChatMemoryEvidenceView.as_view(), name="chat-memory-evidence"),
    path("memories/<int:memory_id>/pin", ChatMemoryPinView.as_view(), name="chat-memory-pin"),
    path("sessions", ChatSessionCreateView.as_view(), name="chat-session-create"),
    path("sessions/<int:session_id>/export", ChatSessionExportView.as_view(), name="chat-session-export"),
    path("sessions/<int:session_id>", ChatSessionDetailView.as_view(), name="chat-session-detail"),
]
