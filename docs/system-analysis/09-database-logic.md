# 9. Database Logic

## 9.1 Entity-Relationship Overview

```
┌──────────┐       ┌──────────────┐       ┌────────────────┐
│  users   │       │ repositories │       │ analysis_jobs  │
├──────────┤       ├──────────────┤       ├────────────────┤
│ PK id    │──1:N──▶│ FK user_id   │──1:N──▶│ FK repository_id│
│ username │       │ PK id        │       │ PK id           │
│ email    │       │ name         │       │ status          │
│ avatar   │       │ full_name    │       │ started_at      │
│ role     │       │ owner_login  │       │ completed_at    │
│ created  │       │ visibility   │       │ error_message   │
└──────────┘       │ default_branch│      └───────┬─────────┘
       │           │ language      │              │
       │           │ size_kb       │      ┌───────▼─────────────┐
       │           │ created_at    │      │ analysis_results    │
       │           └───────┬──────┘      ├─────────────────────┤
       │                   │             │ PK id                │
       │           ┌───────▼──────────┐  │ FK job_id            │
       │           │ workflows        │  │ technologies (JSONB) │
       │           ├──────────────────┤  │ languages (JSONB)    │
       │           │ PK id            │  │ frameworks (JSONB)   │
       │           │ FK repository_id │  │ build_tools (JSONB)  │
       │           │ FK created_by    │  │ test_frameworks (JSONB)│
       │           │ filename         │  │ deployment_configs   │
       │           │ yaml_content     │  │ raw_response (JSONB) │
       │           │ status           │  │ created_at           │
       │           │ validation_result│  └─────────────────────┘
       │           │ created_at       │
       │           └───────┬──────────┘
       │                   │
       │           ┌───────▼──────────┐
       │           │ workflow_runs    │
       │           ├──────────────────┤
       │           │ PK id            │
       │           │ FK workflow_id   │
       │           │ FK repository_id │
       │           │ run_id (GitHub)  │
       │           │ status           │
       │           │ conclusion       │
       │           │ started_at       │
       │           │ completed_at     │
       │           └───────┬──────────┘
       │                   │
       │           ┌───────▼──────────┐       ┌──────────────────┐
       │           │ findings         │       │ recommendations  │
       │           ├──────────────────┤       ├──────────────────┤
       │           │ PK id            │──1:N──▶│ FK finding_id    │
       │           │ FK run_id        │       │ PK id            │
       │           │ FK repository_id │       │ type             │
       │           │ tool             │       │ priority         │
       │           │ rule_id          │       │ explanation      │
       │           │ severity         │       │ fix_code         │
       │           │ file_path        │       │ auto_fixable     │
       │           │ line_number      │       │ breaking_change  │
       │           │ cwe_id           │       │ confidence       │
       │           │ cvss_score       │       │ status           │
       │           │ description      │       │ created_at       │
       │           │ triage_status    │       └──────────────────┘
       │           │ created_at       │
       │           └──────────────────┘
       │
       ├──────────▶┌──────────────────┐
       │           │ pull_requests    │
       │           ├──────────────────┤
       │           │ PK id            │
       │           │ FK repository_id │
       │           │ FK workflow_id   │
       │           │ FK created_by    │
       │           │ pr_number        │
       │           │ pr_url           │
       │           │ branch_name      │
       │           │ status           │
       │           │ created_at       │
       │           │ merged_at        │
       │           └──────────────────┘
       │
       ├──────────▶┌──────────────────┐
       │           │ credentials      │
       │           ├──────────────────┤
       │           │ PK id            │
       │           │ FK user_id       │
       │           │ credential_type  │
       │           │ token_encrypted  │
       │           │ scopes (JSONB)   │
       │           │ expires_at       │
       │           │ created_at       │
       │           └──────────────────┘
       │
       └──────────▶┌──────────────────┐
                   │ audit_logs       │
                   ├──────────────────┤
                   │ PK id            │
                   │ FK user_id       │
                   │ action           │
                   │ resource_type    │
                   │ resource_id      │
                   │ details (JSONB)  │
                   │ ip_address       │
                   │ created_at       │
                   └──────────────────┘
```

---

## 9.2 Main Entity Definitions

### 9.2.1 Users

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `github_id` | BIGINT | UNIQUE, NOT NULL | GitHub user ID |
| `username` | VARCHAR(255) | NOT NULL | GitHub username |
| `email` | VARCHAR(255) | NULLABLE | Email from GitHub profile |
| `avatar_url` | TEXT | NULLABLE | GitHub avatar URL |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT 'user' | 'user', 'admin', 'auditor' |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Account creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |
| `last_login_at` | TIMESTAMPTZ | NULLABLE | Last login timestamp |

**Relationships**:
- One-to-Many → `repositories`
- One-to-Many → `credentials`
- One-to-Many → `audit_logs`
- One-to-Many → `pull_requests` (as `created_by`)
- One-to-Many → `workflows` (as `created_by`)

### 9.2.2 Repositories

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | UUID | FK → users(id), NOT NULL | Owner of this connection |
| `github_repo_id` | BIGINT | NOT NULL | GitHub repository ID |
| `name` | VARCHAR(255) | NOT NULL | Repository name (e.g., "react") |
| `full_name` | VARCHAR(512) | NOT NULL | Full name (e.g., "facebook/react") |
| `owner_login` | VARCHAR(255) | NOT NULL | GitHub owner username |
| `visibility` | VARCHAR(20) | NOT NULL | 'public', 'private', 'internal' |
| `default_branch` | VARCHAR(255) | NOT NULL, DEFAULT 'main' | Default branch name |
| `language` | VARCHAR(100) | NULLABLE | Primary language (from GitHub) |
| `size_kb` | INTEGER | NULLABLE | Repository size in KB |
| `description` | TEXT | NULLABLE | Repository description |
| `is_archived` | BOOLEAN | NOT NULL, DEFAULT false | Archived status |
| `clone_url` | TEXT | NULLABLE | Clone URL (stored temporarily) |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'connected' | 'connected', 'analyzing', 'disconnected' |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Connection creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update |

**Relationships**:
- Many-to-One → `users`
- One-to-Many → `analysis_jobs`
- One-to-Many → `workflows`
- One-to-Many → `workflow_runs`
- One-to-Many → `findings`
- One-to-Many → `pull_requests`

**Indexes**:
```sql
CREATE INDEX idx_repositories_user_id ON repositories(user_id);
CREATE INDEX idx_repositories_full_name ON repositories(full_name);
CREATE UNIQUE INDEX idx_repositories_user_github ON repositories(user_id, github_repo_id);
```

### 9.2.3 Analysis Jobs

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Target repository |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'queued' | 'queued', 'in_progress', 'completed', 'failed', 'cancelled' |
| `progress_percent` | INTEGER | NOT NULL, DEFAULT 0 | 0-100 progress indicator |
| `error_message` | TEXT | NULLABLE | Error message if failed |
| `started_at` | TIMESTAMPTZ | NULLABLE | When processing started |
| `completed_at` | TIMESTAMPTZ | NULLABLE | When processing completed |
| `duration_ms` | INTEGER | NULLABLE | Total duration in milliseconds |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Job creation |

**Relationships**:
- Many-to-One → `repositories`
- One-to-One → `analysis_results`

**Indexes**:
```sql
CREATE INDEX idx_analysis_jobs_repository ON analysis_jobs(repository_id);
CREATE INDEX idx_analysis_jobs_status ON analysis_jobs(status);
```

### 9.2.4 Analysis Results

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `job_id` | UUID | FK → analysis_jobs(id), UNIQUE, NOT NULL | Parent job |
| `technologies` | JSONB | NOT NULL, DEFAULT '{}' | Full technology detection output |
| `languages` | JSONB | NOT NULL, DEFAULT '[]' | Detected languages |
| `frameworks` | JSONB | NOT NULL, DEFAULT '[]' | Detected frameworks |
| `build_tools` | JSONB | NOT NULL, DEFAULT '[]' | Detected build tools |
| `test_frameworks` | JSONB | NOT NULL, DEFAULT '[]' | Detected test frameworks |
| `deployment_configs` | JSONB | NOT NULL, DEFAULT '[]' | Detected deployment configs |
| `file_count` | INTEGER | NOT NULL, DEFAULT 0 | Total files analyzed |
| `analysis_mode` | VARCHAR(20) | NOT NULL | 'clone' or 'api' |
| `raw_llm_response` | JSONB | NULLABLE | Raw OpenRouter response |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Result creation |

### 9.2.5 Workflows

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Target repository |
| `created_by` | UUID | FK → users(id), NOT NULL | Creator |
| `filename` | VARCHAR(512) | NOT NULL | Workflow file name |
| `yaml_content` | TEXT | NOT NULL | Full workflow YAML |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'draft' | 'draft', 'validated', 'repairing', 'repair_failed', 'pr_created', 'merged' |
| `validation_result` | JSONB | NULLABLE | Full validation output |
| `repair_history` | JSONB | NULLABLE | List of repair attempts and results |
| `generation_config` | JSONB | NOT NULL | User config used for generation |
| `trigger_config` | JSONB | NOT NULL | Trigger events config |
| `security_tools_config` | JSONB | NOT NULL | Enabled security tools |
| `ai_explanations` | JSONB | NULLABLE | Inline AI explanations |
| `model_used` | VARCHAR(100) | NULLABLE | LLM model used |
| `tokens_used` | INTEGER | NULLABLE | Token consumption |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update |

**Relationships**:
- Many-to-One → `repositories`
- Many-to-One → `users`
- One-to-Many → `workflow_runs`
- One-to-Many → `pull_requests`

**Indexes**:
```sql
CREATE INDEX idx_workflows_repository ON workflows(repository_id);
CREATE INDEX idx_workflows_status ON workflows(status);
```

### 9.2.6 Workflow Runs

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `workflow_id` | UUID | FK → workflows(id), NULLABLE | Parent workflow |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Repository |
| `github_run_id` | BIGINT | NOT NULL | GitHub Actions run ID |
| `head_sha` | VARCHAR(40) | NOT NULL | Commit SHA |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'queued' | 'queued', 'in_progress', 'completed' |
| `conclusion` | VARCHAR(50) | NULLABLE | 'success', 'failure', 'neutral', 'cancelled', 'timed_out' |
| `started_at` | TIMESTAMPTZ | NULLABLE | Run start |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Run end |
| `duration_seconds` | INTEGER | NULLABLE | Run duration |
| `check_runs_data` | JSONB | NULLABLE | Raw check runs data |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |

**Relationships**:
- Many-to-One → `workflows`
- Many-to-One → `repositories`
- One-to-Many → `findings`

**Indexes**:
```sql
CREATE INDEX idx_workflow_runs_repository ON workflow_runs(repository_id);
CREATE INDEX idx_workflow_runs_github_id ON workflow_runs(github_run_id);
```

### 9.2.7 Findings

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `run_id` | UUID | FK → workflow_runs(id), NOT NULL | Parent workflow run |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Repository (denormalized for querying) |
| `tool` | VARCHAR(50) | NOT NULL | 'semgrep', 'gitleaks', 'trivy', 'codeql', 'dependency_review' |
| `rule_id` | VARCHAR(255) | NOT NULL | Tool-specific rule ID |
| `severity` | VARCHAR(20) | NOT NULL | 'critical', 'high', 'medium', 'low', 'info' |
| `file_path` | TEXT | NOT NULL | Affected file path |
| `line_number` | INTEGER | NULLABLE | Line number |
| `column_number` | INTEGER | NULLABLE | Column number |
| `cwe_id` | VARCHAR(50) | NULLABLE | CWE reference (e.g., 'CWE-79') |
| `cve_id` | VARCHAR(50) | NULLABLE | CVE reference (e.g., 'CVE-2024-1234') |
| `cvss_score` | FLOAT | NULLABLE | CVSS v3.1 score |
| `title` | TEXT | NOT NULL | Short title |
| `description` | TEXT | NULLABLE | Full description |
| `code_snippet` | TEXT | NULLABLE | Relevant code context |
| `package_name` | VARCHAR(255) | NULLABLE | Affected package (for dependency findings) |
| `current_version` | VARCHAR(100) | NULLABLE | Current version |
| `fixed_version` | VARCHAR(100) | NULLABLE | Fixed version |
| `triage_status` | VARCHAR(50) | NOT NULL, DEFAULT 'open' | 'open', 'false_positive', 'accepted_risk', 'fixed', 'wont_fix' |
| `triaged_by` | UUID | FK → users(id), NULLABLE | Who triaged |
| `triaged_at` | TIMESTAMPTZ | NULLABLE | When triaged |
| `raw_output` | JSONB | NULLABLE | Raw tool output |
| `fingerprint` | VARCHAR(64) | NOT NULL | SHA-256 fingerprint for deduplication |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Finding creation |

**Relationships**:
- Many-to-One → `workflow_runs`
- Many-to-One → `repositories`
- Many-to-One → `users` (triaged by)
- One-to-Many → `recommendations`

**Indexes**:
```sql
CREATE INDEX idx_findings_repository ON findings(repository_id);
CREATE INDEX idx_findings_run ON findings(run_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_tool ON findings(tool);
CREATE INDEX idx_findings_triage ON findings(triage_status);
CREATE UNIQUE INDEX idx_findings_fingerprint ON findings(fingerprint);
CREATE INDEX idx_findings_created_at ON findings(created_at DESC);
```

### 9.2.8 Recommendations

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `finding_id` | UUID | FK → findings(id), NULLABLE | Associated finding |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Repository |
| `type` | VARCHAR(50) | NOT NULL | 'dependency_update', 'code_fix', 'secret_removal', 'config_change', 'cicd_hardening' |
| `priority` | VARCHAR(20) | NOT NULL | 'critical', 'high', 'medium' |
| `title` | TEXT | NOT NULL | Short title |
| `explanation` | TEXT | NOT NULL | Why this fix is recommended |
| `fix_code` | TEXT | NULLABLE | Code diff for code fixes |
| `command` | TEXT | NULLABLE | CLI command (for dependency updates) |
| `auto_fixable` | BOOLEAN | NOT NULL, DEFAULT false | Can be auto-applied |
| `breaking_change` | BOOLEAN | NOT NULL, DEFAULT false | Does this change API behavior |
| `confidence` | FLOAT | NOT NULL, DEFAULT 1.0 | LLM confidence 0.0-1.0 |
| `cwe_reference` | TEXT | NULLABLE | CWE URL |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'pending' | 'pending', 'applied', 'ignored', 'failed' |
| `applied_at` | TIMESTAMPTZ | NULLABLE | When applied |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation |

**Relationships**:
- Many-to-One → `findings`
- Many-to-One → `repositories`

**Indexes**:
```sql
CREATE INDEX idx_recommendations_finding ON recommendations(finding_id);
CREATE INDEX idx_recommendations_repository ON recommendations(repository_id);
CREATE INDEX idx_recommendations_priority ON recommendations(priority);
```

### 9.2.9 Pull Requests

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `repository_id` | UUID | FK → repositories(id), NOT NULL | Target repository |
| `workflow_id` | UUID | FK → workflows(id), NULLABLE | Related workflow |
| `created_by` | UUID | FK → users(id), NOT NULL | Creator |
| `pr_number` | INTEGER | NOT NULL | GitHub PR number |
| `pr_url` | TEXT | NOT NULL | GitHub PR URL |
| `branch_name` | VARCHAR(512) | NOT NULL | Source branch name |
| `title` | TEXT | NOT NULL | PR title |
| `description` | TEXT | NULLABLE | PR description |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'open' | 'open', 'closed', 'merged' |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation |
| `merged_at` | TIMESTAMPTZ | NULLABLE | Merge time |

**Relationships**:
- Many-to-One → `repositories`
- Many-to-One → `workflows`
- Many-to-One → `users`

**Indexes**:
```sql
CREATE INDEX idx_pull_requests_repository ON pull_requests(repository_id);
CREATE INDEX idx_pull_requests_pr_number ON pull_requests(repository_id, pr_number);
CREATE INDEX idx_pull_requests_status ON pull_requests(status);
```

### 9.2.10 Credentials

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | UUID | FK → users(id), NOT NULL | Owner |
| `credential_type` | VARCHAR(50) | NOT NULL | 'github_oauth', 'github_pat', 'github_app_installation' |
| `token_encrypted` | BYTEA | NOT NULL | AES-256-GCM encrypted token |
| `token_hash` | VARCHAR(64) | NOT NULL | SHA-256 hash for duplicate detection without decryption |
| `scopes` | JSONB | NULLABLE | Token scopes |
| `expires_at` | TIMESTAMPTZ | NULLABLE | Token expiry |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Whether token is currently valid |
| `last_used_at` | TIMESTAMPTZ | NULLABLE | Last time token was used |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation |

**Relationships**:
- Many-to-One → `users`

**Indexes**:
```sql
CREATE INDEX idx_credentials_user ON credentials(user_id);
CREATE INDEX idx_credentials_active ON credentials(user_id, credential_type, is_active);
```

### 9.2.11 Audit Logs

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | UUID | FK → users(id), NULLABLE | Acting user |
| `action` | VARCHAR(100) | NOT NULL | 'repository.analyze', 'workflow.generate', 'pr.create', etc. |
| `resource_type` | VARCHAR(50) | NOT NULL | 'repository', 'workflow', 'pull_request', etc. |
| `resource_id` | UUID | NULLABLE | ID of the affected resource |
| `details` | JSONB | NOT NULL, DEFAULT '{}' | Action-specific details |
| `ip_address` | INET | NULLABLE | Client IP address |
| `user_agent` | TEXT | NULLABLE | Client user agent |
| `status` | VARCHAR(20) | NOT NULL | 'success', 'failure' |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When action occurred |

**Relationships**:
- Many-to-One → `users`

**Indexes**:
```sql
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
```

---

## 9.3 CRUD Operations Matrix

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| **users** | OAuth callback (auto) | Auth check, profile fetch | Last login, role change | SOFT DELETE (is_active flag) |
| **repositories** | User connects repo | List repos, get details | Update metadata, disconnect | HARD DELETE on disconnect |
| **analysis_jobs** | User triggers analysis | Poll status, list history | Update status, progress | CASCADE with repository |
| **analysis_results** | Agent writes after analysis | Fetch results for UI | NEVER (immutable, append-only) | CASCADE with job |
| **workflows** | Agent generates + user approves | List, fetch YAML | Update status, validation results | CASCADE with repository |
| **workflow_runs** | Monitoring worker detects new run | List runs, get details | Update status, conclusion | Retain for 12 months |
| **findings** | Artifact parser writes | List, filter, search | Triage status only | Retain for 12 months |
| **recommendations** | Recommendation agent writes | List, filter | Apply/ignore status | CASCADE with finding |
| **pull_requests** | System creates PR | List, get status | Status, merge time | NEVER (historical record) |
| **credentials** | OAuth/PAT registration | Internal auth check | Refresh, deactivate | HARD DELETE on disconnect |
| **audit_logs** | ALL service operations | Admin queries | NEVER (immutable) | Retain for 24 months |

---

## 9.4 Data Lifecycle

### 9.4.1 Retention Policies

| Data Type | Retention Period | Storage After Retention | Reason |
|---|---|---|---|
| User accounts | Indefinite (until deletion) | Anonymized aggregation data | Account history |
| Repositories | Indefinite (until disconnected) | Anonymized aggregation data | Repository history |
| Analysis results | 1 year after last analysis | Anonymized aggregate statistics | Trend analysis |
| Workflows (generated YAML) | Indefinite | Full retention | Audit trail of AI decisions |
| Workflow runs | 1 year | Aggregate run statistics | Performance history |
| Findings | 1 year | Anonymized vulnerability trends | Security posture history |
| Recommendations | 1 year | Aggregate fix statistics | AI effectiveness tracking |
| Pull requests | Indefinite | Full retention | Operational history |
| Credentials | Until revoked/expired | NEVER (PII/secret data) | Security |
| Audit logs | 2 years | Compressed archive | Compliance |
| Session data (Redis) | 24 hours | NEVER | Minimal PII storage |

### 9.4.2 Archival Strategy

```sql
-- Scheduled job (runs weekly)
CREATE OR REPLACE FUNCTION archive_old_data() RETURNS void AS $$
BEGIN
    -- Archive findings older than 1 year
    INSERT INTO findings_archive
    SELECT * FROM findings
    WHERE created_at < NOW() - INTERVAL '1 year';
    
    DELETE FROM findings
    WHERE created_at < NOW() - INTERVAL '1 year';
    
    -- Archive workflow runs older than 1 year
    INSERT INTO workflow_runs_archive
    SELECT * FROM workflow_runs
    WHERE created_at < NOW() - INTERVAL '1 year';
    
    DELETE FROM workflow_runs
    WHERE created_at < NOW() - INTERVAL '1 year';
    
    -- Archive audit logs older than 2 years to cold storage
    -- (exported as Parquet to S3/MinIO)
END;
$$ LANGUAGE plpgsql;
```

---

## 9.5 Expected Schema Responsibilities

### 9.5.1 Referential Integrity

- All foreign keys use `ON DELETE CASCADE` for user-owned data (repositories, analysis results, workflows).
- For audit-sensitive tables (audit_logs, findings), use `ON DELETE SET NULL` to preserve historical records when users are deleted.
- Unique constraints on `(user_id, github_repo_id)` in repositories prevent duplicate connections.
- Unique constraint on `fingerprint` in findings prevents duplicate findings.

### 9.5.2 Performance Optimization

- JSONB indexes for frequently queried nested data:
  ```sql
  CREATE INDEX idx_analysis_results_tech ON analysis_results USING GIN (technologies);
  CREATE INDEX idx_findings_raw ON findings USING GIN (raw_output);
  ```
- Partial indexes for active records:
  ```sql
  CREATE INDEX idx_credentials_active_token ON credentials(user_id) WHERE is_active = true;
  CREATE INDEX idx_findings_open ON findings(severity) WHERE triage_status = 'open';
  ```
- Covering indexes for dashboard queries:
  ```sql
  CREATE INDEX idx_findings_dashboard ON findings(repository_id, severity, triage_status, created_at DESC);
  ```

### 9.5.3 Partitioning Strategy

- `findings` table: Partition by `created_at` (monthly) using PostgreSQL declarative partitioning.
- `audit_logs` table: Partition by `created_at` (monthly) for efficient archival.
- `workflow_runs` table: Partition by `created_at` (quarterly).

### 9.5.4 Migration Strategy

- Alembic (Python) for schema migrations, version-controlled in the repository.
- Migration naming convention: `YYYYMMDD_HHMM_description.py`.
- All migrations include both `upgrade()` and `downgrade()` functions.
- Pre-deployment migrations are tested against a staging database clone.
