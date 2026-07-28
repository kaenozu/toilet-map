"""Versioned PostgreSQL migration runner with checksum validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .db_types import DbConnection

MIGRATION_LOCK_ID = 8_764_210_631


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str
    sql: str


def migration_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"


def discover_migrations(directory: Path | None = None) -> list[Migration]:
    root = directory or migration_directory()
    migrations: list[Migration] = []
    for path in sorted(root.glob("*.sql")):
        version, separator, name = path.stem.partition("_")
        if not separator or not version.isdigit():
            raise ValueError(f"invalid migration filename: {path.name}")
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        migrations.append(Migration(version, name, path, checksum, sql))
    if not migrations:
        raise RuntimeError(f"no migrations found in {root}")
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("duplicate migration versions")
    return migrations


def ensure_migration_table(connection: DbConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          checksum TEXT NOT NULL,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def applied_migrations(connection: DbConnection) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {str(row["version"]): dict(row) for row in rows}


def apply_migrations(connection: DbConnection, directory: Path | None = None) -> list[str]:
    """Apply pending migrations atomically while rejecting edited history."""
    ensure_migration_table(connection)
    connection.commit()
    connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
    try:
        applied = applied_migrations(connection)
        newly_applied: list[str] = []
        for migration in discover_migrations(directory):
            previous = applied.get(migration.version)
            if previous is not None:
                if previous["checksum"] != migration.checksum:
                    raise RuntimeError(
                        f"migration {migration.version} checksum changed after application"
                    )
                continue
            try:
                connection.execute(migration.sql)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, checksum)
                    VALUES (%s, %s, %s)
                    """,
                    (migration.version, migration.name, migration.checksum),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            newly_applied.append(migration.version)
        return newly_applied
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))
        connection.commit()
