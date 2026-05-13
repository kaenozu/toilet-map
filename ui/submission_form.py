"""
ui/submission_form.py
Streamlit form for user-submitted toilet data
"""
import json
import os
import time
import streamlit as st

SUBMISSIONS_PATH = "data/user_submissions.jsonl"

CATEGORY_OPTIONS = [
    "public",
    "convenience_store",
    "cafe",
    "hotel",
    "road_station",
    "other",
]


def _cat_labels(t: dict) -> dict[str, str]:
    return {
        "public": t["cat_public"],
        "convenience_store": t["cat_convenience"],
        "cafe": t["cat_cafe"],
        "hotel": t["cat_hotel"],
        "road_station": t["cat_roadstation"],
        "other": t["cat_other"],
    }


def save_submission(data: dict) -> None:
    os.makedirs(os.path.dirname(SUBMISSIONS_PATH), exist_ok=True)
    data["submitted_at"] = time.time()
    with open(SUBMISSIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def render_submission_form(t: dict) -> None:
    labels = _cat_labels(t)
    display_to_internal = {v: k for k, v in labels.items()}

    with st.expander(t["submit_title"], expanded=False):
        with st.form("submission_form", clear_on_submit=True):
            name = st.text_input(t["submit_name"], placeholder=t["submit_name_placeholder"])
            address = st.text_input(t["submit_address"], placeholder=t["submit_address_placeholder"])

            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input(t["submit_lat"], value=35.6762, format="%.6f", step=0.001)
            with col2:
                lng = st.number_input(t["submit_lng"], value=139.6503, format="%.6f", step=0.001)

            cat_display = st.selectbox(t["submit_category"], list(display_to_internal.keys()))

            submitted = st.form_submit_button(t["submit_button"])

            if submitted:
                if not name.strip():
                    st.error(t["submit_error_name"])
                    return
                internal_cat = display_to_internal[cat_display]
                submission = {
                    "title": name.strip(),
                    "address": address.strip(),
                    "lat": lat,
                    "lng": lng,
                    "category": internal_cat,
                    "is_public_toilet": internal_cat == "public",
                }
                save_submission(submission)
                st.success(t["submit_success"])
