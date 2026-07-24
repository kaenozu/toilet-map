-- psql bootstrap for a complete v2 schema.
-- Application deployments should prefer: python -m app.cli init-db
\set ON_ERROR_STOP on
\ir migrations/0001_initial.sql
\ir migrations/0002_source_model.sql
\ir migrations/0003_operational_platform.sql
