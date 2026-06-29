# 4. High-Level System Flow

## 4.1 System Architecture Overview

The DevSecOps Agent platform follows a **layered microservices architecture** with five primary tiers:

```
┌────────────────────────────────────────────────────────────────────┐
│                        CLIENT TIER                                 │
│  React SPA (TypeScript) — Browser                                  │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────────┐    │
│  │ Auth     │ │ Dashboard │ │ Workflow │ │ Security Reports  │    │
│  │ Module   │ │ Module    │ │ Editor   │ │ Module            │    │
│  └──────────┘ └───────────┘ └──────────┘ └───────────────────┘    │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ HTTPS + WSS (TLS 1.3)
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY TIER                            │
│  Nginx / Traefik — Reverse Proxy, Rate Limiting, SSL Termination   │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐     │
│  │ /api/v1/*  │  │ /ws/*        │  │ /.well-known/* (health)│     │
│  │ → FastAPI  │  │ → WebSocket  │  │ → Monitoring           │     │
│  └────────────┘  └──────────────┘  └────────────────────────┘     │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                       APPLICATION TIER                             │
│  FastAPI (Python 3.12+) — Async REST API Server                    │
│  ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌──────────────┐    │
│  │ Auth Router│ │Repo Router │ │Workflow   │ │Dashboard     │    │
│  │ /auth/*    │ │/repos/*    │ │Router     │ │Router        │    │
│  │            │ │            │ │/workflows │ │/dashboard/*  │    │
│  └────────────┘ └────────────┘ └───────────┘ └──────────────┘    │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                       SERVICE LAYER                         │    │
│  │ AuthService │ RepoService │ WorkflowService │ ReportService │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                      INTEGRATION LAYER                      │    │
│  │ GitHubClient │ OpenRouterClient │ QueueClient │ CacheClient │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────┬──────────────────────┬──────────────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│    AI LAYER          │  │         DATA TIER                     │
│  LangGraph Engine    │  │  PostgreSQL 17 — Primary Database     │
│  ┌────────────────┐  │  │  ┌──────────┐ ┌──────────────────┐   │
│  │ Agent          │  │  │  │ Users    │ │ Analysis Results │   │
│  │ Orchestrator   │  │  │  ├──────────┤ ├──────────────────┤   │
│  ├────────────────┤  │  │  │ Repos    │ │ Workflows        │   │
│  │ Repo Analyzer  │  │  │  ├──────────┤ ├──────────────────┤   │
│  │ Agent           │  │  │  │ PRs      │ │ Findings         │   │
│  ├────────────────┤  │  │  ├──────────┤ ├──────────────────┤   │
│  │ Tech Detector  │  │  │  │ Jobs     │ │ Recommendations  │   │
│  │ Agent           │  │  │  ├──────────┤ ├──────────────────┤   │
│  ├────────────────┤  │  │  │ Creds    │ │ Audit Logs       │   │
│  │ Security Req   │  │  │  └──────────┘ └──────────────────┘   │
│  │ Agent           │  │  │                                      │
│  ├────────────────┤  │  └──────────────────────────────────────┘
│  │ Workflow Gen   │  │
│  │ Agent           │  │  ┌──────────────────────────────────────┐
│  ├────────────────┤  │  │         CACHE TIER                    │
│  │ Validator      │  │  │  Redis 7 — Job Queue + Session Cache  │
│  │ Agent           │  │  │  ┌──────────┐ ┌──────────────────┐   │
│  ├────────────────┤  │  │  │ Sessions │ │ Job Queue       │   │
│  │ Repair Agent   │  │  │  ├──────────┤ ├──────────────────┤   │
│  ├────────────────┤  │  │  │ Rate Lmt │ │ Analysis Cache  │   │
│  │ Risk Assessor  │  │  │  ├──────────┤ ├──────────────────┤   │
│  │ Agent           │  │  │  │ GitHub   │ │ Dashboard Cache │   │
│  ├────────────────┤  │  │  │ Cache    │ │                  │   │
│  │ Recommendation │  │  │  └──────────┘ └──────────────────┘   │
│  │ Agent           │  │  └──────────────────────────────────────┘
│  └────────────────┘  │
│  ┌────────────────┐  │
│  │ OpenRouter API │  │
│  │ (LLM Provider) │  │
│  └────────────────┘  │
└──────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ GitHub API   │  │ OpenRouter   │  │ Security Tool Execution  │ │
│  │ (REST/GraphQL)│  │ (LLM Proxy)  │  │ (GitHub Actions Env)    │ │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4.2 Frontend Tier — Detailed Component Architecture

### 4.2.1 React SPA Structure

The frontend is a single-page application built with React 18+ and TypeScript 5+, following the **feature-sliced design** (FSD) architecture pattern:

```
src/
├── app/                    # Application initialization layer
│   ├── App.tsx             # Root component with routing
│   ├── providers/          # Context providers (Auth, Theme, WebSocket)
│   └── router/             # React Router v6 configuration
│
├── pages/                  # Route-level page components
│   ├── landing/            # Unauthenticated landing page
│   ├── auth-callback/      # OAuth callback handler
│   ├── dashboard/          # Main dashboard after login
│   ├── repositories/       # Repository list and selection
│   ├── analysis/           # Repository analysis results
│   ├── workflow-builder/   # Workflow generation configuration
│   ├── workflow-editor/    # Generated workflow diff viewer
│   ├── pr-review/          # Pull Request creation page
│   └── security/           # Security dashboard + reports
│
├── features/               # Business logic modules
│   ├── auth/               # Login, logout, token refresh
│   ├── repositories/       # Repository listing, search, connect
│   ├── analysis/           # Analysis job triggering, progress
│   ├── workflow/           # Workflow generation, validation, repair UI
│   ├── pull-request/       # PR creation, status monitoring
│   └── security/           # Findings display, dashboards, exports
│
├── entities/               # Domain entities (TypeScript interfaces)
│   ├── user.ts
│   ├── repository.ts
│   ├── analysis.ts
│   ├── workflow.ts
│   ├── pull-request.ts
│   └── finding.ts
│
├── shared/                 # Reusable components and utilities
│   ├── ui/                 # Design system components (Button, Card, Modal, etc.)
│   ├── api/                # Axios/Fetch client with interceptors
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utility functions
│   └── config/             # Environment configuration
│
└── widgets/                # Composite UI blocks
    ├── navbar/
    ├── sidebar/
    ├── progress-tracker/
    └── yaml-editor/
```

### 4.2.2 Frontend State Management

- **Zustand** for global application state (auth state, selected repository, active job)
- **TanStack Query (React Query v5)** for server-state synchronization and caching
- **WebSocket context** for real-time analysis progress and workflow execution updates
- **Monaco Editor** for YAML diff viewing with syntax highlighting and inline annotations
- **Recharts / Nivo** for dashboard charting (time-series risk scores, severity breakdowns)

### 4.2.3 Frontend API Communication

```
Frontend (React) → FastAPI REST API (/api/v1/*)
                   │
                   ├── GET    /api/v1/auth/me                    → Current user info
                   ├── POST   /api/v1/auth/logout                → Clear session
                   ├── GET    /api/v1/repositories               → List connected repos
                   ├── POST   /api/v1/repositories               → Connect new repo
                   ├── DELETE /api/v1/repositories/{id}          → Disconnect repo
                   ├── POST   /api/v1/analysis/{repo_id}/start   → Start analysis
                   ├── GET    /api/v1/analysis/{job_id}/status   → Poll analysis status
                   ├── GET    /api/v1/analysis/{job_id}/results  → Get analysis results
                   ├── POST   /api/v1/workflows/generate         → Generate workflow
                   ├── POST   /api/v1/workflows/validate         → Validate workflow
                   ├── POST   /api/v1/workflows/repair           → Repair workflow
                   ├── POST   /api/v1/pull-requests              → Create PR
                   ├── GET    /api/v1/pull-requests/{id}/status  → PR status
                   ├── GET    /api/v1/dashboard/summary          → Dashboard KPIs
                   ├── GET    /api/v1/findings                   → Findings list
                   ├── GET    /api/v1/recommendations            → Recommendations
                   └── GET    /api/v1/reports/export             → Export report
                   
                   WebSocket /ws/analysis/{job_id}   → Real-time analysis progress
                   WebSocket /ws/workflow/{run_id}   → Workflow execution status
```

---

## 4.3 Backend Tier — Detailed Component Architecture

### 4.3.1 FastAPI Application Structure

```
backend/
├── main.py                      # FastAPI app factory, middleware registration
├── config.py                    # Pydantic Settings (env vars)
├── dependencies.py              # Dependency injection (DB session, current user)
│
├── routers/                     # API route handlers
│   ├── auth.py                  # /api/v1/auth/*
│   ├── repositories.py          # /api/v1/repositories/*
│   ├── analysis.py              # /api/v1/analysis/*
│   ├── workflows.py             # /api/v1/workflows/*
│   ├── pull_requests.py         # /api/v1/pull-requests/*
│   ├── dashboard.py             # /api/v1/dashboard/*
│   ├── findings.py              # /api/v1/findings/*
│   ├── recommendations.py       # /api/v1/recommendations/*
│   └── reports.py               # /api/v1/reports/*
│
├── services/                    # Business logic layer
│   ├── auth_service.py          # OAuth flow, JWT management
│   ├── repo_service.py          # Repository CRUD, GitHub API proxy
│   ├── analysis_service.py      # Analysis job orchestration
│   ├── workflow_service.py      # Workflow generation, validation, repair
│   ├── pr_service.py            # Branch + PR creation
│   ├── monitoring_service.py    # Workflow execution polling
│   ├── security_service.py      # Risk scoring, finding aggregation
│   └── report_service.py        # Report generation and export
│
├── models/                      # SQLAlchemy ORM models
│   ├── user.py
│   ├── repository.py
│   ├── analysis.py
│   ├── workflow.py
│   ├── pull_request.py
│   ├── finding.py
│   ├── recommendation.py
│   └── audit_log.py
│
├── schemas/                     # Pydantic request/response schemas
│   ├── auth.py
│   ├── repository.py
│   ├── analysis.py
│   ├── workflow.py
│   ├── pull_request.py
│   ├── dashboard.py
│   ├── finding.py
│   └── recommendation.py
│
├── integrations/                # External service clients
│   ├── github_client.py         # GitHub REST/GraphQL API client
│   ├── openrouter_client.py     # OpenRouter LLM API client
│   └── security_tools.py        # Parsers for Semgrep, Gitleaks, Trivy, etc.
│
├── workers/                     # Background task workers
│   ├── analysis_worker.py       # LangGraph orchestrator worker
│   ├── monitoring_worker.py     # Workflow status polling worker
│   └── report_worker.py         # Report generation worker
│
├── middleware/                   # FastAPI middleware
│   ├── auth_middleware.py       # JWT verification, user injection
│   ├── rate_limit.py            # Per-user rate limiting
│   ├── cors.py                  # CORS configuration
│   └── logging_middleware.py    # Request/response logging
│
├── ai/                          # LangGraph agent definitions
│   ├── orchestrator.py          # Main LangGraph state machine
│   ├── agents/                  # Individual agent implementations
│   │   ├── repo_analyzer.py
│   │   ├── tech_detector.py
│   │   ├── security_requirement.py
│   │   ├── workflow_generator.py
│   │   ├── workflow_validator.py
│   │   ├── workflow_repair.py
│   │   ├── risk_assessor.py
│   │   └── recommendation.py
│   ├── prompts/                 # LLM prompt templates
│   │   ├── system_prompts.py
│   │   └── few_shot_examples.py
│   └── state.py                 # LangGraph State definition (TypedDict)
│
└── migrations/                  # Alembic database migrations
    └── versions/
```

### 4.3.2 Request Lifecycle

```
1. Client Request → Nginx (TLS termination, rate limit check)
2. Nginx → FastAPI (Uvicorn ASGI server)
3. Middleware Chain:
   a. CORSMiddleware → Check origin
   b. LoggingMiddleware → Log request
   c. RateLimitMiddleware → Check rate limit (Redis)
   d. AuthMiddleware → Verify JWT, inject current_user
4. Router → FastAPI route handler
5. Route Handler → Service Layer (business logic)
6. Service → Integration Layer (GitHubClient, OpenRouterClient)
7. Service → Database (via SQLAlchemy async session)
8. Service → Cache (Redis read/write)
9. Response → Pydantic schema serialization
10. Response → JSON → Client
```

---

## 4.4 AI Layer — LangGraph Agent Orchestration

### 4.4.1 LangGraph State Machine Overview

The AI layer is implemented as a **LangGraph StateGraph** — a directed graph where nodes are agents (LLM-powered functions) and edges define state transitions. The orchestration graph is defined declaratively and compiled into a runnable with built-in checkpointing, retry, and parallel execution.

```
                     ┌─────────────────┐
                     │   START NODE    │
                     │  (API Trigger)  │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ REPO ANALYZER   │
                     │ AGENT           │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ TECH DETECTOR   │
                     │ AGENT           │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ SECURITY REQ    │
                     │ AGENT           │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ WORKFLOW GEN    │
                     │ AGENT           │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ WORKFLOW        │
                     │ VALIDATOR       │
                     └────┬───────┬────┘
                          │       │
                    Pass  │       │ Fail
                          │       │
              ┌───────────▼┐  ┌───▼──────────┐
              │ PR CREATION│  │ REPAIR AGENT  │
              │ (API Call) │  └───┬──────┬────┘
              └────────────┘      │      │
                            Pass  │      │ Fail (3rd time)
                                  │      │
                     ┌────────────▼┐  ┌──▼──────────┐
                     │ Re-validate │  │ MANUAL       │
                     │ (loop back) │  │ REVIEW STATE │
                     └─────────────┘  └──────┬───────┘
                                             │
                                    ┌────────▼────────┐
                                    │ RISK ASSESSOR   │
                                    │ AGENT           │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │ RECOMMENDATION  │
                                    │ AGENT           │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │ END NODE        │
                                    └─────────────────┘
```

### 4.4.2 LangGraph State Definition

```python
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    # Input
    repository_id: str
    user_id: str
    github_token: str   # Encrypted, passed in-memory only
    
    # Repository Analysis
    file_tree: Optional[List[Dict[str, Any]]]
    manifest_files: Optional[Dict[str, str]]
    clone_path: Optional[str]
    
    # Technology Detection
    technologies: Optional[List[Dict[str, Any]]]  # [{name, type, confidence, evidence}]
    
    # Security Requirements
    security_requirements: Optional[List[Dict[str, Any]]]
    
    # Workflow
    workflow_yaml: Optional[str]
    workflow_config: Optional[Dict[str, Any]]  # User-selected triggers, tools
    
    # Validation
    validation_errors: Optional[List[Dict[str, Any]]]
    validation_passed: Optional[bool]
    
    # Repair
    repair_attempts: int
    repair_history: Optional[List[Dict[str, Any]]]
    
    # Final
    pr_url: Optional[str]
    pr_number: Optional[int]
    
    # Risk & Recommendations
    findings: Optional[List[Dict[str, Any]]]
    risk_score: Optional[float]
    recommendations: Optional[List[Dict[str, Any]]]
    
    # Control
    status: str  # "analyzing", "generating", "validating", "repairing", "complete", "failed"
    errors: List[str]
```

### 4.4.3 OpenRouter LLM Integration

```python
class OpenRouterClient:
    """
    Wrapper around OpenRouter API for unified LLM access.
    Supports model routing, fallback, and cost tracking.
    """
    BASE_URL = "https://openrouter.ai/api/v1"
    
    # Model tier configuration
    MODELS = {
        "primary": "anthropic/claude-sonnet-4",     # Complex reasoning
        "secondary": "openai/gpt-4o",               # High-quality generation
        "fallback": "google/gemini-2.5-flash",       # Fast + cost-effective
        "lightweight": "meta-llama/llama-4-maverick" # Simple classification
    }
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,  # JSON mode
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """Single LLM call with retry and fallback."""
    
    async def structured_output(
        self,
        model: str,
        messages: List[Dict[str, str]],
        output_schema: Dict,  # JSON Schema for structured output
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """LLM call guaranteeing structured JSON output."""
```

**Model Selection Strategy by Agent:**

| Agent | Model | Reasoning |
|---|---|---|
| Repository Analyzer | `lightweight` | Simple file tree parsing, minimal reasoning |
| Technology Detector | `primary` | Complex multi-language/framework classification |
| Security Requirement | `primary` | Needs deep security knowledge |
| Workflow Generator | `secondary` | Large structured output generation |
| Workflow Validator | `lightweight` | Schema checking, pattern matching |
| Workflow Repair | `secondary` | Complex YAML manipulation |
| Risk Assessor | `primary` | Nuanced risk analysis |
| Recommendation | `secondary` | Code fix generation |

---

## 4.5 GitHub Integration Layer

### 4.5.1 GitHub API Interactions

```
┌──────────────────────────────────────────────────────────────┐
│                    GitHubClient                               │
│                                                              │
│  Authentication Methods:                                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. OAuth Access Token  (user-specific, scoped)        │  │
│  │ 2. GitHub App JWT       (installation-wide)           │  │
│  │ 3. Personal Access Token (user-provided, scoped)      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  API Operations:                                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ GET  /user/repos                     → List repos      │  │
│  │ GET  /repos/{owner}/{repo}           → Get repo        │  │
│  │ GET  /repos/{owner}/{repo}/languages → Languages       │  │
│  │ GET  /repos/{owner}/{repo}/git/trees → File tree       │  │
│  │ POST /repos/{owner}/{repo}/git/refs  → Create branch   │  │
│  │ PUT  /repos/{owner}/{repo}/contents/* → Create file    │  │
│  │ POST /repos/{owner}/{repo}/pulls     → Create PR       │  │
│  │ GET  /repos/{owner}/{repo}/commits/*/check-runs → Checks│  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Rate Limit Handling:                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ • Track X-RateLimit-Remaining header                   │  │
│  │ • Pause when < 50 remaining until X-RateLimit-Reset   │  │
│  │ • Queue non-urgent requests during rate-limited window │  │
│  │ • Use conditional requests (ETag/If-None-Match)        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.6 Database Layer

### 4.6.1 PostgreSQL Schema (Logical Overview)

```
┌──────────┐     ┌──────────────┐     ┌────────────────┐
│  users   │────▶│ repositories │────▶│ analysis_jobs  │
└──────────┘     └──────────────┘     └───────┬────────┘
       │                                       │
       │                              ┌────────▼────────┐
       │                              │ analysis_results │
       │                              └─────────────────┘
       │
       ├──────────▶┌──────────────┐
       │           │   workflows   │
       │           └───────┬──────┘
       │                   │
       │           ┌───────▼────────┐
       │           │ workflow_runs  │
       │           └───────┬────────┘
       │                   │
       │           ┌───────▼────────┐
       │           │   findings     │
       │           └───────┬────────┘
       │                   │
       │           ┌───────▼────────┐
       │           │recommendations │
       │           └────────────────┘
       │
       ├──────────▶┌──────────────┐
       │           │ pull_requests │
       │           └──────────────┘
       │
       ├──────────▶┌──────────────┐
       │           │  audit_logs  │
       │           └──────────────┘
       │
       └──────────▶┌──────────────┐
                   │  credentials │ (encrypted at rest)
                   └──────────────┘
```

### 4.6.2 Redis Cache Architecture

```
Redis Instance (with persistence via AOF):

┌───────────────────────────────────────────┐
│  Key Pattern         │ Purpose           │ TTL    │
├───────────────────────────────────────────┤
│ session:{session_id}  │ JWT session data  │ 24h    │
│ ratelimit:{user_id}:* │ Rate limit counter│ 1m     │
│ github:repos:{user}   │ Repo list cache   │ 5m     │
│ analysis:{job_id}     │ Job status/progress│ 1h    │
│ dashboard:{repo_id}   │ Dashboard cache   │ 30m    │
│ queue:analysis         │ Job queue (List)  │ N/A    │
│ queue:monitoring       │ Monitoring queue  │ N/A    │
└───────────────────────────────────────────┘
```

---

## 4.7 Data Flow Summary

### 4.7.1 Repository Analysis Data Flow

```
User Browser → POST /api/v1/analysis/{repo_id}/start
                    │
                    ▼
            FastAPI Analysis Router
                    │
                    ▼
            AnalysisService.create_job()
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
   PostgreSQL    Redis       LangGraph
   INSERT job    ENQUEUE     Worker picks
   status=q'd    message     up message
                                │
                                ▼
                        OpenRouter LLM
                        (tech detection)
                                │
                                ▼
                        PostgreSQL
                        UPDATE job +
                        INSERT results
                                │
                                ▼
                        Redis PUBLISH
                        (WebSocket notify)
                                │
                                ▼
                        User Browser
                        (SSE/WS update)
```

### 4.7.2 Workflow Generation Data Flow

```
User Browser → POST /api/v1/workflows/generate
                    │
                    ▼
            WorkflowService.generate()
                    │
                    ▼
            LangGraph StateGraph.invoke()
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
   DB: Fetch   OpenRouter    OpenRouter
   analysis    LLM: Security  LLM: Generate
   results     Requirements   Workflow YAML
                    │
                    ▼
            YAML Parser +
            Schema Validator
                    │
            ┌───────┴───────┐
            │               │
        Pass              Fail
            │               │
            ▼               ▼
   Store workflow    ┌──────────────┐
   in PostgreSQL     │ Repair Agent │
                     └──────┬───────┘
                            │
                    ┌───────┴───────┐
                    │               │
                Pass              Fail (3x)
                    │               │
                    ▼               ▼
           Store repaired    Mark "needs
           workflow          manual review"
                    │
                    ▼
            Response to Browser
            (workflow YAML +
             validation status +
             AI explanations)
```
