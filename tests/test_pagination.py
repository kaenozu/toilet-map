"""
tests/test_pagination.py
ui/pagination.py のユニットテスト
"""
import pytest

from ui.pagination import (
    PER_PAGE,
    calc_pagination,
    init_page_state,
    reset_page,
)


class FakeSessionState:
    """reset_page / init_page_state のテスト用に dict + attribute アクセスを模倣"""
    def __init__(self, initial: dict | None = None):
        self._data = dict(initial or {})
    def setdefault(self, key, value):
        return self._data.setdefault(key, value)
    def get(self, key, default=None):
        return self._data.get(key, default)
    def __contains__(self, key):
        return key in self._data
    def __getattr__(self, key):
        if key.startswith("_"):
            return super().__getattribute__(key)
        if key in self._data:
            return self._data[key]
        raise AttributeError(key)
    def __setattr__(self, key, value):
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self._data[key] = value


class TestPageStateManagement:
    def test_init_page_state_sets_default_page(self, monkeypatch):
        fake = FakeSessionState()
        monkeypatch.setattr("streamlit.session_state", fake)
        init_page_state()
        assert fake.get("page") == 1

    def test_init_page_state_does_not_overwrite_page(self, monkeypatch):
        fake = FakeSessionState({"page": 5})
        monkeypatch.setattr("streamlit.session_state", fake)
        init_page_state()
        assert fake.get("page") == 5

    def test_reset_page_keeps_page_on_same_filter_key(self, monkeypatch):
        fake = FakeSessionState({"page": 3, "page_filter_key": "東京|None|"})
        monkeypatch.setattr("streamlit.session_state", fake)
        reset_page("東京|None|")
        assert fake.get("page") == 3

    def test_reset_page_resets_on_filter_key_change(self, monkeypatch):
        fake = FakeSessionState({"page": 3, "page_filter_key": "大阪|None|"})
        monkeypatch.setattr("streamlit.session_state", fake)
        reset_page("東京|None|")
        assert fake.get("page") == 1
        assert fake.get("page_filter_key") == "東京|None|"

    def test_reset_page_does_not_reset_on_first_call(self, monkeypatch):
        fake = FakeSessionState()
        monkeypatch.setattr("streamlit.session_state", fake)
        reset_page("東京|None|")
        assert fake.get("page", "not set") == "not set"


class TestCalcPagination:
    def test_first_page(self):
        total_pages, start, end, page = calc_pagination(50, 1)
        assert total_pages == 3
        assert start == 0
        assert end == 20

    def test_last_page_partial(self):
        total_pages, start, end, page = calc_pagination(25, 2)
        assert total_pages == 2
        assert start == 20
        assert end == 25

    def test_single_page(self):
        total_pages, start, end, page = calc_pagination(10, 1)
        assert total_pages == 1
        assert start == 0
        assert end == 10

    def test_zero_items(self):
        total_pages, start, end, page = calc_pagination(0, 1)
        assert total_pages == 1
        assert start == 0
        assert end == 0

    def test_exact_multiple(self):
        total_pages, start, end, page = calc_pagination(40, 2)
        assert total_pages == 2
        assert start == 20
        assert end == 40

    def test_per_page_value(self):
        assert PER_PAGE == 20

    def test_large_dataset(self):
        total_pages, start, end, page = calc_pagination(1000, 5)
        assert total_pages == 50
        assert start == 80
        assert end == 100

    def test_page_beyond_total(self):
        total_pages, start, end, page = calc_pagination(10, 5)
        assert total_pages == 1
        assert start == 80
        assert end == 10
        assert page == 5  # calc_pagination does not clamp; caller must handle

    def test_boundary_values(self):
        """境界値のテスト"""
        # 1件だけ
        total_pages, start, end, page = calc_pagination(1, 1)
        assert total_pages == 1
        assert start == 0
        assert end == 1

        # 20件ちょうど（PER_PAGEと一致）
        total_pages, start, end, page = calc_pagination(20, 1)
        assert total_pages == 1
        assert start == 0
        assert end == 20

        # 21件（2ページ目ができる）
        total_pages, start, end, page = calc_pagination(21, 1)
        assert total_pages == 2
        assert start == 0
        assert end == 20

        total_pages, start, end, page = calc_pagination(21, 2)
        assert start == 20
        assert end == 21

    def test_page_zero_returns_negative_start(self):
        """page=0 は負のstart_idxになる（callerが制御する想定）"""
        total_pages, start, end, page = calc_pagination(20, 0)
        assert start == -20
        assert end == 0

    def test_very_large_page_number(self):
        total_pages, start, end, page = calc_pagination(100, 999)
        assert start == 19960
        assert end == 100


class FakeColumn:
    """st.columns() が返すモックカラム（with文対応）"""
    def __init__(self):
        self.markdown_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def markdown(self, text, **kwargs):
        self.markdown_calls.append((text, kwargs))


class TestRenderPagination:
    def test_skips_when_total_is_zero(self, monkeypatch):
        from ui.pagination import render_pagination
        caption_calls = []
        monkeypatch.setattr("streamlit.caption", lambda *a, **kw: caption_calls.append(a))
        render_pagination(0, 1, 1, {})
        assert caption_calls == []

    def test_shows_single_page_caption(self, monkeypatch):
        from ui.pagination import render_pagination
        caption_calls = []
        monkeypatch.setattr("streamlit.caption", lambda *a, **kw: caption_calls.append(a))
        render_pagination(10, 1, 1, {"page": "Page"})
        assert caption_calls == [("Page 1/1",)]

    def test_renders_columns_and_buttons_on_multi_page(self, monkeypatch):
        from ui.pagination import render_pagination
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)
        monkeypatch.setattr("streamlit.session_state", FakeSessionState({"page": 2}))

        button_calls = []

        def fake_button(label, **kwargs):
            button_calls.append((label, kwargs))
            return False

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        render_pagination(50, 2, 3, {"page": "Page", "prev": "<", "next": ">"})

        labels = [c[0] for c in button_calls]
        assert "<" in labels
        assert ">" in labels

    def test_prev_disabled_on_first_page(self, monkeypatch):
        from ui.pagination import render_pagination
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)
        monkeypatch.setattr("streamlit.session_state", FakeSessionState({"page": 1}))

        button_disabled = {}

        def fake_button(label, **kwargs):
            button_disabled[label] = kwargs.get("disabled", False)
            return False

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        render_pagination(50, 1, 3, {"page": "Page", "prev": "<", "next": ">"})

        assert button_disabled["<"] is True
        assert button_disabled[">"] is False

    def test_next_disabled_on_last_page(self, monkeypatch):
        from ui.pagination import render_pagination
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)
        monkeypatch.setattr("streamlit.session_state", FakeSessionState({"page": 3}))

        button_disabled = {}

        def fake_button(label, **kwargs):
            button_disabled[label] = kwargs.get("disabled", False)
            return False

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        render_pagination(50, 3, 3, {"page": "Page", "prev": "<", "next": ">"})

        assert button_disabled["<"] is False
        assert button_disabled[">"] is True

    def test_prev_click_sets_page_and_reruns(self, monkeypatch):
        from ui.pagination import render_pagination
        fake_session = FakeSessionState({"page": 3})
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)

        button_return = {"pagination_prev": True, "pagination_next": False}

        def fake_button(label, **kwargs):
            key = kwargs.get("key")
            return button_return.get(key, False)

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.session_state", fake_session)
        rerun_calls = []
        monkeypatch.setattr("streamlit.rerun", lambda: rerun_calls.append(1))

        render_pagination(50, 3, 3, {"page": "Page", "prev": "<", "next": ">"})

        assert fake_session.page == 2
        assert len(rerun_calls) == 1

    def test_next_click_sets_page_and_reruns(self, monkeypatch):
        from ui.pagination import render_pagination
        fake_session = FakeSessionState({"page": 1})
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)

        button_return = {"pagination_prev": False, "pagination_next": True}

        def fake_button(label, **kwargs):
            key = kwargs.get("key")
            return button_return.get(key, False)

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.session_state", fake_session)
        rerun_calls = []
        monkeypatch.setattr("streamlit.rerun", lambda: rerun_calls.append(1))

        render_pagination(50, 1, 3, {"page": "Page", "prev": "<", "next": ">"})

        assert fake_session.page == 2
        assert len(rerun_calls) == 1

    def test_info_col_shows_page_info(self, monkeypatch):
        from ui.pagination import render_pagination
        columns = [FakeColumn(), FakeColumn(), FakeColumn()]
        monkeypatch.setattr("streamlit.columns", lambda *a, **kw: columns)
        monkeypatch.setattr("streamlit.session_state", FakeSessionState({"page": 2}))

        markdown_calls = []

        def fake_button(label, **kwargs):
            return False

        def fake_markdown(text, **kwargs):
            markdown_calls.append(text)

        monkeypatch.setattr("streamlit.button", fake_button)
        monkeypatch.setattr("streamlit.markdown", fake_markdown)
        monkeypatch.setattr("streamlit.rerun", lambda: None)

        render_pagination(50, 2, 5, {"page": "Page", "prev": "<", "next": ">"})

        assert len(markdown_calls) == 1
        assert "Page 2/5" in markdown_calls[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
