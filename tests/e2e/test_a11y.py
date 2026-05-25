"""
tests/e2e/test_a11y.py
Automated accessibility audit using axe-core via Playwright.
Related: app.py, ui/components.py
"""

from playwright.sync_api import Page


class TestAccessibility:
    def test_no_critical_violations(self, streamlit_app, page: Page):
        page.goto(streamlit_app)
        page.wait_for_timeout(5000)
        page.add_script_tag(url="https://cdn.jsdelivr.net/npm/axe-core/axe.min.js")
        page.wait_for_function("typeof window.axe !== 'undefined'")
        results = page.evaluate("""
        () => {
            const root = document.querySelector('[data-testid="stMain"]') || document.body;
            return window.axe.run(root, {
                runOnly: ['wcag2a', 'wcag2aa'],
                rules: { 'color-contrast': { enabled: false } }
            });
        }
        """)
        violations = results.get("violations", [])
        critical = [v for v in violations if v["impact"] in ("critical", "serious")]
        assert len(critical) == 0, (
            f"Found {len(critical)} critical/serious violations:\n"
            + "\n".join(f"- {v['help']} ({len(v['nodes'])} nodes)" for v in critical[:5])
        )
