# AI Repository-Aware DevSecOps Pipeline Engineer — Product Requirements Document

**Document Version:** 2.0
**Status:** Final
**Author:** AI Systems Design Team

---

## Table of Contents

1. Executive Summary
2. Product Vision
3. User Personas
4. Core Workflow (16-Step Process)
5. Repository Analysis Engine
6. DevSecOps Pipeline Generation
7. Security Tool Integration
8. LangGraph Agent Architecture
9. System Architecture
10. Sequence Diagrams
11. API Specifications
12. Database Schema
13. GitHub Integration Design
14. Security Architecture
15. Dashboard Design
16. Frontend Component Tree
17. Risk Scoring Framework
18. Implementation Roadmap
19. MVP Scope
20. Future Enhancements
21. Appendix

---

## 1. Executive Summary

The **AI Repository-Aware DevSecOps Pipeline Engineer** is an intelligent agent platform that autonomously connects to GitHub repositories, analyzes their structure and technology stack, generates secure CI/CD pipelines, deploys them via Pull Requests, executes GitHub Actions workflows, monitors execution, collects security scan outputs, performs comprehensive risk analysis, and delivers actionable remediation — all through an interactive web dashboard.

**Current state:** The existing codebase is a Workflow Security Audit Agent with intent classification, PR review, scan analysis, workflow audit, and report generation. It connects to PostgreSQL, Redis, and supports LLM providers. Frontend is React + TypeScript + Tailwind CSS + Recharts.

**Target state:** A full-lifecycle AI DevSecOps Engineer that requires minimal user input — the user connects a repository and the AI autonomously engineers a secure CI/CD pipeline tailored to the project's actual architecture, technologies, and security requirements.

**Key differentiator:** The AI understands repository context (languages, frameworks, build tools, testing frameworks, containerization, deployment config) and dynamically generates appropriate pipelines with security built in by default. It acts as a DevSecOps engineer, not just a workflow auditor.

---

## 2. Product Vision

> "An AI that autonomously understands any GitHub repository and acts as your team's dedicated DevSecOps engineer — scanning architectures, generating secure pipelines, deploying safely, and continuously improving security posture."

### 2.1 Design Principles

| Principle | Description |
|---|---|
| Repository-Aware | AI scans and understands actual repository contents before generating anything |
| Secure by Default | Every generated workflow includes SAST, dependency scanning, secret detection, container scanning |
| Human in the Loop | All workflow deployments go through PR review — never direct push to main |
| Explainable AI | Every agent decision includes reasoning visible to the user |
| Progressive Enhancement | Start with audit, graduate to auto-generation, mature to auto-remediation |
| Tool-Agnostic Security | Support multiple scanners (Semgrep, Trivy, Gitleaks, OWASP Dependency-Check) with unified output format |

### 2.2 Supported Technologies

**Languages:** Node.js/TypeScript, Python, Go, Java/Kotlin, Rust, Ruby, PHP, .NET/C#
**Frameworks:** Express, NestJS, Spring Boot, Django, Flask, FastAPI, React, Next.js, Vue, Angular, Gin, Echo, Rails, Laravel, ASP.NET
**Build Tools:** npm, yarn, pnpm, pip, poetry, pipenv, go mod, gradle, maven, cargo, bundler, composer, nuget
**Testing:** Jest, Mocha, Vitest, pytest, unittest, go test, JUnit, RSpec, PHPUnit, NUnit
**Containerization:** Docker, docker-compose, Kubernetes, Helm
**Deployment:** Docker, Kubernetes, AWS ECS, Cloud Run, Heroku, Vercel, Netlify
**Scanners:** Semgrep, Trivy, Gitleaks, OWASP Dependency-Check

### 2.3 Key Capabilities

- **Autonomous Repository Understanding** — No manual language/framework input required
- **Technology Stack Detection** — Identifies languages, frameworks, build tools, test frameworks from repo contents
- **Architecture Inference** — Detects monolith, microservices, containerized apps from repo structure
- **Intelligent Pipeline Generation** — Dynamically selects stages based on detected technologies
- **Security Requirement Inference** — Determines necessary security controls based on stack and architecture
- **Secure Workflow Engineering** — Generates production-grade GitHub Actions YAML with security best practices
- **Safe Deployment** — Creates branches, commits, and PRs (never pushes directly to main)
- **End-to-End Monitoring** — Tracks workflow execution in real-time
- **Deep Security Analysis** — Parses scanner outputs, identifies vulnerabilities, maps to compliance frameworks
- **Actionable Recommendations** — Provides specific, code-level remediation for every finding

---

## 3. User Personas

### Persona A: Platform Engineer (Primary)

- **Name:** Alex
- **Role:** Builds and maintains CI/CD infrastructure across multiple repositories
- **Pain:** Spends hours analyzing each repo's tech stack, writing and debugging GitHub Actions YAML; security teams block pipelines due to missing scans
- **Gain:** AI analyzes repos autonomously and generates correct, secure YAML tailored to each project
- **Need:** Minimal input required — connect repo, get a production-ready pipeline

### Persona B: Security Engineer

- **Name:** Sam
- **Role:** Ensures pipeline security compliance across the organization
- **Pain:** Manually auditing every repository's CI/CD configuration; inconsistent security controls across projects
- **Gain:** AI ensures every generated pipeline meets security standards automatically
- **Need:** Compliance mapping, risk scoring, and detailed security reports

### Persona C: Engineering Manager

- **Name:** Jordan
- **Role:** Oversees team velocity and security posture
- **Pain:** No visibility into pipeline security health across multiple repos
- **Gain:** Dashboard showing all repos, their pipeline status, risk scores, and historical trends
- **Need:** High-level overview with drill-down capability

### Persona D: Startup CTO

- **Name:** Taylor
- **Role:** Technical leader at early-stage startup with no dedicated DevOps
- **Pain:** No CI/CD pipeline exists; manual deployment process; no security scanning
- **Gain:** AI sets up entire DevSecOps pipeline from scratch with zero configuration
- **Need:** Connect GitHub repo → get a complete, secure pipeline → deploy

---

## 4. Core Workflow (16-Step Process)

### Phase I: Repository Intake & Analysis

#### Step 1: User connects a GitHub repository

The user provides a GitHub repository URL or selects from connected repos. The system stores the repository reference and GitHub access token.

#### Step 2: AI scans the repository

The AI agent fetches repository metadata and directory structure via GitHub API. It retrieves root-level and well-known path contents (package.json, requirements.txt, Dockerfile, etc.).

| Data Fetched | Source |
|---|---|
| Repository metadata | `GET /repos/{owner}/{repo}` |
| Directory structure | `GET /repos/{owner}/{repo}/contents/` |
| Key config files | Well-known paths (package.json, pom.xml, Dockerfile, etc.) |
| Existing workflows | `.github/workflows/` directory contents |

#### Step 3: Technology detection

The AI analyzes repository contents to detect:

| Detection Target | Signals |
|---|---|
| Programming language | File extensions, lock files, config files |
| Framework | package.json dependencies, import statements, config patterns |
| Build tools | Build config files (webpack.config, tsconfig, Makefile, etc.) |
| Testing frameworks | Test config, test directory structure, devDependencies |
| Package manager | Lock files (package-lock.json, yarn.lock, poetry.lock, go.sum) |
| Containerization | Dockerfile, docker-compose.yml presence |
| Deployment config | Kubernetes manifests, Helm charts, cloud service configs |
| Database | ORM config, connection strings, migration files |

#### Step 4: Architecture detection

The AI infers the application architecture:

| Architecture | Signals |
|---|---|
| Monolith | Single package.json, single Dockerfile, flat structure |
| Microservices | Multiple services/ directories, multiple Dockerfiles, API gateway config |
| Frontend + Backend | Separate client/ and server/ directories, different package managers |
| Containerized | Dockerfile present, docker-compose.yml, Kubernetes manifests |
| Serverless | Cloud Functions triggers, serverless.yml, AWS Lambda handlers |

#### Step 5: Security requirement inference

Based on detected technologies and architecture, the AI determines:

| Security Control | Trigger |
|---|---|
| SAST (Semgrep) | Any source code detected |
| Dependency scanning | Any package manager detected |
| Secret detection | Any repository |
| Container scanning | Dockerfile or container config detected |
| IaC scanning | Kubernetes manifests, Terraform files detected |
| License compliance | Any package manager detected |
| SBOM generation | Containerized applications |
| DAST | Web application frameworks detected |

### Phase II: Pipeline Generation & Validation

#### Step 6: AI generates secure GitHub Actions workflow

The AI dynamically selects pipeline stages based on detection results and generates valid GitHub Actions YAML:

**Possible stages (selected dynamically):**

```
checkout → install → lint → build → unit-test → integration-test →
code-quality → SAST → dep-scan → secret-scan → container-scan →
iac-scan → artifact → deploy
```

**Security controls applied to every generated workflow:**

- All third-party actions pinned to commit SHA (not version tags)
- Minimal `GITHUB_TOKEN` permissions (read-only where possible)
- Concurrency groups configured to prevent duplicate runs
- `persist-credentials: false` on checkout actions
- `if:` conditions on deploy/publish jobs to gate on branch
- Security scans configured to fail on critical/high findings
- Proper job dependencies and ordering

#### Step 7: AI validates the generated workflow

The agent performs multi-layer validation:

| Validation | Method |
|---|---|
| YAML syntax | Python YAML parser |
| GitHub Actions schema | Structural validation (required keys, valid structure) |
| Action pinning | Audit all `uses:` lines for SHA vs tag references |
| Permission scoping | Check `permissions:` blocks for minimality |
| Secret exposure | Scan for `${{ secrets.* }}` in unsafe contexts |
| Stage completeness | Verify all required security stages are present |
| Workflow logic | Validate job dependencies, conditionals, matrix strategies |
| Best practices | Concurrency, caching, error handling, timeouts |

### Phase III: GitHub Deployment

#### Step 8: AI creates a new branch

Creates a branch from the default branch with naming convention:
```
ai-devsecops/generate-workflow-{timestamp}
```

#### Step 9: AI commits the generated workflow

Commits the workflow file to `.github/workflows/ci-cd.yml` on the new branch with a descriptive commit message.

#### Step 10: AI creates a Pull Request

Creates a PR from the new branch to the default branch with:
- Title: `[AI DevSecOps] Add secure CI/CD pipeline for {language}`
- Body: Full explanation of the workflow, detected technologies, security controls, and what each stage does
- Labels: `devsecops`, `automated`, `ai-generated`

The agent **never** auto-merges. The PR waits for human review.

#### Step 11: User reviews and approves the Pull Request

The user reviews the generated workflow, checks the explanation, and merges the PR.

### Phase IV: Execution & Monitoring

#### Step 12: GitHub Actions executes the workflow

Once merged (or via `workflow_dispatch`), GitHub Actions runs the pipeline automatically. The AI monitors execution from the dashboard.

#### Step 13: AI monitors execution status

The agent polls GitHub Actions API every 5 seconds and tracks:

| State | Description |
|---|---|
| Queued | Workflow is waiting for a runner |
| Running | Jobs are executing |
| Success | All jobs completed successfully |
| Failed | One or more jobs failed |
| Cancelled | Workflow was manually cancelled |

The agent also collects:
- Job status and step-by-step progress
- Execution logs per step
- Build artifacts (scan results, test reports)
- Duration per job and total execution time

### Phase V: Analysis & Reporting

#### Step 14: AI performs security analysis

Post-execution, the agent collects and analyzes scanner outputs from workflow artifacts:

**Scanner output parsing:**

| Scanner | Input | Analysis |
|---|---|---|
| Semgrep | SARIF/JSON results | Injection, XSS, crypto misuse, hardcoded secrets |
| Trivy | JSON vulnerability report | OS packages, app dependencies CVEs |
| Gitleaks | JSON findings | API keys, tokens, passwords, certificates |
| OWASP Dependency-Check | JSON report | Library vulnerabilities, CVE details |

**Analysis produces structured findings with:**
- Type, severity, file, line number
- Code snippet showing the vulnerability
- CWE/CVE references
- OWASP category mapping
- Scanner attribution
- Explanation of the vulnerability

#### Step 15: AI calculates risk scores

The risk engine computes:

| Score | Range | Description |
|---|---|---|
| Overall Risk Score | 0–100 | Weighted aggregate of all findings |
| Security Posture Score | 0–100 | Inverse of risk score (100 - risk) |
| Compliance Score | 0–100 | Control coverage percentage |

#### Step 16: AI generates recommendations

Each finding gets a structured recommendation:

```json
{
  "finding_type": "dependency_vulnerability",
  "severity": "critical",
  "file": "package.json",
  "package": "lodash",
  "installed_version": "4.17.20",
  "fixed_version": "4.17.21",
  "cve": "CVE-2024-1234",
  "explanation": "Prototype pollution in lodash allows...",
  "impact": "An attacker could pollute object prototypes...",
  "remediation": "Upgrade lodash from 4.17.20 to 4.17.21",
  "example": "npm install lodash@4.17.21"
}
```

### Phase VI: Dashboard Presentation

The dashboard displays all results including:
- Repository overview with detected technologies
- Generated workflow with syntax-highlighted YAML
- Pull Request status with direct link
- Workflow execution timeline (Gantt-style)
- Security findings with severity breakdown
- Risk score gauge
- Compliance scorecard
- Recommendations list
- Historical execution data

---

## 5. Repository Analysis Engine

### 5.1 Detection Matrix

| Artifact | Detects |
|---|---|
| `package.json` | Node.js, TypeScript, framework (Express, NestJS, React, Next.js, Vue, Angular), test framework (Jest, Mocha, Vitest, Playwright), build tool (Webpack, Vite, esbuild), linting (ESLint) |
| `requirements.txt` / `pyproject.toml` / `Pipfile` | Python, framework (Django, Flask, FastAPI), test framework (pytest, unittest), linting (ruff, flake8, pylint) |
| `go.mod` | Go, framework (Gin, Echo, Fiber, Chi), test (go test) |
| `pom.xml` / `build.gradle` | Java, Kotlin, framework (Spring Boot, Micronaut, Quarkus), build (Maven, Gradle), test (JUnit, TestNG) |
| `Cargo.toml` | Rust, framework (Actix, Rocket, Axum), test (cargo test) |
| `Gemfile` | Ruby, framework (Rails, Sinatra), test (RSpec, Minitest) |
| `composer.json` | PHP, framework (Laravel, Symfony), test (PHPUnit) |
| `*.csproj` / `*.sln` | .NET/C#, framework (ASP.NET, Blazor), test (NUnit, xUnit) |
| `Dockerfile` | Containerization, base image, exposed ports |
| `docker-compose.yml` | Multi-service orchestration, service dependencies |
| `k8s/*.yaml` / `*.k8s.yaml` | Kubernetes deployment, services, ingress |
| `helm/` / `Chart.yaml` | Helm charts |
| `*.tf` / `*.tfvars` | Terraform IaC |
| `serverless.yml` | Serverless framework |
| `.github/workflows/` | Existing CI/CD configuration |

### 5.2 Architecture Detection Logic

```
                      ┌─────────────────────────────┐
                      │    Repository Structure      │
                      └──────────┬──────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Monolith  │ │ Frontend │ │  Multi-  │
              │           │ │ + Backend│ │ Service  │
              └──────────┘ └──────────┘ └──────────┘
                    │            │            │
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Single   │ │ Monorepo │ │ Micro-   │
              │ package  │ │ client/  │ │ services │
              │ Single   │ │ server/  │ │ api/     │
              │ Docker   │ │ Separate │ │ auth/    │
              │          │ │ configs  │ │ Multiple │
              │          │ │          │ │ Docker   │
              └──────────┘ └──────────┘ └──────────┘
```

### 5.3 Detection Output Schema

```json
{
  "language": {
      "primary": "TypeScript",
      "secondary": []
  },
  "frameworks": ["React", "Express"],
  "build_tools": ["Vite", "tsc"],
  "test_frameworks": ["Vitest"],
  "package_manager": "npm",
  "containerization": {
      "has_dockerfile": true,
      "has_docker_compose": true,
      "has_kubernetes": false,
      "has_helm": false
  },
  "architecture": "frontend_backend",
  "has_existing_ci_cd": true,
  "existing_workflows": [".github/workflows/deploy.yml"]
}
```

---

## 6. DevSecOps Pipeline Generation

### 6.1 Dynamic Stage Selection

Stage selection follows a decision tree based on detected technologies:

```
REQUIRED for all projects:
├── checkout
├── dependency_installation
├── lint / code_quality
├── build
├── unit_test
├── SAST (Semgrep)
├── dependency_vulnerability_scan
└── secret_detection (Gitleaks)

CONDITIONAL stages:
├── integration_test              → if: multiple services or DB config detected
├── container_scan (Trivy)        → if: Dockerfile detected
├── container_build               → if: Dockerfile detected
├── iac_scan (Trivy)              → if: Terraform/K8s manifests detected
├── license_compliance            → if: package manager detected
├── sBOM_generation               → if: containerization detected
├── artifact_publish              → if: build produces artifacts
├── deploy                        → if: deployment config detected
├── performance_test              → if: web framework detected
└── e2e_test                      → if: frontend framework detected
```

### 6.2 Workflow Template System

The AI uses an LLM prompt engineered to generate workflows with:

- **Dynamic job construction** — Jobs are added/removed based on detected tech
- **Matrix builds** — Generated for multi-language or multi-version projects
- **Caching configuration** — npm, pip, go module caching based on detected package manager
- **Conditional execution** — `if:` conditions for deploy-only-on-main, skip-on-docs, etc.
- **Environment variables** — Inferred from `.env.example` if present
- **Service containers** — PostgreSQL, Redis, MySQL if database config detected
- **Artifact handling** — Upload scan results, test reports, build artifacts
- **Notification hooks** — Optional Slack/Discord/email integration points

### 6.3 Output Example (Abbreviated)

```yaml
name: AI DevSecOps Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  security-events: write
  pull-requests: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
        with:
          persist-credentials: false
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm run lint

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
        with:
          persist-credentials: false
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm test

  sast:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
      - uses: semgrep/semgrep-action@v1
        with:
          config: p/default

  dep-scan:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
      - uses: actions/dependency-review-action@v4

  secret-scan:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
      - uses: gitleaks/gitleaks-action@v2

  container-scan:
    if: github.ref == 'refs/heads/main'
    needs: [test, sast, dep-scan, secret-scan]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@aabbfeb2ce3c5e9e0b2e9b9a5b0e6e9e0b2e9b9a
      - run: docker build -t app:latest .
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: app:latest
          format: sarif
          output: trivy-results.sarif
          severity: CRITICAL,HIGH
```

---

## 7. Security Tool Integration

### 7.1 Supported Tools

| Tool | Category | Output Format | Purpose | Trigger |
|---|---|---|---|---|
| Semgrep | SAST | SARIF/JSON | Static code analysis for security bugs | Any source code |
| Trivy | Container/FS Scan | JSON/SARIF | Vulnerability scanning (filesystem + container) | Dockerfile or any project |
| Gitleaks | Secret Detection | JSON/CSV | Detect hardcoded secrets, API keys, tokens | Any repository |
| OWASP Dependency-Check | SCA | JSON/XML | Dependency vulnerability scanning | Package manager detected |

### 7.2 Tool Selection Logic

```
detect_tech_stack(repo) →
  if source_code:
    always_include("semgrep")
    always_include("gitleaks")

  if package_manager:
    always_include("dependency-check")

  if dockerfile:
    always_include("trivy-container")

  if terraform or kubernetes:
    always_include("trivy-iac")

  return selected_tools
```

### 7.3 Unified Finding Format

All scanner outputs are normalized into a standard format:

```json
{
  "tool": "semgrep",
  "rule_id": "typescript.react.security.audit.react-css-injection",
  "severity": "high",
  "file": "src/components/UserInput.tsx",
  "line": 42,
  "column": 18,
  "message": "User input is directly interpolated into CSS",
  "description": "Detected user-controlled data in CSS style...",
  "cwe": "CWE-79",
  "owasp": "A7:2017-XSS",
  "code_snippet": "style={{ color: userInput }}",
  "recommendation": "Sanitize user input before using in CSS..."
}
```

---

## 8. LangGraph Agent Architecture

### 8.1 Complete Agent Graph

```
┌──────────────────────────────────────────────────────────────────────────┐
│                AI DEVSEOPS PIPELINE ENGINEER — LANGGRAPH GRAPH            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐                                                   │
│  │  repository_connection_node  │ ◀── User connects GitHub repo           │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌─────────────────────┐                                                   │
│  │   repository_scan_node       │ ◀── Scan repo structure & contents      │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌─────────────────────┐                                                   │
│  │  technology_detection_node  │ ◀── Detect languages, frameworks, tools  │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌─────────────────────┐                                                   │
│  │ architecture_detection_node │ ◀── Detect monolith/microservices/etc    │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌──────────────────────────────┐                                          │
│  │ security_requirement_inference_node│ ◀── Infer required security       │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌─────────────────────┐                                                   │
│  │  workflow_generation_node   │ ◀── Generate GitHub Actions YAML         │
│  └──────────┬──────────┘                                                   │
│             ▼                                                             │
│  ┌─────────────────────┐                                                   │
│  │  workflow_validation_node   │ ◀── Validate YAML + security best prac   │
│  └──────────┬──────────┘                                                   │
│         ┌───┴───┐                                                         │
│         ▼       ▼                                                         │
│     [FAIL]   [PASS]                                                       │
│         │       │                                                         │
│         ▼       ▼                                                         │
│  ┌────────────┐ ┌─────────────────────┐                                   │
│  │ error_handler ││ github_branch_creation_node│── Create branch          │
│  └────────────┘ └──────────┬──────────┘                                   │
│                            ▼                                              │
│              ┌─────────────────────────┐                                  │
│              │  pull_request_creation_node │── Commit + Create PR          │
│              └──────────┬──────────┘                                      │
│                         ▼                                                │
│              ┌─────────────────────┐                                      │
│              │ workflow_execution_node  │── Trigger workflow               │
│              └──────────┬──────────┘                                      │
│                         ▼                                                │
│              ┌─────────────────────┐                                      │
│              │  execution_monitor_node   │── Poll status, stream logs      │
│              └──────────┬──────────┘                                      │
│                    ┌────┴────┐                                            │
│                    ▼         ▼                                            │
│              [COMPLETE]  [TIMEOUT]                                        │
│                    │         │                                            │
│                    ▼         ▼                                            │
│              ┌─────────────────────┐  ┌───────────┐                       │
│              │  security_analysis_node │  │ error_handler│                 │
│              └──────────┬──────────┘  └───────────┘                       │
│                         ▼                                                │
│              ┌─────────────────────┐                                      │
│              │   risk_assessment_node   │── Calculate risk scores          │
│              └──────────┬──────────┘                                      │
│                         ▼                                                │
│              ┌──────────────────────────┐                                 │
│              │ recommendation_generation_node│── Generate remediations     │
│              └──────────┬──────────┘                                      │
│                         ▼                                                │
│              ┌─────────────────────┐                                      │
│              │  response_formatter_node  │── Build final response          │
│              └──────────┬──────────┘                                      │
│                         ▼                                                │
│                    [DASHBOARD]                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 8.2 State Schema

```python
class PipelineEngineerState(TypedDict):
    # --- Phase I: Repository Intake ---
    request_type: str                           # "repository_pipeline"
    github_token: str                           # Encrypted GitHub token
    repository_url: str                         # Full GitHub repo URL
    repository_full_name: str                   # "owner/repo"
    repository_default_branch: str              # "main" or "master"

    # --- Phase I: Repository Analysis ---
    repository_structure: dict | None           # Fetched file tree
    repository_files: dict | None               # Key file contents
    detected_technologies: dict | None          # {language, framework, build_tool, ...}
    detected_architecture: str | None           # "monolith" | "microservices" | "frontend_backend"
    existing_workflows: list[str] | None        # Existing CI/CD configs

    # --- Phase II: Security Requirements ---
    inferred_security_needs: list[str]          # ["sast", "dep-scan", "secret-scan", ...]

    # --- Phase II: Pipeline Generation ---
    generated_workflow: str | None              # YAML string
    generated_stages: list[str]                 # ["lint", "test", "sast", ...]
    generation_explanation: str | None          # Human-readable explanation

    # --- Phase II: Validation ---
    validation_errors: list[str]
    validation_warnings: list[str]
    validation_passed: bool

    # --- Phase III: GitHub Deployment ---
    github_branch: str | None                   # Created branch name
    github_commit_sha: str | None               # Commit hash
    github_pr_number: int | None                # PR number
    github_pr_url: str | None                   # PR URL

    # --- Phase IV: Execution ---
    workflow_run_id: int | None                 # GitHub Actions run ID
    workflow_status: str | None                 # queued/running/success/failed/cancelled
    workflow_conclusion: str | None             # success/failure/cancelled
    workflow_logs: list[dict]                   # [{job, step, status, log}]
    workflow_duration_seconds: int | None

    # --- Phase V: Analysis ---
    scan_results: dict | None                   # Raw scanner outputs
    findings: list[dict]                        # Normalized security findings
    risk_score: float | None                    # 0-100
    security_posture: float | None              # 0-100
    compliance_score: float | None              # 0-100
    severity_breakdown: dict | None             # {critical: N, high: N, ...}

    # --- Phase V: Recommendations ---
    recommendations: list[dict]
    summary: str | None

    # --- Error Handling ---
    errors: list[str]
    error_stage: str | None
```

### 8.3 Node Implementations

```python
def repository_connection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Validate GitHub token and repository access."""
    token = state["github_token"]
    repo = state["repository_full_name"]
    try:
        gh_client = GitHubClient(token)
        repo_data = gh_client.get_repo(repo)
        state["repository_url"] = repo_data.html_url
        state["repository_default_branch"] = repo_data.default_branch
    except GitHubAuthError as e:
        state["errors"].append(f"GitHub connection failed: {str(e)}")
        state["error_stage"] = "connection"
    return state

def repository_scan_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Scan repository structure and read key files."""
    if state["errors"]:
        return state
    token = state["github_token"]
    repo = state["repository_full_name"]
    gh_client = GitHubClient(token)
    structure = gh_client.get_repo_contents(repo, "")
    key_files = {}
    for item in structure:
        if item["name"] in KEY_CONFIG_FILES:
            content = gh_client.get_file_content(repo, item["path"])
            key_files[item["name"]] = content
    workflows = gh_client.get_workflows(repo)
    state["repository_structure"] = structure
    state["repository_files"] = key_files
    state["existing_workflows"] = workflows
    return state

def technology_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Detect technology stack using LLM analysis of repo files."""
    if state["errors"]:
        return state
    files = state["repository_files"]
    structure = state["repository_structure"]
    prompt = TECHNOLOGY_DETECTION_PROMPT.format(
        files=json.dumps(files),
        structure=json.dumps(structure)
    )
    llm_response = llm.invoke(prompt)
    state["detected_technologies"] = json.loads(llm_response.content)
    return state

def architecture_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Detect application architecture from repo structure."""
    if state["errors"]:
        return state
    structure = state["repository_structure"]
    tech = state["detected_technologies"]
    prompt = ARCHITECTURE_DETECTION_PROMPT.format(
        structure=json.dumps(structure),
        technologies=json.dumps(tech)
    )
    llm_response = llm.invoke(prompt)
    state["detected_architecture"] = json.loads(llm_response.content)
    return state

def security_requirement_inference_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Infer security requirements based on detected tech and architecture."""
    if state["errors"]:
        return state
    tech = state["detected_technologies"]
    arch = state["detected_architecture"]
    prompt = SECURITY_INFERENCE_PROMPT.format(
        technologies=json.dumps(tech),
        architecture=json.dumps(arch)
    )
    llm_response = llm.invoke(prompt)
    state["inferred_security_needs"] = json.loads(llm_response.content)
    return state

def workflow_generation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Generate secure GitHub Actions workflow YAML."""
    if state["errors"]:
        return state
    tech = state["detected_technologies"]
    arch = state["detected_architecture"]
    security = state["inferred_security_needs"]
    prompt = WORKFLOW_GENERATION_PROMPT.format(
        technologies=json.dumps(tech),
        architecture=json.dumps(arch),
        security_needs=json.dumps(security)
    )
    llm_response = llm.invoke(prompt)
    state["generated_workflow"] = parse_yaml_from_llm(llm_response.content)
    state["generation_explanation"] = extract_explanation(llm_response.content)
    return state

def workflow_validation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Validate YAML syntax, GitHub schema, and security best practices."""
    if state["errors"]:
        return state
    yaml = state["generated_workflow"]
    validator = WorkflowValidator()
    result = validator.validate(yaml)
    state["validation_errors"] = result.errors
    state["validation_warnings"] = result.warnings
    state["validation_passed"] = result.valid
    return state

def github_branch_creation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Create a new branch from default branch."""
    if state["errors"]:
        return state
    if not state["validation_passed"]:
        state["errors"].append("Validation failed, cannot deploy")
        return state
    token = state["github_token"]
    repo = state["repository_full_name"]
    base_branch = state["repository_default_branch"]
    branch_name = f"ai-devsecops/generate-workflow-{int(time.time())}"
    gh_client = GitHubClient(token)
    sha = gh_client.get_branch_sha(repo, base_branch)
    gh_client.create_branch(repo, branch_name, sha)
    state["github_branch"] = branch_name
    return state

def pull_request_creation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Commit workflow file and create PR."""
    if state["errors"]:
        return state
    token = state["github_token"]
    repo = state["repository_full_name"]
    branch = state["github_branch"]
    yaml = state["generated_workflow"]
    tech = state["detected_technologies"]
    gh_client = GitHubClient(token)
    path = ".github/workflows/ci-cd.yml"
    commit_sha = gh_client.create_file(repo, path, yaml, branch, "Add AI-generated secure CI/CD pipeline")
    pr_title = f"[AI DevSecOps] Add secure CI/CD pipeline for {tech.get('primary', 'project')}"
    pr_body = build_pr_body(state)
    pr = gh_client.create_pr(repo, branch, state["repository_default_branch"], pr_title, pr_body)
    state["github_commit_sha"] = commit_sha
    state["github_pr_number"] = pr.number
    state["github_pr_url"] = pr.html_url
    return state

def workflow_execution_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Trigger workflow_dispatch or wait for PR merge."""
    if state["errors"]:
        return state
    token = state["github_token"]
    repo = state["repository_full_name"]
    gh_client = GitHubClient(token)
    workflow_id = ".github/workflows/ci-cd.yml"
    run_id = gh_client.trigger_workflow(repo, workflow_id, state["repository_default_branch"])
    state["workflow_run_id"] = run_id
    state["workflow_status"] = "queued"
    return state

def execution_monitor_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Monitor workflow execution in real-time."""
    if state["errors"]:
        return state
    token = state["github_token"]
    repo = state["repository_full_name"]
    run_id = state["workflow_run_id"]
    gh_client = GitHubClient(token)
    timeout = 1800
    start = time.time()
    while time.time() - start < timeout:
        run = gh_client.get_workflow_run(repo, run_id)
        state["workflow_status"] = run.status
        state["workflow_conclusion"] = run.conclusion
        state["workflow_logs"] = gh_client.get_job_logs(repo, run_id)
        if run.status in ("completed",):
            break
        time.sleep(5)
    if state["workflow_status"] != "completed":
        state["errors"].append("Workflow execution timed out after 30 minutes")
        state["error_stage"] = "execution"
    return state

def security_analysis_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Parse scanner outputs into unified findings."""
    if state["errors"]:
        return state
    logs = state["workflow_logs"]
    analyzer = SecurityAnalyzer()
    state["findings"] = analyzer.analyze(logs)
    state["scan_results"] = analyzer.raw_results
    return state

def risk_assessment_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Calculate risk, posture, and compliance scores."""
    if state["errors"]:
        return state
    findings = state["findings"]
    analyzer = RiskAnalyzer()
    result = analyzer.calculate(findings)
    state["risk_score"] = result.risk_score
    state["security_posture"] = result.security_posture
    state["compliance_score"] = result.compliance_score
    state["severity_breakdown"] = result.severity_breakdown
    return state

def recommendation_generation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Generate actionable recommendations per finding."""
    if state["errors"]:
        return state
    findings = state["findings"]
    tech = state["detected_technologies"]
    generator = RecommendationGenerator(llm)
    state["recommendations"] = generator.generate(findings, tech)
    return state

def response_formatter_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Format final response with summary and all results."""
    state["summary"] = build_summary(state)
    return state
```

### 8.4 Edge Routing

| From Node | Condition | Target |
|---|---|---|
| workflow_validation_node | `validation_passed == False` | error_handler_node |
| workflow_validation_node | `validation_passed == True` | github_branch_creation_node |
| execution_monitor_node | `workflow_status == "completed"` | security_analysis_node |
| execution_monitor_node | timeout exceeded | error_handler_node |
| Any node | `errors` is non-empty | response_formatter_node (with error info) |

---

## 9. System Architecture

### 9.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    React SPA (Vite)                              │ │
│  │  Dashboard │ Pipeline Generator │ Security Reports │ Settings   │ │
│  │  TanStack Query │ Recharts │ Tailwind CSS │ shadcn/ui           │ │
│  └──────────────────────────┬──────────────────────────────────────┘ │
└─────────────────────────────┼────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          PROXY LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                         Nginx                                    │ │
│  │  /api/* → Backend │ /ai/* → AI Service │ /* → Frontend          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────────┐   ┌───────────────┐
│  BACKEND API   │   │   AI SERVICE      │   │   FRONTEND    │
│  (Go/Fiber)    │   │  (FastAPI+LangGraph)│  │  (React+Vite) │
├───────────────┤   ├───────────────────┤   ├───────────────┤
│  Auth & RBAC   │   │  Agent Graph      │   │  Static SPA   │
│  CRUD APIs     │   │  LLM Orchestration│   │  Assets       │
│  Webhooks      │   │  Security Analysis│   │               │
│  File Storage  │   │  Risk Assessment  │   │               │
│  Health Checks │   │  Recommendation   │   │               │
└───────┬───────┘   └────────┬──────────┘   └───────────────┘
        │                    │
        └────────┬───────────┘
                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                   │
│  ┌─────────────────────┐  ┌──────────────────────────────────────┐   │
│  │     PostgreSQL 16    │  │          Redis 7                      │   │
│  │  ───────────────     │  │  ────────────────                     │   │
│  │  Users                │  │  Rate Limiting                       │   │
│  │  Projects             │  │  Session Cache                       │   │
│  │  Repositories         │  │  SSE Pub/Sub                        │   │
│  │  Pipeline Generations │  │  Workflow Status Cache               │   │
│  │  GitHub Deployments   │  └──────────────────────────────────────┘   │
│  │  Workflow Executions  │                                             │
│  │  Findings             │                                             │
│  │  Risk Assessments     │                                             │
│  │  Recommendations      │                                             │
│  │  Audit Logs           │                                             │
│  └─────────────────────┘                                             │
└──────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │  GitHub API  │  │   OpenAI    │  │  Anthropic  │  │  OpenRouter    │  │
│  │  (REST/v3)  │  │  (GPT-4o)   │  │  (Claude)   │  │  (Multi-LLM)   │  │
│  └────────────┘  └────────────┘  └────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.2 Component Responsibilities

| Component | Stack | Responsibility |
|---|---|---|
| **Frontend** | React 19, TypeScript, Vite, Tailwind, Recharts, TanStack Query, shadcn/ui | Dashboard, pipeline generation UI, security report visualization, real-time execution monitoring, settings |
| **Backend API** | Go (Fiber), GORM, go-redis, golang-jwt | Auth, RBAC, project/repo CRUD, GitHub webhook receiver, workflow state persistence, health checks |
| **AI Service** | Python, FastAPI, LangChain, LangGraph, SQLAlchemy, Uvicorn | Agent graph execution, LLM orchestration, repo analysis, workflow generation, security analysis, risk assessment, recommendation generation |
| **PostgreSQL** | 16 | All persistent data: users, projects, repos, generations, deployments, executions, findings, assessments, recommendations, audit logs |
| **Redis** | 7 | Caching, rate limiting, real-time pub/sub for SSE log streaming, session store |
| **Nginx** | Alpine | Reverse proxy, static asset serving, request routing |
| **LLM Providers** | OpenAI / Anthropic / OpenRouter | Technology detection, architecture analysis, YAML generation, security analysis, recommendation generation |

### 9.3 Container Architecture

```yaml
services:
  postgres:     # PostgreSQL 16 (data)
  redis:        # Redis 7 (cache + pub/sub)
  backend:      # Go Fiber API (CRUD + auth)
  ai-service:   # Python FastAPI + LangGraph (agent engine)
  frontend:     # React + Vite (dashboard SPA)
  nginx:        # Reverse proxy (routes /api, /ai, /)
```

---

## 10. Sequence Diagrams

### 10.1 Full 16-Step Workflow Sequence

```
User          Frontend         Backend            AI Service          GitHub           LLM
 │               │                │                    │                │              │
 │  Connect Repo │                │                    │                │              │
 │──────────────>│                │                    │                │              │
 │               │ POST /ai/repo/pipeline              │                │              │
 │               │─────────────────────────────────────>│                │              │
 │               │                │                    │                │              │
 │               │                │                    │ 1. Validate token              │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 2. Get repo structure          │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 3. Read key files              │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 4. LLM: Tech Detection         │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │                    │ 5. LLM: Architecture Detection │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │                    │ 6. LLM: Security Inference    │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │                    │ 7. LLM: Generate Workflow     │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │                    │ 8. Validate YAML              │
 │               │                │                    │ (internal)     │              │
 │               │                │                    │                │              │
 │               │                │                    │ 9. Create branch               │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 10. Commit workflow            │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 11. Create PR                 │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │  Return PR URL │                    │                │              │
 │               │<─────────────────────────────────────│                │              │
 │               │                │                    │                │              │
 │  Show PR Link │                │                    │                │              │
 │<──────────────│                │                    │                │              │
 │               │                │                    │                │              │
 │  User reviews PR on GitHub ──────────────────────────────────────────────────────>│
 │               │                │                    │                │              │
 │  User merges PR ──────────────────────────────────────────────────────────────>│
 │               │                │                    │                │              │
 │               │                │  GitHub webhook: workflow_run                    │
 │               │                │<───────────────────────────────────               │
 │               │                │                    │                │              │
 │               │                │  POST /ai/pipeline/execute                        │
 │               │                │─────────────────────>│                │            │
 │               │                │                    │                │              │
 │               │                │                    │ 12. Poll workflow status      │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │  (poll every 5s)              │
 │               │                │                    │                │              │
 │               │                │  SSE: status update                                │
 │               │<═══════════════│══════════════════════│                │            │
 │               │                │                    │                │              │
 │               │                │                    │ 13. Collect job logs          │
 │               │                │                    │────────────────>              │
 │               │                │                    │<────────────────               │
 │               │                │                    │                │              │
 │               │                │                    │ 14. LLM: Security Analysis    │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │                    │ 15. Calculate Risk Scores     │
 │               │                │                    │ (internal)     │              │
 │               │                │                    │                │              │
 │               │                │                    │ 16. Generate Recommendations  │
 │               │                │                    │───────────────────────────────>│
 │               │                │                    │<─────────────────────────────────│
 │               │                │                    │                │              │
 │               │                │  Save results      │                │              │
 │               │                │<─────────────────────│                │              │
 │               │                │                    │                │              │
 │  Show Report  │                │                    │                │              │
 │<──────────────│                │                    │                │              │
```

### 10.2 Repository Analysis Sequence (Detailed)

```
AI Service                       GitHub API                    LLM
    │                               │                          │
    │  GET /repos/{owner}/{repo}     │                          │
    │──────────────────────────────>│                          │
    │<──────────────────────────────│                          │
    │  { name, default_branch, ...} │                          │
    │                               │                          │
    │  GET /repos/.../contents/     │                          │
    │──────────────────────────────>│                          │
    │<──────────────────────────────│                          │
    │  [file tree entries]          │                          │
    │                               │                          │
    │  GET /repos/.../contents/package.json                    │
    │──────────────────────────────>│                          │
    │<──────────────────────────────│                          │
    │  GET /repos/.../contents/Dockerfile                     │
    │──────────────────────────────>│                          │
    │<──────────────────────────────│                          │
    │  GET /repos/.../contents/*.github/workflows/*           │
    │──────────────────────────────>│                          │
    │<──────────────────────────────│                          │
    │                               │                          │
    │  LLM: "Analyze this repo:    │                          │
    │  - Files: [package.json, ...] │                          │
    │  - Structure: [...]           │                          │
    │  - Dependencies: {...}"       │                          │
    │─────────────────────────────────────────────────────────>│
    │<─────────────────────────────────────────────────────────│
    │  { language: "TypeScript",                               │
    │    framework: "React+Express",                           │
    │    build: "Vite",                                        │
    │    test: "Vitest",                                       │
    │    docker: true,                                         │
    │    architecture: "frontend_backend" }                    │
    │                               │                          │
```

### 10.3 Security Analysis Sequence (Detailed)

```
AI Service                         LLM                     Storage
    │                               │                         │
    │  Raw scanner outputs:         │                         │
    │  - Semgrep SARIF             │                         │
    │  - Trivy JSON                │                         │
    │  - Gitleaks JSON             │                         │
    │  - OWASP DC JSON             │                         │
    │                               │                         │
    │  Parse and normalize          │                         │
    │  └─ Extract findings           │                         │
    │                               │                         │
    │  LLM: "For each finding:     │                         │
    │  - Classify CWE/OWASP        │                         │
    │  - Determine severity        │                         │
    │  - Generate remediation      │                         │
    │  - Suggest code fix"         │                         │
    │───────────────────────────────>                         │
    │<───────────────────────────────                         │
    │                               │                         │
    │  Calculate risk scores        │                         │
    │  └─ Per-finding severity      │                         │
    │  └─ Aggregate risk (0-100)    │                         │
    │  └─ Security posture (0-100)  │                         │
    │  └─ Compliance score (0-100)  │                         │
    │                               │                         │
    │  Save:                        │                         │
    │  - findings[]                 │                         │
    │  - risk_assessment            │                         │
    │  - compliance_mappings[]      │                         │
    │  - recommendations[]          │                         │
    │────────────────────────────────────────────────────────>│
    │                               │                         │
```

---

## 11. API Specifications

### 11.1 AI Service Endpoints (FastAPI)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| `GET` | `/api/health` | Health check | — | `{ status: "ok", version: "2.0" }` |
| `POST` | `/api/repo/pipeline` | Full pipeline for a repo | `RepoPipelineRequest` | `PipelineResponse` |
| `POST` | `/api/repo/analyze` | Analyze repo only (no generation) | `RepoAnalyzeRequest` | `AnalyzeResponse` |
| `POST` | `/api/pipeline/generate` | Generate from detected tech | `GenerateRequest` | `GeneratedWorkflow` |
| `POST` | `/api/pipeline/validate` | Validate workflow YAML | `ValidateRequest` | `ValidationResponse` |
| `POST` | `/api/pipeline/deploy` | Create branch + commit + PR | `DeployRequest` | `DeployResponse` |
| `POST` | `/api/pipeline/execute` | Trigger workflow run | `ExecuteRequest` | `ExecutionResponse` |
| `GET` | `/api/pipeline/status/{run_id}` | Get workflow execution status | — | `ExecutionStatus` |
| `GET` | `/api/pipeline/status/{run_id}/stream` | SSE stream for live status | — | SSE events |
| `GET` | `/api/pipeline/logs/{run_id}` | Get execution logs | — | `LogResponse` |
| `POST` | `/api/pipeline/analyze/{run_id}` | Analyze completed execution | — | `SecurityReport` |
| `GET` | `/api/pipeline/history/{project_id}` | List pipeline history | — | `PipelineHistory[]` |
| `POST` | `/api/review-pr` | Review a specific PR | `ReviewPRRequest` | `SecurityReport` |

### 11.2 Backend API Endpoints (Go Fiber)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | No | Register user |
| `POST` | `/api/v1/auth/login` | No | Login |
| `POST` | `/api/v1/auth/refresh` | No | Refresh JWT |
| `GET` | `/api/v1/me` | Yes | Current user |
| `GET` | `/api/v1/dashboard/stats` | Yes | Dashboard aggregate stats |
| `GET` | `/api/v1/projects` | Yes | List user projects |
| `POST` | `/api/v1/projects` | Yes | Create project |
| `DELETE` | `/api/v1/projects/:id` | Yes | Delete project |
| `POST` | `/api/v1/repositories/connect` | Yes | Connect GitHub repo |
| `GET` | `/api/v1/repositories/:id` | Yes | Get repo details |
| `DELETE` | `/api/v1/repositories/:id` | Yes | Disconnect repo |
| `GET` | `/api/v1/repositories/:repoId/pipelines` | Yes | List pipeline runs |
| `GET` | `/api/v1/pipelines/:id` | Yes | Get pipeline detail |
| `GET` | `/api/v1/pipelines/:id/report` | Yes | Get security report |
| `POST` | `/api/v1/webhooks/github` | No* | GitHub webhook receiver |

### 11.3 Key Request/Response Schemas

```python
# --- Repo Pipeline Request (Main Entry Point) ---
class RepoPipelineRequest(BaseModel):
    repository_full_name: str       # "owner/repo"
    github_token: str               # User's GitHub PAT
    project_id: str                 # Backend project UUID
    auto_deploy: bool = False       # Auto-create PR (default: require confirmation)

# --- Repo Analysis ---
class RepoAnalyzeRequest(BaseModel):
    repository_full_name: str
    github_token: str

class AnalyzeResponse(BaseModel):
    repository: RepositoryInfo
    technologies: TechnologyProfile
    architecture: ArchitectureProfile
    existing_ci_cd: list[WorkflowInfo]
    inferred_security_needs: list[str]

# --- Technology Profile ---
class TechnologyProfile(BaseModel):
    primary_language: str
    secondary_languages: list[str]
    frameworks: list[str]
    build_tools: list[str]
    test_frameworks: list[str]
    package_manager: str | None
    containerization: ContainerizationInfo
    databases: list[str]
    has_dockerfile: bool
    has_docker_compose: bool
    has_kubernetes_manifests: bool
    has_terraform: bool

# --- Architecture Profile ---
class ArchitectureProfile(BaseModel):
    architecture_type: str                  # monolithic | frontend_backend | microservices
    service_count: int | None
    has_api_gateway: bool
    has_message_queue: bool
    has_database: bool
    is_serverless: bool
    explanation: str

# --- Pipeline Generation ---
class GenerateRequest(BaseModel):
    technologies: TechnologyProfile
    architecture: ArchitectureProfile
    security_needs: list[str]
    repository_default_branch: str

class GeneratedWorkflow(BaseModel):
    workflow_yaml: str
    stages: list[str]
    explanation: str
    warnings: list[str]

# --- Validation ---
class ValidationResponse(BaseModel):
    valid: bool
    syntax_ok: bool
    actions_pinned: bool
    permissions_minimal: bool
    concurrency_configured: bool
    missing_security_stages: list[str]
    issues: list[ValidationIssue]
    errors: list[str]
    warnings: list[str]

class ValidationIssue(BaseModel):
    type: str                               # "unpinned_action" | "excessive_permissions" | ...
    severity: str                           # error | warning | info
    line: int | None
    message: str
    recommendation: str

# --- Deployment ---
class DeployRequest(BaseModel):
    repository_full_name: str
    github_token: str
    workflow_yaml: str
    workflow_filename: str = "ci-cd.yml"
    default_branch: str = "main"
    branch_prefix: str = "ai-devsecops"
    commit_message: str | None
    pr_title: str | None
    pr_body: str | None

class DeployResponse(BaseModel):
    branch: str
    commit_sha: str
    pr_number: int
    pr_url: str
    success: bool

# --- Pipeline Response (Complete) ---
class PipelineResponse(BaseModel):
    pipeline_id: str
    repository: str
    technologies: TechnologyProfile
    architecture: ArchitectureProfile
    generated_workflow: GeneratedWorkflow
    validation: ValidationResponse
    deployment: DeployResponse | None
    execution: ExecutionStatus | None
    security_report: SecurityReport | None
    status: str                             # analysis_complete | generated | validated | deployed | executed | analyzed
    errors: list[str]

# --- Execution ---
class ExecutionStatus(BaseModel):
    run_id: int
    workflow_name: str
    status: str                             # pending | queued | running | completed
    conclusion: str | None                  # success | failure | cancelled | null
    html_url: str
    jobs: list[JobStatus]
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None

class JobStatus(BaseModel):
    id: int
    name: str
    status: str                             # queued | in_progress | completed | waiting
    conclusion: str | None
    started_at: datetime | None
    completed_at: datetime | None
    steps: list[StepStatus]

class StepStatus(BaseModel):
    name: str
    status: str
    conclusion: str | None
    number: int
    started_at: datetime | None
    completed_at: datetime | None

# --- Security Report ---
class SecurityReport(BaseModel):
    pipeline_id: str
    execution_id: str
    summary: str
    risk_score: float
    risk_level: str                         # critical | high | medium | low
    security_posture: float
    compliance_score: float | None
    severity_breakdown: SeverityBreakdown
    compliance_mappings: list[ComplianceMapping]
    findings: list[SecurityFinding]
    recommendations: list[Recommendation]

class SeverityBreakdown(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total: int

class SecurityFinding(BaseModel):
    id: str
    type: str
    severity: str
    scanner: str | None
    title: str
    file: str | None
    line: int | None
    code_snippet: str | None
    package_name: str | None
    installed_version: str | None
    fixed_version: str | None
    cve: str | None
    cwe: str | None
    owasp: str | None
    description: str
    impact: str
    remediation: str

class ComplianceMapping(BaseModel):
    framework: str                          # OWASP_ASVS | CIS | SOC2
    control_id: str
    control_name: str
    status: str                             # passed | failed | not_applicable

class Recommendation(BaseModel):
    id: str
    finding_id: str | None
    category: str                           # "security_fix" | "workflow_improvement" | "compliance" | "best_practice"
    priority: str                           # critical | high | medium | low
    title: str
    description: str
    impact: str
    remediation: str
    example_before: str | None
    example_after: str | None
```

---

## 12. Database Schema

```sql
-- ==============================
-- Core Tables
-- ==============================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255),
    github_username VARCHAR(255),
    github_token    TEXT,                    -- AES-256-GCM encrypted at rest
    role            VARCHAR(50) DEFAULT 'user',  -- admin | user
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE repositories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    github_id       BIGINT NOT NULL,
    full_name       VARCHAR(255) NOT NULL,   -- "owner/repo"
    default_branch  VARCHAR(100) DEFAULT 'main',
    is_connected    BOOLEAN DEFAULT TRUE,
    last_scanned_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Repository Analysis
-- ==============================

CREATE TABLE repository_analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id       UUID REFERENCES repositories(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(50) DEFAULT 'pending', -- pending | scanning | completed | failed
    detected_language   VARCHAR(100),
    detected_frameworks JSONB,               -- ["React", "Express"]
    detected_build_tools JSONB,              -- ["Vite", "tsc"]
    detected_test_frameworks JSONB,          -- ["Vitest"]
    detected_architecture VARCHAR(100),       -- monolithic | frontend_backend | microservices
    has_dockerfile      BOOLEAN DEFAULT FALSE,
    has_docker_compose  BOOLEAN DEFAULT FALSE,
    has_kubernetes      BOOLEAN DEFAULT FALSE,
    has_terraform       BOOLEAN DEFAULT FALSE,
    has_existing_ci_cd  BOOLEAN DEFAULT FALSE,
    existing_workflows  JSONB,               -- [{path, name, content}]
    raw_scan_data       JSONB,               -- Full analysis output from agent
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Pipeline Generation
-- ==============================

CREATE TABLE pipeline_generations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES projects(id) ON DELETE CASCADE,
    repository_id       UUID REFERENCES repositories(id) ON DELETE CASCADE,
    analysis_id         UUID REFERENCES repository_analyses(id) ON DELETE SET NULL,
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    generated_yaml      TEXT,
    stages              JSONB,               -- ["lint", "test", "sast", ...]
    generation_explanation TEXT,             -- Human-readable explanation
    status              VARCHAR(50) DEFAULT 'draft', -- draft | validated | deployed | executed | analyzed | failed
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pipeline_validations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id       UUID REFERENCES pipeline_generations(id) ON DELETE CASCADE,
    valid               BOOLEAN NOT NULL,
    syntax_ok           BOOLEAN NOT NULL,
    actions_pinned      BOOLEAN NOT NULL,
    permissions_minimal BOOLEAN NOT NULL,
    concurrency_configured BOOLEAN NOT NULL,
    missing_stages      JSONB,
    issues              JSONB,               -- [{type, severity, line, message, recommendation}]
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- GitHub Integration
-- ==============================

CREATE TABLE github_deployments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id   UUID REFERENCES pipeline_generations(id) ON DELETE CASCADE,
    branch_name     VARCHAR(255),
    commit_sha      VARCHAR(64),
    commit_message  TEXT,
    pr_number       INTEGER,
    pr_title        TEXT,
    pr_body         TEXT,
    pr_url          TEXT,
    pr_state        VARCHAR(50) DEFAULT 'open',   -- open | merged | closed
    status          VARCHAR(50) DEFAULT 'pending', -- pending | success | failed
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Workflow Execution
-- ==============================

CREATE TABLE workflow_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id   UUID REFERENCES pipeline_generations(id) ON DELETE CASCADE,
    deployment_id   UUID REFERENCES github_deployments(id) ON DELETE SET NULL,
    github_run_id   BIGINT,
    workflow_name   VARCHAR(255),
    status          VARCHAR(50) DEFAULT 'pending', -- pending | queued | running | completed
    conclusion      VARCHAR(50),                   -- success | failure | cancelled | null
    html_url        TEXT,
    jobs            JSONB,                         -- [{id, name, status, conclusion, steps}]
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_seconds INTEGER,
    raw_logs        TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Security Analysis
-- ==============================

CREATE TABLE findings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id    UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    scanner         VARCHAR(50),             -- semgrep | trivy | gitleaks | dep-check
    title           VARCHAR(500),
    finding_type    VARCHAR(100),
    severity        VARCHAR(20) NOT NULL,    -- critical | high | medium | low
    file            VARCHAR(500),
    line            INTEGER,
    code_snippet    TEXT,
    package_name    VARCHAR(255),
    installed_version VARCHAR(100),
    fixed_version   VARCHAR(100),
    cve             VARCHAR(50),
    cwe             VARCHAR(50),
    owasp           VARCHAR(100),
    description     TEXT,
    impact          TEXT,
    remediation     TEXT,
    raw_data        JSONB,                   -- Original scanner output for this finding
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_findings_execution ON findings(execution_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_scanner ON findings(scanner);

CREATE TABLE risk_assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id        UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    risk_score          DECIMAL(5,2),        -- 0-100
    risk_level          VARCHAR(20),         -- critical | high | medium | low
    security_posture    DECIMAL(5,2),        -- 0-100
    compliance_score    DECIMAL(5,2),        -- 0-100
    severity_breakdown  JSONB,              -- {critical: 2, high: 5, medium: 3, low: 10}
    total_findings      INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE compliance_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id    UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    framework       VARCHAR(100),            -- OWASP_ASVS | CIS | SOC2
    control_id      VARCHAR(100),
    control_name    VARCHAR(500),
    status          VARCHAR(50),             -- passed | failed | not_applicable
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id    UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    finding_id      UUID REFERENCES findings(id) ON DELETE SET NULL,
    category        VARCHAR(100),            -- security_fix | workflow_improvement | compliance | best_practice
    priority        VARCHAR(20),             -- critical | high | medium | low
    title           VARCHAR(255),
    description     TEXT,
    impact          TEXT,
    remediation     TEXT,
    example_before  TEXT,
    example_after   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================
-- Audit Trail
-- ==============================

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100),            -- repo_connected | repo_analyzed | pipeline_generated | workflow_deployed | pr_created | workflow_executed | report_generated
    resource_type   VARCHAR(100),            -- repository | pipeline | deployment | execution
    resource_id     UUID,
    metadata        JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);

-- ==============================
-- Materialized Views for Dashboard
-- ==============================

CREATE MATERIALIZED VIEW dashboard_project_stats AS
SELECT
    p.id AS project_id,
    p.name AS project_name,
    COUNT(DISTINCT ra.id) AS total_analyses,
    COUNT(DISTINCT pg.id) AS total_pipelines,
    COUNT(DISTINCT we.id) AS total_executions,
    COUNT(DISTINCT f.id) AS total_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'critical' THEN f.id END) AS critical_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'high' THEN f.id END) AS high_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'medium' THEN f.id END) AS medium_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'low' THEN f.id END) AS low_findings,
    AVG(ra2.risk_score) AS avg_risk_score,
    AVG(ra2.security_posture) AS avg_security_posture,
    AVG(ra2.compliance_score) AS avg_compliance_score,
    MAX(we.created_at) AS last_execution
FROM projects p
LEFT JOIN repositories r ON r.project_id = p.id
LEFT JOIN repository_analyses ra ON ra.repository_id = r.id
LEFT JOIN pipeline_generations pg ON pg.repository_id = r.id
LEFT JOIN workflow_executions we ON we.generation_id = pg.id
LEFT JOIN findings f ON f.execution_id = we.id
LEFT JOIN risk_assessments ra2 ON ra2.execution_id = we.id
GROUP BY p.id, p.name;

CREATE MATERIALIZED VIEW dashboard_recent_activity AS
SELECT
    'analysis' AS activity_type,
    ra.id AS resource_id,
    ra.status AS status,
    r.full_name AS repository_name,
    ra.created_at
FROM repository_analyses ra
JOIN repositories r ON r.id = ra.repository_id
UNION ALL
SELECT
    'pipeline' AS activity_type,
    pg.id AS resource_id,
    pg.status AS status,
    r.full_name AS repository_name,
    pg.created_at
FROM pipeline_generations pg
JOIN repositories r ON r.id = pg.repository_id
UNION ALL
SELECT
    'execution' AS activity_type,
    we.id AS resource_id,
    we.conclusion AS status,
    r.full_name AS repository_name,
    we.created_at
FROM workflow_executions we
JOIN pipeline_generations pg ON pg.id = we.generation_id
JOIN repositories r ON r.id = pg.repository_id
ORDER BY created_at DESC
LIMIT 50;
```

---

## 13. GitHub Integration Design

### 13.1 Authentication

- **GitHub OAuth App** for user authentication
- **Fine-Grained Personal Access Tokens** for repository operations
- Token scopes required: `repo` (private repos), `workflows`, `pull_requests`, `contents`
- Tokens encrypted at rest using AES-256-GCM in PostgreSQL
- Token validation on connection (check scope + repository access)

### 13.2 API Operations Matrix

| Operation | GitHub API | Endpoint | Used By |
|---|---|---|---|
| Get repo info | `GET /repos/{owner}/{repo}` | REST | repository_connection_node |
| Get repo contents | `GET /repos/{owner}/{repo}/contents/{path}` | REST | repository_scan_node |
| Get file content | `GET /repos/{owner}/{repo}/contents/{path}` | REST | repository_scan_node |
| List workflows | `GET /repos/{owner}/{repo}/actions/workflows` | REST | repository_scan_node |
| Get workflow file | `GET /repos/{owner}/{repo}/contents/{path}` | REST | repository_scan_node |
| Get branch SHA | `GET /repos/{owner}/{repo}/git/refs/heads/{branch}` | REST | github_branch_creation_node |
| Create branch | `POST /repos/{owner}/{repo}/git/refs` | REST | github_branch_creation_node |
| Create file | `PUT /repos/{owner}/{repo}/contents/{path}` | REST | pull_request_creation_node |
| Create PR | `POST /repos/{owner}/{repo}/pulls` | REST | pull_request_creation_node |
| Trigger workflow | `POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches` | REST | workflow_execution_node |
| Get workflow run | `GET /repos/{owner}/{repo}/actions/runs/{run_id}` | REST | execution_monitor_node |
| List jobs | `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | REST | execution_monitor_node |
| Download logs | `GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs` | REST | execution_monitor_node |
| List PR files | `GET /repos/{owner}/{repo}/pulls/{number}/files` | REST | security_analysis_node |

### 13.3 Branch Strategy

```
main
  └── ai-devsecops/analyze-{timestamp}           (analysis-only branch, optional)
  └── ai-devsecops/generate-workflow-{timestamp}  (pipeline generation branch)
        └── .github/workflows/ci-cd.yml            (committed workflow file)
              └── Pull Request → main               (user reviews & merges)
```

### 13.4 PR Template

```markdown
## 🤖 AI DevSecOps: Automated Pipeline Generation

### Repository Analysis
**Detected Technologies:**
| Category | Detected |
|---|---|
| Language | {primary_language} |
| Frameworks | {frameworks} |
| Build Tools | {build_tools} |
| Test Framework | {test_frameworks} |
| Architecture | {architecture} |
| Containerization | {containerization} |

### Pipeline Stages
| Stage | Tool | Purpose |
|---|---|---|
{stages_table}

### Security Controls Applied
- ✅ All actions pinned to commit SHA
- ✅ Minimal GITHUB_TOKEN permissions (read-only)
- ✅ Concurrency groups configured
- ✅ `persist-credentials: false` on checkout
- ✅ `if:` conditions on deploy/publish jobs
- ✅ Security scans gating deployment
- ✅ {additional_security_controls}

### Inferred Security Requirements
Based on your project's technology stack, the following security controls were automatically included:
{security_controls_list}

### Next Steps
1. Review the generated workflow file
2. Merge this Pull Request
3. GitHub Actions will automatically execute the pipeline on future pushes
4. Return to the dashboard to monitor execution and review security findings

---

_This PR was automatically generated by AI DevSecOps Pipeline Engineer._
```

---

## 14. Security Architecture

### 14.1 Credential Management

| Credential | Storage | Encryption | Access |
|---|---|---|---|
| GitHub Tokens | PostgreSQL `users.github_token` | AES-256-GCM at rest | Backend encrypts/decrypts |
| LLM API Keys | Environment variables (`.env`) | None (file system restricted) | AI Service reads at startup |
| JWT Signing Secret | Environment variable | None (file system restricted) | Backend signs/verifies |
| Database Password | Environment variable / Docker secrets | None (network isolated) | Backend + AI Service |
| Redis Password | Environment variable | None (network isolated) | Backend + AI Service |

### 14.2 Encryption Implementation

```python
# AES-256-GCM for GitHub tokens at rest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_token(token: str, key: bytes) -> str:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, token.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def decrypt_token(encrypted: str, key: bytes) -> str:
    data = base64.b64decode(encrypted)
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()
```

### 14.3 Authentication & Authorization Flow

```
User → Login (email + password)
  → Backend validates credentials
  → Returns JWT (access_token: 15m, refresh_token: 7d)
  → Frontend stores in HttpOnly cookie or memory
  → Every API request includes Authorization: Bearer <token>
  → Backend validates JWT on every request
  → AI Service validates JWT for internal calls
  → RBAC: admin | user roles
```

### 14.4 RBAC Matrix

| Resource | Admin | User |
|---|---|---|
| View all projects | Yes | Own only |
| Connect repositories | Yes | Yes |
| Run pipeline analysis | Yes | Yes |
| Deploy workflows to GitHub | Yes | Yes |
| Delete projects | Yes | No |
| Delete pipelines | Yes | No |
| Manage users | Yes | No |
| View audit logs | Yes | No |
| Configure LLM providers | Yes | No |
| System settings | Yes | No |

### 14.5 Human Approval Gate

```
Workflow Generated → Validated → Branch Created → Commit → PR Created
                                                              ↓
                                              ╔══════════════════════════════╗
                                              ║  WAITING FOR HUMAN REVIEW     ║
                                              ║  PR is open, not auto-merged ║
                                              ╚══════════════════════════════╝
                                                              ↓
                                              User reviews PR on GitHub
                                                              ↓
                                              User merges PR → Workflow triggers
                                                              ↓
                                              AI monitors execution
```

The agent **never** auto-merges. It creates the PR and waits for human approval.

### 14.6 Audit Trail

Every significant action is logged:

| Action | Event |
|---|---|
| `repo_connected` | User connected a GitHub repository |
| `repo_analyzed` | AI completed repository analysis |
| `pipeline_generated` | AI generated a workflow |
| `pipeline_validated` | Workflow passed/failed validation |
| `branch_created` | AI created a new branch |
| `workflow_committed` | AI committed workflow file |
| `pr_created` | AI created a Pull Request |
| `workflow_executed` | GitHub Actions workflow triggered |
| `execution_completed` | Workflow finished (success/failure) |
| `analysis_completed` | AI completed security analysis |
| `report_generated` | Security report was generated |

```json
{
  "user_id": "uuid",
  "action": "pr_created",
  "resource_type": "github_deployment",
  "resource_id": "uuid",
  "metadata": {
    "repo": "my-org/my-app",
    "branch": "ai-devsecops/generate-workflow-1712345678",
    "pr_number": 42,
    "pr_url": "https://github.com/my-org/my-app/pull/42"
  },
  "ip_address": "10.0.0.1",
  "created_at": "2026-06-05T12:00:00Z"
}
```

### 14.7 Security Best Practices for Generated Workflows

Every generated workflow enforces:

| Practice | Implementation |
|---|---|
| Action pinning | Replace `actions/checkout@v3` → `actions/checkout@aabbfeb2ce3c5e9e` |
| Minimal permissions | `permissions: contents: read, security-events: write` |
| Concurrency | `concurrency: group: ${{ github.workflow }}-${{ github.ref }}` |
| Credential hygiene | `persist-credentials: false` on checkout |
| Deploy gating | `if: github.ref == 'refs/heads/main'` on deploy jobs |
| Step timeouts | `timeout-minutes: 10` on long-running steps |
| Fail-fast | `fail-fast: true` on matrix builds |
| Cache dependencies | `actions/cache` or `setup-*` built-in caching |
| Artifact retention | `actions/upload-artifact` with retention-days |

---

## 15. Dashboard Design

### 15.1 Page Structure

```
Dashboard
├── Overview (landing page)
│   ├── Welcome header with quick actions
│   ├── Stats Row (4 cards)
│   │   ├── Connected Repositories
│   │   ├── Pipelines Generated
│   │   ├── Security Findings
│   │   └── Avg Risk Score
│   ├── Security Trend Chart (stacked bar: findings/severity over time)
│   ├── Recent Activity Feed (chronological event list)
│   └── Quick Actions
│       ├── "Connect Repository" button
│       ├── "Run Pipeline Analysis" button
│       └── "View Security Report" button
│
├── Repositories
│   ├── Repository List
│   │   ├── Table: Name | Language | Pipeline Status | Last Analysis | Risk Score
│   │   └── Actions: Analyze | View Pipelines | Disconnect
│   └── Repository Detail
│       ├── Repository Info (name, url, default branch, languages)
│       ├── Detection Results
│       │   ├── Technology Stack badges
│       │   ├── Architecture badge
│       │   └── Security Requirements tags
│       ├── "Generate Pipeline" button
│       └── Pipeline History table
│
├── Pipeline Detail
│   ├── Pipeline Status Banner (badge: Draft | Validated | Deployed | Executed | Analyzed)
│   ├── Tab: Generated Workflow
│   │   ├── YAML Viewer (syntax-highlighted, line numbers)
│   │   ├── Stage Overview (horizontal flow diagram)
│   │   └── Explanation Panel (why each stage was selected)
│   ├── Tab: Validation Results
│   │   ├── Pass/Fail status per check
│   │   ├── Issues list (file, line, severity, message)
│   │   └── "Deploy to GitHub" button (if validation passed)
│   └── Tab: Deployment
│       ├── Branch name
│       ├── Commit SHA
│       ├── PR link (opens GitHub)
│       └── PR Status (open/merged/closed)
│
├── Execution
│   ├── Execution Status (real-time badge)
│   ├── Timeline (Gantt chart: jobs/steps over time)
│   ├── Job details (expandable per job)
│   └── Live Log Viewer (SSE-backed, auto-scroll)
│
├── Security Report
│   ├── Score Overview
│   │   ├── Risk Score Gauge (0-100 radial, color-coded)
│   │   ├── Security Posture Gauge
│   │   └── Compliance Scorecard
│   ├── Severity Distribution (pie/bar chart)
│   ├── Findings Table (sortable, filterable)
│   │   ├── Columns: Severity | Scanner | Title | File | CVE | Action
│   │   └── Row expansion: Description, Impact, Remediation
│   ├── Compliance Section
│   │   ├── Framework selector (OWASP/CIS/SOC2)
│   │   ├── Control check/uncheck list
│   │   └── Coverage percentage
│   └── Recommendations List
│       ├── Priority badge
│       ├── Title and description
│       ├── Impact statement
│       └── Code example (before/after)
│
├── History
│   ├── Filters: Project, Repository, Date range, Status
│   ├── Table: Date | Repo | Status | Risk Score | Findings
│   └── Click to view pipeline detail
│
└── Settings
    ├── GitHub Connection
    │   ├── Connected accounts
    │   ├── Manage tokens
    │   └── Disconnect
    ├── LLM Provider Config
    │   ├── Provider selector (OpenAI/Anthropic/OpenRouter)
    │   ├── API Key input
    │   └── Model selector
    ├── API Tokens
    └── User Preferences
```

### 15.2 Key UI Components

| Component | Location | Description |
|---|---|---|
| `StatsCard` | Overview | Metric display card with icon, value, label, trend arrow |
| `RiskScoreGauge` | Security Report, Overview | Radial gauge (0-100) with color coding (green/yellow/orange/red) |
| `VulnerabilityChart` | Overview, Security Report | Stacked bar chart (severity over time) using Recharts |
| `SeverityPieChart` | Security Report | Pie/Donut chart showing severity distribution |
| `WorkflowTimeline` | Pipeline Detail, Execution | Gantt-style horizontal bar chart of jobs/steps |
| `LiveLogViewer` | Execution | SSE-backed real-time log streaming with auto-scroll and search |
| `YAMLViewer` | Pipeline Detail | Syntax-highlighted YAML viewer with line numbers using Monaco/CodeMirror |
| `FindingsTable` | Security Report | Sortable, filterable, expandable table with severity badges |
| `ComplianceScorecard` | Security Report | Control checklist with pass/fail/na status per framework |
| `TechnologiesBadge` | Repository Detail | Badges for detected languages, frameworks, tools |
| `StageFlow` | Pipeline Detail | Horizontal connected-node flow diagram of pipeline stages |
| `ActivityFeed` | Overview | Chronological list of recent system events with timestamps |
| `QuickActions` | Overview | Shortcut cards to common operations |
| `PRLinkCard` | Pipeline Detail | Card with PR link, status badge, branch name, commit SHA |

### 15.3 Real-Time Updates

```
ExecutionMonitor component:
  → SSE endpoint: GET /ai/pipeline/status/{run_id}/stream
  → Events:
      event: status
      data: { status: "running", conclusion: null }

      event: job_update
      data: { job_id: 1, name: "test", status: "in_progress" }

      event: step_complete
      data: { job_id: 1, step: 2, name: "Run tests", conclusion: "success" }

      event: log
      data: { job_id: 1, step: 2, text: "PASS tests/index.test.ts" }

      event: completed
      data: { status: "completed", conclusion: "success", duration: 142 }
  → Reconnect on disconnect with Last-Event-ID
```

---

## 16. Frontend Component Tree

```
App
├── AuthProvider (JWT context + refresh logic)
├── QueryClientProvider (TanStack Query)
├── RouterProvider (React Router v6)
│   ├── PublicRoutes
│   │   ├── LoginPage
│   │   │   ├── LoginForm (email + password)
│   │   │   └── GitHubOAuthButton
│   │   └── RegisterPage
│   │       └── RegisterForm
│   │
│   └── ProtectedRoutes (AuthGuard)
│       ├── Layout
│       │   ├── Sidebar
│       │   │   ├── Logo
│       │   │   ├── NavLinks: Overview, Repositories, History, Settings
│       │   │   └── UserMenu (avatar, name, logout)
│       │   ├── TopBar
│       │   │   ├── Breadcrumbs
│       │   │   ├── SearchBar
│       │   │   └── NotificationBell
│       │   └── MainContent
│       │
│       ├── OverviewPage
│       │   ├── WelcomeHeader
│       │   ├── StatsRow
│       │   │   ├── StatsCard (Repos)
│       │   │   ├── StatsCard (Pipelines)
│       │   │   ├── StatsCard (Findings)
│       │   │   └── StatsCard (Risk Score)
│       │   ├── SecurityTrendChart (Recharts BarChart)
│       │   ├── RecentActivityFeed
│       │   │   └── ActivityItem (icon, text, timestamp)
│       │   └── QuickActions
│       │       ├── QuickActionCard (Connect Repo)
│       │       ├── QuickActionCard (New Pipeline)
│       │       └── QuickActionCard (View Reports)
│       │
│       ├── RepositoriesPage
│       │   ├── RepoListHeader (title, connect button)
│       │   ├── RepoTable
│       │   │   ├── Columns: Name, Language, Pipeline, Last Analysis, Risk, Actions
│       │   │   └── RepoRow
│       │   │       ├── RepoNameCell (name, url icon)
│       │   │       ├── LanguageBadge
│       │   │       ├── PipelineStatusBadge
│       │   │       └── ActionButtons (Analyze, View, Disconnect)
│       │   └── ConnectRepoModal
│       │       ├── RepoUrlInput
│       │       ├── TokenInput
│       │       └── ConnectButton
│       │
│       ├── RepoDetailPage
│       │   ├── RepoHeader (name, url, default branch)
│       │   ├── DetectionSection
│       │   │   ├── TechnologiesBadgeGroup
│       │   │   │   ├── LanguageBadge
│       │   │   │   ├── FrameworkBadge
│       │   │   │   ├── BuildToolBadge
│       │   │   │   └── TestFrameworkBadge
│       │   │   ├── ArchitectureBadge
│       │   │   ├── ContainerizationBadges
│       │   │   └── SecurityRequirementsTags
│       │   ├── GeneratePipelineButton
│       │   └── PipelineHistoryTable
│       │       └── PipelineHistoryRow (date, status, stages, actions)
│       │
│       ├── PipelineDetailPage
│       │   ├── PipelineStatusBanner
│       │   ├── Tabs
│       │   │   ├── Tab: Workflow
│       │   │   │   ├── StageFlowDiagram
│       │   │   │   ├── YAMLViewer (CodeMirror/Monaco)
│       │   │   │   └── ExplanationPanel
│       │   │   ├── Tab: Validation
│       │   │   │   ├── ValidationSummary (pass/fail)
│       │   │   │   ├── ValidationIssuesTable
│       │   │   │   └── DeployButton
│       │   │   ├── Tab: Deployment
│       │   │   │   ├── BranchInfo
│       │   │   │   ├── CommitInfo
│       │   │   │   └── PRLinkCard
│       │   │   └── Tab: Execution (shown after merge)
│       │   │       ├── ExecutionStatusBadge
│       │   │       ├── WorkflowTimeline (Gantt chart)
│       │   │       ├── JobAccordion
│       │   │       │   └── JobDetail
│       │   │       │       ├── JobStatusBadge
│       │   │       │       ├── StepList
│       │   │       │       │   └── StepItem (name, status, duration)
│       │   │       │       └── StepLogViewer
│       │   │       └── LiveLogViewer (SSE)
│       │   └── ActionButtons (Re-analyze, View Report)
│       │
│       ├── SecurityReportPage
│       │   ├── ReportHeader (pipeline name, execution date)
│       │   ├── ScoreCardsRow
│       │   │   ├── RiskScoreGauge (radial gauge)
│       │   │   ├── SecurityPostureGauge
│       │   │   └── ComplianceScoreGauge
│       │   ├── SeverityChart (Recharts PieChart)
│       │   ├── FindingsSection
│       │   │   ├── FindingsToolbar (search, filter by severity/scanner)
│       │   │   └── FindingsTable
│       │   │       └── FindingsRow
│       │   │           ├── SeverityBadge
│       │   │           ├── ScannerIcon
│       │   │           ├── Title
│       │   │           ├── FileLocation
│       │   │           ├── CVEBadge
│       │   │           └── ExpandButton → FindingDetail
│       │   │               ├── Description
│       │   │               ├── Impact
│       │   │               ├── Remediation
│       │   │               └── CodeSnippet
│       │   ├── ComplianceSection
│       │   │   ├── FrameworkSelector (dropdown: OWASP/CIS/SOC2)
│       │   │   └── ComplianceChecklist
│       │   │       └── ComplianceItem (control_id, name, pass/fail badge)
│       │   └── RecommendationsSection
│       │       └── RecommendationCard
│       │           ├── PriorityBadge
│       │           ├── Category
│       │           ├── Title
│       │           ├── Description
│       │           ├── Impact
│       │           ├── RemediationText
│       │           └── CodeDiff (before/after)
│       │
│       ├── HistoryPage
│       │   ├── HistoryFilters (date range, repo, status)
│       │   └── HistoryTable
│       │       └── HistoryRow (date, repo, status, risk score, findings count, actions)
│       │
│       └── SettingsPage
│           ├── GitHubSection
│           │   ├── ConnectedAccountsList
│           │   └── ConnectNewAccount
│           ├── LLMSection
│           │   ├── ProviderSelect
│           │   ├── ApiKeyInput (masked)
│           │   └── ModelSelect
│           ├── ApiTokensSection
│           │   └── TokenList
│           └── PreferencesSection
│               └── ThemeToggle, NotificationsToggle
```

---

## 17. Risk Scoring Framework

### 17.1 Per-Finding Severity Weights

| Severity | Weight | Base Score Range | Examples |
|---|---|---|---|
| Critical | 10 | 9.0-10.0 | Active secret exposure, RCE vulnerability, privilege escalation |
| High | 7 | 6.0-8.9 | SQL injection, authentication bypass, known CVE with exploit |
| Medium | 4 | 3.0-5.9 | Dependency vuln without known exploit, missing security control |
| Low | 1 | 0.0-2.9 | Informational, best practice violation, minor misconfiguration |

### 17.2 Overall Risk Score (0–100)

```
RawScore = (Σ severity_weights) / (total_findings * 10) * 100
RiskScore = clamp(RawScore, 0, 100)
```

**Example calculation:**
- 1 Critical (10) + 2 High (7+7) + 3 Low (1+1+1) = 27 total weight
- total_findings = 6
- RawScore = 27 / (6 * 10) * 100 = 45
- RiskScore = 45

### 17.3 Security Posture Score (0–100)

```
PostureScore = 100 - RiskScore
```

### 17.4 Compliance Score (0–100)

For each applicable control:

```
ComplianceScore = (passed_controls / applicable_controls) * 100
```

**OWASP CI/CD Controls:**

| Control ID | Control Name | Weight |
|---|---|---|
| CI/CD-01 | SAST scan present | 15 |
| CI/CD-02 | Dependency vulnerability scan present | 15 |
| CI/CD-03 | Secret detection scan present | 15 |
| CI/CD-04 | Container vulnerability scan present (if Docker) | 15 |
| CI/CD-05 | All third-party actions pinned to commit SHA | 15 |
| CI/CD-06 | Minimal GITHUB_TOKEN permissions | 10 |
| CI/CD-07 | Concurrency groups configured | 10 |
| CI/CD-08 | Deploy job gated with `if:` condition | 5 |

### 17.5 Risk Level Mapping

| Score Range | Level | Color | Action |
|---|---|---|---|
| 0-19 | Low | Green | No immediate action needed |
| 20-39 | Medium | Yellow | Review and plan remediation |
| 40-69 | High | Orange | Prioritize remediation in next sprint |
| 70-100 | Critical | Red | Remediate immediately |

### 17.6 Scoring Visualization

```
Risk Score: 45/100  ████████████████░░░░░░░░░░░░░░  HIGH (Orange)
                    ↑        ↑        ↑        ↑
                   0        25       50       75      100

Severity Breakdown:
  Critical:  1  ████░░░░░░░░░░░░░░░░░░   (8%)
  High:      2  ████████░░░░░░░░░░░░░░   (17%)
  Medium:    0  ░░░░░░░░░░░░░░░░░░░░░░   (0%)
  Low:       3  ████████████░░░░░░░░░░   (25%)
```

---

## 18. Implementation Roadmap

### Phase 1 — Foundation (Weeks 1-3)

| Task | Area | Description |
|---|---|---|
| Fix graph `add_conditional_edges` path_map bug | AI Service | Correct `TOOL_ROUTES` keys to match routing function return values |
| Fix intent_classifier fallback | AI Service | Don't override `request_type` when already set by caller |
| Add `GITHUB_TOKEN` to Settings config | Config | Make GitHub token accessible as `settings.GITHUB_TOKEN` |
| Implement repository_connection_node | AI Service | Validate GitHub token + repo access |
| Implement repository_scan_node | AI Service | Fetch repo contents and key files |
| Add database models for new schema | Backend | Migrate to full schema from Section 12 |
| Frontend: Auth pages | Frontend | Login, Register, GitHub OAuth flow |

### Phase 2 — Repository Analysis (Weeks 4-6)

| Task | Area | Description |
|---|---|---|
| Implement technology_detection_node | AI Service | LLM-based tech stack classification |
| Implement architecture_detection_node | AI Service | LLM-based architecture inference |
| Implement security_requirement_inference_node | AI Service | LLM-based security needs inference |
| `POST /api/repo/analyze` endpoint | AI Service | Full repo analysis API |
| Frontend: Repository detail page | Frontend | Detection results display, technology badges |
| Frontend: Connect repo modal | Frontend | Repository URL + token input |

### Phase 3 — Pipeline Generation & Validation (Weeks 7-9)

| Task | Area | Description |
|---|---|---|
| Implement workflow_generation_node | AI Service | LLM-based YAML generation with security controls |
| Implement workflow_validation_node | AI Service | YAML syntax + schema + security validation |
| Implement github_branch_creation_node | AI Service | Create branch from default |
| Implement pull_request_creation_node | AI Service | Commit workflow + create PR |
| `POST /api/repo/pipeline` endpoint | AI Service | End-to-end pipeline generation |
| Frontend: Pipeline detail page | Frontend | YAML viewer, stage flow, validation results |
| Frontend: PR link and deploy UI | Frontend | Branch/commit/PR display |

### Phase 4 — Execution & Monitoring (Weeks 10-12)

| Task | Area | Description |
|---|---|---|
| Implement workflow_execution_node | AI Service | Trigger `workflow_dispatch` |
| Implement execution_monitor_node | AI Service | Poll GitHub API every 5s |
| SSE log streaming endpoint | AI Service | Real-time log push via Server-Sent Events |
| GitHub webhook receiver | Backend | Listen for `workflow_run` events |
| Frontend: Execution timeline | Frontend | Gantt-style job/step visualization |
| Frontend: Live log viewer | Frontend | SSE-backed real-time log display |
| Frontend: Workflow status banner | Frontend | Real-time status badge updates |

### Phase 5 — Security Analysis & Reporting (Weeks 13-16)

| Task | Area | Description |
|---|---|---|
| Implement security_analysis_node | AI Service | Parse Semgrep/Trivy/Gitleaks/DC outputs |
| Implement risk_assessment_node | AI Service | Calculate risk/posture/compliance scores |
| Implement recommendation_generation_node | AI Service | Per-finding remediation generation |
| `POST /api/pipeline/analyze/{run_id}` | AI Service | Full security analysis endpoint |
| Frontend: Security report page | Frontend | Risk gauge, severity charts, findings table |
| Frontend: Compliance scorecard | Frontend | Framework control checklist |
| Frontend: Recommendations list | Frontend | Priority-sorted remediation cards |

### Phase 6 — Dashboard & Hardening (Weeks 17-20)

| Task | Area | Description |
|---|---|---|
| Dashboard overview page | Frontend | Stats cards, activity feed, security trend chart |
| History page | Frontend | Filterable pipeline execution history |
| RBAC implementation | Backend | Role-based access control |
| Audit logging | Backend | All action audit trail |
| Rate limiting | Backend | Redis-based rate limiting |
| Token encryption | Backend | AES-256-GCM for GitHub tokens |
| Dashboard materialized views | Backend | Refresh strategy for stats |
| Error propagation redesign | AI Service | Structured error handling across all nodes |
| End-to-end tests | All | Integration tests for full 16-step flow |
| Documentation | All | API docs, deployment guide, user guide |

---

## 19. MVP Scope

### MVP Must-Have (Phase 1-3, Weeks 1-9)

1. Fix existing graph bugs (path_map, intent_classifier fallback)
2. Repository connection with GitHub token validation
3. Repository scanning (fetch structure + key config files)
4. Technology detection (language, framework, build tools, test frameworks)
5. Architecture detection (monolith vs multi-service)
6. Security requirement inference (SAST, dependency scan, secret scan, etc.)
7. **`POST /api/repo/pipeline`** endpoint — full end-to-end: analyze → generate → validate → deploy
8. GitHub Actions YAML generation with security controls pinned by default
9. Workflow validation (YAML syntax + security checks)
10. Branch creation + workflow file commit + PR creation
11. Frontend: Connect repository UI
12. Frontend: Repository detail with detection results
13. Frontend: Generated YAML viewer
14. Frontend: Validation results display
15. Frontend: Deploy to GitHub button

### MVP Out of Scope

- Live workflow execution monitoring (Phase 4)
- SSE real-time log streaming (Phase 4)
- Workflow execution timeline visualization (Phase 4)
- Security analysis and risk assessment (Phase 5)
- Compliance mapping and scoring (Phase 5)
- Recommendation generation (Phase 5)
- Security report page (Phase 5)
- Dashboard overview with charts (Phase 6)
- RBAC and audit logging (Phase 6)
- Rate limiting and token encryption (Phase 6)

---

## 20. Future Enhancements

### Short Term (Post-MVP)

| Feature | Description | Value |
|---|---|---|
| Workflow execution monitoring | Track runs, poll status, auto-detect failures | Pipeline observability |
| Live log streaming | SSE-backed real-time log viewer | Debugging speed |
| Security analysis engine | Parse scanner outputs into structured findings | Vulnerability insights |
| Risk scoring | Quantitative risk assessment (0-100) | Prioritization |
| Compliance mapping | OWASP/CIS/SOC2 control mapping | Compliance automation |
| Auto-fix PRs | Agent creates fix PRs for detected issues | Remediation automation |
| Multi-repo support | Batch-generate across repos | Org-wide adoption |
| Scheduled security audits | Weekly cron-triggered audits | Continuous monitoring |

### Medium Term

| Feature | Description |
|---|---|
| **Custom scanner integration** | Allow users to add custom security tools |
| **Slack/Teams notifications** | Alert on critical findings, failed deployments |
| **Kubernetes-aware pipelines** | Helm chart scanning, K8s manifest security checks |
| **IaC scanning** | Terraform, CloudFormation security analysis |
| **License compliance** | Dependency license scanning (GPL, MIT, etc.) |
| **SBOM generation** | SPDX/CycloneDX per build |
| **GitHub Advanced Security integration** | GHAS code scanning + secret scanning APIs |
| **Workflow template marketplace** | Community-contributed workflow templates |
| **PR auto-review enhancements** | Comment on PRs with security findings inline |

### Long Term

| Feature | Description |
|---|---|
| **Multi-cloud deployment** | AWS CodePipeline, GCP Cloud Build, Azure DevOps |
| **Self-healing pipelines** | Auto-rollback, fix, and re-run failed stages |
| **Learning from incidents** | Agent learns from past failures to improve generation |
| **Natural language dashboards** | "Show all critical findings from last week" |
| **Team collaboration** | Share reports, assign findings, review workflows |
| **Cross-repo risk aggregation** | Org-wide risk dashboard across all repos |
| **Auto-remediation** | Agent directly modifies code and opens fix PRs |
| **On-premises deployment** | Support air-gapped environments with local LLM |

---

## 21. Appendix

### Appendix A: Bug Fixes Required in Current Codebase

#### Bug 1: `graph.py:65` — Wrong path_map keys

**File:** `ai-service/app/agents/graph.py`

```python
# Current (broken):
workflow.add_conditional_edges(
    "tool_selector",
    route_selector_to_tool,
    TOOL_ROUTES,  # keys are intent names, but function returns tool node names
)

# Fixed:
WORKFLOW_ROUTES = {
    "pr_tool": "pr_tool",
    "scan_tool": "scan_tool",
    "workflow_tool": "workflow_tool",
    "report_tool": "report_tool",
}
workflow.add_conditional_edges(
    "tool_selector",
    route_selector_to_tool,
    WORKFLOW_ROUTES,
)
```

#### Bug 2: `intent_classifier.py:62` — Wrong fallback overrides caller

**File:** `ai-service/app/agents/nodes/intent_classifier.py`

The fallback `report_gen` should not override `request_type` if already set by the endpoint.

#### Bug 3: `intent_classifier.py:53` — Unused context in format string

The prompt template doesn't use `{context}`, but it's passed to `.format()`.

### Appendix B: Key Metrics & KPIs

| Metric | Target | Measurement |
|---|---|---|
| Repository analysis accuracy | > 95% correct language/framework detection | Manual review of sampled repos |
| Workflow generation validity | > 90% valid YAML on first try | Pass rate of validation node |
| PR creation success rate | > 95% | GitHub API success / total attempts |
| Security scan coverage | 100% of applicable stages present | Audit of generated YAML stages |
| Risk score accuracy | ±1 point vs manual expert review | Sample of 50 workflows reviewed |
| Dashboard page load time | < 2s | Lighthouse/Web Vitals |
| Agent graph execution time | < 45s (excluding LLM) | LangSmith tracing |
| End-to-end pipeline time | < 6 min (including workflow execution) | Request → completed report |
| User satisfaction | NPS > 50 | Quarterly user survey |

### Appendix C: LLM Prompt Templates

#### Technology Detection Prompt

```
You are a DevSecOps engineer analyzing a GitHub repository.

Given the repository files and structure below, identify:
1. PRIMARY programming language
2. SECONDARY languages
3. All FRAMEWORKS detected
4. BUILD TOOLS
5. TEST FRAMEWORKS
6. PACKAGE MANAGER
7. Whether DOCKERFILE exists
8. Whether DOCKER-COMPOSE exists
9. Whether KUBERNETES manifests exist
10. DATABASES used

Repository structure: {structure}
Key files:
{files}

Respond in JSON format:
{{
  "primary_language": "...",
  "secondary_languages": [...],
  "frameworks": [...],
  "build_tools": [...],
  "test_frameworks": [...],
  "package_manager": "...",
  "has_dockerfile": true/false,
  "has_docker_compose": true/false,
  "has_kubernetes": true/false
}}
```

#### Workflow Generation Prompt

```
You are a DevSecOps engineer generating a secure GitHub Actions workflow.

Project profile:
- Language: {language}
- Frameworks: {frameworks}
- Build tools: {build_tools}
- Test frameworks: {test_frameworks}
- Package manager: {package_manager}
- Architecture: {architecture}
- Has Docker: {has_docker}
- Has Kubernetes: {has_k8s}

Required security stages:
{security_stages}

Generate a complete, production-ready GitHub Actions YAML workflow that:

1. Includes ALL required security stages
2. Pins ALL third-party actions to commit SHA (never version tags)
3. Sets MINIMAL GITHUB_TOKEN permissions
4. Configures CONCURRENCY groups
5. Sets persist-credentials: false on checkout
6. Gates deploy jobs with if: github.ref conditions
7. Uses proper caching for dependencies
8. Includes proper job dependencies
9. Sets timeouts on steps

After the YAML, provide a brief explanation of:
- Why each stage was included
- What security controls were applied
- How the workflow is optimized for this specific project

Separate YAML and explanation with: ---EXPLANATION---
```

### Appendix D: Error Handling Strategy

| Error Scenario | Node | Recovery |
|---|---|---|
| Invalid GitHub token | repository_connection_node | Return error message, prompt user for new token |
| Repository not found | repository_connection_node | Return 404, suggest checking URL |
| GitHub API rate limit | Any node | Retry after rate limit reset (Retry-After header) |
| GitHub API timeout | Any node | Retry up to 3 times with exponential backoff |
| LLM call failure | Any LLM node | Retry once, fall back to cached/default if available |
| LLM malformed response | technology_detection_node | Retry with stricter format instructions |
| Invalid YAML generation | workflow_generation_node | Retry with error feedback in prompt |
| Branch creation conflict | github_branch_creation_node | Append unique suffix and retry |
| PR creation conflict | pull_request_creation_node | Check for existing PR, update if exists |
| Workflow trigger failure | workflow_execution_node | Verify workflow file exists, retry |
| Workflow execution timeout | execution_monitor_node | Log partial results, mark as incomplete |
| Scanner output parsing error | security_analysis_node | Log raw output, skip malformed entries |

### Appendix E: Agent Graph Configuration

```python
from langgraph.graph import StateGraph, END

def build_pipeline_engineer_graph() -> StateGraph:
    workflow = StateGraph(PipelineEngineerState)

    # Add nodes
    workflow.add_node("repository_connection", repository_connection_node)
    workflow.add_node("repository_scan", repository_scan_node)
    workflow.add_node("technology_detection", technology_detection_node)
    workflow.add_node("architecture_detection", architecture_detection_node)
    workflow.add_node("security_requirement_inference", security_requirement_inference_node)
    workflow.add_node("workflow_generation", workflow_generation_node)
    workflow.add_node("workflow_validation", workflow_validation_node)
    workflow.add_node("error_handler", error_handler_node)
    workflow.add_node("github_branch_creation", github_branch_creation_node)
    workflow.add_node("pull_request_creation", pull_request_creation_node)
    workflow.add_node("workflow_execution", workflow_execution_node)
    workflow.add_node("execution_monitor", execution_monitor_node)
    workflow.add_node("security_analysis", security_analysis_node)
    workflow.add_node("risk_assessment", risk_assessment_node)
    workflow.add_node("recommendation_generation", recommendation_generation_node)
    workflow.add_node("response_formatter", response_formatter_node)

    # Set entry point
    workflow.set_entry_point("repository_connection")

    # Define edges
    workflow.add_edge("repository_connection", "repository_scan")
    workflow.add_edge("repository_scan", "technology_detection")
    workflow.add_edge("technology_detection", "architecture_detection")
    workflow.add_edge("architecture_detection", "security_requirement_inference")
    workflow.add_edge("security_requirement_inference", "workflow_generation")

    # Conditional edge from validation
    workflow.add_conditional_edges(
        "workflow_validation",
        lambda state: "github_branch_creation" if state["validation_passed"] else "error_handler",
        {
            "github_branch_creation": "github_branch_creation",
            "error_handler": "error_handler",
        }
    )

    workflow.add_edge("github_branch_creation", "pull_request_creation")
    workflow.add_edge("pull_request_creation", "workflow_execution")

    # Conditional edge from execution monitor
    workflow.add_conditional_edges(
        "execution_monitor",
        lambda state: "security_analysis" if state["workflow_status"] == "completed" else "error_handler",
        {
            "security_analysis": "security_analysis",
            "error_handler": "error_handler",
        }
    )

    workflow.add_edge("security_analysis", "risk_assessment")
    workflow.add_edge("risk_assessment", "recommendation_generation")
    workflow.add_edge("recommendation_generation", "response_formatter")
    workflow.add_edge("error_handler", "response_formatter")
    workflow.add_edge("response_formatter", END)

    # Compile
    return workflow.compile()
```

---

*End of PRD — Version 2.0*