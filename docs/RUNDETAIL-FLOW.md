# RunDetail - Pipeline Run Analysis

## Overview

`RunDetail` adalah halaman di aplikasi yang menampilkan detail eksekusi pipeline dari GitHub Actions, termasuk:
- Status dan hasil setiap job
- Security analysis (Risk Score, Compliance, Security Coverage, Workflow Quality)
- Severity breakdown (critical, high, medium, low)
- Security findings/vulnerabilities
- Recommendations

---

## Page URL Structure

```
/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId
```

**Example:**
```
http://localhost:5173/projects/3e0e4d27-b3af-4de7-96a3-0098855d2b11/repos/6fc6baa5-b26d-4542-bd40-6f4db66e3858/pipelines/27/runs/45d23dd3-1f2a-4741-b7e5-7ee8d73a6c89
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER FLOW                                    │
└─────────────────────────────────────────────────────────────────────────┘

1. User navigasi ke RunDetail page
   ↓
2. React Query: useRunDetail(runId) - Ambil data run dari backend
   ↓
3. React Query: useRunAnalysis(runId) - Ambil AI analysis dari backend
   ↓
4. Backend fetch dari GitHub API:
   - GET /repos/{owner}/{repo}/actions/runs/{runId}
   - GET /repos/{owner}/{repo}/actions/runs/{runId}/jobs
   ↓
5. Backend decrypt access token, fetch jobs dari GitHub
   ↓
6. Simpan jobs ke DB (pipeline_runs.jobs - JSONB)
   ↓
7. Frontend render dengan polling 5 detik (jika running)
   ↓
8. Tampilkan: Summary Card → Jobs List → Analysis Cards

┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND FLOW                                    │
└─────────────────────────────────────────────────────────────────────────┘

GitHub Webhook (workflow_run completed)
       ↓
POST /api/v1/webhooks/github
       ↓
Backend parse event → cari repository → cari pipeline → create/update PipelineRun
       ↓
Simpan status, conclusion, html_url ke DB

OR

Frontend polling: GET /api/v1/runs/:runId
       ↓
Backend check if git_hub_run_id exists
       ↓
Decrypt access_token_encrypted (AES-256-GCM)
       ↓
GitHub API: GET /actions/runs/{runId}
       ↓
GitHub API: GET /actions/runs/{runId}/jobs
       ↓
Update pipeline_runs.jobs (JSONB)
       ↓
Return run + jobs to frontend
```

---

## Components Structure

```
RunDetail
├── Header (breadcrumbs + status icon)
├── Summary Card (all passed / some failing / still running)
│   ├── Status Icon (CheckCircle2/XCircle/Loader2)
│   ├── Title & Description
│   ├── Duration
│   └── "View on GitHub" button
│
├── Job List (expandable cards)
│   ├── Failing Checks (red)
│   ├── Running Checks (blue)
│   ├── Successful Checks (green)
│   └── Other Checks (gray)
│
└── Analysis Section (if analysis exists)
    ├── Score Cards (4 cards)
    │   ├── Risk Score
    │   ├── Compliance
    │   ├── Security Coverage
    │   └── Workflow Quality
    │
    ├── Severity Breakdown (4 columns)
    │   ├── Critical (red)
    │   ├── High (orange)
    │   ├── Medium (yellow)
    │   └── Low (blue)
    │
    ├── AI Analysis (explanation text)
    │
    ├── Security Findings (expandable list)
    │   ├── Severity Badge
    │   ├── Title/Type
    │   ├── Scanner Badge
    │   ├── Explanation
    │   ├── File:Line (code location)
    │   ├── Recommendation
    │   └── Code Snippet (if any)
    │
    └── Recommendations (list)
        ├── Title
        ├── Description
        ├── Remediation
        └── Priority Badge
```

---

## Hooks Used

### `useRunDetail(runId)`
```typescript
// Fetch run detail from backend
GET /api/v1/runs/:runId

// Response:
{
  id, pipeline_id, run_number, git_hub_run_id,
  status, conclusion, html_url,
  duration_seconds, created_at,
  jobs: JSONB // parsed from GitHub API
}
```

**Behavior:**
- Polls every 5 seconds if status is "running", "queued", "pending"
- Fetches fresh data from GitHub API if `git_hub_run_id` exists
- Decrypts repository access token automatically

### `useRunAnalysis(runId)`
```typescript
// Fetch AI-generated analysis
GET /api/v1/runs/:runId/analysis

// Response:
{
  risk_score,        // float (0-100)
  compliance_score,   // float (0-100)
  security_coverage_score,
  workflow_quality_score,
  findings_summary, // JSON array
  severity_breakdown, // JSON {critical, high, medium, low}
  recommendations,   // JSON array
  ai_explanation
}
```

---

## State Management

### Job Categorization
```typescript
const failingJobs = jobs.filter(j => 
  j.conclusion === "failure" || 
  j.conclusion === "cancelled" || 
  j.conclusion === "skipped"
)

const successfulJobs = jobs.filter(j => 
  j.conclusion === "success"
)

const pendingJobs = jobs.filter(j => 
  !j.conclusion || 
  j.status === "running" || 
  j.status === "queued" || 
  j.status === "pending"
)
```

### Display States
| State | Condition | UI |
|-------|-----------|-----|
| All Passed | `failedCount === 0 && pendingCount === 0 && totalChecks > 0` | Green summary card |
| Some Failing | `failedCount > 0` | Red summary card |
| Still Running | `pendingCount > 0` | Blue summary card + spinner |
| No Job Data | `jobs.length === 0` | Empty state message |

---

## Polling Logic

```typescript
// From useExecutionStatus hook
refetchInterval: (query) => {
  const status = query.state.data?.status
  if (status === "completed" || status === "success" || 
      status === "failure" || status === "cancelled") {
    return false  // Stop polling
  }
  return 5000  // Poll every 5 seconds
}
```

**When polling stops:**
- Status is `completed`
- Conclusion is `success`, `failure`, or `cancelled`

---

## Security Analysis Scores

| Score | Range | Color | Meaning |
|-------|-------|-------|---------|
| Risk Score | 0-100 | Red < 60, Yellow 30-60, Green > 30 | Higher = more risk |
| Compliance | 0-100 | Blue | Higher = more compliant |
| Security Coverage | 0-100 | Purple | Higher = more covered |
| Workflow Quality | 0-100 | Teal | Higher = better quality |

---

## Severity Breakdown

| Severity | Color | Background | Used For |
|----------|-------|------------|----------|
| Critical | Red | #fef2f2 | Immediate security issues |
| High | Orange | #fff7ed | Significant security issues |
| Medium | Yellow | #fefce8 | Moderate security issues |
| Low | Blue | #eff6ff | Minor security issues |

---

## Data Parsing

```typescript
// Parse jobs from JSONB
const jobs: PipelineJob[] = run.jobs 
  ? JSON.parse(run.jobs as string) 
  : []

// Parse findings
const findings = analysis.findings_summary 
  ? JSON.parse(analysis.findings_summary as string) 
  : []

// Parse severity
const severity: Record<string, number> = analysis.severity_breakdown 
  ? JSON.parse(analysis.severity_breakdown as string) 
  : {}

// Parse recommendations
const recommendations = analysis.recommendations 
  ? JSON.parse(analysis.recommendations as string) 
  : []
```

---

## Finding Structure

```typescript
interface Finding {
  scanner?: string       // e.g., "trivy", "semgrep", "gitleaks"
  type?: string          // e.g., "vulnerability", "secret", "misconfiguration"
  severity?: string      // "critical" | "high" | "medium" | "low"
  file?: string           // e.g., "src/main.go"
  line?: number          // line number in file
  code_snippet?: string   // code causing the issue
  explanation?: string    // human-readable explanation
  recommendation?: string // how to fix
  title?: string          // finding title
}
```

---

## Recommendation Structure

```typescript
interface Recommendation {
  title?: string          // recommendation title
  description?: string    // detailed description
  remediation?: string   // how to implement
  priority?: string        // "high" | "medium" | "low"
  impact?: string          // impact of the recommendation
}
```

---

## Backend API Endpoints

### GET /api/v1/runs/:runId
Fetch run detail (from DB or GitHub API)

**Response:**
```json
{
  "id": "uuid",
  "pipeline_id": "uuid",
  "run_number": 1,
  "git_hub_run_id": 12345678,
  "status": "completed",
  "conclusion": "success",
  "html_url": "https://github.com/owner/repo/actions/runs/12345678",
  "duration_seconds": 180,
  "jobs": "[{\"id\": 1, \"name\": \"lint\", ...}]"
}
```

### GET /api/v1/runs/:runId/analysis
Fetch AI analysis from DB

**Response:**
```json
{
  "risk_score": 45.5,
  "compliance_score": 85.0,
  "security_coverage_score": 78.0,
  "workflow_quality_score": 92.0,
  "findings_summary": "[{\"severity\": \"high\", ...}]",
  "severity_breakdown": "{\"critical\": 4, \"high\": 4, \"medium\": 2, \"low\": 0}",
  "recommendations": "[{\"title\": \"Fix X\", ...}]",
  "ai_explanation": "The pipeline completed successfully..."
}
```

### POST /api/v1/webhooks/github
Receive GitHub webhook for workflow_run events

**Body:**
```json
{
  "action": "completed",
  "workflow_run": {
    "id": 12345678,
    "status": "completed",
    "conclusion": "success",
    "html_url": "...",
    "run_number": 1
  },
  "repository": {
    "full_name": "owner/repo"
  }
}
```

---

## Database Schema

### pipeline_runs
```sql
CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY,
  pipeline_id UUID REFERENCES pipelines(id),
  run_number INT,
  git_hub_run_id BIGINT,
  status VARCHAR(20),        -- pending, queued, running, completed
  conclusion VARCHAR(20),    -- success, failure, cancelled, skipped
  html_url TEXT,
  jobs JSONB,                -- GitHub jobs array
  duration_seconds INT,
  created_at TIMESTAMP
);
```

### pipeline_analyses
```sql
CREATE TABLE pipeline_analyses (
  id UUID PRIMARY KEY,
  pipeline_run_id UUID REFERENCES pipeline_runs(id),
  risk_score FLOAT,
  compliance_score FLOAT,
  workflow_quality_score FLOAT,
  security_coverage_score FLOAT,
  findings_summary JSONB,
  severity_breakdown JSONB,
  recommendations JSONB,
  ai_explanation TEXT,
  raw_scan_data JSONB,
  created_at TIMESTAMP
);
```

---

## File Locations

| File | Path | Description |
|------|------|-------------|
| Page | `frontend/src/pages/RunDetail.tsx` | Main page component |
| Hooks | `frontend/src/hooks/usePipelinesV2.ts` | Data fetching hooks |
| Backend | `backend/handlers/pipeline.go` | Run detail handler |
| DB | `backend/models/pipeline_run.go` | Database model |

---

## Troubleshooting

### "No job data available"
- Check if GitHub access token is valid
- Check if repository is connected properly
- Check webhook delivery in GitHub settings

### "Pipeline is running" but no jobs
- GitHub might still be collecting job data
- Check GitHub Actions UI directly
- Verify webhook is configured

### Analysis shows 0.0 for all scores
- Analysis might not be generated yet
- Check if `/api/v1/runs/:runId/analysis` returns data
- Verify pipeline_analyses table has records

### Jobs not updating
- Polling might be disabled
- Check network tab for failed requests
- Verify GitHub API rate limits not hit

---

## Pipeline ID Linking Issue

### Problem
When a workflow runs from a PR, the PipelineRun might be linked to the wrong pipeline_id. This happens because:

1. **Webhook Handler** uses `pipelines[0]` - always takes the first (latest) pipeline
2. **SyncRuns** uses specific pipeline_id from URL params
3. If multiple pipelines exist, webhook might link to wrong pipeline

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WEBHOOK HANDLER (webhook_handler.go)                   │
└─────────────────────────────────────────────────────────────────────────┘

GitHub sends workflow_run event
       ↓
Find repository by full_name
       ↓
Find pipelines: h.pipelineRepo.FindByRepository(repo.ID)
       ↓
USE pipelines[0] ← PROBLEM: Takes first (latest), not specific version
       ↓
Create PipelineRun with pipeline_id = pipelines[0].ID

┌─────────────────────────────────────────────────────────────────────────┐
│                    SYNC RUNS (pipeline_handler.go)                        │
└─────────────────────────────────────────────────────────────────────────┘

User clicks "Sync from GitHub"
       ↓
Get pipeline_id from URL: /repositories/:repoId/pipelines/:version/sync-runs
       ↓
Find specific pipeline by repo_id + version
       ↓
Delete existing runs for this pipeline
       ↓
Fetch runs from GitHub for workflow file
       ↓
Create PipelineRuns with correct pipeline_id

RESULT: SyncRuns creates correct link, webhook might create duplicate with wrong link
```

### Root Cause Analysis

In `webhook_handler.go` line 113-119:
```go
pipelines, err := h.pipelineRepo.FindByRepository(repo.ID)
if err != nil || len(pipelines) == 0 {
    c.JSON(http.StatusOK, gin.H{"message": "no pipeline found for repository, skipping"})
    return
}
pipeline := pipelines[0]  // ← Always uses first pipeline (latest)
```

This assumes all workflow runs belong to the latest pipeline, which is incorrect when:
- User has pipeline v1, v2, v3
- Workflow from PR might be from v1 or v2
- Webhook links to v3 instead of correct version

### Solution

The workflow file name should include the pipeline version to enable correct linking:

**Current (Problem):**
```
.github/workflows/ci-cd.yml
.github/workflows/devsecops.yml
```

**Fixed (Solution):**
```
.github/workflows/ai-devsecops-v1.yml
.github/workflows/ai-devsecops-v2.yml
.github/workflows/ai-devsecops-v3.yml
```

### Implementation

1. **AI Service** - Generate workflow with version in filename:
```python
# In pull_request_creation_node.py
workflow_filename = f".github/workflows/ai-devsecops-v{version}.yml"
```

2. **Backend** - Store workflow filename in deployment_results:
```go
// In pipeline_handler.go SyncRuns
workflowFile := ""
if pipeline.DeploymentResults != "" {
    var depInfo struct {
        WorkflowFile string `json:"workflow_file"`
    }
    json.Unmarshal([]byte(pipeline.DeploymentResults), &depInfo)
    workflowFile = depInfo.WorkflowFile
}
```

3. **Webhook** - Match workflow file to pipeline:
```go
// Find pipeline by workflow file pattern
for _, p := range pipelines {
    if strings.Contains(p.DeploymentResults, workflowFileFromEvent) {
        pipeline = p
        break
    }
}
```

### Verification

Check if pipeline_id matches:

```sql
-- Check runs for a specific pipeline
SELECT 
    pr.id as run_id,
    pr.pipeline_id,
    p.version_number,
    pr.github_run_id,
    pr.status
FROM pipeline_runs pr
JOIN pipelines p ON pr.pipeline_id = p.id
WHERE p.repository_id = 'your-repo-id'
ORDER BY pr.created_at DESC;

-- Check deployment_results for workflow file
SELECT 
    id,
    version_number,
    deployment_results
FROM pipelines
WHERE repository_id = 'your-repo-id'
ORDER BY version_number DESC;
```

### Expected Result

| run_id | pipeline_id | version | github_run_id | workflow_file |
|--------|-------------|---------|---------------|---------------|
| abc123 | xyz789 | 3 | 123456 | ai-devsecops-v3.yml |
| def456 | uvw123 | 2 | 123457 | ai-devsecops-v2.yml |
| ghi789 | rst456 | 1 | 123458 | ai-devsecops-v1.yml |

Each run should link to the correct pipeline version based on the workflow file used.