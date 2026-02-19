import os
import shutil
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_by_env
from app.errors import register_error_handlers
from app.extensions import bcrypt, cache, csrf, db, limiter, login_manager, migrate
from app.models import User
from app.routes.api.v1 import api_v1_bp
from app.routes.web.admin import web_admin_bp
from app.routes.web.auth import web_auth_bp
from app.routes.web.dashboard import web_dashboard_bp
from app.routes.web.receipt import web_receipt_bp
from app.services import NotificationService


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    load_dotenv()
    env = os.getenv("FLASK_ENV", "development")

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_dir = os.path.join(project_root, "templates")
    static_dir = os.path.join(project_root, "static")

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=template_dir,
        static_folder=static_dir,
    )
    app.config.from_object(config_by_env.get(env, config_by_env["development"]))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:////") and db_uri != "sqlite:///:memory:":
        relative_path = db_uri.replace("sqlite:///", "", 1)
        absolute_path = os.path.join(project_root, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{absolute_path}"

    upload_dir = app.config["UPLOAD_DIR"]
    if not os.path.isabs(upload_dir):
        upload_dir = os.path.join(project_root, upload_dir)
    app.config["UPLOAD_DIR"] = upload_dir

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    default_limits = [item.strip() for item in str(app.config.get("RATELIMIT_DEFAULT", "")).split(";") if item.strip()]
    limiter.init_app(app, default_limits=default_limits)
    login_manager.init_app(app)
    _init_sentry(app)

    register_error_handlers(app)

    app.register_blueprint(web_auth_bp)
    app.register_blueprint(web_dashboard_bp)
    app.register_blueprint(web_receipt_bp)
    app.register_blueprint(web_admin_bp)
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    if env == "development":
        with app.app_context():
            _ensure_dev_schema(app)
            _ensure_sqlite_runtime_compat(app)
    else:
        with app.app_context():
            _ensure_sqlite_runtime_compat(app)

    @app.context_processor
    def inject_csrf_token():
        unread_count = 0
        notifications = []
        try:
            from flask_login import current_user

            if current_user.is_authenticated:
                unread_count = NotificationService.unread_count(current_user.id)
                notifications = NotificationService.latest_for_user(current_user.id, limit=8)
        except Exception:
            pass
        return {
            "csrf_token": generate_csrf,
            "global_unread_count": unread_count,
            "global_notifications": notifications,
        }

    return app


def _init_sentry(app):
    dsn = app.config.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            environment=os.getenv("FLASK_ENV", "production"),
        )
        app.logger.info("Sentry initialized.")
    except Exception as exc:
        app.logger.warning("Sentry initialization failed: %s", exc)


def _ensure_dev_schema(app):
    """
    Development convenience:
    - If legacy SQLite schema is detected (old MVP columns), backup DB and recreate.
    - Otherwise just ensure tables exist.
    """
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_file = None
    if db_uri.startswith("sqlite:////"):
        db_file = db_uri.replace("sqlite:////", "/", 1)

    if db_file and os.path.exists(db_file):
        try:
            result = db.session.execute(text("PRAGMA table_info(users)"))
            rows = result.fetchall()
            columns = {row[1] for row in rows}
            id_type = next((row[2] for row in rows if row[1] == "id"), "")
            # New schema expects full_name + updated_at.
            is_legacy_users = (
                "full_name" not in columns
                or "phone" not in columns
                or "updated_at" not in columns
                or str(id_type).upper() != "INTEGER"
            )
            tractor_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(tractors)")).fetchall()}
            booking_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(bookings)")).fetchall()}
            payment_table_exists = (
                db.session.execute(
                    text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='payments'")
                ).scalar()
                > 0
            )
            missing_new_columns = (
                "average_rating" not in tractor_columns
                or "pincode" not in tractor_columns
                or "village" not in tractor_columns
                or "district" not in tractor_columns
                or "paid_at" not in booking_columns
                or "owner_id" not in booking_columns
                or not payment_table_exists
            )

            if is_legacy_users or missing_new_columns:
                backup = f"{db_file}.legacy-backup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                shutil.copy2(db_file, backup)
                app.logger.warning("Legacy DB detected. Backed up to %s and recreating schema.", backup)
                db.drop_all()
                db.create_all()
                return
        except Exception:
            # If introspection fails, continue with best effort create_all.
            pass

    db.create_all()


def _ensure_sqlite_runtime_compat(app):
    """
    Production-safe SQLite compatibility guard.
    Adds missing columns required by newer models without destructive resets.
    """
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not db_uri.startswith("sqlite:"):
        return

    def table_exists(table_name):
        return (
            db.session.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=:name"),
                {"name": table_name},
            ).scalar()
            > 0
        )

    def column_exists(table_name, column_name):
        rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(row[1] == column_name for row in rows)

    try:
        if table_exists("users"):
            if not column_exists("users", "phone"):
                db.session.execute(text("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''"))
            if not column_exists("users", "is_verified_owner"):
                db.session.execute(text("ALTER TABLE users ADD COLUMN is_verified_owner INTEGER NOT NULL DEFAULT 0"))
            if not column_exists("users", "last_login"):
                db.session.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))

        if table_exists("tractors"):
            if not column_exists("tractors", "pincode"):
                db.session.execute(text("ALTER TABLE tractors ADD COLUMN pincode TEXT NOT NULL DEFAULT ''"))
            if not column_exists("tractors", "village"):
                db.session.execute(text("ALTER TABLE tractors ADD COLUMN village TEXT"))
            if not column_exists("tractors", "district"):
                db.session.execute(text("ALTER TABLE tractors ADD COLUMN district TEXT"))
            if not column_exists("tractors", "equipment_type"):
                db.session.execute(
                    text("ALTER TABLE tractors ADD COLUMN equipment_type TEXT NOT NULL DEFAULT 'Tractor'")
                )
            if not column_exists("tractors", "availability_status"):
                db.session.execute(
                    text("ALTER TABLE tractors ADD COLUMN availability_status TEXT NOT NULL DEFAULT 'available'")
                )

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning("SQLite runtime compatibility migration skipped: %s", exc)
