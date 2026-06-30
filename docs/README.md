# Documentation Index

This directory contains documentation for the DevSecOps platform features.

---

## Quick Links

| Feature | Document | Description |
|---------|----------|-------------|
| **Pipeline Runs** | [RUNDETAIL-FLOW.md](./RUNDETAIL-FLOW.md) | RunDetail page - job execution & analysis |
| **Security Analysis** | [RUNANALYSIS-FLOW.md](./RUNANALYSIS-FLOW.md) | RunAnalysis page - security scores & findings |
| **Pipeline Sync** | [PIPELINE-SYNC-FLOW.md](./PIPELINE-SYNC-FLOW.md) | Sync mechanism - GitHub to DB |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │ PipelineGenerator │    │PipelineVersion  │    │    RunDetail     │   │
│  │  (Generate YAML)  │    │     Detail       │    │  (Job Execution) │   │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘   │
│           │                      │                      │              │
│           └──────────────────────┼──────────────────────┘              │
│                                  │                                     │
│                         ┌────────┴────────┐                          │
│                         │   RunAnalysis    │                          │
│                         │(Security Scores)│                          │
│                         └────────┬────────┘                          │
└──────────────────────────────────┼────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (Go)                                │
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│  │   Pipeline   │    │    Run      │    │   Webhook   │               │
│  │   Handler    │    │   Handler   │    │   Handler   │               │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│         │                  │                  │                        │
│         └──────────────────┼──────────────────┘                        │
│                            │                                           │
│                   ┌────────┴────────┐                                  │
│                   │   PostgreSQL    │                                  │
│                   └─────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           AI SERVICE (Python)                          │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                    LangGraph Pipeline                        │       │
│  │                                                          │       │
│  │  repository_scan → technology_detection                 │       │
│  │           → architecture_detection → security_inference │       │
│  │           → workflow_generation → workflow_validation  │       │
│  │                                                          │       │
│  │  security_analyzer → risk_assessor → compliance_mapper  │       │
│  │           → recommendation_gen → response_formatter     │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Flow Diagrams

### 1. Pipeline Generation Flow
```
User clicks "Generate Pipeline"
       ↓
Frontend → POST /api/pipeline/generate
       ↓
Backend → AI Service
       ↓
AI Service LangGraph:
  1. repository_connection (connect to GitHub)
  2. repository_scan (scan repo structure)
  3. vulnerability_scan (scan dependencies)
  4. technology_detection (detect languages/frameworks)
  5. architecture_detection (detect monolith — only per R2.1)
  6. deployment_detection (detect Docker/K8s/Terraform)
  7. security_requirement_inference (determine security controls)
  8. workflow_generation (generate GitHub Actions YAML)
  9. workflow_validation (validate YAML, fix issues)
       ↓
Return generated workflow + analysis
       ↓
User reviews → Deploys via PR
```

### 2. Pipeline Execution Flow
```
GitHub Actions runs workflow
       ↓
GitHub sends webhook (workflow_run event)
       ↓
Backend receives webhook → Updates PipelineRun status
       ↓
Frontend polls for status (every 5s)
       ↓
Fetch jobs from GitHub API
       ↓
Store jobs in DB (pipeline_runs.jobs)
       ↓
If completed → Trigger AI Analysis
       ↓
User views RunDetail → Sees job results
```

### 3. Security Analysis Flow
```
Pipeline run completes
       ↓
Backend triggers AI analysis:
  POST /api/pipeline/analyze/{run_id}
       ↓
AI Service LangGraph:
  1. security_analyzer (parse scan results)
  2. risk_assessor (calculate risk score)
  3. compliance_mapper (map to OWASP/CIS)
  4. recommendation_gen (generate recommendations)
  5. response_formatter (format output)
       ↓
Store analysis in DB (pipeline_analyses)
       ↓
User views RunAnalysis → Sees scores & findings
```

---

## Database Tables

### Core Tables
| Table | Description |
|-------|-------------|
| `users` | User accounts |
| `projects` | User projects |
| `repositories` | Connected GitHub repos |
| `pipelines` | Generated pipeline versions |
| `pipeline_runs` | Workflow execution runs |
| `pipeline_analyses` | Security analysis results |

### Relationship
```
users (1) ──→ (many) projects
projects (1) ──→ (many) repositories
repositories (1) ──→ (many) pipelines
pipelines (1) ──→ (many) pipeline_runs
pipeline_runs (1) ──→ (0..1) pipeline_analyses
```

---

## API Endpoints

### Backend (Go) - `/api/v1`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/runs/:runId` | Get run detail + jobs |
| GET | `/runs/:runId/analysis` | Get security analysis |
| POST | `/repositories/:repoId/pipelines/:version/sync-runs` | Sync runs from GitHub |
| POST | `/webhooks/github` | GitHub webhook receiver |

### AI Service (Python) - `/api/pipeline`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate` | Generate pipeline workflow |
| POST | `/deploy` | Deploy workflow to GitHub |
| POST | `/repo/analyze` | Analyze repository |
| POST | `/analyze/{run_id}` | Analyze pipeline run |
| POST | `/analyze-execution/{run_id}` | Analyze execution failure |

---

## Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React + TypeScript | UI |
| State | TanStack Query | Data fetching |
| Styling | Tailwind CSS | Styling |
| Backend | Go + Gin | API server |
| Database | PostgreSQL | Data storage |
| AI | Python + LangGraph | Pipeline generation |
| LLM | OpenAI/GPT-4 | Text generation |
| GitHub API | REST | Repository access |

---

## File Structure

```
coba-4/
├── backend/                    # Go API server
│   ├── handlers/
│   │   ├── pipeline.go        # Pipeline endpoints
│   │   └── webhook.go        # GitHub webhook handler
│   ├── models/
│   │   └── pipeline_run.go   # Database models
│   └── main.go
│
├── frontend/                   # React application
│   ├── src/
│   │   ├── pages/
│   │   │   ├── PipelineGenerator.tsx
│   │   │   ├── PipelineVersionDetail.tsx
│   │   │   ├── RunDetail.tsx
│   │   │   └── RunAnalysis.tsx
│   │   ├── hooks/
│   │   │   ├── usePipelinesV2.ts
│   │   │   └── usePipeline.ts
│   │   └── components/
│   │       └── ...
│   └── package.json
│
├── ai-service/               # Python AI service
│   ├── app/
│   │   ├── agents/
│   │   │   ├── nodes/       # LangGraph nodes
│   │   │   ├── pipeline_graph.py
│   │   │   └── pipeline_state.py
│   │   ├── api/
│   │   │   └── pipeline.py  # API endpoints
│   │   └── services/
│   │       ├── llm_service.py
│   │       └── github_service.py
│   └── requirements.txt
│
└── docs/                      # This documentation
    ├── RUNDETAIL-FLOW.md
    ├── RUNANALYSIS-FLOW.md
    └── PIPELINE-SYNC-FLOW.md
```

---

## Common Tasks

### Add new security scanner
1. Update `security_analyzer_node.py`
2. Add parsing logic for scanner output
3. Update findings schema
4. Add to frontend display

### Add new security control
1. Update `security_requirement_inference_node.py`
2. Add control definition
3. Update workflow generator prompt
4. Add to frontend control selector

### Add new compliance framework
1. Update `compliance_mapper_node.py`
2. Add mapping rules
3. Update compliance schema
4. Add to frontend compliance display

---

## Environment Variables

### Backend
```
DATABASE_URL=postgres://...
GITHUB_WEBHOOK_SECRET=xxx
JWT_SECRET=xxx
```

### AI Service
```
OPENAI_API_KEY=sk-xxx
DATABASE_URL=postgres://...
```

### Frontend
```
VITE_API_URL=http://localhost:8080
VITE_AI_SERVICE_URL=http://localhost:8000
```

---

## Deployment

### Backend (Go)
```bash
go build -o server ./backend
./server
```

### AI Service (Python)
```bash
cd ai-service
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend (React)
```bash
cd frontend
npm install
npm run build
# Serve dist/ with nginx/caddy
```

---

## Monitoring

### Health Check
```
GET /api/v1/health
```

### Metrics
- Request latency
- Error rate
- GitHub API rate limits
- Database connection pool

### Logs
- Request/response logs
- Webhook delivery logs
- AI generation logs
- Error logs

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Pipeline not generating | Check AI service is running |
| Jobs not showing | Verify GitHub token has `repo` scope |
| Analysis showing 0.0 | Check pipeline_analyses table |
| Webhook not working | Verify webhook URL is accessible |
| LLM errors | Check OpenAI API key and quota |

---

## Support

For issues or questions, check:
1. [RUNDETAIL-FLOW.md](./RUNDETAIL-FLOW.md)
2. [RUNANALYSIS-FLOW.md](./RUNANALYSIS-FLOW.md)
3. [PIPELINE-SYNC-FLOW.md](./PIPELINE-SYNC-FLOW.md)
4. GitHub Issues