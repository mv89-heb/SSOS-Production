"""Phase 3.2C — Validation & Import Preview Engine."""
import difflib
import re
from decimal import Decimal, InvalidOperation

from app.models.import_mapping import (
    MAPPING_STATUS_APPROVED,
    TARGET_BARCODE,
    TARGET_CATEGORY,
    TARGET_DISCOUNT_PRICE,
    TARGET_PRICE,
    TARGET_PRICE_AFTER_VAT,
    TARGET_PRICE_BEFORE_VAT,
    TARGET_PRODUCT_CODE,
    TARGET_PRODUCT_NAME,
    TARGET_SUPPLIER_NAME,
    TARGET_SUPPLIER_OFFER,
    TARGET_UNIT,
)
from app.models.import_validation import (
    ACTION_CREATE,
    ACTION_ERROR,
    ACTION_EXISTING,
    ACTION_SKIP,
    ACTION_UPDATE,
    ImportPreview,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    VALIDATION_STATUS_COMPLETED,
)
from app.repositories.import_mapping_repository import ImportMappingRepository
from app.repositories.import_row_repository import ImportRowRepository
from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_validation_repository import (
    ImportIssueRepository,
    ImportPreviewRepository,
    ImportValidationRepository,
)
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.audit_service import AuditService

_PRIMARY_PRICE_TARGETS = (
    TARGET_PRICE,
    TARGET_PRICE_BEFORE_VAT,
    TARGET_PRICE_AFTER_VAT,
    TARGET_DISCOUNT_PRICE,
)
_PRICE_TYPE_PRIORITY = {"regular": 0, "before_vat": 1, "after_vat": 2, "discount": 3, None: 4}
UNIT_SYNONYMS = {
    "קג": "קילו", 'ק"ג': "קילו", "ק''ג": "קילו", 'ק״ג': "קילו",
    "יח": "יחידה", "יח'": "יחידה", 'יח״': "יחידה",
}
_SIMILAR_NAME_THRESHOLD = 0.85
_UNUSUAL_PRICE_CHANGE_RATIO = 0.5
_CURRENCY_RE = re.compile(r"[\u20aa$\u20ac,\s]")


class ImportValidationError(Exception):
    pass


def _clean(value) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_supplier(value) -> str:
    text = _clean(value).lower()
    text = re.sub(r"[-_/\\]+", " ", text)
    text = re.sub(r"[()\[\]{},.:'\"״׳]", " ", text)
    text = re.sub(r"\bאנד\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_price(raw):
    s = _clean(raw)
    if not s:
        return None, None
    try:
        return Decimal(_CURRENCY_RE.sub("", s)), None
    except InvalidOperation:
        return None, f"'{raw}' is not a valid number"


def _names_similar(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _SIMILAR_NAME_THRESHOLD


class ImportValidationService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_repo = ImportSessionRepository(tenant_id)
        self.row_repo = ImportRowRepository(tenant_id)
        self.mapping_repo = ImportMappingRepository(tenant_id)
        self.validation_repo = ImportValidationRepository(tenant_id)
        self.preview_repo = ImportPreviewRepository(tenant_id)
        self.issue_repo = ImportIssueRepository(tenant_id)
        self.product_repo = ProductRepository(tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id)

    def get_latest_validation(self, session_id: int):
        self.session_repo.get_by_id_or_404(session_id)
        return self.validation_repo.get_latest_by_session(session_id)

    def validate(self, session_id: int):
        session = self.session_repo.get_by_id_or_404(session_id)
        if not session.staged_sheet_name:
            raise ImportValidationError("This session has no staged sheet to validate.")

        mapping = self.mapping_repo.get_by_session_and_sheet(session_id, session.staged_sheet_name)
        if not mapping:
            raise ImportValidationError("No mapping exists for this session yet — run Mapping first.")
        if mapping.status != MAPPING_STATUS_APPROVED:
            raise ImportValidationError("The mapping must be approved before validation can run.")

        self.validation_repo.delete_previous_for_session(session_id)
        validation = self.validation_repo.model(
            tenant_id=self.tenant_id,
            import_session_id=session_id,
            import_mapping_id=mapping.id,
            status=VALIDATION_STATUS_COMPLETED,
            created_by=self.user_id,
        )
        self.validation_repo.add(validation)

        rows = self.row_repo.get_all_by_session(session_id)
        existing_products = self.product_repo.get_all_for_matching()
        existing_suppliers = self.supplier_repo.get_all_for_matching()
        known_units = {p.unit.strip() for p in existing_products if p.unit}

        supplier_by_name = {_normalize_supplier(s.name): s for s in existing_suppliers if s.name}
        product_by_barcode = {p.barcode.strip(): p for p in existing_products if p.barcode}
        product_by_code = {p.sku.strip().lower(): p for p in existing_products if p.sku}
        product_by_name = {p.name.strip().lower(): p for p in existing_products if p.name}
        columns_by_index = {c.column_index: c for c in mapping.columns}

        summary = {
            "products_to_create": 0,
            "products_to_update": 0,
            "products_to_skip": 0,
            "suppliers_to_create": 0,
            "offers_to_create": 0,
            "offers_to_update": 0,
            "warning_count": 0,
            "error_count": 0,
        }
        preview_rows, issues = [], []
        seen_in_file_by_barcode, seen_in_file_by_name = {}, {}
        pending_new_suppliers = {}

        for row in rows:
            preview, row_issues = self._interpret_row(
                row, columns_by_index, session,
                product_by_barcode, product_by_code, product_by_name,
                supplier_by_name, pending_new_suppliers, known_units,
                seen_in_file_by_barcode, seen_in_file_by_name,
            )
            preview.tenant_id = self.tenant_id
            preview.import_validation_id = validation.id
            preview_rows.append(preview)

            for issue_data in row_issues:
                issues.append(self.issue_repo.model(
                    tenant_id=self.tenant_id,
                    import_validation_id=validation.id,
                    **issue_data,
                ))
                if issue_data["severity"] == SEVERITY_ERROR:
                    summary["error_count"] += 1
                else:
                    summary["warning_count"] += 1

            if preview.product_action == ACTION_CREATE:
                summary["products_to_create"] += 1
            elif preview.product_action == ACTION_UPDATE:
                summary["products_to_update"] += 1
            elif preview.product_action == ACTION_SKIP:
                summary["products_to_skip"] += 1

            for offer in preview.offers or []:
                if offer["action"] == ACTION_CREATE:
                    summary["offers_to_create"] += 1
                elif offer["action"] == ACTION_UPDATE:
                    summary["offers_to_update"] += 1

        summary["suppliers_to_create"] = len(pending_new_suppliers)
        self.preview_repo.bulk_add(preview_rows)
        self.issue_repo.bulk_add(issues)
        for key, value in summary.items():
            setattr(validation, key, value)

        AuditService.log_event(
            self.tenant_id,
            self.user_id,
            "import.validated",
            f"Validated {session.filename} ({len(rows)} row(s))",
            {"import_validation_id": validation.id, **summary},
        )
        return validation

    def _interpret_row(
        self, row, columns_by_index, session,
        product_by_barcode, product_by_code, product_by_name,
        supplier_by_name, pending_new_suppliers, known_units,
        seen_in_file_by_barcode, seen_in_file_by_name,
    ):
        values = row.raw_values or []

        def value_for(target):
            for idx, col in columns_by_index.items():
                if col.final_target == target and idx < len(values) and _clean(values[idx]):
                    return _clean(values[idx])
            return None

        issues = []

        def add_issue(severity, code, message, field=None):
            issues.append({
                "row_number": row.row_number,
                "field": field,
                "severity": severity,
                "code": code,
                "message": message,
            })

        product_name = value_for(TARGET_PRODUCT_NAME)
        product_code = value_for(TARGET_PRODUCT_CODE)
        barcode = value_for(TARGET_BARCODE)
        category = value_for(TARGET_CATEGORY)
        unit = value_for(TARGET_UNIT)

        if not product_name:
            add_issue(SEVERITY_ERROR, "missing_product_name", "Row has no product name.", "product_name")
            return ImportPreview(
                row_number=row.row_number,
                product_action=ACTION_ERROR,
                product_name=None,
                has_errors=True,
                has_warnings=False,
                offers=[],
            ), issues

        if not unit:
            add_issue(SEVERITY_WARNING, "missing_unit", f'Product "{product_name}" has no unit.', "unit")
        elif unit in UNIT_SYNONYMS:
            add_issue(SEVERITY_WARNING, "unit_normalization_suggestion", f'Unit "{unit}" could be normalized to "{UNIT_SYNONYMS[unit]}".', "unit")
        elif known_units and unit not in known_units and not any(_names_similar(unit, u) for u in known_units):
            add_issue(SEVERITY_WARNING, "new_unit", f'"{unit}" is a new unit not seen elsewhere in the catalog.', "unit")

        if barcode:
            if barcode in seen_in_file_by_barcode:
                add_issue(SEVERITY_WARNING, "duplicate_in_file", f"Barcode {barcode} also appears on row {seen_in_file_by_barcode[barcode]}.", "barcode")
            else:
                seen_in_file_by_barcode[barcode] = row.row_number

        name_key = product_name.strip().lower()
        if name_key in seen_in_file_by_name:
            add_issue(SEVERITY_WARNING, "duplicate_in_file", f'Product name "{product_name}" also appears on row {seen_in_file_by_name[name_key]}.', "product_name")
        else:
            seen_in_file_by_name[name_key] = row.row_number

        offer_entries = []
        for idx, col in columns_by_index.items():
            if col.final_target != TARGET_SUPPLIER_OFFER or idx >= len(values):
                continue
            raw_price = _clean(values[idx])
            if not raw_price:
                continue
            price, price_error = _parse_price(raw_price)
            supplier_name = col.final_supplier_name
            if not supplier_name:
                add_issue(SEVERITY_ERROR, "missing_supplier_name", f'Column "{col.column_header}" is mapped as a supplier offer but has no supplier assigned.', "supplier")
                continue
            if price_error:
                add_issue(SEVERITY_ERROR, "invalid_price", price_error, "price")
                continue
            offer_entries.append({"column_index": idx, "supplier_id": col.final_supplier_id, "supplier_name": supplier_name, "price": price, "price_type": col.final_price_type})

        best_by_supplier = {}
        for entry in offer_entries:
            key = _normalize_supplier(entry["supplier_name"])
            current = best_by_supplier.get(key)
            if current is None or _PRICE_TYPE_PRIORITY.get(entry["price_type"], 4) < _PRICE_TYPE_PRIORITY.get(current["price_type"], 4):
                best_by_supplier[key] = entry
        offer_entries = list(best_by_supplier.values())

        primary_supplier_name = value_for(TARGET_SUPPLIER_NAME)
        primary_supplier_id = None

        if primary_supplier_name:
            primary_supplier_id = self._resolve_supplier(primary_supplier_name, supplier_by_name, pending_new_suppliers)
            if primary_supplier_id:
                supplier_obj = next((s for s in supplier_by_name.values() if s.id == primary_supplier_id), None)
                if supplier_obj:
                    primary_supplier_name = supplier_obj.name
        elif not offer_entries and session.supplier_id and session.supplier:
            primary_supplier_name = session.supplier.name
            primary_supplier_id = session.supplier_id
        elif not offer_entries:
            # In TALL spreadsheets the supplier is often encoded in the
            # price-column mapping metadata rather than as a row value.
            mapped_supplier_names = {
                _clean(col.final_supplier_name)
                for col in columns_by_index.values()
                if col.final_target in _PRIMARY_PRICE_TARGETS and _clean(col.final_supplier_name)
            }
            if len(mapped_supplier_names) == 1:
                primary_supplier_name = next(iter(mapped_supplier_names))
                primary_supplier_id = self._resolve_supplier(primary_supplier_name, supplier_by_name, pending_new_suppliers)

        primary_price = None
        for target in _PRIMARY_PRICE_TARGETS:
            val = value_for(target)
            if val:
                primary_price, price_error = _parse_price(val)
                if price_error:
                    add_issue(SEVERITY_ERROR, "invalid_price", price_error, "price")
                    primary_price = None
                break

        if offer_entries:
            offer_entries.sort(key=lambda o: o["price"])
            primary_entry = offer_entries[0]
            primary_price = primary_entry["price"]
            primary_supplier_name = primary_entry["supplier_name"]
            primary_supplier_id = primary_entry["supplier_id"] or self._resolve_supplier(primary_supplier_name, supplier_by_name, pending_new_suppliers)

        if not primary_supplier_name:
            add_issue(SEVERITY_ERROR, "missing_supplier", f'Product "{product_name}" has no supplier.', "supplier")
        if primary_price is None:
            add_issue(SEVERITY_ERROR, "missing_price", f'Product "{product_name}" has no usable price.', "price")
        elif primary_price == 0:
            add_issue(SEVERITY_WARNING, "zero_price", f'Product "{product_name}" has a price of 0.', "price")
        elif primary_price < 0:
            add_issue(SEVERITY_ERROR, "negative_price", f'Product "{product_name}" has a negative price.', "price")

        matched_product = None
        if barcode and barcode in product_by_barcode:
            candidate = product_by_barcode[barcode]
            if primary_supplier_id is None or candidate.supplier_id == primary_supplier_id:
                matched_product = candidate
        if matched_product is None and product_code and product_code.strip().lower() in product_by_code:
            candidate = product_by_code[product_code.strip().lower()]
            if primary_supplier_id is None or candidate.supplier_id == primary_supplier_id:
                matched_product = candidate
        if matched_product is None and name_key in product_by_name:
            candidate = product_by_name[name_key]
            if primary_supplier_id is None or candidate.supplier_id == primary_supplier_id:
                matched_product = candidate

        if matched_product is None and name_key in product_by_name and primary_supplier_id is not None:
            add_issue(SEVERITY_WARNING, "same_product_other_supplier", f'"{product_name}" already exists for another supplier; a supplier-specific listing will be created.', "supplier")
        elif matched_product is None:
            for existing_name, existing_product in product_by_name.items():
                if _names_similar(name_key, existing_name):
                    add_issue(SEVERITY_WARNING, "similar_product_name", f'"{product_name}" is similar to existing product "{existing_product.name}" — review before creating a duplicate.', "product_name")
                    break

        old_price = Decimal(str(matched_product.current_price)) if matched_product is not None and matched_product.current_price is not None else None
        has_blocking_error = any(i["severity"] == SEVERITY_ERROR for i in issues)

        if matched_product is not None:
            if has_blocking_error:
                product_action = ACTION_ERROR
            elif primary_price is not None and primary_price != old_price:
                product_action = ACTION_UPDATE
                if old_price not in (None, 0) and abs(primary_price - old_price) / old_price >= _UNUSUAL_PRICE_CHANGE_RATIO:
                    pct = ((primary_price - old_price) / old_price) * 100
                    add_issue(SEVERITY_WARNING, "unusual_price_change", f'Price for "{product_name}" would change from {old_price} to {primary_price} ({"+" if pct > 0 else ""}{pct:.0f}%).', "price")
            else:
                product_action = ACTION_SKIP
        else:
            product_action = ACTION_ERROR if has_blocking_error else ACTION_CREATE

        resolved_offers = []
        for entry in offer_entries:
            supplier_id = entry["supplier_id"] or self._resolve_supplier(entry["supplier_name"], supplier_by_name, pending_new_suppliers)
            resolved_offers.append({
                "supplier_name": entry["supplier_name"], "matched_supplier_id": supplier_id,
                "price": float(entry["price"]), "price_type": entry["price_type"],
                "action": ACTION_CREATE if matched_product is None else ACTION_UPDATE,
            })

        if not offer_entries and primary_supplier_name and primary_price is not None:
            resolved_offers.append({
                "supplier_name": primary_supplier_name, "matched_supplier_id": primary_supplier_id,
                "price": float(primary_price), "price_type": "regular",
                "action": ACTION_CREATE if matched_product is None else ACTION_UPDATE,
                "is_primary": True,
            })

        return ImportPreview(
            row_number=row.row_number, product_action=product_action, product_name=product_name,
            matched_product_id=matched_product.id if matched_product else None, unit=unit,
            category=category,
            supplier_action=(ACTION_EXISTING if primary_supplier_id else (ACTION_CREATE if primary_supplier_name else None)),
            supplier_name=primary_supplier_name, matched_supplier_id=primary_supplier_id,
            price=primary_price, old_price=old_price if product_action == ACTION_UPDATE else None,
            offers=resolved_offers,
            has_errors=any(i["severity"] == SEVERITY_ERROR for i in issues),
            has_warnings=any(i["severity"] == SEVERITY_WARNING for i in issues),
        ), issues

    @staticmethod
    def _resolve_supplier(name: str, supplier_by_name: dict, pending_new_suppliers: dict):
        normalized = _normalize_supplier(name)
        if not normalized:
            return None
        exact = supplier_by_name.get(normalized)
        if exact:
            return exact.id
        candidates = []
        source_tokens = set(normalized.split())
        for canonical, supplier in supplier_by_name.items():
            canonical_tokens = set(canonical.split())
            if normalized in canonical or canonical in normalized:
                candidates.append(supplier)
                continue
            if source_tokens and canonical_tokens:
                overlap = len(source_tokens & canonical_tokens)
                if overlap >= 1 and overlap / len(source_tokens) >= 0.66:
                    candidates.append(supplier)
        unique = {s.id: s for s in candidates}
        if len(unique) == 1:
            return next(iter(unique.values())).id
        if len(unique) > 1:
            return None
        fuzzy = []
        for canonical, supplier in supplier_by_name.items():
            ratio = difflib.SequenceMatcher(None, normalized, canonical).ratio()
            if ratio >= 0.90:
                fuzzy.append((ratio, supplier))
        fuzzy.sort(key=lambda item: item[0], reverse=True)
        if fuzzy and (len(fuzzy) == 1 or fuzzy[0][0] - fuzzy[1][0] >= 0.03):
            return fuzzy[0][1].id
        pending_new_suppliers.setdefault(normalized, name.strip())
        return None
