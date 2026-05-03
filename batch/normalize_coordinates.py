"""
batch/normalize_coordinates.py
raw データ内の longtitude typo を longitude に正規化する。

使い方:
  python batch/normalize_coordinates.py
"""
from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TARGET_FILES = [
    SCRIPT_DIR / "raw_data.json",
    SCRIPT_DIR / "raw_data.json.bak",
    *sorted((SCRIPT_DIR / "raw_parts").glob("part_*.json")),
]


def normalize_file(path: Path) -> int:
    """1ファイル内の longtitude を longitude に置換し、置換数を返す。"""
    replaced = 0

    lines = path.read_text(encoding="utf-8").splitlines()
    normalized_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            normalized_lines.append(line)
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            normalized_lines.append(line)
            continue

        if isinstance(obj, dict) and "longtitude" in obj and "longitude" not in obj:
            obj["longitude"] = obj.pop("longtitude")
            replaced += 1
        normalized_lines.append(json.dumps(obj, ensure_ascii=False))

    path.write_text("\n".join(normalized_lines) + ("\n" if lines else ""), encoding="utf-8")
    return replaced


def main() -> None:
    total = 0
    for path in TARGET_FILES:
        if not path.exists():
            continue
        total += normalize_file(path)
    print(f"Normalized {total} coordinate fields.")


if __name__ == "__main__":
    main()
