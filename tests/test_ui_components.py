"""
tests/test_ui_components.py
ui/components.py のユニットテスト（app_config テストは test_app_config.py に集約）
"""
from datetime import date

import pytest

from ui.components import (
    build_data_freshness_text,
    build_result_context_text,
    build_score_legend_html,
    build_toilet_card_html,
    render_score_legend,
)
from ui.helpers import get_equipment_tags


class TestBuildResultContextText:
    def test_page_limited_results_include_timing(self):
        text = build_result_context_text(120, 120, 3.4, 45.6)
        assert "一覧 120件" in text
        assert "地図 120件" in text
        assert "絞り込み 3ms" in text
        assert "地図 46ms" in text

    def test_full_results_without_timing_stays_compact(self):
        text = build_result_context_text(10, 10)
        assert "一覧 10件" in text
        assert "地図 10件" in text
        assert "絞り込み" not in text

    def test_partial_timings(self):
        text = build_result_context_text(20, 20, filter_elapsed_ms=30.0)
        assert "絞り込み 30ms" in text
        assert "地図 0ms" not in text
        assert "地図 100ms" not in text

    def test_no_timings(self):
        text = build_result_context_text(5, 5)
        assert "一覧 5件" in text
        assert "|" not in text or "ms" not in text

    def test_zero_timings(self):
        text = build_result_context_text(1, 1, 0.0, 0.0)
        assert "0ms" in text


class TestBuildDataFreshnessText:
    @staticmethod
    def translations() -> dict[str, str]:
        return {
            "freshness": "データ鮮度",
            "source_updated": "生成",
            "db_synced": "DB同期",
            "freshness_current": "最新",
            "freshness_aging": "更新から時間が経過",
            "freshness_stale": "古いデータ",
            "freshness_unknown": "更新日不明",
            "freshness_age_days": "{days}日前",
        }

    def test_includes_generated_and_synced_times(self):
        meta = {
            "last_updated": "2026-05-10 21:27:30",
            "db_synced_at": "2026-05-10 21:28:05",
        }

        text = build_data_freshness_text(meta, self.translations(), today=date(2026, 5, 17))

        assert "🟢 データ鮮度: 最新 (7日前)" in text
        assert "生成 2026-05-10 21:27:30" in text
        assert "DB同期 2026-05-10 21:28:05" in text

    def test_falls_back_when_sync_time_missing(self):
        meta = {"last_updated": "2026-05-10 21:27:30"}
        t = {
            "freshness": "Freshness",
            "source_updated": "Generated",
            "db_synced": "DB synced",
            "freshness_current": "Current",
            "freshness_age_days": "{days} days ago",
        }

        text = build_data_freshness_text(meta, t, today=date(2026, 5, 10))

        assert "🟢 Freshness: Current (0 days ago)" in text
        assert "Generated 2026-05-10 21:27:30" in text
        assert "DB synced N/A" in text

    @pytest.mark.parametrize(
        ("today", "expected"),
        [
            (date(2026, 5, 18), "🟡 データ鮮度: 更新から時間が経過 (8日前)"),
            (date(2026, 6, 10), "🔴 データ鮮度: 古いデータ (31日前)"),
        ],
    )
    def test_marks_aging_and_stale_data(self, today: date, expected: str):
        text = build_data_freshness_text(
            {"last_updated": "2026-05-10T21:27:30+09:00"},
            self.translations(),
            today=today,
        )
        assert expected in text

    @pytest.mark.parametrize("value", [None, "", "not-a-date", "2026-05-18"])
    def test_marks_missing_invalid_or_future_dates_unknown(self, value: object):
        text = build_data_freshness_text(
            {"last_updated": value},
            self.translations(),
            today=date(2026, 5, 17),
        )
        assert "⚪ データ鮮度: 更新日不明" in text


class TestEquipmentTags:
    def test_normalizes_synonyms_prefixes_and_duplicates(self):
        tags = get_equipment_tags(
            [
                ["多目的トイレ", 3],
                ["多機能", 1],
                ["+おむつ交換", 2],
                ["-車いす", 1],
                ["清潔", 9],
            ]
        )

        assert tags == ["多目的", "おむつ替え", "車椅子対応"]

    @pytest.mark.parametrize("keywords", [None, "車椅子", {}, [[], [None], 123]])
    def test_ignores_missing_or_malformed_keywords(self, keywords: object):
        assert get_equipment_tags(keywords) == []


class TestBuildToiletCardHtml:
    @staticmethod
    def toilet(**overrides):
        toilet = {
            "title": "テストトイレ", "category": "公園", "address": "東京都",
            "toilet_score": 80.0, "confidence": 0.8, "is_public_toilet": True,
            "rating": 4.5, "review_count": 100, "lat": 35.0, "lng": 139.0,
            "link": "https://maps.google.com/", "sample_reviews": [], "top_keywords": [],
        }
        toilet.update(overrides)
        return toilet

    def test_basic_card(self):
        html = build_toilet_card_html(self.toilet(link=""))
        assert "テストトイレ" in html

    def test_with_link(self):
        toilet = {
            "title": "A", "category": "カフェ", "address": "大阪",
            "toilet_score": 50.0, "confidence": 0.5, "is_public_toilet": False,
            "rating": 3.0, "review_count": 10, "lat": 34.0, "lng": 135.0,
            "link": "https://maps.google.com/", "sample_reviews": [], "top_keywords": [],
        }
        html = build_toilet_card_html(toilet)
        assert 'href="https://maps.google.com/"' in html

    def test_no_rank_no_meta(self):
        toilet = {
            "title": "B", "category": "公園", "address": "東京",
            "toilet_score": 60.0, "confidence": 0.6, "is_public_toilet": False,
            "rating": 4.0, "review_count": 20, "sample_reviews": [], "top_keywords": [],
        }
        html = build_toilet_card_html(toilet)
        assert "#" not in html or 'style="color:#999' not in html

    def test_no_link_no_coords_no_dirs(self):
        toilet = {
            "title": "C", "category": "駅", "address": "大阪",
            "toilet_score": 70.0, "confidence": 0.7, "is_public_toilet": True,
            "rating": 4.0, "review_count": 15, "lat": 34.0, "lng": 135.0,
            "sample_reviews": [], "top_keywords": [],
        }
        html = build_toilet_card_html(toilet)
        assert "Google Maps" not in html

    def test_no_link_no_latlng_no_maps_links(self):
        toilet = {
            "title": "D", "category": "駅", "address": "大阪",
            "toilet_score": 70.0, "confidence": 0.7, "is_public_toilet": True,
            "rating": 4.0, "review_count": 15, "sample_reviews": [], "top_keywords": [],
        }
        html = build_toilet_card_html(toilet)
        assert "Google Maps" not in html
        assert "ルート検索" not in html

    def test_accessible_name_includes_rank_and_quality_context(self):
        html = build_toilet_card_html(self.toilet(), rank=3)

        assert (
            'aria-label="順位 3位、テストトイレ、スコア 80点、評価 4.5、'
            '口コミ 100件、信頼度 80%、公共トイレ、住所 東京都"'
        ) in html

    def test_map_links_have_destination_specific_accessible_names(self):
        html = build_toilet_card_html(self.toilet())

        assert (
            'aria-label="テストトイレをGoogle Mapsで開く（新しいタブ） / '
            'Open テストトイレ in Google Maps (new tab)"'
        ) in html
        assert (
            'aria-label="テストトイレへのルートを検索（新しいタブ） / '
            'Get directions to テストトイレ (new tab)"'
        ) in html

    def test_accessibility_labels_escape_title_and_hide_decorative_content(self):
        html = build_toilet_card_html(self.toilet(title='A "B" & C'), rank=1)

        assert "A &quot;B&quot; &amp; C" in html
        assert '<span aria-hidden="true" style="color:#999' in html
        assert '<span aria-hidden="true">&#x1F4CD;</span>' in html
        assert '<span aria-hidden="true">&#x2B50;</span>' in html
        assert 'class="toilet-card-arrow" aria-hidden="true"' in html

    def test_displays_review_derived_equipment_mentions(self):
        html = build_toilet_card_html(
            self.toilet(
                top_keywords=[
                    ["多目的", 4],
                    ["おむつ交換", 2],
                    ["車椅子", 1],
                    ["清潔", 10],
                ]
            )
        )

        assert 'class="toilet-card-equipment" aria-hidden="true"' in html
        assert "設備の言及:" in html
        assert ">多目的</span>" in html
        assert ">おむつ替え</span>" in html
        assert ">車椅子対応</span>" in html
        assert "口コミで設備の言及 多目的、おむつ替え、車椅子対応" in html
        assert "清潔</span>" not in html

    def test_hides_equipment_row_without_supported_mentions(self):
        html = build_toilet_card_html(self.toilet(top_keywords=[["清潔", 10], ["広い", 3]]))

        assert "toilet-card-equipment" not in html
        assert "設備の言及:" not in html
        assert "口コミで設備の言及" not in html


class TestBuildScoreLegendHtml:
    def test_explains_unscored_state_accessibly(self):
        html = build_score_legend_html()

        assert 'role="group"' in html
        assert 'aria-label="スコア凡例 / Score legend"' in html
        assert 'aria-label="低スコアから高スコア / Low to high score"' in html
        assert "未採点 / Unscored" in html
        assert "color:#6b7280" in html
        assert "flex-wrap:wrap" in html


class TestRenderScoreLegend:
    def test_returns_no_error(self):
        render_score_legend()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
