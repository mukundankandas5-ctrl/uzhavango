from app.extensions import db
from app.models.base import PKType, TimestampMixin


class Tractor(TimestampMixin, db.Model):
    __tablename__ = "tractors"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    owner_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_per_hour = db.Column(db.Numeric(10, 2), nullable=False)
    image_path = db.Column(db.String(500), nullable=True)

    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    longitude = db.Column(db.Numeric(10, 7), nullable=True)
    location_label = db.Column(db.String(255), nullable=True)
    pincode = db.Column(db.String(6), nullable=False, index=True, default="")
    village = db.Column(db.String(120), nullable=True)
    district = db.Column(db.String(120), nullable=True)
    equipment_type = db.Column(db.String(24), nullable=False, default="Tractor", index=True)
    availability_status = db.Column(db.String(24), nullable=False, default="available", index=True)

    is_available = db.Column(db.Boolean, nullable=False, default=True, index=True)
    rating_avg = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    average_rating = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    rating_count = db.Column(db.Integer, nullable=False, default=0)

    owner = db.relationship("User", back_populates="tractors")
    bookings = db.relationship("Booking", back_populates="tractor", lazy="dynamic")
    reviews = db.relationship("Review", back_populates="tractor", lazy="dynamic")

    __table_args__ = (
        db.Index("ix_tractors_owner_available", "owner_id", "is_available"),
        db.Index("ix_tractors_created_at", "created_at"),
        db.Index("ix_tractors_pincode", "pincode"),
    )
