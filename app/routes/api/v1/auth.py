from flask import Blueprint, jsonify, request
from flask_login import login_required, login_user, logout_user

from app.services import AuthService

api_auth_bp = Blueprint("api_auth", __name__)


@api_auth_bp.post("/register")
def api_register():
    payload = request.get_json(silent=True) or {}
    user = AuthService.register_user(
        full_name=payload.get("full_name", ""),
        email=payload.get("email", ""),
        password=payload.get("password", ""),
        role=payload.get("role", ""),
        phone=payload.get("phone", ""),
    )
    login_user(user)
    return jsonify({"id": user.id, "email": user.email, "role": user.role}), 201


@api_auth_bp.post("/login")
def api_login():
    payload = request.get_json(silent=True) or {}
    user = AuthService.authenticate_user(payload.get("email", ""), payload.get("password", ""))
    login_user(user)
    return jsonify({"id": user.id, "email": user.email, "role": user.role})


@api_auth_bp.post("/logout")
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})
