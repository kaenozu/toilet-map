"""
tests/test_pagination.py
ui/pagination.py のユニットテスト
"""
import pytest
import pandas as pd
from ui.pagination import (
    calc_pagination, PER_PAGE,
)


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
