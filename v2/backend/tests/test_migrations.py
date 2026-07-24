"""Migration discovery and checksum tests."""

from pathlib import Path

from app.migrations import discover_migrations


def test_migrations_are_versioned_and_ordered(tmp_path: Path) -> None:
    (tmp_path / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    migrations = discover_migrations(tmp_path)
    assert [migration.version for migration in migrations] == ["0001", "0002"]
    assert len(migrations[0].checksum) == 64
