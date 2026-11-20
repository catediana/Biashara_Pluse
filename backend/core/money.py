from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")


def to_decimal(value):
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Money values must not be booleans or floats.")
    if not isinstance(value, (Decimal, int, str)):
        raise TypeError("Money values must be Decimal, int, or string.")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Money value is not a valid decimal.") from exc
    if not amount.is_finite():
        raise ValueError("Money value must be finite.")
    return amount


def quantize_money(value):
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
