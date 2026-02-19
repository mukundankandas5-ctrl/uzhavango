from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

try:
    from flask_caching import Cache
except Exception:  # pragma: no cover - fallback for minimal local envs
    class Cache:  # type: ignore[override]
        def init_app(self, app):
            _ = app

        def cached(self, timeout=0):
            _ = timeout

            def decorator(func):
                return func

            return decorator

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:  # pragma: no cover - fallback for minimal local envs
    class Limiter:  # type: ignore[override]
        def __init__(self, key_func=None, default_limits=None):
            _ = key_func, default_limits

        def init_app(self, app, default_limits=None):
            _ = app, default_limits

        def limit(self, _rule):
            def decorator(func):
                return func

            return decorator

    def get_remote_address():  # type: ignore[override]
        return "127.0.0.1"


db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
login_manager = LoginManager()
login_manager.login_view = "web_auth.login"
login_manager.login_message_category = "error"
