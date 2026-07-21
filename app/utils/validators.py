import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_RE.match(email.strip()))


def is_strong_password(password: str) -> bool:
    """Minimum viable password policy: 8+ chars, at least one letter and one digit."""
    if not password or len(password) < 8:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit


def validate_product_payload(data: dict) -> str | None:
    """Returns an error message if the product payload is invalid, else None.
    Only validates fields that are present — this is shared by create (where
    some fields are required elsewhere) and update (where every field is
    optional), so it must not require anything itself."""
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
