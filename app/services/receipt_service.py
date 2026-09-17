import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.models.idempotency_key import IdempotencyKey
from app.models.inventory_movement import InventoryMovement, MOVEMENT_RECEIPT
from app.models.order import Order, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.services.audit_service import AuditService


class ReceiptService:
    """Transactional receiving with request-level idempotency."""

    MAX_LINE_QUANTITY = Decimal("100000")
    MAX_IDEMPOTENCY_KEY_LENGTH = 255

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def list_for_order(self, order_id: int) -> list[Receipt]:
        order = db.session.scalar(
            select(Order).where(Order.id == order_id, Order.tenant_id == self.tenant_id)
        )
        if order is None:
            raise NotFound("Order not found")
        return db.session.scalars(
            select(Receipt)
            .where(Receipt.tenant_id == self.tenant_id, Receipt.order_id == order_id)
            .order_by(Receipt.id.asc())
        ).all()

    def get(self, receipt_id: int) -> Receipt:
        receipt = db.session.scalar(
            select(Receipt).where(
                Receipt.id == receipt_id,
                Receipt.tenant_id == self.tenant_id,
            )
        )
        if receipt is None:
            raise NotFound("Receipt not found")
        return receipt

    def create_receipt(self, user, order_id: int, payload: dict, idempotency_key: str | None = None) -> tuple[Receipt, bool]:
        request_hash = self._request_hash(payload)
        if idempotency_key:
            existing = self._get_idempotency_key(idempotency_key)
            if existing:
                return self._replay_or_conflict(existing, request_hash)

        order = db.session.scalar(
            select(Order)
            .where(Order.id == order_id, Order.tenant_id == self.tenant_id)
            .with_for_update()
        )
        if order is None:
            raise NotFound("Order not found")
        if order.status != STATUS_SENT:
            raise Conflict("Only sent orders can be received")

        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise BadRequest("Receipt must contain at least one item")
        if len(raw_items) > 5000:
            raise BadRequest("Too many receipt items")

        parsed = self._parse_items(raw_items)
        order_item_ids = list(parsed)
        order_items = db.session.scalars(
            select(OrderItem)
            .where(
                OrderItem.tenant_id == self.tenant_id,
                OrderItem.order_id == order_id,
                OrderItem.id.in_(order_item_ids),
            )
            .order_by(OrderItem.id.asc())
            .with_for_update()
        ).all()
        by_id = {item.id: item for item in order_items}
        missing = [item_id for item_id in order_item_ids if item_id not in by_id]
        if missing:
            raise NotFound(f"Order item {missing[0]} not found")

        product_ids = sorted({item.product_id for item in order_items})
        products = db.session.scalars(
            select(Product)
            .where(Product.tenant_id == self.tenant_id, Product.id.in_(product_ids))
            .order_by(Product.id.asc())
            .with_for_update()
        ).all()
        products_by_id = {product.id: product for product in products}
        if len(products_by_id) != len(product_ids):
            raise NotFound("One or more products in the order are no longer available")

        receipt_number = self._receipt_number(payload.get("receipt_number"))
        receipt = Receipt(
            tenant_id=self.tenant_id,
            order_id=order.id,
            receipt_number=receipt_number,
            status=RECEIPT_POSTED,
            received_by=user.id,
            received_at=datetime.now(timezone.utc),
            notes=self._notes(payload.get("notes")),
        )
        db.session.add(receipt)
        db.session.flush()

        for order_item_id, quantity in parsed.items():
            order_item = by_id[order_item_id]
            received_before = self._received_quantity(order_item.id)
            remaining = Decimal(order_item.quantity) - received_before
            if quantity > remaining:
                raise Conflict(
                    f"Receipt quantity for order item {order_item.id} exceeds remaining quantity "
                    f"({remaining})"
                )

            product = products_by_id[order_item.product_id]
            current_stock = Decimal(product.current_stock or 0)
            new_balance = current_stock + quantity
            product.current_stock = int(new_balance)

            db.session.add(
                ReceiptItem(
                    tenant_id=self.tenant_id,
                    receipt_id=receipt.id,
                    order_item_id=order_item.id,
                    quantity=quantity,
                )
            )
            db.session.add(
                InventoryMovement(
                    tenant_id=self.tenant_id,
                    product_id=product.id,
                    user_id=user.id,
                    receipt_id=receipt.id,
                    movement_type=MOVEMENT_RECEIPT,
                    quantity=quantity,
                    balance_after=new_balance,
                    reference_type="receipt",
                    reference_id=str(receipt.id),
                    note=f"Receipt {receipt.receipt_number}",
                    occurred_at=receipt.received_at,
                )
            )

        if idempotency_key:
            self._store_idempotency_key(
                user_id=user.id,
                key=idempotency_key,
                request_hash=request_hash,
                resource_id=receipt.id,
            )

        AuditService.log_event(
            self.tenant_id,
            user.id,
            "inventory.receipt_posted",
            f"Receipt {receipt.receipt_number} posted for order {order.order_number}",
            {
                "receipt_id": receipt.id,
                "order_id": order.id,
                "order_number": order.order_number,
                "item_count": len(parsed),
            },
        )
        return receipt, False

    def _get_idempotency_key(self, key: str) -> IdempotencyKey | None:
        return db.session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == self.tenant_id,
                IdempotencyKey.key == key,
            )
        )

    def _replay_or_conflict(self, record: IdempotencyKey, request_hash: str) -> tuple[Receipt, bool]:
        if record.request_hash != request_hash:
            raise Conflict("Idempotency-Key was already used with a different request")
        if record.resource_type != "receipt":
            raise Conflict("Idempotency-Key is already associated with another resource")
        receipt = self.get(record.resource_id)
        return receipt, True

    def _store_idempotency_key(self, user_id: int, key: str, request_hash: str, resource_id: int) -> None:
        record = IdempotencyKey(
            tenant_id=self.tenant_id,
            user_id=user_id,
            key=key,
            request_hash=request_hash,
            resource_type="receipt",
            resource_id=resource_id,
            response_status=201,
        )
        db.session.add(record)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing = self._get_idempotency_key(key)
            if existing and existing.request_hash == request_hash and existing.resource_type == "receipt":
                raise Conflict("Duplicate idempotent receipt request")
            raise Conflict("Idempotency-Key is already in use")

    @staticmethod
    def _request_hash(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _received_quantity(self, order_item_id: int) -> Decimal:
        value = db.session.scalar(
            select(func.coalesce(func.sum(ReceiptItem.quantity), 0))
            .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
            .where(
                ReceiptItem.tenant_id == self.tenant_id,
                ReceiptItem.order_item_id == order_item_id,
                Receipt.tenant_id == self.tenant_id,
                Receipt.status == RECEIPT_POSTED,
            )
        )
        return Decimal(value or 0)

    def _parse_items(self, raw_items: list) -> dict[int, Decimal]:
        parsed: dict[int, Decimal] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                raise BadRequest("Each receipt item must be an object")
            order_item_id = item.get("order_item_id")
            if not isinstance(order_item_id, int) or isinstance(order_item_id, bool) or order_item_id <= 0:
                raise BadRequest("order_item_id must be a positive integer")
            if order_item_id in parsed:
                raise BadRequest("Each order item may appear only once per receipt")

            raw_quantity = item.get("quantity")
            try:
                quantity = Decimal(str(raw_quantity))
            except (InvalidOperation, TypeError, ValueError):
                raise BadRequest("Receipt quantity must be a positive integer")
            if quantity != quantity.to_integral_value() or quantity <= 0 or quantity > self.MAX_LINE_QUANTITY:
                raise BadRequest("Receipt quantity must be a positive integer")
            parsed[order_item_id] = quantity
        return parsed

    @staticmethod
    def _notes(value) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise BadRequest("notes must be a string")
        value = value.strip()
        if len(value) > 5000:
            raise BadRequest("notes is too long")
        return value or None

    @classmethod
    def _validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or len(value) > cls.MAX_IDEMPOTENCY_KEY_LENGTH:
            raise BadRequest("Idempotency-Key must contain 1-255 characters")
        return value

    @staticmethod
    def _receipt_number(value) -> str:
        if value is not None:
            if not isinstance(value, str):
                raise BadRequest("receipt_number must be a string")
            value = value.strip()
            if not value or len(value) > 40:
                raise BadRequest("receipt_number must contain 1-40 characters")
            return value
        return f"RCPT-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"
