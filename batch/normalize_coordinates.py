"""
batch/normalize_coordinates.py
raw データ内の longtitude typo を longitude に正規化する。

使い方:
  python batch/normalize_coordinates.py
"""
from __future__ import annotations

import json
import tempfile
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

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=str(path.parent),
        prefix=f"{path.stem}.",
        suffix=".tmp",
    ) as tmp_file:
        temp_path = Path(tmp_file.name)
        with path.open("r", encoding="utf-8") as src:
            for line in src:
                stripped = line.strip()
                if not stripped:
                    tmp_file.write(line)
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    tmp_file.write(line)
                    continue

                if isinstance(obj, dict) and "longtitude" in obj and "longitude" not in obj:
                    obj["longitude"] = obj.pop("longtitude")
                    replaced += 1

                serialized = json.dumps(obj, ensure_ascii=False)
                if line.endswith("\n"):
                    serialized += "\n"
                tmp_file.write(serialized)

    temp_path.replace(path)
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
