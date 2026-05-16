"""
tests/test_progress_tracker.py
progress_tracker.py のユニットテスト（ファイルI/O）
"""
from progress_tracker import (
    load_progress,
    merge_part_files,
    publish_expansion_status,
    save_progress,
)


class TestLoadProgress:
    def test_returns_empty_set_for_missing_file(self, tmp_path):
        assert load_progress(str(tmp_path / "nonexistent")) == set()

    def test_loads_integers(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("1\n3\n5\n", encoding="utf-8")
        assert load_progress(str(path)) == {1, 3, 5}

    def test_skips_empty_lines(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("1\n\n3\n", encoding="utf-8")
        assert load_progress(str(path)) == {1, 3}

    def test_empty_file(self, tmp_path):
        path = tmp_path / ".progress"
        path.write_text("", encoding="utf-8")
        assert load_progress(str(path)) == set()


class TestSaveProgress:
    def test_writes_sorted_integers(self, tmp_path):
        path = tmp_path / ".progress"
        save_progress({3, 1, 5}, str(path))
        content = path.read_text(encoding="utf-8")
        assert content == "1\n3\n5\n"

    def test_empty_set(self, tmp_path):
        path = tmp_path / ".progress"
        save_progress(set(), str(path))
        assert path.read_text(encoding="utf-8") == ""


class TestPublishExpansionStatus:
    def test_calls_update_expansion_status(self, monkeypatch):
        calls = []

        def fake_update(run_id, data):
            calls.append((run_id, data))

        monkeypatch.setattr("progress_tracker.update_expansion_status", fake_update)

        publish_expansion_status(
            "run_001",
            pref="東京都", city="千代田区",
            total=10, done=5, success=4, failed=1,
            started_at=1000.0, status="running", message="progress",
        )

        assert len(calls) == 1
        run_id, data = calls[0]
        assert run_id == "run_001"
        assert data["prefecture"] == "東京都"
        assert data["city"] == "千代田区"
        assert data["status"] == "running"
        assert data["progress"]["completed_queries"] == 5


class TestMergePartFiles:
    def test_merges_all_parts_in_order(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for i in range(1, 4):
            (raw_dir / f"part_{i:03d}.json").write_text(f'{{"part": {i}}}\n', encoding="utf-8")

        output = tmp_path / "merged.json"
        merge_part_files(str(raw_dir), str(output), 3)

        content = output.read_text(encoding="utf-8")
        assert '{"part": 1}' in content
        assert '{"part": 2}' in content
        assert '{"part": 3}' in content

    def test_skips_missing_parts(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "part_001.json").write_text('{"part": 1}\n', encoding="utf-8")
        (raw_dir / "part_003.json").write_text('{"part": 3}\n', encoding="utf-8")

        output = tmp_path / "merged.json"
        merge_part_files(str(raw_dir), str(output), 3)

        content = output.read_text(encoding="utf-8")
        assert '{"part": 1}' in content
        assert '{"part": 3}' in content
