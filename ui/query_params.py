"""
ui/query_params.py
URL query parameter handling for Streamlit app.
"""
import streamlit as st
from ui.i18n import LANGUAGE_CODE_TO_LABEL, LANGUAGE_OPTIONS


def normalize_query_params(raw_params: dict) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_params.items():
        if isinstance(value, list):
            normalized[key] = str(value[0]) if value else ""
        else:
            normalized[key] = str(value or "")
    return normalized


def read_query_params() -> dict[str, str]:
    query_params = getattr(st, "query_params", None)
    if query_params is not None:
        return normalize_query_params(dict(query_params))
    getter = getattr(st, "experimental_get_query_params", None)
    if getter is None:
        return {}
    return normalize_query_params(getter())


def write_query_params(params: dict[str, str]) -> None:
    query_params = getattr(st, "query_params", None)
    if query_params is not None:
        query_params.clear()
        for key, value in params.items():
            query_params[key] = str(value)
        return
    setter = getattr(st, "experimental_set_query_params", None)
    if setter is not None:
        setter(**params)


def apply_language_query_param(query_params: dict[str, str]) -> None:
    lang_code = query_params.get("lang", "")
    if lang_code in LANGUAGE_CODE_TO_LABEL:
        st.session_state["lang_select"] = LANGUAGE_CODE_TO_LABEL[lang_code]


LANGUAGE_LABEL_TO_CODE = {label: code for code, label in LANGUAGE_CODE_TO_LABEL.items()}


def resolve_ui_state_from_query_params(
    query_params: dict[str, str],
    prefectures: list[str],
    translated_to_internal: dict,
    t: dict[str, str],
) -> dict[str, object]:
    state: dict[str, object] = {}
    reverse_filter_map = {internal: display for display, internal in translated_to_internal.items()}

    pref = query_params.get("pref", "")
    if pref in prefectures:
        state["pref_select"] = pref

    filter_key = query_params.get("filter", "")
    if filter_key in reverse_filter_map:
        state["filter_select"] = reverse_filter_map[filter_key]

    search_query = query_params.get("search", "")
    if search_query:
        state["search_input"] = search_query

    gps_enabled = query_params.get("gps", "")
    if gps_enabled in {"0", "1"}:
        state["gps_enabled"] = gps_enabled == "1"

    sort_key = query_params.get("sort", "")
    sort_label_map = {"clean": t["sort_clean"], "near": t["sort_near"]}
    if sort_key in sort_label_map:
        state["sort_select"] = sort_label_map[sort_key]

    page_value = query_params.get("page", "")
    try:
        page_number = int(page_value)
    except ValueError:
        page_number = 0
    if page_number > 0:
        state["page"] = page_number

    return state


def build_query_params_from_state(
    lang: str,
    selected_pref: str,
    filter_key: str,
    search_query: str,
    sort_order: str,
    gps_enabled: bool,
    page: int,
    t: dict[str, str],
) -> dict[str, str]:
    params: dict[str, str] = {}

    if lang_code := LANGUAGE_LABEL_TO_CODE.get(lang):
        params["lang"] = lang_code
    if selected_pref:
        params["pref"] = selected_pref
    if filter_key:
        params["filter"] = filter_key
    if search_query:
        params["search"] = search_query

    params["sort"] = "near" if sort_order == t["sort_near"] else "clean"
    params["gps"] = "1" if gps_enabled else "0"
    params["page"] = str(max(1, page))
    return params
