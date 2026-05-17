"""
tests/e2e/test_smoke.py
Playwright E2E end-to-end test for Streamlit app.
Related: app.py, ui/sidebar.py, ui/pagination.py
"""

import subprocess
import sys
import time

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app in background for E2E tests."""
    port = "18502"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", port, "--server.headless", "true"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


class TestSmoke:
    def test_title_displayed(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        expect(page).to_have_title("トイレきれい度マップ")

    def test_sidebar_renders(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        sidebar = page.locator('[data-testid="stSidebar"]')
        expect(sidebar).to_be_visible()

    def test_map_renders(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        map_el = page.locator("iframe[title*='folium']")
        expect(map_el).to_be_visible(timeout=15000)

    def test_filter_selectable(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        filter_select = page.locator('[data-testid="stSelectbox"]').first
        expect(filter_select).to_be_visible()

    def test_pagination_renders_with_data(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        buttons = page.locator("button:has-text('次へ')")
        expect(buttons.first).to_be_visible(timeout=15000)
