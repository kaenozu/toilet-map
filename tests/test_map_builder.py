"""
tests/test_map_builder.py
ui/map_builder.py のユニットテスト
"""
import pytest
from ui.map_builder import calc_map_center, calc_cluster_radius, build_map
from app_config import PREFECTURE_CENTERS


class TestCalcMapCenter:
    def test_all_prefecture_returns_meta_center(self):
        meta = {"center_lat": 36.0, "center_lng": 139.0, "zoom": 6}
        lat, lng, zoom = calc_map_center("全て", meta, {})
        assert lat == 36.0
        assert lng == 139.0
        assert zoom == 6

    def test_specific_prefecture_with_stats(self):
        meta = {"center_lat": 36.0, "center_lng": 139.0, "zoom": 6}
        pref_stats = {"東京都": {"count": 10, "center_lat": 35.68, "center_lng": 139.69}}
        lat, lng, zoom = calc_map_center("東京都", meta, pref_stats)
        assert lat == pytest.approx(35.68, abs=0.01)
        assert lng == pytest.approx(139.69, abs=0.01)
        assert zoom == 11

    def test_specific_prefecture_fallback_to_center(self):
        meta = {"center_lat": 36.0, "center_lng": 139.0, "zoom": 6}
        lat, lng, zoom = calc_map_center("東京都", meta, {})
        expected = PREFECTURE_CENTERS["東京都"]
        assert lat == expected[0]
        assert lng == expected[1]
        assert zoom == 11

    def test_specific_prefecture_low_count_fallback(self):
        meta = {"center_lat": 36.0, "center_lng": 139.0, "zoom": 6}
        pref_stats = {"東京都": {"count": 3, "center_lat": 35.68, "center_lng": 139.69}}
        lat, lng, zoom = calc_map_center("東京都", meta, pref_stats)
        expected = PREFECTURE_CENTERS["東京都"]
        assert lat == expected[0]
        assert lng == expected[1]

    def test_unknown_prefecture_uses_meta(self):
        meta = {"center_lat": 36.0, "center_lng": 139.0, "zoom": 6}
        lat, lng, zoom = calc_map_center("未知県", meta, {})
        assert lat == 36.0
        assert lng == 139.0


class TestCalcClusterRadius:
    def test_small_count(self):
        assert calc_cluster_radius(10) == 50

    def test_medium_count(self):
        assert calc_cluster_radius(499) == 50
        assert calc_cluster_radius(500) == 80

    def test_large_count(self):
        assert calc_cluster_radius(600) == 80

    def test_very_large_count(self):
        assert calc_cluster_radius(2000) == 100

    def test_zero(self):
        assert calc_cluster_radius(0) == 50


class TestBuildMap:
    def test_empty_toilets(self):
        m = build_map([], 35.68, 139.69, 10)
        assert m is not None

    def test_with_toilets(self):
        toilets = [
            {
                "title": "テストトイレ",
                "category": "カフェ",
                "address": "東京都",
                "lat": 35.68,
                "lng": 139.69,
                "toilet_score": 80,
                "is_public_toilet": False,
                "confidence": 0.8,
                "toilet_review_count": 3,
                "top_keywords": [("+きれい", 2)],
                "sample_reviews": [],
                "phone": "",
                "rating": 4.0,
                "review_count": 10,
                "link": "",
            }
        ]
        m = build_map(toilets, 35.68, 139.69, 10)
        assert m is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
