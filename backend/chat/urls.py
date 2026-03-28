from django.urls import path

from chat.controllers import ChatSessionCreateView, chat_ask_view

urlpatterns = [
    path("ask", chat_ask_view, name="chat-ask"),
    path("sessions", ChatSessionCreateView.as_view(), name="chat-session-create"),
]
