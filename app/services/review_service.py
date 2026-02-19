from decimal import Decimal

from sqlalchemy import func

from app.errors import AppError
from app.extensions import db
from app.models import Booking, Review, Tractor


class ReviewService:
    @staticmethod
    def upsert_review(tractor_id, farmer_id, rating, comment):
        try:
            rating_int = int(rating)
        except Exception as exc:
            raise AppError("Rating must be an integer between 1 and 5.", 400) from exc

        if rating_int < 1 or rating_int > 5:
            raise AppError("Rating must be an integer between 1 and 5.", 400)

        tractor = Tractor.query.get(tractor_id)
        if not tractor:
            raise AppError("Tractor not found.", 404)

        eligible_booking = (
            Booking.query.filter_by(tractor_id=tractor_id, farmer_id=farmer_id)
            .filter(Booking.status.in_(["completed", "paid"]))
            .filter(Booking.farmer_confirmed_at.isnot(None))
            .first()
        )
        if not eligible_booking:
            raise AppError("Review unlocks after completion confirmation.", 403)

        review = Review.query.filter_by(tractor_id=tractor_id, farmer_id=farmer_id).first()
        if review:
            review.rating = rating_int
            review.comment = (comment or "").strip() or None
        else:
            review = Review(
                tractor_id=tractor_id,
                farmer_id=farmer_id,
                rating=rating_int,
                comment=(comment or "").strip() or None,
            )
            db.session.add(review)

        # Materialized aggregate update for faster reads.
        avg_rating, rating_count = (
            db.session.query(func.avg(Review.rating), func.count(Review.id))
            .filter(Review.tractor_id == tractor_id)
            .one()
        )
        tractor.rating_avg = Decimal(str(round(float(avg_rating or 0), 2)))
        tractor.average_rating = tractor.rating_avg
        tractor.rating_count = int(rating_count or 0)

        db.session.commit()
        return review
