from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.decorators import role_required
from app.services import ReviewService

api_review_bp = Blueprint("api_review", __name__)


@api_review_bp.post("")
@login_required
@role_required("farmer")
def add_review():
    payload = request.get_json(silent=True) or {}
    review = ReviewService.upsert_review(
        tractor_id=payload.get("tractor_id"),
        farmer_id=current_user.id,
        rating=payload.get("rating"),
        comment=payload.get("comment"),
    )
    return jsonify({"id": review.id, "rating": review.rating})
