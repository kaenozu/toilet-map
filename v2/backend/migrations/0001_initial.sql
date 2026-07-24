-- Initial v2 PostgreSQL/PostGIS schema.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$ BEGIN
  CREATE TYPE dataset_status AS ENUM ('staging', 'validating', 'validated', 'published', 'superseded', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');
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

  UPDATE dataset_versions
     SET status = 'superseded'
   WHERE status = 'published' AND id <> target_id;

  UPDATE dataset_versions
     SET status = 'published', published_at = now()
   WHERE id = target_id;
END;
$$ LANGUAGE plpgsql;
