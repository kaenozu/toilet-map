"""
ui/session_state.py
Centralized session state schema for toilet-map app.

存在理由: アプリ全体で使う session_state のキーを一元管理し、
各モジュールが個別に setdefault するのを防ぐため。

関連ファイル: app.py, ui/pagination.py, ui/sidebar.py, ui/query_params.py
"""
import streamlit as st

from ui.i18n import DEFAULT_LANGUAGE


def init_session_state() -> None:
    """アプリ全体で使う session_state キーにデフォルト値を設定する。"""
    st.session_state.setdefault("page", 1)
    st.session_state.setdefault("page_filter_key", "")
    st.session_state.setdefault("lang_select", DEFAULT_LANGUAGE)
    st.session_state.setdefault("_show_shortcuts", False)
    st.session_state.setdefault("compact_mode", False)
    st.session_state.setdefault("font_size", "medium")
    st.session_state.setdefault("font_family", "sans-serif")
    st.session_state.setdefault("show_heatmap", False)
