from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*roles):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return func(*args, **kwargs)

        return inner

    return wrapper
