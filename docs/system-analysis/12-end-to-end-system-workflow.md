# 12. End-to-End System Workflow

## 12.1 Complete System Workflow: User Login → Security Report Generation

This section describes the complete end-to-end workflow covering all system components, actors, and decision points from initial user authentication through final security report generation.

### Phase 1: Authentication & Onboarding

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 1.1 | User | Navigates to platform URL | React SPA renders landing page with "Login with GitHub" button | Frontend: unauthenticated | — |
| 1.2 | User | Clicks "Login with GitHub" | Backend generates CSRF state token, stores in Redis (TTL: 10min), redirects to GitHub OAuth | Backend: state stored in Redis | — |
| 1.3 | GitHub | Shows authorization screen | User sees requested scopes: `repo`, `workflow`, `read:org` | GitHub: authorization pending | **DP1**: User accepts → proceed; User denies → return to landing with error |
| 1.4 | GitHub | Redirects to `/api/v1/auth/callback?code=X&state=Y` | Backend verifies state against Redis, exchanges code for access token via GitHub API | Backend: code validated | **DP2**: State mismatch → reject with 400; State match → continue |
| 1.5 | Backend | Exchanges code for token | `POST https://github.com/login/oauth/access_token` | GitHub: returns access_token + refresh_token | **DP3**: Token exchange fails → retry 1x, then show error |
| 1.6 | Backend | Encrypts and stores token | AES-256-GCM encryption → INSERT into `credentials` table → CREATE/UPDATE `users` record | DB: user created/updated, credential stored | — |
| 1.7 | Backend | Creates JWT session | RS256-signed JWT (sub, exp, role, session_id) → stored in Redis → set HttpOnly Secure cookie | Redis: session created; Frontend: authenticated | — |
| 1.8 | Frontend | Redirects to `/dashboard` | `GET /api/v1/auth/me` → renders dashboard with empty repository state | Frontend: authenticated state | **DP4**: First login → show onboarding wizard; Returning → show dashboard |

### Phase 2: Repository Connection

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 2.1 | User | Clicks "Connect Repository" | `GET /api/v1/github/repositories` → lists user's GitHub repos (paginated) | Frontend: repository browser | — |
| 2.2 | GitHub | Returns repository list | Paginated response with `Link` headers; cached in Redis for 5 min | Redis: repo list cached | **DP5**: Zero repos → show "Create a repository" guidance |
| 2.3 | User | Searhes/filters and selects a repository | Frontend sends `POST /api/v1/repositories` with `{full_name, github_repo_id}` | Frontend: repo selected | — |
| 2.4 | Backend | Verifies repository access | `GET /repos/{owner}/{repo}` via GitHub API → checks visibility, archived status, permissions | GitHub: repo verified | **DP6**: Private repo + insufficient scope → prompt re-auth; Archived repo → warn user; Valid → continue |
| 2.5 | Backend | Creates repository record | INSERT into `repositories` with status "connected" | DB: repository record created | **DP7**: Duplicate (same user+repo) → return existing record |

### Phase 3: Repository Analysis

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 3.1 | User | Clicks "Analyze" on repo card | `POST /api/v1/analysis/{repo_id}/start` | Frontend: analysis triggering | — |
| 3.2 | Backend | Creates analysis job | INSERT into `analysis_jobs` (status: queued) → ENQUEUE to Redis queue `queue:analysis` | DB: job queued; Redis: message enqueued | — |
| 3.3 | Backend | Returns 202 Accepted | `{job_id: "uuid", status: "queued"}` → frontend opens WebSocket connection | Frontend: listening for progress | — |
| 3.4 | LangGraph Worker | Dequeues job from Redis | Worker picks up `{job_id, repository_id, user_id}` → `graph.ainvoke(initial_state)` | LangGraph: state machine started | — |
| 3.5 | Repo Analyzer Agent | Clones repository | `git clone --depth=1 --single-branch` → scans file tree → builds manifest | LangGraph State: `file_manifest`, `manifest_files` populated | **DP8**: Clone fails → fall back to GitHub Tree API; Repo > 100MB → skip clone, use API |
| 3.6 | Repo Analyzer Agent | Publishes progress | Redis PUBLISH `analysis:{job_id}` → WebSocket → Frontend shows "Scanning files... 25%" | Frontend: progress bar updates | — |
| 3.7 | Tech Detector Agent | Calls OpenRouter LLM | Structured prompt with file tree + manifests → LLM returns JSON classification | LangGraph State: `technologies` populated | **DP9**: LLM timeout → retry with truncated prompt; After 3 retries → heuristic-only mode |
| 3.8 | Tech Detector Agent | Cross-validates results | Compares LLM output against deterministic patterns (e.g., package.json → Node.js) | LangGraph State: `technologies` adjusted with confidence scores | **DP10**: Low confidence (<0.7) → mark as "uncertain" for user review |
| 3.9 | Tech Detector Agent | Publishes progress | Redis PUBLISH → Frontend shows "Analyzing technologies... 75%" | Frontend: progress bar updates | — |
| 3.10 | LangGraph | Completes execution | Extracts final state → INSERT into `analysis_results` → UPDATE `analysis_jobs` status="completed" | DB: results persisted | — |
| 3.11 | Backend | Notifies frontend | Redis PUBLISH "complete" → WebSocket → Frontend fetches `GET /api/v1/analysis/{job_id}/results` | Frontend: analysis results displayed | — |

### Phase 4: Security Assessment

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 4.1 | User | Reviews analysis results | Views technology cards with confidence scores; can confirm or correct uncertain detections | Frontend: analysis review | **DP11**: User corrects detection → system records correction for future few-shot learning |
| 4.2 | User | Clicks "Generate Workflow" | Frontend shows configuration panel: triggers, target branch, security tools selection | Frontend: workflow config form | — |
| 4.3 | User | Configures and submits | Selects triggers (push, PR, schedule), enables tools (default: all), clicks "Generate" | Frontend: config submitted | **DP12**: No security tools selected → warn "No security scanning"; minimum enforced (Gitleaks) |
| 4.4 | Security Requirement Agent | Infers security needs | LLM call with technology stack + OWASP mapping → returns `{required_tools, inferred_secrets}` | LangGraph State: `security_requirements` populated | — |

### Phase 5: Workflow Generation & Validation

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 5.1 | Workflow Generator Agent | Generates YAML | LLM call (model: secondary, temp=0.2) → structured prompt with tech + security context → returns complete workflow YAML | LangGraph State: `workflow_yaml` populated | **DP13**: Token limit exceeded → split generation (build → test → scan → deploy) |
| 5.2 | Workflow Generator Agent | Post-processes YAML | Strips markdown fences, validates YAML parse, adds header comment, formats indentation | LangGraph State: `workflow_yaml` cleaned | **DP14**: YAML parse fails at this stage → immediate syntax repair |
| 5.3 | Workflow Validator Agent | Validates workflow | 4-stage validation: (1) YAML syntax, (2) GitHub Actions schema, (3) security policy, (4) LLM semantic check | LangGraph State: `validation_errors`, `validation_passed` | **DP15**: Any ERROR → route to Repair Agent; All WARNING → allow with caution; All PASS → ready for PR |
| 5.4 | [IF VALIDATION FAILS] | Workflow Repair Agent | Classifies errors → applies fixes by category → LLM repair for semantics → returns repaired YAML | LangGraph State: `workflow_yaml` repaired, `repair_attempts` incremented | **DP16**: Attempt < 3 → re-validate; Attempt >= 3 → manual review; Loop detected → manual review |
| 5.5 | [RE-VALIDATION LOOP] | Validator re-checks repaired YAML | Same 4-stage validation on repaired output | LangGraph State: `validation_passed` updated | Back to DP15 |
| 5.6 | Backend | Returns result to frontend | `GET /api/v1/workflows/{id}` → YAML + validation status + AI explanations | Frontend: diff editor displayed | — |

### Phase 6: Pull Request Creation

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 6.1 | User | Reviews workflow in diff editor | Hovers over steps to see AI explanations; may edit YAML directly | Frontend: workflow review | **DP17**: User edits YAML → re-validate before PR creation |
| 6.2 | User | Clicks "Create Pull Request" | Frontend shows PR metadata form: auto-suggested branch name, title, description | Frontend: PR form | — |
| 6.3 | User | Confirms and submits | `POST /api/v1/pull-requests` with `{repo_id, workflow_id, title, description}` | Frontend: PR submission | — |
| 6.4 | Backend | Checks GitHub write access | `GET /repos/{owner}/{repo}` → checks `permissions.push == true` | GitHub: permissions verified | **DP18**: No write access → error: "Need write access to create PR" |
| 6.5 | Backend | Checks branch protection | `GET /repos/{owner}/{repo}/branches/{branch}/protection` | GitHub: protection rules fetched | **DP19**: Protection blocks PR → warn user; list requirements |
| 6.6 | Backend | Creates branch | `POST /repos/{owner}/{repo}/git/refs` → creates `devsecops/secure-workflow-{ts}` | GitHub: branch created | **DP20**: Branch exists → append suffix or update existing |
| 6.7 | Backend | Commits workflow file | `PUT /repos/{owner}/{repo}/contents/.github/workflows/{filename}.yml` | GitHub: file committed | — |
| 6.8 | Backend | Creates Pull Request | `POST /repos/{owner}/{repo}/pulls` → PR created on GitHub | GitHub: PR created | **DP21**: Duplicate PR → return existing PR URL |
| 6.9 | Backend | Stores PR metadata | INSERT into `pull_requests` table | DB: PR record created | — |
| 6.10 | Backend | Enqueues monitoring job | ENQUEUE to Redis `queue:monitoring` | Redis: monitoring job queued | — |
| 6.11 | Frontend | Shows success | Displays PR URL + link to GitHub | Frontend: success state | — |

### Phase 7: Workflow Execution & Monitoring

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 7.1 | GitHub Actions | Workflow triggered by PR | PR push triggers `pull_request` event → GitHub Actions starts workflow execution | GitHub: workflow running | — |
| 7.2 | Monitoring Worker | Dequeues monitoring job | Started polling loop: `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` every 15s (active) / 60s (idle) | Worker: polling active | **DP22**: Rate limited → wait until reset; Timeout → retry with backoff |
| 7.3 | Monitoring Worker | Tracks check statuses | Updates `workflow_runs` table with check statuses; publishes WebSocket updates | DB: check_runs updated; Frontend: real-time status | — |
| 7.4 | Security Tools | Execute in GitHub Actions | Semgrep, Gitleaks, Trivy, CodeQL, Dependency Review run sequentially/parallel | GitHub: scan results generated as artifacts | **DP23**: Tool fails → log failure; mark run as partial; investigate logs |
| 7.5 | GitHub Actions | Workflow completes | All checks have status "completed" → artifacts available | GitHub: run completed | **DP24**: All checks passed → success; Some failed → partial success; All failed → failed |
| 7.6 | Monitoring Worker | Detects completion | All checks "completed" → exits polling loop → downloads artifacts | Worker: processing results | — |
| 7.7 | Monitoring Worker | Downloads artifacts | `GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` → downloads SARIF + JSON files | Worker: artifacts downloaded | **DP25**: Artifact missing → mark as "incomplete"; files corrupted → log error |
| 7.8 | Monitoring Worker | Parses findings | Parses SARIF (CodeQL, Semgrep, Trivy), JSON (Gitleaks) → deduplicates → INSERT into `findings` | DB: findings persisted | — |

### Phase 8: Risk Assessment

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 8.1 | Risk Assessor Agent | Calculates risk score | Weighted scoring: Σ(severity_weight × cvss_mult × cwe_mult × exposure_mult) → normalize to 0-100 | LangGraph State: `risk_score` calculated | — |
| 8.2 | Risk Assessor Agent | Categorizes risk | Score mapping: >=75→CRITICAL, >=50→HIGH, >=25→MEDIUM, >=10→LOW, <10→MINIMAL | LangGraph State: `risk_category` set | — |
| 8.3 | [CONDITIONAL] | LLM qualitative assessment | IF risk_score >= 25: LLM call for qualitative analysis (key concerns, attack surface, compliance, urgency) | LangGraph State: `qualitative_assessment` populated | **DP26**: Score < 25 → skip LLM; Score >= 25 → invoke LLM |
| 8.4 | Risk Assessor Agent | Calculates trend | Linear regression on historical scores → "improving", "stable", "worsening", "worsening_significantly" | LangGraph State: `risk_trend` set | — |
| 8.5 | Risk Assessor Agent | Persists assessment | INSERT into `risk_assessments` table | DB: risk assessment stored | — |

### Phase 9: Recommendation Generation

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 9.1 | Recommendation Agent | Groups findings | Categorizes findings: dependency_updates, code_fixes, secret_removal, config_changes, cicd_hardening | LangGraph State: findings grouped | — |
| 9.2 | Recommendation Agent | Generates dependency fixes | For Trivy/Dependency Review findings: deterministic upgrade commands + version mapping | LangGraph State: dependency recommendations | — |
| 9.3 | Recommendation Agent | Generates code fixes | For Semgrep/CodeQL findings: LLM call with code context → fix diff + explanation | LangGraph State: code fix recommendations | **DP27**: LLM confidence < 0.7 → flag "requires_review"; Breaking change detected → add warning |
| 9.4 | Recommendation Agent | Generates secret removal recs | For Gitleaks findings: "Remove hardcoded secret at {file}:{line}, use environment variable" | LangGraph State: secret removal recommendations | — |
| 9.5 | Recommendation Agent | Persists recommendations | INSERT into `recommendations` table | DB: recommendations stored | — |

### Phase 10: Security Dashboard & Reporting

| Step | Actor | Action | System Response | State Transition | Decision Point |
|---|---|---|---|---|---|
| 10.1 | User | Navigates to Security Dashboard | `GET /api/v1/dashboard/summary?repo_id=X` → aggregated KPIs | Frontend: dashboard rendered | — |
| 10.2 | Frontend | Renders KPI cards | Total Scans, Vulnerabilities (by severity), Risk Score (with trend arrow), Compliance Status | Frontend: KPI cards with delta indicators | — |
| 10.3 | Frontend | Renders charts | Risk Score Trend (line chart), Vulnerabilities by Severity (doughnut), Findings by Tool (bar chart) | Frontend: charts rendered | — |
| 10.4 | User | Clicks severity segment in chart | `GET /api/v1/findings?repo_id=X&severity=critical` → filtered findings table | Frontend: filtered findings | — |
| 10.5 | User | Clicks "Details" on a finding | `GET /api/v1/findings/{id}` → code snippet, CWE/CVE, remediation preview | Frontend: finding detail modal | — |
| 10.6 | User | Triages finding | Selects triage status (false_positive, accepted_risk, fixed) → `PATCH /api/v1/findings/{id}/triage` | DB: triage status updated; Risk score recalculated | — |
| 10.7 | User | Views recommendations | `GET /api/v1/recommendations?repo_id=X` → categorized recommendation cards | Frontend: recommendations list | — |
| 10.8 | User | Clicks "Apply Fix" on recommendation | System creates branch with fix code → creates PR (auto-fixable) or shows manual instructions (non-auto) | GitHub: fix PR created | **DP28**: Auto-fixable + confidence >= 0.7 → auto-apply; Otherwise → manual apply required |
| 10.9 | User | Clicks "Export Report" | `GET /api/v1/reports/export?repo_id=X&format=pdf` → server generates PDF with all findings, scores, recommendations | Frontend: file download | **DP29**: Report too large → paginate; Format: PDF, JSON, CSV |
| 10.10 | User | Downloads report | Receives PDF file with cryptographic signature for non-repudiation | Frontend: download complete | — |

### END OF FLOW

---

## 12.2 Decision Point Summary Table

| DP# | Decision Point | Condition | Branch A (Happy Path) | Branch B (Alternative) |
|---|---|---|---|---|
| DP1 | OAuth authorization | User authorizes | Proceed to callback | Return to landing, show error |
| DP2 | CSRF state validation | State token matches | Exchange code for token | Reject with 400 |
| DP3 | Token exchange | GitHub returns 200 | Continue to session creation | Retry 1x, then error |
| DP4 | First login check | `user.created_at` is recent | Show onboarding wizard | Show dashboard |
| DP5 | Repository list | `repos.length > 0` | Show repository browser | Show "Create repo" guidance |
| DP6 | Repository access | Token has required scopes | Continue to record creation | Prompt re-auth |
| DP7 | Duplicate repo connection | Same user+repo exists | Return existing record | Create new record |
| DP8 | Clone success | Git exits with 0 | Continue with local analysis | Fall back to GitHub API |
| DP9 | LLM timeout | OpenRouter responds in time | Use LLM results | Retry/fallback to heuristic |
| DP10 | Confidence threshold | All >= 0.7 | Auto-accept | Flag for user review |
| DP11 | User correction | User modifies detection | Record correction | Use auto-detected value |
| DP12 | Security tools selected | `enabled_tools` not empty | Use user selection | Inject minimum baseline |
| DP13 | Token limit | Prompt fits in context | Single generation call | Split into stages |
| DP14 | YAML parse | Syntax is valid | Continue to validation | Immediate syntax repair |
| DP15 | Validation result | No ERRORs | Route to PR creation | Route to Repair Agent |
| DP16 | Repair attempts | Attempt < 3 | Re-validate | Manual review |
| DP17 | User edits YAML | YAML was modified | Re-validate | Use as-is |
| DP18 | Write access | User can push | Create branch | Show permissions error |
| DP19 | Branch protection | No blocking rules | Create PR | Warn user; list blockers |
| DP20 | Branch exists | Branch name unique | Create new branch | Append suffix / update |
| DP21 | Duplicate PR | No existing PR | Create PR | Return existing PR URL |
| DP22 | Rate limit | Headers show remaining > 0 | Continue polling | Wait until reset |
| DP23 | Tool execution | All jobs pass | Full success | Mark partial; investigate |
| DP24 | Workflow conclusion | All checks complete | Download artifacts | Handle incomplete run |
| DP25 | Artifact available | Artifact download OK | Parse findings | Mark incomplete |
| DP26 | Risk score threshold | Score >= 25 | Invoke LLM assessment | Skip LLM |
| DP27 | Recommendation confidence | >= 0.7 | Auto-apply available | Flag "requires_review" |
| DP28 | Auto-fixability | Auto-fixable + confidence OK | Auto-create fix PR | Manual instructions |
| DP29 | Report size | Within memory limits | Generate PDF | Paginate report |

---

## 12.3 System State at Each Phase

| Phase | Frontend State | Backend State | Database State | AI Layer State | GitHub State |
|---|---|---|---|---|---|
| 1. Auth | Landing/Authenticated | Session created | User, Credential records | Inactive | OAuth token active |
| 2. Connection | Repository browser | Repo list cached | Repository record | Inactive | Repo connected |
| 3. Analysis | Progress bar (WS) | Job processing | Job, Results records | Agent chain active | Repo content accessed |
| 4. Assessment | Analysis review | Results serving | Analysis results | Security Req Agent | Idle |
| 5. Generation | Diff editor | YAML serving | Workflow record | Gen+Valid+Repair active | Idle |
| 6. PR Creation | PR form → Success | PR processing | PR record | Complete | Branch, PR created |
| 7. Execution | Live status (WS) | Polling active | Run, Check records | Monitoring worker | Workflow running |
| 8. Risk | Dashboard loading | Risk calculating | Findings, Risk records | Risk Agent active | Workflow complete |
| 9. Recommendations | Recommendations tab | Recommendation serving | Recommendation records | Rec Agent active | Idle |
| 10. Reporting | Dashboard complete | Report generating | All data persisted | Complete | Idle |
