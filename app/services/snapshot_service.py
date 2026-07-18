from datetime import datetime, timezone
from decimal import Decimal


class SnapshotService:
    """
    Freezes an order's line items, pricing, and totals at a specific point in
    time (submission). Later edits to catalog prices or promotions must never
    change what a historical order shows it charged.
    """

    @staticmethod
    def build_snapshot(order) -> dict:
        return {
            "order_number": order.order_number,
            "supplier_name": order.supplier_name,
            "supplier_contact": order.supplier_contact,
            "supplier_email": order.supplier_email,
            "items": order.items or [],
            "subtotal": float(order.subtotal or 0),
            "discount_total": float(order.discount_total or 0),
            "tax_total": float(order.tax_total or 0),
            "final_total": float(order.final_total or 0),
            "currency": order.currency,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

    @staticmethod
    def apply_snapshot(order) -> None:
        order.snapshot = SnapshotService.build_snapshot(order)
        order.snapshot_taken_at = datetime.now(timezone.utc)

    @staticmethod
    def compute_totals(items: list, discount_total: float = 0, tax_rate: float = 0.0) -> dict:
        """
        items: list of {"quantity": int, "unit_price": float, ...}
        Uses Decimal internally to avoid float rounding drift on money.
        """
        subtotal = Decimal("0")
        for item in items or []:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("unit_price", 0)))
            subtotal += qty * price

        discount = Decimal(str(discount_total or 0))
        taxable = max(subtotal - discount, Decimal("0"))
        tax = (taxable * Decimal(str(tax_rate or 0))).quantize(Decimal("0.01"))
        final_total = (taxable + tax).quantize(Decimal("0.01"))

        return {
            "subtotal": float(subtotal.quantize(Decimal("0.01"))),
            "discount_total": float(discount.quantize(Decimal("0.01"))),
            "tax_total": float(tax),
            "final_total": float(final_total),
        }
