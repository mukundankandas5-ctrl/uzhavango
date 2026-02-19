from flask_login import UserMixin

from app.extensions import db
from app.models.base import PKType, TimestampMixin


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(10), nullable=False, index=True, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(24), nullable=False, index=True)
    is_verified_owner = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    tractors = db.relationship("Tractor", back_populates="owner", lazy="dynamic")
    bookings = db.relationship("Booking", back_populates="farmer", lazy="dynamic", foreign_keys="Booking.farmer_id")
    owner_bookings = db.relationship("Booking", back_populates="owner", lazy="dynamic", foreign_keys="Booking.owner_id")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    earnings = db.relationship("OwnerEarning", back_populates="owner", lazy="dynamic")
    sent_messages = db.relationship(
        "ChatMessage",
        back_populates="sender",
        lazy="dynamic",
        foreign_keys="ChatMessage.sender_id",
    )
