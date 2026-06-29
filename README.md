# AI DevSecOps Security Assistant

![Build](https://img.shields.io/badge/build-passing-brightgreen) ![Go](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go) ![Node](https://img.shields.io/badge/Node-20+-339933?logo=nodedotjs) ![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python) ![License](https://img.shields.io/badge/license-MIT-blue) ![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)

An AI-powered DevSecOps assistant that automates security scanning, vulnerability analysis, CI/CD workflow auditing, and incident response. It integrates with GitHub repositories to provide intelligent PR reviews, SAST/DAST/SCA scan orchestration, and AI-driven remediation recommendations.

## Architecture

```mermaid
graph TB
    subgraph "Client"
        Browser[Browser]
    end

    subgraph "Proxy Layer"
        Nginx[Nginx<br/>Port 80]
    end

    subgraph "Frontend"
        React[React + Vite<br/>Port 5173]
    end

    subgraph "Backend Services"
        GoAPI[Go/Gin API<br/>Port 8080]
    end

    subgraph "AI Layer"
        FastAPI[FastAPI + LangGraph<br/>Port 8000]
        Agent[AI Agent<br/>Intent Classifier<br/>Security Analyzer<br/>Risk Assessor<br/>Recommendation Gen]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL 16)]
        Redis[(Redis 7)]
    end

    subgraph "External"
        GitHub[GitHub API]
        LLM[OpenAI / Anthropic]
    end

    Browser --> Nginx
    Nginx -->|/api/*| GoAPI
    Nginx -->|/ai/*| FastAPI
    Nginx -->|/*| React

    GoAPI --> PG
    GoAPI --> Redis
    GoAPI --> FastAPI
    GoAPI --> GitHub

    FastAPI --> Agent
    FastAPI --> PG
    FastAPI --> Redis
    Agent --> LLM
```

## Tech Stack

### Backend (Go)
| Technology | Purpose |
|---|---|
| Go 1.22+ | Runtime |
| Gin | HTTP framework |
| GORM | ORM / PostgreSQL |
| go-redis | Redis client |
| golang-jwt | JWT auth |
| Viper | Config management |
| Zap | Structured logging |

### AI Service (Python)
| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | HTTP framework |
| LangChain + LangGraph | AI agent orchestration |
| LangSmith | LLM observability |
| SQLAlchemy | ORM / PostgreSQL |
| Uvicorn | ASGI server |

### Frontend (React)
| Technology | Purpose |
|---|---|
| Node 20+ | Runtime |
| React 19 | UI library |
| Vite | Bundler / dev server |
| TanStack Query | Server state |
| React Router | Routing |
| Recharts | Charts |
| Tailwind CSS | Styling |
| shadcn/ui + Radix | Component primitives |
| Axios | HTTP client |

### Infrastructure
| Technology | Purpose |
|---|---|
| Docker + Compose | Container orchestration |
| PostgreSQL 16 | Primary database |
| Redis 7 | Caching / sessions |
| Nginx | Reverse proxy |
| GitHub Actions | CI/CD |

## Features

- **🔐 Authentication & RBAC** — JWT-based auth with refresh tokens and role-based access control
- **📦 Project & Repository Management** — Organize scans by project; connect GitHub repos
- **🔍 SAST / DAST / SCA Scans** — Upload and manage security scan results from any tool
- **🤖 AI-Powered Analysis** — LangGraph agent classifies intent, analyzes vulnerabilities, assesses risk, and generates remediation
- **📝 AI PR Review** — Automated pull request security review via GitHub integration
- **🔁 CI/CD Workflow Auditing** — Analyze GitHub Actions workflows for security misconfigurations
- **🚨 Incident Management** — Track, investigate, and generate incident reports
- **📊 Dashboard** — Unified security metrics and stats visualization

> ![Screenshot Placeholder](/.github/screenshots/dashboard.png?raw=true)
> ![Screenshot Placeholder](/.github/screenshots/scan-detail.png?raw=true)
> ![Screenshot Placeholder](/.github/screenshots/ai-analysis.png?raw=true)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/)
- Go 1.22+ (local development)
- Node.js 18+ (local development)
- Python 3.11+ (local development)
- An OpenAI or Anthropic API key (for AI features)

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ai-devsecops-assistant.git
cd ai-devsecops-assistant

# 2. Copy environment variables
cp .env.example .env
# Edit .env and set OPENAI_API_KEY (or ANTHROPIC_API_KEY)

# 3. Start all services
docker compose up -d

# 4. Open the app
open http://localhost:8082
```

The frontend loads at `http://localhost:8082`, the backend API at `http://localhost:8082/api/v1`, and the AI service at `http://localhost:8082/ai`.

## Project Structure

```
ai-devsecops-assistant/
├── .env.example                  # Root environment template
├── docker-compose.yml            # Multi-service orchestration
├── nginx.conf                    # Reverse proxy config
├── backend/                      # Go API service
│   ├── cmd/server/main.go        # Entry point
│   ├── internal/
│   │   ├── config/               # Viper-based configuration
│   │   ├── database/             # PostgreSQL + Redis connections
│   │   ├── handlers/             # HTTP handlers (auth, project, scan, AI, etc.)
│   │   ├── middleware/           # CORS, logging, JWT auth
│   │   ├── models/              # GORM models (User, Scan, Vulnerability, etc.)
│   │   ├── repositories/        # Data access layer
│   │   ├── services/            # Business logic layer
│   │   └── utils/               # Crypto helpers
│   ├── Dockerfile
│   ├── go.mod / go.sum
│   └── .env.example
├── ai-service/                   # Python AI agent service
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings
│   │   ├── api/                 # Route definitions
│   │   ├── agents/              # LangGraph agent (graph, nodes, schemas)
│   │   │   ├── graph.py         # Agent state graph
│   │   │   └── nodes/           # Intent classifier, security analyzer, etc.
│   │   ├── services/            # LLM service, agent service
│   │   ├── schemas/             # Pydantic models
│   │   └── database.py          # SQLAlchemy connection
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                     # React SPA
│   ├── src/
│   │   ├── main.tsx             # Entry point
│   │   ├── App.tsx              # Router setup
│   │   ├── pages/               # Dashboard, Scans, PR Review, Incidents, etc.
│   │   └── components/          # Reusable UI components
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── .github/
│   └── workflows/
│       ├── deploy.yml           # Deploy pipeline (main branch)
│       └── pr-pipeline.yml      # PR security pipeline
└── README.md
```

## API Overview

All API routes are prefixed with `/api/v1`. Protected routes require a `Bearer <token>` Authorization header.

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Health check | No |
| `GET` | `/api/v1/health` | Health check | No |
| `POST` | `/api/v1/auth/register` | Register user | No |
| `POST` | `/api/v1/auth/login` | Login | No |
| `POST` | `/api/v1/auth/refresh` | Refresh token | No |
| `GET` | `/api/v1/me` | Current user | Yes |
| `GET` | `/api/v1/dashboard/stats` | Dashboard stats | Yes |
| `GET` | `/api/v1/projects` | List projects | Yes |
| `POST` | `/api/v1/projects` | Create project | Yes |
| `DELETE` | `/api/v1/projects/:id` | Delete project | Yes |
| `POST` | `/api/v1/repositories/connect` | Connect GitHub repo | Yes |
| `GET` | `/api/v1/projects/:projectId/repositories` | List repos in project | Yes |
| `DELETE` | `/api/v1/repositories/:id` | Delete repository | Yes |
| `POST` | `/api/v1/scans/:type` | Upload scan (sast/dast/sca) | Yes |
| `GET` | `/api/v1/scans/:id` | Get scan detail | Yes |
| `GET` | `/api/v1/repositories/:repoId/scans` | List scans for repo | Yes |
| `GET` | `/api/v1/repositories/:repoId/pr/:number` | Get PR info from GitHub | Yes |
| `POST` | `/api/v1/repositories/:repoId/audit-workflow` | Audit GitHub Actions workflow | Yes |
| `POST` | `/api/v1/ai/analyze` | AI vulnerability analysis | Yes |
| `POST` | `/api/v1/ai/review-pr` | AI PR review | Yes |
| `POST` | `/api/v1/ai/audit-workflow` | AI workflow audit | Yes |
| `GET` | `/api/v1/ai/reports/:id` | Get AI report | Yes |
| `POST` | `/api/v1/projects/:projectId/incidents` | Create incident | Yes |
| `GET` | `/api/v1/projects/:projectId/incidents` | List incidents | Yes |
| `GET` | `/api/v1/incidents/:id` | Get incident detail | Yes |
| `POST` | `/api/v1/incidents/:id/generate` | Generate incident report | Yes |

## AI Agent Workflow

```mermaid
graph LR
    User[User Request] --> IC[Intent Classifier]
    IC -->|analyze| SA[Security Analyzer]
    IC -->|review-pr| PR[PR Review Tool]
    IC -->|audit-workflow| WA[Workflow Auditor]
    IC -->|scan| ST[Scan Tool]

    SA --> RA[Risk Assessor]
    RA --> RG[Recommendation Gen]
    RG --> RT[Report Tool]
    RT --> RF[Response Formatter]

    PR --> RF
    WA --> RF
    ST --> RF

    RF --> Response[Final Response]

    subgraph "Tool Layer"
        SA
        PR
        WA
        ST
    end

    subgraph "Analysis Layer"
        RA
        RG
    end

    subgraph "Output Layer"
        RT
        RF
    end
```

The agent uses **LangGraph** to build a stateful, multi-node reasoning graph:

1. **Intent Classifier** — Routes the request to the correct tool (analyze, review-pr, audit-workflow, scan)
2. **Security Analyzer** — Deep vulnerability analysis using LLM context
3. **Risk Assessor** — CVSS-like scoring and severity classification
4. **Recommendation Generator** — Produces actionable remediation steps
5. **Report Tool** — Persists results to the database
6. **Response Formatter** — Structures the final output

## CI/CD Pipeline

### Pull Request Pipeline (`.github/workflows/pr-pipeline.yml`)
Runs on every PR:

| Job | Tools |
|---|---|
| **Lint** | `go vet`, ESLint, Ruff |
| **Test** | `go test`, `npm test` with coverage |
| **Semgrep** | SAST rule scanning (`p/default`) |
| **Gitleaks** | Secret leak detection |
| **Trivy** | Filesystem vulnerability scan (CRITICAL/HIGH) |

### Deploy Pipeline (`.github/workflows/deploy.yml`)
Runs on push to `main`:
- Builds all Docker images via `docker compose build`
- SSH-deploys to target server with `git pull && docker compose up -d --build`

## Deployment

### Railway

```bash
# Backend
railway service create backend
railway up --service backend --dockerfile backend/Dockerfile --target prod

# AI Service
railway service create ai-service
railway up --service ai-service --dockerfile ai-service/Dockerfile

# Frontend
railway service create frontend
railway up --service frontend --dockerfile frontend/Dockerfile

# Add Postgres and Redis plugins via Railway dashboard
```

### Fly.io

```bash
# Backend
fly launch --name ai-devsecops-backend --dockerfile backend/Dockerfile --target prod
fly postgres create --name ai-devsecops-db
fly redis create --name ai-devsecops-redis

# AI Service
fly launch --name ai-devsecops-ai --dockerfile ai-service/Dockerfile

# Frontend
fly launch --name ai-devsecops-frontend --dockerfile frontend/Dockerfile

# Set secrets
fly secrets set OPENAI_API_KEY=sk-... JWT_SECRET=...
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SERVER_PORT` | Backend API port | `8080` |
| `SERVER_HOST` | Backend host | `0.0.0.0` |
| `DATABASE_HOST` | PostgreSQL host | `postgres` |
| `DATABASE_PORT` | PostgreSQL port | `5432` |
| `DATABASE_USER` | PostgreSQL user | `postgres` |
| `DATABASE_PASSWORD` | PostgreSQL password | `postgres` |
| `DATABASE_NAME` | PostgreSQL database name | `ai_devsecops` |
| `DATABASE_SSLMODE` | PostgreSQL SSL mode | `disable` |
| `DATABASE_URL` | PostgreSQL connection string (AI service) | `postgresql://postgres:postgres@postgres:5432/ai_devsecops` |
| `REDIS_HOST` | Redis host | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `JWT_SECRET` | JWT signing secret | `change-me-in-production` |
| `JWT_ACCESS_DURATION` | Access token TTL | `15m` |
| `JWT_REFRESH_DURATION` | Refresh token TTL | `168h` |
| `ENCRYPTION_KEY` | Encryption key for sensitive data | — |
| `AI_SERVICE_URL` | Internal AI service URL | `http://ai-service:8000` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `OPENROUTER_API_KEY` | OpenRouter API key | — |
| `OPENROUTER_BASE_URL` | OpenRouter base URL | `https://openrouter.ai/api/v1` |
| `LLM_PROVIDER` | LLM provider (`openai` / `anthropic` / `openrouter`) | `openrouter` |
| `LLM_MODEL` | LLM model name | `deepseek/deepseek-v4-flash` |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `false` |
| `LANGCHAIN_API_KEY` | LangSmith API key | — |
| `LANGCHAIN_PROJECT` | LangSmith project name | `ai-devsecops-assistant` |
| `BACKEND_API_URL` | Backend URL (from AI service) | `http://backend:8080/api/v1` |
| `VITE_API_URL` | API URL (from frontend) | `/api/v1` |

## API Testing

### Testing the GitHub Repository Connection

This endpoint validates your GitHub token and repository access before storing them.

**Prerequisites:** [jq](https://jqlang.org/) installed for JSON parsing.

```bash
# 1. Register a user
curl -s -X POST http://localhost:8082/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!","name":"Test User"}'

# 2. Login to get JWT token
TOKEN=$(curl -s -X POST http://localhost:8082/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# 3. Create a project
PROJECT_ID=$(curl -s -X POST http://localhost:8082/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"My Project","description":"Testing repo connection"}' | jq -r '.project.id')

echo "Project ID: $PROJECT_ID"

# 4. Test with INVALID token (expect HTTP 401)
echo "=== Test 1: Invalid token ==="
curl -s -X POST http://localhost:8082/api/v1/repositories/connect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"github_token\":\"ghp_invalid\",\"full_name\":\"owner/repo\"}"

# 5. Test with token lacking repo scope (expect HTTP 401 with permission error)
echo "=== Test 2: Token without repo scope ==="
curl -s -X POST http://localhost:8082/api/v1/repositories/connect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"github_token\":\"ghp_no_repo_scope\",\"full_name\":\"owner/private-repo\"}"

# 6. Test with VALID token (expect HTTP 201)
echo "=== Test 3: Valid token ==="
curl -s -X POST http://localhost:8082/api/v1/repositories/connect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"github_token\":\"ghp_your_real_token\",\"full_name\":\"your-username/your-repo\"}"
```

**Expected responses:**

| Scenario | HTTP Status | Response |
|---|---|---|
| Invalid/expired token | `401` | `{"error":"invalid GitHub token: GitHub token is invalid or expired: ..."}` |
| Token lacks repo permissions | `401` | `{"error":"invalid GitHub token: token lacks permission to access owner/repo. Required scope: repo"}` |
| Repo not found or inaccessible | `401` | `{"error":"invalid GitHub token: repository owner/repo not found or token lacks access"}` |
| Success | `201` | `{"repository":{"id":"...","full_name":"owner/repo",...}}` |

### Required GitHub Token Scopes

Create a [GitHub Personal Access Token](https://github.com/settings/tokens) with these scopes:

| Scope | Required For |
|---|---|
| `repo` (Full control of private repos) | Accessing private repositories |
| `public_repo` | Public repositories only |
| `read:org` | Reading organization membership (optional) |

> Tokens with only `public_repo` scope will fail to connect private repositories. If you get a 401 "lacks permission" error, create a new token with the `repo` scope.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Run linting and tests:
   ```bash
   cd backend && go vet ./... && go test ./...
   cd frontend && npm run lint
   cd ai-service && ruff check . && pytest
   ```
5. Commit using conventional commits (`feat:`, `fix:`, `chore:`, etc.)
6. Push and open a Pull Request

All PRs automatically run the security pipeline (Semgrep, Gitleaks, Trivy). Secrets must never be committed.

## License

MIT — see [LICENSE](LICENSE) for details.