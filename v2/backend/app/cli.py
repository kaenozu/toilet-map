from __future__ import annotations

import argparse
from pathlib import Path

from .db import apply_schema, database
from .importer import import_legacy
from .worker import publish_dataset, validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Toilet Map v2 administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    import_parser = sub.add_parser("import-legacy")
    import_parser.add_argument("path", type=Path)
    import_parser.add_argument("--source", default="legacy-json")
    import_parser.add_argument("--publish", action="store_true")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("dataset_id", type=int)
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("dataset_id", type=int)
    sub.add_parser("status")
    args = parser.parse_args()

    if args.command == "init-db":
        apply_schema()
    elif args.command == "import-legacy":
        dataset_id, count = import_legacy(args.path, source=args.source)
        validate_dataset(dataset_id)
        if args.publish:
            publish_dataset(dataset_id)
        print(f"dataset={dataset_id} records={count} published={args.publish}")
    elif args.command == "validate":
        validate_dataset(args.dataset_id)
    elif args.command == "publish":
        publish_dataset(args.dataset_id)
    elif args.command == "status":
        with database() as connection:
            rows = connection.execute(
                "SELECT id, status, source, record_count, created_at, published_at FROM dataset_versions ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    main()
