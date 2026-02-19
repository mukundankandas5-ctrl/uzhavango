from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app.decorators import role_required
from app.errors import AppError
from app.extensions import db
import json

from app.models import Booking, Notification, OwnerEarning, Review, Tractor, User
from app.services import (
    BookingService,
    ChatService,
    FileService,
    NotificationService,
    PlatformService,
    ReviewService,
    TractorService,
)

web_dashboard_bp = Blueprint("web_dashboard", __name__)


def _is_sqlite():
    try:
        return db.engine.url.get_backend_name() == "sqlite"
    except Exception:
        return False


def _safe_datetime_query(query, model, *column_names):
    """
    SQLite guard: old rows may contain numeric datetime values that break SQLAlchemy parsing.
    Keep only NULL or text datetime storage on affected columns.
    """
    if not _is_sqlite():
        return query
    for column_name in column_names:
        if not hasattr(model, column_name):
            continue
        col = getattr(model, column_name)
        query = query.filter(or_(col.is_(None), func.typeof(col) == "text"))
    return query


@web_dashboard_bp.get("/dashboard")
@login_required
def dashboard():
    if current_user.role == "owner":
        return redirect(url_for("web_dashboard.owner_dashboard"))
    if current_user.role == "admin":
        return redirect(url_for("web_admin.admin_dashboard"))
    return redirect(url_for("web_dashboard.farmer_dashboard"))


@web_dashboard_bp.post("/notifications/read")
@login_required
def mark_notifications_read():
    NotificationService.mark_all_read(current_user.id)
    flash("Notifications marked as read.", "success")
    next_url = request.form.get("next") or request.referrer or url_for("web_dashboard.dashboard")
    return redirect(next_url)


@web_dashboard_bp.get("/owner")
@login_required
@role_required("owner")
def owner_dashboard():
    listings = Tractor.query.filter_by(owner_id=current_user.id).order_by(Tractor.created_at.desc()).all()
    tractor_listings = [item for item in listings if (item.equipment_type or "Tractor") == "Tractor"]
    equipment_listings = [item for item in listings if (item.equipment_type or "Tractor") != "Tractor"]
    bookings_q = (
        Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
        .filter(Tractor.owner_id == current_user.id)
        .order_by(Booking.created_at.desc())
    )
    bookings_q = _safe_datetime_query(
        bookings_q,
        Booking,
        "created_at",
        "updated_at",
        "start_time",
        "end_time",
        "accepted_at",
        "completed_at",
        "paid_at",
    )
    bookings = bookings_q.all()

    notifications_q = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(
        Notification.created_at.desc()
    )
    notifications_q = _safe_datetime_query(notifications_q, Notification, "created_at", "updated_at")
    notifications = notifications_q.limit(5).all()
    revenue_rows = (
        db.session.query(OwnerEarning, Booking, Tractor)
        .join(Booking, Booking.id == OwnerEarning.booking_id)
        .join(Tractor, Tractor.id == Booking.tractor_id)
        .filter(OwnerEarning.owner_id == current_user.id)
        .order_by(OwnerEarning.created_at.desc())
        .all()
    )
    gross_total = sum(float(row[0].gross_amount or 0) for row in revenue_rows)
    platform_fee_total = sum(float(row[0].platform_fee or 0) for row in revenue_rows)
    total_earnings = sum(float(row[0].net_amount or 0) for row in revenue_rows)

    revenue_breakdown = [
        {
            "booking_id": booking.id,
            "tractor_title": tractor.title,
            "farmer_name": booking.farmer.full_name if booking.farmer else "Farmer",
            "hours": booking.hours,
            "gross_amount": float(earning.gross_amount or 0),
            "platform_fee": float(earning.platform_fee or 0),
            "net_amount": float(earning.net_amount or 0),
            "receipt_number": booking.payment.receipt_number if booking.payment else None,
            "created_at": earning.created_at,
        }
        for earning, booking, tractor in revenue_rows
    ]

    return render_template(
        "owner_dashboard.html",
        tractor_listings=tractor_listings,
        equipment_listings=equipment_listings,
        bookings=bookings,
        notifications=notifications,
        total_earnings=total_earnings,
        gross_total=gross_total,
        platform_fee_total=platform_fee_total,
        revenue_breakdown=revenue_breakdown,
        equipment_types=sorted(TractorService.EQUIPMENT_TYPES),
    )


@web_dashboard_bp.post("/owner/tractors")
@login_required
@role_required("owner")
def create_tractor():
    payload = {
        "title": request.form.get("title"),
        "description": request.form.get("description"),
        "price_per_hour": request.form.get("price_per_hour"),
        "pincode": request.form.get("pincode"),
        "village": request.form.get("village"),
        "district": request.form.get("district"),
        "equipment_type": request.form.get("equipment_type"),
        "latitude": request.form.get("latitude"),
        "longitude": request.form.get("longitude"),
        "location_label": request.form.get("location_label"),
        "availability_status": request.form.get("availability_status") or "available",
    }

    image_file = request.files.get("tractor_image")
    camera_image = request.form.get("camera_image", "")

    try:
        payload["image_path"] = None
        if image_file and image_file.filename:
            payload["image_path"] = FileService.save_image(image_file, current_app.config["UPLOAD_DIR"])
        elif camera_image:
            payload["image_path"] = FileService.save_camera_data_url(camera_image, current_app.config["UPLOAD_DIR"])

        listing = TractorService.create_tractor(current_user.id, payload)
        listing_type = (listing.equipment_type or "Equipment").strip()
        listing_name = (listing.title or listing_type).strip()
        flash(f"{listing_type} listed successfully: {listing_name}.", "success")
    except AppError as exc:
        flash(exc.message, "error")
    except Exception:
        flash("Unable to create tractor listing. Please retry.", "error")

    return redirect(url_for("web_dashboard.owner_dashboard"))


@web_dashboard_bp.post("/add_tractor")
@login_required
@role_required("owner")
def create_tractor_legacy():
    return create_tractor()


@web_dashboard_bp.post("/owner/tractors/<int:tractor_id>/availability")
@login_required
@role_required("owner")
def toggle_tractor(tractor_id):
    status = request.form.get("availability_status")
    if status:
        TractorService.update_availability_status(
            tractor_id=tractor_id,
            owner_id=current_user.id,
            availability_status=status,
        )
    else:
        TractorService.toggle_availability(
            tractor_id=tractor_id,
            owner_id=current_user.id,
            is_available=request.form.get("is_available") == "true",
        )
    flash("Availability updated.", "success")
    return redirect(url_for("web_dashboard.owner_dashboard"))


@web_dashboard_bp.post("/owner/bookings/<int:booking_id>/status")
@login_required
@role_required("owner")
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.tractor.owner_id != current_user.id:
        flash("Not authorized for this booking.", "error")
        return redirect(url_for("web_dashboard.owner_dashboard"))

    try:
        BookingService.transition_booking(booking, request.form.get("status"), current_user)
        flash("Booking updated.", "success")
    except AppError as exc:
        flash(exc.message, "error")
    return redirect(url_for("web_dashboard.owner_dashboard"))


@web_dashboard_bp.get("/farmer")
@login_required
@role_required("farmer")
def farmer_dashboard():
    page = request.args.get("page", 1, type=int)
    tractors_page = (
        Tractor.query.filter(Tractor.availability_status != "offline")
        .filter(Tractor.equipment_type == "Tractor")
        .order_by(Tractor.created_at.desc())
        .paginate(page=page, per_page=9, error_out=False)
    )
    addon_rows = (
        Tractor.query.filter(Tractor.availability_status != "offline")
        .filter(Tractor.equipment_type != "Tractor")
        .order_by(Tractor.created_at.desc())
        .all()
    )
    addons_by_owner = {}
    for row in addon_rows:
        addons_by_owner.setdefault(row.owner_id, []).append(row)

    history_q = Booking.query.filter_by(farmer_id=current_user.id).order_by(Booking.created_at.desc())
    history_q = _safe_datetime_query(
        history_q,
        Booking,
        "created_at",
        "updated_at",
        "start_time",
        "end_time",
        "accepted_at",
        "completed_at",
        "paid_at",
    )
    history = history_q.limit(12).all()

    notifications_q = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(
        Notification.created_at.desc()
    )
    notifications_q = _safe_datetime_query(notifications_q, Notification, "created_at", "updated_at")
    notifications = notifications_q.limit(5).all()
    my_reviews = Review.query.filter_by(farmer_id=current_user.id).all()
    my_review_map = {r.tractor_id: r for r in my_reviews}
    return render_template(
        "farmer_dashboard.html",
        tractors_page=tractors_page,
        addons_by_owner=addons_by_owner,
        booking_history=history,
        notifications=notifications,
        my_review_map=my_review_map,
        commission_pct=float(PlatformService.get_decimal("commission_pct", 10)),
    )


@web_dashboard_bp.post("/farmer/bookings")
@login_required
@role_required("farmer")
def create_booking():
    try:
        booking_date = (request.form.get("booking_date") or "").strip()
        start_clock = (request.form.get("start_time") or "").strip()
        start_dt = None
        if booking_date and start_clock:
            try:
                start_dt = datetime.fromisoformat(f"{booking_date}T{start_clock}").replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise AppError("Invalid booking date/time.", 400) from exc
        addon_quantities = {}
        addon_payload = request.form.get("addon_quantities")
        if addon_payload:
            try:
                parsed = json.loads(addon_payload)
                if isinstance(parsed, dict):
                    addon_quantities = parsed
            except Exception:
                addon_quantities = {}

        BookingService.create_booking(
            farmer_id=current_user.id,
            tractor_id=request.form.get("tractor_id", type=int),
            hours=request.form.get("hours", type=int),
            start_time=start_dt,
            farmer_note=request.form.get("farmer_note"),
            addon_quantities=addon_quantities,
        )
        flash("Booking request sent.", "success")
    except AppError as exc:
        flash(exc.message, "error")
    return redirect(url_for("web_dashboard.farmer_dashboard"))


@web_dashboard_bp.post("/farmer/bookings/<int:booking_id>/status")
@login_required
@role_required("farmer")
def farmer_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.farmer_id != current_user.id:
        flash("Not authorized for this booking.", "error")
        return redirect(url_for("web_dashboard.farmer_dashboard"))

    status = request.form.get("status")
    try:
        if status == "confirm_completed":
            BookingService.farmer_confirm_completion(
                booking=booking,
                farmer_id=current_user.id,
                confirmed_hours=request.form.get("confirmed_hours", type=int),
            )
        else:
            BookingService.transition_booking(booking, status, current_user)
        flash("Booking status updated.", "success")
    except AppError as exc:
        flash(exc.message, "error")
    return redirect(url_for("web_dashboard.farmer_dashboard"))


@web_dashboard_bp.post("/book")
@login_required
@role_required("farmer")
def create_booking_legacy():
    return create_booking()


@web_dashboard_bp.post("/farmer/reviews")
@login_required
@role_required("farmer")
def create_review():
    try:
        ReviewService.upsert_review(
            tractor_id=request.form.get("tractor_id", type=int),
            farmer_id=current_user.id,
            rating=request.form.get("rating"),
            comment=request.form.get("comment"),
        )
        flash("Review saved.", "success")
    except AppError as exc:
        flash(exc.message, "error")
    return redirect(url_for("web_dashboard.farmer_dashboard"))


@web_dashboard_bp.post("/add_review")
@login_required
@role_required("farmer")
def create_review_legacy():
    return create_review()


@web_dashboard_bp.get("/tractors")
def tractors_catalog():
    pincode = (request.args.get("pincode") or "").strip()
    village = (request.args.get("village") or "").strip()
    equipment_type = (request.args.get("equipment_type") or "").strip().title()
    listing_mode = (request.args.get("listing_mode") or "all").strip().lower()
    search_term = (request.args.get("q") or "").strip()

    if search_term and not pincode and not village:
        if search_term.isdigit():
            pincode = search_term
        else:
            village = search_term

    query = Tractor.query.filter(Tractor.availability_status != "offline")

    if pincode:
        query = query.filter(Tractor.pincode == pincode)
    elif village:
        query = query.filter(Tractor.village.ilike(f"%{village}%"))
    else:
        return jsonify({"count": 0, "tractors": [], "high_demand": False})

    if equipment_type:
        query = query.filter(Tractor.equipment_type == equipment_type)
    if listing_mode == "addon":
        query = query.filter(Tractor.equipment_type != "Tractor")

    threshold = int(PlatformService.get_decimal("surge_threshold", 5))
    local_bookings = 0
    if pincode:
        local_bookings = (
            Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
            .filter(Tractor.pincode == pincode)
            .filter(Booking.status.in_(["pending", "accepted", "en_route", "working"]))
            .count()
        )
    high_demand = pincode and local_bookings > threshold

    rows = query.order_by(Tractor.created_at.desc()).limit(50).all()
    payload = []
    for t in rows:
        completed_jobs = Booking.query.filter_by(owner_id=t.owner_id, status="paid").count()
        badges = []
        if getattr(t.owner, "is_verified_owner", False):
            badges.append("Verified Owner")
        if float(t.average_rating or t.rating_avg or 0) > 4.5:
            badges.append("Top Rated")
        if completed_jobs >= 100:
            badges.append("100+ Jobs")
        payload.append(
            {
                "tractor_id": t.id,
                "name": t.title,
                "price": str(t.price_per_hour),
                "pincode": t.pincode,
                "village": t.village,
                "image": t.image_path,
                "rating": float(t.average_rating or t.rating_avg or 0),
                "status": t.availability_status,
                "equipment_type": t.equipment_type,
                "badges": badges,
            }
        )
    return jsonify(
        {
            "count": len(payload),
            "high_demand": bool(high_demand),
            "message": _availability_message(
                count=len(payload),
                locality=(pincode or village),
                equipment_type=equipment_type,
                listing_mode=listing_mode,
            ),
            "equipment_label": equipment_type or ("Add-on equipment" if listing_mode == "addon" else "Tractors"),
            "listing_mode": listing_mode,
            "tractors": payload,
        }
    )


def _availability_message(count, locality, equipment_type, listing_mode):
    local = locality or "your area"
    if equipment_type:
        label = f"{equipment_type.lower()} unit{'s' if count != 1 else ''}"
    elif listing_mode == "addon":
        label = f"add-on equipment unit{'s' if count != 1 else ''}"
    else:
        label = f"tractor{'s' if count != 1 else ''}"
    return f"{count} {label} available in {local}"


@web_dashboard_bp.get("/tractor/<int:tractor_id>")
@login_required
@role_required("farmer")
def tractor_detail(tractor_id):
    tractor = Tractor.query.get_or_404(tractor_id)
    owner = User.query.get_or_404(tractor.owner_id)
    recent_booking = (
        Booking.query.filter_by(tractor_id=tractor.id, farmer_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .first()
    )
    return render_template(
        "tractor_detail.html",
        tractor=tractor,
        owner=owner,
        recent_booking=recent_booking,
    )


@web_dashboard_bp.get("/bookings/<int:booking_id>/messages")
@login_required
def booking_messages(booking_id):
    try:
        rows = ChatService.list_messages(booking_id, current_user)
    except AppError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(
        [
            {
                "id": row.id,
                "sender_id": row.sender_id,
                "sender_name": row.sender.full_name,
                "message": row.message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    )


@web_dashboard_bp.post("/bookings/<int:booking_id>/messages")
@login_required
def send_booking_message(booking_id):
    payload = request.get_json(silent=True) or {}
    try:
        row = ChatService.post_message(
            booking_id=booking_id,
            sender_id=current_user.id,
            sender_user=current_user,
            message=payload.get("message"),
        )
    except AppError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(
        {
            "id": row.id,
            "message": row.message,
            "sender_id": row.sender_id,
            "sender_name": row.sender.full_name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    )


@web_dashboard_bp.get("/bookings/<int:owner_id>")
@login_required
@role_required("owner")
def owner_bookings(owner_id):
    if owner_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    rows = (
        Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
        .filter(Tractor.owner_id == owner_id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": b.id,
                "tractor_id": b.tractor_id,
                "tractor_title": b.tractor.title,
                "farmer_name": b.farmer.full_name,
                "farmer_phone": b.farmer.phone,
                "hours": b.hours,
                "status": b.status,
                "total_amount": str(b.total_amount),
                "receipt_number": b.payment.receipt_number if b.payment else None,
                "created_at": b.created_at.isoformat(),
            }
            for b in rows
        ]
    )


@web_dashboard_bp.get("/owner/bookings")
@login_required
@role_required("owner")
def owner_bookings_direct():
    rows = (
        Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
        .filter(Tractor.owner_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "booking_id": b.id,
                "tractor_name": b.tractor.title,
                "farmer_name": b.farmer.full_name,
                "farmer_phone": b.farmer.phone,
                "status": b.status,
                "created_at": b.created_at.isoformat(),
            }
            for b in rows
        ]
    )
