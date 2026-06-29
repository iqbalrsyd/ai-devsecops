-- ============================================================
-- Migration v3: Pipeline-Centric Redesign
-- Drops old Scans/Findings/Incidents tables
-- Creates new Pipeline/PipelineRun/PipelineAnalysis/RepositoryInsight tables
-- ============================================================

BEGIN;

-- ============================================================
-- Step 1: Drop old tables (Scans, Reports, Incidents)
-- ============================================================

DROP MATERIALIZED VIEW IF EXISTS dashboard_project_stats;
DROP MATERIALIZED VIEW IF EXISTS dashboard_recent_activity;
DROP MATERIALIZED VIEW IF EXISTS mv_dashboard_stats;

DROP TABLE IF EXISTS recommendations CASCADE;
DROP TABLE IF EXISTS compliance_mappings CASCADE;
DROP TABLE IF EXISTS risk_assessments CASCADE;
DROP TABLE IF EXISTS findings CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS workflow_executions CASCADE;
DROP TABLE IF EXISTS github_deployments CASCADE;
DROP TABLE IF EXISTS repository_analyses CASCADE;
DROP TABLE IF EXISTS pipeline_validations CASCADE;

-- ============================================================
-- Step 2: Rename old pipeline_generations → pipelines
-- ============================================================

ALTER TABLE IF EXISTS pipeline_generations RENAME TO pipelines;

-- Drop old columns
ALTER TABLE pipelines DROP COLUMN IF EXISTS analysis_id;
ALTER TABLE pipelines DROP COLUMN IF EXISTS generation_explanation;

-- Add new columns
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS version_number INTEGER;
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS user_requirements TEXT;
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS generation_params JSONB DEFAULT '{}';
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS security_controls_applied JSONB DEFAULT '[]';
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS compliance_metadata JSONB DEFAULT '{}';
ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS deployment_results JSONB;

-- Migrate existing data
UPDATE pipelines SET version_number = 1 WHERE version_number IS NULL;
UPDATE pipelines SET prompt = query WHERE prompt IS NULL;
UPDATE pipelines SET generation_params = COALESCE(project_profile::jsonb, '{}') WHERE generation_params = '{}';

-- Add unique constraint
DELETE FROM pipelines a USING pipelines b WHERE a.id < b.id AND a.repository_id = b.repository_id AND a.version_number = b.version_number;
ALTER TABLE pipelines ADD CONSTRAINT pipelines_repo_version_unique UNIQUE (repository_id, version_number);
ALTER TABLE pipelines ALTER COLUMN version_number SET NOT NULL;
ALTER TABLE pipelines ALTER COLUMN prompt SET NOT NULL;
ALTER TABLE pipelines ALTER COLUMN generated_yaml SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pipelines_repository ON pipelines(repository_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_version ON pipelines(repository_id, version_number);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_created ON pipelines(created_at);

-- ============================================================
-- Step 3: Create pipeline_runs table
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    run_number      INTEGER NOT NULL,
    github_run_id   BIGINT,
    status          VARCHAR(50) DEFAULT 'pending',
    conclusion      VARCHAR(50),
    html_url        TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_seconds INTEGER,
    jobs            JSONB,
    logs_url        TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(pipeline_id, run_number)
);

-- Migrate data from old workflow_executions
INSERT INTO pipeline_runs (id, pipeline_id, run_number, github_run_id, status, conclusion, html_url, started_at, completed_at, duration_seconds, jobs, logs_url, error_message, created_at)
SELECT
    we.id,
    we.generation_id,
    ROW_NUMBER() OVER (PARTITION BY we.generation_id ORDER BY we.created_at) as run_number,
    we.github_run_id,
    we.status,
    we.conclusion,
    we.html_url,
    we.started_at,
    we.completed_at,
    we.duration_seconds,
    we.jobs,
    we.logs_url,
    we.error_message,
    we.created_at
FROM workflow_executions we
WHERE EXISTS (SELECT 1 FROM pipelines p WHERE p.id = we.generation_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline ON pipeline_runs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_github ON pipeline_runs(github_run_id);

-- ============================================================
-- Step 4: Create pipeline_analyses table
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_analyses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id         UUID NOT NULL UNIQUE REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    risk_score              DECIMAL(5,2),
    compliance_score        DECIMAL(5,2),
    workflow_quality_score  DECIMAL(5,2),
    security_coverage_score DECIMAL(5,2),
    findings_summary        JSONB,
    severity_breakdown      JSONB DEFAULT '{}',
    recommendations         JSONB DEFAULT '[]',
    ai_explanation          TEXT,
    raw_scan_data           JSONB,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_analyses_run ON pipeline_analyses(pipeline_run_id);

-- ============================================================
-- Step 5: Create repository_insights table
-- ============================================================

CREATE TABLE IF NOT EXISTS repository_insights (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id       UUID NOT NULL UNIQUE REFERENCES repositories(id) ON DELETE CASCADE,
    primary_language    VARCHAR(100),
    secondary_languages JSONB DEFAULT '[]',
    frameworks          JSONB DEFAULT '[]',
    build_tools         JSONB DEFAULT '[]',
    package_managers    JSONB DEFAULT '[]',
    test_frameworks     JSONB DEFAULT '[]',
    architecture_type   VARCHAR(50),
    has_dockerfile      BOOLEAN DEFAULT FALSE,
    has_docker_compose  BOOLEAN DEFAULT FALSE,
    has_kubernetes      BOOLEAN DEFAULT FALSE,
    has_terraform       BOOLEAN DEFAULT FALSE,
    has_existing_ci_cd  BOOLEAN DEFAULT FALSE,
    existing_workflows  JSONB DEFAULT '[]',
    dependency_ecosystem JSONB DEFAULT '[]',
    raw_analysis_output JSONB,
    analyzed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Step 6: Recreate audit_logs (simplified)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100),
    resource_type   VARCHAR(100),
    resource_id     UUID,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);

-- ============================================================
-- Step 7: Create materialized view for dashboard
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dashboard_stats AS
SELECT
    COUNT(DISTINCT p.id) AS total_projects,
    COUNT(DISTINCT r.id) AS total_repositories,
    COUNT(DISTINCT pl.id) AS total_pipelines,
    COUNT(DISTINCT pr.id) AS total_executions,
    COUNT(DISTINCT pa.id) AS total_analyses,
    COALESCE(
        (COUNT(DISTINCT CASE WHEN pr.conclusion = 'success' THEN pr.id END) * 100.0 /
        NULLIF(COUNT(DISTINCT CASE WHEN pr.conclusion IS NOT NULL THEN pr.id END), 0)),
        0
    ) AS pipeline_success_rate,
    COALESCE(AVG(pa.risk_score), 0) AS avg_risk_score,
    COALESCE(AVG(pa.compliance_score), 0) AS avg_compliance_score,
    COALESCE(AVG(pa.security_coverage_score), 0) AS avg_security_coverage,
    COALESCE(AVG(pa.workflow_quality_score), 0) AS avg_workflow_quality
FROM projects p
LEFT JOIN repositories r ON r.project_id = p.id
LEFT JOIN pipelines pl ON pl.repository_id = r.id
LEFT JOIN pipeline_runs pr ON pr.pipeline_id = pl.id
LEFT JOIN pipeline_analyses pa ON pa.pipeline_run_id = pr.id;

COMMIT;
