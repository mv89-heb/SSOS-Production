from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, HTTPException

from app.extensions import db
from app.models.product import Product
from app.models.regulated_egg_price import RegulatedEggPrice
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

regulated_prices_bp = Blueprint("regulated_prices", __name__, url_prefix="/api/regulatory-prices")

SIZE_LABELS = {"M": "בינוני", "L": "גדול", "XL": "ענק"}
EXCLUDED_TERMS = ("חופש", "free range", "אורגני", "organic", "אומגה", "omega", "מועשר")


def _size_for_name(name):
    value = str(name or "").strip().lower()
    if any(term in value for term in EXCLUDED_TERMS):
        return None
    padded = f" {value} "
    if " xl " in padded or "אקסטרה לארג" in value or "ענק" in value:
        return "XL"
    if " מדיום" in value or " בינוני" in value or " m " in padded:
        return "M"
    if " גדול" in value or " large" in value or " l " in padded:
        return "L"
    return None


def _handle(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


@regulated_prices_bp.route("/eggs", methods=["GET"])
@login_required
def list_regulated_egg_prices():
    try:
        PermissionService.require_permission("reports.view")
        rows = db.session.execute(
            select(RegulatedEggPrice).order_by(RegulatedEggPrice.effective_date.desc(), RegulatedEggPrice.size_code)
        ).scalars().all()
        latest_date = max((row.effective_date for row in rows), default=None)
        current = [row.to_dict() for row in rows if row.effective_date == latest_date]
        products = db.session.execute(
            select(Product).where(Product.tenant_id == current_user.tenant_id, Product.active.is_(True))
            .order_by(Product.name.asc())
        ).scalars().all()
        matches = []
        for product in products:
            if "ביצ" not in str(product.name or "").lower() and "egg" not in str(product.name or "").lower():
                continue
            size = _size_for_name(product.name)
            matches.append({
                "product_id": product.id,
                "product_name": product.name,
                "supplier_id": product.supplier_id,
                "supplier_name": product.supplier.name if product.supplier else None,
                "size_code": size,
                "size_label": SIZE_LABELS.get(size),
                "regulated": size is not None,
                "exclusion_reason": "מוצר מוחרג מפיקוח" if size is None else None,
                "max_consumer_price": next((item["max_consumer_price"] for item in current if item["size_code"] == size), None),
                "product_current_price": float(product.current_price) if product.current_price is not None else None,
                "note": "מחיר המוצר בקטלוג הוא מחיר ספק/רכש ואינו מוחלף במחיר תקרה לצרכן.",
            })
        return jsonify({
            "success": True,
            "current_release": current,
            "history": [row.to_dict() for row in rows],
            "matched_products": matches,
            "effective_date": latest_date.isoformat() if latest_date else None,
            "source_scope": "מחיר מרבי לצרכן לאריזת 12 ביצים; אינו מחיר רכישה מספק.",
        })
    except HTTPException as exc:
        return _handle(exc)


@regulated_prices_bp.route("/eggs/releases", methods=["POST"])
@login_required
def add_regulated_egg_release():
    try:
        PermissionService.require_role_at_least("manager")
        payload = request.get_json(silent=True) or {}
        source_url = str(payload.get("source_url") or "").strip()
        host = (urlparse(source_url).hostname or "").lower()
        if host not in {"gov.il", "www.gov.il", "data.gov.il", "www.data.gov.il"}:
            raise BadRequest("יש להזין קישור למקור ממשלתי רשמי בלבד.")
        try:
            effective = date.fromisoformat(str(payload.get("effective_date") or ""))
            published = date.fromisoformat(str(payload.get("published_at") or "")) if payload.get("published_at") else None
        except ValueError:
            raise BadRequest("תאריך תחילה או פרסום אינו תקין.")
        title = str(payload.get("source_title") or "").strip()
        items = payload.get("items")
        if not title or not isinstance(items, list) or len(items) != 3:
            raise BadRequest("נדרשים כותרת מקור ושלושה מחירים: M, L, XL.")
        normalized = {}
        for item in items:
            size = str(item.get("size_code") or "").upper()
            if size not in SIZE_LABELS or size in normalized:
                raise BadRequest("יש לספק בדיוק גדלים M, L ו-XL.")
            try:
                price = Decimal(str(item.get("max_consumer_price")))
            except (InvalidOperation, TypeError):
                raise BadRequest("מחיר אינו תקין.")
            if not price.is_finite() or price <= 0 or price > 1000:
                raise BadRequest("מחיר חייב להיות חיובי ותקין.")
            normalized[size] = price.quantize(Decimal("0.01"))
        if set(normalized) != set(SIZE_LABELS):
            raise BadRequest("חסרים מחירים לאחד הגדלים.")
        existing = db.session.execute(
            select(RegulatedEggPrice.id).where(RegulatedEggPrice.effective_date == effective)
        ).first()
        if existing:
            raise Conflict("כבר קיים עדכון מחירים לתאריך התחילה הזה.")
        change = payload.get("change_percent")
        change = Decimal(str(change)) if change not in (None, "") else None
        if change is not None and (not change.is_finite() or abs(change) > 100):
            raise BadRequest("אחוז השינוי אינו תקין.")
        created = []
        for size, price in normalized.items():
            row = RegulatedEggPrice(
                size_code=size, pack_size=12, max_consumer_price=price,
                effective_date=effective, published_at=published,
                change_percent=change, source_url=source_url, source_title=title,
                created_by_tenant_id=current_user.tenant_id, created_by_user_id=current_user.id,
            )
            db.session.add(row)
            created.append(row)
        AuditService.log_event(
            current_user.tenant_id, current_user.id, "REGULATORY_EGG_PRICE_RELEASE_ADDED",
            "נוסף עדכון רשמי למחירי ביצים מפוקחים",
            {"effective_date": effective.isoformat(), "source_url": source_url, "prices": {k: str(v) for k, v in normalized.items()}},
        )
        db.session.commit()
        return jsonify({"success": True, "release": [row.to_dict() for row in created]}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except Exception:
        db.session.rollback()
        raise
