"""Conservative product-image lookup through Open Food Facts.

Only barcode-based matches are accepted. We never infer an image from a similar
name, and the caller should only fill products without a manually supplied image.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SOURCE_NAME = "Open Food Facts"
SOURCE_BASE = "https://world.openfoodfacts.org"


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _is_synthetic_barcode(value):
    return bool(re.fullmatch(r"990000010000\d+", str(value or "").strip()))


def _allowed_image_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    from urllib.parse import urlparse
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"images.openfoodfacts.org", "static.openfoodfacts.org"}:
        return None
    return value.strip()


def lookup_product_image(barcode, timeout=8):
    """Return a verified-by-barcode image candidate, or a reason no match exists."""
    normalized = _digits(barcode)
    if not normalized or _is_synthetic_barcode(normalized):
        return {"image_url": None, "reason": "missing_or_synthetic_barcode"}
    endpoint = f"{SOURCE_BASE}/api/v2/product/{quote(normalized, safe='')}.json?fields=code,product_name,brands,quantity,image_front_url,selected_images"
    request = Request(endpoint, headers={"User-Agent": "SSOS-Procurement/1.0 (product image lookup)", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        return {"image_url": None, "reason": "source_unavailable"}
    if payload.get("status") != 1 or not isinstance(payload.get("product"), dict):
        return {"image_url": None, "reason": "product_not_found"}
    product = payload["product"]
    returned_code = _digits(product.get("code"))
    # Ignore leading zero differences only; never accept a different barcode.
    if returned_code.lstrip("0") != normalized.lstrip("0"):
        return {"image_url": None, "reason": "barcode_mismatch"}
    selected = product.get("selected_images") or {}
    front = selected.get("front") if isinstance(selected, dict) else {}
    display = front.get("display") if isinstance(front, dict) else {}
    candidate = (
        product.get("image_front_url")
        or (display.get("en") if isinstance(display, dict) else None)
        or (display.get("he") if isinstance(display, dict) else None)
    )
    image_url = _allowed_image_url(candidate)
    if not image_url:
        return {"image_url": None, "reason": "image_not_available"}
    return {
        "image_url": image_url,
        "reason": "matched",
        "source": SOURCE_NAME,
        "source_url": f"{SOURCE_BASE}/product/{normalized}",
        "product_name": str(product.get("product_name") or "").strip() or None,
    }
