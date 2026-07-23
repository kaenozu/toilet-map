CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE dataset_status AS ENUM ('staging', 'validating', 'published', 'failed');
CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');

CREATE TABLE dataset_versions (
  id BIGSERIAL PRIMARY KEY,
  status dataset_status NOT NULL DEFAULT 'staging',
  source TEXT NOT NULL,
  record_count INTEGER NOT NULL DEFAULT 0,
  validation_report JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX one_published_dataset
  ON dataset_versions ((status)) WHERE status = 'published';

CREATE TABLE places (
  id BIGSERIAL PRIMARY KEY,
  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  stable_key TEXT NOT NULL,
  name TEXT NOT NULL,
  address TEXT NOT NULL DEFAULT '',
  prefecture TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  toilet_score NUMERIC(5,2),
  confidence NUMERIC(5,4),
  review_count INTEGER NOT NULL DEFAULT 0,
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(dataset_version_id, stable_key)
);

CREATE INDEX places_location_gix ON places USING GIST(location);
CREATE INDEX places_dataset_prefecture_idx ON places(dataset_version_id, prefecture);

CREATE TABLE provider_records (
  id BIGSERIAL PRIMARY KEY,
  place_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  external_id TEXT NOT NULL,
  raw_payload JSONB NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(provider, external_id)
);

CREATE TABLE jobs (
  id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL,
  status job_status NOT NULL DEFAULT 'queued',
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempts INTEGER NOT NULL DEFAULT 0,
  error_code TEXT,
  error_message TEXT,
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX jobs_claim_idx ON jobs(status, available_at, id);
