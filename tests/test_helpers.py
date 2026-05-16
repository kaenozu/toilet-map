"""
tests/test_helpers.py
Tests for ui/helpers.py UI helper functions

関連: ui/helpers.py, app_config.py, ui/popups.py
"""
from ui.helpers import esc, get_score_style, safe_href


class TestEsc:
    def test_none_returns_empty(self):
        assert esc(None) == ""

    def test_empty_string_returns_empty(self):
        assert esc("") == ""

    def test_escapes_html_special_chars(self):
        assert esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

    def test_escapes_quotes(self):
        assert esc('he said "hello"') == "he said &quot;hello&quot;"

    def test_plain_text_passes_through(self):
        assert esc("hello world") == "hello world"

    def test_ampersand_escaped(self):
        assert esc("a & b") == "a &amp; b"


class TestSafeHref:
    def test_none_returns_empty(self):
        assert safe_href(None) == ""

    def test_empty_returns_empty(self):
        assert safe_href("") == ""

    def test_valid_https_url(self):
        url = "https://maps.google.com/?q=35.0,139.0"
        result = safe_href(url)
        assert result.startswith("https://maps.google.com/")
        assert "&amp;" in result or "&" not in result

    def test_valid_http_url(self):
        assert safe_href("http://example.com") == "http://example.com"

    def test_javascript_url_rejected(self):
        assert safe_href("javascript:alert(1)") == ""

    def test_ftp_url_rejected(self):
        assert safe_href("ftp://example.com") == ""

    def test_url_without_netloc_rejected(self):
        assert safe_href("http://") == ""

    def test_whitespace_stripped(self):
        url = "  https://example.com  "
        result = safe_href(url)
        assert result == "https://example.com"

    def test_url_with_special_chars_escaped(self):
        url = "https://example.com/?a=1&b=2"
        result = safe_href(url)
        assert "&amp;" in result


class TestGetScoreStyle:
    def test_100_returns_green(self):
        color, emoji, label = get_score_style(100)
        assert color == "#27ae60"
        assert "とてもきれい" in label

    def test_80_returns_top_range(self):
        color, emoji, label = get_score_style(80)
        assert color == "#27ae60"

    def test_79_returns_second_range(self):
        color, emoji, label = get_score_style(79)
        assert color == "#2ecc71"

    def test_65_boundary(self):
        color, emoji, label = get_score_style(65)
        assert color == "#2ecc71"

    def test_60_returns_yellow(self):
        color, emoji, label = get_score_style(60)
        assert color == "#f1c40f"

    def test_50_boundary(self):
        color, emoji, label = get_score_style(50)
        assert color == "#f1c40f"

    def test_40_returns_orange(self):
        color, emoji, label = get_score_style(40)
        assert color == "#f39c12"

    def test_35_boundary(self):
        color, emoji, label = get_score_style(35)
        assert color == "#f39c12"

    def test_20_returns_red(self):
        color, emoji, label = get_score_style(20)
        assert color == "#e74c3c"

    def test_0_returns_red(self):
        color, emoji, label = get_score_style(0)
        assert color == "#e74c3c"

    def test_negative_returns_lowest_range(self):
        color, emoji, label = get_score_style(-5)
        assert color == "#e74c3c"
        assert label == "要注意"

    def test_exact_threshold_boundary(self):
        color80, _, _ = get_score_style(80)
        color79, _, _ = get_score_style(79)
        assert color80 != color79
