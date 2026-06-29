# AI Pipeline Architecture — Current State

## Overview

- **Total node files**: 25 files di `app/agents/nodes/`
- **Entry point**: `app/api/pipeline.py` → `app/services/pipeline_service.py` → `_invoke_graph_phase()` / direct node calls
- **LangGraph graph**: `app/agents/pipeline_graph.py` (di-*compile* tapi TIDAK digunakan untuk routing — semua flow driven via `pipeline_service.py`)

> ⚠️ `pipeline_graph.py` di-*compile* tapi semua flow execution dilakukan langsung via `pipeline_service.py`, bukan via `pipeline_graph.invoke()`. Graph ini ada tapi tidak dipakai.

---

## 1. Pipeline Flows (Yang Dipakai)

### Flow A: `run_repo_pipeline` (Full Pipeline — dari API `/repo/pipeline`)
```
repository_connection → repository_scan → vulnerability_scan →
technology_detection → architecture_detection → deployment_detection →
security_requirement_inference → workflow_generation → workflow_validation →
[jika validation_errors ADA] → workflow_repair → workflow_validation →
run_repo_deploy (branch + PR creation)
```

**File**: `pipeline_service.py:1033` | **API endpoint**: `POST /pipeline/repo/pipeline`

---

### Flow B: `run_repo_analyze` (Analyze Only — dari API `/repo/analyze`)
```
repository_connection → repository_scan → vulnerability_scan →
technology_detection → architecture_detection → deployment_detection →
security_requirement_inference
```

**File**: `pipeline_service.py:686` | **API endpoint**: `POST /pipeline/repo/analyze`

---

### Flow C: `run_repo_generate` (Generate + Validate — dari API `/generate`)
```
repository_connection → repository_scan → vulnerability_scan →
technology_detection → architecture_detection → deployment_detection →
security_requirement_inference → workflow_generation → workflow_validation →
[jika validation_errors ADA] → workflow_repair → workflow_validation
```

**File**: `pipeline_service.py:801` | **API endpoint**: `POST /pipeline/generate`

---

### Flow D: `run_repo_deploy` (Branch + PR Creation — dari API `/deploy` atau auto_deploy)
```
repository_connection → github_branch_creation → pull_request_creation
```

**File**: `pipeline_service.py:839` | **API endpoint**: `POST /pipeline/deploy`

---

### Flow E: `run_repo_execute` (Trigger Workflow — dari API `/execute`)
```
repository_connection → workflow_execution
```

**File**: `pipeline_service.py:1049` | **API endpoint**: `POST /pipeline/execute`

---

### Flow F: `run_execution_analysis` (Analyze Failed Run — dari API `/analyze-execution/{run_id}`)
```
repository_connection
  → execution_log_collection (collect failed jobs + logs from GitHub API)
  → failure_analysis (classify failure type, confidence, explanation)
  → root_cause_detection (deep analysis, evidence, affected components)
  → remediation_generation (generate YAML fix from root cause)
  → remediation_pr_creation (create branch, commit fixed YAML, create PR)
```

**File**: `pipeline_service.py:1069` | **API endpoint**: `POST /pipeline/analyze-execution/{run_id}`
**Frontend trigger**: Tombol "Fix Failed Workflow" di RunDetail (muncul saat `run.conclusion === "failure"`)

---

### Flow G: `run_pipeline_analysis` (Post-Run Security Analysis — dari API `/analyze/{run_id}`)
```
security_analysis → risk_assessment → compliance_mapper →
recommendation_generation → response_formatter
```

**File**: `pipeline_service.py:1173` | **API endpoint**: `POST /pipeline/analyze/{run_id}`

---

## 2. Nodes — Dipakai vs Tidak Dipakai

### ✅ Dipakai (Langsung Dieksekusi)

| Node | File | Dipakai di Flow |
|------|------|-----------------|
| `repository_connection_node` | `repository_connection_node.py` | A, B, C, D, E, F |
| `repository_scan_node` | `repository_scan_node.py` | A, B, C |
| `vulnerability_scan_node` | `vulnerability_scan_node.py` | A, B, C |
| `technology_detection_node` | `technology_detection_node.py` | A, B, C |
| `architecture_detection_node` | `architecture_detection_node.py` | A, B, C |
| `deployment_detection_node` | `deployment_detection_node.py` | A, B, C |
| `security_requirement_inference_node` | `security_requirement_inference_node.py` | A, B, C |
| `workflow_generator_node` | `workflow_generator.py` | A, C |
| `workflow_validator_node` | `workflow_validator.py` | A, C, G |
| `github_branch_creation_node` | `github_branch_creation_node.py` | A, D |
| `pull_request_creation_node` | `pull_request_creation_node.py` | A, D |
| `workflow_execution_node` | `workflow_execution.py` | A, E |
| `execution_log_collection_node` | `execution_log_collection_node.py` | F |
| `workflow_failure_analysis_node` | `workflow_failure_analysis_node.py` | F |
| `root_cause_detection_node` | `root_cause_detection_node.py` | F |
| `workflow_remediation_generation_node` | `workflow_remediation_generation_node.py` | F |
| `remediation_pr_creation_node` | `remediation_pr_creation_node.py` | F |
| `security_analyzer_node` | `security_analyzer.py` | G |
| `risk_assessor_node` | `risk_assessor.py` | G |
| `compliance_mapper_node` | `compliance_mapper.py` | G |
| `recommendation_gen_node` | `recommendation_gen.py` | G |
| `response_formatter_node` | `response_formatter.py` | G |
| `workflow_repair_node` | `workflow_repair_node.py` | A, C (ENHANCED — 2 mode) |

### ❌ Dead Code (Ada di node_map tapi tidak pernah dipanggil)

| Node | File | Masalah |
|------|------|---------|
| `execution_monitor_node` | `execution_monitor.py` | Di-import di `pipeline_graph.py` dan `node_map`, tapi TIDAK ada di urutan `_invoke_graph_phase` manapun |

---

## 3. Schema Fields — Ada Tapi Tidak Dihitung

| Field | Schema | Node Penghitung | Status |
|-------|--------|----------------|--------|
| `workflow_quality_score` | `pipeline_analyses` (DB) | ✅ `SyncRuns` (backend Go) hitung dari job pass rate | ✅ Sudah |
| `security_coverage_score` | `pipeline_analyses` (DB) | ✅ `SyncRuns` (backend Go) hitung dari security job count | ✅ Sudah |

---

## 4. API Endpoints

### Backend (Go/Gin) — `/api/v1/*`

| Method | Path | Handler | Catatan |
|--------|------|---------|---------|
| GET | `/health` | HealthHandler | ✅ |
| GET | `/api/v1/health` | HealthHandler | ✅ |
| POST | `/api/v1/auth/register` | AuthHandler.Register | ✅ |
| POST | `/api/v1/auth/login` | AuthHandler.Login | ✅ |
| POST | `/api/v1/auth/refresh` | AuthHandler.Refresh | ✅ |
| GET | `/api/v1/me` | AuthHandler.Me | ✅ Enhanced — return full user object |
| PUT | `/api/v1/me` | AuthHandler.UpdateProfile | ✅ **BARU** |
| POST | `/api/v1/auth/change-password` | AuthHandler.ChangePassword | ✅ **BARU** |
| GET | `/api/v1/projects` | ProjectHandler.List | ✅ |
| POST | `/api/v1/projects` | ProjectHandler.Create | ✅ |
| GET | `/api/v1/projects/:projectId` | ProjectHandler.GetByID | ✅ |
| PUT | `/api/v1/projects/:projectId/compliance` | ProjectHandler.UpdateCompliance | ✅ |
| DELETE | `/api/v1/projects/:projectId` | ProjectHandler.Delete | ✅ |
| POST | `/api/v1/repositories/connect` | RepositoryHandler.Connect | ✅ |
| GET | `/api/v1/projects/:projectId/repositories` | RepositoryHandler.ListByProject | ✅ |
| GET | `/api/v1/repositories/:repoId` | RepositoryHandler.GetByID | ✅ |
| DELETE | `/api/v1/repositories/:repoId` | RepositoryHandler.Delete | ✅ |
| GET | `/api/v1/repositories/:repoId/insights` | PipelineHandler.GetInsights | ✅ |
| POST | `/api/v1/repositories/:repoId/analyze` | PipelineHandler.AnalyzeRepository | ✅ **BARU** |
| GET | `/api/v1/pipelines` | PipelineHandler.ListAll | ✅ |
| GET | `/api/v1/pipelines/:pipelineId` | PipelineHandler.GetByID | ✅ |
| DELETE | `/api/v1/pipelines/:pipelineId` | PipelineHandler.Delete | ✅ |
| POST | `/api/v1/pipelines/compare` | PipelineHandler.Compare | ✅ |
| GET | `/api/v1/repositories/:repoId/pipelines` | PipelineHandler.ListByRepository | ✅ |
| GET | `/api/v1/repositories/:repoId/pipelines/:version` | PipelineHandler.GetByVersion | ✅ |
| DELETE | `/api/v1/repositories/:repoId/pipelines/:version` | PipelineHandler.DeleteByVersion | ✅ **BARU** |
| POST | `/api/v1/repositories/:repoId/pipelines/generate` | PipelineHandler.Generate | ✅ **BARU** — orchestrate AI + save to DB |
| POST | `/api/v1/repositories/:repoId/pipelines/:version/sync-runs` | PipelineHandler.SyncRuns | ✅ |
| GET | `/api/v1/pipelines/:pipelineId/runs` | PipelineHandler.ListRuns | ✅ |
| GET | `/api/v1/runs/:runId` | PipelineHandler.GetRun | ✅ |
| POST | `/api/v1/runs/:runId/cancel` | PipelineHandler.CancelRun | ✅ **BARU** |
| GET | `/api/v1/runs/:runId/analysis` | PipelineHandler.GetAnalysis | ✅ |
| GET | `/api/v1/dashboard/stats` | DashboardHandler.Stats | ✅ |
| POST | `/api/v1/webhooks/github` | WebhookHandler.HandleGitHubWebhook | ✅ |

### AI Service (FastAPI) — `/ai/pipeline/*`

| Method | Path | Catatan |
|--------|------|---------|
| POST | `/pipeline/repo/analyze` | ✅ |
| POST | `/pipeline/repo/pipeline` | ✅ |
| POST | `/pipeline/generate` | ✅ |
| POST | `/pipeline/validate` | ✅ |
| POST | `/pipeline/deploy` | ✅ |
| POST | `/pipeline/execute` | ✅ |
| GET | `/pipeline/latest-run` | ✅ |
| GET | `/pipeline/status/:run_id` | ✅ |
| GET | `/pipeline/status/:run_id/stream` | ✅ SSE |
| GET | `/pipeline/logs/:run_id` | ✅ |
| POST | `/pipeline/analyze/:run_id` | ✅ |
| GET | `/pipeline/analysis/:run_id` | ✅ |
| POST | `/pipeline/analyze-execution/:run_id` | ✅ |
| POST | `/pipeline/compliance` | ✅ |
| POST | `/pipeline/webhook/github` | ✅ |

---

## 5. Frontend Routes

| Path | Component | Catatan |
|------|-----------|---------|
| `/` | LandingPage | ✅ |
| `/login` | LoginPage | ✅ |
| `/register` | RegisterPage | ✅ |
| `/dashboard` | DashboardPage | ✅ |
| `/projects/:projectId` | ProjectDetailPage | ✅ |
| `/projects/:projectId/repos/:repoId` | RepoDetailPage | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines` | PipelineHistory | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines/generate` | PipelineGenerator | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines/:version` | PipelineVersionDetail | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines/compare` | PipelineCompare | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId` | RunDetail | ✅ |
| `/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId/analysis` | RunAnalysis | ✅ **BARU** |
| `/pipelines` | PipelineHistory | ✅ |
| `/settings` | SettingsPage | ✅ **BARU** |

---

## 6. Ringkasan

```
Backend (Go):    19 → 25 endpoints (+6 baru: generate, analyze, delete-by-version, cancel-run, update-profile, change-password)
AI Service:      15 endpoints (semua ada)
Frontend routes: 14 → 15 (+settings, +analysis page)
Frontend hooks:  semua AI endpoints sekarang wired ke usePipeline.ts

Dipakai:         23 nodes (semua remediation nodes sekarang aktif)
Dead code:       1 node (execution_monitor)
Remediation flow: 5-node chain (collection → analysis → root_cause → fix → PR)
```

---

## 7. Files Baru / Ubah

### Backend (Go)
- `internal/services/ai_service.go` — **BARU** — HTTP client ke AI service
- `internal/handlers/pipeline_handler.go` — **UBAH** — +Generate, +AnalyzeRepository, +DeleteByVersion, +CancelRun
- `internal/handlers/auth_handler.go` — **UBAH** — +UpdateProfile, +ChangePassword, Me enhanced
- `internal/services/auth_service.go` — **UBAH** — +GetUserByID, +UpdateUser, +ChangePassword
- `internal/repositories/user_repository.go` — **UBAH** — +Update method
- `internal/services/github_service.go` — **UBAH** — +CancelWorkflowRun
- `cmd/server/main.go` — **UBAH** — register semua endpoint baru

### Frontend
- `src/pages/Settings.tsx` — **BARU**
- `src/App.tsx` — **UBAH** — +settings route, +analysis route
- `src/hooks/usePipeline.ts` — **UBAH** — +usePipelineAnalyze, +useWorkflowCompliance
- `src/pages/RunDetail.tsx` — **UBAH** — +link ke analysis page, **+ tombol "Fix Failed Workflow"** (trigger remediation chain)
- `src/components/Header.tsx` — **UBAH** — +settings icon

### AI Service
- `app/agents/nodes/workflow_repair_node.py` — **UBAH** — 2 mode repair (validation + execution failure)
- `app/models/schemas.py` — **UBAH** — +ExecutionFailureFix schema