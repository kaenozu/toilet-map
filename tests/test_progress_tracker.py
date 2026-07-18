"""progress_tracker.py file-I/O tests."""

from progress_tracker import (
    load_progress,
    merge_part_files,
    publish_expansion_status,
    query_fingerprint,
    save_progress,
)


class TestLoadProgress:
    def test_returns_empty_for_missing_file(self, tmp_path):
        assert load_progress(str(tmp_path / "nonexistent")) == {}

    def test_loads_index_and_fingerprint(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("1\tabc\n3\tdef\n", encoding="utf-8")
        assert load_progress(str(path)) == {1: "abc", 3: "def"}

    def test_legacy_rows_are_loaded_as_stale(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("1\n\n3\n", encoding="utf-8")
        assert load_progress(str(path)) == {1: "", 3: ""}

    def test_invalid_rows_are_ignored(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("bad\tvalue\n2\tok\n", encoding="utf-8")
        assert load_progress(str(path)) == {2: "ok"}


class TestSaveProgress:
    def test_writes_sorted_rows_atomically(self, tmp_path):
        path = tmp_path / ".progress"
        save_progress({3: "c", 1: "a", 5: "e"}, str(path))
        assert path.read_text(encoding="utf-8") == "1\ta\n3\tc\n5\te\n"
        assert not (tmp_path / ".progress.tmp").exists()

    def test_empty_mapping(self, tmp_path):
        path = tmp_path / ".progress"
        save_progress({}, str(path))
        assert path.read_text(encoding="utf-8") == ""

    def test_fingerprint_changes_with_query(self):
        assert query_fingerprint("query1") != query_fingerprint("query2")


class TestPublishExpansionStatus:
    def test_calls_update_expansion_status(self, monkeypatch):
        calls = []
        monkeypatch.setattr("progress_tracker.update_expansion_status", lambda run_id, data: calls.append((run_id, data)))
        publish_expansion_status(
            "run_001", pref="東京都", city="千代田区", total=10, done=5,
            success=4, failed=1, started_at=1000.0, status="running", message="progress",
        )
        run_id, data = calls[0]
        assert run_id == "run_001"
        assert data["prefecture"] == "東京都"
        assert data["progress"]["completed_queries"] == 5


class TestMergePartFiles:
    def test_merges_all_parts_in_order(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for index in range(1, 4):
            (raw_dir / f"part_{index:03d}.json").write_text(f'{{"part": {index}}}\n', encoding="utf-8")
        output = tmp_path / "merged.json"
        merge_part_files(str(raw_dir), str(output), 3)
        content = output.read_text(encoding="utf-8")
        assert content.index('{"part": 1}') < content.index('{"part": 2}') < content.index('{"part": 3}')

    def test_skips_missing_parts(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "part_001.json").write_text('{"part": 1}\n', encoding="utf-8")
        (raw_dir / "part_003.json").write_text('{"part": 3}\n', encoding="utf-8")
        output = tmp_path / "merged.json"
        merge_part_files(str(raw_dir), str(output), 3)
        assert '{"part": 1}' in output.read_text(encoding="utf-8")
        assert '{"part": 3}' in output.read_text(encoding="utf-8")
