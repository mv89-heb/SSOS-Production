from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.models.order import (
    Order,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_APPROVED,
    STATUS_SENT,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
    VALID_STATUSES,
)
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.audit_service import AuditService
from app.services.snapshot_service import SnapshotService


class OrderService:
    """
    Order lifecycle: draft -> submitted -> approved -> sent -> completed,
    with `cancelled` reachable from draft/submitted/approved.

    Editing (update_order) is only permitted in `draft` — from `submitted`
    onward the order carries a frozen Snapshot (see SnapshotService) that
    must never be rewritten by a later edit, price change, or product
    deletion. Status transitions each have their own method rather than
    being folded into update_order, so each transition can carry its own
    permission/precondition/audit semantics.
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.repo = OrderRepository(tenant_id=tenant_id)
        self.product_repo = ProductRepository(tenant_id=tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id=tenant_id)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_order(self, user, payload: dict) -> Order:
        supplier_id = payload.get("supplier_id")
        # IDOR Protection: BaseRepo throws 404 if supplier belongs to another tenant
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)

        input_items = payload.get("items", [])
        if not isinstance(input_items, list) or not input_items:
            raise BadRequest("Order must have items")

        enriched_items = self._build_snapshot_items(input_items)
        totals = SnapshotService.compute_totals(enriched_items)

        order = Order(
            tenant_id=self.tenant_id,
            user_id=user.id,
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

        self.repo.add(order)

        AuditService.log_event(
            self.tenant_id, user.id, "order.created",
            f"Order {order.order_number} created via catalog",
            {"order_id": order.id, "final_total": order.final_total},
        )
        return order

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def list_orders(self, status: str = None, limit: int = 50, offset: int = 0) -> list:
        """Tenant-scoped listing (via OrderRepository, which is built on
        BaseRepository._tenant_select — every query is filtered by
        tenant_id). Supports pagination through limit/offset."""
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))

        if status:
            if status not in VALID_STATUSES:
                raise BadRequest(f"Invalid status filter: {status}")
            return self.repo.list_by_status(status, limit=limit, offset=offset)

        return self.repo.list_all(limit=limit, offset=offset)

    def get_order(self, order_id: int) -> Order:
        """Returns the order only if it belongs to the current tenant;
        raises 404 otherwise (BaseRepository.get_by_id_or_404)."""
        return self.repo.get_by_id_or_404(order_id)

    # ------------------------------------------------------------------
    # Update (draft-only content edits)
    # ------------------------------------------------------------------
    def update_order(self, user, order_id: int, payload: dict) -> Order:
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_DRAFT:
            raise Conflict(
                f"Order can only be edited while in '{STATUS_DRAFT}' status (current: '{order.status}')"
            )

        if "notes" in payload:
            order.notes = payload.get("notes")

        if "items" in payload:
            input_items = payload.get("items")
            if not isinstance(input_items, list) or not input_items:
                raise BadRequest("Order must have items")
            enriched_items = self._build_snapshot_items(input_items)
            totals = SnapshotService.compute_totals(enriched_items)
            order.items = enriched_items
            order.subtotal = totals["subtotal"]
            order.discount_total = totals["discount_total"]
            order.tax_total = totals["tax_total"]
            order.final_total = totals["final_total"]

        AuditService.log_event(
            self.tenant_id, user.id, "order.updated",
            f"Order {order.order_number} updated",
            {"order_id": order.id},
        )
        return order

    # ------------------------------------------------------------------
    # Delete (draft-only)
    # ------------------------------------------------------------------
    def delete_order(self, user, order_id: int) -> None:
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_DRAFT:
            raise Conflict(
                f"Only '{STATUS_DRAFT}' orders can be deleted (current: '{order.status}')"
            )

        AuditService.log_event(
            self.tenant_id, user.id, "order.deleted",
            f"Order {order.order_number} deleted",
            {"order_id": order.id, "order_number": order.order_number},
        )
        self.repo.delete(order)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------
    def submit_order(self, user, order_id: int) -> Order:
        """draft -> submitted. Freezes the immutable Snapshot: from this
        point on, later catalog/price changes never alter this order."""
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_DRAFT:
            raise Conflict(
                f"Only '{STATUS_DRAFT}' orders can be submitted (current: '{order.status}')"
            )

        order.status = STATUS_SUBMITTED
        SnapshotService.apply_snapshot(order)

        AuditService.log_event(
            self.tenant_id, user.id, "order.submitted",
            f"Order {order.order_number} submitted for approval",
            {"order_id": order.id},
        )
        return order

    def approve_order(self, user, order_id: int) -> Order:
        """submitted -> approved. Caller (route) is responsible for
        enforcing the manager/admin role requirement via PermissionService,
        consistent with how every other route in this module gates access."""
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_SUBMITTED:
            raise Conflict(
                f"Only '{STATUS_SUBMITTED}' orders can be approved (current: '{order.status}')"
            )

        order.status = STATUS_APPROVED

        AuditService.log_event(
            self.tenant_id, user.id, "order.approved",
            f"Order {order.order_number} approved",
            {"order_id": order.id, "approved_by": user.id},
        )
        return order

    def reject_order(self, user, order_id: int, reason: str = "") -> Order:
        """submitted -> cancelled, with the reason preserved. Role
        enforcement lives in the route, same as approve_order."""
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_SUBMITTED:
            raise Conflict(
                f"Only '{STATUS_SUBMITTED}' orders can be rejected (current: '{order.status}')"
            )

        order.status = STATUS_CANCELLED
        rejection_note = f"Rejected: {reason}" if reason else "Rejected"
        order.notes = f"{order.notes}\n{rejection_note}" if order.notes else rejection_note

        AuditService.log_event(
            self.tenant_id, user.id, "order.rejected",
            f"Order {order.order_number} rejected",
            {"order_id": order.id, "reason": reason, "rejected_by": user.id},
        )
        return order

    def mark_sent(self, user, order_id: int) -> Order:
        """approved -> sent."""
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_APPROVED:
            raise Conflict(
                f"Only '{STATUS_APPROVED}' orders can be marked sent (current: '{order.status}')"
            )
        order.status = STATUS_SENT
        AuditService.log_event(
            self.tenant_id, user.id, "order.sent",
            f"Order {order.order_number} sent to supplier",
            {"order_id": order.id},
        )
        return order

    def mark_completed(self, user, order_id: int) -> Order:
        """sent -> completed."""
        order = self.repo.get_by_id_or_404(order_id)
        if order.status != STATUS_SENT:
            raise Conflict(
                f"Only '{STATUS_SENT}' orders can be completed (current: '{order.status}')"
            )
        order.status = STATUS_COMPLETED
        AuditService.log_event(
            self.tenant_id, user.id, "order.completed",
            f"Order {order.order_number} completed",
            {"order_id": order.id},
        )
        return order

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _build_snapshot_items(self, input_items: list) -> list:
        """Resolves product_ids against this tenant's catalog and freezes
        their current name/sku/price into plain line-item dicts. Products
        are looked up once via get_many_by_ids (also tenant-scoped), so an
        item referencing another tenant's product simply won't resolve."""
        product_ids = [i.get("product_id") for i in input_items]
        products = {p.id: p for p in self.product_repo.get_many_by_ids(product_ids)}

        enriched_items = []
        for item in input_items:
            p_id = item.get("product_id")
            p = products.get(p_id)
            if not p:
                raise NotFound(f"Product {p_id} not found in your catalog")

            qty = int(item.get("quantity", 1))
            unit_price = float(p.current_price)

            enriched_items.append({
                "product_id": p.id,
                "sku": p.sku,
                "product_name": p.name,
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": round(qty * unit_price, 2),
            })
        return enriched_items
