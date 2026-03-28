from django.urls import path

from authentication.controllers.auth_controller import login_view, register_view


urlpatterns = [
    path("register", register_view, name="register"),
    path("login", login_view, name="login"),
]
