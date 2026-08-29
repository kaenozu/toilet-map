from pathlib import Path

path = Path("v2/backend/app/public_api.py")
text = path.read_text(encoding="utf-8")
old = "    conditions: list[str] = [\"d.status = 'published'\"]\n"
new = "    conditions: list[str] = [\"d.status = 'published'\", \"f.status = 'active'\"]\n"
if text.count(old) != 1:
    raise SystemExit(f"conditions count={text.count(old)}")
text = text.replace(old, new, 1)
old = "          FROM {model.table} p\n          JOIN dataset_versions d ON d.id = p.dataset_version_id\n         WHERE {where_sql}\n"
new = "          FROM {model.table} p\n          JOIN dataset_versions d ON d.id = p.dataset_version_id\n          JOIN facilities f ON f.id = p.facility_id\n         WHERE {where_sql}\n"
if text.count(old) != 2:
    raise SystemExit(f"list join block count={text.count(old)}")
text = text.replace(old, new, 2)
old = """              FROM {model.table} p
              JOIN dataset_versions d ON d.id = p.dataset_version_id
             WHERE {id_condition} AND d.status = 'published'
"""
new = """              FROM {model.table} p
              JOIN dataset_versions d ON d.id = p.dataset_version_id
              JOIN facilities f ON f.id = p.facility_id
             WHERE {id_condition} AND d.status = 'published' AND f.status = 'active'
"""
if text.count(old) != 1:
    raise SystemExit(f"detail join count={text.count(old)}")
text = text.replace(old, new, 1)
old = """            SELECT d.id AS dataset_version_id, d.published_at, d.record_count,
                   count(p.id) FILTER (WHERE p.toilet_score IS NOT NULL) AS scored_count,
                   avg(p.toilet_score)::float AS average_score,
                   count(DISTINCT NULLIF(p.prefecture, '')) AS prefecture_count
              FROM dataset_versions d
              LEFT JOIN {model.table} p ON p.dataset_version_id = d.id
             WHERE d.status = 'published'
             GROUP BY d.id
"""
new = """            SELECT d.id AS dataset_version_id, d.published_at, count(p.id) AS record_count,
                   count(p.id) FILTER (WHERE p.toilet_score IS NOT NULL) AS scored_count,
                   avg(p.toilet_score)::float AS average_score,
                   count(DISTINCT NULLIF(p.prefecture, '')) AS prefecture_count
              FROM dataset_versions d
              LEFT JOIN {model.table} p
                ON p.dataset_version_id = d.id
               AND EXISTS (
                 SELECT 1 FROM facilities active_facility
                  WHERE active_facility.id = p.facility_id
                    AND active_facility.status = 'active'
               )
             WHERE d.status = 'published'
             GROUP BY d.id
"""
if text.count(old) != 1:
    raise SystemExit(f"stats block count={text.count(old)}")
text = text.replace(old, new, 1)
old = """            f\"\"\"SELECT p.prefecture AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                WHERE d.status = 'published' AND p.prefecture <> ''
"""
new = """            f\"\"\"SELECT p.prefecture AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                JOIN facilities f ON f.id = p.facility_id
                WHERE d.status = 'published' AND f.status = 'active' AND p.prefecture <> ''
"""
if text.count(old) != 1:
    raise SystemExit(f"prefecture facet count={text.count(old)}")
text = text.replace(old, new, 1)
old = """            f\"\"\"SELECT p.category AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                WHERE d.status = 'published' AND p.category <> ''
"""
new = """            f\"\"\"SELECT p.category AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                JOIN facilities f ON f.id = p.facility_id
                WHERE d.status = 'published' AND f.status = 'active' AND p.category <> ''
"""
if text.count(old) != 1:
    raise SystemExit(f"category facet count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
Path("tools/repair_issue140.py").unlink()
Path(".github/workflows/repair-issue140-public-api.yml").unlink()
