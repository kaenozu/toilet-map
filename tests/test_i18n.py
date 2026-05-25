"""
tests/test_i18n.py
Internationalization tests - translation lookup, fallback, and key completeness audit.
Related: ui/i18n.py, ui/components.py
"""

from ui.components import build_result_context_text
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, LANGUAGES, get_language_strings

# --- Existing tests ---

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


# --- i18n audit tests ---

class TestI18nCompleteness:
    """All languages must have the same set of keys as the default language."""

    def _key_set(self, lang: str) -> set:
        return set(LANGUAGES[lang].keys())

    def test_all_languages_have_same_keys(self):
        ja_keys = self._key_set("日本語")
        for lang_name in LANGUAGES:
            lang_keys = self._key_set(lang_name)
            missing = ja_keys - lang_keys
            extra = lang_keys - ja_keys
            assert not missing, f"{lang_name} missing keys: {missing}"
            assert not extra, f"{lang_name} has extra keys: {extra}"

    def test_default_language_has_all_keys(self):
        keys = self._key_set(DEFAULT_LANGUAGE)
        assert "language_label" in keys
        assert "title" in keys
        assert "gps" in keys
        assert "prefecture" in keys
        assert "filter" in keys

    def test_no_empty_values_in_default(self):
        for key, value in LANGUAGES[DEFAULT_LANGUAGE].items():
            assert value and str(value).strip(), f"Key '{key}' has empty value in default language"

    def test_no_placeholder_text_in_translations(self):
        """Ensure no raw template markers like {key} leak into translations."""
        for lang_name, translations in LANGUAGES.items():
            for key, value in translations.items():
                if isinstance(value, str) and "{" in value:
                    allowed_format_keys = ["page"]
                    if key not in allowed_format_keys:
                        raise AssertionError(f"{lang_name}.{key} contains '{{' but is not in allowed_format_keys")
