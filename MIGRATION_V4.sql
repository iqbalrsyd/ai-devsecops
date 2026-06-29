-- ============================================================
-- Migration v4: Remediation Tracking
-- Adds remediation_status column to pipeline_runs
-- ============================================================

BEGIN;

ALTER TABLE pipeline_runs
ADD COLUMN IF NOT EXISTS remediation_status VARCHAR(50) DEFAULT 'none';

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_remediation ON pipeline_runs(remediation_status);

COMMIT;
