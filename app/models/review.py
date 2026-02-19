from app.extensions import db
from app.models.base import PKType, TimestampMixin


class Review(TimestampMixin, db.Model):
    __tablename__ = "reviews"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    tractor_id = db.Column(PKType, db.ForeignKey("tractors.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id = db.Column(PKType, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.SmallInteger, nullable=False)
    comment = db.Column(db.Text, nullable=True)

    tractor = db.relationship("Tractor", back_populates="reviews")

    __table_args__ = (
        db.UniqueConstraint("tractor_id", "farmer_id", name="uq_review_tractor_farmer"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
    )
