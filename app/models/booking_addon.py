from app.extensions import db
from app.models.base import PKType, TimestampMixin


class BookingAddon(TimestampMixin, db.Model):
    __tablename__ = "booking_addons"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    booking_id = db.Column(PKType, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    addon_tractor_id = db.Column(PKType, db.ForeignKey("tractors.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    booking = db.relationship("Booking", back_populates="addons")
    addon_tractor = db.relationship("Tractor")

