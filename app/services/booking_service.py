from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.errors import AppError
from app.extensions import db
from app.models import Booking, BookingAddon, OwnerEarning, Payment, Tractor
from app.services.notification_service import NotificationService
from app.services.platform_service import PlatformService

BOOKING_TRANSITIONS = {
    "pending": {"accepted", "cancelled"},
    "accepted": {"en_route", "cancelled"},
    "en_route": {"working", "cancelled"},
    "working": {"completed", "cancelled"},
    "completed": {"paid"},
    "paid": set(),
    "cancelled": set(),
    # Backward compatibility for older lifecycle values.
    "requested": {"accepted", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "rejected": set(),
}


class BookingService:
    @staticmethod
    def _status_label(status):
        return (status or "").replace("_", " ").title()

    @staticmethod
    def _generate_receipt_number():
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"UZG-{today}-"
        count_today = Payment.query.filter(Payment.receipt_number.like(f"{prefix}%")).count() + 1
        return f"{prefix}{count_today:04d}"

    @staticmethod
    def _create_payment_for_booking(booking):
        if booking.payment:
            return booking.payment

        payment = Payment(
            booking_id=booking.id,
            receipt_number=BookingService._generate_receipt_number(),
            amount=booking.total_amount,
            farmer_id=booking.farmer_id,
            owner_id=booking.tractor.owner_id,
            payment_status="paid",
        )
        booking.status = "paid"
        booking.paid_at = datetime.now(timezone.utc)

        fee = Decimal(str(booking.commission_amount or 0))
        net = Decimal(str(booking.total_amount)) - fee
        if not OwnerEarning.query.filter_by(booking_id=booking.id).first():
            earning = OwnerEarning(
                owner_id=booking.tractor.owner_id,
                booking_id=booking.id,
                gross_amount=booking.total_amount,
                platform_fee=fee,
                net_amount=net,
            )
            db.session.add(earning)
        db.session.add(payment)
        return payment

    @staticmethod
    def _has_conflict(tractor_id, start_dt, end_dt):
        active_statuses = {"pending", "accepted", "en_route", "working", "completed", "paid"}
        return (
            Booking.query.filter(Booking.tractor_id == tractor_id)
            .filter(Booking.status.in_(active_statuses))
            .filter(Booking.start_time < end_dt, Booking.end_time > start_dt)
            .first()
            is not None
        )

    @staticmethod
    def create_booking(
        farmer_id,
        tractor_id,
        hours,
        start_time=None,
        farmer_note=None,
        addon_quantities=None,
    ):
        tractor = Tractor.query.get(tractor_id)
        if not tractor or tractor.availability_status == "offline" or (tractor.equipment_type or "Tractor") != "Tractor":
            raise AppError("Tractor unavailable.", 409)

        try:
            hours_int = int(hours)
            if hours_int <= 0:
                raise ValueError
        except Exception as exc:
            raise AppError("Hours must be a positive integer.", 400) from exc

        start_dt = start_time or datetime.now(timezone.utc)
        end_dt = start_dt + timedelta(hours=hours_int)
        if end_dt <= start_dt:
            raise AppError("Invalid booking duration.", 400)

        if BookingService._has_conflict(tractor.id, start_dt, end_dt):
            raise AppError("Tractor already booked for the selected time slot.", 409)

        price = Decimal(str(tractor.price_per_hour or 0))
        surge_multiplier = BookingService._surge_multiplier_for_pincode(tractor.pincode)
        price = (price * surge_multiplier).quantize(Decimal("0.01"))
        base_total = (price * Decimal(hours_int)).quantize(Decimal("0.01"))
        addon_total = Decimal("0.00")
        addon_rows = []
        parsed_addons = addon_quantities or {}
        if parsed_addons:
            addon_ids = [int(k) for k in parsed_addons.keys() if str(k).isdigit()]
            if addon_ids:
                addon_listings = (
                    Tractor.query.filter(Tractor.id.in_(addon_ids))
                    .filter(Tractor.owner_id == tractor.owner_id)
                    .filter(Tractor.availability_status != "offline")
                    .filter(Tractor.equipment_type != "Tractor")
                    .all()
                )
                addon_by_id = {row.id: row for row in addon_listings}
                for raw_id, raw_qty in parsed_addons.items():
                    if not str(raw_id).isdigit():
                        continue
                    addon_id = int(raw_id)
                    addon = addon_by_id.get(addon_id)
                    if not addon:
                        continue
                    try:
                        qty = int(raw_qty)
                    except Exception:
                        qty = 0
                    if qty <= 0:
                        continue
                    row_total = (Decimal(str(addon.price_per_hour)) * Decimal(hours_int) * Decimal(qty)).quantize(
                        Decimal("0.01")
                    )
                    addon_total += row_total
                    addon_rows.append((addon_id, qty, row_total))

        total = (base_total + addon_total).quantize(Decimal("0.01"))
        commission_pct = PlatformService.get_decimal("commission_pct", Decimal("10"))
        commission_amount = (total * (commission_pct / Decimal("100"))).quantize(Decimal("0.01"))
        owner_payout = total - commission_amount

        booking = Booking(
            tractor_id=tractor.id,
            farmer_id=farmer_id,
            owner_id=tractor.owner_id,
            hours=hours_int,
            start_time=start_dt,
            end_time=end_dt,
            quoted_price_per_hour=price,
            total_amount=total,
            status="pending",
            farmer_note=(farmer_note or "").strip() or None,
            surge_multiplier=surge_multiplier,
            commission_pct=commission_pct,
            commission_amount=commission_amount,
            owner_payout_amount=owner_payout,
            total_base_price=base_total,
            total_addon_price=addon_total,
            grand_total=total,
        )
        db.session.add(booking)
        db.session.flush()
        for addon_id, qty, row_total in addon_rows:
            db.session.add(
                BookingAddon(
                    booking_id=booking.id,
                    addon_tractor_id=addon_id,
                    quantity=qty,
                    total_price=row_total,
                )
            )

        NotificationService.push(
            user_id=tractor.owner_id,
            title="New booking request",
            message=f"You received a booking request for {tractor.title}.",
        )
        if surge_multiplier > Decimal("1.00"):
            NotificationService.push(
                user_id=farmer_id,
                title="Surge pricing alert",
                message=f"High demand in {tractor.pincode}. Surge {surge_multiplier}x applied.",
            )

        db.session.commit()
        return booking

    @staticmethod
    def _surge_multiplier_for_pincode(pincode):
        threshold = int(PlatformService.get_decimal("surge_threshold", Decimal("5")))
        booking_count = (
            Booking.query.join(Tractor, Tractor.id == Booking.tractor_id)
            .filter(Tractor.pincode == pincode)
            .filter(Booking.status.in_(["pending", "accepted", "en_route", "working"]))
            .count()
        )
        return Decimal("1.10") if booking_count > threshold else Decimal("1.00")

    @staticmethod
    def transition_booking(booking, new_status, actor_user):
        current = (booking.status or "").lower()
        new_status = (new_status or "").strip().lower()
        if new_status == "rejected":
            new_status = "cancelled"
        if current == "requested":
            current = "pending"
        if current == "in_progress":
            current = "working"

        if new_status not in BOOKING_TRANSITIONS.get(current, set()):
            raise AppError(f"Invalid status transition from {current} to {new_status}.", 400)

        booking.status = new_status
        now = datetime.now(timezone.utc)

        if new_status == "accepted":
            booking.accepted_at = now
            NotificationService.push(
                booking.farmer_id,
                "Booking accepted",
                f"Your booking for {booking.tractor.title} was accepted.",
            )
        elif new_status == "cancelled":
            booking.cancelled_at = now
            NotificationService.push(
                booking.farmer_id,
                "Booking cancelled",
                f"Your booking for {booking.tractor.title} was cancelled.",
            )
        elif new_status == "en_route":
            booking.en_route_at = now
            NotificationService.push(
                booking.farmer_id,
                "Tractor en route",
                f"The owner marked booking #{booking.id} as en route.",
            )
        elif new_status == "working":
            booking.started_at = now
            NotificationService.push(
                booking.farmer_id,
                "Work started",
                f"Work has started for booking #{booking.id}.",
            )
        elif new_status == "completed":
            booking.completed_at = now
            NotificationService.push(
                booking.farmer_id,
                "Work completed by owner",
                "Please confirm completion and actual hours to finalize payment.",
            )
        elif new_status == "paid":
            payment = BookingService._create_payment_for_booking(booking)
            NotificationService.push(
                booking.farmer_id,
                "Payment successful",
                f"Payment completed. Receipt #{payment.receipt_number}.",
            )
            NotificationService.push(
                booking.tractor.owner_id,
                "Payment received",
                f"Payment completed for booking #{booking.id}. Receipt #{payment.receipt_number}.",
            )

        db.session.commit()
        return booking

    @staticmethod
    def farmer_confirm_completion(booking, farmer_id, confirmed_hours):
        if booking.farmer_id != farmer_id:
            raise AppError("Not authorized for this booking.", 403)
        if booking.status != "completed":
            raise AppError("Booking is not waiting for completion confirmation.", 400)
        try:
            hours_int = int(confirmed_hours)
            if hours_int <= 0:
                raise ValueError
        except Exception as exc:
            raise AppError("Confirmed hours must be positive.", 400) from exc

        booking.completion_confirmed_hours = hours_int
        booking.farmer_confirmed_at = datetime.now(timezone.utc)
        payment = BookingService._create_payment_for_booking(booking)
        NotificationService.push(
            booking.owner_id,
            "Farmer confirmed completion",
            f"Booking #{booking.id} has been finalized and paid.",
        )
        db.session.commit()
        return payment
