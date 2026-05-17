"""
ui/metrics.py
In-app metrics visualization for performance and usage monitoring.
Related: app.py, ui/data_loader.py
"""
import streamlit as st


class MetricsCollector:
    """Simple in-memory metrics collector."""
    def __init__(self):
        self._timings: dict[str, list[float]] = {}

    def record(self, name: str, elapsed_ms: float) -> None:
        if name not in self._timings:
            self._timings[name] = []
        self._timings[name].append(elapsed_ms)
        if len(self._timings[name]) > 100:
            self._timings[name] = self._timings[name][-100:]

    def get_stats(self, name: str) -> dict:
        vals = self._timings.get(name, [])
        if not vals:
            return {"count": 0}
        return {
            "count": len(vals),
            "avg_ms": sum(vals) / len(vals),
            "min_ms": min(vals),
            "max_ms": max(vals),
            "last_ms": vals[-1],
        }

    def all_stats(self) -> dict:
        return {k: self.get_stats(k) for k in self._timings}


_metrics = None

def get_metrics() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def render_metrics_dashboard() -> None:
    """Show metrics in an expander in the main area."""
    coll = get_metrics()
    stats = coll.all_stats()
    if not stats:
        return
    with st.expander("📊 パフォーマンスメトリクス", expanded=False):
        for name, s in stats.items():
            if s["count"] > 0:
                st.metric(
                    label=name,
                    value=f"{s['avg_ms']:.0f}ms",
                    delta=f"{s['last_ms']:.0f}ms (last)",
                )
