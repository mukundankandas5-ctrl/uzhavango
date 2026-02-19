from app.errors import AppError
from app.extensions import bcrypt, db
from app.models import User
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from werkzeug.security import check_password_hash as check_werkzeug_password_hash
import re
import secrets


class AuthService:
    @staticmethod
    def _normalize_phone(phone):
        digits = "".join(ch for ch in (phone or "") if ch.isdigit())
        if not re.fullmatch(r"\d{10}", digits):
            raise AppError("Phone number must be exactly 10 digits.", 400)
        return digits

    @staticmethod
    def send_otp(phone):
        # Placeholder for future OTP integration.
        # Intentionally no SMS side effects in current release.
        _ = phone
        return True

    @staticmethod
    def register_user(full_name, email, password, role, phone):
        if role not in {"farmer", "owner"}:
            raise AppError("Invalid role.", 400)

        normalized_email = (email or "").strip().lower()
        normalized_phone = AuthService._normalize_phone(phone)
        if not full_name or not normalized_email or not password or not normalized_phone:
            raise AppError("Name, email, phone, and password are required.", 400)

        existing = User.query.filter_by(email=normalized_email).first()
        if existing:
            raise AppError("Email already registered.", 409)
        if role == "farmer":
            existing_farmer_phone = (
                User.query.filter(func.lower(User.role) == "farmer", User.phone == normalized_phone).first()
            )
            if existing_farmer_phone:
                raise AppError("Phone number already registered as farmer.", 409)

        user = User(
            full_name=full_name.strip(),
            email=normalized_email,
            phone=normalized_phone,
            role=role,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            message = str(getattr(exc, "orig", exc)).lower()
            if "users.email" in message or "unique constraint failed: users.email" in message:
                raise AppError("Email already registered.", 409) from exc
            raise AppError("Could not create account due to invalid data.", 400) from exc
        return user

    @staticmethod
    def farmer_login_or_register(full_name, phone):
        normalized_name = (full_name or "").strip()
        normalized_phone = AuthService._normalize_phone(phone)
        if not normalized_name:
            raise AppError("Full name is required.", 400)

        user = User.query.filter(func.lower(User.role) == "farmer", User.phone == normalized_phone).first()
        created = False
        if user:
            user.full_name = normalized_name
        else:
            local = f"farmer.{normalized_phone}"
            domain = "instant.uzhavango.local"
            candidate_email = f"{local}@{domain}"
            while User.query.filter_by(email=candidate_email).first():
                candidate_email = f"{local}.{secrets.token_hex(2)}@{domain}"

            user = User(
                full_name=normalized_name,
                email=candidate_email,
                phone=normalized_phone,
                role="farmer",
                password_hash=bcrypt.generate_password_hash(secrets.token_urlsafe(24)).decode("utf-8"),
            )
            db.session.add(user)
            created = True

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        return user, created

    @staticmethod
    def authenticate_user(email, password):
        user = User.query.filter_by(email=(email or "").strip().lower()).first()
        if not user:
            raise AppError("Invalid credentials.", 401)

        plain_password = password or ""
        is_valid = False

        # Primary verifier for the production hash format.
        try:
            is_valid = bcrypt.check_password_hash(user.password_hash, plain_password)
        except ValueError:
            is_valid = False

        # Backward compatibility with legacy MVP hashes (Werkzeug).
        if not is_valid:
            try:
                is_valid = check_werkzeug_password_hash(user.password_hash, plain_password)
                if is_valid:
                    user.password_hash = bcrypt.generate_password_hash(plain_password).decode("utf-8")
                    db.session.commit()
            except Exception:
                is_valid = False

        if not is_valid:
            raise AppError("Invalid credentials.", 401)
        if not user.is_active_user:
            raise AppError("User account is inactive.", 403)
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        return user
