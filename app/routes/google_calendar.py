from flask import Blueprint, current_app, jsonify, redirect, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.services import google_calendar_service as gcal


google_calendar_bp = Blueprint("google_calendar", __name__, url_prefix="/api/integrations/google-calendar")


def _frontend_redirect(status: str, message: str = "") -> str:
    base = current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") or "/dashboard/settings"
    separator = "&" if "?" in base else "?"
    return f"{base}/dashboard/settings?google_calendar={status}{separator}message={request.args.get('message', message)}"


@google_calendar_bp.route("/status", methods=["GET"])
@login_required
def status():
    connection = gcal.get_connection(current_user.id, current_user.tenant_id)
    calendars = []
    if connection:
        try:
            calendars = [
                {"id": item.get("id"), "name": item.get("summaryOverride") or item.get("summary") or item.get("id")}
                for item in gcal.list_calendars(connection)
                if item.get("id")
            ]
        except Exception:
            calendars = []
    return jsonify({
        "success": True,
        "configured": gcal.is_configured(),
        "connection": connection.to_dict() if connection else None,
        "calendars": calendars,
    })


@google_calendar_bp.route("/connect", methods=["GET"])
@login_required
def connect():
    if not gcal.is_configured():
        return jsonify({"success": False, "error": "google_calendar_not_configured", "message": "חיבור Google Calendar דורש הגדרת OAuth בשרת."}), 503
    try:
        return redirect(gcal.authorization_url(current_user.id))
    except RuntimeError as exc:
        return jsonify({"success": False, "error": "google_calendar_not_configured", "message": str(exc)}), 503


@google_calendar_bp.route("/callback", methods=["GET"])
def callback():
    error = request.args.get("error")
    state = request.args.get("state", "")
    if error:
        return redirect(_frontend_redirect("error", error))
    code = request.args.get("code")
    if not state or not code:
        return redirect(_frontend_redirect("error", "missing_oauth_code"))
    try:
        user_id = gcal.read_oauth_state(state)
        from app.models.user import User
        user = db.session.get(User, user_id)
        if user is None or not user.active:
            raise BadRequest("משתמש Google Calendar אינו פעיל")
        token_payload = gcal.exchange_code(code)
        gcal.save_connection(user.id, user.tenant_id, token_payload)
        return redirect(_frontend_redirect("connected"))
    except Exception as exc:
        current_app.logger.exception("Google Calendar OAuth callback failed")
        return redirect(_frontend_redirect("error", str(exc)[:180]))


@google_calendar_bp.route("/disconnect", methods=["POST"])
@login_required
def disconnect():
    gcal.delete_connection(current_user.id, current_user.tenant_id)
    return jsonify({"success": True})


@google_calendar_bp.route("/calendar", methods=["POST"])
@login_required
def select_calendar():
    data = request.get_json(silent=True) or {}
    calendar_id = str(data.get("calendar_id") or "").strip()
    if not calendar_id:
        return jsonify({"success": False, "error": "calendar_id_required", "message": "יש לבחור יומן."}), 400
    connection = gcal.get_connection(current_user.id, current_user.tenant_id)
    if not connection:
        return jsonify({"success": False, "error": "google_calendar_not_connected", "message": "Google Calendar אינו מחובר."}), 409
    allowed = {item.get("id") for item in gcal.list_calendars(connection)}
    if calendar_id not in allowed:
        return jsonify({"success": False, "error": "calendar_not_writable", "message": "אין הרשאת כתיבה ליומן שנבחר."}), 403
    connection.calendar_id = calendar_id
    connection.calendar_name = next((item.get("summaryOverride") or item.get("summary") for item in gcal.list_calendars(connection) if item.get("id") == calendar_id), calendar_id)
    db.session.commit()
    return jsonify({"success": True, "connection": connection.to_dict()})
