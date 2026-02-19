from app.extensions import db
from app.models.base import PKType, TimestampMixin


class Equipment(TimestampMixin, db.Model):
    __tablename__ = "equipment"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price_per_hour = db.Column(db.Numeric(10, 2), nullable=False)
    image_path = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    tractor_links = db.relationship("TractorEquipment", back_populates="equipment", lazy="dynamic", cascade="all, delete-orphan")
    booking_addons = db.relationship("BookingAddon", back_populates="equipment", lazy="dynamic")

