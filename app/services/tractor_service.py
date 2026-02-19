from decimal import Decimal
import re

from sqlalchemy.orm import joinedload

from app.errors import AppError
from app.extensions import db
from app.models import Tractor


class TractorService:
    EQUIPMENT_TYPES = {"Tractor", "Rotavator", "Harvester", "Seeder", "Sprayer", "Plough"}
    AVAILABILITY_STATUSES = {"available", "busy", "offline"}

    @staticmethod
    def _parse_coordinate(value, label):
        raw = (value or "").strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except Exception as exc:
            raise AppError(f"Invalid {label} value.", 400) from exc

    @staticmethod
    def create_tractor(owner_id, payload):
        title = (payload.get("title") or "").strip()
        price_per_hour = payload.get("price_per_hour")
        pincode = (payload.get("pincode") or "").strip()
        village = (payload.get("village") or "").strip() or None
        district = (payload.get("district") or "").strip() or None
        equipment_type = (payload.get("equipment_type") or "Tractor").strip().title()
        availability_status = (payload.get("availability_status") or "available").strip().lower()

        if not title or price_per_hour is None:
            raise AppError("Tractor title and price per hour are required.", 400)
        if not re.fullmatch(r"\d{6}", pincode):
            raise AppError("Pincode must be exactly 6 digits.", 400)
        if equipment_type not in TractorService.EQUIPMENT_TYPES:
            raise AppError("Invalid equipment type.", 400)
        if availability_status not in TractorService.AVAILABILITY_STATUSES:
            raise AppError("Invalid availability status.", 400)

        try:
            price_per_hour = Decimal(str(price_per_hour))
            if price_per_hour <= 0:
                raise ValueError
        except Exception as exc:
            raise AppError("Price per hour must be a positive number.", 400) from exc

        latitude = TractorService._parse_coordinate(payload.get("latitude"), "latitude")
        longitude = TractorService._parse_coordinate(payload.get("longitude"), "longitude")

        tractor = Tractor(
            owner_id=owner_id,
            title=title,
            description=(payload.get("description") or "").strip() or None,
            price_per_hour=price_per_hour,
            image_path=payload.get("image_path"),
            latitude=latitude,
            longitude=longitude,
            location_label=(payload.get("location_label") or "").strip() or None,
            pincode=pincode,
            village=village,
            district=district,
            equipment_type=equipment_type,
            availability_status=availability_status,
            is_available=(availability_status != "offline"),
        )
        db.session.add(tractor)
        db.session.commit()
        return tractor

    @staticmethod
    def list_tractors(page=1, per_page=12, only_available=True):
        query = Tractor.query.options(joinedload(Tractor.owner)).order_by(Tractor.created_at.desc())
        if only_available:
            query = query.filter_by(is_available=True)
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def toggle_availability(tractor_id, owner_id, is_available):
        tractor = Tractor.query.filter_by(id=tractor_id, owner_id=owner_id).first()
        if not tractor:
            raise AppError("Tractor not found.", 404)
        tractor.is_available = bool(is_available)
        tractor.availability_status = "available" if tractor.is_available else "offline"
        db.session.commit()
        return tractor

    @staticmethod
    def update_availability_status(tractor_id, owner_id, availability_status):
        tractor = Tractor.query.filter_by(id=tractor_id, owner_id=owner_id).first()
        if not tractor:
            raise AppError("Tractor not found.", 404)
        status = (availability_status or "").strip().lower()
        if status not in TractorService.AVAILABILITY_STATUSES:
            raise AppError("Invalid availability status.", 400)
        tractor.availability_status = status
        tractor.is_available = status != "offline"
        db.session.commit()
        return tractor
