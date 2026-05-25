"""
tests/visual/test_components.py
Individual component screenshot previews for visual inspection.
Related: ui/components.py, ui/popups.py, tests/e2e/test_screenshots.py
"""
from pathlib import Path

from playwright.sync_api import Page

SCREENSHOT_DIR = Path("tests/visual/screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class TestComponentPreviews:
    """Render individual components and capture screenshots."""

    def test_toilet_card_preview(self, page: Page):
        page.set_content("""
        <html><body>
        <div class="toilet-card" role="listitem" tabindex="0"
             style="border:1px solid #ddd;border-radius:8px;padding:12px;margin:16px;
                    font-family:sans-serif;max-width:400px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <strong>サンプル駅前トイレ</strong>
            <span style="font-weight:800;font-size:18px;color:#27ae60;">✨ 85点</span>
          </div>
          <div style="color:#888;font-size:11px;margin:4px 0;">📍 東京都千代田区丸の内1-1</div>
          <div style="display:flex;gap:4px;flex-wrap:wrap;margin:6px 0;">
            <span style="background:#e8f5e9;padding:2px 6px;border-radius:4px;font-size:10px;">🧻 清潔</span>
            <span style="background:#e3f2fd;padding:2px 6px;border-radius:4px;font-size:10px;">🚻 多目的</span>
          </div>
          <div style="color:#555;font-size:11px;">⭐ 4.2 (120件) | 信頼度 95%</div>
        </div>
        </body></html>
        """)
        card = page.locator(".toilet-card")
        card.screenshot(path=str(SCREENSHOT_DIR / "toilet-card.png"))

    def test_score_legend_preview(self, page: Page):
        page.set_content("""
        <html><body style="font-family:sans-serif;">
        <div style="display:flex;align-items:center;gap:4px;font-size:12px;margin:16px;">
            <span role="img" aria-label="low score">💩</span>
            <div style="width:200px;height:14px;border-radius:7px;
                background:linear-gradient(to right,#e74c3c,#f39c12,#f1c40f,#2ecc71,#27ae60);"></div>
            <span role="img" aria-label="high score">✨</span>
        </div>
        </body></html>
        """)
        legend = page.locator("div[style*='display:flex']")
        legend.screenshot(path=str(SCREENSHOT_DIR / "score-legend.png"))

    def test_pagination_preview(self, page: Page):
        page.set_content("""
        <html><body style="font-family:sans-serif;">
        <div style="display:flex;gap:8px;align-items:center;justify-content:center;padding:16px;">
            <button style="padding:4px 16px;border:1px solid #ddd;border-radius:4px;background:#fff;cursor:pointer;">‹ 前へ</button>
            <span style="font-weight:600;">Page 1/3</span>
            <button style="padding:4px 16px;border:1px solid #ddd;border-radius:4px;background:#1a73e8;color:#fff;cursor:pointer;">次へ ›</button>
        </div>
        </body></html>
        """)
        pagination = page.locator("div[style*='display:flex']")
        pagination.screenshot(path=str(SCREENSHOT_DIR / "pagination.png"))
