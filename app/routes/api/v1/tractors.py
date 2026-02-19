from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.decorators import role_required
from app.services import FileService, TractorService

api_tractor_bp = Blueprint("api_tractor", __name__)


@api_tractor_bp.get("")
def list_tractors():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=12, type=int)
    paginated = TractorService.list_tractors(page=page, per_page=min(per_page, 50), only_available=True)

    return jsonify(
        {
            "items": [
                {
                    "id": t.id,
                    "title": t.title,
                    "price_per_hour": str(t.price_per_hour),
                    "owner_name": t.owner.full_name,
                    "location_label": t.location_label,
                    "is_available": t.is_available,
                    "rating_avg": float(t.rating_avg),
                    "average_rating": float(t.average_rating),
                    "rating_count": t.rating_count,
                    "image_path": t.image_path,
                }
                for t in paginated.items
            ],
            "meta": {
                "page": paginated.page,
                "pages": paginated.pages,
                "total": paginated.total,
                "has_next": paginated.has_next,
                "has_prev": paginated.has_prev,
            },
        }
    )


@api_tractor_bp.post("")
@login_required
@role_required("owner")
def create_tractor():
    payload = dict(request.form)
    image = request.files.get("tractor_image")
    if image:
        payload["image_path"] = FileService.save_image(image, current_app.config["UPLOAD_DIR"])
    tractor = TractorService.create_tractor(current_user.id, payload)
    return jsonify({"id": tractor.id, "title": tractor.title}), 201


@api_tractor_bp.patch("/<int:tractor_id>/availability")
@login_required
@role_required("owner")
def toggle_availability(tractor_id):
    payload = request.get_json(silent=True) or {}
    tractor = TractorService.toggle_availability(
        tractor_id=tractor_id,
        owner_id=current_user.id,
        is_available=payload.get("is_available", True),
    )
    return jsonify({"id": tractor.id, "is_available": tractor.is_available})
