import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import BadHeaderError, send_mail


class ProviderDeliveryError(Exception):
    def __init__(self, message, *, retryable):
        super().__init__(message)
        self.retryable = retryable


def _http_error(error):
    retryable = error.code == 429 or error.code >= 500
    raise ProviderDeliveryError(
        f"Messaging provider returned HTTP {error.code}.",
        retryable=retryable,
    ) from error


def _request_json(request):
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _http_error(exc)
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise ProviderDeliveryError(
            "Messaging provider request failed.",
            retryable=True,
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderDeliveryError(
            "Messaging provider returned an invalid response.",
            retryable=True,
        )
    return payload


class AfricasTalkingClient:
    endpoint = "https://api.africastalking.com/version1/messaging"

    def __init__(self):
        self.username = getattr(settings, "AFRICASTALKING_USERNAME", "")
        self.api_key = getattr(settings, "AFRICASTALKING_API_KEY", "")
        self.sender_id = getattr(settings, "AFRICASTALKING_SENDER_ID", "")
        if not self.username or not self.api_key:
            raise ImproperlyConfigured(
                "Africa's Talking username and API key must be configured."
            )

    def send_sms(self, *, recipient, message):
        payload = {
            "username": self.username,
            "to": recipient,
            "message": message,
        }
        if self.sender_id:
            payload["from"] = self.sender_id
        request = urllib.request.Request(
            self.endpoint,
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "apiKey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        result = _request_json(request)
        message_data = result.get("SMSMessageData")
        recipients = (
            message_data.get("Recipients", [])
            if isinstance(message_data, dict)
            else []
        )
        if not isinstance(recipients, list) or not recipients:
            raise ProviderDeliveryError(
                "Africa's Talking did not confirm SMS delivery.",
                retryable=True,
            )
        recipient_result = recipients[0]
        if not isinstance(recipient_result, dict):
            raise ProviderDeliveryError(
                "Africa's Talking returned an invalid SMS result.",
                retryable=True,
            )
        if recipient_result.get("statusCode") != 101:
            raise ProviderDeliveryError(
                "Africa's Talking rejected the SMS.",
                retryable=False,
            )
        return recipient_result.get("messageId", "")


class WhatsAppCloudClient:
    def __init__(self):
        self.access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        self.api_version = getattr(settings, "WHATSAPP_API_VERSION", "")
        if not self.access_token or not self.phone_number_id or not self.api_version:
            raise ImproperlyConfigured(
                "WhatsApp access token, phone number ID, and API version must be configured."
            )

    def send_text(self, *, recipient, message):
        endpoint = (
            f"https://graph.facebook.com/{self.api_version}/"
            f"{self.phone_number_id}/messages"
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": message},
                }
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )
        result = _request_json(request)
        messages = result.get("messages", [])
        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
            or not messages[0].get("id")
        ):
            raise ProviderDeliveryError(
                "WhatsApp did not confirm message acceptance.",
                retryable=True,
            )
        return messages[0]["id"]


def send_email(*, recipient, subject, message):
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except BadHeaderError as exc:
        raise ProviderDeliveryError(
            "Email contains an invalid header.",
            retryable=False,
        ) from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise ProviderDeliveryError("Email delivery failed.", retryable=True) from exc
    if sent != 1:
        raise ProviderDeliveryError(
            "Email backend did not confirm delivery.",
            retryable=True,
        )
    return ""


def send_via_channel(*, channel, recipient, subject, message):
    if channel == "email":
        return send_email(
            recipient=recipient,
            subject=subject,
            message=message,
        )
    if channel == "sms":
        return AfricasTalkingClient().send_sms(
            recipient=recipient,
            message=message,
        )
    if channel == "whatsapp":
        return WhatsAppCloudClient().send_text(
            recipient=recipient,
            message=message,
        )
    raise ValueError(f"Unsupported messaging channel: {channel}")
