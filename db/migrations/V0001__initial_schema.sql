CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE SCHEMA IF NOT EXISTS core;
CREATE TABLE IF NOT EXISTS core.migrations_applied (
  version text primary key,
  applied_at timestamptz not null default now()
);
INSERT INTO core.migrations_applied(version)
VALUES ('V0001') ON CONFLICT DO NOTHING;
