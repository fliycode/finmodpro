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
