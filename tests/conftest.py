"""
tests/conftest.py
Shared fixtures and configuration for test suite.
Related: tests/e2e/test_smoke.py, tests/e2e/test_a11y.py
"""

import os

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
