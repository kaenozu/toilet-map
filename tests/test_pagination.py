"""
tests/test_pagination.py
ui/pagination.py のユニットテスト
"""
import pytest
from ui.pagination import (
    calc_pagination, init_page_state, reset_page, PER_PAGE,
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
