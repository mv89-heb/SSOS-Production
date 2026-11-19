from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.models.order import VALID_STATUSES
from app.models.saved_order_search import SavedOrderSearch
from app.models.supplier import Supplier


MAX_SAVED_SEARCHES_PER_USER = 20
MAX_NAME_LENGTH = 80
MAX_QUERY_LENGTH = 200
MAX_DATE_RANGE_DAYS = 731
ALLOWED_FILTERS = {"q", "status", "supplier_id", "start_date", "end_date"}


class SavedOrderSearchService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def list(self):
        return db.session.execute(
            select(SavedOrderSearch)
            .where(
                SavedOrderSearch.tenant_id == self.tenant_id,
                SavedOrderSearch.user_id == self.user_id,
            )
            .order_by(SavedOrderSearch.updated_at.desc(), SavedOrderSearch.id.desc())
        ).scalars().all()

    def create(self, name, filters):
        normalized_name = self._validate_name(name)
        normalized_filters = self._validate_filters(filters)

        count = db.session.scalar(
            select(func.count()).select_from(SavedOrderSearch).where(
                SavedOrderSearch.tenant_id == self.tenant_id,
                SavedOrderSearch.user_id == self.user_id,
            )
        ) or 0
        if count >= MAX_SAVED_SEARCHES_PER_USER:
            raise Conflict(f"You can save up to {MAX_SAVED_SEARCHES_PER_USER} searches")

        duplicate = db.session.scalar(
            select(SavedOrderSearch.id).where(
                SavedOrderSearch.tenant_id == self.tenant_id,
                SavedOrderSearch.user_id == self.user_id,
                func.lower(SavedOrderSearch.name) == normalized_name.lower(),
            )
        )
        if duplicate is not None:
            raise Conflict("A saved search with this name already exists")

        saved = SavedOrderSearch(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            name=normalized_name,
            filters=normalized_filters,
        )
        db.session.add(saved)
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise Conflict("A saved search with this name already exists") from exc
        return saved

    def delete(self, saved_search_id: int):
        saved = db.session.scalar(
            select(SavedOrderSearch).where(
                SavedOrderSearch.id == saved_search_id,
                SavedOrderSearch.tenant_id == self.tenant_id,
                SavedOrderSearch.user_id == self.user_id,
            )
        )
        if saved is None:
            raise NotFound("Saved search not found")
        db.session.delete(saved)
        db.session.commit()
        return saved_search_id

    @staticmethod
    def _validate_name(value):
        if not isinstance(value, str):
            raise BadRequest("name must be text")
        name = value.strip()
        if not name:
            raise BadRequest("name is required")
        if len(name) > MAX_NAME_LENGTH:
            raise BadRequest(f"name cannot exceed {MAX_NAME_LENGTH} characters")
        return name

    def _validate_filters(self, value):
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise BadRequest("filters must be an object")
        unknown = set(value) - ALLOWED_FILTERS
        if unknown:
            raise BadRequest("Unsupported saved-search filter")

        query = value.get("q", "")
        if not isinstance(query, str):
            raise BadRequest("q must be text")
        query = query.strip()
        if len(query) > MAX_QUERY_LENGTH:
            raise BadRequest(f"q cannot exceed {MAX_QUERY_LENGTH} characters")

        status = value.get("status") or "all"
        if status not in (*VALID_STATUSES, "all"):
            raise BadRequest("Invalid status filter")

        supplier_id = value.get("supplier_id")
        if supplier_id not in (None, ""):
            try:
                supplier_id = int(supplier_id)
            except (TypeError, ValueError):
                raise BadRequest("supplier_id must be an integer")
            if supplier_id <= 0:
                raise BadRequest("supplier_id must be positive")
            supplier_exists = db.session.scalar(
                select(Supplier.id).where(
                    Supplier.id == supplier_id,
                    Supplier.tenant_id == self.tenant_id,
                )
            )
            if supplier_exists is None:
                raise BadRequest("supplier_id is not available in this organization")
        else:
            supplier_id = None

        start_date = self._parse_date(value.get("start_date"), "start_date")
        end_date = self._parse_date(value.get("end_date"), "end_date")
        if start_date and end_date:
            if end_date < start_date:
                raise BadRequest("end_date must not be earlier than start_date")
            if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
                raise BadRequest(f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days")

        return {
            "q": query,
            "status": status,
            "supplier_id": supplier_id,
            "start_date": start_date.isoformat() if start_date else "",
            "end_date": end_date.isoformat() if end_date else "",
        }

    @staticmethod
    def _parse_date(value, field):
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            raise BadRequest(f"{field} must use YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise BadRequest(f"{field} must use YYYY-MM-DD")
        if parsed.isoformat() != value:
            raise BadRequest(f"{field} must use YYYY-MM-DD")
        return parsed
