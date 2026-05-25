"""
tests/test_generate_queries.py
generate_queries.py のユニットテスト
"""
import json

import pytest
from generate_queries import (
    BATCH_SIZE,
    PREFECTURE_QUERY_TEMPLATES,
    _dedupe_queries,
    build_queries,
    load_prefectures,
    main,
    write_batches,
)


class TestLoadPrefectures:
    def test_loads_json(self, tmp_path, monkeypatch):
        data = {"東京都": ["千代田区", "新宿区"], "大阪府": ["大阪市"]}
        f = tmp_path / "prefecture_cities.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr("generate_queries.DATA_FILE", str(f))
        assert load_prefectures() == data

    def test_raises_on_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("generate_queries.DATA_FILE", str(tmp_path / "nope.json"))
        with pytest.raises(FileNotFoundError):
            load_prefectures()


class TestDedupeQueries:
    def test_removes_duplicates(self):
        queries = ["q1", "q2", "q1", "q3"]
        assert _dedupe_queries(queries) == ["q1", "q2", "q3"]

    def test_empty_list(self):
        assert _dedupe_queries([]) == []


class TestBuildQueries:
    def test_uses_city_template(self):
        queries = build_queries(["東京"], ["トイレ in {city}"])
        assert queries == ["トイレ in 東京"]

    def test_uses_prefecture_template(self):
        queries = build_queries(["東京都"], PREFECTURE_QUERY_TEMPLATES)
        assert "公共トイレ in 東京都" in queries

    def test_deduplicates_across_locations(self):
        queries = build_queries(["東京", "東京"], ["トイレ in {city}"])
        assert queries == ["トイレ in 東京"]


class TestWriteBatches:
    def test_writes_files_with_headers(self, tmp_path):
        queries = [f"q{i}" for i in range(BATCH_SIZE * 2 + 1)]
        n = write_batches(queries, str(tmp_path), city="東京", prefecture="東京都", start_index=1)
        assert n == 3  # 25 queries / 12 per batch = 3 files
        files = sorted(tmp_path.iterdir())
        assert len(files) == 3
        for _i, f in enumerate(files):
            content = f.read_text(encoding="utf-8")
            assert "# city: 東京" in content
            assert "# prefecture: 東京都" in content

    def test_start_index_controls_filename(self, tmp_path):
        queries = ["q1", "q2"]
        write_batches(queries, str(tmp_path), start_index=5, city="大阪")
        assert (tmp_path / "batch_005.txt").exists()

    def test_no_headers_when_city_and_prefecture_empty(self, tmp_path):
        queries = ["q1"]
        write_batches(queries, str(tmp_path))
        content = (tmp_path / "batch_001.txt").read_text(encoding="utf-8")
        assert "# city:" not in content
        assert "# prefecture:" not in content

    def test_deduplicates_before_writing(self, tmp_path):
        queries = ["q1", "q1", "q2"]
        write_batches(queries, str(tmp_path))
        content = (tmp_path / "batch_001.txt").read_text(encoding="utf-8")
        lines = [ln for ln in content.split("\n") if ln.strip() and not ln.startswith("#")]
        assert lines == ["q1", "q2"]


class TestMain:
    def test_invokes_pipeline(self, tmp_path, monkeypatch):
        monkeypatch.setattr("generate_queries.QUERIES_DIR", str(tmp_path / "queries.d"))

        prefectures = {"東京都": ["千代田区"]}
        monkeypatch.setattr("generate_queries.load_prefectures", lambda: prefectures)
        monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

        main()

        pref_dir = tmp_path / "queries.d" / "東京都"
        assert pref_dir.is_dir()
        files = list(pref_dir.iterdir())
        assert len(files) > 0

    def test_empty_prefectures(self, tmp_path, monkeypatch):
        monkeypatch.setattr("generate_queries.QUERIES_DIR", str(tmp_path / "queries.d"))
        monkeypatch.setattr("generate_queries.load_prefectures", lambda: {})
        monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

        main()

        assert (tmp_path / "queries.d").is_dir()


class TestBatchSizeConstant:
    def test_batch_size(self):
        assert BATCH_SIZE == 12


class TestQueryTemplatesAlias:
    def test_is_independent_copy(self):
        from generate_queries import CITY_QUERY_TEMPLATES, QUERY_TEMPLATES
        original_len = len(QUERY_TEMPLATES)
        QUERY_TEMPLATES.append("__test_dummy__")
        assert len(QUERY_TEMPLATES) == original_len + 1
        assert len(CITY_QUERY_TEMPLATES) == original_len
        QUERY_TEMPLATES.pop()
