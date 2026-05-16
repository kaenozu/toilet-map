"""
tests/test_i18n.py
ui/i18n.py と翻訳付きテキストのテスト
"""

from ui.components import build_result_context_text
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings


def test_get_language_strings_falls_back_to_default_language():
    fallback = get_language_strings("unknown-language")
    default_strings = get_language_strings(DEFAULT_LANGUAGE)

    assert fallback["title"] == default_strings["title"]
    assert fallback["no_results"] == default_strings["no_results"]
    assert default_strings["title"] == APP_TITLE


def test_build_result_context_text_uses_translations():
    english = get_language_strings("English")

    text = build_result_context_text(12, 8, 3.0, 5.0, english)

    assert "List 12 items" in text
    assert "Map 8 items" in text
    assert "Filter 3ms" in text
