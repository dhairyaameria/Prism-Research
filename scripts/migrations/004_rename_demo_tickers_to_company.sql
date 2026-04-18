-- One-shot: align legacy demo tickers with company-style codes (no data loss).
-- Run if you seeded before FRANCLOUD / MERIDIAN / SABLE were introduced.
UPDATE documents SET ticker = 'FRANCLOUD'
  WHERE tenant_id = 'frustrated_fran' AND ticker = 'FRAN';
UPDATE documents SET ticker = 'MERIDIAN'
  WHERE tenant_id = 'anxious_andy' AND ticker = 'ANDY';
UPDATE documents SET ticker = 'SABLE'
  WHERE tenant_id = 'cautious_carl' AND ticker = 'CARL';
