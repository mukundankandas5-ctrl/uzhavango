from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import math

from app.errors import AppError
from app.extensions import cache, limiter
from app.models import Booking, Review, Tractor, User
from app.services import AuthService, PlatformService

web_auth_bp = Blueprint("web_auth", __name__)


@web_auth_bp.get("/")
def landing():
    return render_template("index.html")


@web_auth_bp.get("/api/platform-stats")
@cache.cached(timeout=120)
def platform_stats():
    avg_rating = (
        float(db_value(func.avg(Review.rating)) or 0)
    )
    verified_owners = int(
        db_value(func.count(User.id), User.role == "owner") or 0
    )
    total_bookings = int(db_value(func.count(Booking.id)) or 0)
    villages_served = int(
        db_distinct_non_empty_count(Tractor.location_label) or 0
    )

    return {
        "average_rating": round(avg_rating, 1),
        "verified_owners": verified_owners,
        "total_bookings": total_bookings,
        "villages_served": villages_served,
    }


@web_auth_bp.post("/location-search")
@limiter.limit("30 per minute")
def location_search():
    payload = request.get_json(silent=True) or {}
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    equipment_type = (payload.get("equipment_type") or "").strip().title()
    listing_mode = (payload.get("listing_mode") or "all").strip().lower()
    if lat is None or lon is None:
        return jsonify({"error": "Unable to detect pincode."}), 400

    try:
        query = urlencode(
            {
                "lat": lat,
                "lon": lon,
                "format": "json",
            }
        )
        req = Request(
            f"https://nominatim.openstreetmap.org/reverse?{query}",
            headers={"User-Agent": "UzhavanGo/1.0"},
        )
        with urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        postcode = ((data.get("address") or {}).get("postcode") or "").strip()
        digits = "".join(ch for ch in postcode if ch.isdigit())[:6]
        if len(digits) != 6:
            return jsonify({"error": "Unable to detect pincode."}), 404

        threshold = int(PlatformService.get_decimal("surge_threshold", 5))
        high_demand = (
            Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
            .filter(Tractor.pincode == digits)
            .filter(Booking.status.in_(["pending", "accepted", "en_route", "working"]))
            .count()
            > threshold
        )

        tractors_query = Tractor.query.filter_by(pincode=digits).filter(Tractor.availability_status != "offline")
        if equipment_type:
            tractors_query = tractors_query.filter(Tractor.equipment_type == equipment_type)
        if listing_mode == "addon":
            tractors_query = tractors_query.filter(Tractor.equipment_type != "Tractor")
        tractors = tractors_query.order_by(Tractor.created_at.desc()).limit(50).all()
        payload = []
        for t in tractors:
            distance_km = None
            if t.latitude is not None and t.longitude is not None:
                distance_km = round(haversine_km(float(lat), float(lon), float(t.latitude), float(t.longitude)), 1)
            payload.append(
                {
                    "tractor_id": t.id,
                    "name": t.title,
                    "price": str(t.price_per_hour),
                    "pincode": t.pincode,
                    "image": t.image_path,
                    "rating": float(t.average_rating or t.rating_avg or 0),
                    "distance_km": distance_km,
                    "status": t.availability_status,
                }
            )
        payload.sort(key=lambda item: item["distance_km"] if item["distance_km"] is not None else 10_000)
        return jsonify(
            {
                "pincode": digits,
                "high_demand": bool(high_demand),
                "message": f"{len(payload)} {(equipment_type or ('Add-on equipment' if listing_mode == 'addon' else 'Tractors')).lower()} available in {digits}",
                "equipment_label": equipment_type or ("Add-on equipment" if listing_mode == "addon" else "Tractors"),
                "listing_mode": listing_mode,
                "weather_alert": weather_demand_hint(
                    lat=lat,
                    lon=lon,
                    district=(data.get("address") or {}).get("state_district"),
                ),
                "tractors": payload,
            }
        )
    except Exception:
        return jsonify({"error": "Unable to detect pincode."}), 502


@web_auth_bp.post("/api/equipment-recommendation")
def equipment_recommendation():
    payload = request.get_json(silent=True) or {}
    crop = (payload.get("crop") or "").strip().lower()
    land_size = float(payload.get("land_size") or 0)
    season = (payload.get("season") or "").strip().lower()
    district = (payload.get("district") or "").strip()
    if not crop or land_size <= 0 or not season:
        return jsonify({"error": "Crop, land size, and season are required."}), 400

    equipment = "Tractor"
    hours = max(2, int(land_size * 1.2))
    if crop in {"rice", "paddy"} and season in {"kharif", "monsoon"}:
        equipment = "Rotavator"
        hours = max(3, int(land_size * 1.8))
    elif crop in {"wheat", "maize"} and season in {"rabi", "winter"}:
        equipment = "Seeder"
        hours = max(2, int(land_size * 1.4))
    elif crop in {"sugarcane", "cotton"}:
        equipment = "Harvester"
        hours = max(4, int(land_size * 2.2))
    elif crop in {"vegetable", "banana"}:
        equipment = "Sprayer"
        hours = max(2, int(land_size * 1.1))
    elif crop in {"groundnut", "millet"}:
        equipment = "Plough"
        hours = max(2, int(land_size * 1.3))

    district_hint = f" for {district}" if district else ""
    return jsonify(
        {
            "equipment": equipment,
            "hours": hours,
            "message": f"Suggested {equipment}{district_hint} for {land_size} acre(s) in {season.title()} season.",
        }
    )


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def weather_demand_hint(lat, lon, district):
    if not district:
        return None
    try:
        weather_query = urlencode(
            {
                "latitude": lat,
                "longitude": lon,
                "daily": "precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 2,
            }
        )
        weather_req = Request(
            f"https://api.open-meteo.com/v1/forecast?{weather_query}",
            headers={"User-Agent": "UzhavanGo/1.0"},
        )
        with urlopen(weather_req, timeout=8) as response:
            weather_data = json.loads(response.read().decode("utf-8"))
        probs = (weather_data.get("daily") or {}).get("precipitation_probability_max") or []
        tomorrow_prob = probs[1] if len(probs) > 1 else (probs[0] if probs else 0)
        if int(tomorrow_prob or 0) >= 60:
            return f"High demand expected tomorrow due to rain forecast in {district}."
    except Exception:
        pass
    return None


@web_auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web_dashboard.dashboard"))

    if request.method == "GET":
        return render_template("register.html")

    try:
        user = AuthService.register_user(
            full_name=request.form.get("full_name", ""),
            email=request.form.get("email", ""),
            password=request.form.get("password", ""),
            role=request.form.get("role", ""),
            phone=request.form.get("phone", ""),
        )
        login_user(user)
        flash("Account created successfully.", "success")
        return redirect(url_for("web_dashboard.dashboard"))
    except AppError as exc:
        flash(exc.message, "error")
        return redirect(url_for("web_auth.register"))


@web_auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web_dashboard.dashboard"))

    if request.method == "GET":
        return render_template("login.html")

    try:
        role = (request.form.get("role") or "").strip().lower()
        if role == "farmer":
            full_name = request.form.get("full_name", "")
            phone = request.form.get("phone", "")
            AuthService.send_otp(phone)
            user, created = AuthService.farmer_login_or_register(full_name=full_name, phone=phone)
            login_user(user)
            if created:
                flash("Welcome to UzhavanGo 🚜", "success")
            else:
                flash(f"Welcome back, {user.full_name}", "success")
            return redirect(url_for("web_dashboard.dashboard"))

        user = AuthService.authenticate_user(
            email=request.form.get("email", ""),
            password=request.form.get("password", ""),
        )
        if role == "owner" and user.role == "farmer":
            raise AppError("Use Farmer login with name and phone.", 400)
        login_user(user)
        flash("Welcome back.", "success")
        return redirect(url_for("web_dashboard.dashboard"))
    except AppError as exc:
        flash(exc.message, "error")
        return redirect(url_for("web_auth.login"))


@web_auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("web_auth.landing"))


@web_auth_bp.get("/terms")
def terms_page():
    return render_template("terms.html")


@web_auth_bp.get("/privacy")
def privacy_page():
    return render_template("privacy.html")


@web_auth_bp.get("/refund")
def refund_page():
    return render_template("refund.html")


def db_value(expr, where_clause=None):
    query = User.query.session.query(expr)
    if where_clause is not None:
        query = query.filter(where_clause)
    return query.scalar()


def db_distinct_non_empty_count(column):
    return (
        User.query.session.query(func.count(func.distinct(column)))
        .filter(column.isnot(None))
        .filter(column != "")
        .scalar()
    )
