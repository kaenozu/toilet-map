-- Public datasets expose only currently active facilities.
-- This replaces publish_dataset without rewriting applied migration history.
CREATE OR REPLACE FUNCTION publish_dataset(target_id BIGINT) RETURNS VOID AS $$
DECLARE
  target_status dataset_status;
  target_count BIGINT;
  invalid_count BIGINT;
  snapshot_count BIGINT;
BEGIN
  SELECT status INTO target_status FROM dataset_versions WHERE id = target_id FOR UPDATE;
  IF target_status IS NULL THEN
    RAISE EXCEPTION 'dataset % does not exist', target_id;
  END IF;
  IF target_status <> 'validated' THEN
    RAISE EXCEPTION 'dataset % must be validated before publication (status=%)', target_id, target_status;
  END IF;

  SELECT count(*) INTO target_count
    FROM places p
    JOIN facilities f ON f.id = p.facility_id
   WHERE p.dataset_version_id = target_id
     AND f.status = 'active';
  IF target_count = 0 THEN
    RAISE EXCEPTION 'dataset % contains no active places', target_id;
  END IF;

  SELECT count(*) INTO invalid_count
    FROM places p
    JOIN facilities f ON f.id = p.facility_id
    LEFT JOIN facility_source_links link
      ON link.source_record_id = p.source_record_id
     AND link.facility_id = p.facility_id
     AND link.status = 'matched'
   WHERE p.dataset_version_id = target_id
     AND f.status = 'active'
     AND (p.source_record_id IS NULL OR link.id IS NULL);
  IF invalid_count > 0 THEN
    RAISE EXCEPTION 'dataset % contains % unresolved active canonical records', target_id, invalid_count;
  END IF;

  DELETE FROM published_place_snapshots WHERE dataset_version_id = target_id;
  INSERT INTO published_place_snapshots (
    dataset_version_id, legacy_place_id, facility_id, source_record_id, stable_key, name, address,
    prefecture, category, location, toilet_score, confidence, review_count, attributes,
    source_count, trust_score, verification_status, last_verified_at
  )
  SELECT p.dataset_version_id,
         p.id,
         p.facility_id,
         p.source_record_id,
         p.stable_key,
         p.name,
         p.address,
         p.prefecture,
         p.category,
         p.location,
         p.toilet_score,
         p.confidence,
         p.review_count,
         f.attributes || p.attributes,
         (SELECT count(*) FROM facility_source_links matched
           WHERE matched.facility_id = p.facility_id AND matched.status = 'matched'),
         source_record_trust_score(sr),
         sr.verification_status,
         COALESCE(f.last_verified_at, sr.observed_at, sr.fetched_at)
    FROM places p
    JOIN facilities f ON f.id = p.facility_id
    JOIN source_records sr ON sr.id = p.source_record_id
    JOIN facility_source_links link
      ON link.source_record_id = p.source_record_id
     AND link.facility_id = p.facility_id
     AND link.status = 'matched'
   WHERE p.dataset_version_id = target_id
     AND f.status = 'active';

  SELECT count(*) INTO snapshot_count
    FROM published_place_snapshots WHERE dataset_version_id = target_id;
  IF snapshot_count <> target_count THEN
    RAISE EXCEPTION 'dataset % active snapshot count mismatch: expected %, got %', target_id, target_count, snapshot_count;
  END IF;

  UPDATE dataset_versions SET status = 'superseded'
   WHERE status = 'published' AND id <> target_id;
  UPDATE dataset_versions SET status = 'published', published_at = now(), record_count = snapshot_count
   WHERE id = target_id;
END;
$$ LANGUAGE plpgsql;
