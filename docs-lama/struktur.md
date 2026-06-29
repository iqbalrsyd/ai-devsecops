# Struktur Aplikasi (v3 — Pipeline-Centric)

## Route Map

| Route | Page | Deskripsi |
|---|---|---|
| `/` | Landing | Brand page, tombol Login / Register |
| `/login` | Login | Form email + password |
| `/register` | Register | Form name/email/password |
| `/dashboard` | Dashboard | Aggregated stats across ALL projects, repos, pipelines |
| `/projects/:projectId` | ProjectDetail | Overview + Repositories tabs |
| `/projects/:projectId/repos/:repoId` | RepoDetail | Overview + Pipelines + Insights tabs |
| `/projects/:projectId/repos/:repoId/pipelines` | PipelineHistory | All pipeline versions for this repo |
| `/projects/:projectId/repos/:repoId/pipelines/generate` | PipelineGenerator | Generate pipeline with structured inputs |
| `/projects/:projectId/repos/:repoId/pipelines/:version` | PipelineVersionDetail | Workflow + Runs + Details tabs |
| `/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId` | RunDetail | Execution detail + jobs + timeline |
| `/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId/analysis` | RunAnalysis | AI-generated scores, findings, recommendations |
| `/projects/:projectId/repos/:repoId/pipelines/compare` | PipelineCompare | Compare two pipeline versions |
| `/pipelines` | PipelineHistory | Global pipeline history across all repos |

## Flow User

```
Landing → Login → Dashboard
                      │
                      ├─ Klik project → ProjectDetail
                      │                   ├─ [Overview] → Stat cards, repos
                      │                   └─ [Repositories] → List repo
                      │                        └─ Klik repo → RepoDetail
                      │                             ├─ [Overview] → Repo info, latest pipeline
                      │                             ├─ [Pipelines] → All versions 
                      │                             │    ├─ Klik version → PipelineVersionDetail
                      │                             │    │    ├─ [Workflow] → YAML + explanation
                      │                             │    │    ├─ [Runs] → List runs
                      │                             │    │    │    └─ Klik run → RunDetail
                      │                             │    │    │         └─ Analysis → RunAnalysis
                      │                             │    │    └─ [Details] → Params, controls
                      │                             │    ├─ Generate → PipelineGenerator
                      │                             │    └─ Compare → PipelineCompare
                      │                             └─ [Insights] → Languages, frameworks, tools
                      │
                      └─ Klik pipeline (global) → PipelineHistory
```

## Detail Page & Logic

### 1. Dashboard
- **Data:** `GET /api/v1/dashboard/stats`
- **Komponen:** Stat cards (Total Projects/Repos/Pipelines/Executions), Pipeline Success Rate, Avg Risk Score, Compliance Score, Security Coverage, Recent Pipelines
- **Flow:** Klik project → `/projects/:id`

### 2. ProjectDetail
- **Data:** `GET /projects`, `GET /projects/:projectId/repositories`
- **2 Tab:** Overview (project info + repo cards), Repositories (full list + connect)
- **Flow:** Klik repo → `/projects/:id/repos/:repoId`

### 3. RepoDetail
- **Data:** `GET /repositories/:id`, `GET /repositories/:repoId/pipelines`, `GET /repositories/:repoId/insights`
- **3 Tab:** Overview (info + quick actions + latest pipeline), Pipelines (all versions), Insights (languages, frameworks, tools)
- **Flow:** Klik Generate → `/projects/:id/repos/:repoId/pipelines/generate`

### 4. PipelineHistory (global or per-repo)
- **Data:** `GET /api/v1/pipelines` (global, paginated) or `GET /repositories/:repoId/pipelines`
- **Komponen:** Search, filter, sort, pagination, compare button
- **Flow:** Klik version → detail page

### 5. PipelineGenerator
- **Data:** Pre-filled from repository insights
- **Flow:** Generate → validate → deploy PR

### 6. PipelineVersionDetail
- **Data:** `GET /repositories/:repoId/pipelines/:version`
- **3 Tab:** Workflow (YAML + AI explanation), Runs (list pipeline runs), Details (params, controls)

### 7. RunDetail
- **Data:** `GET /runs/:runId`
- **Komponen:** Duration, GitHub link, timeline, jobs list
- **Flow:** View Analysis → `/runs/:runId/analysis`

### 8. RunAnalysis
- **Data:** `GET /runs/:runId/analysis`
- **Komponen:** Risk Score, Compliance Score, Security Coverage, Workflow Quality, Severity Breakdown, Findings Summary, Recommendations

### 9. PipelineCompare
- **Data:** `POST /api/v1/pipelines/compare`
- **Komponen:** Two selects, Score comparison cards, Detailed delta table

## API Reference

### Backend (Go) — `GET /api/v1/*`
| Endpoint | Method | Purpose |
|---|---|---|
| `/dashboard/stats` | GET | Dashboard aggregated stats |
| `/projects` | GET/POST | List/create projects |
| `/projects/:id` | GET/DELETE | Get/delete project |
| `/repositories/connect` | POST | Connect GitHub repo |
| `/projects/:projectId/repositories` | GET | List repos |
| `/repositories/:id` | GET/DELETE | Get/delete repo |
| `/repositories/:repoId/insights` | GET | Repository insights |
| `/repositories/:repoId/pipelines` | GET | List pipeline versions |
| `/repositories/:repoId/pipelines/:version` | GET | Get pipeline by version |
| `/pipelines` | GET | List all pipelines (global) |
| `/pipelines/:pipelineId` | GET/DELETE | Get/delete pipeline |
| `/pipelines/:pipelineId/runs` | GET | List runs for pipeline |
| `/pipelines/compare` | POST | Compare two pipelines |
| `/runs/:runId` | GET | Get run detail |
| `/runs/:runId/analysis` | GET | Get pipeline analysis |
| `/auth/*` | POST | Auth endpoints |
| `/health` | GET | Health check |
| `/webhooks/github` | POST | GitHub webhook receiver |

## Flow Job Data dari GitHub (Run Detail)

### 1. Github Webhook → Buat PipelineRun
```
[GitHub Actions]
  → workflow_run event (queued | in_progress | completed)
  → POST /api/v1/webhooks/github
      Body: {
        "action": "completed",
        "workflow_run": { id, status, conclusion, html_url, run_number },
        "repository": { full_name }
      }
  → [Backend] parse event type (X-GitHub-Event header)
  → [Backend] cari repository dari DB by full_name
  → [Backend] cari pipeline terbaru dari repository
  → [Backend] cari existing PipelineRun by github_run_id
      ├─ if not found → CREATE PipelineRun { pipeline_id, github_run_id, status, conclusion }
      └─ if found → UPDATE status/conclusion
  ← [GitHub] 200 OK
```

### 2. Get Run Detail → Fetch Jobs dari GitHub API
```
[Frontend] RunDetail.tsx
  → useRunDetail(runId) → polling setiap 5 detik (sampai completed/failed)
  → GET /api/v1/runs/:runId

[Backend] PipelineHandler.GetRun
  → runRepo.FindByID(runId) → preload Pipeline + Repository
  → if github_run_id > 0 && repository has token:
      → decrypt AccessTokenEncrypted (AES-256-GCM)
      → GitHub API: GET /repos/{owner}/{repo}/actions/runs/{runId}
          ← { status, conclusion, html_url }
      → Backend: update run.Status, run.Conclusion, run.HTMLURL
      → GitHub API: GET /repos/{owner}/{repo}/actions/runs/{runId}/jobs
          ← { jobs: [{ id, name, status, conclusion, steps: [...] }] }
      → Backend: map ke JSON → simpan ke run.Jobs (JSONB)
      → Backend: runRepo.Update(run)
  → return run (with jobs)

[Frontend]
  → run.jobs ? JSON.parse(run.jobs) : []
  → Tampilkan:
      ├─ Summary card (all passed / some failing / still running)
      ├─ Failing checks → JobCard → steps
      ├─ Running checks → JobCard → steps (dengan spinner)
      ├─ Successful checks → JobCard → steps
      └─ No job data available (jika jobs.length === 0)
```

### 3. List Runs (tanpa job detail)
```
[Frontend] PipelineVersionDetail.tsx
  → usePipelineRuns(pipelineId)
  → GET /api/v1/pipelines/:pipelineId/runs

[Backend] PipelineHandler.ListRuns
  → runRepo.FindByPipeline(pipelineId)
  → return { runs: [...] } (jobs field dari DB, mungkin null)

[Frontend]
  → Render RunCardV2 untuk setiap run
  → Expand → parse run.jobs → tampilkan job list
  → Jika jobs null → "No job data available"
  → Klik job → navigasi ke /runs/:runId (panggil GetRun -> fetch fresh dari GitHub)
```

### 4. Data Flow Diagram
```
┌──────────┐   workflow_run webhook   ┌───────────┐   GET /actions/runs/{id}/jobs   ┌──────────┐
│  GitHub  │ ───────────────────────→ │   Backend │ ←────────────────────────────── │  GitHub  │
│ Actions  │                          │   (Go)    │ ──────────────────────────────→ │   API    │
└──────────┘                          └─────┬─────┘    decrypt token first          └──────────┘
                                            │
                                ┌───────────┴───────────┐
                                │        Database        │
                                │  pipeline_runs.jobs    │
                                │  (JSONB)               │
                                └───────────┬───────────┘
                                            │
                                    GET /runs/:runId
                                            │
┌──────────┐                          ┌─────┴─────┐
│  Client  │ ←────────────────────── │   Backend  │
│ (React)  │   polling 5s            │   (Go)     │
└──────────┘                          └───────────┘
```

### 1. Connect GitHub Repository
```
[User] → POST /repositories/connect { repoUrl, accessToken }
  → [Backend] validasi input
      → [GitHub API] GET /repos/{owner}/{repo} (verify repo exists)
          ← 200: { name, owner, default_branch, languages_url }
      → [Backend] simpan ke DB: { repo_id, owner, name, branch, hook_id }
      → [GitHub API] POST /repos/{owner}/{repo}/hooks (create webhook)
          ← 201: { id, config: { url, events: ["push","pull_request","workflow_run"] } }
      → [Backend] return 201: { repoId, name, webhookId }
  ← [User] menerima konfirmasi
```

### 2. Generate Pipeline → AI Agent → PR ke GitHub
```
[User] → POST /repositories/:repoId/pipelines/generate
         Body: { buildTool, testFramework, deployTarget, additionalConfig? }
  → [Backend] ambil insights repo dari DB
  → [Backend] kirim ke AI Agent:
      POST /api/ai/generate-pipeline
      Request: {
        repoContext: { language, frameworks, buildTool, deps },
        userInput: { testFramework, deployTarget, additionalConfig }
      }
      ← Response AI: {
          pipelineYaml: string,
          explanation: string,
          suggestions: string[],
          riskLevel: "low" | "medium" | "high"
        }
  → [Backend] validasi YAML syntax
  → [Backend] buat branch baru: pipeline/generate-{timestamp}
  → [GitHub API] PUT /repos/{owner}/{repo}/contents/{path}
      Body: { branch, message, content: base64(pipelineYaml), committer }
      ← 201: { commit: { sha, html_url } }
  → [GitHub API] POST /repos/{owner}/{repo}/pulls
      Body: { title, head, base, body }
      ← 201: { number, html_url, state }
  → [Backend] simpan pipeline version + run record ke DB
  ← [User] return 201: { version, prUrl, pipelineYaml, explanation }
```

### 3. Webhook — GitHub Event Masuk
```
[GitHub] → POST /api/v1/webhooks/github
           Event: push | pull_request | workflow_run
  → [Backend] verifikasi signature (HMAC-SHA256)
  → [Backend] cari repoId dari hook_id
  → [Backend] simpan event ke DB (raw payload)
  → [Backend] classification:
      ├─ workflow_run (completed) → trigger analisis AI
      │   → [GitHub API] GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs
      │       ← 200: { jobs: [{ status, conclusion, steps, logs }] }
      │   → [Backend] kirim ke AI Agent:
      │       POST /api/ai/analyze-run
      │       Request: {
      │         pipelineVersion,
      │         runId,
      │         jobs: [{ name, status, conclusion, duration, steps }],
      │         repoContext: { language, frameworks }
      │       }
      │       ← Response AI: {
      │           riskScore: 0-100,
      │           complianceScore: 0-100,
      │           securityCoverage: 0-100,
      │           workflowQuality: 0-100,
      │           severityBreakdown: { critical, high, medium, low },
      │           findings: [{ category, severity, message, suggestion }],
      │           recommendations: string[]
      │         }
      │   → [Backend] simpan analysis ke DB
      │   └─ [Backend] update run status: completed | failed
      │
      ├─ push → update branch reference di DB
      └─ pull_request (opened/synchronized) → trigger pipeline validation
          → [AI Agent] POST /api/ai/validate-pipeline
              Request: { prDiff, currentPipeline }
              ← Response: { valid, issues: [], suggestions: [] }
  ← [GitHub] return 200 OK
```

### 4. View Analysis (dari DB, tanpa re-trigger AI)
```
[User] → GET /runs/:runId/analysis
  → [Backend] query analysis dari DB by runId
  → [Backend] if analysis exists:
      ← 200: {
          riskScore, complianceScore, securityCoverage,
          workflowQuality, severityBreakdown,
          findings, recommendations, analyzedAt
        }
      → jika tidak ada → 404
  ← [User] render komponen RunAnalysis
```

### 5. Manual Re-Analysis
```
[User] → POST /runs/:runId/analysis/refresh
  → [Backend] cek run exists + sudah completed
  → [Backend] fetch ulang jobs dari GitHub API
  → [Backend] kirim ke AI Agent (sama seperti #3)
  → [Backend] update analysis di DB
  ← [User] return analysis terbaru
```

### 6. Compare Pipelines
```
[User] → POST /api/v1/pipelines/compare
         Body: { pipelineIdA, pipelineIdB }
  → [Backend] ambil kedua pipeline + analysis dari DB
  → [Backend] kirim ke AI Agent:
      POST /api/ai/compare-pipelines
      Request: {
        pipelineA: { yaml, analysis },
        pipelineB: { yaml, analysis }
      }
      ← Response AI: {
          scores: {
            a: { risk, compliance, security, quality },
            b: { risk, compliance, security, quality }
          },
          deltas: [{ metric, delta, impact, recommendation }],
          summary: string
        }
  → [Backend] cache hasil comparison
  ← [User] return comparison data
```

### 7. AI Agent Internal Routes
| Route | Method | Purpose | Input | Output |
|---|---|---|---|---|
| `/api/ai/generate-pipeline` | POST | Generate `.github/workflows/*.yml` | `{ repoContext, userInput }` | `{ pipelineYaml, explanation, suggestions, riskLevel }` |
| `/api/ai/analyze-run` | POST | Analyze pipeline run results | `{ pipelineVersion, runId, jobs, repoContext }` | `{ riskScore, complianceScore, securityCoverage, workflowQuality, severityBreakdown, findings, recommendations }` |
| `/api/ai/validate-pipeline` | POST | Validate PR pipeline changes | `{ prDiff, currentPipeline }` | `{ valid, issues[], suggestions[] }` |
| `/api/ai/compare-pipelines` | POST | Compare two pipeline versions | `{ pipelineA, pipelineB }` | `{ scores, deltas[], summary }` |

## AI Agent — Prompt Strategy

AI Agent adalah Python service yang bertindak sebagai middleware antara Backend dan LLM (OpenAI GPT / Claude). Setiap endpoint punya **system prompt** + **user prompt template** sendiri.

### Arsitektur Internal AI Agent

```
[Backend] → HTTP Request
  → [AI Agent Router] → match endpoint
      → [Prompt Builder] construct system + user prompt dari template + input
          → [LLM Caller] call LLM API (dengan JSON mode / function calling)
              ← [LLM] raw response
          → [Response Parser] parse & validate JSON
          → [Response Builder] strukturkan ke format yang dijanjikan
  ← [Backend] HTTP Response
```

### Prompt Templates per Endpoint

#### a. Generate Pipeline (`/api/ai/generate-pipeline`)
```
System Prompt:
  "Kamu adalah AI pipeline engineer yang ahli dalam GitHub Actions.
   Tugasmu generate file .github/workflows/*.yml berdasarkan konteks
   repository dan input user. Output harus JSON valid dengan field:
   pipelineYaml (string), explanation (string), suggestions (array),
   riskLevel (low|medium|high)."

User Prompt (template):
  "Repository context:
   - Language: {language}
   - Frameworks: {frameworks}
   - Build tool: {buildTool}
   - Dependencies: {deps}

   User request:
   - Build tool: {userInput.buildTool}
   - Test framework: {userInput.testFramework}
   - Deploy target: {userInput.deployTarget}
   {if additionalConfig} - Additional: {userInput.additionalConfig}{endif}

   Buat pipeline YAML yang optimal untuk repository ini.
   Sertakan: lint, test, build, security scan, dan deploy stages.
   Beri juga explanation dan suggestions untuk improvement."
```

#### b. Analyze Run (`/api/ai/analyze-run`)
```
System Prompt:
  "Kamu adalah AI DevOps analyst. Tugasmu menganalisis hasil eksekusi
   pipeline GitHub Actions dan memberikan skor serta rekomendasi.
   Output JSON: riskScore (0-100), complianceScore (0-100),
   securityCoverage (0-100), workflowQuality (0-100),
   severityBreakdown {critical,high,medium,low},
   findings [{category,severity,message,suggestion}],
   recommendations [string]."

User Prompt (template):
  "Pipeline version: {pipelineVersion}
   Run ID: {runId}
   Repository: {repoContext.language} | {repoContext.frameworks}

   Jobs executed:
   {for each job}
   - {job.name}: {job.status} ({job.conclusion})
     Duration: {job.duration}
     Steps: {job.steps}
   {endfor}

   Analisis hasil run ini. Beri skor untuk setiap kategori,
   temukan isu-isu (test failures, security gaps, bottleneck),
   dan berikan rekomendasi perbaikan."
```

#### c. Validate Pipeline (`/api/ai/validate-pipeline`)
```
System Prompt:
  "Kamu adalah AI code reviewer spesialis GitHub Actions.
   Tugasmu me-review perubahan pipeline YAML di PR dan
   memberikan validasi. Output JSON: valid (boolean),
   issues [{line,severity,message}], suggestions [string]."

User Prompt (template):
  "Current pipeline:
  {currentPipeline}

  PR diff (pipeline-related changes):
  {prDiff}

  Review perubahan pipeline ini. Apakah ada syntax error,
  security issue, best practice violation, atau potential
  breaking changes?"
```

#### d. Compare Pipelines (`/api/ai/compare-pipelines`)
```
System Prompt:
  "Kamu adalah AI DevOps consultant. Tugasmu membandingkan
   dua versi pipeline dan memberikan analisis dampak.
   Output JSON: scores {a: {risk,compliance,security,quality},
   b: {risk,compliance,security,quality}},
   deltas [{metric,delta,impact,recommendation}], summary (string)."

User Prompt (template):
  "Pipeline A (version {versionA}):
  {pipelineA.yaml}
  Analysis: {pipelineA.analysis}

  Pipeline B (version {versionB}):
  {pipelineB.yaml}
  Analysis: {pipelineB.analysis}

  Bandingkan kedua pipeline. Hitung delta setiap metric,
  jelaskan impact dari perubahan, dan rekomendasi pipeline
  mana yang lebih baik untuk digunakan."
```

### LLM Configuration per Endpoint
| Endpoint | Model | Temperature | Max Tokens | Response Format |
|---|---|---|---|---|
| `/api/ai/generate-pipeline` | `gpt-4` / `claude-3-opus` | 0.3 | 4096 | JSON (function calling) |
| `/api/ai/analyze-run` | `gpt-4` / `claude-3-sonnet` | 0.1 | 2048 | JSON (function calling) |
| `/api/ai/validate-pipeline` | `gpt-4` / `claude-3-sonnet` | 0.1 | 1024 | JSON (function calling) |
| `/api/ai/compare-pipelines` | `gpt-4` / `claude-3-opus` | 0.2 | 2048 | JSON (function calling) |

### Context Injection
- **Repo insights** (language, frameworks, deps) diambil dari DB Backend, dikirim sebagai bagian dari request ke AI Agent
- **GitHub API data** (job logs, commit diff) di-fetch oleh Backend, bukan oleh AI Agent — AI Agent hanya nerima data yang sudah terstruktur
- **Tidak ada akses langsung** dari AI Agent ke GitHub atau DB — semua komunikasi lewat Backend

## Arsitektur Komunikasi

```
┌─────────┐    HTTPS     ┌───────────┐   HTTP/gRPC   ┌───────────┐   REST API   ┌──────────┐
│  Client │ ←──────────→ │  Backend  │ ←───────────→ │ AI Agent  │ ←──────────→ │  GitHub  │
│ (React) │              │  (Go)     │               │  (Python)  │             │   API    │
└─────────┘              └───────────┘               └───────────┘             └──────────┘
                              │                                                    │
                              │                  Webhook (push/pull/workflow_run)  │
                              └────────────────────────────────────────────────────┘
```
