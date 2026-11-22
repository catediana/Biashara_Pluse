import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class MpesaProviderError(Exception):
    pass


class DarajaClient:
    timeout_seconds = 10

    def __init__(self):
        self.consumer_key = getattr(settings, "MPESA_CONSUMER_KEY", "")
        self.consumer_secret = getattr(settings, "MPESA_CONSUMER_SECRET", "")
        self.shortcode = getattr(settings, "MPESA_SHORTCODE", "")
        self.passkey = getattr(settings, "MPESA_PASSKEY", "")
        self.callback_url = getattr(settings, "MPESA_CALLBACK_URL", "")
        self.transaction_type = getattr(
            settings,
            "MPESA_TRANSACTION_TYPE",
            "CustomerPayBillOnline",
        )
        self.environment = getattr(settings, "MPESA_ENV", "sandbox")
        if self.environment == "sandbox":
            self.base_url = "https://sandbox.safaricom.co.ke"
        elif self.environment == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            raise ImproperlyConfigured("MPESA_ENV must be sandbox or production.")
        if not all(
            (
                self.consumer_key,
                self.consumer_secret,
                self.shortcode,
                self.passkey,
                self.callback_url,
            )
        ):
            raise ImproperlyConfigured(
                "Daraja credentials, shortcode, passkey, and callback URL are required."
            )
        if self.transaction_type not in (
            "CustomerPayBillOnline",
            "CustomerBuyGoodsOnline",
        ):
            raise ImproperlyConfigured(
                "MPESA_TRANSACTION_TYPE must be a supported STK transaction type."
            )
        parsed_callback = urllib.parse.urlsplit(self.callback_url)
        if parsed_callback.scheme not in ("http", "https") or not parsed_callback.netloc:
            raise ImproperlyConfigured("MPESA_CALLBACK_URL must be an absolute URL.")
        if self.environment == "production" and parsed_callback.scheme != "https":
            raise ImproperlyConfigured(
                "MPESA_CALLBACK_URL must use HTTPS in production."
            )

    def _request(self, path, *, payload=None, access_token=False):
        headers = {"Accept": "application/json"}
        body = None
        if access_token:
            credentials = f"{self.consumer_key}:{self.consumer_secret}".encode()
            headers["Authorization"] = (
                "Basic " + base64.b64encode(credentials).decode("ascii")
            )
            url = (
                f"{self.base_url}/oauth/v1/generate"
                "?grant_type=client_credentials"
            )
        else:
            headers["Authorization"] = f"Bearer {self._access_token()}"
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
            url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                result = json.loads(response.read())
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise MpesaProviderError(
                "Daraja payment request failed; the payment remains pending."
            ) from exc
        if not isinstance(result, dict):
            raise MpesaProviderError("Daraja returned an invalid response.")
        return result

    def _access_token(self):
        result = self._request("", access_token=True)
        token = result.get("access_token")
        if not token:
            raise MpesaProviderError("Daraja did not return an access token.")
        return token

    def initiate_stk_push(self, *, amount, phone_number, account_reference, description):
        if amount <= 0 or amount != amount.to_integral_value():
            raise ValueError("Daraja STK Push amounts must be whole currency units.")
        timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        ).decode("ascii")
        result = self._request(
            "/mpesa/stkpush/v1/processrequest",
            payload={
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": self.transaction_type,
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference[:12],
                "TransactionDesc": description[:13],
            },
        )
        if result.get("ResponseCode") != "0":
            raise MpesaProviderError("Daraja rejected the STK Push request.")
        checkout_request_id = result.get("CheckoutRequestID")
        merchant_request_id = result.get("MerchantRequestID")
        if not checkout_request_id or not merchant_request_id:
            raise MpesaProviderError("Daraja returned incomplete STK request details.")
        return {
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
        }

    def query_stk_push(self, *, checkout_request_id):
        timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        ).decode("ascii")
        return self._request(
            "/mpesa/stkpushquery/v1/query",
            payload={
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id,
            },
        )


def normalize_kenyan_phone(value):
    normalized = re.sub(r"[\s()-]", "", value)
    if normalized.startswith("+"):
        normalized = normalized[1:]
    if not normalized.isdigit():
        raise ValueError("Enter a valid Kenyan mobile number.")
    digits = normalized
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") and len(digits) == 9:
        digits = "254" + digits
    elif digits.startswith("1") and len(digits) == 9:
        digits = "254" + digits
    if (
        len(digits) != 12
        or not digits.startswith("254")
        or digits[3] not in "17"
    ):
        raise ValueError("Enter a valid Kenyan mobile number.")
    return digits
