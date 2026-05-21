"""
ui/i18n.py
Simple translation system loading definitions from i18n.json.
"""
import json
import os

DEFAULT_LANGUAGE = "日本語"

# Load translation JSON file
_json_path = os.path.join(os.path.dirname(__file__), "i18n.json")
with open(_json_path, encoding="utf-8") as _f:
    LANGUAGES = json.load(_f)

LANGUAGE_CODE_TO_LABEL = {
    "ja": "日本語",
    "en": "English",
    "ko": "한국어",
    "zh": "中文",
    "fr": "Français",
    "es": "Español",
}
LANGUAGE_OPTIONS = tuple(LANGUAGES.keys())
APP_TITLE = LANGUAGES[DEFAULT_LANGUAGE]["title"]


def get_language_strings(lang: str) -> dict[str, str]:
    """Get the translation dictionary for the selected language, falling back to default."""
    return LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE])
