from pathlib import Path


def test_public_queries_hide_non_active_facilities_and_unknown_fee():
    source = Path("app/public_api.py").read_text(encoding="utf-8")
    assert "f.status = 'active'" in source
    assert "JOIN facilities f ON f.id = p.facility_id" in source
    assert "IN ('no', 'false', '0')" in source
    assert "COALESCE(p.attributes->>'fee', 'no')" not in source


def test_publish_migration_only_snapshots_active_facilities():
    migration = Path("migrations/0004_public_facility_status.sql").read_text(encoding="utf-8")
    assert migration.count("f.status = 'active'") >= 3
    assert "record_count = snapshot_count" in migration
