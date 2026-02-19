from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func

from app.decorators import role_required
from app.models import Booking, Payment, Review, Tractor, User
from app.services import PlatformService

web_admin_bp = Blueprint("web_admin", __name__)


@web_admin_bp.get("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    total_users = User.query.count()
    total_tractors = Tractor.query.count()
    total_bookings = Booking.query.count()
    total_revenue = float(db_scalar(func.coalesce(func.sum(Payment.amount), 0)))
    avg_rating = float(db_scalar(func.coalesce(func.avg(Tractor.average_rating), 0)))
    commission_total = float(db_scalar(func.coalesce(func.sum(Booking.commission_amount), 0)))
    owner_payout_total = float(db_scalar(func.coalesce(func.sum(Booking.owner_payout_amount), 0)))

    top_tractors = (
        db_rows(
            Booking.query.with_entities(
                Tractor.title.label("tractor_title"),
                func.count(Booking.id).label("booking_count"),
            )
            .join(Tractor, Tractor.id == Booking.tractor_id)
            .group_by(Tractor.id)
            .order_by(func.count(Booking.id).desc())
            .limit(5)
        )
    )

    recent_transactions = (
        Payment.query.order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )

    demand_by_district = db_rows(
        db_session_query(
            Tractor.district.label("district"),
            func.count(Booking.id).label("bookings"),
        )
        .join(Booking, Booking.tractor_id == Tractor.id)
        .filter(Tractor.district.isnot(None))
        .filter(Tractor.district != "")
        .group_by(Tractor.district)
        .order_by(func.count(Booking.id).desc())
        .limit(12)
    )
    supply_by_district = db_rows(
        db_session_query(
            Tractor.district.label("district"),
            func.count(Tractor.id).label("supply"),
        )
        .filter(Tractor.district.isnot(None))
        .filter(Tractor.district != "")
        .group_by(Tractor.district)
        .order_by(func.count(Tractor.id).asc())
        .limit(12)
    )

    fraud_alerts = build_fraud_alerts()
    owners = User.query.filter_by(role="owner").order_by(User.created_at.desc()).limit(30).all()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_tractors=total_tractors,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        commission_total=commission_total,
        owner_payout_total=owner_payout_total,
        avg_rating=avg_rating,
        top_tractors=top_tractors,
        recent_transactions=recent_transactions,
        demand_by_district=demand_by_district,
        supply_by_district=supply_by_district,
        fraud_alerts=fraud_alerts,
        owners=owners,
        commission_pct=float(PlatformService.get_decimal("commission_pct", 10)),
        surge_threshold=int(PlatformService.get_decimal("surge_threshold", 5)),
    )


@web_admin_bp.get("/admin/analytics")
@login_required
@role_required("admin")
def analytics_dashboard():
    daily = db_rows(
        Payment.query.with_entities(
            func.date(Payment.created_at).label("period"),
            func.sum(Payment.amount).label("revenue"),
        )
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
        .limit(30)
    )

    weekly = db_rows(
        Payment.query.with_entities(
            func.strftime("%Y-W%W", Payment.created_at).label("period"),
            func.sum(Payment.amount).label("revenue"),
        )
        .group_by(func.strftime("%Y-W%W", Payment.created_at))
        .order_by(func.strftime("%Y-W%W", Payment.created_at))
        .limit(12)
    )

    monthly = db_rows(
        Payment.query.with_entities(
            func.strftime("%Y-%m", Payment.created_at).label("period"),
            func.sum(Payment.amount).label("revenue"),
        )
        .group_by(func.strftime("%Y-%m", Payment.created_at))
        .order_by(func.strftime("%Y-%m", Payment.created_at))
        .limit(12)
    )

    by_tractor = db_rows(
        Payment.query.with_entities(
            Tractor.title.label("name"),
            func.sum(Payment.amount).label("revenue"),
        )
        .join(Booking, Booking.id == Payment.booking_id)
        .join(Tractor, Tractor.id == Booking.tractor_id)
        .group_by(Tractor.id)
        .order_by(func.sum(Payment.amount).desc())
        .limit(10)
    )

    by_owner = db_rows(
        Payment.query.with_entities(
            User.full_name.label("name"),
            func.sum(Payment.amount).label("revenue"),
        )
        .join(User, User.id == Payment.owner_id)
        .group_by(User.id)
        .order_by(func.sum(Payment.amount).desc())
        .limit(10)
    )

    growth = db_rows(
        Booking.query.with_entities(
            func.date(Booking.created_at).label("period"),
            func.count(Booking.id).label("bookings"),
        )
        .group_by(func.date(Booking.created_at))
        .order_by(func.date(Booking.created_at))
        .limit(30)
    )

    return render_template(
        "analytics.html",
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        by_tractor=by_tractor,
        by_owner=by_owner,
        growth=growth,
    )


@web_admin_bp.get("/admin/analytics/data")
@login_required
@role_required("admin")
def analytics_data():
    rows = db_rows(
        Payment.query.with_entities(
            func.date(Payment.created_at).label("period"),
            func.sum(Payment.amount).label("revenue"),
        )
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
        .limit(60)
    )
    return jsonify(rows)


@web_admin_bp.post("/admin/settings")
@login_required
@role_required("admin")
def update_platform_settings():
    commission_pct = request.form.get("commission_pct", type=float)
    surge_threshold = request.form.get("surge_threshold", type=int)
    if commission_pct is None or commission_pct < 0 or commission_pct > 100:
        flash("Commission must be between 0 and 100.", "error")
        return redirect(url_for("web_admin.admin_dashboard"))
    if surge_threshold is None or surge_threshold < 1:
        flash("Surge threshold must be at least 1.", "error")
        return redirect(url_for("web_admin.admin_dashboard"))
    PlatformService.set_setting("commission_pct", commission_pct)
    PlatformService.set_setting("surge_threshold", surge_threshold)
    flash("Platform settings updated.", "success")
    return redirect(url_for("web_admin.admin_dashboard"))


@web_admin_bp.post("/admin/owners/<int:owner_id>/verify")
@login_required
@role_required("admin")
def verify_owner(owner_id):
    owner = User.query.filter_by(id=owner_id, role="owner").first_or_404()
    owner.is_verified_owner = request.form.get("is_verified_owner") == "true"
    from app.extensions import db

    db.session.commit()
    flash("Owner verification updated.", "success")
    return redirect(url_for("web_admin.admin_dashboard"))


def db_scalar(expr):
    from app.extensions import db

    value = db.session.query(expr).scalar()
    return value or 0


def db_rows(query):
    return [dict(row._mapping) for row in query.all()]


def db_session_query(*cols):
    from app.extensions import db

    return db.session.query(*cols)


def build_fraud_alerts():
    alerts = []
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    farmers = db_session_query(
        User.id.label("user_id"),
        User.full_name.label("name"),
        func.count(Booking.id).label("cancel_count"),
    ).join(Booking, Booking.farmer_id == User.id).filter(
        User.role == "farmer",
        Booking.status == "cancelled",
        Booking.updated_at >= seven_days_ago,
    ).group_by(User.id).having(func.count(Booking.id) > 5).all()
    for row in farmers:
        alerts.append(f"Farmer {row.name} has {int(row.cancel_count)} cancellations in 7 days.")

    owners = db_session_query(
        User.id.label("user_id"),
        User.full_name.label("name"),
        func.sum(case((Booking.status == "cancelled", 1), else_=0)).label("rejections"),
        func.count(Booking.id).label("total"),
    ).join(Booking, Booking.owner_id == User.id).filter(User.role == "owner").group_by(User.id).all()
    for row in owners:
        total = int(row.total or 0)
        rejects = int(row.rejections or 0)
        if total >= 5 and rejects / total > 0.8:
            alerts.append(f"Owner {row.name} has rejection/cancellation ratio above 80%.")

    suspicious_reviews = db_session_query(
        Review.farmer_id.label("farmer_id"),
        func.count(Review.id).label("count_reviews"),
    ).group_by(Review.farmer_id).having(func.count(Review.id) >= 10).all()
    for row in suspicious_reviews:
        alerts.append(f"Farmer ID {row.farmer_id} posted unusually high review volume ({int(row.count_reviews)}).")

    return alerts
