from app.extensions import db
from app.models.base import TimestampMixin


class PlatformSetting(TimestampMixin, db.Model):
    __tablename__ = "platform_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

