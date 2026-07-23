-- Operational hardening, entity-resolution workflow, trust read model, and reports.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'retry_wait';
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled';
ALTER TYPE facility_status ADD VALUE IF NOT EXISTS 'merged';

ALTER TABLE facilities
  ADD COLUMN IF NOT EXISTS merged_into_id BIGINT REFERENCES facilities(id) ON DELETE SET NULL;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS parent_job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS dataset_version_id BIGINT REFERENCES dataset_versions(id) ON DELETE CASCADE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS retryable BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stats JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency_idx ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS jobs_lease_idx ON jobs(status, lease_expires_at) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS facility_match_candidates (
  id BIGSERIAL PRIMARY KEY,
  source_record_id BIGINT NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  distance_m NUMERIC(10,2) NOT NULL CHECK (distance_m >= 0),
  name_similarity NUMERIC(5,4) NOT NULL CHECK (name_similarity BETWEEN 0 AND 1),
  address_similarity NUMERIC(5,4) NOT NULL CHECK (address_similarity BETWEEN 0 AND 1),
  candidate_score NUMERIC(5,4) NOT NULL CHECK (candidate_score BETWEEN 0 AND 1),
  reason JSONB NOT NULL DEFAULT '{}'::jsonb,
  dismissed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source_record_id, facility_id)
);
CREATE INDEX IF NOT EXISTS facility_match_candidates_source_idx
  ON facility_match_candidates(source_record_id, candidate_score DESC);

CREATE TABLE IF NOT EXISTS facility_reports (
  id BIGSERIAL PRIMARY KEY,
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  source_record_id BIGINT NOT NULL UNIQUE REFERENCES source_records(id) ON DELETE CASCADE,
  report_type TEXT NOT NULL CHECK (report_type IN (
    'closed', 'temporarily_closed', 'broken', 'wrong_location', 'accessibility', 'cleanliness', 'other'
  )),
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
  fingerprint TEXT NOT NULL UNIQUE,
  decided_at TIMESTAMPTZ,
  decided_by TEXT,
  decision_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS facility_reports_status_idx ON facility_reports(status, created_at DESC);

CREATE TABLE IF NOT EXISTS dimension_observations (
  id BIGSERIAL PRIMARY KEY,
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  source_record_id BIGINT REFERENCES source_records(id) ON DELETE SET NULL,
  review_id BIGINT REFERENCES reviews(id) ON DELETE SET NULL,
  dimension TEXT NOT NULL REFERENCES score_dimensions(key),
  model_version TEXT NOT NULL,
  value NUMERIC(5,2) NOT NULL CHECK (value BETWEEN 0 AND 100),
  confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  evidence_count INTEGER NOT NULL DEFAULT 1 CHECK (evidence_count >= 0),
  extraction_method TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source_record_id, dimension, model_version)
);
CREATE INDEX IF NOT EXISTS dimension_observations_facility_idx
  ON dimension_observations(facility_id, dimension, observed_at DESC);

INSERT INTO dimension_observations (
  facility_id, source_record_id, review_id, dimension, model_version, value,
  confidence, evidence_count, extraction_method, observed_at, created_at
)
SELECT facility_id, source_record_id, review_id, dimension, model_version, value,
       COALESCE(reliability_weight, 0), 1, extraction_method,
       COALESCE(observed_at, created_at), created_at
  FROM score_evidence
 WHERE value IS NOT NULL
ON CONFLICT (source_record_id, dimension, model_version) DO NOTHING;

ALTER TABLE facility_scores ADD COLUMN IF NOT EXISTS source_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE facility_scores ADD COLUMN IF NOT EXISTS calculation_basis JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE published_place_snapshots ADD COLUMN IF NOT EXISTS legacy_place_id BIGINT;
ALTER TABLE published_place_snapshots ADD COLUMN IF NOT EXISTS source_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE published_place_snapshots ADD COLUMN IF NOT EXISTS trust_score NUMERIC(5,2) CHECK (trust_score BETWEEN 0 AND 100);
ALTER TABLE published_place_snapshots
  ADD COLUMN IF NOT EXISTS verification_status verification_status NOT NULL DEFAULT 'unverified';
ALTER TABLE published_place_snapshots ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS published_place_snapshots_legacy_place_idx
  ON published_place_snapshots(dataset_version_id, legacy_place_id) WHERE legacy_place_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS published_place_snapshots_trust_idx
  ON published_place_snapshots(dataset_version_id, trust_score DESC NULLS LAST);

CREATE OR REPLACE FUNCTION source_record_trust_score(record source_records) RETURNS NUMERIC AS $$
DECLARE
  confidence_factor NUMERIC;
  verification_factor NUMERIC;
  freshness_factor NUMERIC;
BEGIN
  confidence_factor := COALESCE(record.confidence, 0.4);
  verification_factor := CASE record.verification_status
    WHEN 'human_verified' THEN 1.0
    WHEN 'automatically_verified' THEN 0.9
    WHEN 'unverified' THEN 0.65
    WHEN 'disputed' THEN 0.2
    WHEN 'stale' THEN 0.1
    WHEN 'rejected' THEN 0.0
  END;
  freshness_factor := CASE
    WHEN record.expires_at IS NOT NULL AND record.expires_at <= now() THEN 0.2
    WHEN record.fetched_at <= now() - interval '365 days' THEN 0.5
    WHEN record.fetched_at <= now() - interval '180 days' THEN 0.7
    ELSE 1.0
  END;
  RETURN round(LEAST(100, GREATEST(0, confidence_factor * verification_factor * freshness_factor * 100)), 2);
END;
$$ LANGUAGE plpgsql STABLE;

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

  SELECT count(*) INTO target_count FROM places WHERE dataset_version_id = target_id;
  IF target_count = 0 THEN
    RAISE EXCEPTION 'dataset % contains no places', target_id;
  END IF;

  SELECT count(*) INTO invalid_count
    FROM places p
    LEFT JOIN facility_source_links link
      ON link.source_record_id = p.source_record_id
     AND link.facility_id = p.facility_id
     AND link.status = 'matched'
   WHERE p.dataset_version_id = target_id
     AND (p.facility_id IS NULL OR p.source_record_id IS NULL OR link.id IS NULL);
  IF invalid_count > 0 THEN
    RAISE EXCEPTION 'dataset % contains % unresolved canonical records', target_id, invalid_count;
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
   WHERE p.dataset_version_id = target_id;

  SELECT count(*) INTO snapshot_count
    FROM published_place_snapshots WHERE dataset_version_id = target_id;
  IF snapshot_count <> target_count THEN
    RAISE EXCEPTION 'dataset % snapshot count mismatch: expected %, got %', target_id, target_count, snapshot_count;
  END IF;

  UPDATE dataset_versions SET status = 'superseded'
   WHERE status = 'published' AND id <> target_id;
  UPDATE dataset_versions SET status = 'published', published_at = now()
   WHERE id = target_id;
END;
$$ LANGUAGE plpgsql;

UPDATE published_place_snapshots snapshot
   SET legacy_place_id = p.id,
       source_count = source_counts.total,
       trust_score = source_record_trust_score(sr),
       verification_status = sr.verification_status,
       last_verified_at = COALESCE(f.last_verified_at, sr.observed_at, sr.fetched_at),
       attributes = f.attributes || p.attributes
  FROM places p
  JOIN facilities f ON f.id = p.facility_id
  JOIN source_records sr ON sr.id = p.source_record_id
  JOIN LATERAL (
    SELECT count(*) AS total FROM facility_source_links link
     WHERE link.facility_id = p.facility_id AND link.status = 'matched'
  ) source_counts ON TRUE
 WHERE snapshot.dataset_version_id = p.dataset_version_id
   AND snapshot.facility_id = p.facility_id;
