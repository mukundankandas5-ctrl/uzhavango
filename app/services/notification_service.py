from app.extensions import db
from app.models import Notification


class NotificationService:
    @staticmethod
    def push(user_id, title, message):
        notification = Notification(user_id=user_id, title=title, message=message)
        db.session.add(notification)
        db.session.flush()
        return notification

    @staticmethod
    def unread_count(user_id):
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def latest_for_user(user_id, limit=10):
        return (
            Notification.query.filter_by(user_id=user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_all_read(user_id):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
