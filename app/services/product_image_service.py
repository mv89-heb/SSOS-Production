"""Conservative product-image lookup with a free fallback source.

Open Food Facts is preferred. UPCitemdb is a rate-limited fallback. Matches
must be exact by barcode or normalized product title; existing images are
handled by the calling route and are never overwritten.
"""
import json
import logging
import re
import threading
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

SOURCE_NAME = "Open Food Facts"
SOURCE_BASE = "https://world.openfoodfacts.org"
FALLBACK_SOURCE_NAME = "UPCitemdb"
FALLBACK_SOURCE_BASE = "https://api.upcitemdb.com/prod/trial"
# The free UPCitemdb plan permits only two searches per 30 seconds and 20/day.
# Enforce a conservative per-process interval and honor provider response headers
# by treating HTTP errors (including 429) as unavailable, never as no-match.
_UPC_SEARCH_LOCK = threading.Lock()
_UPC_LAST_SEARCH_AT = 0.0
_UPC_SEARCH_INTERVAL_SECONDS = 16.0


def _digits(value):
    return re.sub(r"\\D", "", str(value or ""))


def _is_synthetic_barcode(value):
    return bool(re.fullmatch(r"990000010000\\d+", str(value or "").strip()))


def _allowed_image_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return value.strip()


def _request_json(url, timeout):
    request = Request(url, headers={"User-Agent": "SSOS-Procurement/1.0 (product image lookup)", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Log only the status and host, never product names or barcodes.
        logger.warning("Product image source returned HTTP %s from %s", exc.code, urlparse(url).hostname)
        return None
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        logger.warning("Product image source connection failed at %s (%s)", urlparse(url).hostname, type(reason).__name__ if reason is not None else "URLError")
        return None
    except (TimeoutError, OSError) as exc:
        logger.warning("Product image source request failed at %s (%s)", urlparse(url).hostname, type(exc).__name__)
        return None
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Product image source returned invalid JSON (%s)", type(exc).__name__)
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
    normalized = "".join(ch if ch.isalnum() else " " for ch in normalized)
    return tuple(sorted(normalized.split()))


def _upcitemdb_request(endpoint, params, timeout, is_search=False):
    global _UPC_LAST_SEARCH_AT
    if is_search:
        # UPCitemdb's free search tier is substantially slower than a normal
        # batch API. Defer rather than trigger a rate-limit lockout.
        with _UPC_SEARCH_LOCK:
            elapsed = time.monotonic() - _UPC_LAST_SEARCH_AT
            if elapsed < _UPC_SEARCH_INTERVAL_SECONDS:
                return None
            _UPC_LAST_SEARCH_AT = time.monotonic()
    url = f"{FALLBACK_SOURCE_BASE}/{endpoint}?{urlencode(params)}"
    return _request_json(url, timeout)


def _upcitemdb_lookup(barcode, product_name, timeout):
    normalized = _digits(barcode)
    if normalized and not _is_synthetic_barcode(normalized):
        payload = _upcitemdb_request("lookup", {"upc": normalized}, timeout)
        if payload is None:
            return {"image_url": None, "reason": "source_unavailable"}
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                returned_codes = {_digits(item.get(key)) for key in ("ean", "upc", "gtin")}
                returned_codes.discard("")
                if not any(code.lstrip("0") == normalized.lstrip("0") for code in returned_codes):
                    continue
                image_url = next((_allowed_image_url(url) for url in (item.get("images") if isinstance(item.get("images"), list) else []) if _allowed_image_url(url)), None)
                if image_url:
                    return {
                        "image_url": image_url, "reason": "matched",
                        "source": FALLBACK_SOURCE_NAME,
                        "source_url": f"https://www.upcitemdb.com/",
                        "product_name": str(item.get("title") or "").strip() or None,
                        "match_method": "exact_barcode",
                    }
    # A barcode lookup is a distinct operation. Let the caller decide whether
    # to run one separate name search, so a failed lookup never consumes two
    # search requests in the same batch item.
    if normalized and not _is_synthetic_barcode(normalized):
        return {"image_url": None, "reason": "product_not_found"}
    if not product_name or len(_normalize_product_name(product_name)) < 2:
        return {"image_url": None, "reason": "product_not_found"}
    payload = _upcitemdb_request(
        "search", {"s": str(product_name).strip(), "match_mode": "1", "type": "product"}, timeout, is_search=True
    )
    if payload is None:
        return {"image_url": None, "reason": "source_unavailable"}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {"image_url": None, "reason": "source_unavailable"}
    tokens = _normalize_product_name(product_name)
    matches = []
    for item in items:
        if not isinstance(item, dict) or _normalize_product_name(item.get("title")) != tokens:
            continue
        image_url = next((_allowed_image_url(url) for url in item.get("images", []) if _allowed_image_url(url)), None)
        if image_url:
            matches.append((image_url, item))
    unique = {(url, str(item.get("ean") or item.get("upc") or item.get("title") or "")) for url, item in matches}
    if len(unique) != 1:
        return {"image_url": None, "reason": "name_match_ambiguous" if unique else "product_not_found"}
    image_url, item = matches[0]
    return {
        "image_url": image_url, "reason": "matched_by_exact_name",
        "source": FALLBACK_SOURCE_NAME, "source_url": "https://www.upcitemdb.com/",
        "product_name": str(item.get("title") or "").strip() or None,
        "match_method": "exact_normalized_name",
    }


def _name_lookup(product_name, timeout):
    tokens = _normalize_product_name(product_name)
    if len(tokens) < 2:
        return {"image_url": None, "reason": "product_name_too_short"}
    query = urlencode({
        "search_terms": str(product_name).strip(), "search_simple": "1",
        "action": "process", "json": "1", "page_size": "50",
        "fields": "code,product_name,brands,quantity,image_front_url,selected_images",
        "lc": "he", "cc": "il",
    })
    payload = _request_json(f"{SOURCE_BASE}/cgi/search.pl?{query}", timeout)
    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        return {"image_url": None, "reason": "source_unavailable"}
    matches = []
    for product in payload["products"]:
        if not isinstance(product, dict) or _normalize_product_name(product.get("product_name")) != tokens:
            continue
        code = _digits(product.get("code"))
        image_url = _image_from_product(product)
        if code and image_url:
            matches.append((code, image_url, product))
    unique = {(code, image_url) for code, image_url, _ in matches}
    if len(unique) != 1:
        return {"image_url": None, "reason": "name_match_ambiguous" if unique else "product_not_found"}
    code, image_url = next(iter(unique))
    product = next(p for c, u, p in matches if c == code and u == image_url)
    return {
        "image_url": image_url, "reason": "matched_by_exact_name",
        "source": SOURCE_NAME, "source_url": f"{SOURCE_BASE}/product/{code}",
        "product_name": product.get("product_name"), "match_method": "exact_normalized_name",
    }


def lookup_product_image(barcode, product_name=None, timeout=4):
    """Return an exact-match image candidate, trying UPCitemdb if OFF is unavailable or has no image."""
    normalized = _digits(barcode)
    usable_barcode = bool(normalized and not _is_synthetic_barcode(normalized))
    primary_reason = "missing_or_synthetic_barcode"
    off_unavailable = False
    if usable_barcode:
        endpoint = f"{SOURCE_BASE}/api/v2/product/{quote(normalized, safe='')}.json?fields=code,product_name,brands,quantity,image_front_url,selected_images"
        payload = _request_json(endpoint, timeout)
        off_unavailable = payload is None
        primary_reason = "source_unavailable" if off_unavailable else "product_not_found"
        if payload is not None and isinstance(payload, dict) and payload.get("status") == 1 and isinstance(payload.get("product"), dict):
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
            primary_reason = "image_not_available"
        # Try the fallback after an OFF miss/outage. Do not query OFF a second
        # time after a failed barcode request to the same unavailable host.
        fallback = _upcitemdb_lookup(normalized, product_name, timeout)
        if fallback.get("image_url") or fallback.get("reason") == "source_unavailable":
            return fallback
        if fallback.get("reason") not in {"product_not_found", "image_not_available"}:
            return fallback
        if off_unavailable:
            if product_name and fallback.get("reason") == "product_not_found":
                return _upcitemdb_lookup(None, product_name, timeout)
            return fallback
    if product_name:
        primary = _name_lookup(product_name, timeout)
        if primary.get("image_url"):
            return primary
        fallback = _upcitemdb_lookup(None, product_name, timeout)
        if fallback.get("image_url") or fallback.get("reason") == "source_unavailable":
            return fallback
        if primary.get("reason") == "source_unavailable" and fallback.get("reason") == "product_not_found":
            return {"image_url": None, "reason": "source_unavailable"}
        return primary
    return {"image_url": None, "reason": primary_reason}
