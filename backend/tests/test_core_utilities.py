from decimal import Decimal

import pytest

from core.audit import REDACTED_VALUE, redact_audit_metadata
from core.money import quantize_money, to_decimal


def test_money_uses_decimal_rounding():
    assert quantize_money("12.345") == Decimal("12.35")
    assert to_decimal(12) == Decimal("12")


@pytest.mark.parametrize("value", [12.5, True])
def test_money_rejects_float_and_boolean(value):
    with pytest.raises(TypeError):
        to_decimal(value)


def test_audit_metadata_redacts_sensitive_values_recursively():
    metadata = {
        "access_token": "do-not-log",
        "customer_id": "customer-1",
        "nested": [{"api_key": "do-not-log-either"}],
    }

    assert redact_audit_metadata(metadata) == {
        "access_token": REDACTED_VALUE,
        "customer_id": "customer-1",
        "nested": [{"api_key": REDACTED_VALUE}],
    }
