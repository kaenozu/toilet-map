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

        bounds = _calc_fit_bounds(toilets)

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
