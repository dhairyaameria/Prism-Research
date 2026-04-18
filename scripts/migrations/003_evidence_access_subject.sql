-- Cross-tenant / cross-ticker evidence access requests (demo + governance).
ALTER TABLE evidence_access_requests
  ADD COLUMN IF NOT EXISTS subject_tenant_id TEXT,
  ADD COLUMN IF NOT EXISTS subject_ticker TEXT,
  ADD COLUMN IF NOT EXISTS request_note TEXT;
