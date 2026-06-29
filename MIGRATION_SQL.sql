-- Database Migration: AI DevSecOps Pipeline Engineer
-- From: Workflow Audit Agent (v1) → Repository-Aware Pipeline Engineer (v2)
-- Run this after removing legacy Go models from AutoMigrate

-- ==============================
-- Drop legacy tables
-- ==============================
DROP TABLE IF EXISTS scans CASCADE;
DROP TABLE IF EXISTS vulnerabilities CASCADE;
DROP TABLE IF EXISTS ai_reports CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;

-- ==============================
-- Create repository_analyses table
-- ==============================
CREATE TABLE IF NOT EXISTS repository_analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id       UUID REFERENCES repositories(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(50) DEFAULT 'pending',
    detected_language   VARCHAR(100),
    detected_frameworks JSONB,
    detected_build_tools JSONB,
    detected_test_frameworks JSONB,
    detected_architecture VARCHAR(100),
    has_dockerfile      BOOLEAN DEFAULT FALSE,
    has_docker_compose  BOOLEAN DEFAULT FALSE,
    has_kubernetes      BOOLEAN DEFAULT FALSE,
    has_terraform       BOOLEAN DEFAULT FALSE,
    has_existing_ci_cd  BOOLEAN DEFAULT FALSE,
    existing_workflows  JSONB,
    raw_scan_data       JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Add columns to repositories
-- ==============================
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS last_scanned_at TIMESTAMPTZ;

-- ==============================
-- Add columns to workflow_executions
-- ==============================
ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS workflow_name VARCHAR(255);

-- ==============================
-- Add columns to pipeline_generations
-- ==============================
ALTER TABLE pipeline_generations ADD COLUMN IF NOT EXISTS analysis_id UUID REFERENCES repository_analyses(id);

-- ==============================
-- Create indexes for new queries
-- ==============================
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_findings_execution ON findings(execution_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_execution ON risk_assessments(execution_id);

-- ==============================
-- Create materialized views for dashboard
-- ==============================
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_project_stats AS
SELECT
    p.id AS project_id,
    p.name AS project_name,
    COUNT(DISTINCT r.id) AS total_repositories,
    COUNT(DISTINCT pg.id) AS total_pipelines,
    COUNT(DISTINCT we.id) AS total_executions,
    COUNT(DISTINCT f.id) AS total_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'critical' THEN f.id END) AS critical_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'high' THEN f.id END) AS high_findings,
    AVG(ra.risk_score) AS avg_risk_score,
    AVG(ra.security_posture) AS avg_security_posture,
    MAX(we.created_at) AS last_execution
FROM projects p
LEFT JOIN repositories r ON r.project_id = p.id
LEFT JOIN pipeline_generations pg ON pg.repository_id = r.id
LEFT JOIN workflow_executions we ON we.generation_id = pg.id
LEFT JOIN findings f ON f.execution_id = we.id
LEFT JOIN risk_assessments ra ON ra.execution_id = we.id
GROUP BY p.id, p.name;