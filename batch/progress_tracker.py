# mypy: disable-error-code="no-redef"
"""Scrape progress persistence keyed by query fingerprint."""

from __future__ import annotations

import hashlib
import os

try:
    from .utils import update_expansion_status
except ImportError:
    from utils import update_expansion_status

PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get("PROGRESS_FILE", ".progress"))
ProgressState = dict[int, str]


def query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()[:16]


def load_queries(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as file:
        return [stripped for line in file if (stripped := line.strip()) and not stripped.startswith("#")]


def load_progress(path: str = PROGRESS_FILE) -> ProgressState:
    """Load `index<TAB>fingerprint`; legacy index-only rows are treated as stale."""
    if not os.path.exists(path):
        return {}
    progress: ProgressState = {}
    with open(path, encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            index_text, separator, fingerprint = stripped.partition("\t")
            try:
                index = int(index_text)
            except ValueError:
                continue
            progress[index] = fingerprint if separator else ""
    return progress


def save_progress(done: ProgressState, path: str = PROGRESS_FILE) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        for index in sorted(done):
            file.write(f"{index}\t{done[index]}\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def publish_expansion_status(
    run_id: str,
    *,
    pref: str,
    city: str,
    total: int,
    done: int,
    success: int,
    failed: int,
    started_at: float,
    status: str = "running",
    message: str = "",
) -> None:
    update_expansion_status(
        run_id,
        {
            "prefecture": pref,
            "city": city,
            "status": status,
            "message": message,
            "pid": os.getpid(),
            "started_at": started_at,
            "progress": {
                "completed_queries": done,
                "total_queries": total,
                "success_count": success,
                "failed_count": failed,
            },
        },
    )


def merge_part_files(raw_dir: str, output_path: str, total: int) -> None:
    with open(output_path, "w", encoding="utf-8") as output:
        for index in range(1, total + 1):
            part_path = os.path.join(raw_dir, f"part_{index:03d}.json")
            if os.path.exists(part_path):
                with open(part_path, encoding="utf-8") as part:
                    output.write(part.read())
