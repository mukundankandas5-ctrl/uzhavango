from datetime import datetime, timezone

from app.extensions import db
from sqlalchemy import BigInteger, Integer


# Use BIGINT in PostgreSQL, but INTEGER in SQLite so autoincrement works.
PKType = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
