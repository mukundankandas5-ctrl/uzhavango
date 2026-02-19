from flask import Blueprint

from app.extensions import csrf
from app.routes.api.v1.auth import api_auth_bp
from app.routes.api.v1.bookings import api_booking_bp
from app.routes.api.v1.notifications import api_notification_bp
from app.routes.api.v1.reviews import api_review_bp
from app.routes.api.v1.tractors import api_tractor_bp

api_v1_bp = Blueprint("api_v1", __name__)
api_v1_bp.register_blueprint(api_auth_bp, url_prefix="/auth")
api_v1_bp.register_blueprint(api_tractor_bp, url_prefix="/tractors")
api_v1_bp.register_blueprint(api_booking_bp, url_prefix="/bookings")
api_v1_bp.register_blueprint(api_review_bp, url_prefix="/reviews")
api_v1_bp.register_blueprint(api_notification_bp, url_prefix="/notifications")

csrf.exempt(api_v1_bp)
