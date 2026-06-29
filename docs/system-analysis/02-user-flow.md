# 2. User Flow

## 2.A First-Time User — Onboarding Flow

### Preconditions
- User has a GitHub account
- User has not previously authenticated with the platform
- Platform is deployed and accessible at a known URL

### Step-by-Step Journey

| Step | User Action | System Response | Data/State |
|---|---|---|---|
| 1 | Navigates to the platform URL | Serves the React SPA landing page with "Login with GitHub" CTA button | Client: unauthenticated state |
| 2 | Clicks "Login with GitHub" | Redirects browser to GitHub OAuth authorization URL with state=csrf_token, scope=repo+read:org+workflow | Backend: Generates cryptographically random CSRF token, stores in Redis with 10-min TTL |
| 3 | GitHub asks "Authorize DevSecOps Agent?" — User clicks "Authorize" | GitHub redirects to `/api/v1/auth/callback?code=AUTH_CODE&state=CSRF_TOKEN` | GitHub: Authorization code (1-time use, 10-min TTL) |
| 4 | (Automatic) | Backend exchanges authorization code for access token via `POST https://github.com/login/oauth/access_token` | Database: Creates/updates User record, encrypted token in Credential vault |
| 5 | (Automatic) | Backend creates JWT session token, sets HttpOnly Secure cookie, redirects to `/dashboard` | Redis: Session stored. Client: Authenticated SPA state |
| 6 | Sees Welcome onboarding modal with 3-step guide | System checks if user has any connected repositories (empty state) | Client: `GET /api/v1/repositories` returns `[]` |
| 7 | Clicks "Connect Repository" | System fetches user's GitHub repositories via GitHub API (paginated) | Backend: `GET /api/v1/github/repositories?page=1&per_page=30` |
| 8 | Views repository list; searches by name; selects target repo | System validates repository access, stores repository metadata | Database: INSERT into repositories table |
| 9 | Clicks "Start Analysis" on selected repository | System begins Repository Analysis flow (see Flow B) | State: Repository.analysis_status = "pending" |
| 10 | Watches analysis progress bar with step indicators | System pushes progress updates via WebSocket or SSE | Client: Real-time progress rendering |

### Decision Points
- **DP1**: User denies GitHub authorization → Return to landing page with error explanation
- **DP2**: User has zero repositories → Show educational content about creating a repository
- **DP3**: Repository is private and token lacks scope → Prompt user to re-authorize with expanded scopes
- **DP4**: Repository is empty (no commits) → Show message: "Repository is empty. Cannot analyze."

### Success Path
User successfully authenticates, selects a repository, and arrives at the analysis results page within 2 minutes.

### Failure Paths
| Failure | Detection | Recovery |
|---|---|---|
| GitHub OAuth timeout | 10-min Redis TTL on state token | Redirect user to re-initiate login with fresh state token |
| Access token exchange failure | GitHub returns 4xx/5xx | Log error, show "GitHub authentication failed. Please try again." |
| Repository listing failure (rate limit) | GitHub returns 403 + `X-RateLimit-Remaining: 0` | Show rate-limit countdown timer; suggest waiting or using a PAT |
| Session creation failure (DB down) | PostgreSQL connection error | Retry 3x with exponential backoff; fail gracefully with "Service temporarily unavailable" |

---

## 2.B Repository Analysis Flow

### Preconditions
- User is authenticated
- User has selected a repository
- Repository has at least one commit on the default branch

### Step-by-Step Journey

| Step | User Action | System Response | Data/State |
|---|---|---|---|
| 1 | Clicks "Analyze Repository" button | Backend creates an AnalysisJob record, enqueues to Redis Bull/BullMQ queue | Database: analysis_jobs (status: queued) |
| 2 | Views "Analysis in progress..." with step-by-step progress | LangGraph agent picks up job; orchestrates multi-agent pipeline | Redis: Job status, progress counter |
| 3 | — | Repository Analyzer Agent clones repository (shallow clone, depth=1) | Filesystem: `/tmp/repos/{job_id}/` |
| 4 | — | Scans directory tree; identifies key files (package.json, go.mod, Cargo.toml, etc.) | Agent state: `{file_tree: [...], manifest_files: [...]}` |
| 5 | — | Technology Detection Agent classifies languages (via GitHub Linguist or file extension heuristics + LLM) | Agent state: `{languages: [{name: "Python", confidence: 0.98}, ...]}` |
| 6 | — | Technology Detection Agent identifies frameworks (Django, React, Express, etc.) and versions | Agent state: `{frameworks: [{name: "Django", version: "4.2", confidence: 0.95}]}` |
| 7 | — | Technology Detection Agent identifies build tools (npm, pip, Maven, Gradle, etc.) | Agent state: `{build_tools: ["npm", "webpack"]}` |
| 8 | — | Technology Detection Agent identifies testing frameworks (Jest, pytest, JUnit, etc.) | Agent state: `{test_frameworks: ["Jest", "React Testing Library"]}` |
| 9 | — | Technology Detection Agent identifies deployment configs (Dockerfile, docker-compose.yml, Kubernetes manifests, etc.) | Agent state: `{deployment_configs: [{type: "Docker", file: "Dockerfile"}]}` |
| 10 | Sees "Analysis complete" with summary card | System persists analysis results to database; updates job status to "completed" | Client: API response with full analysis result |
| 11 | Views detected technologies in categorized cards with confidence percentages | System renders interactive technology cards with expand/collapse | Client: State update |
| 12 | Clicks on any technology card to see source evidence (file path, line excerpt) | System fetches evidence details from stored analysis data | Client: Modal with code snippet |

### Decision Points
- **DP1**: `manifest_files` is empty → Agent falls back to heuristic detection (file extensions, directory naming conventions)
- **DP2**: LLM returns low-confidence classification (< 0.7) → Mark as "uncertain," request user confirmation, lower temperature and re-query
- **DP3**: Repository contains a monorepo structure → Agent branches into sub-analysis for each package workspace
- **DP4**: Repository exceeds size threshold (> 100 MB) → Skip shallow clone; use GitHub Tree API (read-only, no local clone); warn user that deep file analysis is unavailable

### Success Path
Analysis completes in < 60 seconds, all technologies correctly identified, results persisted.

### Failure Paths
| Failure | Detection | Recovery |
|---|---|---|
| Clone failure (auth, permissions) | Git process exits with non-zero | Retry once with fresh token; if still failing, use GitHub API to list files; flag repository as "limited analysis" |
| LLM timeout (OpenRouter 30s) | HTTP request timeout | Retry with reduced prompt context (truncate file listing); after 3 retries, fall back to heuristic-only detection |
| Technology misclassification | Heuristic: confidence < 0.7 | Mark uncertain; allow user correction in UI; log correction for future few-shot examples |
| File count exceeds token limit | Token counting before LLM call | Apply tree-depth limit, sample key directories, use summary prompts |

---

## 2.C Workflow Generation Flow

### Preconditions
- Repository analysis is complete
- Technology detection results are available
- User has reviewed and confirmed analysis results (or skipped confirmation)

### Step-by-Step Journey

| Step | User Action | System Response |
|---|---|---|
| 1 | Clicks "Generate Workflow" | System presents a configuration panel: target branch, workflow triggers (push, PR, schedule, manual), security tools to include |
| 2 | User toggles security tools: enables Semgrep, Gitleaks, Trivy, Dependency Review, CodeQL (default: all) | System validates that tool configurations are compatible with detected tech stack |
| 3 | User selects trigger events: "Push to main", "Pull Request to main", "Schedule: daily at 02:00 UTC" | System previews trigger YAML fragment |
| 4 | User clicks "Generate" | Backend creates WorkflowGenerationJob in Redis queue |
| 5 | — | Security Requirement Agent infers required security gates based on tech stack (e.g., "npm audit" for Node.js, "bandit" for Python) + user-selected tools |
| 6 | — | Workflow Generator Agent constructs a complete GitHub Actions workflow YAML via LLM with structured prompts |
| 7 | Views generated workflow in a side-by-side diff viewer (left: empty/proposed, right: generated) | System renders YAML with syntax highlighting, line numbers, and inline AI explanation tooltips |
| 8 | Hovers over any step to see AI rationale: "Added Semgrep scan because this project uses Python with Django" | System renders explanation overlay with confidence score |
| 9 | Clicks "Validate" | System triggers Workflow Validator Agent (see Flow in Section 5) |
| 10 | If validation passes → sees green checkmark with "Ready to create PR" | System enables "Create Pull Request" button |
| 10a | If validation fails → sees error list with "Suggest Repair" button | System offers AI-powered auto-repair option |

### Decision Points
- **DP1**: User does not enable any security tools → Warn user: "No security tools selected. Pipeline will lack security scanning." Allow override but flag in audit log.
- **DP2**: Detected tech stack has no known security tool support → Generate build+test only; note in explanation: "No compatible security tool found for {tech}."
- **DP3**: Workflow YAML exceeds GitHub's 512 KB size limit → Warn user; suggest splitting into multiple workflow files.
- **DP4**: Generated workflow duplicates an existing workflow file → Show diff against existing; warn about potential conflicts; offer to overwrite or create separate file.

### Success Path
Validated workflow YAML, ready for PR creation.

### Failure Paths
| Failure | Detection | Recovery |
|---|---|---|
| LLM generates invalid YAML syntax | YAML parser (PyYAML/ruamel) raises parse error | Route to Workflow Repair Agent (Section 2.D flow) |
| LLM hallucinates non-existent GitHub Actions | Validation against `actions/schema.json` | Repair agent replaces hallucinated action with real equivalent |
| Generated workflow uses deprecated action versions | Version check against GitHub Marketplace API | Auto-upgrade to latest major version; note in explanation |
| Token limit exceeded during generation | Token counter before LLM call | Split generation into stages (build → test → deploy → security); stitch results |

---

## 2.D Pull Request Creation Flow

### Preconditions
- Validated workflow YAML exists
- User has write access to the target repository
- GitHub App or PAT has `contents: write` and `pull_requests: write` scopes

### Step-by-Step Journey

| Step | User Action | System Response |
|---|---|---|
| 1 | Clicks "Create Pull Request" | System presents PR metadata form: branch name (auto-suggested: `devsecops/add-secure-workflow`), title, description (auto-generated) |
| 2 | User edits PR title and description; optionally adds reviewers | System previews the PR as it will appear on GitHub |
| 3 | User clicks "Submit PR" | Backend creates branch via GitHub API: `POST /repos/{owner}/{repo}/git/refs` → `POST /repos/{owner}/{repo}/contents/{path}` for workflow file |
| 4 | (Automatic) | System creates PR via: `POST /repos/{owner}/{repo}/pulls` |
| 5 | Sees success notification with link to PR on GitHub | System stores PR metadata (number, URL, status) in database |
| 6 | Clicks link to view PR on GitHub | External redirect to `github.com/{owner}/{repo}/pull/{number}` |
| 7 | Monitors PR checks running (CI/CD) | System polls GitHub Checks API; displays check statuses in dashboard |
| 8 | PR passes all checks → User merges PR via GitHub UI or platform button | System records PR status as "merged" in database |
| 8a | PR fails checks → User sees failure details; requests AI fix | System creates new commit on PR branch with fix; pushes update |

### Decision Points
- **DP1**: Branch name already exists → Append incrementing suffix (e.g., `-2`, `-3`)
- **DP2**: PR title contains sensitive keywords → Filter via regex patterns; warn user
- **DP3**: Target branch is protected and requires specific reviewers → Auto-assign from CODEOWNERS; note that PR may be gated

### Success Path
PR created, checks pass, merged into target branch.

### Failure Paths
| Failure | Detection | Recovery |
|---|---|---|
| Branch creation fails (permission) | GitHub returns 403 | Show: "Insufficient permissions. Ensure GitHub App is installed on this repository." |
| File push fails (branch protection) | GitHub returns 422 | Suggest user push to a different base branch or adjust branch protection rules |
| PR creation fails (duplicate) | GitHub returns 422 | Check for existing open PR; offer to update existing PR instead |
| Rate limit on PR creation | GitHub returns 403 + rate limit headers | Queue operation; execute when rate limit resets |

---

## 2.E Security Dashboard Review Flow

### Preconditions
- At least one repository has been analyzed
- At least one workflow execution has completed

### Step-by-Step Journey

| Step | User Action | System Response |
|---|---|---|
| 1 | Navigates to "Security Dashboard" from top nav | System fetches aggregated security data: `GET /api/v1/dashboard?repo_id=X&time_range=30d` |
| 2 | Views overview cards: Total Scans, Vulnerabilities Found (Critical/High/Medium/Low), Risk Score Trend, Compliance Status | System renders KPI cards with delta indicators (↑/↓ vs previous period) |
| 3 | Views "Risk Score Trend" line chart (time-series) | System fetches historical risk scores from database, renders Chart.js/Recharts line chart |
| 4 | Views "Vulnerabilities by Severity" doughnut chart | System aggregates findings by severity level |
| 5 | Views "Findings by Tool" bar chart | System groups findings by scan tool (Semgrep, Gitleaks, Trivy, etc.) |
| 6 | Clicks on a severity segment in the doughnut chart | System filters findings table to that severity; navigates to detailed findings list |
| 7 | Views findings table with columns: Tool, Rule ID, File, Line, Severity, Description, Status, Action | System renders paginated findings with filtering and sorting |
| 8 | Clicks "Details" on a finding | System fetches full finding detail: code snippet, CWE/CVE reference, remediation guidance |
| 9 | Marks a finding as "False Positive" (dropdown: triage action) | System persists triage status; recalculates risk score excluding false positives |
| 10 | Clicks "Export Report" → selects format (PDF, JSON, CSV) | System generates report with all findings, risk scores, remediation recommendations; downloads to browser |

### Decision Points
- **DP1**: Zero findings found → Display "All Clear" celebration state with security badge
- **DP2**: Critical findings detected → Show prominent red alert banner: "CRITICAL vulnerabilities detected. Immediate action required."

### Success Path
User reviews findings, triages false positives, exports compliance report.

---

## 2.F Security Recommendation Review Flow

### Preconditions
- At least one security scan has completed
- Findings exist in the database

### Step-by-Step Journey

| Step | User Action | System Response |
|---|---|---|
| 1 | Clicks "Recommendations" tab from Security Dashboard | System fetches AI-generated recommendations: `GET /api/v1/recommendations?repo_id=X` |
| 2 | Views recommendations grouped by category: "Dependency Updates," "Code Fixes," "Configuration Changes," "CI/CD Hardening" | System renders categorized card list |
| 3 | Views a recommendation: severity badge, CWE reference, affected files, AI-generated fix code snippet with diff | System renders code diff with syntax highlighting |
| 4 | Clicks "Explain" on a recommendation | System fetches LLM-generated explanation: why this fix is recommended, what the vulnerability exploits, references to OWASP/CWE |
| 5 | Clicks "Apply Fix" | System generates a new branch with the suggested fix, creates a PR (or applies via direct commit, config-dependent) |
| 6 | Clicks "Ignore" → selects reason: "False Positive," "Accepted Risk," "Not Applicable" | System records ignore decision with reason; suppresses in future reports |
| 7 | Views "Implementation Progress" tracker: X/Y recommendations applied | System updates progress based on merged PRs that included the recommended fixes |
| 8 | Clicks "Generate Summary Report" | LLM generates a natural-language executive summary of all recommendations and their status |

### Decision Points
- **DP1**: Recommendation involves breaking changes → Add prominent warning; flag as "Requires Manual Review"
- **DP2**: LLM-generated fix code is syntactically invalid → Trigger Repair Agent; if repair fails, flag as "Requires Manual Review"

### Success Path
User reviews, applies trusted recommendations, generates summary report.
