import re
import unicodedata

from email_validator import EmailNotValidError, validate_email

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_EMAIL_IGNORABLE_CHARS = {
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
    "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
}


def normalize_email(email: str) -> str:
    """Normalize email input without performing DNS/deliverability checks."""
    if not isinstance(email, str):
        return ""
    normalized = unicodedata.normalize("NFKC", email)
    normalized = "".join(ch for ch in normalized if ch not in _EMAIL_IGNORABLE_CHARS)
    normalized = normalized.replace("\u00a0", " ").strip()
    if normalized.lower().startswith("mailto:"):
        normalized = normalized[7:].strip()
    normalized = normalized.strip("<>\"'").strip()
    return normalized.lower()


def is_valid_email(email: str) -> bool:
    """Validate normal internet email syntax; never query DNS."""
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254 or not EMAIL_RE.fullmatch(normalized):
        return False
    try:
        result = validate_email(normalized, check_deliverability=False)
    except (EmailNotValidError, TypeError, ValueError):
        return False
    return bool(result.normalized)


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
            if float(data["current_price"]) < 0:
                return "current_price must not be negative"
        except (TypeError, ValueError):
            return "current_price must be a number"

    barcode = data.get("barcode")
    if barcode is not None and barcode != "" and not str(barcode).strip().isdigit():
        return "barcode must contain digits only"

    return None


def secure_upload_extension_ok(filename: str, allowed_extensions: set) -> bool:
    if not filename or "." not in filename:
        return False
    ext = "." + filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions
