"""
tests/test_map_builder.py
ui/map_builder.py の回帰テスト
"""

from ui.map_builder import _calc_fit_bounds, _collect_valid_coordinates, _collect_valid_toilets, build_map


def _make_toilet(title: str, lat: object, lng: object) -> dict:
    return {
        "title": title,
        "category": "公園",
        "toilet_score": 80,
        "is_public_toilet": True,
        "confidence": 0.5,
        "toilet_review_count": 2,
        "address": "東京都千代田区",
        "rating": 4.0,
        "review_count": 10,
        "sample_reviews": [],
        "top_keywords": [],
        "lat": lat,
        "lng": lng,
    }


class TestCalcFitBounds:
    def test_ignores_invalid_coordinates(self):
        toilets = [
            _make_toilet("valid", 35.68, 139.69),
            _make_toilet("missing lat", None, 139.70),
            _make_toilet("string lat", "abc", 139.71),
            _make_toilet("out of range", 91.0, 139.72),
        ]

        valid = _collect_valid_toilets(toilets)
        bounds = _calc_fit_bounds(valid)

        assert bounds == [[35.67, 139.68], [35.69, 139.7]]

    def test_deduplicates_same_coordinates_for_bounds(self):
        toilets = [
            _make_toilet("first", 35.68, 139.69),
            _make_toilet("second", 35.68, 139.69),
        ]

        coords = _collect_valid_coordinates(toilets)

        assert coords == [(35.68, 139.69)]


class TestBuildMap:
    def test_skips_invalid_coordinates(self):
        toilets = [
            _make_toilet("valid toilet", 35.68, 139.69),
            _make_toilet("invalid toilet", "abc", None),
        ]

        m = build_map(toilets, 35.68, 139.69, 12)
        html = m.get_root().render()

        assert "valid toilet" in html
        assert "invalid toilet" not in html

    def test_deduplicates_same_coordinates(self):
        toilets = [
            _make_toilet("first toilet", 35.68, 139.69),
            _make_toilet("second toilet", 35.68, 139.69),
        ]

        valid_toilets = _collect_valid_toilets(toilets)
        m = build_map(toilets, 35.68, 139.69, 12)
        html = m.get_root().render()

        assert len(valid_toilets) == 1
        assert "second toilet" not in html


class TestCoerceCoordinate:
    def test_invalid_returns_none(self):
        from ui.map_builder import _coerce_coordinate

        assert _coerce_coordinate("abc") is None
        assert _coerce_coordinate(None) is None
        assert _coerce_coordinate(float("inf")) is None
        assert _coerce_coordinate(float("nan")) is None


class TestCalcClusterRadius:
    def test_large_count_returns_max(self):
        from ui.map_builder import calc_cluster_radius

        assert calc_cluster_radius(9999) == 100
        assert calc_cluster_radius(1000) == 100


class TestCalcMapCenter:
    def test_prefecture_stats_used_when_available(self, monkeypatch):
        from ui.map_builder import calc_map_center

        stats = {"東京都": {"count": 10, "center_lat": 35.7, "center_lng": 139.7}}
        lat, lng, zoom = calc_map_center("東京都", {}, stats)
        assert lat == 35.7
        assert lng == 139.7
        assert zoom == 11

    def test_prefecture_center_fallback_when_stats_low(self, monkeypatch):
        from ui.map_builder import PREFECTURE_CENTERS, calc_map_center

        monkeypatch.setitem(PREFECTURE_CENTERS, "東京都", (35.5, 139.5))
        stats = {"東京都": {"count": 2, "center_lat": 0, "center_lng": 0}}
        lat, lng, zoom = calc_map_center("東京都", {}, stats)
        assert lat == 35.5
        assert lng == 139.5


class TestCalcMapCenterFallback:
    def test_all_prefecture_uses_meta(self):
        from ui.map_builder import calc_map_center
        meta = {"center_lat": 36.0, "center_lng": 138.0, "zoom": 6}
        lat, lng, zoom = calc_map_center("全て", meta, {})
        assert lat == 36.0
        assert lng == 138.0
        assert zoom == 6


class TestCalcFitBoundsEdgeCases:
    def test_no_valid_coords_returns_none(self):
        from ui.map_builder import _calc_fit_bounds

        assert _calc_fit_bounds([]) is None

    def test_empty_list_returns_none(self):
        from ui.map_builder import _calc_fit_bounds

        assert _calc_fit_bounds([]) is None

    def test_single_point_expands(self):
        from ui.map_builder import _calc_fit_bounds, _collect_valid_toilets

        toilets = [_make_toilet("only", 35.0, 139.0)]
        valid = _collect_valid_toilets(toilets)
        bounds = _calc_fit_bounds(valid)
        assert bounds is not None
        assert bounds[0][0] < 35.0  # south expanded
        assert bounds[1][0] > 35.0  # north expanded
