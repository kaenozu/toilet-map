"""
tests/test_ui_components.py
ui/components.py のユニットテスト
"""
import pytest
from app_config import get_score_style, esc
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend


class TestGetScoreStyle:
    def test_high_score(self):
        color, emoji, label = get_score_style(90)
        assert emoji == "✨"
        assert label == "とてもきれい"

    def test_low_score(self):
        color, emoji, label = get_score_style(10)
        assert emoji == "💩"

    def test_esc_none(self):
        assert esc(None) == ""

    def test_esc_html(self):
        assert esc("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"


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
        # map_elapsed_ms未指定なので、地図のtimingは表示されない
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
    def test_includes_generated_and_synced_times(self):
        meta = {
            "last_updated": "2026-05-10 21:27:30",
            "db_synced_at": "2026-05-10 21:28:05",
        }
        t = {
            "freshness": "データ鮮度",
            "source_updated": "生成",
            "db_synced": "DB同期",
        }

        text = build_data_freshness_text(meta, t)

        assert "データ鮮度" in text
        assert "生成 2026-05-10 21:27:30" in text
        assert "DB同期 2026-05-10 21:28:05" in text

    def test_falls_back_when_sync_time_missing(self):
        meta = {"last_updated": "2026-05-10 21:27:30"}
        t = {
            "freshness": "Freshness",
            "source_updated": "Generated",
            "db_synced": "DB synced",
        }

        text = build_data_freshness_text(meta, t)

        assert "Generated 2026-05-10 21:27:30" in text
        assert "DB synced N/A" in text


class TestRenderScoreLegend:
    def test_returns_no_error(self):
        render_score_legend()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
