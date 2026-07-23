from __future__ import annotations

import argparse
from pathlib import Path

from .db import apply_schema, database
from .importer import import_legacy
from .worker import (
    detect_stale_source_records,
    publish_dataset,
    resolve_source_records,
    validate_dataset,
)


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
    sub.add_parser("data-quality")
    sub.add_parser("resolve-sources")
    sub.add_parser("expire-sources")
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
                "SELECT id, status, source, record_count, created_at, published_at "
                "FROM dataset_versions ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            print(dict(row))
    elif args.command == "data-quality":
        with database() as connection:
            row = connection.execute(
                """
                SELECT
                  (SELECT count(*) FROM facilities) AS facilities,
                  (SELECT count(*) FROM source_records WHERE record_status = 'active') AS active_source_records,
                  (SELECT count(*) FROM source_records WHERE record_status = 'stale') AS stale_source_records,
                  (SELECT count(*) FROM facility_source_links WHERE status = 'pending') AS pending_links,
                  (SELECT count(*) FROM facility_source_links WHERE status = 'rejected') AS rejected_links
                """
            ).fetchone()
        print(dict(row or {}))
    elif args.command == "resolve-sources":
        print(f"resolved={resolve_source_records()}")
    elif args.command == "expire-sources":
        print(f"expired={detect_stale_source_records()}")


if __name__ == "__main__":
    main()
