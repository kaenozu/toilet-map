"""
batch/merge_to_db.py
JSON データを既存 SQLite にマージし、都道府県 NULL を修復する。
to_sqlite.py への互換ラッパー。

関連ファイル:
  - batch/to_sqlite.py (実装本体)
  - batch/db_utils.py (共通ユーティリティ)
  - data/toilets.db (出力 DB)
"""
from to_sqlite import merge as _merge

merge = _merge

if __name__ == "__main__":
    import sys
    from to_sqlite import merge
    path = sys.argv[1] if len(sys.argv) > 1 else "data/toilets.json.gz"
    merge(path)
