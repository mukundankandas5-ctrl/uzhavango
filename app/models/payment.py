from app.extensions import db
from app.models.base import PKType, TimestampMixin


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    booking_id = db.Column(PKType, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    receipt_number = db.Column(db.String(32), nullable=False, unique=True, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    farmer_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_status = db.Column(db.String(24), nullable=False, default="paid", index=True)

    booking = db.relationship("Booking", back_populates="payment")
