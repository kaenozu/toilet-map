"""
tests/test_streamlit_app.py
streamlit_app.py のエントリポイントテスト
"""


def test_module_imports_successfully():
    import streamlit_app
    assert hasattr(streamlit_app, "main")
