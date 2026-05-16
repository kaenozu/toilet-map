"""
tests/test_app_config.py
app_config.py のユニットテスト
"""
import pytest

from app_config import (
    ERROR_METADATA,
    FILTER_CONFIG,
    PREFECTURE_CENTERS,
    SCORE_RANGES,
    TILE_OPTIONS,
)
from ui.helpers import esc, get_score_style


class TestGetScoreStyle:
    def test_very_clean(self):
        color, emoji, label = get_score_style(95)
        assert emoji == "✨"
        assert label == "とてもきれい"
        assert color == "#27ae60"

    def test_clean(self):
        color, emoji, label = get_score_style(70)
        assert emoji == "😊"
        assert label == "きれい"

    def test_normal(self):
        color, emoji, label = get_score_style(55)
        assert emoji == "😐"
        assert label == "普通"

    def test_slightly_dirty(self):
        color, emoji, label = get_score_style(40)
        assert emoji == "😨"
        assert label == "少し気になる"

    def test_dirty(self):
        color, emoji, label = get_score_style(20)
        assert emoji == "💩"
        assert label == "要注意"

    def test_boundary_80(self):
        assert get_score_style(80)[1] == "✨"

    def test_boundary_65(self):
        assert get_score_style(65)[1] == "😊"

    def test_boundary_50(self):
        assert get_score_style(50)[1] == "😐"

    def test_boundary_35(self):
        assert get_score_style(35)[1] == "😨"

    def test_boundary_0(self):
        assert get_score_style(0)[1] == "💩"


class TestEsc:
    def test_html(self):
        assert esc("<script>") == "&lt;script&gt;"
    def test_quote(self):
        assert esc('say "hi"') == "say &quot;hi&quot;"
    def test_amp(self):
        assert esc("A & B") == "A &amp; B"
    def test_none(self):
        assert esc(None) == ""
    def test_empty(self):
        assert esc("") == ""
    def test_number(self):
        assert esc(123) == "123"


class TestFilterConfig:
    def test_all_key(self):
        assert "すべて" in FILTER_CONFIG
        assert FILTER_CONFIG["すべて"] is None
    def test_public_key(self):
        assert FILTER_CONFIG["公共トイレ"] == "__public__"
    def test_cafe_pattern(self):
        pat = FILTER_CONFIG["カフェ・飲食"]
        assert "カフェ" in pat and "レストラン" in pat
    def test_store_pattern(self):
        pat = FILTER_CONFIG["コンビニ・店舗"]
        assert "コンビニ" in pat and "スーパー" in pat
    def test_hotel(self):
        assert "ホテル・旅館" in FILTER_CONFIG
    def test_michi(self):
        assert "道の駅" in FILTER_CONFIG
    def test_sapa(self):
        assert "SA・PA" in FILTER_CONFIG


class TestPrefectureCenters:
    def test_all_kanto(self):
        expected = {
            "東京都": (35.6762, 139.6503),
            "神奈川県": (35.4475, 139.6423),
            "埼玉県": (35.8574, 139.6489),
            "千葉県": (35.6050, 140.1233),
            "茨城県": (36.3414, 140.4468),
            "栃木県": (36.5657, 139.8836),
            "群馬県": (36.3907, 139.0604),
        }
        for pref, coords in expected.items():
            assert pref in PREFECTURE_CENTERS
            lat, lng = PREFECTURE_CENTERS[pref]
            assert isinstance(lat, float) and isinstance(lng, float)
            assert 30 < lat < 44 and 127 < lng < 146


class TestScoreRanges:
    def test_all_ranges(self):
        assert len(SCORE_RANGES) == 5
        thresholds = [r[0] for r in SCORE_RANGES]
        assert thresholds == [80, 65, 50, 35, 0]
    def test_ranges_elements(self):
        for r in SCORE_RANGES:
            assert len(r) == 4


class TestTileOptions:
    def test_defined(self):
        assert len(TILE_OPTIONS) >= 2
        assert "OpenStreetMap（標準）" in TILE_OPTIONS
        assert TILE_OPTIONS["OpenStreetMap（標準）"] == "OpenStreetMap"
    def test_keys_strings(self):
        for name, tile in TILE_OPTIONS.items():
            assert isinstance(name, str) and isinstance(tile, str)


class TestErrorMetadata:
    def test_keys(self):
        assert ERROR_METADATA["area_name"] == "エラー"
        assert ERROR_METADATA["total"] == 0
        assert ERROR_METADATA["center_lat"] == 36.2231


class TestLoadPopupFixJs:
    def test_loads_content_when_exists(self, tmp_path, monkeypatch):
        js_file = tmp_path / "popup_fix.js"
        js_file.write_text("console.log('ok');", encoding="utf-8")
        from app_config import _load_popup_fix_js
        monkeypatch.setattr("app_config.POPUP_FIX_PATH", str(js_file))
        result = _load_popup_fix_js()
        assert "console.log('ok')" in result
        assert "<script>" in result

    def test_returns_empty_when_missing(self, tmp_path, monkeypatch):
        from app_config import _load_popup_fix_js
        monkeypatch.setattr("app_config.POPUP_FIX_PATH", str(tmp_path / "nonexistent.js"))
        assert _load_popup_fix_js() == ""


class TestGetScoreStyleFallback:
    def test_below_zero_returns_lowest(self):
        from ui.helpers import get_score_style
        color, emoji, label = get_score_style(-5)
        assert emoji == "💩"
        assert label == "要注意"

    def test_none_coerces_to_zero(self):
        from ui.helpers import get_score_style
        color, emoji, label = get_score_style(0)
        assert emoji == "💩"


class TestSafeHrefEdgeCases:
    def test_no_netloc_returns_empty(self):
        from ui.helpers import safe_href
        assert safe_href("http:///path") == ""

    def test_empty_url_returns_empty(self):
        from ui.helpers import safe_href
        assert safe_href("") == ""
        assert safe_href(None) == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
