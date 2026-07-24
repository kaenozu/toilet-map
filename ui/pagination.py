"""Pagination state and SQL offset helpers."""

from __future__ import annotations

import streamlit as st

PER_PAGE = 20


def init_page_state() -> None:
    st.session_state.setdefault("page", 1)
    st.session_state.setdefault("page_filter_key", "")


def reset_page(filter_key: str) -> None:
    if "page_filter_key" in st.session_state and st.session_state.page_filter_key != filter_key:
        st.session_state.page = 1
    st.session_state.page_filter_key = filter_key


def normalize_page(page: int, total_pages: int) -> int:
    return min(max(1, int(page)), max(1, int(total_pages)))


def calc_offset(page: int, per_page: int = PER_PAGE) -> int:
    return (max(1, int(page)) - 1) * max(1, int(per_page))


def calc_pagination(total: int, page: int, per_page: int = PER_PAGE) -> tuple[int, int, int, int]:
    safe_per_page = max(1, per_page)
    total_pages = max(1, (total + safe_per_page - 1) // safe_per_page)
    start_idx = (page - 1) * safe_per_page
    end_idx = min(start_idx + safe_per_page, total)
    return total_pages, start_idx, end_idx, page


def render_pagination(total: int, page: int, total_pages: int, t: dict[str, str]) -> None:
    if total <= 0:
        return
    if total_pages <= 1:
        st.caption(f"{t['page']} 1/1")
        return

    prev_col, info_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if st.button(t["prev"], disabled=page <= 1, key="pagination_prev", use_container_width=True):
            st.session_state.page = max(1, page - 1)
            st.rerun()
    with info_col:
        st.markdown(
            f"<div style='text-align:center; padding-top:0.45rem; font-weight:600;'>{t['page']} {page}/{total_pages}</div>",
            unsafe_allow_html=True,
        )
    with next_col:
        if st.button(t["next"], disabled=page >= total_pages, key="pagination_next", use_container_width=True):
            st.session_state.page = min(total_pages, page + 1)
            st.rerun()
