"""
batch/expansion_query.py
自動拡張におけるクエリファイルの管理・マージ・分類
auto_expand.py から分離。本モジュールは test_batch_scrape_pipeline.py からインポートされる。
"""
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from generate_queries import (
    CITY_QUERY_TEMPLATES as GENERATE_CITY_QUERY_TEMPLATES,
)
from generate_queries import (
    PREFECTURE_QUERY_TEMPLATES as GENERATE_PREFECTURE_QUERY_TEMPLATES,
)
from generate_queries import (
    build_queries,
    write_batches,
)
from utils import logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_DIR = os.path.join(SCRIPT_DIR, "queries.d")

# スコープ付き拡張用テンプレート（auto_expand の budget 制限付きクエリ）
# generate_queries.py の CITY_QUERY_TEMPLATES（フル21種）とは別物
SCOPED_CITY_TEMPLATES = ["{city} トイレ", "{city} 公衆トイレ"]
SCOPED_PREFECTURE_TEMPLATES = ["{pref} トイレ きれい", "{pref} トイレ アクセス"]

CITY_QUERY_BUDGET_TEMPLATES = SCOPED_CITY_TEMPLATES
PREFECTURE_QUERY_BUDGET_TEMPLATES = SCOPED_PREFECTURE_TEMPLATES

@dataclass
class _ExpansionContext:
    target_pref: str = ""
    target_city: str = ""
    city_budget: int = 0
    pref_budget: int = 0


_ctx = _ExpansionContext()


def reset_context() -> None:
    """コンテキストを初期状態にリセットする（テスト用）"""
    _ctx.target_pref = ""
    _ctx.target_city = ""
    _ctx.city_budget = 0
    _ctx.pref_budget = 0


def set_active_context(pref: str, city: str, city_budget: int = 0, pref_budget: int = 0) -> tuple[str, str, int, int]:
    prev = (_ctx.target_pref, _ctx.target_city, _ctx.city_budget, _ctx.pref_budget)
    _ctx.target_pref = pref
    _ctx.target_city = city
    _ctx.city_budget = city_budget
    _ctx.pref_budget = pref_budget
    return prev


@contextmanager
def active_context(pref: str, city: str, city_budget: int = 0, pref_budget: int = 0):
    """コンテキスト保存/復元付きでスコープ付き利用するためのコンテキストマネージャ"""
    prev = set_active_context(pref, city, city_budget, pref_budget)
    try:
        yield
    finally:
        set_active_context(*prev)


def query_limits_for_count(count: int) -> tuple[int, int]:
    if count == 0:
        return (8, 4)
    if count < 4:
        return (12, 4)
    if count < 6:
        return (16, 6)
    return (len(SCOPED_CITY_TEMPLATES), len(SCOPED_PREFECTURE_TEMPLATES))


def _slugify(value: str) -> str:
    safe_chars = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    slug = "".join(safe_chars).strip("_")
    return slug or "all"


def _load_query_lines(path: Path) -> list[str]:
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)
    except OSError:
        return []
    return lines


def _read_query_header(path: Path) -> tuple[str, str]:
    city = ""
    prefecture = ""
    try:
        with path.open("r", encoding="utf-8") as f:
            for _ in range(5):
                raw_line = f.readline()
                if not raw_line:
                    break
                stripped = raw_line.strip()
                if stripped.startswith("# city:"):
                    city = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("# prefecture:"):
                    prefecture = stripped.split(":", 1)[1].strip()
                if city and prefecture:
                    break
    except OSError as exc:
        logger.warning(f"Failed to read query header: {path} ({exc})")
    return city, prefecture


def _file_mentions_city(path: Path, city: str) -> bool:
    if not city:
        return False
    return any(city in line for line in _load_query_lines(path))


def _next_batch_index(pref_dir: Path) -> int:
    indices = [0]
    for path in pref_dir.glob("batch_*.txt"):
        try:
            indices.append(int(path.stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(indices) + 1


def ensure_query_files(pref: str) -> None:
    pref_dir = Path(QUERIES_DIR) / pref
    pref_dir.mkdir(parents=True, exist_ok=True)

    if not _ctx.target_city:
        return

    target_label = f"{pref}{_ctx.target_city}" if pref else _ctx.target_city
    target_path = pref_dir / f"batch_{_next_batch_index(pref_dir):03d}_target.txt"
    city_queries = build_queries([target_label], GENERATE_CITY_QUERY_TEMPLATES)
    with target_path.open("w", encoding="utf-8") as f:
        f.write(f"# city: {_ctx.target_city}\n")
        if pref:
            f.write(f"# prefecture: {pref}\n")
        f.write("\n".join(city_queries) + "\n")

    if not pref:
        return

    has_pref_queries = False
    for path in pref_dir.glob("batch_*.txt"):
        if path.name == target_path.name:
            continue
        header_city, header_pref = _read_query_header(path)
        if header_pref == pref and not header_city:
            has_pref_queries = True
            break

    if has_pref_queries:
        return

    pref_queries = build_queries([pref], GENERATE_PREFECTURE_QUERY_TEMPLATES)
    write_batches(
        pref_queries,
        str(pref_dir),
        city="",
        prefecture=pref,
        start_index=_next_batch_index(pref_dir),
    )


def find_batch_files(pref: str) -> list[Path]:
    pref_dir = Path(QUERIES_DIR) / pref
    if not pref_dir.exists():
        return []
    return sorted(pref_dir.glob("batch_*.txt"))


def _classify_query_file(path: Path) -> str:
    header_city, header_pref = _read_query_header(path)
    if _ctx.target_city:
        if header_city and header_city != _ctx.target_city:
            return ""
        if header_city == _ctx.target_city or _file_mentions_city(path, _ctx.target_city):
            return "city"
        if header_pref and _ctx.target_pref and header_pref != _ctx.target_pref:
            return ""
        return "pref"
    return "pref" if not header_city else "city"


def merge_query_files(files: list[str | Path]) -> str:
    city_budget = _ctx.city_budget or len(SCOPED_CITY_TEMPLATES)
    pref_budget = _ctx.pref_budget or len(SCOPED_PREFECTURE_TEMPLATES)
    city_queries: list[str] = []
    pref_queries: list[str] = []
    seen: set[str] = set()

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            continue

        bucket = _classify_query_file(path)
        if not bucket:
            continue

        bucket_queries = city_queries if bucket == "city" else pref_queries
        bucket_budget = city_budget if bucket == "city" else pref_budget

        for query in _load_query_lines(path):
            if len(bucket_queries) >= bucket_budget:
                break
            if query in seen:
                continue
            bucket_queries.append(query)
            seen.add(query)

    merged_queries = city_queries + pref_queries
    if not merged_queries:
        return ""

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt", dir=SCRIPT_DIR) as tmp:
        if _ctx.target_pref:
            tmp.write(f"# prefecture: {_ctx.target_pref}\n")
        if _ctx.target_city:
            tmp.write(f"# city: {_ctx.target_city}\n")
        for query in merged_queries:
            tmp.write(f"{query}\n")
        return tmp.name
