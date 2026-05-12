"""
batch/progress_tracker.py
スクレイプの進捗管理とファイル I/O ユーティリティ
進捗ファイルの読み書き、ステータス公開、パーツファイルマージ
"""
import os
from utils import logger, update_expansion_status

PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get("PROGRESS_FILE", ".progress"))


def load_queries(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [stripped for line in f if (stripped := line.strip()) and not stripped.startswith("#")]


def load_progress(path: str = PROGRESS_FILE) -> set[int]:
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return {int(line.strip()) for line in f if line.strip()}


def save_progress(done: set[int], path: str = PROGRESS_FILE) -> None:
    with open(path, "w") as f:
        for idx in sorted(done):
            f.write(f"{idx}\n")


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
    with open(output_path, "w", encoding="utf-8") as outf:
        for i in range(1, total + 1):
            part = os.path.join(raw_dir, f"part_{i:03d}.json")
            if os.path.exists(part):
                with open(part, "r", encoding="utf-8") as pf:
                    outf.write(pf.read())
