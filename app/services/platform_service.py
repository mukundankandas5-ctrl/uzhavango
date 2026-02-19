from decimal import Decimal

from app.extensions import db
from app.models import PlatformSetting


class PlatformService:
    @staticmethod
    def get_setting(key, default=None):
        setting = PlatformSetting.query.filter_by(key=key).first()
        if not setting:
            return default
        return setting.value

    @staticmethod
    def get_decimal(key, default):
        raw = PlatformService.get_setting(key, str(default))
        try:
            return Decimal(str(raw))
        except Exception:
            return Decimal(str(default))

    @staticmethod
    def set_setting(key, value):
        setting = PlatformSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = PlatformSetting(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
        return setting

