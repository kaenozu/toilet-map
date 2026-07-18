# mypy: disable-error-code="no-redef"
"""Common utility functions for batch processing."""

from __future__ import annotations

import gzip
import json
import logging
import os
import platform
import re
import tempfile
import time
from contextlib import contextmanager
from typing import Any

try:
    from .scoring_config import PREFECTURES
except ImportError:
    from scoring_config import PREFECTURES

msvcrt: Any = None
fcntl: Any = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

if platform.system() == "Windows":
    import msvcrt
else:
    try:
        import fcntl
    except ImportError:
        fcntl = None


def load_jsonl(path: str) -> list[dict[str, object]]:
    if not os.path.exists(path):
        return []
    places: list[dict[str, object]] = []
    with open(path, encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(f"Failed to decode JSON line {line_number} in {path}: {exc}")
                continue
            if isinstance(value, dict):
                places.append(value)
            else:
                logger.warning(f"Skipping non-object JSON line {line_number} in {path}")
    return places


def _atomic_target(path: str) -> tuple[int, str]:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    return tempfile.mkstemp(prefix=f".{os.path.basename(path)}-", suffix=".tmp", dir=directory)


def save_json(path: str, data: dict[str, object], indent: int = 2, compress: bool = False) -> None:
    """Atomically save JSON, optionally as gzip, so readers never see partial data."""
    target_path = path
    if compress and not target_path.endswith(".gz"):
        target_path += ".gz"

    fd, temp_path = _atomic_target(target_path)
    os.close(fd)
    try:
        if compress:
            with gzip.open(temp_path, "wt", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=indent)
        else:
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=indent)
                file.flush()
                os.fsync(file.fileno())
        os.replace(temp_path, target_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning(f"Could not remove temporary file {temp_path}: {exc}")
    logger.info(f"Saved: {target_path}")


def count_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as file:
        return sum(1 for line in file if line.strip() and not line.lstrip().startswith("#"))


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _normalize_address_text(address: str) -> str:
    return re.sub(r"[\s\u3000/・,、\-()（）]+", "", address or "")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
EXPANSION_STATUS_PATH = os.path.join(SCRIPT_DIR, "expansion_status.json")
EXPANSION_STATUS_LOCK_PATH = os.path.join(SCRIPT_DIR, ".expansion_status.lock")
EXPANSION_STATUS_RETENTION_SEC = 300


def read_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Failed to read JSON file: {path} ({exc})")
        return default


def write_json_atomic(path: str, data: object) -> None:
    directory = os.path.dirname(path)
    if directory:
        ensure_dir(directory)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning(f"Could not remove temporary file {temp_path}: {exc}")


def update_expansion_status(run_id: str, data: dict[str, object] | None = None, remove: bool = False) -> dict[str, object]:
    with file_lock(EXPANSION_STATUS_LOCK_PATH):
        now = time.time()
        status = read_json_file(EXPANSION_STATUS_PATH, {"updated_at": 0, "runs": []})
        runs = {
            str(entry.get("run_id")): entry
            for entry in status.get("runs", [])
            if isinstance(entry, dict) and entry.get("run_id")
        }
        runs = {
            run_key: entry
            for run_key, entry in runs.items()
            if entry.get("status") == "running"
            or now - float(entry.get("updated_at", now)) <= EXPANSION_STATUS_RETENTION_SEC
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
    """Cross-platform process lock for Windows, Linux and macOS."""
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
    if not address:
        return ""
    normalized = _normalize_address_text(address)
    for prefecture in PREFECTURES:
        if prefecture in normalized:
            return prefecture
    for alias, prefecture in sorted(PREFECTURE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in normalized:
            return prefecture
    return ""
