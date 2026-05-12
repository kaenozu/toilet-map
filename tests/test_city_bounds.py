"""
tests/test_city_bounds.py
batch/city_bounds.py のユニットテスト
"""
import json
import pytest
from city_bounds import is_in_bounds, filter_raw_data


class TestIsInBounds:
    def test_point_inside_bounds(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, 139.5, bounds) is True

    def test_point_on_south_boundary(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.0, 139.5, bounds) is True

    def test_point_on_north_boundary(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(36.0, 139.5, bounds) is True

    def test_point_on_west_boundary(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, 139.0, bounds) is True

    def test_point_on_east_boundary(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, 140.0, bounds) is True

    def test_point_below_bounds(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(34.0, 139.5, bounds) is False

    def test_point_above_bounds(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(37.0, 139.5, bounds) is False

    def test_point_west_of_bounds(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, 138.0, bounds) is False

    def test_point_east_of_bounds(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, 141.0, bounds) is False

    def test_out_of_range_lat(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(999.0, 139.5, bounds) is False

    def test_out_of_range_lng(self):
        bounds = {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}
        assert is_in_bounds(35.5, -999.0, bounds) is False


class TestFilterRawData:
    def test_filter_by_city_name(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        entry = {"title": "A", "address": "東京都渋谷区", "latitude": 35.68, "longitude": 139.69}
        input_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        total, kept = filter_raw_data(str(input_path), str(output_path), "渋谷区")

        assert total == 1
        assert kept == 1

    def test_filter_by_coords_without_city(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        inside = {"title": "A", "address": "", "latitude": 35.5, "longitude": 139.5}
        outside = {"title": "B", "address": "", "latitude": 34.0, "longitude": 135.0}
        input_path.write_text(
            json.dumps(inside, ensure_ascii=False) + "\n" + json.dumps(outside, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        total, kept = filter_raw_data(
            str(input_path), str(output_path), "",
            bounds={"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0},
        )

        assert total == 2
        assert kept == 1
        content = output_path.read_text(encoding="utf-8").strip()
        assert json.dumps(inside, ensure_ascii=False) in content

    def test_empty_bounds_keeps_only_city_match(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        match = {"title": "A", "address": "東京都渋谷区", "latitude": 35.68, "longitude": 150.0}
        no_match = {"title": "B", "address": "大阪府大阪市", "latitude": 34.69, "longitude": 135.50}
        input_path.write_text(
            json.dumps(match, ensure_ascii=False) + "\n" + json.dumps(no_match, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        total, kept = filter_raw_data(str(input_path), str(output_path), "渋谷区")

        assert total == 2
        assert kept == 1

    def test_skips_empty_lines(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        input_path.write_text("\n\n", encoding="utf-8")

        total, kept = filter_raw_data(str(input_path), str(output_path), "渋谷区")

        assert total == 2
        assert kept == 0

    def test_skips_invalid_json(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        input_path.write_text("{invalid\n", encoding="utf-8")

        total, kept = filter_raw_data(str(input_path), str(output_path), "渋谷区")

        assert total == 1
        assert kept == 0

    def test_missing_lat_lng_skips_coord_match(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        entry = {"title": "A", "address": ""}
        input_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        total, kept = filter_raw_data(
            str(input_path), str(output_path), "",
            bounds={"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0},
        )

        assert total == 1
        assert kept == 0
