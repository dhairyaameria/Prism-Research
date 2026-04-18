-- Apply when upgrading an existing DB (init.sql already includes this for fresh installs).
-- Example: psql $DATABASE_URL -f scripts/migrations/001_tenant_llm.sql

CREATE TABLE IF NOT EXISTS tenant_llm_profiles (
    tenant_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    openai_api_base TEXT,
    ollama_api_base TEXT,
    api_key_env TEXT,
    google_api_key_env TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE runs ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_ticker ON documents(tenant_id, ticker);
