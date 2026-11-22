import re
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.integrations.mpesa import DarajaClient, normalize_kenyan_phone


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0712 345 678", "254712345678"),
        ("+254 (712) 345-678", "254712345678"),
        ("0112345678", "254112345678"),
    ],
)
def test_normalize_kenyan_mpesa_phone(value, expected):
    assert normalize_kenyan_phone(value) == expected


def test_daraja_stk_request_contains_expected_payment_details(monkeypatch):
    with override_settings(
        MPESA_ENV="sandbox",
        MPESA_CONSUMER_KEY="sandbox-key",
        MPESA_CONSUMER_SECRET="sandbox-secret",
        MPESA_SHORTCODE="174379",
        MPESA_PASSKEY="sandbox-passkey",
        MPESA_CALLBACK_URL="https://example.test/api/retail/mpesa/callback/",
        MPESA_TRANSACTION_TYPE="CustomerPayBillOnline",
    ):
        client = DarajaClient()
        captured = {}

        def fake_request(path, *, payload=None, access_token=False):
            captured["path"] = path
            captured["payload"] = payload
            captured["access_token"] = access_token
            return {
                "ResponseCode": "0",
                "CheckoutRequestID": "ws_CO_test_001",
                "MerchantRequestID": "merchant_test_001",
            }

        monkeypatch.setattr(client, "_request", fake_request)
        result = client.initiate_stk_push(
            amount=Decimal("10.00"),
            phone_number="254712345678",
            account_reference="BP-123456789012345",
            description="Retail sale payment",
        )

    assert captured["path"] == "/mpesa/stkpush/v1/processrequest"
    assert captured["access_token"] is False
    assert captured["payload"]["Amount"] == 10
    assert captured["payload"]["PhoneNumber"] == "254712345678"
    assert captured["payload"]["PartyA"] == "254712345678"
    assert captured["payload"]["TransactionType"] == "CustomerPayBillOnline"
    assert captured["payload"]["CallBackURL"].endswith("/api/retail/mpesa/callback/")
    assert re.fullmatch(r"\d{14}", captured["payload"]["Timestamp"])
    assert result == {
        "checkout_request_id": "ws_CO_test_001",
        "merchant_request_id": "merchant_test_001",
    }


def test_normalize_kenyan_phone_rejects_non_mobile_or_invalid_input():
    with pytest.raises(ValueError):
        normalize_kenyan_phone("0712AB5678")
