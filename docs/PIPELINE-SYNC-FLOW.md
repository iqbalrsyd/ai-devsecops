# Pipeline Sync Flow

## Overview

Pipeline sync adalah mekanisme untuk menyinkronkan data workflow run dari GitHub Actions ke database aplikasi. Ini memastikan bahwa:
- Data pipeline selalu up-to-date
- Webhook events diproses dengan benar
- Job data tersimpan untuk analisis

---

## Sync Triggers

### 1. GitHub Webhook (Automatic)
```
GitHub Event → Backend Webhook Handler → Update/Create PipelineRun
```
**Events:**
- `workflow_run.completed`
- `workflow_run.in_progress`
- `workflow_run.queued`

### 2. Frontend Sync Button (Manual)
```
User clicks "Sync from GitHub" → API call → Backend fetches from GitHub → Update DB
```

### 3. Polling (Auto-refresh)
```
Frontend polls every 5s → Backend checks GitHub API → Update if changed
```

---

## Webhook Flow

```
┌──────────────┐     POST /api/v1/webhooks/github     ┌──────────────┐
│   GitHub     │ ────────────────────────────────────→ │   Backend    │
│   Actions    │     workflow_run event (completed)    │   (Go/Gin)   │
└──────────────┘                                      └──────┬───────┘
                                                              │
                                                              ▼
                                               ┌───────────────────────────────┐
                                               │  1. Parse event               │
                                               │  2. Find repository in DB     │
                                               │  3. Match workflow to pipeline│
                                               │     (by workflow_file path)   │
                                               │  4. Create/Update PipelineRun │
                                               └───────────────────────────────┘
                                                              │
                                                              ▼
                                               ┌───────────────────────────────┐
                                               │  If completed:                │
                                               │    → Trigger AI Analysis      │
                                               │    → POST /ai/pipeline/analyze │
                                               └───────────────────────────────┘
```

### Workflow Matching Logic
The webhook handler matches workflows to pipelines by comparing the workflow path from the GitHub event with the `workflow_file` stored in `deployment_results`:

1. Extract `workflow.path` from webhook event (e.g., `.github/workflows/ai-devsecops-v1.yml`)
2. Query all pipelines for the repository
3. For each pipeline, parse `deployment_results.workflow_file`
4. Match if paths are equal
5. Fall back to latest pipeline if no match

This ensures that runs from different pipeline versions are correctly linked to their respective pipelines.

### Webhook Handler Code
```go
// backend/handlers/webhook.go

func HandleGitHubWebhook(c *gin.Context) {
    var payload GitHubWebhookPayload
    c.ShouldBindJSON(&payload)
    
    if payload.Action == "completed" {
        workflowRun := payload.WorkflowRun
        
        // Find repository
        repo := repositoryRepo.FindByFullName(workflowRun.Repository.FullName)
        
        // Find latest pipeline
        pipeline := pipelineRepo.FindLatestByRepoID(repo.ID)
        
        // Create or update run
        existingRun := pipelineRunRepo.FindByGitHubRunID(workflowRun.ID)
        if existingRun {
            existingRun.Status = workflowRun.Status
            existingRun.Conclusion = workflowRun.Conclusion
            pipelineRunRepo.Update(existingRun)
        } else {
            newRun := PipelineRun{
                PipelineID: pipeline.ID,
                GitHubRunID: workflowRun.ID,
                RunNumber: workflowRun.RunNumber,
                Status: workflowRun.Status,
                Conclusion: workflowRun.Conclusion,
                HTMLURL: workflowRun.HTMLURL,
            }
            pipelineRunRepo.Create(newRun)
        }
        
        // Trigger analysis if completed
        if workflowRun.Status == "completed" {
            go triggerAnalysis(pipeline.ID, newRun.ID)
        }
    }
}
```

---

## Manual Sync Flow (Frontend)

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                  │
└─────────────────────────────────────────────────────────────────┘

User clicks "Sync from GitHub"
       ↓
useSyncRuns.mutateAsync({ repoId, version })
       ↓
POST /api/v1/repositories/:repoId/pipelines/:version/sync-runs
       ↓
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
└─────────────────────────────────────────────────────────────────┘

1. Find repository by repoId
2. Find pipeline by repoId + version
3. Get workflow_file from deployment_results (e.g., .github/workflows/ai-devsecops-v1.yml)
4. Extract filename for GitHub API (ai-devsecops-v1.yml)
5. Get workflow runs from GitHub API:
   GET /repos/{owner}/{repo}/actions/workflows/{filename}/runs
6. For each run:
   - Create or update PipelineRun record
   - Fetch jobs for completed runs:
     GET /repos/{owner}/{repo}/actions/runs/{runId}/jobs
   - Store jobs in pipeline_runs.jobs (JSONB)
7. Return list of synced run IDs

```

### Workflow File Handling
The sync endpoint handles versioned workflow filenames:
1. Reads `workflow_file` from `deployment_results` (full path)
2. Strips `.github/workflows/` prefix for GitHub API calls
3. Fetches runs only for that specific workflow file
4. This ensures runs from v1 workflow don't appear in v3 pipeline

### API Endpoint
```
POST /api/v1/repositories/:repoId/pipelines/:version/sync-runs

Response:
{
  "synced": ["run_id_1", "run_id_2", ...],
  "total": 5
}
```

---

## Polling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                  │
└─────────────────────────────────────────────────────────────────┘

useExecutionStatus(repositoryId, runId)
       ↓
Query runs every 5 seconds (if running)
       ↓
GET /api/v1/runs/:runId?repo_id=owner/repo
       ↓
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                   │
└─────────────────────────────────────────────────────────────────┘

1. Check if run has git_hub_run_id
2. If yes:
   - Decrypt repository access token
   - Call GitHub API:
     GET /repos/{owner}/{repo}/actions/runs/{runId}
     GET /repos/{owner}/{repo}/actions/runs/{runId}/jobs
   - Update pipeline_runs table
3. Return updated run data
```

### Polling Code
```typescript
// frontend/src/hooks/usePipelinesV2.ts

export function useExecutionStatus(repositoryId: string, runId: number | null) {
  return useQuery({
    queryKey: ["execution-status", repositoryId, runId],
    queryFn: async () => {
      const res = await api.get(`/runs/${runId}`, {
        params: { repository_id: repositoryId }
      })
      return res.data
    },
    enabled: !!repositoryId && !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "completed" || status === "success" || 
          status === "failure" || status === "cancelled") {
        return false  // Stop polling
      }
      return 5000  // Poll every 5 seconds
    },
  })
}
```

---

## Job Data Structure

GitHub API returns jobs in this format:

```json
{
  "jobs": [
    {
      "id": 123,
      "name": "lint",
      "status": "completed",
      "conclusion": "success",
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:01:30Z",
      "steps": [
        {
          "name": "Set up job",
          "status": "completed",
          "conclusion": "success",
          "number": 1,
          "started_at": "...",
          "completed_at": "..."
        },
        {
          "name": "Run golangci-lint",
          "status": "completed",
          "conclusion": "success",
          "number": 2,
          ...
        }
      ]
    }
  ]
}
```

### Stored in DB as JSONB
```sql
UPDATE pipeline_runs 
SET jobs = '[{"id": 123, "name": "lint", ...}]'::jsonb
WHERE id = :run_id
```

---

## Sync States

| State | Trigger | Action |
|-------|---------|--------|
| pending | Run created | Create record, wait |
| queued | Run queued | Update status |
| in_progress | Run started | Update status, start polling |
| completed | Run finished | Update conclusion, fetch jobs, trigger analysis |
| completed (failure) | Run failed | Update conclusion, fetch jobs, trigger analysis |

---

## Error Handling

### Webhook Failures
```
GitHub → Webhook fails (timeout/error)
       ↓
GitHub retries (configured in webhook settings)
       ↓
If still fails → Check GitHub webhook logs
       ↓
Manual sync via frontend
```

### Token Decryption Failures
```
Backend tries to decrypt access_token_encrypted
       ↓
Decryption fails (wrong key/corrupted)
       ↓
Log error, return empty jobs
       ↓
Frontend shows "No job data available"
```

### GitHub API Rate Limits
```
GitHub returns 403 Rate limit exceeded
       ↓
Backend implements exponential backoff
       ↓
Retry with delays
       ↓
Cache responses to reduce API calls
```

---

## Database Schema

### pipeline_runs
```sql
CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
  run_number INT NOT NULL,
  git_hub_run_id BIGINT,
  
  -- Status tracking
  status VARCHAR(20) DEFAULT 'pending',  -- pending, queued, running, completed
  conclusion VARCHAR(20),                  -- success, failure, cancelled, skipped, null
  
  -- GitHub data
  html_url TEXT,
  jobs JSONB,                              -- GitHub jobs array
  
  -- Timing
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_seconds INT,
  
  -- Metadata
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pipeline_runs_pipeline_id ON pipeline_runs(pipeline_id);
CREATE INDEX idx_pipeline_runs_github_run_id ON pipeline_runs(git_hub_run_id);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
```

### pipelines
```sql
CREATE TABLE pipelines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  
  -- Generation data
  prompt TEXT,
  generated_yaml TEXT,
  stages JSONB,
  generation_params JSONB,
  
  -- Validation & deployment
  validation_results JSONB,
  deployment_results JSONB,
  
  -- Metadata
  status VARCHAR(20) DEFAULT 'draft',  -- draft, generated, validated, deployed, failed
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  UNIQUE(repository_id, version_number)
);

CREATE INDEX idx_pipelines_repository_id ON pipelines(repository_id);
CREATE INDEX idx_pipelines_status ON pipelines(status);
```

---

## Performance Considerations

### Batch Processing
```go
// Sync multiple runs in one API call
func syncAllRuns(repo *Repository) {
    runs := github.GetWorkflowRuns(repo.FullName, repo.Token)
    
    for _, run := range runs {
        go syncSingleRun(run)  // Goroutine per run
    }
}
```

### Caching
```go
// Cache GitHub responses for 30 seconds
cache := redis.NewCache("github:", 30*time.Second)

func getRunFromGitHub(runID int64) (*GitHubRun, error) {
    cacheKey := fmt.Sprintf("run:%d", runID)
    
    if cached := cache.Get(cacheKey); cached != nil {
        return cached, nil
    }
    
    run := github.API.GetRun(runID)
    cache.Set(cacheKey, run)
    
    return run, nil
}
```

### Debouncing
```typescript
// Don't sync if sync already in progress
const [syncing, setSyncing] = useState(false)

const handleSync = async () => {
  if (syncing) return
  setSyncing(true)
  
  await syncRuns.mutateAsync({ repoId, version })
  
  setSyncing(false)
}
```

---

## Monitoring

### Metrics to Track
- Webhook delivery success rate
- Sync latency (GitHub → DB)
- GitHub API rate limit usage
- Failed syncs count
- Job data freshness

### Logs
```go
// Log sync events
log.Info("Syncing runs",
  "repo", repo.FullName,
  "count", len(runs),
  "duration", time.Since(start),
)

// Log errors
log.Error("Sync failed",
  "repo", repo.FullName,
  "error", err.Error(),
)
```

---

## File Locations

| File | Path | Description |
|------|------|-------------|
| Frontend | `frontend/src/pages/PipelineVersionDetail.tsx` | Sync button component |
| Hooks | `frontend/src/hooks/usePipelinesV2.ts` | useSyncRuns, useExecutionStatus |
| Backend | `backend/internal/handlers/pipeline_handler.go` | SyncRuns endpoint |
| Webhook | `backend/internal/handlers/webhook_handler.go` | Webhook handler |
| GitHub Service | `backend/internal/services/github_service.go` | ListWorkflowRunsForFile |
| Models | `backend/internal/models/pipeline.go` | Pipeline & PipelineRun models |
| AI Service | `ai-service/app/agents/nodes/pull_request_creation_node.py` | Workflow filename generation |

---

## Troubleshooting

### "Sync from GitHub" button not working
1. Check browser console for errors
2. Verify repository is connected (has access token)
3. Check GitHub token has `repo` scope
4. Verify backend can reach GitHub API

### Webhook not receiving events
1. Check GitHub webhook settings
2. Verify webhook URL is accessible
3. Check GitHub webhook delivery logs
4. Test webhook with curl:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"action":"completed",...}' \
     https://your-api.com/api/v1/webhooks/github
   ```

### Jobs not showing
1. Check if run has `git_hub_run_id` in DB
2. Verify access token is not expired
3. Check GitHub API rate limits
4. Verify jobs are stored in DB:
   ```sql
   SELECT jobs FROM pipeline_runs WHERE id = :run_id;
   ```

### Stale data
1. Check `updated_at` timestamp
2. Manually trigger sync
3. Check webhook delivery status in GitHub
4. Verify polling is working (check network tab)

### Runs linked to wrong pipeline version
1. Check `deployment_results.workflow_file` in DB for each pipeline:
   ```sql
   SELECT id, version_number, deployment_results FROM pipelines WHERE repository_id = :repo_id;
   ```
2. Verify workflow files are versioned (e.g., `ai-devsecops-v1.yml`, `ai-devsecops-v2.yml`)
3. Check webhook logs for workflow matching:
   - `[Webhook] Matched workflow '.github/workflows/ai-devsecops-v1.yml' to pipeline v1`
4. If runs still link to wrong pipeline, check if `deployment_results` is empty

### GitHub API returns 404 for workflow runs
1. Verify workflow filename in `deployment_results` is correct
2. Check if workflow file exists in repository:
   ```bash
   git ls-files .github/workflows/
   ```
3. GitHub API expects just filename, not full path:
   - Correct: `ai-devsecops-v1.yml`
   - Incorrect: `.github/workflows/ai-devsecops-v1.yml`
4. Check backend logs for: `[SyncRuns] Using workflow file: .github/workflows/ai-devsecops-v1.yml`