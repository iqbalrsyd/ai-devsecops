# Migration Report: AI DevSecOps Pipeline Engineer

**Date:** 2026-06-06
**Status:** Complete Assessment

---

## Table of Contents

1. Architecture Overview
2. Backend (Go) Assessment
3. AI Service (Python) Assessment
4. Frontend (React) Assessment
5. Files to Remove
6. Files to Refactor
7. Files to Create
8. Migration Plan
9. Database Migration Plan
10. LangGraph Refactoring Plan

---

## 1. Architecture Overview

### Current Architecture (Workflow Audit Agent)

```
Go Backend (Gin/Fiber)        Python AI Service (FastAPI)     React Frontend
┌──────────────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ Auth + Users          │     │ Old Graph (graph.py)    │     │ ScanUpload       │
│ Projects               │     │  intent_classifier    │     │ ScanDetail       │
│ Repositories           │     │  tool_selector        │     │ PRReview         │
│ Scans (LEGACY)         │     │  pr_review_tool       │     │ WorkflowAudit    │
│ Vulnerabilities(LEGACY)│     │  scan_tool            │     │ IncidentDetail   │
│ AI Reports (LEGACY)    │     │  workflow_tool        │     │ Incidents        │
│ Incidents (LEGACY)     │     │  report_tool          │     │ PipelineGen(*)   │
│ Pipeline Gen (*)       │     │  security_analyzer    │     │ PipelineDet(*)   │
│ Workflow Exec (*)      │     │  risk_assessor        │     │ SecurityRep(*)   │
│ Findings (*)            │     │  recommendation_gen   │     │ Dashboard(+)     │
│ Risk Assessments (*)    │     │  response_formatter   │     │                  │
│ Recommendations (*)     │     │                        │     │                  │
│ ComplianceMap (*)       │     │ New Graph (pipeline)   │     │                  │
│ GitHubDeployments (*)   │     │  requirement_analyzer  │     │                  │
└──────────────────────┘     │  project_profile_builder │     └──────────────────┘
  Key: (*) aligns with PRD   │  workflow_generator      │
       (+) partially aligns  │  workflow_validator      │
       (LEGACY) = remove     │  github_integration      │
                              │  workflow_execution      │
                              │  execution_monitor       │
                              │  compliance_mapper       │
                              │  security_analyzer       │
                              │  risk_assessor           │
                              │  recommendation_gen      │
                              │  response_formatter      │
                              └────────────────────────┘
```

### Target Architecture (Repository-Aware Pipeline Engineer)

```
Go Backend (Gin)              Python AI Service (FastAPI)     React Frontend
┌──────────────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ Auth + Users (KEEP)   │     │ New Pipeline Graph      │     │ RepositoryDashboard
│ Projects (KEEP)        │     │  repository_connection  │     │ Pipeline Dashboard│
│ Repositories (KEEP)    │     │  repository_scan        │     │ Execution Monitor│
│ Pipeline (REFACTOR)    │     │  technology_detection   │     │ Security Report  │
│ GitHub (REFACTOR)      │     │  architecture_detection │     │ History          │
│ Dashboard (REFACTOR)   │     │  security_req_inference │     │ Settings         │
│ + SSE Streaming (NEW)  │     │  workflow_generation    │     │                  │
│ + Webhooks (NEW)       │     │  workflow_validation    │     │                  │
│                        │     │  github_branch_create   │     │                  │
│                        │     │  pull_request_create    │     │                  │
│                        │     │  workflow_execution     │     │                  │
│                        │     │  execution_monitor      │     │                  │
│                        │     │  security_analysis      │     │                  │
│                        │     │  risk_assessment        │     │                  │
│                        │     │  recommendation_gen     │     │                  │
│                        │     │  response_formatter     │     │                  │
└──────────────────────┘     └────────────────────────┘     └──────────────────┘
```

---

## 2. Backend (Go) Assessment

### 2.1 Files to KEEP (with minor refactoring)

| File | Reason | Action |
|---|---|---|
| `cmd/server/main.go` | Core entry point | Refactor routing, drop legacy handlers |
| `internal/config/config.go` | Configuration loading | Keep |
| `internal/database/postgres.go` | PostgreSQL connection | Keep |
| `internal/database/redis.go` | Redis connection | Keep |
| `internal/middleware/auth.go` | JWT auth | Keep |
| `internal/middleware/cors.go` | CORS | Keep |
| `internal/middleware/logger.go` | Logging | Keep |
| `internal/utils/crypto.go` | AES encryption | Keep |
| `internal/models/user.go` | User model | Keep |
| `internal/models/project.go` | Project model | Keep |
| `internal/models/repository.go` | Repository model | Keep (add fields) |
| `internal/models/refresh_token.go` | Refresh token | Keep |
| `internal/models/role.go` | Role constants | Keep |
| `internal/services/auth_service.go` | Auth logic | Keep |
| `internal/services/project_service.go` | Project CRUD | Keep |
| `internal/services/repository_service.go` | Repo CRUD | Keep |
| `internal/services/github_service.go` | GitHub API | **Refactor heavily** - needs branch/create/commit/PR/workflow APIs |
| `internal/handlers/health.go` | Health check | Keep |
| `internal/handlers/auth_handler.go` | Auth endpoints | Keep |
| `internal/handlers/project_handler.go` | Project endpoints | Keep |
| `internal/handlers/repository_handler.go` | Repo endpoints | Keep |
| `internal/handlers/dashboard_handler.go` | Dashboard stats | **Refactor** - switch from scan-centric to pipeline-centric |

### 2.2 Files to REFACTOR

| File | Current Purpose | New Purpose | Changes |
|---|---|---|---|
| `main.go` | Registers all handlers | Register only new architecture handlers | Remove scan/incident/legacy handlers, add pipeline/webhook routes |
| `handlers/dashboard_handler.go` | Scan-centric stats | Pipeline-centric stats | Query pipeline_generations + workflow_executions + findings instead of scans + vulnerabilities |
| `services/github_service.go` | Read-only GitHub ops (validate token, fetch PR, fetch workflows) | Full GitHub integration | Add: create_branch, create_file, create_pr, trigger_workflow, get_workflow_run, list_workflow_jobs, get_workflow_logs |

### 2.3 Files to REMOVE (Legacy)

| File | Reason | Replacement |
|---|---|---|
| `internal/handlers/scan_handler.go` | Scan upload is obsolete | Replaced by auto-scanning in AI service |
| `internal/handlers/ai_handler.go` | AI endpoint routing to old audit graph | Replaced by direct pipeline API |
| `internal/handlers/pr_handler.go` | PR info fetch (duplicated in AI service) | Replaced by AI service PR operations |
| `internal/handlers/workflow_handler.go` | Workflow audit endpoint | Obsolete |
| `internal/handlers/incident_handler.go` | Incident management | Obsolete |
| `internal/services/scan_service.go` | Scan CRUD + parsing | Replaced by AI service security analysis |
| `internal/services/ai_service.go` | HTTP bridge to old AI service | Obsolete (AI service now drives directly) |
| `internal/services/incident_service.go` | Incident management | Obsolete |
| `internal/models/scan.go` | Scan model (upload-based) | Obsolete |
| `internal/models/vulnerability.go` | Vulnerability model | Obsolete (replaced by `Finding`) |
| `internal/models/ai_report.go` | AI report model | Obsolete |
| `internal/models/incident.go` | Incident model | Obsolete |

### 2.4 Models to KEEP (already match PRD)

These models in `internal/models/` already align with the PRD schema:

| Model | Status | Notes |
|---|---|---|
| `pipeline_generation.go` | Keep | Matches PRD |
| `github_deployment.go` | Keep | Matches PRD |
| `workflow_execution.go` | Keep | Matches PRD (remove `LogsURL` field) |
| `finding.go` | Keep | Matches PRD |
| `risk_assessment.go` | Keep | Matches PRD |
| `compliance_mapping.go` | Keep | Matches PRD |
| `recommendation.go` | Keep | Matches PRD |

### 2.5 Repository Files to KEEP

| File | Status |
|---|---|
| `internal/repositories/user_repository.go` | Keep |
| `internal/repositories/refresh_token_repository.go` | Keep |
| `internal/repositories/project_repository.go` | Keep |
| `internal/repositories/repository_repository.go` | Keep |

### 2.6 Repository Files to REMOVE

| File | Reason |
|---|---|
| `internal/repositories/scan_repository.go` | Scan model removed |
| `internal/repositories/incident_repository.go` | Incident model removed |

---

## 3. AI Service (Python) Assessment

### 3.1 New Pipeline Graph Nodes

The PRD specifies 16 nodes. Current `pipeline_graph.py` has 12 nodes. These need to be added/modified:

| Node | Status | Description |
|---|---|---|
| `repository_connection_node` | **NEW** | Validate GitHub token + repo access |
| `repository_scan_node` | **NEW** | Fetch repo contents, structure, key files |
| `technology_detection_node` | **NEW** | LLM-based tech stack classification |
| `architecture_detection_node` | **NEW** | LLM-based architecture inference |
| `security_requirement_inference_node` | **NEW** | LLM-based security needs inference |
| `workflow_generator_node` | **KEEP** | Already exists, update to use new state fields |
| `workflow_validator_node` | **KEEP** | Already exists |
| `github_branch_creation_node` | **REFACTOR** | Split from `github_integration_node` |
| `pull_request_creation_node` | **REFACTOR** | Split from `github_integration_node` |
| `workflow_execution_node` | **KEEP** | Already exists |
| `execution_monitor_node` | **KEEP** | Already exists |
| `security_analysis_node` | **REFACTOR** | Rename from `security_analyzer_node`, add unified finding format |
| `risk_assessment_node` | **KEEP** | Already exists |
| `recommendation_generation_node` | **KEEP** | Already exists (as `recommendation_gen`) |
| `response_formatter_node` | **KEEP** | Already exists |

### 3.2 Files to KEEP (AI Service)

| File | Action |
|---|---|
| `app/main.py` | Keep - entry point |
| `app/config.py` | Keep - settings |
| `app/database.py` | Keep - DB connection |
| `app/services/llm_service.py` | Keep - LLM provider |
| `app/services/github_service.py` | **REFACTOR** - add repo scanning + branch/commit/PR operations |
| `app/services/pipeline_service.py` | **REFACTOR** - update for new graph |
| `app/services/agent_service.py` | **REMOVE** - legacy old graph |
| `app/api/pipeline.py` | **REFACTOR** - add repo-aware endpoints |
| `app/agents/pipeline_state.py` | **REFACTOR** - add repo analysis fields |
| `app/agents/pipeline_schemas.py` | **REFACTOR** - add TechnologyProfile, ArchitectureProfile |
| `app/agents/pipeline_graph.py` | **REFACTOR** - new routing, new nodes |
| `app/agents/nodes/workflow_generator.py` | Keep |
| `app/agents/nodes/workflow_validator.py` | Keep |
| `app/agents/nodes/github_integration.py` | **SPLIT** into branch_creation + pr_creation |
| `app/agents/nodes/workflow_execution.py` | Keep |
| `app/agents/nodes/execution_monitor.py` | Keep (add timeout fix, SSE fields) |
| `app/agents/nodes/security_analyzer.py` | **REFACTOR** - use unified finding format from PRD |
| `app/agents/nodes/risk_assessor.py` | Keep (add 0-100 scoring per PRD) |
| `app/agents/nodes/compliance_mapper.py` | Keep |
| `app/agents/nodes/recommendation_gen.py` | Keep (add code example before/after) |
| `app/agents/nodes/response_formatter.py` | Keep |

### 3.3 Files to REMOVE (AI Service)

| File | Reason |
|---|---|
| `app/agents/graph.py` | Old audit graph (intent_classifier → tool_selector → tools) |
| `app/agents/security_agent.py` | Old AgentState for audit graph |
| `app/agents/schemas.py` | Old SecurityFinding, AgentResponse for audit graph |
| `app/agents/nodes/intent_classifier.py` | Audit intent routing obsolete |
| `app/agents/nodes/tool_selector.py` | Audit tool selection obsolete |
| `app/agents/nodes/pr_review_tool.py` | PR review obsolete (now part of pipeline flow) |
| `app/agents/nodes/scan_tool.py` | Manual scan upload tool obsolete |
| `app/agents/nodes/workflow_tool.py` | Workflow fetch tool obsolete |
| `app/agents/nodes/report_tool.py` | Report fetch from DB obsolete |
| `app/agents/nodes/requirement_analyzer.py` | Replaced by repository_scan + technology_detection |
| `app/agents/nodes/project_profile_builder.py` | Replaced by architecture_detection + security_inference |
| `app/api/analyze.py` | Old endpoints (/analyze, /review-pr, /audit-workflow) |
| `app/schemas/analyze.py` | Old request/response schemas |
| `app/services/agent_service.py` | Old graph runner |

### 3.4 New Files to CREATE (AI Service)

| File | Purpose |
|---|---|
| `app/agents/nodes/repository_connection_node.py` | Validate GitHub token + repo access |
| `app/agents/nodes/repository_scan_node.py` | Fetch repo structure + key config files |
| `app/agents/nodes/technology_detection_node.py` | LLM-based tech stack detection |
| `app/agents/nodes/architecture_detection_node.py` | LLM-based architecture detection |
| `app/agents/nodes/security_requirement_inference_node.py` | LLM-based security needs inference |
| `app/agents/nodes/github_branch_creation_node.py` | Create branch (split from github_integration) |
| `app/agents/nodes/pull_request_creation_node.py` | Commit + create PR (split from github_integration) |
| `app/agents/nodes/error_handler.py` | Centralized error handling node |

---

## 4. Frontend (React) Assessment

### 4.1 Pages to KEEP

| Page | Status |
|---|---|
| `login.tsx` | Keep |
| `register.tsx` | Keep |
| `landing.tsx` | Keep |
| `dashboard.tsx` | **REFACTOR** - switch from scan stats to pipeline/repo stats |
| `ProjectDetail.tsx` | **REFACTOR** - add repo analysis view, pipeline generation |
| `PipelineGenerator.tsx` | **REFACTOR** - convert to repo-aware generator |
| `PipelineDetail.tsx` | **REFACTOR** - add execution monitoring tab |
| `SecurityReport.tsx` | **REFACTOR** - add compliance scorecard, recommendations |

### 4.2 Pages to REMOVE

| Page | Reason |
|---|---|
| `ScanUpload.tsx` | Manual scan upload obsolete |
| `ScanDetail.tsx` | Manual scan viewing obsolete |
| `PRReview.tsx` | PR review via audit flow obsolete |
| `WorkflowAudit.tsx` | Workflow audit page obsolete |
| `Incidents.tsx` | Incident management obsolete |
| `IncidentDetail.tsx` | Incident detail obsolete |

### 4.3 Components to KEEP

| Component | Status |
|---|---|
| `ProtectedRoute.tsx` | Keep |
| `AuthLayout.tsx` | Keep |
| `CodeBlock.tsx` | Keep |
| `CodeDiff.tsx` | Keep |
| `YamlViewer.tsx` | Keep |
| `RiskScoreGauge.tsx` | Keep |
| `SeverityChart.tsx` | Keep |
| `VulnerabilityChart.tsx` | Keep |
| `FindingsTable.tsx` | Keep |
| `FindingCard.tsx` | Keep |
| `ComplianceScorecard.tsx` | Keep |
| `RecommendationsList.tsx` | Keep |
| `ValidationResults.tsx` | Keep |
| `ExecutionTimeline.tsx` | Keep |
| `LiveLogViewer.tsx` | Keep |
| `PRLink.tsx` | Keep |
| `ConnectRepoModal.tsx` | Keep |
| `QuickActions.tsx` | Keep |
| `RecentActivity.tsx` | Keep |
| `RequirementForm.tsx` | Keep |

### 4.4 Components to REMOVE

| Component | Reason |
|---|---|
| `IncidentReportView.tsx` | Incident obsolete |
| `NewIncidentModal.tsx` | Incident obsolete |
| `WorkflowFileCard.tsx` | Workflow audit obsolete |
| `VulnerabilityBadge.tsx` | Vulnerability model replaced by Finding |

### 4.5 New Components to CREATE

| Component | Purpose |
|---|---|
| `TechnologiesBadge.tsx` | Display detected tech stack as badges |
| `StageFlow.tsx` | Horizontal flow diagram of pipeline stages |
| `RepoAnalysisView.tsx` | Display repository detection results |
| `ArchitectureBadge.tsx` | Display detected architecture |

### 4.6 App.tsx Route Refactoring

**Remove routes:**
- `/projects/:id/upload`
- `/projects/:id/upload/:repoId`
- `/projects/:id/scans/:scanId`
- `/projects/:id/pr-review`
- `/projects/:id/workflow-audit`
- `/projects/:id/incidents/:incidentId`

**Add routes:**
- `/repositories/:id/analysis` - Repository analysis results
- `/repositories/:id/pipeline` - Generate pipeline for repo
- `/history` - Pipeline execution history
- `/settings` - LLM/GitHub settings

---

## 5. Files to Remove — Complete List

### Go Backend (9 files)
```
backend/internal/handlers/scan_handler.go
backend/internal/handlers/ai_handler.go
backend/internal/handlers/pr_handler.go
backend/internal/handlers/workflow_handler.go
backend/internal/handlers/incident_handler.go
backend/internal/services/scan_service.go
backend/internal/services/ai_service.go
backend/internal/services/incident_service.go
backend/internal/repositories/scan_repository.go
backend/internal/repositories/incident_repository.go
```

### Go Models (4 files)
```
backend/internal/models/scan.go
backend/internal/models/vulnerability.go
backend/internal/models/ai_report.go
backend/internal/models/incident.go
```

### AI Service (12 files)
```
ai-service/app/agents/graph.py
ai-service/app/agents/security_agent.py
ai-service/app/agents/schemas.py
ai-service/app/agents/nodes/intent_classifier.py
ai-service/app/agents/nodes/tool_selector.py
ai-service/app/agents/nodes/pr_review_tool.py
ai-service/app/agents/nodes/scan_tool.py
ai-service/app/agents/nodes/workflow_tool.py
ai-service/app/agents/nodes/report_tool.py
ai-service/app/agents/nodes/requirement_analyzer.py
ai-service/app/agents/nodes/project_profile_builder.py
ai-service/app/api/analyze.py
ai-service/app/schemas/analyze.py
ai-service/app/services/agent_service.py
```

### Frontend (6 pages)
```
frontend/src/pages/ScanUpload.tsx
frontend/src/pages/ScanDetail.tsx
frontend/src/pages/PRReview.tsx
frontend/src/pages/WorkflowAudit.tsx
frontend/src/pages/Incidents.tsx
frontend/src/pages/IncidentDetail.tsx
```

### Frontend (4 components)
```
frontend/src/components/IncidentReportView.tsx
frontend/src/components/NewIncidentModal.tsx
frontend/src/components/WorkflowFileCard.tsx
frontend/src/components/VulnerabilityBadge.tsx
```

---

## 6. Files to Refactor — Complete List

### Go Backend
| File | Change |
|---|---|
| `cmd/server/main.go` | Remove legacy handlers, add SSE/webhook routes, remove legacy models from AutoMigrate |
| `internal/handlers/dashboard_handler.go` | Query pipeline_generations + executions + findings instead of scans + vulnerabilities |
| `internal/services/github_service.go` | Add create_branch, create_file, create_pr, trigger_workflow_dispatch, get_workflow_run, list_workflow_jobs, get_workflow_logs |

### AI Service
| File | Change |
|---|---|
| `app/agents/pipeline_state.py` | Add: repository_url, github_token, repository_structure, detected_technologies, detected_architecture, inferred_security_needs, scan_results, severity_breakdown, security_posture, error_stage |
| `app/agents/pipeline_schemas.py` | Add: RepoPipelineRequest, TechnologyProfile, ArchitectureProfile, SecurityReport, Recommendation model |
| `app/agents/pipeline_graph.py` | New routing: add 5 new repo-analysis nodes, split github_integration into branch + PR nodes, update routing logic |
| `app/agents/nodes/security_analyzer.py` | Add scanner-specific parsers (Semgrep/Trivy/Gitleaks/DC), unified finding output per PRD |
| `app/agents/nodes/risk_assessor.py` | Update to PRD scoring: 0-100 scale, severity breakdown, security posture score |
| `app/agents/nodes/recommendation_gen.py` | Add before/after code examples, priority levels |
| `app/agents/nodes/workflow_generator.py` | Accept new state fields (detected_technologies, architecture) instead of project_profile |
| `app/agents/nodes/execution_monitor.py` | Fix timeout detection, add SSE event emission, collect artifact URLs |
| `app/agents/nodes/compliance_mapper.py` | Update to use new state fields |
| `app/agents/nodes/response_formatter.py` | Update to include risk_level, compliance mappings, severity breakdown |
| `app/services/github_service.py` | Add list_workflows, get_repo_contents, get_file_content functions |
| `app/services/pipeline_service.py` | Add run_repo_pipeline function (end-to-end), update for new graph |
| `app/api/pipeline.py` | Add POST /api/repo/pipeline (main entry point), POST /api/repo/analyze (analysis only) |

### Frontend
| File | Change |
|---|---|
| `src/App.tsx` | Remove legacy routes, add new repository/routes |
| `src/pages/dashboard.tsx` | Switch from scan stats to repo/pipeline/risk stats |
| `src/pages/ProjectDetail.tsx` | Add repository analysis view, pipeline generation button |
| `src/pages/PipelineGenerator.tsx` | Convert to repo-aware generator with detection results display |
| `src/pages/PipelineDetail.tsx` | Add execution monitoring tab with live logs |
| `src/pages/SecurityReport.tsx` | Add compliance scorecard, recommendations list |

---

## 7. Files to Create — Complete List

### AI Service (8 new files)
```
ai-service/app/agents/nodes/repository_connection_node.py
ai-service/app/agents/nodes/repository_scan_node.py
ai-service/app/agents/nodes/technology_detection_node.py
ai-service/app/agents/nodes/architecture_detection_node.py
ai-service/app/agents/nodes/security_requirement_inference_node.py
ai-service/app/agents/nodes/github_branch_creation_node.py
ai-service/app/agents/nodes/pull_request_creation_node.py
ai-service/app/agents/nodes/error_handler.py
```

### Frontend (4 new components)
```
frontend/src/components/TechnologiesBadge.tsx
frontend/src/components/StageFlow.tsx
frontend/src/components/RepoAnalysisView.tsx
frontend/src/components/ArchitectureBadge.tsx
```

### Go Backend (1 new file)
```
backend/internal/adapters/ai_adapter.go  (HTTP client to AI service for pipeline operations)
```

---

## 8. Migration Plan

### Phase 1: Remove Legacy (Day 1)
1. Delete all files listed in Section 5 (Files to Remove)
2. Update `go.mod` if needed (remove unused deps)
3. Remove legacy models from `main.go` AutoMigrate
4. Remove legacy routes from `main.go`
5. Remove legacy imports from `main.go`

### Phase 2: AI Service — New Graph Nodes (Day 2-3)
1. Create `repository_connection_node.py`
2. Create `repository_scan_node.py`
3. Create `technology_detection_node.py`
4. Create `architecture_detection_node.py`
5. Create `security_requirement_inference_node.py`
6. Create `github_branch_creation_node.py` (split from github_integration)
7. Create `pull_request_creation_node.py` (split from github_integration)
8. Create `error_handler.py`

### Phase 3: AI Service — Refactor Existing Nodes (Day 3-4)
1. Update `pipeline_state.py` — add new fields
2. Update `pipeline_schemas.py` — add new models
3. Update `pipeline_graph.py` — new routing, new nodes
4. Update `workflow_generator.py` — use new state fields
5. Update `security_analyzer.py` — scanner-specific parsers
6. Update `risk_assessor.py` — PRD scoring model
7. Update `recommendation_gen.py` — code examples
8. Update `execution_monitor.py` — SSE, timeout fix
9. Update `response_formatter.py` — full PRD output

### Phase 4: AI Service — API + Services (Day 4-5)
1. Update `pipeline_service.py` — new graph runner
2. Update `github_service.py` — add repo content fetching
3. Refactor `api/pipeline.py` — add repo-aware endpoints
4. Remove old API routes

### Phase 5: Go Backend — Refactor (Day 5-6)
1. Refactor `github_service.go` — add full CRUD operations
2. Refactor `main.go` — clean routing, remove old handlers
3. Refactor `handlers/dashboard_handler.go` — pipeline-centric stats
4. Create `adapters/ai_adapter.go` — HTTP client for AI pipeline ops

### Phase 6: Frontend — Remove Legacy (Day 6)
1. Delete legacy pages and components
2. Update `App.tsx` routes

### Phase 7: Frontend — Refactor (Day 7-8)
1. Refactor `dashboard.tsx`
2. Refactor `ProjectDetail.tsx`
3. Refactor `PipelineGenerator.tsx`
4. Refactor `PipelineDetail.tsx`
5. Refactor `SecurityReport.tsx`
6. Create new components: TechnologiesBadge, StageFlow, etc.

### Phase 8: Testing & Verification (Day 9-10)
1. Verify backend compiles and starts
2. Verify AI service starts and graph compiles
3. Verify frontend builds
4. End-to-end test: connect repo → analyze → generate → deploy → PR

---

## 9. Database Migration Plan

### Tables to DROP
```sql
DROP TABLE IF EXISTS scans CASCADE;
DROP TABLE IF EXISTS vulnerabilities CASCADE;
DROP TABLE IF EXISTS ai_reports CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
-- Keep: users, refresh_tokens, projects, repositories
-- Keep: pipeline_generations, github_deployments, workflow_executions
-- Keep: findings, risk_assessments, compliance_mappings, recommendations
```

### Columns to ADD
```sql
-- repositories: add support for repo analysis
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS last_scanned_at TIMESTAMPTZ;
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS detected_language VARCHAR(100);
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS detected_frameworks JSONB;
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS detected_architecture VARCHAR(100);

-- workflow_executions: add real-time monitoring support
ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS workflow_name VARCHAR(255);

-- pipeline_generations: add repo analysis integration
ALTER TABLE pipeline_generations ADD COLUMN IF NOT EXISTS analysis_id UUID REFERENCES repository_analyses(id);
```

### Column Modifications
```sql
-- workflow_executions: widen status enum
ALTER TABLE workflow_executions ALTER COLUMN status TYPE VARCHAR(50);
```

---

## 10. LangGraph Refactoring Plan

### Current Graph (`pipeline_graph.py`)

```
requirement_analyzer → project_profile_builder → workflow_generator → workflow_validator
                                                                          ↓
                                                               ┌──── passed ────┐
                                                               │                │
                                                          github_integration  error_handler
                                                               │                │
                                                          workflow_execution   │
                                                               │                │
                                                          execution_monitor    │
                                                               │                │
                                                          ┌──── completed ────┘
                                                          │
                                                     security_analyzer → risk_assessor → compliance_mapper → recommendation_gen → response_formatter → END
```

### New Graph

```
repository_connection → repository_scan → technology_detection → architecture_detection
                                                                          ↓
                                                             security_requirement_inference
                                                                          ↓
                                                                  workflow_generation
                                                                          ↓
                                                                  workflow_validation
                                                                          ↓
                                                               ┌──── passed ────┐
                                                               │                │
                                                          github_branch_creation  error_handler
                                                               │                │
                                                          pull_request_creation  │
                                                               │                │
                                                          workflow_execution    │
                                                               │                │
                                                          execution_monitor     │
                                                               │                │
                                                          ┌──── completed ─────┘
                                                          │
                                                     security_analysis → risk_assessment → recommendation_generation → response_formatter → END
```

### Routing Logic

| From | Condition | To |
|---|---|---|
| workflow_validation | validation_passed=True | github_branch_creation |
| workflow_validation | validation_passed=False | error_handler |
| execution_monitor | workflow_status=="completed" | security_analysis |
| execution_monitor | timeout/error | error_handler |
| error_handler | — | response_formatter |
| Any node | errors detected | error_handler (via `add_conditional_edges`) |

---

**End of Migration Report. Ready to begin implementation.**