"""Operational CLI for migrations, ingestion, validation, and data quality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .db import apply_schema, database
from .importer import import_legacy
from .resolution import generate_match_candidates
from .worker import (
    detect_stale_source_records,
    ingest_osm_region,
    publish_dataset,
    resolve_source_records,
    validate_dataset,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toilet-map-v2")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("migration-status")

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

    candidates = sub.add_parser("generate-candidates")
    candidates.add_argument("--dataset-id", type=int)
    candidates.add_argument("--source-record-id", type=int)
    candidates.add_argument("--max-distance-m", type=float, default=300)
    candidates.add_argument("--minimum-score", type=float, default=0.35)

    osm = sub.add_parser("ingest-osm")
    osm.add_argument("--region", choices=("kumagaya", "gyoda", "fukaya"), required=True)
    return parser


def _data_quality() -> dict[str, object]:
    with database() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM facilities) AS facilities,
              (SELECT count(*) FROM source_records WHERE record_status = 'active') AS active_source_records,
              (SELECT count(*) FROM source_records WHERE record_status = 'stale') AS stale_source_records,
              (SELECT count(*) FROM facility_source_links WHERE status = 'pending') AS pending_links,
              (SELECT count(*) FROM facility_source_links WHERE status = 'rejected') AS rejected_links,
              (SELECT count(*) FROM facility_reports WHERE status = 'pending') AS pending_reports,
              (SELECT count(*) FROM published_place_snapshots snapshot
                JOIN dataset_versions dataset ON dataset.id = snapshot.dataset_version_id
               WHERE dataset.status = 'published') AS published_snapshots
            """
        ).fetchone()
    return dict(row or {})


def main() -> None:
    args = _parser().parse_args()
    if args.command == "init-db":
        applied = apply_schema()
        print(json.dumps({"applied": applied}, ensure_ascii=False))
    elif args.command == "migration-status":
        with database() as connection:
            rows = connection.execute(
                "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
        for row in rows:
            print(dict(row))
    elif args.command == "import-legacy":
        dataset_id, count = import_legacy(args.path, source=args.source)
        validate_dataset(dataset_id)
        if args.publish:
            publish_dataset(dataset_id)
        print({"dataset_version_id": dataset_id, "record_count": count, "published": args.publish})
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
        print(json.dumps(_data_quality(), ensure_ascii=False, default=str))
    elif args.command == "resolve-sources":
        print(f"resolved={resolve_source_records()}")
    elif args.command == "expire-sources":
        print(f"expired={detect_stale_source_records()}")
    elif args.command == "generate-candidates":
        with database() as connection:
            total = generate_match_candidates(
                connection,
                dataset_version_id=args.dataset_id,
                source_record_id=args.source_record_id,
                max_distance_m=args.max_distance_m,
                minimum_score=args.minimum_score,
            )
            connection.commit()
        print(f"generated={total}")
    elif args.command == "ingest-osm":
        print(json.dumps(ingest_osm_region(args.region), ensure_ascii=False))


if __name__ == "__main__":
    main()
