"""
ui/pipeline_status.py
Web UI for monitoring batch data pipeline execution status.
Related: batch/auto_expand_pipeline.bat, batch/expansion_status.json, app.py
"""
import json
from pathlib import Path

import streamlit as st

STATUS_FILE = Path("batch/expansion_status.json")


def render_pipeline_status() -> None:
    """Show pipeline execution status in an expander."""
    if not STATUS_FILE.exists():
        return
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    with st.expander("🔄 データパイプライン状況", expanded=False):
        last_run = data.get("last_run", "不明")
        status = data.get("status", "unknown")
        stage = data.get("current_stage", "-")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("最終実行", last_run[:16] if len(last_run) > 16 else last_run)
        with col2:
            st.metric("状態", status)
        with col3:
            st.metric("現在のステージ", stage)

        if data.get("errors"):
            st.error(f"エラー: {data['errors']}")
