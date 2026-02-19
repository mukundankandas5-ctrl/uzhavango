from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models import Booking, Tractor
from app.services import BookingService

api_booking_bp = Blueprint("api_booking", __name__)


@api_booking_bp.post("")
@login_required
def create_booking():
    if current_user.role != "farmer":
        return jsonify({"error": "Forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    booking = BookingService.create_booking(
        farmer_id=current_user.id,
        tractor_id=payload.get("tractor_id"),
        hours=payload.get("hours"),
        farmer_note=payload.get("farmer_note"),
    )
    return jsonify({"id": booking.id, "status": booking.status}), 201


@api_booking_bp.get("/me")
@login_required
def my_bookings():
    if current_user.role != "farmer":
        return jsonify({"error": "Forbidden"}), 403
    rows = Booking.query.filter_by(farmer_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": b.id,
                "status": b.status,
                "tractor_id": b.tractor_id,
                "hours": b.hours,
                "total_amount": str(b.total_amount),
                "start_time": b.start_time.isoformat(),
            }
            for b in rows
        ]
    )


@api_booking_bp.patch("/<int:booking_id>/status")
@login_required
def update_status(booking_id):
    payload = request.get_json(silent=True) or {}
    booking = Booking.query.get_or_404(booking_id)
    tractor = Tractor.query.get_or_404(booking.tractor_id)
    new_status = (payload.get("status") or "").lower()

    if current_user.role == "owner":
        if tractor.owner_id != current_user.id:
            return jsonify({"error": "Forbidden"}), 403
    elif current_user.role == "farmer":
        if booking.farmer_id != current_user.id or new_status not in {"completed"}:
            return jsonify({"error": "Forbidden"}), 403
    else:
        return jsonify({"error": "Forbidden"}), 403

    booking = BookingService.transition_booking(booking, new_status, current_user)
    return jsonify({"id": booking.id, "status": booking.status})
