"""
tests/e2e/test_screenshots.py
Screenshot regression tests using Playwright.
Related: tests/e2e/test_smoke.py
"""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Page

SCREENSHOT_DIR = Path("tests/e2e/screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


def _image_signature(image_bytes: bytes) -> tuple[int, tuple[int, int]]:
    """Create a small perceptual signature for screenshot comparisons."""
    image = Image.open(BytesIO(image_bytes)).convert("L").resize((8, 8))
    # Pillow 14 removes getdata(); use get_flattened_data when available.
    pixels = list(image.get_flattened_data()) if hasattr(image, "get_flattened_data") else list(image.getdata())
    average = sum(pixels) / len(pixels)
    signature = 0
    for pixel in pixels:
        signature = (signature << 1) | int(pixel >= average)
    return signature, image.size


def _assert_screenshot_matches_baseline(screenshot: bytes, baseline: Path, max_distance: int = 10) -> None:
    existing = baseline.read_bytes()
    actual_signature, actual_size = _image_signature(screenshot)
    baseline_signature, baseline_size = _image_signature(existing)
    assert actual_size == baseline_size, (
        f"Screenshot dimensions changed: baseline={baseline_size}, actual={actual_size}"
    )
    distance = (actual_signature ^ baseline_signature).bit_count()
    assert distance <= max_distance, (
        f"Screenshot hash changed by {distance} bits (limit {max_distance})"
    )


def _assert_map_screenshot_matches_baseline(screenshot: bytes, baseline: Path) -> None:
    """Compare the map screenshot using dimensions only because tiles are dynamic."""
    existing = baseline.read_bytes()
    _, actual_size = _image_signature(screenshot)
    _, baseline_size = _image_signature(existing)
    assert actual_size == baseline_size, (
        f"Screenshot dimensions changed: baseline={baseline_size}, actual={actual_size}"
    )


def _update_or_compare_screenshot(
    screenshot: bytes,
    baseline: Path,
    update_screenshots: bool,
    compare_callback,
) -> None:
    existed_before = baseline.exists()
    if existed_before and not update_screenshots:
        compare_callback(screenshot, baseline)
        return

    baseline.write_bytes(screenshot)
    message = "Baseline updated. Re-run without --update-screenshots to compare." if existed_before else "Baseline created. Re-run to compare."
    pytest.skip(message)


class TestScreenshotRegression:
    """Compare screenshots against baselines to detect visual regressions."""

    def test_full_page_screenshot(self, streamlit_app, page: Page, update_screenshots: bool):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        screenshot = page.screenshot(full_page=True)
        baseline = SCREENSHOT_DIR / "full_page.png"
        _update_or_compare_screenshot(
            screenshot,
            baseline,
            update_screenshots,
            lambda current, existing: _assert_screenshot_matches_baseline(current, existing, max_distance=40),
        )

    def test_sidebar_screenshot(self, streamlit_app, page: Page, update_screenshots: bool):
        page.goto(streamlit_app)
        page.wait_for_timeout(3000)
        sidebar = page.locator('[data-testid="stSidebar"]')
        screenshot = sidebar.screenshot()
        baseline = SCREENSHOT_DIR / "sidebar.png"
        _update_or_compare_screenshot(screenshot, baseline, update_screenshots, _assert_screenshot_matches_baseline)

    def test_map_screenshot(self, streamlit_app, page: Page, update_screenshots: bool):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        map_iframe = page.locator("iframe[title*='folium']")
        screenshot = map_iframe.screenshot()
        baseline = SCREENSHOT_DIR / "map.png"
        _update_or_compare_screenshot(screenshot, baseline, update_screenshots, _assert_map_screenshot_matches_baseline)
