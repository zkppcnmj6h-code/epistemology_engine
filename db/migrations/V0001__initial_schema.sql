CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ontology;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS eval;
CREATE SCHEMA IF NOT EXISTS finops;
CREATE SCHEMA IF NOT EXISTS hil;
CREATE SCHEMA IF NOT EXISTS registry;

CREATE TABLE IF NOT EXISTS core.migrations_applied (
  version text primary key,
  applied_at timestamptz not null default now()
);

CREATE TABLE ontology.topic_taxonomy (
  taxonomy_id uuid primary key default uuid_generate_v4(),
  version text unique not null,
  body jsonb not null,
  checksum bytea not null,
  created_at timestamptz not null default now()
);

CREATE TABLE registry.models (
  model_key text primary key, -- e.g., "text-embed-3-large@2025-05"
  family text, -- "openai", "bge", "clip"
  modality text, -- "text", "vision", "multimodal"
  dims int, -- embedding dimension if applicable
  provider text,
  released_at timestamptz,
  deprecated_at timestamptz
);

CREATE TABLE registry.policies (
  policy_id uuid primary key default uuid_generate_v4(),
  name text unique not null, -- e.g., "vision_v1"
  body jsonb not null, -- DPI rules, token caps, routing
  created_at timestamptz not null default now()
);

CREATE TABLE core.sources (
  source_id uuid primary key,
  uri text not null,
  mime_type text,
  title text,
  metadata jsonb,
  created_at timestamptz not null default now()
);

CREATE TABLE core.documents (
  doc_id uuid primary key,
  source_id uuid not null references core.sources(source_id),
  external_ref text,
  lang text,
  status text not null default 'ingested', -- ingested|parsed|chunked|indexed|published
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

CREATE TABLE core.pages (
  page_id uuid primary key,
  doc_id uuid not null references core.documents(doc_id) on delete cascade,
  page_num int not null,
  dpi int,
  text text, -- OCR/plaintext
  vision_features jsonb, -- cached detections
  content_hash bytea not null, -- sha256
  created_at timestamptz not null default now(),
  unique (doc_id, page_num)
);

CREATE TABLE core.chunks (
  chunk_id uuid primary key,
  doc_id uuid not null references core.documents(doc_id) on delete cascade,
  page_id uuid references core.pages(page_id),
  span jsonb, -- offsets/coords
  text text not null,
  topic_hint text,
  created_at timestamptz not null default now()
);

CREATE TABLE core.embeddings (
  embedding_id uuid primary key,
  chunk_id uuid not null references core.chunks(chunk_id) on delete cascade,
  model_key text not null references registry.models(model_key),
  dims int not null,
  vec vector not null,
  created_at timestamptz not null default now()
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embeddings_hnsw
ON core.embeddings USING hnsw (vec) WITH (m = 16, ef_construction = 200);

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_trgm
ON core.chunks USING gin (text gin_trgm_ops);

CREATE TABLE core.chunk_topics (
  chunk_id uuid not null references core.chunks(chunk_id) on delete cascade,
  taxonomy_version text not null,
  topic_path text not null,
  score real not null,
  primary key (chunk_id, taxonomy_version, topic_path)
);

CREATE TABLE ops.runs (
  run_id uuid primary key,
  pipeline text not null, -- e.g., "ingest-index-publish"
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running', -- running|succeeded|failed|rolled_back
  metadata jsonb
);

CREATE TABLE ops.run_steps (
  run_id uuid not null references ops.runs(run_id) on delete cascade,
  step_name text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  info jsonb,
  primary key (run_id, step_name)
);

CREATE TABLE ops.write_sets (
  write_set_id uuid primary key,
  run_id uuid not null references ops.runs(run_id),
  table_name text not null,
  pk jsonb not null, -- {cols, vals}
  before jsonb,
  after jsonb,
  op text not null, -- INSERT|UPDATE|DELETE
  applied_at timestamptz not null default now()
);

CREATE TABLE ops.sync_state (
  mirror text not null, -- "notion"
  entity_table text not null, -- "core.documents"
  entity_pk jsonb not null,
  mirror_id text, -- Notion page_id
  mirror_rev text,
  last_synced_at timestamptz,
  primary key (mirror, entity_table, entity_pk)
);

CREATE TABLE eval.test_suites (
  suite_id uuid primary key,
  name text unique not null,
  description text,
  assertions jsonb not null, -- inline specs for MVP
  created_at timestamptz not null default now()
);

CREATE TABLE eval.scores (
  score_id uuid primary key,
  suite_id uuid references eval.test_suites(suite_id),
  run_id uuid references ops.runs(run_id),
  metrics jsonb not null,
  created_at timestamptz not null default now()
);

CREATE TABLE finops.usage_events (
  event_id uuid primary key,
  run_id uuid references ops.runs(run_id),
  model_key text references registry.models(model_key),
  tokens_prompt bigint default 0,
  tokens_completion bigint default 0,
  cost_usd numeric(12,6) default 0,
  meta jsonb,
  created_at timestamptz not null default now()
);

CREATE TABLE hil.feedback_events (
  feedback_id uuid primary key,
  entity_table text not null,
  entity_pk jsonb not null,
  reviewer_id text,
  channel text, -- "console", "mobile"
  label text, -- "approve", "reject", "needs_attention"
  payload jsonb,
  created_at timestamptz not null default now()
);

INSERT INTO core.migrations_applied(version)
VALUES ('V0001') ON CONFLICT DO NOTHING;
