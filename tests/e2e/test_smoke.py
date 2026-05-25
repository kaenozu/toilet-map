"""
tests/e2e/test_smoke.py
Playwright E2E end-to-end test for Streamlit app.
Related: app.py, ui/sidebar.py, ui/pagination.py
"""

from playwright.sync_api import Page, expect

from ui.i18n import APP_TITLE


class TestSmoke:
    def test_title_displayed(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_function("document.title !== 'Streamlit'")
        expect(page).to_have_title(APP_TITLE)

    def test_sidebar_renders(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        sidebar = page.locator('[data-testid="stSidebar"]')
        expect(sidebar).to_be_visible()

    def test_map_renders(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        map_selector = "iframe[src*='streamlit_folium'], iframe[title*='folium']"
        page.wait_for_selector(map_selector, state="attached", timeout=30000)
        assert page.locator(map_selector).count() >= 1

    def test_filter_selectable(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        filter_select = page.locator('[data-testid="stSelectbox"]').first
        expect(filter_select).to_be_visible()

    def test_pagination_renders_with_data(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        buttons = page.locator("button:has-text('次へ')")
        expect(buttons.first).to_be_visible(timeout=15000)
