from app.extensions import db
from app.models.base import PKType, TimestampMixin


class ChatMessage(TimestampMixin, db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    booking_id = db.Column(PKType, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)

    booking = db.relationship("Booking")
    sender = db.relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])

