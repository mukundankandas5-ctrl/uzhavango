from kivy.animation import Animation
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager


def register_brand_font():
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ]
    for path in font_candidates:
        try:
            LabelBase.register(name="BrandSerif", fn_regular=path)
            return
        except Exception:
            continue


class StarRow(Widget):
    rating = NumericProperty(0)

    def set_rating(self, value):
        self.rating = value
        for i in range(1, 6):
            star = self.ids.get(f"star_{i}")
            if not star:
                continue
            star.icon = "star" if i <= value else "star-outline"
            star.theme_text_color = "Custom"
            star.text_color = (0.89, 0.68, 0.17, 1) if i <= value else (0.58, 0.62, 0.67, 1)
            if i == value:
                Animation.cancel_all(star, "scale")
                anim = Animation(scale=1.2, d=0.1) + Animation(scale=1.0, d=0.12)
                anim.start(star)


class LoginScreen(MDScreen):
    pass


class DashboardScreen(MDScreen):
    avg_rating = StringProperty("4.6")


class ReceiptScreen(MDScreen):
    receipt_no = StringProperty("UZG-20260218-0001")


class UzhavanGoMobile(MDApp):
    def build(self):
        register_brand_font()
        Builder.load_file("mobile/uzhavango.kv")
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Green"
        sm = MDScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(ReceiptScreen(name="receipt"))
        return sm


if __name__ == "__main__":
    UzhavanGoMobile().run()
