"""ui/map_builder.py regression tests."""

from app_config import TILE_OPTIONS
from ui.map_builder import (
    _calc_fit_bounds,
    _coerce_coordinate,
    _collect_valid_coordinates,
    _collect_valid_toilets,
    build_map,
    calc_cluster_radius,
    calc_map_center,
)


def _make_toilet(title: str, lat: object, lng: object) -> dict:
    return {
        "source_id": f"test:{title}",
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
        assert _calc_fit_bounds(toilets) == [[35.67, 139.68], [35.69, 139.7]]

    def test_preserves_same_coordinates_for_distinct_facilities(self):
        toilets = [_make_toilet("first", 35.68, 139.69), _make_toilet("second", 35.68, 139.69)]
        assert _collect_valid_coordinates(toilets) == [(35.68, 139.69), (35.68, 139.69)]

    def test_no_valid_coords_returns_none(self):
        assert _calc_fit_bounds([_make_toilet("bad", None, None)]) is None

    def test_empty_list_returns_none(self):
        assert _calc_fit_bounds([]) is None

    def test_single_point_expands(self):
        bounds = _calc_fit_bounds([_make_toilet("only", 35.0, 139.0)])
        assert bounds is not None
        assert bounds[0][0] < 35.0
        assert bounds[1][0] > 35.0


class TestBuildMap:
    def test_skips_invalid_coordinates(self):
        toilets = [_make_toilet("valid toilet", 35.68, 139.69), _make_toilet("invalid toilet", "abc", None)]
        html = build_map(toilets, 35.68, 139.69, 12).get_root().render()
        assert "valid toilet" in html
        assert "invalid toilet" not in html

    def test_preserves_same_coordinates(self):
        toilets = [_make_toilet("first toilet", 35.68, 139.69), _make_toilet("second toilet", 35.68, 139.69)]
        assert len(_collect_valid_toilets(toilets)) == 2
        html = build_map(toilets, 35.68, 139.69, 12).get_root().render()
        assert "first toilet" in html
        assert "second toilet" in html

    def test_custom_opentopomap_has_attribution(self):
        tile = TILE_OPTIONS["地形図（OpenTopoMap）"]
        html = build_map([_make_toilet("A", 35.68, 139.69)], 35.68, 139.69, 12, tile=tile).get_root().render()
        assert "OpenTopoMap" in html
        assert "openstreetmap.org/copyright" in html


class TestCoerceCoordinate:
    def test_invalid_returns_none(self):
        assert _coerce_coordinate("abc") is None
        assert _coerce_coordinate(None) is None
        assert _coerce_coordinate(float("inf")) is None
        assert _coerce_coordinate(float("nan")) is None


class TestCalcClusterRadius:
    def test_large_count_returns_max(self):
        assert calc_cluster_radius(9999) == 100
        assert calc_cluster_radius(1000) == 100


class TestCalcMapCenter:
    def test_prefecture_stats_used_when_available(self):
        stats = {"東京都": {"count": 10, "center_lat": 35.7, "center_lng": 139.7}}
        assert calc_map_center("東京都", {}, stats) == (35.7, 139.7, 11)

    def test_prefecture_center_fallback_when_stats_low(self, monkeypatch):
        from ui.map_builder import PREFECTURE_CENTERS
        monkeypatch.setitem(PREFECTURE_CENTERS, "東京都", (35.5, 139.5))
        stats = {"東京都": {"count": 2, "center_lat": 0, "center_lng": 0}}
        assert calc_map_center("東京都", {}, stats) == (35.5, 139.5, 11)

    def test_all_prefecture_uses_meta(self):
        meta = {"center_lat": 36.0, "center_lng": 138.0, "zoom": 6}
        assert calc_map_center("全て", meta, {}) == (36.0, 138.0, 6)
