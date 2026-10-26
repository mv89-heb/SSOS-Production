"""Conservative product-image lookup through Open Food Facts.

Barcode matches are preferred. If no usable barcode exists, a name search is
accepted only when the normalized product-name token sets match exactly.
"""
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
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


def _request_json(url, timeout):
    request = Request(url, headers={"User-Agent": "SSOS-Procurement/1.0 (product image lookup)", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        return None


def _image_from_product(product):
    selected = product.get("selected_images") or {}
    front = selected.get("front") if isinstance(selected, dict) else {}
    display = front.get("display") if isinstance(front, dict) else {}
    candidate = (
        product.get("image_front_url")
        or (display.get("en") if isinstance(display, dict) else None)
        or (display.get("he") if isinstance(display, dict) else None)
    )
    return _allowed_image_url(candidate)


def _normalize_product_name(value):
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    # Keep letters and digits; normalize punctuation and whitespace.
    normalized = "".join(ch if ch.isalnum() else " " for ch in normalized)
    return tuple(sorted(normalized.split()))


def _name_lookup(product_name, timeout):
    tokens = _normalize_product_name(product_name)
    if len(tokens) < 2:
        return {"image_url": None, "reason": "product_name_too_short"}
    query = urlencode({
        "search_terms": str(product_name).strip(),
        "search_simple": "1",
        "action": "process",
        "json": "1",
        "page_size": "50",
        "fields": "code,product_name,brands,quantity,image_front_url,selected_images",
        "lc": "he",
        "cc": "il",
    })
    payload = _request_json(f"{SOURCE_BASE}/cgi/search.pl?{query}", timeout)
    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        return {"image_url": None, "reason": "source_unavailable"}
    matches = []
    for product in payload["products"]:
        if not isinstance(product, dict):
            continue
        if _normalize_product_name(product.get("product_name")) != tokens:
            continue
        code = _digits(product.get("code"))
        image_url = _image_from_product(product)
        if code and image_url:
            matches.append((code, image_url, product))
    # Multiple distinct barcode matches are ambiguous even when names look alike.
    unique = {(code, image_url) for code, image_url, _ in matches}
    if len(unique) != 1:
        return {"image_url": None, "reason": "name_match_ambiguous" if unique else "product_not_found"}
    code, image_url = next(iter(unique))
    return {
        "image_url": image_url,
        "reason": "matched_by_exact_name",
        "source": SOURCE_NAME,
        "source_url": f"{SOURCE_BASE}/product/{code}",
        "product_name": next((p.get("product_name") for c, u, p in matches if c == code and u == image_url), None),
        "match_method": "exact_normalized_name",
    }


def lookup_product_image(barcode, product_name=None, timeout=4):
    """Return a safe image candidate, preferring barcode and requiring exact fallback names."""
    normalized = _digits(barcode)
    usable_barcode = bool(normalized and not _is_synthetic_barcode(normalized))
    barcode_reason = "missing_or_synthetic_barcode"
    if usable_barcode:
        endpoint = f"{SOURCE_BASE}/api/v2/product/{quote(normalized, safe='')}.json?fields=code,product_name,brands,quantity,image_front_url,selected_images"
        payload = _request_json(endpoint, timeout)
        barcode_reason = "source_unavailable" if payload is None else "product_not_found"
        if isinstance(payload, dict) and payload.get("status") == 1 and isinstance(payload.get("product"), dict):
            product = payload["product"]
            returned_code = _digits(product.get("code"))
            if returned_code.lstrip("0") != normalized.lstrip("0"):
                return {"image_url": None, "reason": "barcode_mismatch"}
            image_url = _image_from_product(product)
            if image_url:
                return {
                    "image_url": image_url, "reason": "matched", "source": SOURCE_NAME,
                    "source_url": f"{SOURCE_BASE}/product/{normalized}",
                    "product_name": str(product.get("product_name") or "").strip() or None,
                    "match_method": "exact_barcode",
                }
            barcode_reason = "image_not_available"
    if product_name:
        return _name_lookup(product_name, timeout)
    return {"image_url": None, "reason": barcode_reason}
