from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient


User = get_user_model()


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def csrf_headers(client):
    response = client.get(reverse("accounts:csrf"))
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def create_user(email="member@example.com", password="StrongPassword!42"):
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name="Pulse",
        last_name="Member",
    )


@pytest.mark.django_db
def test_registration_validates_password_and_establishes_http_only_session(client):
    headers = csrf_headers(client)
    response = client.post(
        reverse("accounts:register"),
        {"full_name": "Amina Wanjiku", "email": "amina@example.com", "password": "short"},
        format="json",
        **headers,
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="amina@example.com").exists()

    response = client.post(
        reverse("accounts:register"),
        {
            "full_name": "Amina Wanjiku",
            "email": "amina@example.com",
            "password": "AminaStrongPassword!42",
        },
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 201
    assert response.json()["user"]["first_name"] == "Amina"
    assert client.cookies["sessionid"]["httponly"]

    response = client.get(reverse("accounts:current_user"))
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "amina@example.com"


@pytest.mark.django_db
def test_login_logout_and_session_refresh_require_csrf(client):
    user = create_user()

    response = client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "StrongPassword!42"},
        format="json",
    )
    assert response.status_code == 403

    response = client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "incorrect"},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 401

    response = client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "StrongPassword!42"},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 200
    old_session_key = client.session.session_key

    response = client.post(
        reverse("accounts:session_refresh"),
        {},
        format="json",
    )
    assert response.status_code == 403

    response = client.post(
        reverse("accounts:session_refresh"),
        {},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 200
    assert client.session.session_key != old_session_key

    response = client.post(
        reverse("accounts:logout"),
        {},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 204
    assert client.get(reverse("accounts:current_user")).status_code == 403


@pytest.mark.django_db
def test_password_reset_is_non_enumerating_and_changes_password(client):
    user = create_user()

    response = client.post(
        reverse("accounts:password_reset_request"),
        {"email": "unknown@example.com"},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["detail"].startswith("If an account exists")
    assert len(mail.outbox) == 0

    response = client.post(
        reverse("accounts:password_reset_request"),
        {"email": user.email},
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 1

    reset_link = next(
        line.strip()
        for line in mail.outbox[0].body.splitlines()
        if line.startswith("http://")
    )
    uidb64, token = urlparse(reset_link).path.rstrip("/").split("/")[-2:]
    confirm_url = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "token": token},
    )

    response = client.post(
        confirm_url,
        {
            "new_password": "NewStrongPassword!84",
            "new_password_confirm": "NewStrongPassword!84",
        },
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewStrongPassword!84")

    response = client.post(
        confirm_url,
        {
            "new_password": "AnotherStrongPassword!84",
            "new_password_confirm": "AnotherStrongPassword!84",
        },
        format="json",
        **csrf_headers(client),
    )
    assert response.status_code == 400
    assert not user.check_password("AnotherStrongPassword!84")


@pytest.mark.django_db
def test_login_is_rate_limited(client):
    user = create_user()
    url = reverse("accounts:login")
    headers = csrf_headers(client)

    responses = [
        client.post(
            url,
            {"email": user.email, "password": "incorrect"},
            format="json",
            **headers,
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [
        401,
        401,
        401,
        401,
        401,
        429,
    ]


@pytest.mark.django_db
def test_password_reset_rejects_mismatched_passwords_and_invalid_tokens(client):
    user = create_user()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    invalid_url = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "token": "invalid-token"},
    )

    response = client.post(
        invalid_url,
        {
            "new_password": "NewStrongPassword!84",
            "new_password_confirm": "DifferentStrongPassword!84",
        },
        format="json",
        **csrf_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset link."

    invalid_uid_url = reverse(
        "accounts:password_reset_confirm",
        kwargs={
            "uidb64": urlsafe_base64_encode(b"\xff"),
            "token": "invalid-token",
        },
    )
    response = client.post(
        invalid_uid_url,
        {
            "new_password": "NewStrongPassword!84",
            "new_password_confirm": "NewStrongPassword!84",
        },
        format="json",
        **csrf_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset link."
