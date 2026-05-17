"""
batch/backup_db.py
Automatic SQLite database backup with generation management.
Related: data/toilets.db, app_config.py
"""
import shutil
from datetime import UTC, datetime
from pathlib import Path

from app_config import DB_PATH

BACKUP_DIR = Path("data/backups")
MAX_BACKUPS = 14  # Keep 2 weeks of daily backups


def backup_database() -> Path:
    """Copy the current DB to a timestamped backup file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"toilets_{timestamp}.db"
    shutil.copy2(DB_PATH, dest)
    print(f"Backup created: {dest} ({dest.stat().st_size / 1024:.1f} KB)")
    _prune_old_backups()
    return dest


def _prune_old_backups() -> None:
    """Remove backups beyond MAX_BACKUPS, keeping the most recent ones."""
    backups = sorted(BACKUP_DIR.glob("toilets_*.db"), reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()
        print(f"Removed old backup: {old}")


if __name__ == "__main__":
    backup_database()
