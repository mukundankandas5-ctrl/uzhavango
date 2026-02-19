from app.extensions import db
from app.models.base import PKType, TimestampMixin


class Booking(TimestampMixin, db.Model):
    __tablename__ = "bookings"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    tractor_id = db.Column(PKType, db.ForeignKey("tractors.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    hours = db.Column(db.Integer, nullable=False)
    quoted_price_per_hour = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    total_base_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_addon_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    grand_total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    surge_multiplier = db.Column(db.Numeric(5, 2), nullable=False, default=1)
    commission_pct = db.Column(db.Numeric(5, 2), nullable=False, default=10)
    commission_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    owner_payout_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    en_route_at = db.Column(db.DateTime(timezone=True), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    farmer_confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completion_confirmed_hours = db.Column(db.Integer, nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)

    farmer_note = db.Column(db.Text, nullable=True)
    owner_note = db.Column(db.Text, nullable=True)

    tractor = db.relationship("Tractor", back_populates="bookings")
    farmer = db.relationship("User", back_populates="bookings", foreign_keys=[farmer_id])
    owner = db.relationship("User", back_populates="owner_bookings", foreign_keys=[owner_id])
    payment = db.relationship("Payment", back_populates="booking", uselist=False)
    addons = db.relationship("BookingAddon", back_populates="booking", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("ix_bookings_farmer_status", "farmer_id", "status"),
        db.Index("ix_bookings_tractor_status", "tractor_id", "status"),
        db.CheckConstraint("hours > 0", name="ck_booking_hours_positive"),
    )
