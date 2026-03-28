from django.urls import path

from chat.controllers import chat_ask_view

urlpatterns = [
    path("ask", chat_ask_view, name="chat-ask"),
]
