"""
ui/types.py
Shared TypedDict definitions for UI components
"""
import streamlit as st
from typing import TypedDict, Optional, Any

class ToiletDict(TypedDict, total=False):
    """トイレデータの型定義"""
    title: str
    category: str
    address: str
    lat: float
    lng: float
    phone: str
    rating: float
    review_count: int
    link: str
    is_public_toilet: bool
    toilet_score: float
    confidence: float
    toilet_review_count: int
    top_keywords: list[tuple[str, int]]
    sample_reviews: list[dict[str, Any]]
    prefecture: str
    distance: Optional[float]


class AppState:
    """型安全なセッション状態管理"""

    @property
    def lang(self) -> str:
        return st.session_state.get("lang_select", "日本語")

    @lang.setter
    def lang(self, value: str) -> None:
        st.session_state["lang_select"] = value

    @property
    def pref(self) -> str:
        return st.session_state.get("pref_select", "全て")

    @pref.setter
    def pref(self, value: str) -> None:
        st.session_state["pref_select"] = value

    @property
    def filter_type(self) -> str:
        return st.session_state.get("filter_select", "すべて")

    @filter_type.setter
    def filter_type(self, value: str) -> None:
        st.session_state["filter_select"] = value

    @property
    def search_query(self) -> str:
        return st.session_state.get("search_input", "")

    @search_query.setter
    def search_query(self, value: str) -> None:
        st.session_state["search_input"] = value

    @property
    def gps_enabled(self) -> bool:
        return st.session_state.get("gps_enabled", False)

    @gps_enabled.setter
    def gps_enabled(self, value: bool) -> None:
        st.session_state["gps_enabled"] = value

    @property
    def dark_mode(self) -> bool:
        return st.session_state.get("dark_mode", False)

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        st.session_state["dark_mode"] = value

    @property
    def page(self) -> int:
        return st.session_state.get("page", 1)

    @page.setter
    def page(self, value: int) -> None:
        st.session_state["page"] = value

