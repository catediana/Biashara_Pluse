from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("csrf/", views.csrf_token, name="csrf"),
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path(
        "password-reset/request/",
        views.password_reset_request,
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/<str:uidb64>/<str:token>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path("me/", views.current_user, name="current_user"),
    path("session/refresh/", views.session_refresh, name="session_refresh"),
]
