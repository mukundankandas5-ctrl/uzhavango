from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.models import Notification
from app.services import NotificationService

api_notification_bp = Blueprint("api_notification", __name__)


@api_notification_bp.get("/me")
@login_required
def my_notifications():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ]
    )


@api_notification_bp.post("/me/read")
@login_required
def mark_all_read():
    NotificationService.mark_all_read(current_user.id)
    return jsonify({"ok": True})
