# 7. Sequence Diagram Description

## 7.1 Repository Analysis Sequence

### Actors
- **User**: The authenticated DevSecOps engineer
- **React Frontend**: The browser-based SPA
- **FastAPI Backend**: The API server handling HTTP requests
- **Redis Queue**: Job queue for async task processing
- **LangGraph Orchestrator**: The agent state machine
- **Repo Analyzer Agent**: Clones and scans repository
- **Tech Detector Agent**: LLM-powered technology classification
- **OpenRouter API**: External LLM service
- **GitHub API**: External GitHub REST API
- **PostgreSQL**: Primary database

### Interaction Flow

```
User          React FE      FastAPI      Redis Q      LangGraph     Repo        Tech        OpenRouter   GitHub API   PostgreSQL
  │              │             │            │            │          Analyzer     Detector        │            │             │
  │─Click───────▶│             │            │            │            │            │             │            │             │
  │ "Analyze"    │──POST──────▶│            │            │            │            │             │            │             │
  │              │ /analysis/  │            │            │            │            │             │            │             │
  │              │ {repo_id}/  │──INSERT───▶│            │            │            │             │            │             │
  │              │ start       │ analysis_  │            │            │            │             │            │             │
  │              │             │ job        │──ENQUEUE──▶│            │            │             │            │             │
  │              │             │            │            │            │            │             │            │             │
  │              │◀──202───────│            │            │            │            │             │            │             │
  │              │ {job_id}    │            │◀──DEQUEUE──│            │            │             │            │             │
  │              │             │            │            │──INVOKE──▶│            │             │            │             │
  │              │             │            │            │            │──GET──────▶│             │            │             │
  │              │             │            │            │            │ /repos/*   │             │            │             │
  │              │             │            │            │            │◀──200──────│             │            │             │
  │              │             │            │            │            │ repo data  │             │            │             │
  │              │             │            │            │            │──git clone─│             │            │             │
  │              │             │            │            │            │ (shallow)  │             │            │             │
  │              │             │            │            │            │──scan─────▶│             │            │             │
  │              │             │            │            │            │ file tree  │             │            │             │
  │              │──WS connect▶│            │            │            │            │             │            │             │
  │              │ /ws/{job_id}│            │◀──PUBLISH──│◀───────────│            │             │            │             │
  │              │◀──progress──│            │ "scanning" │            │            │             │            │             │
  │              │ 25%         │            │            │            │──PASS────▶│             │            │             │
  │              │             │            │            │            │ state      │──POST──────▶│            │             │
  │              │             │            │            │            │            │ /chat/comp  │            │             │
  │              │             │            │            │            │            │◀──200──────│            │             │
  │              │             │            │            │            │            │ JSON struct │            │             │
  │              │             │            │            │            │            │◀──PASS─────│            │             │
  │              │             │            │            │◀──STATE───│            │ state       │            │             │
  │              │             │            │            │ updated    │            │             │            │             │
  │              │             │◀──PUBLISH──│◀───────────│            │            │             │            │             │
  │              │◀──progress──│ "analyzing│            │            │            │             │            │             │
  │              │ 75%         │"           │            │            │            │             │            │             │
  │              │             │            │            │──COMPLETE─│            │             │            │             │
  │              │             │            │            │            │            │             │──UPDATE────▶│             │
  │              │             │            │            │            │            │             │ analysis_   │             │
  │              │             │            │            │            │            │             │ jobs        │             │
  │              │             │            │            │            │            │             │──INSERT────▶│             │
  │              │             │            │            │            │            │             │ analysis_   │             │
  │              │             │            │            │            │            │             │ results     │             │
  │              │◀──GET───────│            │            │            │            │             │             │             │
  │              │ /analysis/  │──SELECT───▶│            │            │            │             │             │             │
  │              │ {job_id}/   │            │            │            │            │             │             │◀───────────│
  │              │ results     │◀───────────│            │            │            │             │             │             │
  │              │◀──200───────│            │            │            │            │             │             │             │
  │              │ technologies│            │            │            │            │             │             │             │
  │              │             │            │            │            │            │             │             │             │
  │─View────────▶│             │            │            │            │            │             │             │             │
  │  results     │             │            │            │            │            │             │             │             │
```

### Key Interaction Details

1. **Job Creation**: The frontend POSTs to `/api/v1/analysis/{repo_id}/start`. The backend creates an `analysis_jobs` record and enqueues a message to Redis. Returns `202 Accepted` with `{job_id}` immediately (non-blocking).

2. **Dequeue & Invoke**: A background worker continuously polls the Redis queue. Upon dequeuing, it invokes `graph.ainvoke(initial_state)` which enters the LangGraph orchestration.

3. **Real-Time Progress**: Each agent node publishes status updates to Redis Pub/Sub channel `analysis:{job_id}`. The FastAPI WebSocket handler subscribes to this channel and pushes updates to the connected frontend.

4. **GitHub API Interaction**: The Repo Analyzer calls `GET /repos/{owner}/{repo}` for metadata and `git clone --depth=1` for cloning. If the clone fails, it falls back to `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`.

5. **OpenRouter Interaction**: The Tech Detector sends a structured prompt to OpenRouter's chat completions endpoint with `response_format: {type: "json_object"}` for guaranteed JSON output.

6. **Database Persistence**: After LangGraph completes, the final state is extracted and persisted to `analysis_results` as JSONB. The job status is updated to "completed."

---

## 7.2 Workflow Generation Sequence

### Actors
- **User**
- **React Frontend**
- **FastAPI Backend**
- **LangGraph Orchestrator**
- **Security Requirement Agent**
- **Workflow Generator Agent**
- **Workflow Validator Agent**
- **Workflow Repair Agent**
- **OpenRouter API**
- **PostgreSQL**

### Interaction Flow

```
User         React FE       FastAPI       LangGraph     SecReq        WorkflowGen    Validator     Repair       OpenRouter    PostgreSQL
  │             │              │              │            │              │             │             │              │            │
  │─Config─────▶│              │              │            │              │             │             │              │            │
  │ triggers,   │──POST───────▶│              │            │              │             │             │              │            │
  │ tools       │ /workflows/  │              │            │              │             │             │              │            │
  │             │ generate     │──ENQUEUE─────▶│            │              │             │             │              │            │
  │             │              │              │──INVOKE───▶│              │             │             │              │            │
  │             │              │              │            │──POST───────▶│             │             │              │            │
  │             │              │              │            │ OpenRouter   │             │             │              │            │
  │             │              │              │            │◀──200───────│             │             │              │            │
  │             │              │              │            │ sec. reqs   │             │             │              │            │
  │             │              │              │            │──PASS──────▶│             │             │              │            │
  │             │              │              │            │ state        │──POST──────▶│             │              │            │
  │             │              │              │            │              │ OpenRouter  │             │              │            │
  │             │              │              │            │              │◀──200──────│             │              │            │
  │             │              │              │            │              │ workflow    │             │              │            │
  │             │              │              │            │              │ YAML        │             │              │            │
  │             │              │              │            │              │──PASS──────▶│             │              │            │
  │             │              │              │            │              │ state       │──VALIDATE──▶│              │            │
  │             │              │              │            │              │             │             │              │            │
  │             │              │              │            │              │             │ [ALT: Validation FAILS]
  │             │              │              │            │              │             │──PASS──────▶│              │            │
  │             │              │              │            │              │             │ errors      │──POST───────▶│            │
  │             │              │              │            │              │             │             │ OpenRouter   │            │
  │             │              │              │            │              │             │             │◀──200───────│            │
  │             │              │              │            │              │             │             │ fixed YAML  │            │
  │             │              │              │            │              │             │◀──PASS──────│              │            │
  │             │              │              │            │              │             │ repaired    │              │            │
  │             │              │              │            │              │             │──VALIDATE──▶│              │            │
  │             │              │              │            │              │             │             │ (re-run)     │            │
  │             │              │              │            │              │             │             │              │            │
  │             │              │              │ [END ALT: Validation PASSES]
  │             │              │              │            │              │             │──PASS──────▶│              │            │
  │             │              │              │            │              │             │ "passed"    │              │            │
  │             │              │              │◀──STATE────│              │             │             │              │            │
  │             │              │              │ complete   │              │             │             │              │            │
  │             │              │              │───────────▶│              │             │             │              │            │
  │             │              │              │            │              │             │             │              │──INSERT───▶│
  │             │              │              │            │              │             │             │              │ workflows  │
  │             │◀──GET────────│              │            │              │             │             │              │            │
  │             │ /workflows/  │──SELECT─────▶│            │              │             │             │              │◀──────────│
  │             │ {id}         │◀────────────│            │              │             │             │              │            │
  │◀───────────│              │              │            │              │             │             │              │            │
  │ View diff  │              │              │            │              │             │             │              │            │
  │ editor     │              │              │            │              │             │             │              │            │
```

### Key Interaction Details

1. **User Configuration Input**: Before generation, the user selects trigger events (push, PR, schedule), target branch, and which security tools to enable/disable.

2. **Sequential Agent Execution**: LangGraph orchestrator invokes Security Requirement Agent first (to determine what scans are needed), then passes state to Workflow Generator Agent.

3. **Validation-Repair Loop**: If the Validator finds errors, it passes them to the Repair Agent (not back to the Generator). The Repair Agent fixes and returns the repaired YAML to the Validator for re-evaluation. This loop continues up to 3 times.

4. **Persistence**: On completion, both the original and final YAML are stored in the `workflows` table with the entire generation history for audit purposes.

---

## 7.3 Pull Request Creation Sequence

### Actors
- **User**
- **React Frontend**
- **FastAPI Backend**
- **GitHub API**
- **PostgreSQL**
- **Redis (for monitoring queue)**

### Interaction Flow

```
User         React FE       FastAPI       GitHub API      PostgreSQL       Redis
  │             │              │              │               │               │
  │─Review─────▶│              │              │               │               │
  │ workflow    │              │              │               │               │
  │─Click──────▶│              │              │               │               │
  │ "Create PR" │──POST───────▶│              │               │               │
  │             │ /pull-requests│             │               │               │
  │             │ {repo_id,     │              │               │               │
  │             │  workflow_yaml│─GET refs────▶│               │               │
  │             │  title, desc} │ /git/refs/   │               │               │
  │             │              │ heads/main   │               │               │
  │             │              │◀──200────────│               │               │
  │             │              │ ref.sha      │               │               │
  │             │              │              │               │               │
  │             │              │──POST refs───▶│               │               │
  │             │              │ /git/refs    │               │               │
  │             │              │ branch=      │               │               │
  │             │              │ devsecops/.. │               │               │
  │             │              │◀──201────────│               │               │
  │             │              │ new branch   │               │               │
  │             │              │              │               │               │
  │             │              │──PUT file────▶│               │               │
  │             │              │ /contents/   │               │               │
  │             │              │ .github/     │               │               │
  │             │              │ workflows/   │               │               │
  │             │              │ *.yml        │               │               │
  │             │              │◀──201────────│               │               │
  │             │              │ commit sha   │               │               │
  │             │              │              │               │               │
  │             │              │──POST PR─────▶│               │               │
  │             │              │ /pulls       │               │               │
  │             │              │◀──201────────│               │               │
  │             │              │ PR #42, URL  │               │               │
  │             │              │              │               │               │
  │             │              │──INSERT──────▶───────────────▶               │
  │             │              │ pull_requests│               │               │
  │             │              │              │               │               │
  │             │              │──ENQUEUE─────▶──────────────────────────────▶│
  │             │              │ monitoring   │               │               │
  │             │              │ job          │               │               │
  │             │              │              │               │               │
  │◀───────────│◀──200────────│              │               │               │
  │ PR created │ {pr_url,      │              │               │               │
  │ + link     │  pr_number}   │              │               │               │
  │             │              │              │               │               │
  │─Click link─▶│ (external redirect to github.com/{owner}/{repo}/pull/42)
```

### Key Interaction Details

1. **Branch Creation**: The system gets the SHA of the default branch's latest commit via `GET /repos/{owner}/{repo}/git/refs/heads/{branch}`, then creates a new branch from that SHA via `POST /repos/{owner}/{repo}/git/refs`.

2. **File Commit**: The workflow YAML is committed to the new branch via `PUT /repos/{owner}/{repo}/contents/.github/workflows/{filename}.yml` with a descriptive commit message.

3. **PR Creation**: The PR is opened from the new branch to the default branch. The PR body is auto-generated with technology summary and enabled security tools list.

4. **Monitoring Job Enqueue**: After PR creation, a monitoring job is enqueued to Redis. A background worker will poll the GitHub Checks API for workflow execution status.

5. **Idempotency**: If a PR already exists for the same branch (detected via branch name), the system returns the existing PR URL instead of creating a duplicate.

---

## 7.4 Security Scan Result Analysis Sequence

### Actors
- **GitHub Actions** (workflow runners)
- **FastAPI Monitoring Worker**
- **GitHub API**
- **Risk Assessor Agent**
- **Recommendation Agent**
- **OpenRouter API**
- **PostgreSQL**
- **User / React Frontend**

### Interaction Flow

```
GitHub Actions   Worker      GitHub API     Risk Assessor   Recommend.    OpenRouter    PostgreSQL     User/FE
     │             │              │              │              │             │              │             │
     │──Complete──▶│              │              │              │             │              │             │
     │ (webhook/   │              │              │              │             │              │             │
     │  polling)   │──GET checks─▶│              │              │             │              │             │
     │             │ /commits/*/  │              │              │             │              │             │
     │             │ check-runs   │              │              │             │              │             │
     │             │◀──200────────│              │              │             │              │             │
     │             │ check_runs[] │              │              │             │              │             │
     │             │              │              │              │             │              │             │
     │             │──GET artifacts▶              │              │             │              │             │
     │             │ /actions/    │              │              │             │              │             │
     │             │ runs/{id}/   │              │              │             │              │             │
     │             │ artifacts    │              │              │             │              │             │
     │             │◀──200────────│              │              │             │              │             │
     │             │ artifacts[]  │              │              │             │              │             │
     │             │              │              │              │             │              │             │
     │             │──DOWNLOAD & PARSE each artifact──▶        │             │              │             │
     │             │ Semgrep SARIF, Gitleaks JSON, Trivy SARIF, CodeQL SARIF  │              │             │
     │             │              │              │              │             │              │             │
     │             │──DEDUPLICATE & INSERT────────▶─────────────▶──────────────▶              │             │
     │             │              │              │              │             │ findings      │             │
     │             │              │              │              │             │              │             │
     │             │──INVOKE─────▶│              │              │             │              │             │
     │             │              │──CALCULATE──▶│              │             │              │             │
     │             │              │ risk score   │──POST───────▶─────────────▶              │             │
     │             │              │              │ OpenRouter   │             │              │             │
     │             │              │              │◀──200───────│             │              │             │
     │             │              │              │ qual. assess│             │              │             │
     │             │              │              │──INSERT─────▶─────────────▶───────────────▶             │
     │             │              │              │ risk_       │             │ risk_scores   │             │
     │             │              │              │ assessments │             │              │             │
     │             │              │              │              │             │              │             │
     │             │              │              │──PASS──────▶│             │              │             │
     │             │              │              │ state        │──POST──────▶──────────────▶             │
     │             │              │              │              │ OpenRouter  │              │             │
     │             │              │              │              │◀──200──────│              │             │
     │             │              │              │              │ code fixes  │              │             │
     │             │              │              │              │──INSERT─────▶──────────────▶             │
     │             │              │              │              │ recommend.  │ recommend-    │             │
     │             │              │              │              │             │ ations       │             │
     │             │              │              │              │             │              │             │
     │             │──SEND NOTIFICATION──────────▶──────────────▶─────────────▶──────────────▶             │
     │             │              │              │              │             │              │─in-app notif▶│
     │             │              │              │              │             │              │              │
     │             │              │              │              │             │              │──GET────────▶│
     │             │              │              │              │             │              │ /dashboard/  │
     │             │              │              │              │             │              │ summary      │
     │             │              │              │              │             │◀─────────────│              │
     │             │◀─────────────────────────────│              │             │              │              │
     │             │              │              │              │             │              │◀─View dash──│
     │             │              │              │              │             │              │  board      │
```

### Key Interaction Details

1. **Workflow Completion Detection**: The monitoring worker polls `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` every 15 seconds during active execution. When all check runs have status "completed," the worker exits the polling loop.

2. **Artifact Download & Parsing**: Each security tool uploads results as workflow artifacts (SARIF for Semgrep/Trivy/CodeQL, JSON for Gitleaks). The worker downloads each artifact ZIP, extracts, parses, and deduplicates findings.

3. **Risk Assessment Trigger**: After findings are persisted, the worker invokes the Risk Assessor Agent. If the normalized risk score is >= 25, the agent makes an LLM call for qualitative assessment.

4. **Recommendation Trigger**: The Risk Assessor passes state to the Recommendation Agent, which generates code fixes for code-level findings via LLM and deterministic upgrade commands for dependency findings.

5. **Notification & Dashboard**: After all processing, the worker publishes a Redis notification event. The WebSocket handler pushes this to the frontend, which fetches updated dashboard data via REST API.
