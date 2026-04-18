CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT,
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('earnings_transcript', 'filing', 'internal_note', 'external_news', 'pdf_filing')),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    body TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_documents_ticker ON documents(ticker);
CREATE INDEX idx_documents_tenant_ticker ON documents(tenant_id, ticker);

-- Per-tenant LLM routing (open-source via Ollama, Baseten, vLLM, or Gemini).
-- Secrets are never stored here: only env var *names* that the API process resolves at runtime.
CREATE TABLE tenant_llm_profiles (
    tenant_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    openai_api_base TEXT,
    ollama_api_base TEXT,
    api_key_env TEXT,
    google_api_key_env TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    thesis_json JSONB,
    quality_passed BOOLEAN,
    quality_report JSONB,
    replay_of UUID REFERENCES runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_runs_tenant ON runs(tenant_id);

CREATE TABLE hops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    intent TEXT,
    payload JSONB NOT NULL DEFAULT '{}',
    duration_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_hops_run ON hops(run_id);

CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    citation_id TEXT NOT NULL,
    source_kind TEXT,
    chunk_id UUID REFERENCES chunks(id),
    doc_title TEXT,
    quote_span TEXT,
    retrieval_score FLOAT,
    used_by_agent TEXT,
    hop_id UUID REFERENCES hops(id),
    extra JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_citations_run ON citations(run_id);

CREATE TABLE matrix_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    theme TEXT NOT NULL,
    summary TEXT,
    confidence FLOAT,
    evidence TEXT,
    citation_ids JSONB DEFAULT '[]',
    row_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_matrix_run ON matrix_rows(run_id);

CREATE TABLE contradictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    tension_type TEXT,
    description TEXT NOT NULL,
    side_a_citation_ids JSONB DEFAULT '[]',
    side_b_citation_ids JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contradictions_run ON contradictions(run_id);

CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    passed INT NOT NULL,
    failed INT NOT NULL,
    scenarios JSONB NOT NULL DEFAULT '[]'
);

CREATE TABLE tenant_members (
    tenant_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'analyst', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, principal)
);

CREATE INDEX idx_tenant_members_tenant ON tenant_members(tenant_id);

CREATE TABLE analyst_feedback (
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

CREATE INDEX idx_analyst_feedback_run ON analyst_feedback(run_id);

CREATE TABLE evidence_access_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    requester TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
    subject_tenant_id TEXT,
    subject_ticker TEXT,
    request_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_access_tenant ON evidence_access_requests(tenant_id);
