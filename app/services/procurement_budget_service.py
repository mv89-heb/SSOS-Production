import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, or_, select
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from app.extensions import db
from app.models.order import (
    Order,
    STATUS_SUBMITTED,
    STATUS_APPROVED,
    STATUS_SENT,
    STATUS_COMPLETED,
)
from app.models.procurement_budget import ProcurementBudget
from app.models.user import ROLE_ADMIN, ROLE_MANAGER
from app.services.audit_service import AuditService


COMMITTED_ORDER_STATUSES = (
    STATUS_SUBMITTED,
    STATUS_APPROVED,
    STATUS_SENT,
    STATUS_COMPLETED,
)


class BudgetLimitExceeded(Conflict):
    def __init__(self, budget_impact):
        super().__init__("ההזמנה חורגת מתקציב מוגדר במצב חסימה. נדרשת עקיפה מאושרת עם נימוק.")
        self.budget_impact = budget_impact


class ProcurementBudgetService:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _scope_value(value):
        if not isinstance(value, str):
            raise BadRequest("scope_value must be text")
        value = value.strip()
        if not value or len(value) > 120:
            raise BadRequest("scope_value must contain 1-120 characters")
        return value

    @staticmethod
    def _parse_period_start(value, period_type):
        if not isinstance(value, str):
            raise BadRequest("period_start must use YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError):
            raise BadRequest("period_start must use YYYY-MM-DD")
        if parsed.isoformat() != value:
            raise BadRequest("period_start must use YYYY-MM-DD")
        if period_type == "weekly" and parsed.weekday() != 0:
            raise BadRequest("A weekly budget must start on Monday")
        if period_type == "monthly" and parsed.day != 1:
            raise BadRequest("A monthly budget must start on the first day of the month")
        return parsed

    @staticmethod
    def _period_end(period_type, period_start):
        if period_type == "weekly":
            return period_start + timedelta(days=7)
        if period_start.month == 12:
            return date(period_start.year + 1, 1, 1)
        return date(period_start.year, period_start.month + 1, 1)

    @staticmethod
    def _period_start_for(period_type, value):
        if period_type == "weekly":
            return value - timedelta(days=value.weekday())
        return date(value.year, value.month, 1)

    @staticmethod
    def _validate_payload(payload):
        if not isinstance(payload, dict):
            raise BadRequest("Budget payload must be an object")
        scope_type = payload.get("scope_type")
        if scope_type not in {"department", "project"}:
            raise BadRequest("scope_type must be department or project")
        scope_value = ProcurementBudgetService._scope_value(payload.get("scope_value"))
        period_type = payload.get("period_type")
        if period_type not in {"weekly", "monthly"}:
            raise BadRequest("period_type must be weekly or monthly")
        period_start = ProcurementBudgetService._parse_period_start(payload.get("period_start"), period_type)
        try:
            amount = Decimal(str(payload.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            raise BadRequest("Budget amount must be a positive number")
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise BadRequest("Budget amount must be greater than zero and within the supported range")
        currency = str(payload.get("currency") or "ILS").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise BadRequest("currency must be a three-letter ISO currency code")
        enforcement_mode = payload.get("enforcement_mode", "warn")
        if enforcement_mode not in {"warn", "block"}:
            raise BadRequest("enforcement_mode must be warn or block")
        active = payload.get("active", True)
        if not isinstance(active, bool):
            raise BadRequest("active must be a boolean")
        return {
            "scope_type": scope_type,
            "scope_value": scope_value,
            "period_type": period_type,
            "period_start": period_start,
            "amount": amount.quantize(Decimal("0.01")),
            "currency": currency,
            "enforcement_mode": enforcement_mode,
            "active": active,
        }

    def list_budgets(self, active_only=True):
        query = ProcurementBudget.query.filter_by(tenant_id=self.tenant_id)
        if active_only:
            query = query.filter(ProcurementBudget.active.is_(True))
        budgets = query.order_by(
            ProcurementBudget.period_start.desc(),
            ProcurementBudget.scope_type.asc(),
            ProcurementBudget.scope_value.asc(),
        ).all()
        return [self._serialize_with_spend(budget) for budget in budgets]

    def create_budget(self, user, payload):
        values = self._validate_payload(payload)
        self._ensure_unique(values)
        budget = ProcurementBudget(
            tenant_id=self.tenant_id,
            created_by=user.id,
            **values,
        )
        db.session.add(budget)
        db.session.flush()
        AuditService.log_event(
            self.tenant_id, user.id, "procurement_budget.created",
            f"Budget created for {budget.scope_type}: {budget.scope_value}",
            {"budget_id": budget.id, "scope_type": budget.scope_type,
             "scope_value": budget.scope_value, "period_type": budget.period_type,
             "period_start": budget.period_start.isoformat(), "amount": str(budget.amount),
             "currency": budget.currency, "enforcement_mode": budget.enforcement_mode},
        )
        return self._serialize_with_spend(budget)

    def update_budget(self, user, budget_id, payload):
        budget = self._get_budget(budget_id, for_update=True)
        merged = {
            "scope_type": budget.scope_type,
            "scope_value": budget.scope_value,
            "period_type": budget.period_type,
            "period_start": budget.period_start.isoformat(),
            "amount": str(budget.amount),
            "currency": budget.currency,
            "enforcement_mode": budget.enforcement_mode,
            "active": budget.active,
        }
        merged.update(payload or {})
        values = self._validate_payload(merged)
        self._ensure_unique(values, exclude_id=budget.id)
        for key, value in values.items():
            setattr(budget, key, value)
        budget.updated_at = datetime.now(timezone.utc)
        AuditService.log_event(
            self.tenant_id, user.id, "procurement_budget.updated",
            f"Budget {budget.id} updated",
            {"budget_id": budget.id, "scope_type": budget.scope_type,
             "scope_value": budget.scope_value, "period_start": budget.period_start.isoformat()},
        )
        return self._serialize_with_spend(budget)

    def deactivate_budget(self, user, budget_id):
        budget = self._get_budget(budget_id, for_update=True)
        if not budget.active:
            return self._serialize_with_spend(budget)
        budget.active = False
        budget.updated_at = datetime.now(timezone.utc)
        AuditService.log_event(
            self.tenant_id, user.id, "procurement_budget.deactivated",
            f"Budget {budget.id} deactivated",
            {"budget_id": budget.id, "scope_type": budget.scope_type,
             "scope_value": budget.scope_value},
        )
        return self._serialize_with_spend(budget)

    def preview_order(self, order):
        impacts = []
        order_date = order.planned_order_date or (
            order.created_at.date() if order.created_at else datetime.now(timezone.utc).date()
        )
        order_amount = Decimal(str(order.final_total or 0))
        currency = (order.currency or "ILS").upper()
        missing_scopes = []
        for scope_type in ("department", "project"):
            period_budgets = []
            for period_type in ("weekly", "monthly"):
                period_start = self._period_start_for(period_type, order_date)
                period_budgets.extend(ProcurementBudget.query.filter(
                    ProcurementBudget.tenant_id == self.tenant_id,
                    ProcurementBudget.active.is_(True),
                    ProcurementBudget.scope_type == scope_type,
                    ProcurementBudget.period_type == period_type,
                    ProcurementBudget.period_start == period_start,
                    ProcurementBudget.currency == currency,
                ).all())
            scope_value = getattr(order, scope_type, None)
            matching = [
                budget for budget in period_budgets
                if scope_value and budget.scope_value.casefold() == str(scope_value).strip().casefold()
            ]
            if period_budgets and not matching:
                missing_scopes.append(scope_type)
            for budget in matching:
                spent = self._spent_for_budget(budget, exclude_order_id=order.id)
                projected = spent + order_amount
                budget_amount = Decimal(str(budget.amount))
                impacts.append({
                    "budget_id": budget.id,
                    "scope_type": budget.scope_type,
                    "scope_value": budget.scope_value,
                    "period_type": budget.period_type,
                    "period_start": budget.period_start.isoformat(),
                    "period_end": self._period_end(budget.period_type, budget.period_start).isoformat(),
                    "currency": budget.currency,
                    "budget_amount": float(budget_amount),
                    "committed_before": float(spent),
                    "order_amount": float(order_amount),
                    "projected_total": float(projected),
                    "remaining_after": float(budget_amount - projected),
                    "over_budget": projected > budget_amount,
                    "enforcement_mode": budget.enforcement_mode,
                })
        impacts.sort(key=lambda item: (item["scope_type"], item["scope_value"]))
        blocks = [item for item in impacts if item["over_budget"] and item["enforcement_mode"] == "block"]
        warnings = [item for item in impacts if item["over_budget"] and item["enforcement_mode"] == "warn"]
        assignment_required = bool(missing_scopes)
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "department": order.department,
            "project": order.project,
            "currency": currency,
            "budget_date": order_date.isoformat(),
            "impacts": impacts,
            "over_budget": any(item["over_budget"] for item in impacts),
            "assignment_required": assignment_required,
            "missing_scopes": missing_scopes,
            "blocked": bool(blocks or assignment_required),
            "warnings": warnings,
            "blocks": blocks,
        }

    def _active_budget_ids_for_order(self, order):
        order_date = order.planned_order_date or (
            order.created_at.date() if order.created_at else datetime.now(timezone.utc).date()
        )
        ids = set()
        for period_type in ("weekly", "monthly"):
            period_start = self._period_start_for(period_type, order_date)
            ids.update(db.session.scalars(select(ProcurementBudget.id).where(
                ProcurementBudget.tenant_id == self.tenant_id,
                ProcurementBudget.active.is_(True),
                ProcurementBudget.period_type == period_type,
                ProcurementBudget.period_start == period_start,
                ProcurementBudget.currency == (order.currency or "ILS").upper(),
            )).all())
        return sorted(ids)

    def evaluate_submission(self, order, user, override_reason=None):
        # Lock all active budgets for this period/currency in stable order, then
        # recalculate commitments inside the transaction to prevent concurrent
        # submissions from consuming the same remaining budget.
        for budget_id in self._active_budget_ids_for_order(order):
            self._get_budget(budget_id, for_update=True)
        impact = self.preview_order(order)
        if impact["blocked"]:
            reason = str(override_reason or "").strip()
            if not reason:
                raise BudgetLimitExceeded(impact)
            if user.role not in (ROLE_MANAGER, ROLE_ADMIN):
                raise Forbidden("Only a manager or administrator can override a budget block or missing budget assignment")
            if len(reason) > 1000:
                raise BadRequest("Budget override reason is too long")
            event = "order.budget_assignment_override" if impact["assignment_required"] else "order.budget_override"
            AuditService.log_event(
                self.tenant_id, user.id, event,
                f"Budget override for order {order.order_number}",
                {"order_id": order.id, "order_number": order.order_number,
                 "reason": reason, "budget_impact": impact["blocks"],
                 "missing_scopes": impact["missing_scopes"],
                 "overridden_by": user.id},
            )
        elif impact["warnings"]:
            AuditService.log_event(
                self.tenant_id, user.id, "order.budget_warning",
                f"Order {order.order_number} exceeds a warning-only budget",
                {"order_id": order.id, "budget_impact": impact["warnings"]},
            )
        return impact

    def _spent_for_budget(self, budget, exclude_order_id=None):
        period_end = self._period_end(budget.period_type, budget.period_start)
        start_at = datetime.combine(budget.period_start, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(period_end, time.min, tzinfo=timezone.utc)
        scope_column = getattr(Order, budget.scope_type)
        date_filter = or_(
            and_(
                Order.planned_order_date.is_not(None),
                Order.planned_order_date >= budget.period_start,
                Order.planned_order_date < period_end,
            ),
            and_(
                Order.planned_order_date.is_(None),
                Order.created_at >= start_at,
                Order.created_at < end_at,
            ),
        )
        query = select(func.coalesce(func.sum(Order.final_total), 0)).where(
            Order.tenant_id == self.tenant_id,
            Order.status.in_(COMMITTED_ORDER_STATUSES),
            Order.currency == budget.currency,
            func.lower(scope_column) == budget.scope_value.casefold(),
            date_filter,
        )
        if exclude_order_id is not None:
            query = query.where(Order.id != exclude_order_id)
        total = db.session.scalar(query)
        return Decimal(str(total or 0))

    def _serialize_with_spend(self, budget):
        spent = self._spent_for_budget(budget)
        return budget.to_dict(spent_amount=spent)

    def _ensure_unique(self, values, exclude_id=None):
        query = ProcurementBudget.query.filter(
            ProcurementBudget.tenant_id == self.tenant_id,
            ProcurementBudget.scope_type == values["scope_type"],
            func.lower(ProcurementBudget.scope_value) == values["scope_value"].casefold(),
            ProcurementBudget.period_type == values["period_type"],
            ProcurementBudget.period_start == values["period_start"],
            ProcurementBudget.currency == values["currency"],
        )
        if exclude_id is not None:
            query = query.filter(ProcurementBudget.id != exclude_id)
        if query.first():
            raise Conflict("A budget already exists for this scope, period and currency")

    def _get_budget(self, budget_id, for_update=False):
        query = ProcurementBudget.query.filter_by(id=budget_id, tenant_id=self.tenant_id)
        if for_update:
            query = query.with_for_update()
        budget = query.first()
        if budget is None:
            raise NotFound("Budget not found")
        return budget
