from app.errors import AppError
from app.extensions import db
from app.models import Booking, ChatMessage


class ChatService:
    @staticmethod
    def can_access_booking_chat(booking, user):
        return user.role == "admin" or user.id in {booking.farmer_id, booking.owner_id}

    @staticmethod
    def list_messages(booking_id, user):
        booking = Booking.query.get(booking_id)
        if not booking:
            raise AppError("Booking not found.", 404)
        if not ChatService.can_access_booking_chat(booking, user):
            raise AppError("Forbidden.", 403)
        return (
            ChatMessage.query.filter_by(booking_id=booking_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(300)
            .all()
        )

    @staticmethod
    def post_message(booking_id, sender_id, sender_user, message):
        booking = Booking.query.get(booking_id)
        if not booking:
            raise AppError("Booking not found.", 404)
        if not ChatService.can_access_booking_chat(booking, sender_user):
            raise AppError("Forbidden.", 403)
        text = (message or "").strip()
        if not text:
            raise AppError("Message is required.", 400)

        row = ChatMessage(booking_id=booking_id, sender_id=sender_id, message=text)
        db.session.add(row)
        db.session.commit()
        return row

