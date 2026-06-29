# 3. Business Process Flow

## 3.1 BPMN-Level Process Description

The DevSecOps Agent platform implements a **linear-iterative business process** with parallelized sub-processes. The end-to-end flow encompasses nine major phases:

```
[Start] → Repository Selection → Analysis → Security Assessment → Workflow Generation → Validation → Repair ↻ → PR Creation → Workflow Execution → Security Reporting → [End]
```

---

## 3.2 Phase 1: Repository Selection

### Business Objective
Establish a secure connection to a target GitHub repository for automated analysis and workflow generation.

### Step-by-Step Process

1. **Authentication Gateway**
   - User authenticates via GitHub OAuth 2.0 with `repo`, `workflow`, and `read:org` scopes.
   - System exchanges authorization code for an access token (encrypted at rest).
   - System creates a JWT session token with 24-hour expiry, stored in Redis for stateless validation.

2. **Repository Discovery**
   - System calls `GET /user/repos?sort=updated&per_page=100` via GitHub API.
   - Repositories are paginated (100 per page); system respects `Link` header for pagination.
   - Results are cached in Redis for 5 minutes to avoid redundant API calls.

3. **Repository Selection**
   - User browses a searchable, filterable list (filter by language, visibility, last updated).
   - User selects a repository; system performs an access-rights verification:
     - `GET /repos/{owner}/{repo}` — confirms existence and visibility.
     - `GET /repos/{owner}/{repo}/branches` — confirms default branch existence.
   - If verification passes, the repository record is persisted in the `repositories` table with status = "connected."

4. **Business Rules**
   - User may connect a maximum of 50 repositories per account (configurable via admin panel).
   - Private repositories require the user's PAT to have `repo` (full) scope; public repositories require only `public_repo`.
   - Archived repositories are flagged and excluded from workflow generation unless explicitly opted in.

---

## 3.3 Phase 2: Analysis

### Business Objective
Automatically identify all technologies, languages, frameworks, build tools, test frameworks, and deployment configurations in a target repository.

### Step-by-Step Process

1. **Job Queuing**
   - An `AnalysisJob` record is created in the database with status "queued."
   - A message is enqueued to Redis (Bull/BullMQ pattern) containing `{job_id, repository_id, user_id, options}`.
   - A LangGraph orchestrator worker dequeues the message and initializes the agent state machine.

2. **Repository Cloning**
   - Worker performs a shallow clone: `git clone --depth=1 --single-branch {url} /tmp/repos/{job_id}`.
   - If the repository exceeds 100 MB, the system falls back to GitHub Tree API (no local clone).
   - Clone progress is streamed; failure at this stage triggers retry with fallback.

3. **File Tree Analysis**
   - The Repository Analyzer Agent scans the directory tree recursively, building a structured file manifest.
   - Key manifest files are identified: `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`, `Makefile`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/*.yml`.
   - The agent counts file extensions to produce a preliminary language distribution.

4. **Technology Detection**
   - The Technology Detection Agent processes the file manifest through an LLM (OpenRouter).
   - The LLM prompt includes: the file tree structure, manifest file contents, directory naming patterns.
   - The LLM returns structured JSON with: languages, frameworks, build tools, test frameworks, deployment configs — each with confidence scores and source evidence.

5. **Result Validation**
   - Results are cross-validated against known signatures (e.g., `requirements.txt` always implies Python).
   - Low-confidence results (< 0.7 confidence) are flagged for user review.
   - Results are persisted to the `analysis_results` table as a JSONB column.

6. **Business Rules**
   - Analysis must complete within 120 seconds; timeout triggers fallback to heuristic-only mode.
   - Monorepos are detected by the presence of multiple `package.json` or build configuration files in subdirectories.
   - Analysis results are immutable after creation; a new analysis creates a new record (append-only audit trail).

---

## 3.4 Phase 3: Security Assessment

### Business Objective
Infer security requirements based on the detected technology stack, regulatory context, and organizational policies.

### Step-by-Step Process

1. **Security Requirement Inference**
   - The Security Requirement Agent receives the technology detection output.
   - The LLM is prompted with: detected technologies + a knowledge base of security best practices (OWASP Top 10, SANS CWE Top 25, framework-specific guides).
   - The agent outputs a list of required security scanning stages mapped to specific tools:
     - **SAST** (Static Application Security Testing) → Semgrep, CodeQL
     - **Secret Detection** → Gitleaks
     - **Dependency/Container Scanning** → Trivy, Dependency Review
     - **Dynamic Analysis** → (optional, noted as out-of-scope for CI/CD pipeline)

2. **Tool Compatibility Mapping**
   - Each detected language/framework is cross-referenced with tool compatibility:
     - Python → Semgrep (Python ruleset), Bandit (optional), Safety (dependency check)
     - JavaScript/TypeScript → Semgrep (JS/TS ruleset), npm audit, CodeQL (JS/TS queries)
     - Go → Semgrep (Go ruleset), CodeQL (Go queries), govulncheck
     - Java → Semgrep (Java ruleset), CodeQL (Java queries), OWASP Dependency Check
     - Docker → Trivy, Dockle, Hadolint
     - Kubernetes → Kubesec, kube-linter, Trivy (config scanning)

3. **Severity Threshold Configuration**
   - Default severity thresholds are applied:
     - Critical findings: Block PR merge
     - High findings: Require review
     - Medium findings: Log and notify
     - Low findings: Log only
   - Users may customize thresholds per repository via the UI.

4. **Business Rules**
   - At least one SAST tool must be selected for every repository (non-negotiable minimum).
   - Secret detection (Gitleaks) is mandatory for all repositories.
   - Security requirements are versioned; changes create an audit log entry.

---

## 3.5 Phase 4: Workflow Generation

### Business Objective
Generate a syntactically and semantically correct GitHub Actions workflow YAML file that implements build, test, and security scanning stages.

### Step-by-Step Process

1. **Workflow Template Selection**
   - The Workflow Generator Agent selects a base template based on the technology stack.
   - For unrecognized stacks, a generic multi-stage template is used.

2. **Stage Construction**
   - The agent constructs workflow stages sequentially:
     - **Checkout Stage**: `actions/checkout@v4`
     - **Setup Stage**: Install language runtime + dependencies (e.g., `actions/setup-node@v4`, `pip install -r requirements.txt`)
     - **Build Stage**: Execute build command (e.g., `npm run build`, `make build`)
     - **Test Stage**: Execute test command (e.g., `npm test`, `pytest`)
     - **SAST Stage**: Run Semgrep + CodeQL analysis
     - **Secret Detection Stage**: Run Gitleaks
     - **Dependency Scan Stage**: Run Trivy + Dependency Review
     - **Container Scan Stage** (conditional): If Dockerfile detected, run Trivy image scan
     - **Artifact Stage** (conditional): Upload build artifacts
     - **Deploy Stage** (conditional): If deployment config detected, generate deploy steps

3. **Prompt Engineering**
   - The LLM receives a structured prompt with:
     - System instruction: "You are a DevSecOps expert. Generate a production-grade GitHub Actions workflow."
     - Context: Technology stack, file paths, security requirements.
     - Constraints: Action versions must be pinned, secrets must use `${{ secrets.* }}` syntax, no hardcoded credentials.
     - Output format: Valid YAML only, no markdown fences.

4. **Post-Processing**
   - LLM output is cleaned (stripped of markdown fences if present).
   - YAML is pretty-printed with consistent indentation (2 spaces).
   - A unique workflow file name is generated: `devsecops-pipeline-{timestamp}.yml`.

5. **Business Rules**
   - Workflow must not exceed GitHub's 512 KB file size limit.
   - All action versions must be pinned to SHA or major version tags (e.g., `@v4`, not `@main`).
   - Secrets must never be hardcoded; violations trigger automatic rejection.

---

## 3.6 Phase 5: Validation

### Business Objective
Verify that the generated workflow YAML is syntactically valid, semantically correct, and conforms to GitHub Actions schema and security policies.

### Step-by-Step Process

1. **Syntax Validation (Static)**
   - Parse YAML using a strict YAML parser (ruamel.yaml or PyYAML).
   - If parsing fails with a syntax error → Route to Repair Phase.
   - On success, normalize YAML structure for downstream validation.

2. **Schema Validation**
   - Validate the workflow structure against the GitHub Actions workflow schema (JSON Schema):
     - `name`, `on`, `jobs` must be present.
     - Each job must have `runs-on` or `uses`.
     - Steps must have `uses` or `run` (or both).
     - Valid trigger events: `push`, `pull_request`, `schedule`, `workflow_dispatch`, `release`, etc.
   - Schema violations are collected into an error list ranked by severity (ERROR, WARNING).

3. **Security Policy Validation**
   - Custom security policies are checked:
     - Are all required security tools present? (e.g., Semgrep job exists?)
     - Are action versions pinned?
     - Are any `secrets.*` references undefined (not present in the inferred secrets list)?
     - Are any steps running shell commands with unsanitized inputs?
     - Is `permissions` block present and set to `contents: read` minimum?
   - Each policy violation generates a `SecurityPolicyViolation` record.

4. **Semantic Validation (LLM-based)**
   - The validated YAML + policy violation list is fed to an LLM with the prompt: "Does this workflow correctly build, test, and scan the described project? Identify any logical errors."
   - The LLM outputs a pass/fail with reasoning.

5. **Business Rules**
   - All ERROR-level violations block PR creation.
   - WARNING-level violations allow PR creation with a caution notice.
   - Validation results are persisted for audit trail.

---

## 3.7 Phase 6: Repair (Self-Correction Loop)

### Business Objective
Automatically correct validation failures without human intervention, up to a maximum retry limit.

### Step-by-Step Process

1. **Error Classification**
   - Each validation error is classified into:
     - **Syntax Error**: YAML parse failure (fixable)
     - **Schema Error**: Missing required field, wrong type (fixable)
     - **Security Policy Error**: Missing security tool (fixable)
     - **Semantic Error**: Logical flow problem (partially fixable)

2. **Repair Strategy Selection**
   - **Syntax Errors**: Use a YAML auto-fixer that operates on the raw text (regex-based indentation fix, quote normalization).
   - **Schema Errors**: The Repair Agent uses an LLM with a few-shot prompt containing pairs of (invalid YAML, corrected YAML).
   - **Security Policy Errors**: The Repair Agent inserts missing security job blocks with default configurations.
   - **Semantic Errors**: The Repair Agent re-generates the affected job(s) with corrected logic.

3. **Repair Execution**
   - The Repair Agent receives: `{original_workflow, error_list, error_classifications}`.
   - It outputs: `{repaired_workflow, change_summary}`.
   - The repaired workflow is re-submitted to the Validation Phase.

4. **Iteration Control**
   - Maximum 3 repair iterations per workflow generation.
   - If 3 iterations fail → workflow is marked as "repair_failed," user is notified.
   - Each iteration is logged with the error list and repair diff.

5. **Business Rules**
   - Repair must not introduce new security vulnerabilities.
   - Each repair iteration must produce a different output (detect infinite loops via hash comparison).
   - Repairs that modify user-configured triggers or permissions require explicit user confirmation.

---

## 3.8 Phase 8: Pull Request Creation

### Business Objective
Deliver the validated workflow into the target repository as a GitHub Pull Request.

### Step-by-Step Process

1. **Branch Creation**
   - Generate branch name: `devsecops/secure-workflow-{timestamp}-{short_hash}`.
   - Create branch from the repository's default branch: `POST /repos/{owner}/{repo}/git/refs`.

2. **File Commit**
   - Create/update workflow file: `PUT /repos/{owner}/{repo}/contents/.github/workflows/{filename}.yml`.
   - Commit message: "feat(ci): add automated DevSecOps pipeline\n\nGenerated by AI-Powered DevSecOps Agent.\nIncludes: SAST, secret detection, dependency scanning, [other stages]."

3. **Pull Request Creation**
   - Create PR: `POST /repos/{owner}/{repo}/pulls`.
   - PR title: "feat(ci): add secure CI/CD pipeline with DevSecOps scanning"
   - PR body: Auto-generated summary including detected technologies, included security scans, and a note that this PR was AI-generated.
   - Assign reviewers (optional, from CODEOWNERS or user selection).
   - Add labels: `devsecops`, `automated`, `security`, `ci`.

4. **Post-Creation**
   - Store PR metadata in database: `{pr_number, pr_url, status: "open", created_at}`.
   - System begins polling GitHub Checks API for workflow execution status (Phase 9).
   - User receives notification (in-app + optional email/webhook).

5. **Business Rules**
   - PR creation is idempotent; duplicate requests for the same repo+branch return the existing PR URL.
   - Branch protection rules may block PR creation; system surfaces GitHub's error message to the user.

---

## 3.9 Phase 9: Workflow Execution & Monitoring

### Business Objective
Monitor the execution of generated workflows, collect scan results, and make them available for reporting.

### Step-by-Step Process

1. **Execution Trigger**
   - Workflow execution begins when the PR is created (triggers `pull_request` event) or when the PR is merged to the default branch (triggers `push` event).

2. **Status Polling**
   - Backend worker polls GitHub Checks API: `GET /repos/{owner}/{repo}/commits/{sha}/check-runs`.
   - Polling interval: 15 seconds during active execution; 60 seconds otherwise.
   - Statuses tracked: `queued`, `in_progress`, `completed`.
   - Conclusions tracked: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`.

3. **Artifact Collection**
   - Upon workflow completion, the system downloads scan result artifacts (SARIF files from CodeQL, JSON reports from Semgrep/Gitleaks/Trivy).
   - Artifacts are stored in the database as JSONB (for structured querying) and as raw file references (for download).

4. **Scan Result Parsing**
   - Each tool's output is parsed into a unified finding format:
     ```
     {
       tool: "semgrep",
       rule_id: "python.django.security.audit.xss",
       severity: "high",
       file_path: "src/views.py",
       line_number: 42,
       description: "Detected potential XSS vulnerability",
       cwe_id: "CWE-79",
       cvss_score: 7.5,
       remediation: "...",
       raw_output: "{...}"
     }
     ```
   - Findings are deduplicated across tools (same file+line+category means same finding).

5. **Business Rules**
   - Workflow execution artifacts are retained for 90 days (configurable).
   - Failed workflow executions trigger an in-app notification with a link to the GitHub Actions run log.

---

## 3.10 Phase 10: Security Reporting

### Business Objective
Aggregate all scan findings, calculate risk scores, generate remediation recommendations, and present an interactive security dashboard.

### Step-by-Step Process

1. **Findings Aggregation**
   - All parsed findings are loaded from the database for the target repository and time range.
   - Findings are grouped by tool, severity, file, and CWE category.

2. **Risk Score Calculation** (see Section 5.5 for detailed logic)
   - A weighted risk score is calculated per repository:
     ```
     RiskScore = (Critical × 10) + (High × 5) + (Medium × 2) + (Low × 1)
     ```
   - Scores are normalized to a 0-100 scale.
   - Time-series risk scores are computed using historical snapshots.

3. **Recommendation Generation** (see Section 5.6 for detailed logic)
   - The Recommendation Agent processes high and critical findings through an LLM.
   - The LLM generates: fix code snippets, configuration changes, library upgrade paths.
   - Each recommendation includes a confidence score and CWE reference.

4. **Dashboard Population**
   - Aggregated data is cached in Redis for 30 minutes to reduce database load.
   - Dashboard data is delivered via REST API: `GET /api/v1/dashboard/summary`, `/findings`, `/recommendations`, `/risk-score`.

5. **Report Export**
   - PDF generation uses a server-side template (WeasyPrint or similar) populated with findings.
   - JSON export provides machine-readable complete data.
   - CSV export provides tabular findings for spreadsheet analysis.

6. **Business Rules**
   - Reports are generated on-demand and cached for 10 minutes.
   - Historical reports are retained for 12 months.
   - Risk scores must be recalculated after any finding is triaged (marked as false positive, fixed, etc.).

---

## 3.11 Process Orchestration Summary

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Repository  │────▶│   Analysis   │────▶│   Security    │────▶│   Workflow    │
│  Selection   │     │   (LangGraph)│     │  Assessment   │     │  Generation   │
└─────────────┘     └─────────────┘     └──────────────┘     └──────┬───────┘
                                                                     │
                                                              ┌──────▼───────┐
                                                              │  Validation   │
                                                              └──────┬───────┘
                                                             Pass    │   Fail
                                                         ┌───────────▼──────┐
                                                         │                  │
                                                    ┌────▼────┐     ┌─────▼──────┐
                                                    │  PR     │     │   Repair   │──────┐
                                                    │ Create  │     │  (max 3x)  │      │
                                                    └────┬────┘     └─────┬──────┘      │
                                                         │            Pass │        Fail │
                                              ┌──────────▼──────────┐    │    ┌────▼────┐
                                              │ Workflow Execution  │◀───┘    │  Manual  │
                                              │   & Monitoring      │         │  Review  │
                                              └──────────┬──────────┘         └──────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │  Security Reporting │
                                              │  (Dashboard + PDF)  │
                                              └─────────────────────┘
```
