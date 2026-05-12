"""
batch/utils.py
Common utility functions for batch processing.
"""
import json
import os
import sys
import logging
import gzip
import re
import time
import tempfile
from contextlib import contextmanager
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    import msvcrt
except ImportError:  # pragma: no cover - Windows fallback only
    msvcrt = None

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback only
    fcntl = None

def load_jsonl(path: str) -> list[dict[str, Any]]:
    """Load JSONL file into a list of dictionaries."""
    if not os.path.exists(path):
        return []
    places = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    places.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode JSON line in {path}: {e}")
    return places

def save_json(path: str, data: dict[str, Any], indent: int = 2, compress: bool = False) -> None:
    """Save dictionary to JSON file (optionally compressed with gzip)."""
    target_path = path
    if compress:
        if not target_path.endswith(".gz"):
            target_path += ".gz"
        with gzip.open(target_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
    else:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
    logger.info(f"Saved: {target_path}")

def count_lines(path: str) -> int:
    """Count non-empty lines in a file (excluding comments)."""
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip() and not line.startswith("#"))

def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def _normalize_address_text(address: str) -> str:
    return re.sub(r"[\s\u3000/・,、\-()（）]+", "", address or "")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
EXPANSION_STATUS_PATH = os.path.join(PROJECT_ROOT, "static", "expansion_status.json")
EXPANSION_STATUS_LOCK_PATH = os.path.join(SCRIPT_DIR, ".expansion_status.lock")
EXPANSION_STATUS_RETENTION_SEC = 300


def read_json_file(path: str, default: Any) -> Any:
    """Read JSON from disk and fall back to default on failure."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Failed to read JSON file: {path} ({exc})")
        return default


def write_json_atomic(path: str, data: Any) -> None:
    """Write JSON atomically."""
    directory = os.path.dirname(path)
    if directory:
        ensure_dir(directory)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def update_expansion_status(run_id: str, data: dict[str, Any] | None = None, remove: bool = False) -> dict[str, Any]:
    """Merge one run entry into the shared expansion status file."""
    with file_lock(EXPANSION_STATUS_LOCK_PATH):
        now = time.time()
        status = read_json_file(EXPANSION_STATUS_PATH, {"updated_at": 0, "runs": []})
        runs = {
            str(entry.get("run_id")): entry
            for entry in status.get("runs", [])
            if isinstance(entry, dict) and entry.get("run_id")
        }

        runs = {
            rid: entry
            for rid, entry in runs.items()
            if entry.get("status") == "running" or now - float(entry.get("updated_at", now)) <= EXPANSION_STATUS_RETENTION_SEC
        }

        if remove:
            runs.pop(run_id, None)
        else:
            current = runs.get(run_id, {})
            if data:
                current.update(data)
            current["run_id"] = run_id
            current["updated_at"] = now
            runs[run_id] = current

        payload = {"updated_at": now, "runs": list(runs.values())}
        write_json_atomic(EXPANSION_STATUS_PATH, payload)
        return payload


@contextmanager
def file_lock(path: str, timeout: float = 600.0, poll_interval: float = 0.5):
    """Process-wide lock for shared batch artifacts."""
    directory = os.path.dirname(path)
    if directory:
        ensure_dir(directory)

    with open(path, "a+b") as lock_file:
        if os.path.getsize(path) == 0:
            lock_file.write(b"0")
            lock_file.flush()

        start = time.time()
        while True:
            try:
                lock_file.seek(0)
                if msvcrt is not None:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                elif fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    raise RuntimeError("File locking is not supported on this platform")
                break
            except OSError:
                if time.time() - start >= timeout:
                    raise TimeoutError(f"Timed out waiting for lock: {path}")
                time.sleep(poll_interval)

        try:
            yield
        finally:
            if msvcrt is not None:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scoring_config import PREFECTURES


def _build_prefecture_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for prefecture in PREFECTURES:
        if prefecture == "北海道":
            continue
        if prefecture.endswith(("都", "道", "府", "県")):
            alias = prefecture[:-1]
            if alias:
                aliases.setdefault(alias, prefecture)
    return aliases


PREFECTURE_ALIASES = _build_prefecture_aliases()


def extract_prefecture(address: str) -> str:
    """住所文字列から都道府県を抽出"""
    if not address:
        return ""

    normalized = _normalize_address_text(address)

    for pref in PREFECTURES:
        if pref in normalized:
            return pref

    for alias, prefecture in sorted(PREFECTURE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in normalized:
            return prefecture

    if "北海道" in normalized:
        return "北海道"

    return ""
