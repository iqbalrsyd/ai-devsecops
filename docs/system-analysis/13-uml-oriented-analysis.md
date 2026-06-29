# 13. UML-Oriented Analysis

## 13.1 Use Case Diagram Description

### 13.1.1 Actors

| Actor | Type | Description |
|---|---|---|
| **DevSecOps Engineer** | Primary | The main system user who connects repositories, triggers analysis, generates workflows, and reviews security results |
| **Security Auditor** | Secondary | Reviews security dashboards, exports compliance reports, configures policies |
| **System Administrator** | Secondary | Manages system configuration, monitors health, rotates secrets |
| **Repository Owner** | External | GitHub repository owner who reviews and merges AI-generated PRs |
| **GitHub** | External System | External API for repository access, OAuth authentication, and CI/CD execution |
| **OpenRouter** | External System | External LLM API service providing AI capabilities |
| **LangGraph Engine** | Internal System | The multi-agent orchestrator that coordinates AI operations |

### 13.1.2 Use Cases

```
System Boundary: AI-Powered DevSecOps Agent Platform
══════════════════════════════════════════════════════════

DevSecOps Engineer:
├── Authenticate with GitHub OAuth         ◀── includes ── GitHub OAuth Service
├── Connect GitHub Repository              ◀── extends ── Verify Repository Access
├── Analyze Repository Structure           ◀── includes ── LangGraph Agent Chain
│   ├── Detect Languages
│   ├── Detect Frameworks
│   ├── Detect Build Tools
│   ├── Detect Test Frameworks
│   └── Detect Deployment Configurations
├── Configure Workflow Generation          ◀── extends ── Select Security Tools
├── Generate Secure CI/CD Workflow         ◀── includes ── LLM Generation + Validation
├── Validate/Repair Generated Workflow     ◀── includes ── Self-Correction Loop
├── Create Pull Request                    ◀── includes ── GitHub Branch/PR API
├── Monitor Workflow Execution             ◀── includes ── GitHub Checks API Polling
├── View Security Dashboard                ◀── includes ── Risk Score Calculation
├── Review Security Findings               ◀── extends ── Triage Findings
├── Review AI Recommendations              ◀── extends ── Apply Auto-Fixes
├── Export Security Report                 ◀── extends ── PDF/JSON/CSV Generation
└── Provide Feedback on AI Decisions       ◀── extends ── Few-Shot Learning Input

Security Auditor:
├── View Organization Security Dashboard
├── Configure Security Policies            ◀── extends ── Severity Thresholds
├── Audit AI Decision Logs
├── Export Compliance Reports
└── Override Risk Scores

System Administrator:
├── Manage System Configuration
├── Monitor System Health
├── Manage API Keys & Secrets
├── View Audit Logs
└── Manage Rate Limits

Repository Owner:
├── Review AI-Generated PR
├── Merge PR
├── Configure Branch Protection            (external to system)
└── Manage Repository Secrets              (external to system)
```

### 13.1.3 Use Case Relationships

```
                     ┌──────────────────────────┐
                     │   Authenticate with       │
                     │   GitHub OAuth            │
                     └─────────────┬────────────┘
                                   │ <<include>>
                     ┌─────────────▼────────────┐
                     │   Connect GitHub          │
                     │   Repository              │
                     └─────────────┬────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Analyze          │    │ Generate Secure │    │ View Security   │
│ Repository       │    │ CI/CD Workflow  │    │ Dashboard       │
│ Structure        │    │                 │    │                 │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │ <<include>>          │ <<include>>          │ <<extend>>
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ LangGraph Agent  │    │ Validate &      │    │ Triage Findings │
│ Chain            │    │ Repair Loop     │    │                 │
└─────────────────┘    └────────┬────────┘    └─────────────────┘
                                │
                                │ <<include>>
                                ▼
                       ┌─────────────────┐
                       │ Create Pull      │
                       │ Request          │
                       └────────┬────────┘
                                │
                                │ <<include>>
                                ▼
                       ┌─────────────────┐
                       │ Monitor Workflow │
                       │ Execution        │
                       └────────┬────────┘
                                │
                                │ <<include>>
                                ▼
                       ┌─────────────────┐
                       │ Calculate Risk   │
                       │ Score & Generate │
                       │ Recommendations  │
                       └─────────────────┘
```

---

## 13.2 Activity Diagram Description

*(Detailed branching activity flows are provided in Section 8 with four complete activity diagrams.)*

### Summary of Activity Diagrams:

1. **Repository Analysis Activity**: Covers clone/API fallback, file tree scanning, LLM classification, cross-validation, confidence checking, and result persistence. Main branch: clone → scan → LLM → validate. Alternative: API fallback, heuristic mode, user confirmation for low confidence.

2. **Workflow Generation Activity**: Covers config validation, security requirement inference, LLM YAML generation, post-processing, and 4-stage validation. Branching on config validity, YAML parse success, schema validity, policy compliance, and semantic correctness.

3. **Workflow Self-Correction Activity**: Covers error classification, attempt counting, loop detection, category-specific repairs (syntax, schema, policy, semantic), and re-validation routing. Maximum 3 iterations with loop detection.

4. **Security Risk Assessment Activity**: Covers finding aggregation, deduplication, weighted scoring, normalization, categorization, trend analysis, conditional LLM assessment for high-risk repos, and notification routing based on urgency.

---

## 13.3 Sequence Diagram Description

*(Detailed sequence diagrams are provided in Section 7 with four complete sequence flows.)*

### Summary of Sequence Diagrams:

1. **Repository Analysis Sequence**: 12 actors including User → React FE → FastAPI → Redis Q → LangGraph → Repo Analyzer → Tech Detector → OpenRouter → GitHub API → PostgreSQL. Shows async job queueing, WebSocket progress updates, and LLM integration.

2. **Workflow Generation Sequence**: 11 actors with highlighted validation-repair loop. Shows conditional routing (Agent passes errors to Repair, not back to Generator) and the re-validation cycle.

3. **Pull Request Creation Sequence**: 7 actors showing the multi-step GitHub API interaction: get ref SHA → create branch → commit file → create PR → enqueue monitoring. Includes idempotency handling.

4. **Security Scan Result Analysis Sequence**: 8 actors showing post-execution flow: polling detection → artifact download → finding parsing → risk assessment → recommendation generation → dashboard population.

---

## 13.4 Component Diagram Description

### 13.4.1 Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       AI-Powered DevSecOps Agent                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────┐          ┌───────────────────────────┐   │
│  │   Frontend Application    │          │    Backend Application     │   │
│  │   ┌───────────────────┐   │  HTTPS  │   ┌───────────────────┐    │   │
│  │   │ Auth Module       │   │◀───────▶│   │ Auth Service      │    │   │
│  │   │ Dashboard Module  │   │   WSS   │   │ Repo Service      │    │   │
│  │   │ Workflow Module   │   │         │   │ Analysis Service  │    │   │
│  │   │ Security Module   │   │         │   │ Workflow Service  │    │   │
│  │   └───────────────────┘   │         │   │ PR Service        │    │   │
│  └───────────────────────────┘         │   │ Monitoring Service│    │   │
│                                        │   │ Report Service    │    │   │
│                                        │   └───────┬───────────┘    │   │
│                                        │           │                │   │
│  ┌─────────────────────────────────────┼───────────┼────────────┐   │   │
│  │            AI Layer                 │           │            │   │   │
│  │  ┌──────────────────────────────┐   │   ┌───────▼──────────┐ │   │   │
│  │  │  LangGraph Orchestrator      │   │   │  Integration     │ │   │   │
│  │  │  ┌──────────────────────┐    │   │   │  Layer           │ │   │   │
│  │  │  │ Repo Analyzer Agent  │    │   │   │  ┌───────────┐  │ │   │   │
│  │  │  │ Tech Detector Agent  │    │   │   │  │ GitHub    │  │ │   │   │
│  │  │  │ Security Req Agent   │    │   │   │  │ Client    │  │ │   │   │
│  │  │  │ Workflow Gen Agent   │    │   │   │  ├───────────┤  │ │   │   │
│  │  │  │ Validator Agent      │    │   │   │  │ OpenRouter│  │ │   │   │
│  │  │  │ Repair Agent         │    │   │   │  │ Client    │  │ │   │   │
│  │  │  │ Risk Assessor Agent  │    │   │   │  ├───────────┤  │ │   │   │
│  │  │  │ Recommendation Agent │    │   │   │  │ Redis     │  │ │   │   │
│  │  │  └──────────────────────┘    │   │   │  │ Client    │  │ │   │   │
│  │  └──────────────────────────────┘   │   │  └───────────┘  │ │   │   │
│  └─────────────────────────────────────┘   └─────────────────┘ │   │   │
│                                                                          │
│  ┌──────────────────────┐          ┌──────────────────────┐             │
│  │   PostgreSQL         │          │   Redis              │             │
│  │   - Users            │          │   - Session Cache    │             │
│  │   - Repositories     │          │   - Job Queue        │             │
│  │   - Analysis Results │          │   - Rate Limiter     │             │
│  │   - Workflows        │          │   - Dashboard Cache  │             │
│  │   - Findings         │          │   - Pub/Sub          │             │
│  │   - Recommendations  │          │                      │             │
│  │   - Audit Logs       │          │                      │             │
│  └──────────────────────┘          └──────────────────────┘             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

External Systems:
┌────────────────┐    ┌────────────────┐    ┌──────────────────────┐
│  GitHub API    │    │  OpenRouter    │    │  GitHub Actions      │
│  - REST v3     │    │  API           │    │  (Workflow Runners)  │
│  - GraphQL v4  │    │  - Chat Compl. │    │  - Semgrep           │
│  - OAuth 2.0   │    │  - Model List  │    │  - Gitleaks          │
│                │    │  - Cost Track  │    │  - Trivy             │
│                │    │                │    │  - CodeQL            │
│                │    │                │    │  - Dependency Review │
└────────────────┘    └────────────────┘    └──────────────────────┘
```

### 13.4.2 Component Interfaces

| Component | Provided Interface | Required Interface |
|---|---|---|
| **Auth Module** | Login page, OAuth redirect, session management | `POST /auth/*` REST endpoints |
| **Dashboard Module** | KPI cards, charts, findings table, recommendations list | `GET /dashboard/*`, `GET /findings/*`, `GET /recommendations/*` |
| **Workflow Module** | Diff editor, config form, validation status display | `POST /workflows/*`, `GET /workflows/*`, WebSocket |
| **Auth Service** | JWT generation, token validation, OAuth flow | GitHub OAuth API, Redis (sessions), PostgreSQL (users) |
| **Repo Service** | Repository CRUD, access verification | GitHub API, PostgreSQL |
| **Analysis Service** | Job creation, progress tracking | Redis (queue), LangGraph Orchestrator |
| **Workflow Service** | Generation, validation, repair orchestration | LangGraph Orchestrator, PostgreSQL |
| **LangGraph Orchestrator** | Agent state machine, conditional routing | OpenRouter API, GitHub API, PostgreSQL |
| **GitHub Client** | Repo access, PR creation, check polling | GitHub REST API |
| **OpenRouter Client** | Chat completions, structured output | OpenRouter API |

---

## 13.5 Deployment Diagram Description

### 13.5.1 Deployment Nodes

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION ENVIRONMENT                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐         │
│  │                   Kubernetes Cluster (k8s)                   │         │
│  │                                                              │         │
│  │  ┌─────────────────────────────────────────────────────┐    │         │
│  │  │              Frontend Deployment                     │    │         │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │    │         │
│  │  │  │ React Pod 1 │  │ React Pod 2 │  │ React Pod N │  │    │         │
│  │  │  │ (nginx+spa) │  │ (nginx+spa) │  │ (nginx+spa) │  │    │         │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘  │    │         │
│  │  │         Port: 80 (served by nginx)                   │    │         │
│  │  └─────────────────────────────────────────────────────┘    │         │
│  │                            │                                 │         │
│  │  ┌─────────────────────────▼───────────────────────────┐    │         │
│  │  │              Backend Deployment                      │    │         │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │    │         │
│  │  │  │ FastAPI Pod 1│  │ FastAPI Pod 2│  │FastAPI Pod N│ │    │         │
│  │  │  │ (uvicorn)    │  │ (uvicorn)    │  │ (uvicorn)   │ │    │         │
│  │  │  │ Port: 8000   │  │ Port: 8000   │  │ Port: 8000  │ │    │         │
│  │  │  └──────────────┘  └──────────────┘  └────────────┘ │    │         │
│  │  └─────────────────────────────────────────────────────┘    │         │
│  │                            │                                 │         │
│  │  ┌─────────────────────────▼───────────────────────────┐    │         │
│  │  │              Worker Deployment                       │    │         │
│  │  │  ┌──────────────────┐  ┌──────────────────┐         │    │         │
│  │  │  │ Analysis Worker  │  │ Monitoring Worker│         │    │         │
│  │  │  │ (LangGraph)      │  │ (GitHub Poller)  │         │    │         │
│  │  │  │ Replicas: 3      │  │ Replicas: 2      │         │    │         │
│  │  │  └──────────────────┘  └──────────────────┘         │    │         │
│  │  └─────────────────────────────────────────────────────┘    │         │
│  │                                                              │         │
│  │  ┌─────────────────────────────────────────────────────┐    │         │
│  │  │              Ingress / API Gateway                   │    │         │
│  │  │  ┌──────────────────────────────────────────────┐   │    │         │
│  │  │  │  Nginx Ingress / Traefik                     │   │    │         │
│  │  │  │  - TLS Termination (Let's Encrypt)           │   │    │         │
│  │  │  │  - Rate Limiting                             │   │    │         │
│  │  │  │  - WebSocket Upgrade                         │   │    │         │
│  │  │  │  - Load Balancing                            │   │    │         │
│  │  │  └──────────────────────────────────────────────┘   │    │         │
│  │  └─────────────────────────────────────────────────────┘    │         │
│  │                                                              │         │
│  │  ┌──────────────────────┐  ┌──────────────────────┐         │         │
│  │  │  PostgreSQL Stateful │  │  Redis Stateful       │         │         │
│  │  │  Set                 │  │  Set                  │         │         │
│  │  │  ┌────────────────┐  │  │  ┌────────────────┐   │         │         │
│  │  │  │ PostgreSQL Pod │  │  │  │ Redis Pod      │   │         │         │
│  │  │  │ Port: 5432     │  │  │  │ Port: 6379     │   │         │         │
│  │  │  │ PVC: 100Gi SSD │  │  │  │ PVC: 20Gi SSD  │   │         │         │
│  │  │  └────────────────┘  │  │  └────────────────┘   │         │         │
│  │  │  Replicas: 1 (w/     │  │  Replicas: 1 (w/     │         │         │
│  │  │  standby)            │  │  AOF persistence)    │         │         │
│  │  └──────────────────────┘  └──────────────────────┘         │         │
│  └─────────────────────────────────────────────────────────────┘         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
│ GitHub       │    │ OpenRouter   │    │ Container Registry   │
│ api.github.  │    │ openrouter.  │    │ (Docker Hub / GHCR)  │
│ com          │    │ ai           │    │                      │
└──────────────┘    └──────────────┘    └──────────────────────┘
```

### 13.5.2 Development Environment

```
Developer Machine:
┌──────────────────────────────────────────────┐
│  Docker Compose                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ React    │ │ FastAPI  │ │ LangGraph│      │
│  │ Dev      │ │ (reload) │ │ Worker   │      │
│  │ :3000    │ │ :8000    │ │ :8001    │      │
│  └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐                   │
│  │ Postgres │ │ Redis    │                   │
│  │ :5432    │ │ :6379    │                   │
│  └──────────┘ └──────────┘                   │
└──────────────────────────────────────────────┘
```

---

## 13.6 Class Diagram Description

### 13.6.1 Domain Model Classes

```
┌─────────────────────────┐       ┌─────────────────────────┐
│         User            │       │      Credential         │
├─────────────────────────┤       ├─────────────────────────┤
│ - id: UUID              │──1:N──│ - id: UUID              │
│ - github_id: BigInt     │       │ - user_id: UUID (FK)    │
│ - username: String      │       │ - credential_type: Enum │
│ - email: String?        │       │ - token_encrypted: Bytes│
│ - avatar_url: String?   │       │ - token_hash: String    │
│ - role: Enum            │       │ - scopes: JSONB         │
│ - created_at: DateTime  │       │ - expires_at: DateTime? │
│ - updated_at: DateTime  │       │ - is_active: Bool       │
│ - last_login_at: DT?    │       │ - last_used_at: DT?     │
├─────────────────────────┤       ├─────────────────────────┤
│ + login(oauth_code)     │       │ + encrypt(token)        │
│ + logout()              │       │ + decrypt()             │
│ + refresh_token()       │       │ + revoke()              │
└─────────────────────────┘       │ + rotate(new_token)     │
          │                        └─────────────────────────┘
          │ 1:N
          ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│      Repository         │       │     AnalysisJob         │
├─────────────────────────┤       ├─────────────────────────┤
│ - id: UUID              │──1:N──│ - id: UUID              │
│ - user_id: UUID (FK)    │       │ - repository_id: UUID   │
│ - github_repo_id: BigInt│       │ - status: Enum          │
│ - name: String          │       │ - progress_percent: Int │
│ - full_name: String     │       │ - error_message: String?│
│ - owner_login: String   │       │ - started_at: DateTime? │
│ - visibility: Enum      │       │ - completed_at: DT?     │
│ - default_branch: String│       │ - duration_ms: Int?     │
│ - is_archived: Bool     │       ├─────────────────────────┤
│ - status: Enum          │       │ + start()               │
├─────────────────────────┤       │ + update_progress(pct)  │
│ + verify_access()       │       │ + complete(results)     │
│ + disconnect()          │       │ + fail(error_msg)       │
└─────────────────────────┘       └────────────┬────────────┘
          │ 1:N                                │ 1:1
          ▼                                    ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│       Workflow          │       │    AnalysisResult       │
├─────────────────────────┤       ├─────────────────────────┤
│ - id: UUID              │       │ - id: UUID              │
│ - repository_id: UUID   │       │ - job_id: UUID (FK)     │
│ - created_by: UUID      │       │ - technologies: JSONB   │
│ - filename: String      │       │ - languages: JSONB      │
│ - yaml_content: Text    │       │ - frameworks: JSONB     │
│ - status: Enum          │       │ - build_tools: JSONB    │
│ - validation_result: JB │       │ - test_frameworks: JSONB│
│ - repair_history: JSONB │       │ - deployment_configs: JB│
│ - ai_explanations: JB   │       │ - analysis_mode: Enum   │
├─────────────────────────┤       │ - file_count: Int       │
│ + generate(context)     │       ├─────────────────────────┤
│ + validate()            │       │ + to_dict()             │
│ + repair(errors)        │       │ + get_technologies()    │
└────────────┬────────────┘       └─────────────────────────┘
             │ 1:N
             ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│     WorkflowRun         │       │       Finding           │
├─────────────────────────┤       ├─────────────────────────┤
│ - id: UUID              │──1:N──│ - id: UUID              │
│ - workflow_id: UUID (FK)│       │ - run_id: UUID (FK)     │
│ - repository_id: UUID   │       │ - repository_id: UUID   │
│ - github_run_id: BigInt │       │ - tool: Enum            │
│ - head_sha: String      │       │ - rule_id: String       │
│ - status: Enum          │       │ - severity: Enum        │
│ - conclusion: Enum?     │       │ - file_path: String     │
│ - check_runs_data: JB   │       │ - line_number: Int?     │
├─────────────────────────┤       │ - cwe_id: String?       │
│ + start_monitoring()    │       │ - cvss_score: Float?    │
│ + poll_status()         │       │ - triage_status: Enum   │
│ + download_artifacts()  │       │ - fingerprint: String   │
└─────────────────────────┘       ├─────────────────────────┤
                                  │ + triage(status, user)  │
                                  │ + deduplicate()         │
                                  │ + to_sarif()            │
                                  └────────────┬────────────┘
                                               │ 1:N
                                               ▼
                                  ┌─────────────────────────┐
                                  │    Recommendation       │
                                  ├─────────────────────────┤
                                  │ - id: UUID              │
                                  │ - finding_id: UUID (FK) │
                                  │ - repository_id: UUID   │
                                  │ - type: Enum            │
                                  │ - priority: Enum        │
                                  │ - explanation: Text     │
                                  │ - fix_code: Text?       │
                                  │ - auto_fixable: Bool    │
                                  │ - breaking_change: Bool │
                                  │ - confidence: Float     │
                                  │ - status: Enum          │
                                  ├─────────────────────────┤
                                  │ + apply()               │
                                  │ + ignore(reason)        │
                                  │ + to_pr_body()          │
                                  └─────────────────────────┘

┌─────────────────────────┐       ┌─────────────────────────┐
│     PullRequest         │       │       AuditLog          │
├─────────────────────────┤       ├─────────────────────────┤
│ - id: UUID              │       │ - id: UUID              │
│ - repository_id: UUID   │       │ - user_id: UUID? (FK)   │
│ - workflow_id: UUID?    │       │ - action: String        │
│ - created_by: UUID      │       │ - resource_type: String │
│ - pr_number: Int        │       │ - resource_id: UUID?    │
│ - pr_url: String        │       │ - details: JSONB        │
│ - branch_name: String   │       │ - ip_address: INET?     │
│ - status: Enum          │       │ - status: Enum          │
├─────────────────────────┤       ├─────────────────────────┤
│ + create_branch()       │       │ + log(action, details)  │
│ + commit_file()         │       │ + query(filters)        │
│ + open_pr()             │       └─────────────────────────┘
└─────────────────────────┘
```

---

## 13.7 Entity Relationship Diagram Description

*(The complete ERD with all entities, attributes, relationships, and indexes is provided in Section 9 — Database Logic.)*

### Summary of Key Relationships:

```
users ──1:N──▶ repositories
users ──1:N──▶ credentials
users ──1:N──▶ audit_logs

repositories ──1:N──▶ analysis_jobs
repositories ──1:N──▶ workflows
repositories ──1:N──▶ workflow_runs
repositories ──1:N──▶ findings
repositories ──1:N──▶ pull_requests

analysis_jobs ──1:1──▶ analysis_results

workflows ──1:N──▶ workflow_runs
workflows ──1:N──▶ pull_requests

workflow_runs ──1:N──▶ findings

findings ──1:N──▶ recommendations

Cardinalities:
- User:Repository = 1:N (a user connects up to 50 repos)
- Repository:Workflow = 1:N (a repo may have multiple generated workflows)
- Workflow:WorkflowRun = 1:N (a workflow may execute many times)
- WorkflowRun:Finding = 1:N (each run produces many findings)
- Finding:Recommendation = 1:N (a finding may have multiple fix options)
```

### Relationship Types:

| Parent | Child | Type | On Delete | On Update |
|---|---|---|---|---|
| users | repositories | Identifying | CASCADE | CASCADE |
| users | credentials | Identifying | CASCADE | CASCADE |
| users | audit_logs | Non-identifying | SET NULL | CASCADE |
| repositories | analysis_jobs | Identifying | CASCADE | CASCADE |
| repositories | workflows | Identifying | CASCADE | CASCADE |
| repositories | workflow_runs | Identifying | CASCADE | CASCADE |
| repositories | findings | Identifying | CASCADE | CASCADE |
| repositories | pull_requests | Identifying | CASCADE | CASCADE |
| repositories | recommendations | Identifying | CASCADE | CASCADE |
| analysis_jobs | analysis_results | Identifying | CASCADE | CASCADE |
| workflows | workflow_runs | Identifying | SET NULL | CASCADE |
| workflow_runs | findings | Identifying | CASCADE | CASCADE |
| findings | recommendations | Identifying | CASCADE | CASCADE |
| workflows | pull_requests | Non-identifying | SET NULL | CASCADE |
