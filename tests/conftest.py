"""
tests/conftest.py
Shared fixtures and configuration for test suite.
Related: tests/e2e/test_smoke.py, tests/e2e/test_a11y.py
"""

import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom test-suite options."""
    parser.addoption(
        "--update-screenshots",
        action="store_true",
        default=False,
        help="Overwrite screenshot baselines instead of comparing them",
    )


@pytest.fixture(scope="session")
def playwright():
    """Provide a shared Playwright driver for the test session."""
    with sync_playwright() as playwright_instance:
        yield playwright_instance


@pytest.fixture(scope="session")
def browser(playwright):
    """Launch a shared Chromium browser for E2E tests."""
    browser_instance = playwright.chromium.launch(headless=True)
    yield browser_instance
    browser_instance.close()


@pytest.fixture()
def context(browser):
    """Create an isolated browser context per test."""
    context_instance = browser.new_context(viewport={"width": 1440, "height": 1600})
    yield context_instance
    context_instance.close()


@pytest.fixture()
def page(context):
    """Create a fresh page per test."""
    page_instance = context.new_page()
    yield page_instance
    page_instance.close()


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app in background for E2E tests."""
    port = "18502"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            port,
            "--server.headless",
            "true",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://localhost:{port}"
    for _ in range(30):
        try:
            import urllib.request

            urllib.request.urlopen(f"{url}/_stcore/health")
            break
        except Exception:
            time.sleep(2)
    else:
        proc.kill()
        raise RuntimeError("Streamlit app failed to start")
    yield url
    proc.kill()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def update_screenshots(request: pytest.FixtureRequest) -> bool:
    """Return whether screenshot baselines should be regenerated."""
    return bool(request.config.getoption("--update-screenshots"))
