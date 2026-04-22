from django.urls import path

from authentication.controllers.auth_controller import (
    csrf_view,
    login_view,
    logout_view,
    refresh_view,
    register_view,
)


urlpatterns = [
    path("csrf", csrf_view, name="csrf"),
    path("register", register_view, name="register"),
    path("login", login_view, name="login"),
    path("refresh", refresh_view, name="refresh"),
    path("logout", logout_view, name="logout"),
]
