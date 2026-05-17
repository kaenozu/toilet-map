"""
ui/reviews.py
Simple user review submission form for toilet-map.
Related: app.py, data/reviews.db
"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

REVIEWS_DB = Path("data/reviews.db")


def _ensure_table():
    conn = sqlite3.connect(str(REVIEWS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id TEXT,
            rating INTEGER CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def render_review_form(place_id: str, place_title: str) -> None:
    """Render a simple review submission form."""
    _ensure_table()
    with st.expander(f"\U0001f4ac {place_title} にレビューを書く", expanded=False):
        rating = st.slider("評価", 1, 5, 3, key=f"rating_{place_id}")
        comment = st.text_area("コメント（任意）", max_chars=200, key=f"comment_{place_id}")
        if st.button("送信", key=f"submit_{place_id}"):
            try:
                conn = sqlite3.connect(str(REVIEWS_DB))
                conn.execute(
                    "INSERT INTO reviews (place_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
                    (place_id, rating, comment, datetime.now(UTC).isoformat()),
                )
                conn.commit()
                conn.close()
                st.success("レビューを送信しました！")
            except Exception as e:
                st.error(f"送信に失敗しました: {e}")
