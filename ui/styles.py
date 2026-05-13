"""
ui/styles.py
Mobile CSS styles for Streamlit app
Loads from static/mobile.css
"""
import os

_STYLES_DIR = os.path.dirname(os.path.abspath(__file__))
_MOBILE_CSS_PATH = os.path.join(_STYLES_DIR, "..", "static", "mobile.css")


def _load_mobile_css() -> str:
    try:
        with open(_MOBILE_CSS_PATH, "r", encoding="utf-8") as f:
            return "<style>\n" + f.read() + "\n</style>"
    except FileNotFoundError:
        return ""


MOBILE_CSS = _load_mobile_css()
