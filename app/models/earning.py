from app.extensions import db
from app.models.base import PKType, TimestampMixin


class OwnerEarning(TimestampMixin, db.Model):
    __tablename__ = "owner_earnings"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    owner_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = db.Column(PKType, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True)
    gross_amount = db.Column(db.Numeric(12, 2), nullable=False)
    platform_fee = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    net_amount = db.Column(db.Numeric(12, 2), nullable=False)

    owner = db.relationship("User", back_populates="earnings")
