from __future__ import annotations

import json
import logging

from flask import current_app

from app.extensions import db
from app.models.web_push_subscription import WebPushSubscription

logger = logging.getLogger(__name__)


def public_key() -> str:
    return current_app.config.get("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()


def is_configured() -> bool:
    return bool(public_key() and current_app.config.get("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip() and current_app.config.get("WEB_PUSH_VAPID_CLAIMS_EMAIL", "").strip())


def save_subscription(user_id: int, tenant_id: int, payload: dict, user_agent: str | None = None) -> WebPushSubscription:
    endpoint = str(payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError("Invalid push subscription")

    subscription = WebPushSubscription.query.filter_by(user_id=user_id, endpoint=endpoint).one_or_none()
    if subscription is None:
        subscription = WebPushSubscription(
            user_id=user_id,
            tenant_id=tenant_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=(user_agent or "")[:500] or None,
        )
        db.session.add(subscription)
    else:
        subscription.tenant_id = tenant_id
        subscription.p256dh = p256dh
        subscription.auth = auth
        subscription.user_agent = (user_agent or subscription.user_agent or "")[:500] or None
    db.session.commit()
    return subscription


def remove_subscription(user_id: int, endpoint: str) -> None:
    subscription = WebPushSubscription.query.filter_by(user_id=user_id, endpoint=endpoint).one_or_none()
    if subscription:
        db.session.delete(subscription)
        db.session.commit()


def send_to_user(user_id: int, payload: dict) -> int:
    """Best-effort Web Push. Invalid/expired subscriptions are removed."""
    if not is_configured():
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush is not installed; skipping web push")
        return 0

    subscriptions = WebPushSubscription.query.filter_by(user_id=user_id).all()
    delivered = 0
    private_key = current_app.config["WEB_PUSH_VAPID_PRIVATE_KEY"]
    claims = {"sub": current_app.config["WEB_PUSH_VAPID_CLAIMS_EMAIL"]}
    encoded = json.dumps(payload, ensure_ascii=False)

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=encoded,
                vapid_private_key=private_key,
                vapid_claims=claims,
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Web Push delivery failed status=%s endpoint=%s", status, subscription.endpoint[:80])
            if status in (404, 410):
                db.session.delete(subscription)
        except Exception:
            logger.exception("Unexpected Web Push delivery failure")

    db.session.commit()
    return delivered
