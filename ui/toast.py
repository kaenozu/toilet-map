"""
ui/toast.py
Ephemeral toast notification system using st.toast (Streamlit 1.36+)
Related: app.py, ui/data_loader.py
"""
import streamlit as st


def show_toast(message: str, icon: str = "ℹ️") -> None:
    st.toast(message, icon=icon)
