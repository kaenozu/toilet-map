CREATE EXTENSION IF NOT EXISTS postgis;

DO $$ BEGIN
  CREATE TYPE dataset_status AS ENUM ('staging', 'validating', 'validated', 'published', 'superseded', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE source_type AS ENUM (
    'google_maps', 'openstreetmap', 'municipality_open_data', 'user_submission', 'admin', 'legacy'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE verification_status AS ENUM (
    'unverified', 'automatically_verified', 'human_verified', 'disputed', 'rejected', 'stale'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE source_record_status AS ENUM ('active', 'stale', 'superseded', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE facility_link_status AS ENUM ('pending', 'matched', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE facility_status AS ENUM ('active', 'temporarily_closed', 'closed', 'removed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS dataset_versions (
  id BIGSERIAL PRIMARY KEY,
  status dataset_status NOT NULL DEFAULT 'staging',
  source TEXT NOT NULL,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
  validation_report JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  validated_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS one_published_dataset
  ON dataset_versions ((status)) WHERE status = 'published';

CREATE TABLE IF NOT EXISTS places (
  id BIGSERIAL PRIMARY KEY,
  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  stable_key TEXT NOT NULL,
  name TEXT NOT NULL CHECK (btrim(name) <> ''),
  address TEXT NOT NULL DEFAULT '',
  prefecture TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  toilet_score NUMERIC(5,2) CHECK (toilet_score BETWEEN 0 AND 100),
  confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
  review_count INTEGER NOT NULL DEFAULT 0 CHECK (review_count >= 0),
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(dataset_version_id, stable_key)
);

CREATE INDEX IF NOT EXISTS places_location_gix ON places USING GIST(location);
CREATE INDEX IF NOT EXISTS places_dataset_prefecture_idx ON places(dataset_version_id, prefecture);
CREATE INDEX IF NOT EXISTS places_dataset_score_idx ON places(dataset_version_id, toilet_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS places_search_idx ON places USING GIN(to_tsvector('simple', name || ' ' || address));

CREATE TABLE IF NOT EXISTS provider_records (
  id BIGSERIAL PRIMARY KEY,
  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  place_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  raw_payload JSONB NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(dataset_version_id, provider, external_id)
);

CREATE TABLE IF NOT EXISTS reviews (
  id BIGSERIAL PRIMARY KEY,
  place_id BIGINT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  external_id TEXT,
  body TEXT NOT NULL,
  rating NUMERIC(2,1),
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(place_id, provider, external_id)
);

CREATE TABLE IF NOT EXISTS score_history (
  id BIGSERIAL PRIMARY KEY,
  place_id BIGINT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  model_version TEXT NOT NULL,
  score NUMERIC(5,2),
  confidence NUMERIC(5,4),
  explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL,
  status job_status NOT NULL DEFAULT 'queued',
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  error_code TEXT,
  error_message TEXT,
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs(status, available_at, id);

-- Canonical facilities live independently of any published dataset version.
CREATE TABLE IF NOT EXISTS facilities (
  id BIGSERIAL PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE,
  status facility_status NOT NULL DEFAULT 'active',
  name TEXT NOT NULL CHECK (btrim(name) <> ''),
  address TEXT NOT NULL DEFAULT '',
  prefecture TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS facilities_location_gix ON facilities USING GIST(location);
CREATE INDEX IF NOT EXISTS facilities_prefecture_idx ON facilities(prefecture);
CREATE INDEX IF NOT EXISTS facilities_search_idx
  ON facilities USING GIN(to_tsvector('simple', name || ' ' || address));

-- A source record is one provider observation, not the canonical facility itself.
CREATE TABLE IF NOT EXISTS source_records (
  id BIGSERIAL PRIMARY KEY,
  dataset_version_id BIGINT REFERENCES dataset_versions(id) ON DELETE CASCADE,
  source_type source_type NOT NULL,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  record_status source_record_status NOT NULL DEFAULT 'active',
  name TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  prefecture TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  location GEOGRAPHY(POINT, 4326),
  confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
  verification_status verification_status NOT NULL DEFAULT 'unverified',
  observed_at TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  content_hash TEXT NOT NULL,
  superseded_by BIGINT REFERENCES source_records(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(dataset_version_id, provider, external_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS source_records_out_of_band_unique
  ON source_records(provider, external_id, content_hash)
  WHERE dataset_version_id IS NULL;
CREATE INDEX IF NOT EXISTS source_records_location_gix ON source_records USING GIST(location);
CREATE INDEX IF NOT EXISTS source_records_provider_idx ON source_records(provider, external_id);
CREATE INDEX IF NOT EXISTS source_records_expiry_idx
  ON source_records(record_status, expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS source_records_verification_idx
  ON source_records(verification_status, fetched_at DESC);

CREATE TABLE IF NOT EXISTS facility_source_links (
  id BIGSERIAL PRIMARY KEY,
  facility_id BIGINT REFERENCES facilities(id) ON DELETE CASCADE,
  source_record_id BIGINT NOT NULL UNIQUE REFERENCES source_records(id) ON DELETE CASCADE,
  status facility_link_status NOT NULL DEFAULT 'pending',
  match_method TEXT,
  match_score NUMERIC(5,4) CHECK (match_score BETWEEN 0 AND 1),
  decision_reason TEXT,
  decided_at TIMESTAMPTZ,
  decided_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'matched' OR facility_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS facility_source_links_facility_idx
  ON facility_source_links(facility_id, status);
CREATE INDEX IF NOT EXISTS facility_source_links_pending_idx
  ON facility_source_links(status, created_at) WHERE status = 'pending';

-- Immutable, versioned read-model rows used by the public API after cutover.
CREATE TABLE IF NOT EXISTS published_place_snapshots (
  id BIGSERIAL PRIMARY KEY,
  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
  source_record_id BIGINT REFERENCES source_records(id) ON DELETE SET NULL,
  stable_key TEXT NOT NULL,
  name TEXT NOT NULL CHECK (btrim(name) <> ''),
  address TEXT NOT NULL DEFAULT '',
  prefecture TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  toilet_score NUMERIC(5,2) CHECK (toilet_score BETWEEN 0 AND 100),
  confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
  review_count INTEGER NOT NULL DEFAULT 0 CHECK (review_count >= 0),
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(dataset_version_id, facility_id)
);

CREATE INDEX IF NOT EXISTS published_place_snapshots_location_gix
  ON published_place_snapshots USING GIST(location);
CREATE INDEX IF NOT EXISTS published_place_snapshots_dataset_score_idx
  ON published_place_snapshots(dataset_version_id, toilet_score DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS score_dimensions (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL
);

INSERT INTO score_dimensions (key, label) VALUES
  ('cleanliness', 'Cleanliness'),
  ('odor', 'Odor'),
  ('congestion', 'Congestion'),
  ('freshness', 'Freshness'),
  ('equipment', 'Equipment'),
  ('accessibility', 'Accessibility'),
  ('child_friendliness', 'Child friendliness')
ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label;

CREATE TABLE IF NOT EXISTS facility_scores (
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL REFERENCES score_dimensions(key),
  model_version TEXT NOT NULL,
  score NUMERIC(5,2) CHECK (score BETWEEN 0 AND 100),
  confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
  evidence_count INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
  last_observed_at TIMESTAMPTZ,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(facility_id, dimension, model_version)
);

CREATE TABLE IF NOT EXISTS score_evidence (
  id BIGSERIAL PRIMARY KEY,
  facility_id BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  source_record_id BIGINT REFERENCES source_records(id) ON DELETE SET NULL,
  review_id BIGINT REFERENCES reviews(id) ON DELETE SET NULL,
  dimension TEXT NOT NULL REFERENCES score_dimensions(key),
  model_version TEXT NOT NULL,
  value NUMERIC(5,2) CHECK (value BETWEEN 0 AND 100),
  reliability_weight NUMERIC(5,4) CHECK (reliability_weight BETWEEN 0 AND 1),
  extraction_method TEXT NOT NULL,
  observed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source_record_id, dimension, model_version)
);

ALTER TABLE places
  ADD COLUMN IF NOT EXISTS facility_id BIGINT REFERENCES facilities(id) ON DELETE SET NULL;
ALTER TABLE places
  ADD COLUMN IF NOT EXISTS source_record_id BIGINT REFERENCES source_records(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS places_facility_idx ON places(facility_id);
CREATE INDEX IF NOT EXISTS places_source_record_idx ON places(source_record_id);

-- Backfill the new entity model when upgrading an existing v2 database.
INSERT INTO facilities (
  canonical_key, name, address, prefecture, category, location, attributes, created_at, updated_at
)
SELECT DISTINCT ON (p.stable_key)
       'legacy:' || p.stable_key,
       p.name,
       p.address,
       p.prefecture,
       p.category,
       p.location,
       p.attributes,
       p.created_at,
       now()
  FROM places p
  JOIN dataset_versions d ON d.id = p.dataset_version_id
 ORDER BY p.stable_key, (d.status = 'published') DESC, p.dataset_version_id DESC
ON CONFLICT (canonical_key) DO NOTHING;

INSERT INTO source_records (
  dataset_version_id, source_type, provider, external_id, name, address, prefecture, category,
  location, confidence, verification_status, fetched_at, raw_payload, content_hash
)
SELECT pr.dataset_version_id,
       CASE
         WHEN lower(pr.provider) LIKE '%openstreetmap%' OR lower(pr.provider) = 'osm' THEN 'openstreetmap'::source_type
         WHEN lower(pr.provider) LIKE '%google%' THEN 'google_maps'::source_type
         WHEN lower(pr.provider) LIKE '%municipal%' OR lower(pr.provider) LIKE '%open-data%' THEN 'municipality_open_data'::source_type
         ELSE 'legacy'::source_type
       END,
       pr.provider,
       pr.external_id,
       p.name,
       p.address,
       p.prefecture,
       p.category,
       p.location,
       p.confidence,
       'unverified'::verification_status,
       pr.fetched_at,
       pr.raw_payload,
       md5(pr.raw_payload::text)
  FROM provider_records pr
  JOIN places p ON p.id = pr.place_id
ON CONFLICT (dataset_version_id, provider, external_id) DO NOTHING;

INSERT INTO facility_source_links (
  facility_id, source_record_id, status, match_method, match_score, decision_reason, decided_at
)
SELECT f.id,
       sr.id,
       'matched'::facility_link_status,
       'legacy_stable_key',
       1.0,
       'Backfilled from the legacy stable key',
       now()
  FROM source_records sr
  JOIN places p
    ON p.dataset_version_id = sr.dataset_version_id
   AND p.stable_key = sr.external_id
  JOIN facilities f ON f.canonical_key = 'legacy:' || p.stable_key
ON CONFLICT (source_record_id) DO NOTHING;

UPDATE places p
   SET facility_id = f.id
  FROM facilities f
 WHERE p.facility_id IS NULL
   AND f.canonical_key = 'legacy:' || p.stable_key;

WITH source_mapping AS (
  SELECT pr.place_id, min(sr.id) AS source_record_id
    FROM provider_records pr
    JOIN source_records sr
      ON sr.dataset_version_id = pr.dataset_version_id
     AND sr.provider = pr.provider
     AND sr.external_id = pr.external_id
   WHERE pr.place_id IS NOT NULL
   GROUP BY pr.place_id
)
UPDATE places p
   SET source_record_id = source_mapping.source_record_id
  FROM source_mapping
 WHERE p.source_record_id IS NULL
   AND source_mapping.place_id = p.id;

CREATE OR REPLACE FUNCTION publish_dataset(target_id BIGINT) RETURNS VOID AS $$
DECLARE target_status dataset_status;
BEGIN
  SELECT status INTO target_status FROM dataset_versions WHERE id = target_id FOR UPDATE;
  IF target_status IS NULL THEN
    RAISE EXCEPTION 'dataset % does not exist', target_id;
  END IF;
  IF target_status <> 'validated' THEN
    RAISE EXCEPTION 'dataset % must be validated before publication (status=%)', target_id, target_status;
  END IF;

  DELETE FROM published_place_snapshots WHERE dataset_version_id = target_id;
  INSERT INTO published_place_snapshots (
    dataset_version_id, facility_id, source_record_id, stable_key, name, address, prefecture,
    category, location, toilet_score, confidence, review_count, attributes
  )
  SELECT p.dataset_version_id,
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
         p.attributes
    FROM places p
   WHERE p.dataset_version_id = target_id
     AND p.facility_id IS NOT NULL;

  IF (SELECT count(*) FROM published_place_snapshots WHERE dataset_version_id = target_id)
       <> (SELECT count(*) FROM places WHERE dataset_version_id = target_id) THEN
    RAISE EXCEPTION 'dataset % contains places without canonical facilities', target_id;
  END IF;

  UPDATE dataset_versions
     SET status = 'superseded'
   WHERE status = 'published' AND id <> target_id;

  UPDATE dataset_versions
     SET status = 'published', published_at = now()
   WHERE id = target_id;
END;
$$ LANGUAGE plpgsql;

-- Ensure an already-published dataset also has the new read model after upgrade.
INSERT INTO published_place_snapshots (
  dataset_version_id, facility_id, source_record_id, stable_key, name, address, prefecture,
  category, location, toilet_score, confidence, review_count, attributes
)
SELECT p.dataset_version_id,
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
       p.attributes
  FROM places p
  JOIN dataset_versions d ON d.id = p.dataset_version_id
 WHERE d.status = 'published'
   AND p.facility_id IS NOT NULL
ON CONFLICT (dataset_version_id, facility_id) DO UPDATE SET
  source_record_id = EXCLUDED.source_record_id,
  stable_key = EXCLUDED.stable_key,
  name = EXCLUDED.name,
  address = EXCLUDED.address,
  prefecture = EXCLUDED.prefecture,
  category = EXCLUDED.category,
  location = EXCLUDED.location,
  toilet_score = EXCLUDED.toilet_score,
  confidence = EXCLUDED.confidence,
  review_count = EXCLUDED.review_count,
  attributes = EXCLUDED.attributes;
