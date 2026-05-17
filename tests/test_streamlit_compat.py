"""
tests/test_streamlit_compat.py
Detect breaking changes from future Streamlit versions.
Related: app.py, requirements-app.txt
"""
import importlib.metadata

import pytest


class TestStreamlitCompat:
    def test_streamlit_installed(self):
        """Verify Streamlit is installed."""
        ver = importlib.metadata.version("streamlit")
        assert ver, "Streamlit not installed"

    def test_streamlit_version_within_range(self):
        """Check Streamlit version is within supported range."""
        from packaging.version import Version
        ver = Version(importlib.metadata.version("streamlit"))
        assert ver.major == 1, f"Expected Streamlit major version 1, got {ver.major}"
        assert ver.minor >= 36, f"Need Streamlit >= 1.36, got {ver}"

    def test_streamlit_no_deprecated_api_calls(self):
        """Scan app code for known deprecated Streamlit APIs."""
        import ast
        import pathlib
        deprecated_apis = {
            "st.cache": "Use st.cache_data or st.cache_resource",
            "st.empty": "Consider alternatives",
            "st.beta_": "Beta APIs are removed",
        }
        app_path = pathlib.Path("app.py")
        tree = ast.parse(app_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and hasattr(node.func, 'attr'):
                full_name = f"st.{node.func.attr}"
                for old, hint in deprecated_apis.items():
                    if old in full_name:
                        pytest.fail(f"Deprecated API {full_name} in app.py: {hint}")
