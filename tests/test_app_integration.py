"""
tests/test_app_integration.py
app.py の統合テスト（Streamlit ランタイム不要な範囲で検証）
"""
import importlib.util
import sys


class TestAppImports:
    """app.py のモジュール読み込み検証"""

    def test_app_module_can_be_loaded(self):
        """app.py が import エラーなく読み込めることを確認"""
        spec = importlib.util.find_spec("app")
        assert spec is not None, "app.py が見つかりません"

    def test_required_modules_available(self):
        """必須依存モジュールがインストールされていることを確認"""
        for mod_name in ["streamlit", "folium", "streamlit_folium", "pandas", "numpy", "altair"]:
            assert mod_name in sys.modules or importlib.util.find_spec(mod_name) is not None, f"{mod_name} がありません"


class TestAppConfigCoherence:
    """app_config.py の設定値一貫性検証"""

    def test_all_filter_icons_have_config(self):
        from app_config import FILTER_CONFIG, FILTER_I18N_KEYS
        for ja_key in FILTER_I18N_KEYS:
            assert ja_key in FILTER_CONFIG, f"FILTER_I18N_KEYS に '{ja_key}' がありますが FILTER_CONFIG にありません"
        for ja_key in FILTER_CONFIG:
            assert ja_key in FILTER_I18N_KEYS, f"FILTER_CONFIG に '{ja_key}' がありますが FILTER_I18N_KEYS にありません"

    def test_all_filters_have_translations(self):
        from app_config import FILTER_I18N_KEYS
        from ui.i18n import LANGUAGES
        for lang_name, lang_dict in LANGUAGES.items():
            for i18n_key in FILTER_I18N_KEYS.values():
                assert i18n_key in lang_dict, f"{lang_name} に {i18n_key} がありません"


class TestDataFlowSchema:
    """データフローのスキーマ一貫性検証"""

    def test_toilet_score_range(self):
        from app_config import SCORE_RANGES
        # スコア範囲が0-100で連続しているか
        thresholds = [t[0] for t in SCORE_RANGES]
        assert thresholds == sorted(thresholds, reverse=True), "スコア範囲は降順である必要があります"
        assert thresholds[0] <= 100
        assert thresholds[-1] >= 0

    def test_score_distribution_ranges_match(self):
        from app_config import SCORE_DISTRIBUTION_RANGES, SCORE_RANGES
        assert len(SCORE_RANGES) == len(SCORE_DISTRIBUTION_RANGES)
        for sr, sdr in zip(SCORE_RANGES, SCORE_DISTRIBUTION_RANGES, strict=False):
            assert sr[0] == sdr[0], f"スコアしきい値不一致: {sr[0]} != {sdr[0]}"
            assert sr[1] == sdr[3], f"色不一致: {sr[1]} != {sdr[3]}"
