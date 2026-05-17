"""
ui/analytics.py
Privacy-focused analytics integration (Plausible/Umami).
Related: app.py
"""
import streamlit as st


def inject_analytics() -> None:
    """Inject analytics scripts if configured via secrets or environment."""
    plausible_domain = _get_plausible_domain()
    umami_url = _get_umami_url()
    umami_id = _get_umami_id()

    if plausible_domain:
        st.markdown(
            f"""
            <script defer data-domain="{plausible_domain}"
            src="https://plausible.io/js/script.js"></script>
            """,
            unsafe_allow_html=True,
        )

    if umami_url and umami_id:
        st.markdown(
            f"""
            <script defer src="{umami_url}"
            data-website-id="{umami_id}"></script>
            """,
            unsafe_allow_html=True,
        )


def _get_plausible_domain() -> str:
    try:
        return st.secrets.get("analytics", {}).get("plausible_domain", "")
    except Exception:
        return ""


def _get_umami_url() -> str:
    try:
        return st.secrets.get("analytics", {}).get("umami_url", "")
    except Exception:
        return ""


def _get_umami_id() -> str:
    try:
        return st.secrets.get("analytics", {}).get("umami_website_id", "")
    except Exception:
        return ""
