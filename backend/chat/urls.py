from django.urls import path

from chat.controllers import (
    ChatSessionCreateView,
    ChatSessionDetailView,
    ChatSessionExportView,
    chat_ask_stream_view,
    chat_ask_view,
)

urlpatterns = [
    path("ask", chat_ask_view, name="chat-ask"),
    path("ask/stream", chat_ask_stream_view, name="chat-ask-stream"),
    path("sessions", ChatSessionCreateView.as_view(), name="chat-session-create"),
    path("sessions/<int:session_id>/export", ChatSessionExportView.as_view(), name="chat-session-export"),
    path("sessions/<int:session_id>", ChatSessionDetailView.as_view(), name="chat-session-detail"),
]
