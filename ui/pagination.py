"""
ui/pagination.py
ページネーション状態管理
app.py から分離
"""
import streamlit as st

PER_PAGE = 20


def init_page_state() -> None:
    st.session_state.setdefault("page", 1)
    st.session_state.setdefault("page_filter_key", "")


def reset_page(filter_key: str) -> None:
    if "page_filter_key" in st.session_state and st.session_state.page_filter_key != filter_key:
        st.session_state.page = 1
    st.session_state.page_filter_key = filter_key


def calc_pagination(total: int, page: int) -> tuple[int, int, int, int]:
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, total)
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

