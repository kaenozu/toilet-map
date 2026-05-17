"""
tests/e2e/test_screenshots.py
Screenshot regression tests using Playwright.
Related: tests/e2e/test_smoke.py
"""
from pathlib import Path

import pytest
from playwright.sync_api import Page

SCREENSHOT_DIR = Path("tests/e2e/screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class TestScreenshotRegression:
    """Compare screenshots against baselines to detect visual regressions."""

    @pytest.mark.skip(reason="Baseline screenshots not yet committed")
    def test_full_page_screenshot(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        screenshot = page.screenshot(full_page=True)
        baseline = SCREENSHOT_DIR / "full_page.png"
        if baseline.exists():
            existing = baseline.read_bytes()
            size_ratio = len(screenshot) / len(existing)
            assert 0.95 <= size_ratio <= 1.05, (
                f"Screenshot size changed by {abs(1 - size_ratio) * 100:.1f}% "
                f"(baseline: {len(existing)} bytes, actual: {len(screenshot)} bytes)"
            )
        else:
            baseline.write_bytes(screenshot)
            pytest.skip("Baseline created. Re-run to compare.")

    @pytest.mark.skip(reason="Baseline screenshots not yet committed")
    def test_sidebar_screenshot(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(3000)
        sidebar = page.locator('[data-testid="stSidebar"]')
        screenshot = sidebar.screenshot()
        baseline = SCREENSHOT_DIR / "sidebar.png"
        if baseline.exists():
            size_ratio = len(screenshot) / len(baseline.read_bytes())
            assert 0.90 <= size_ratio <= 1.10
        else:
            baseline.write_bytes(screenshot)
            pytest.skip("Baseline created. Re-run to compare.")

    @pytest.mark.skip(reason="Baseline screenshots not yet committed")
    def test_map_screenshot(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        map_iframe = page.locator("iframe[title*='folium']")
        screenshot = map_iframe.screenshot()
        baseline = SCREENSHOT_DIR / "map.png"
        if baseline.exists():
            size_ratio = len(screenshot) / len(baseline.read_bytes())
            assert 0.90 <= size_ratio <= 1.10
        else:
            baseline.write_bytes(screenshot)
            pytest.skip("Baseline created. Re-run to compare.")
