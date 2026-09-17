from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound
from sqlalchemy import select

from app.extensions import db
from app.models.user import ROLE_ADMIN, ROLE_MANAGER
from app.models.order import (
    Order,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_APPROVED,
    STATUS_SENT,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
    VALID_STATUSES,
    REMINDER_COMPLETE,
)
from app.models.order_item import OrderItem
from app.models.supplier_offer import SupplierProductOffer
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.audit_service import AuditService
from app.services.snapshot_service import SnapshotService


class OrderService:
    """Purchase-order lifecycle with relational OrderItem as operational source."""

    MAX_LINE_QUANTITY = 100_000

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.repo = OrderRepository(tenant_id=tenant_id)
        self.product_repo = ProductRepository(tenant_id=tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id=tenant_id)

    def create_order(self, user, payload: dict) -> Order:
        supplier_id = payload.get("supplier_id")
        if supplier_id is None:
            raise NotFound("Supplier not found")
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            raise BadRequest("A valid supplier_id is required")
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)
        input_items = payload.get("items", [])
        if not isinstance(input_items, list) or not input_items:
            raise BadRequest("Order must have items")

        enriched_items = self._build_snapshot_items(input_items, supplier_id)
        totals = SnapshotService.compute_totals(enriched_items)
        order = Order(
            tenant_id=self.tenant_id,
            user_id=user.id,
            supplier_id=supplier.id,
            order_number=self.repo.next_order_number(),
            supplier_name=supplier.name,
            supplier_contact=supplier.contact_name,
            supplier_email=supplier.email,
            status=STATUS_DRAFT,
            items=enriched_items,
            currency=payload.get("currency", "ILS"),
            notes=payload.get("notes"),
            **totals,
        )
        self._replace_order_items(order, enriched_items)
        self.repo.add(order)
        AuditService.log_event(
            self.tenant_id,
            user.id,
            "order.created",
            f"Order {order.order_number} created via catalog",
            {"order_id": order.id, "final_total": order.final_total},
        )
        return order

    def list_orders(self, status: str = None, limit: int = 50, offset: int = 0) -> list:
        try:
            limit = max(1, min(int(limit or 50), 200))
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError):
            raise BadRequest("limit and offset must be integers")
        if status:
            if status not in VALID_STATUSES:
                raise BadRequest(f"Invalid status filter: {status}")
            return self.repo.list_by_status(status, limit=limit, offset=offset)
        return self.repo.list_all(limit=limit, offset=offset)

    def get_order(self, order_id: int) -> Order:
        return self.repo.get_by_id_or_404(order_id)

    def update_order(self, user, order_id: int, payload: dict) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_DRAFT:
            raise Conflict(f"Order can only be edited while in '{STATUS_DRAFT}' status (current: '{order.status}')")
        if user.role not in (ROLE_MANAGER, ROLE_ADMIN) and order.user_id != user.id:
            raise Conflict("Only the order creator or a manager can edit this draft")

        if "notes" in payload:
            order.notes = payload.get("notes")
        if "items" in payload:
            input_items = payload.get("items")
            if not isinstance(input_items, list) or not input_items:
                raise BadRequest("Order must have items")
            enriched_items = self._build_snapshot_items(input_items, order.supplier_id)
            totals = SnapshotService.compute_totals(enriched_items)
            order.items = enriched_items
            order.subtotal = totals["subtotal"]
            order.discount_total = totals["discount_total"]
            order.tax_total = totals["tax_total"]
            order.final_total = totals["final_total"]
            self._replace_order_items(order, enriched_items)

        AuditService.log_event(
            self.tenant_id,
            user.id,
            "order.updated",
            f"Order {order.order_number} updated",
            {"order_id": order.id},
        )
        return order

    def delete_order(self, user, order_id: int) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_DRAFT and user.role not in (ROLE_MANAGER, ROLE_ADMIN):
            raise Forbidden("Only a manager or administrator can delete an order after submission")
        if order.status == STATUS_DRAFT and user.role not in (ROLE_MANAGER, ROLE_ADMIN) and order.user_id != user.id:
            raise Forbidden("Only the order creator or a manager can delete this draft")

        status = order.status
        number = order.order_number
        calendar_event_id = order.google_calendar_event_id
        AuditService.log_event(
            self.tenant_id,
            user.id,
            "order.deleted",
            f"Order {number} deleted",
            {
                "order_id": order.id,
                "order_number": number,
                "previous_status": status,
                "google_calendar_event_id": calendar_event_id,
                "administrative_delete": status != STATUS_DRAFT or user.role == ROLE_ADMIN,
            },
        )
        self.repo.delete(order)
        return order

    def delete_order_as_admin(self, user, order_id: int) -> None:
        if user.role != ROLE_ADMIN:
            raise Forbidden("Only a system administrator can permanently delete an existing order")
        self.delete_order(user, order_id)

    def submit_order(self, user, order_id: int) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_DRAFT:
            raise Conflict(f"Only '{STATUS_DRAFT}' orders can be submitted (current: '{order.status}')")
        if user.role not in (ROLE_MANAGER, ROLE_ADMIN) and order.user_id != user.id:
            raise Conflict("Only the order creator or a manager can submit this draft")
        if not order.order_items:
            raise Conflict("An order must contain at least one item before submission")
        order.status = STATUS_SUBMITTED
        SnapshotService.apply_snapshot(order)
        AuditService.log_event(self.tenant_id, user.id, "order.submitted", f"Order {order.order_number} submitted for approval", {"order_id": order.id})
        return order

    def approve_order(self, user, order_id: int) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_SUBMITTED:
            raise Conflict(f"Only '{STATUS_SUBMITTED}' orders can be approved (current: '{order.status}')")
        if order.user_id == user.id:
            raise Conflict("The order creator cannot approve their own order")
        order.status = STATUS_APPROVED
        AuditService.log_event(self.tenant_id, user.id, "order.approved", f"Order {order.order_number} approved", {"order_id": order.id, "approved_by": user.id})
        return order

    def reject_order(self, user, order_id: int, reason: str = "") -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_SUBMITTED:
            raise Conflict(f"Only '{STATUS_SUBMITTED}' orders can be rejected (current: '{order.status}')")
        if order.user_id == user.id:
            raise Conflict("The order creator cannot reject their own order")
        reason = (reason or "").strip()
        if len(reason) > 1000:
            raise BadRequest("Rejection reason is too long")
        rejection_note = f"Rejected: {reason}" if reason else "Rejected"
        order.notes = f"{order.notes}\n{rejection_note}" if order.notes else rejection_note
        order.status = STATUS_CANCELLED
        order.reminder_state = REMINDER_COMPLETE
        order.next_reminder_at = None
        AuditService.log_event(self.tenant_id, user.id, "order.rejected", f"Order {order.order_number} rejected", {"order_id": order.id, "reason": reason, "rejected_by": user.id})
        return order

    def mark_sent(self, user, order_id: int) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_APPROVED:
            raise Conflict(f"Only '{STATUS_APPROVED}' orders can be marked sent (current: '{order.status}')")
        order.status = STATUS_SENT
        order.reminder_state = REMINDER_COMPLETE
        order.next_reminder_at = None
        AuditService.log_event(self.tenant_id, user.id, "order.sent", f"Order {order.order_number} sent to supplier", {"order_id": order.id})
        return order

    def mark_completed(self, user, order_id: int) -> Order:
        order = self.repo.get_by_id_for_update(order_id)
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_SENT:
            raise Conflict(f"Only '{STATUS_SENT}' orders can be completed (current: '{order.status}')")
        order.status = STATUS_COMPLETED
        order.reminder_state = REMINDER_COMPLETE
        order.next_reminder_at = None
        AuditService.log_event(self.tenant_id, user.id, "order.completed", f"Order {order.order_number} completed", {"order_id": order.id})
        return order

    def _build_snapshot_items(self, input_items: list, order_supplier_id: int) -> list:
        if not all(isinstance(item, dict) for item in input_items):
            raise BadRequest("Each order item must be an object")
        if not isinstance(order_supplier_id, int) or order_supplier_id <= 0:
            raise Conflict("Order supplier is not configured")

        product_ids = []
        for item in input_items:
            product_id = item.get("product_id")
            if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
                raise BadRequest("Each order item requires a valid product_id")
            product_ids.append(product_id)
        products = {p.id: p for p in self.product_repo.get_many_by_ids(product_ids)}

        offer_ids = [item.get("supplier_offer_id") for item in input_items if item.get("supplier_offer_id") is not None]
        offers = {}
        if offer_ids:
            if any(not isinstance(offer_id, int) or isinstance(offer_id, bool) or offer_id <= 0 for offer_id in offer_ids):
                raise BadRequest("supplier_offer_id must be a positive integer")
            offers = {
                offer.id: offer
                for offer in db.session.execute(
                    select(SupplierProductOffer).where(
                        SupplierProductOffer.tenant_id == self.tenant_id,
                        SupplierProductOffer.id.in_(offer_ids),
                    )
                ).scalars().all()
            }

        enriched_items = []
        for item in input_items:
            p_id = item["product_id"]
            product = products.get(p_id)
            if not product:
                raise NotFound(f"Product {p_id} not found in your catalog")
            if not product.active:
                raise Conflict(f"Product {p_id} is inactive and cannot be ordered")

            raw_qty = item.get("quantity", 1)
            if isinstance(raw_qty, bool):
                raise BadRequest("Quantity must be a positive integer")
            try:
                qty = int(raw_qty)
            except (TypeError, ValueError):
                raise BadRequest("Quantity must be a positive integer")
            if qty <= 0 or qty > self.MAX_LINE_QUANTITY:
                raise BadRequest(f"Quantity must be between 1 and {self.MAX_LINE_QUANTITY}")

            offer_id = item.get("supplier_offer_id")
            offer = offers.get(offer_id) if offer_id is not None else None
            if offer_id is not None and offer is None:
                raise NotFound(f"Supplier offer {offer_id} not found")
            if offer is not None:
                if not offer.active:
                    raise Conflict(f"Supplier offer {offer.id} is inactive")
                if offer.product_id != product.id or offer.supplier_id != order_supplier_id:
                    raise Conflict("Supplier offer does not match the ordered product and supplier")
                unit_price = float(offer.price)
                currency = offer.currency or "ILS"
                offer_snapshot = offer.to_dict()
                supplier_sku = offer.supplier_sku
            else:
                if product.supplier_id != order_supplier_id:
                    raise Conflict("Product is assigned to a different supplier; select a valid supplier offer")
                unit_price = float(product.current_price)
                currency = product.currency or "ILS"
                offer_snapshot = None
                supplier_sku = product.supplier_sku

            if unit_price < 0:
                raise Conflict(f"Product {p_id} has an invalid negative price")

            enriched_items.append({
                "product_id": product.id,
                "sku": product.sku,
                "product_name": product.name,
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": round(qty * unit_price, 2),
                "currency": currency,
                "supplier_offer_id": offer.id if offer is not None else None,
                "supplier_sku": supplier_sku,
                "unit": offer.unit if offer is not None else product.unit,
                "units_per_carton": offer.units_per_carton if offer is not None else product.units_per_carton,
                "offer_snapshot": offer_snapshot,
            })
        return enriched_items

    def _replace_order_items(self, order: Order, enriched_items: list) -> None:
        order.order_items.clear()
        for item in enriched_items:
            order.order_items.append(
                OrderItem(
                    tenant_id=self.tenant_id,
                    product_id=item["product_id"],
                    supplier_offer_id=item.get("supplier_offer_id"),
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    currency=item.get("currency") or order.currency or "ILS",
                    product_snapshot={
                        "product_id": item["product_id"],
                        "sku": item.get("sku"),
                        "product_name": item.get("product_name"),
                        "unit": item.get("unit"),
                        "units_per_carton": item.get("units_per_carton"),
                        "supplier_sku": item.get("supplier_sku"),
                    },
                    offer_snapshot=item.get("offer_snapshot"),
                )
            )
