import json
from urllib.parse import parse_qs

import pytest
from django.core import mail
from django.test import override_settings

from apps.integrations.messaging import (
    AfricasTalkingClient,
    WhatsAppCloudClient,
    send_email,
)


class MockResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload


def test_africas_talking_sms_uses_environment_credentials(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return MockResponse(
            {
                "SMSMessageData": {
                    "Recipients": [
                        {"statusCode": 101, "messageId": "AT-message-1"}
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "apps.integrations.messaging.urllib.request.urlopen",
        urlopen,
    )
    with override_settings(
        AFRICASTALKING_USERNAME="sandbox",
        AFRICASTALKING_API_KEY="test-api-key",
        AFRICASTALKING_SENDER_ID="BIASHARA",
    ):
        message_id = AfricasTalkingClient().send_sms(
            recipient="+254712345678",
            message="Payment received.",
        )
    request, timeout = requests[0]
    assert message_id == "AT-message-1"
    assert timeout == 15
    assert request.full_url == AfricasTalkingClient.endpoint
    assert request.get_header("Apikey") == "test-api-key"
    assert parse_qs(request.data.decode())["to"] == ["+254712345678"]


def test_whatsapp_cloud_uses_bearer_token_and_graph_api(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return MockResponse({"messages": [{"id": "wamid.1"}]})

    monkeypatch.setattr(
        "apps.integrations.messaging.urllib.request.urlopen",
        urlopen,
    )
    with override_settings(
        WHATSAPP_ACCESS_TOKEN="test-access-token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        WHATSAPP_API_VERSION="v21.0",
    ):
        message_id = WhatsAppCloudClient().send_text(
            recipient="254712345678",
            message="Your receipt is ready.",
        )
    request, _ = requests[0]
    assert message_id == "wamid.1"
    assert request.full_url.endswith("/v21.0/123456789/messages")
    assert request.get_header("Authorization") == "Bearer test-access-token"
    assert json.loads(request.data)["messaging_product"] == "whatsapp"


@pytest.mark.django_db
def test_email_integration_uses_django_mail_backend():
    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="notifications@example.test",
    ):
        send_email(
            recipient="cashier@example.test",
            subject="Shift closed",
            message="Your shift has been reconciled.",
        )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].from_email == "notifications@example.test"
    assert mail.outbox[0].subject == "Shift closed"
