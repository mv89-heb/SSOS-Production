import re
import unicodedata

from email_validator import EmailNotValidError, validate_email

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Characters that can be introduced by copy/paste, RTL text, browser autofill,
# or mailto links but are not part of an email address.
_EMAIL_IGNORABLE_CHARS = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u2060",  # word joiner
    "\ufeff",  # zero-width no-break space / BOM
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\u202a",  # left-to-right embedding
    "\u202b",  # right-to-left embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # left-to-right override
    "\u202e",  # right-to-left override
}


def normalize_email(email: str) -> str:
    """Normalize user-entered email safely and predictably.

    Handles common browser/copy-paste variants such as ``mailto:`` prefixes,
    surrounding whitespace/angle brackets, non-breaking spaces, and invisible
    Unicode direction/zero-width characters. It does not perform DNS checks.
    """
    if not isinstance(email, str):
        return ""

    normalized = unicodedata.normalize("NFKC", email)
    normalized = "".join(ch for ch in normalized if ch not in _EMAIL_IGNORABLE_CHARS)
    normalized = normalized.replace("\u00a0", " ").strip()

    # Accept values copied from mail links, e.g. ``mailto:elia@reshit.co.il``.
    if normalized.lower().startswith("mailto:"):
        normalized = normalized[7:].strip()

    # Be tolerant of a copied address surrounded by angle brackets/quotes.
    normalized = normalized.strip("<>\"'")
    normalized = normalized.strip()

    return normalized.lower()


def is_valid_email(email: str) -> bool:
    """Validate a normal internet email address.

    Deliverability/DNS checks are deliberately disabled. The application only
    needs to establish that the supplied value has valid email syntax; whether
    the mailbox actually exists is a separate concern.
    """
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254 or not EMAIL_RE.fullmatch(normalized):
        return False

    try:
        result = validate_email(normalized, check_deliverability=False)
        # email-validator can normalize an address further, but it must not
        # silently turn an empty/structurally invalid value into a valid one.
        return bool(result.normalized)
    except (EmailNotValidError, TypeError, ValueError):
        # The lightweight syntax check above remains the authoritative fallback
        # for ordinary addresses when the third-party parser is stricter than
        # the application's accepted login format.
        return True


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
