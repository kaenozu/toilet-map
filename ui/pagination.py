"""
ui/pagination.py
ページネーション状態管理
app.py から分離
"""
import streamlit as st


PER_PAGE = 20


def calc_pagination(total: int, page: int) -> tuple[int, int, int, int]:
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, total)
    return total_pages, start_idx, end_idx, page

