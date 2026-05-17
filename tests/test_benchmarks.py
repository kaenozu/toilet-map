"""
tests/test_benchmarks.py
Benchmark tests for performance regression detection.

Relates to: tests/test_data_loader.py, ui/data_loader.py, app_config.py
"""


class TestBenchmarks:
    def test_pref_stats_calculation_speed(self, benchmark):
        import sqlite3

        import pandas as pd

        from app_config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        toilets = pd.read_sql("SELECT * FROM toilets", conn).to_dict("records")
        conn.close()

        def compute():
            import math
            pref_stats = {}
            for t in toilets:
                pref = t.get("prefecture")
                if not pref or (isinstance(pref, float) and math.isnan(pref)):
                    continue
                if pref not in pref_stats:
                    pref_stats[pref] = {"count": 0, "lat_sum": 0.0, "lng_sum": 0.0}
                pref_stats[pref]["count"] += 1
                pref_stats[pref]["lat_sum"] += t["lat"] or 0
                pref_stats[pref]["lng_sum"] += t["lng"] or 0
            for data in pref_stats.values():
                c = data.pop("count")
                data["center_lat"] = data.pop("lat_sum") / c if c else 0
                data["center_lng"] = data.pop("lng_sum") / c if c else 0
            return pref_stats

        result = benchmark(compute)
        assert len(result) > 0


class TestBenchmarkBudget:
    def test_pref_stats_within_budget(self, benchmark):
        import sqlite3

        import pandas as pd

        from app_config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        toilets = pd.read_sql("SELECT * FROM toilets", conn).to_dict("records")
        conn.close()

        def compute():
            import math
            pref_stats = {}
            for t in toilets:
                pref = t.get("prefecture")
                if not pref or (isinstance(pref, float) and math.isnan(pref)):
                    continue
                if pref not in pref_stats:
                    pref_stats[pref] = {"count": 0, "lat_sum": 0.0, "lng_sum": 0.0}
                pref_stats[pref]["count"] += 1
                pref_stats[pref]["lat_sum"] += t["lat"] or 0
                pref_stats[pref]["lng_sum"] += t["lng"] or 0
            for data in pref_stats.values():
                c = data.pop("count")
                data["center_lat"] = data.pop("lat_sum") / c if c else 0
                data["center_lng"] = data.pop("lng_sum") / c if c else 0
            return pref_stats

        result = benchmark(compute)
        assert benchmark.stats.stats.mean < 0.5, "perf budget exceeded: pref_stats > 500ms"
        assert len(result) > 0
