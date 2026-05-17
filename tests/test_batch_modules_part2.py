"""
tests/test_batch_modules.py
batch modules のモックベースユニットテスト
docker_exec, city_bounds, auto_expand, scrape_runner の関数をテスト
"""
import os
import shutil

from auto_expand import _build_gap_entry, _load_current_stats, _lookup_city_count, _select_targets
from scrape_filter import fetch_city_bounds
from scrape_runner import _cleanup_on_success


class TestAutoExpandStats:
    """auto_expand.py の集計・選択関数のテスト"""

    def test_load_current_stats_empty(self, monkeypatch, tmp_path):
        import auto_expand as ae
        monkeypatch.setattr(ae, "CURRENT_DATA_PATHS", [str(tmp_path / "nonexistent.json.gz")])
        stats = _load_current_stats()
        assert isinstance(stats, dict)

    def test_lookup_city_count_found(self):
        stats = {
            "prefecture_city_counts": {
                "東京都": {"千代田区": "5", "渋谷区": "3"},
            }
        }
        assert _lookup_city_count(stats, "東京都", "千代田区") == 5

    def test_lookup_city_count_not_found(self):
        stats = {
            "prefecture_city_counts": {
                "東京都": {"千代田区": "5"},
            }
        }
        assert _lookup_city_count(stats, "東京都", "新宿区") == 0

    def test_lookup_city_count_missing_pref(self):
        stats = {"prefecture_city_counts": {"東京都": {}}}
        assert _lookup_city_count(stats, "大阪府", "大阪市") == 0

    def test_lookup_city_count_non_dict_nested(self):
        stats = {"prefecture_city_counts": "invalid"}
        assert _lookup_city_count(stats, "東京都", "千代田区") == 0

    def test_lookup_city_count_non_int_value(self):
        stats = {"prefecture_city_counts": {"東京都": {"千代田区": "abc"}}}
        assert _lookup_city_count(stats, "東京都", "千代田区") == 0

    def test_build_gap_entry_with_count(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "2", "熊谷市": "5"},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市", count=2)
        assert entry["prefecture"] == "埼玉県"
        assert entry["city"] == "羽生市"
        assert entry["count"] == 2
        assert entry["prefecture_total"] == 7
        assert entry["active"] is True

    def test_build_gap_entry_without_count(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "3"},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市")
        assert entry["count"] == 3

    def test_build_gap_entry_inactive(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市", count=0)
        assert entry["active"] is False

    def test_select_targets_with_target_pref_and_city(self):
        stats = {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}}
        targets = _select_targets(stats, max_areas=5, target_pref="埼玉県", target_city="羽生市")
        assert len(targets) == 1
        assert targets[0]["prefecture"] == "埼玉県"
        assert targets[0]["city"] == "羽生市"

    def test_select_targets_with_target_pref_only(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "0", "熊谷市": "2"},
            }
        }
        targets = _select_targets(stats, max_areas=1, target_pref="埼玉県")
        assert len(targets) >= 1

    def test_select_targets_empty_when_pref_unknown(self):
        stats = {"prefecture_city_counts": {"東京都": {}}}
        targets = _select_targets(stats, max_areas=5, target_pref="存在しない県")
        assert targets == []

    def test_select_targets_with_target_city_only(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "0"},
            }
        }
        targets = _select_targets(stats, max_areas=5, target_city="羽生市")
        assert len(targets) == 1
        assert targets[0]["city"] == "羽生市"

    def test_select_targets_target_city_not_found(self):
        stats = {"prefecture_city_counts": {}}
        targets = _select_targets(stats, max_areas=5, target_city="存在しない市")
        assert targets == []

    def test_select_targets_defaults_to_gaps(self):
        stats = {"prefecture_city_counts": {}}
        targets = _select_targets(stats, max_areas=3)
        assert isinstance(targets, list)



class TestScrapeRunner:
    """scrape_runner.py のモックテスト"""

    def test_fetch_city_bounds_with_pref_only(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(name, pref=""):
            calls.append(name if not pref else (name, pref))
            return {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("", "東京都")
        assert result is not None

    def test_fetch_city_bounds_with_pref_and_city(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(city, pref=""):
            calls.append((city, pref))
            if pref:
                return {"south": 35.6, "north": 35.7, "west": 139.6, "east": 139.8}
            return None

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result is not None
        assert calls == [("渋谷区", "東京都")]

    def test_fetch_city_bounds_fallback_to_city_only(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(city, pref=""):
            calls.append((city, pref))
            return None

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result is None
        assert calls == [("渋谷区", "東京都"), ("渋谷区", "")]

    def test_cleanup_on_success_no_failures(self, monkeypatch, tmp_path):
        import scrape_runner as sr

        progress = tmp_path / "progress.json"
        progress.write_text("{}", encoding="utf-8")
        raw_dir = tmp_path / "raw_parts"
        raw_dir.mkdir()

        monkeypatch.setattr(sr, "RAW_DIR", str(raw_dir))

        removed = []

        def fake_remove(p):
            removed.append(("remove", p))

        monkeypatch.setattr(os, "remove", fake_remove)
        monkeypatch.setattr(shutil, "rmtree", lambda p: removed.append(("rmtree", str(p))))

        _cleanup_on_success(0, str(progress))

        assert any("rmtree" in str(r) for r in removed)
        assert any("remove" in str(r) for r in removed)

    def test_cleanup_on_success_with_failures(self, monkeypatch):
        removed = []
        monkeypatch.setattr(os, "remove", lambda p: removed.append(p))
        monkeypatch.setattr(shutil, "rmtree", lambda p: removed.append(p))

        _cleanup_on_success(3, "/fake/progress")
        assert removed == []



class TestAutoExpandEdgeCases:
    def test_load_current_stats_oserror(self, monkeypatch):
        from auto_expand import _load_current_stats
        monkeypatch.setattr("auto_expand.load_json", lambda _: (_ for _ in ()).throw(OSError))
        stats = _load_current_stats()
        assert stats["total"] == 0

    def test_select_targets_exact_match(self):
        from auto_expand import _select_targets
        stats = {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}}
        targets = _select_targets(stats, max_areas=5, target_pref="埼玉県", target_city="羽生市")
        assert len(targets) == 1

    def test_select_targets_pref_fallback_with_city_order(self):
        from auto_expand import _select_targets
        stats = {"prefecture_city_counts": {"埼玉県": {"熊谷市": "0", "羽生市": "1"}}}
        targets = _select_targets(stats, max_areas=3, target_pref="埼玉県")
        assert len(targets) >= 1

    def test_run_auto_expansion_no_targets(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr(ae, "_load_current_stats", lambda: {"prefecture_city_counts": {}, "total": 0, "scored": 0, "score_avg": 0})
        monkeypatch.setattr(ae, "find_gaps", lambda *a, **kw: [])
        ae.run_auto_expansion(max_areas=5)

    def test_auto_expand_main_exits_on_zero_args(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr("sys.argv", ["auto_expand.py"])
        monkeypatch.setattr(ae, "run_auto_expansion", lambda *a, **kw: None)
        ae.main()

    def test_auto_expand_main_passes_args(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr("sys.argv", ["auto_expand.py", "--prefecture", "東京都", "--city", "渋谷区"])
        captured = {}
        def _capture(*args):
            captured["max_areas"] = args[0] if len(args) > 0 else None
            captured["target_pref"] = args[1] if len(args) > 1 else ""
            captured["target_city"] = args[2] if len(args) > 2 else ""
        monkeypatch.setattr(ae, "run_auto_expansion", _capture)
        ae.main()
        assert captured.get("target_city") == "渋谷区"

    def test_run_auto_expansion_file_not_found(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr(ae, "_load_current_stats", lambda: {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}, "total": 0, "scored": 0, "score_avg": 0})
        monkeypatch.setattr(ae, "find_gaps", lambda *a, **kw: [{"prefecture": "埼玉県", "city": "羽生市", "count": 0}])
        monkeypatch.setattr(ae, "query_limits_for_count", lambda c: (2, 2))
        monkeypatch.setattr(ae, "active_context", lambda *a, **kw: _null_context())
        monkeypatch.setattr(ae, "ensure_query_files", lambda p: None)
        monkeypatch.setattr(ae, "find_batch_files", lambda p: [])
        monkeypatch.setattr(ae, "merge_query_files", lambda f: "")
        monkeypatch.setattr(ae.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError))
        ae.run_auto_expansion(max_areas=1)



def _null_context():
    class NullCtx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return NullCtx()



