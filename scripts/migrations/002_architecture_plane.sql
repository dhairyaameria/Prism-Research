-- RBAC, quality gate, analyst feedback, evidence access stub, PDF source kind.
-- Apply (psql URL must not contain +asyncpg):
--   ./scripts/apply_migrations.sh
-- Or: psql "${DATABASE_URL//+asyncpg/}" -f scripts/migrations/002_architecture_plane.sql

ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_source_kind_check;
ALTER TABLE documents ADD CONSTRAINT documents_source_kind_check CHECK (
    source_kind IN ('earnings_transcript', 'filing', 'internal_note', 'external_news', 'pdf_filing')
);

ALTER TABLE runs ADD COLUMN IF NOT EXISTS quality_passed BOOLEAN;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS quality_report JSONB;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS replay_of UUID REFERENCES runs(id);

CREATE TABLE IF NOT EXISTS tenant_members (
    tenant_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'analyst', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, principal)
);

CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant ON tenant_members(tenant_id);

CREATE TABLE IF NOT EXISTS analyst_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    thumbs SMALLINT,
    note TEXT,
    scrubbed_note TEXT,
    edited_thesis JSONB,
    extra JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analyst_feedback_run ON analyst_feedback(run_id);

CREATE TABLE IF NOT EXISTS evidence_access_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    requester TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_access_tenant ON evidence_access_requests(tenant_id);
