from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.middleware.csrf import get_token
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
)


User = get_user_model()
INVALID_CREDENTIALS = {"detail": "Invalid email or password."}
PASSWORD_RESET_ACCEPTED = {
    "detail": (
        "If an account exists for that email address, "
        "password reset instructions have been sent."
    )
}


def throttle_scope(scope):
    def decorate(view):
        view.cls.throttle_scope = scope
        return view

    return decorate


def serialize_user(user):
    return {
        "id": str(user.pk),
        "email": getattr(user, User.get_email_field_name(), ""),
        "first_name": getattr(user, "first_name", ""),
        "last_name": getattr(user, "last_name", ""),
    }


def get_reset_user(uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User._default_manager.get(pk=uid)
    except (
        TypeError,
        ValueError,
        OverflowError,
        UnicodeDecodeError,
        DjangoValidationError,
        User.DoesNotExist,
    ):
        raise Http404 from None
    if not default_token_generator.check_token(user, token):
        raise Http404
    return user


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token(request):
    return Response({"csrf_token": get_token(request)})


@throttle_scope("auth_register")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@csrf_protect
def register(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    auth_login(
        request,
        user,
        backend=settings.AUTHENTICATION_BACKENDS[0],
    )
    return Response(
        {"user": serialize_user(user), "csrf_token": get_token(request)},
        status=status.HTTP_201_CREATED,
    )


@throttle_scope("auth_login")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@csrf_protect
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        **{
            User.USERNAME_FIELD: serializer.validated_data["email"],
            "password": serializer.validated_data["password"],
        },
    )
    if user is None:
        return Response(
            INVALID_CREDENTIALS,
            status=status.HTTP_401_UNAUTHORIZED,
        )
    auth_login(request, user)
    return Response(
        {"user": serialize_user(user), "csrf_token": get_token(request)}
    )


@throttle_scope("auth_logout")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@csrf_protect
def logout(request):
    auth_logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@throttle_scope("auth_password_reset")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@csrf_protect
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    form = PasswordResetForm(data=serializer.validated_data)
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            subject_template_name="accounts/password_reset_subject.txt",
            email_template_name="accounts/password_reset_email.txt",
            extra_email_context={
                "password_reset_url": settings.PASSWORD_RESET_URL.rstrip("/")
            },
        )
    return Response(PASSWORD_RESET_ACCEPTED)


@throttle_scope("auth_password_reset_confirm")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@csrf_protect
def password_reset_confirm(request, uidb64, token):
    try:
        user = get_reset_user(uidb64, token)
    except Http404:
        return Response(
            {"detail": "Invalid or expired reset link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PasswordResetConfirmSerializer(
        data=request.data,
        context={"user": user},
    )
    serializer.is_valid(raise_exception=True)
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response({"detail": "Password has been reset."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user(request):
    return Response({"user": serialize_user(request.user)})


@throttle_scope("auth_session_refresh")
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def session_refresh(request):
    request.session.cycle_key()
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    return Response(
        {"user": serialize_user(request.user), "csrf_token": get_token(request)}
    )
