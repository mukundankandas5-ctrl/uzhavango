from io import BytesIO

from flask import Blueprint, Response, render_template, request
from flask_login import current_user, login_required

from app.models import Payment

web_receipt_bp = Blueprint("web_receipt", __name__)


@web_receipt_bp.get("/receipt/<receipt_number>")
@login_required
def receipt_page(receipt_number):
    payment = (
        Payment.query.filter_by(receipt_number=receipt_number)
        .join(Payment.booking)
        .first_or_404()
    )

    booking = payment.booking
    tractor = booking.tractor
    owner = tractor.owner
    farmer = booking.farmer

    if current_user.role not in {"admin"} and current_user.id not in {payment.farmer_id, payment.owner_id}:
        return render_template("error.html", message="Forbidden"), 403

    pdf_error = None
    if request.args.get("format") == "pdf":
        try:
            return _pdf_receipt_response(payment, booking, tractor, owner.full_name, farmer.full_name)
        except ModuleNotFoundError:
            pdf_error = "PDF export is unavailable: install reportlab in your environment."

    return render_template(
        "receipt.html",
        payment=payment,
        booking=booking,
        tractor=tractor,
        owner_name=owner.full_name,
        farmer_name=farmer.full_name,
        pdf_error=pdf_error,
    )


def _pdf_receipt_response(payment, booking, tractor, owner_name, farmer_name):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 60
    p.setFont("Helvetica-Bold", 22)
    p.drawString(50, y, "UzhavanGo Receipt")

    y -= 36
    p.setFont("Helvetica", 12)
    lines = [
        f"Receipt: {payment.receipt_number}",
        f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"Tractor: {tractor.title}",
        f"Farmer: {farmer_name}",
        f"Owner: {owner_name}",
        f"Hours: {booking.hours}",
        f"Rate/Hour: INR {booking.quoted_price_per_hour}",
        f"Total: INR {payment.amount}",
        f"Status: {payment.payment_status.title()}",
    ]

    for line in lines:
        p.drawString(50, y, line)
        y -= 24

    p.showPage()
    p.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={payment.receipt_number}.pdf"},
    )
