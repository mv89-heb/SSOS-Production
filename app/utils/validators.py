import math
import re
import unicodedata


# Syntax-only validation for login email addresses.
#
# We deliberately do not perform DNS/deliverability checks and do not depend
# on the version-specific policy of email-validator. A valid application login
# address such as elia@reshit.co.il must behave identically in local, CI and
# Render environments.
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

_EMAIL_IGNORABLE_CHARS = {
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
    "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
}


def normalize_email(email: str) -> str:
    """Normalize a user-entered login email without network checks."""
    if not isinstance(email, str):
        return ""

    normalized = unicodedata.normalize("NFKC", email)
    normalized = "".join(ch for ch in normalized if ch not in _EMAIL_IGNORABLE_CHARS)
    normalized = normalized.replace("\u00a0", " ").strip()

    if normalized.lower().startswith("mailto:"):
        normalized = normalized[7:].strip()

    return normalized.strip("<>\"'").strip().lower()


def is_valid_email(email: str) -> bool:
    """Return True when *email* has a safe, conventional login syntax."""
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254:
        return False
    return EMAIL_RE.fullmatch(normalized) is not None


def is_strong_password(password: str) -> bool:
    """Minimum password policy: 8+ chars, one letter and one digit."""
    if not isinstance(password, str) or len(password) < 8:
        return False
    return any(c.isalpha() for c in password) and any(c.isdigit() for c in password)


def validate_product_payload(data: dict) -> str | None:
    """Return an error message for invalid product fields, otherwise None."""
    for field in ("units_per_carton", "current_stock", "min_stock", "recommended_stock"):
        if field in data and data[field] is not None:
            value = data[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return f"{field} must be a non-negative integer"

    if "current_price" in data and data["current_price"] is not None:
        try:
            price = float(data["current_price"])
        except (TypeError, ValueError):
            return "current_price must be a number"
        if not math.isfinite(price):
            return "current_price must be a finite number"
        if price < 0:
            return "current_price must not be negative"

    barcode = data.get("barcode")
    if barcode is not None and barcode != "" and not str(barcode).strip().isdigit():
        return "barcode must contain digits only"

    return None


def secure_upload_extension_ok(filename: str, allowed_extensions: set) -> bool:
    if not filename or "." not in filename:
        return False
    ext = "." + filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions
