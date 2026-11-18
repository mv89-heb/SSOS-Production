"""VAT normalization for supplier prices stored on a net (before-VAT) basis."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

DEFAULT_VAT_RATE = Decimal("0.18")


def normalize_price_before_vat(value, price_type: str | None = None, vat_rate=DEFAULT_VAT_RATE) -> Decimal:
    """Return a two-decimal net price; gross values are divided by 1 + VAT rate."""
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        rate = vat_rate if isinstance(vat_rate, Decimal) else Decimal(str(vat_rate))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid price or VAT rate")
    if not amount.is_finite() or amount < 0 or not rate.is_finite() or rate < 0:
        raise ValueError("Price and VAT rate must be finite and non-negative")
    if str(price_type or "").strip().lower() == "after_vat":
        amount = amount / (Decimal("1") + rate)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
