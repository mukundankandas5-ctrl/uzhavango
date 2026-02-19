from app.extensions import db
from app.models.base import PKType, TimestampMixin


class TractorEquipment(TimestampMixin, db.Model):
    __tablename__ = "tractor_equipment"

    id = db.Column(PKType, primary_key=True, autoincrement=True)
    tractor_id = db.Column(PKType, db.ForeignKey("tractors.id", ondelete="CASCADE"), nullable=False, index=True)
    equipment_id = db.Column(PKType, db.ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True)

    tractor = db.relationship("Tractor", back_populates="equipment_links")
    equipment = db.relationship("Equipment", back_populates="tractor_links")

    __table_args__ = (
        db.UniqueConstraint("tractor_id", "equipment_id", name="uq_tractor_equipment"),
    )

