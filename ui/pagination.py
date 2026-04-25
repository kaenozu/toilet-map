"""
ui/pagination.py
ページネーションUI・CSVエクスポート
app.py から分離
"""
import streamlit as st
import pandas as pd


PER_PAGE = 20


def calc_pagination(total: int, page: int) -> tuple[int, int, int, int]:
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, total)
    return total_pages, start_idx, end_idx, page


def init_page_state():
    if "page" not in st.session_state:
        st.session_state.page = 1
    if "last_filter_key" not in st.session_state:
        st.session_state.last_filter_key = ""


def reset_page(filter_key: str):
    if st.session_state.get("last_filter_key", "") != filter_key:
        st.session_state.page = 1
        st.session_state.last_filter_key = filter_key


def render_pagination(total: int, page: int, total_pages: int):
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        prev_disabled = page <= 1
        if st.button("◀ 前へ", disabled=prev_disabled, use_container_width=True):
            st.session_state.page = max(1, page - 1)
            st.rerun()
    with col_page:
        st.markdown(
            f"<div style='text-align:center;padding:4px;font-size:14px;font-weight:600;'>"
            f"ページ {page}/{total_pages}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        next_disabled = page >= total_pages
        if st.button("次へ ▶", disabled=next_disabled, use_container_width=True):
            st.session_state.page = min(total_pages, page + 1)
            st.rerun()


def render_csv_export(filtered: pd.DataFrame, selected_pref: str, filter_type: str):
    if len(filtered) > 0:
        csv = filtered.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv,
            file_name=f"toilet_map_{selected_pref}_{filter_type}.csv",
            mime="text/csv",
            use_container_width=True,
        )