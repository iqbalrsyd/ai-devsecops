# 1. Stakeholder Analysis

## 1.1 Stakeholder Identification Matrix

| Stakeholder Type | Role | Criticality | Engagement Frequency |
|---|---|---|---|
| Primary Users | Direct system operators | High | Daily |
| Secondary Users | Consumers of system outputs | Medium | Weekly |
| System Administrators | Platform maintainers | High | As needed |
| Repository Owners | Source code custodians | Critical | Per-operation |

## 1.2 Primary Users — DevSecOps Engineers & Developers

### Responsibilities
- Initiate repository connections via GitHub OAuth
- Trigger repository analysis operations
- Review AI-generated GitHub Actions workflow proposals
- Approve or reject generated Pull Requests
- Monitor CI/CD pipeline execution results through the security dashboard
- Review security risk scores and remediation recommendations
- Configure security tool preferences (enable/disable Semgrep, Gitleaks, Trivy, CodeQL, Dependency Review)
- Provide feedback on AI-generated workflows via the UI (thumbs up/down or explicit correction input)
- Manage personal GitHub Personal Access Token (PAT) scopes

### Interactions with System
1. Authenticate via GitHub OAuth 2.0 Authorization Code Grant flow
2. Select target repository from an OAuth-scoped repository list
3. Observe real-time analysis progress via WebSocket or polling
4. View generated workflow YAML in a syntax-highlighted diff editor
5. Receive AI-explanation text for every generated step
6. Respond to validation failures by approving AI-suggested repairs
7. Browse historical security reports with time-series drill-down
8. Export security reports as PDF or JSON for compliance audits

### Success Criteria from Primary User Perspective
- 90% of generated workflows pass GitHub Actions schema validation on the first attempt
- Semantic correctness of generated workflows (i.e., the pipeline actually builds, tests, and deploys correctly) exceeds 80%
- Repository analysis phase completes in under 60 seconds for repositories up to 50 MB
- Security risk scores correlate with manual expert assessment within ±15% margin

## 1.3 Secondary Users — Security Auditors & Compliance Officers

### Responsibilities
- Review consolidated security reports across multiple repositories
- Verify completeness of security scans (confirm all five tools executed)
- Validate that generated workflows include mandatory security gates
- Cross-reference AI risk scores with organizational risk thresholds
- Export compliance evidence for frameworks such as SOC 2, ISO 27001, or OWASP ASVS
- Define organization-wide security baselines (minimum scan coverage requirements)
- Audit AI decision logs for explainability and bias analysis

### Interactions with System
1. Log in with GitHub OAuth (same as primary users)
2. Navigate to the Security Dashboard with organization-wide scope
3. Filter reports by repository, time range, severity level, or CWE category
4. Drill down into individual scan results (Semgrep rule violations, Gitleaks findings, Trivy CVEs)
5. Examine AI-generated remediation recommendations with confidence scores
6. Export reports with cryptographic digital signatures for non-repudiation
7. Set policy thresholds that gate PR approval (e.g., "critical vulnerabilities block merge")

### Success Criteria from Secondary User Perspective
- All security findings are traceable to the originating scan tool and rule identifier
- Remediation recommendations cite specific CWE/CVE identifiers where applicable
- Report generation and export complete in under 10 seconds
- Policy enforcement operates automatically without manual intervention

## 1.4 System Administrators — Platform Operators

### Responsibilities
- Deploy and maintain the FastAPI backend, PostgreSQL database, and Redis cache
- Manage OpenRouter API key rotation and rate-limit monitoring
- Monitor system health via observability endpoints (Prometheus metrics, structured logging)
- Perform database backup and recovery operations
- Manage horizontal scaling of LangGraph agent workers
- Rotate GitHub App private keys and webhook secrets
- Configure network firewall rules and ingress/egress policies
- Maintain infrastructure-as-code (Terraform/Ansible) for reproducible deployments
- Monitor cost attribution (OpenRouter token usage per user/repository)

### Interactions with System
1. Deploy via Docker Compose (development) or Kubernetes (production)
2. Access health-check endpoints: `/api/v1/health`, `/api/v1/health/ready`, `/api/v1/health/live`
3. View structured logs in JSON format via ELK stack or Grafana Loki
4. Receive PagerDuty/Opsgenie alerts on critical failure conditions
5. Execute database migrations using Alembic CLI
6. Rotate secrets via HashiCorp Vault or sealed Kubernetes secrets
7. Scale LangGraph worker replicas via `docker-compose up --scale agent-worker=N`

### Success Criteria from Administrator Perspective
- System availability (uptime) >= 99.5% during business hours
- Mean time to recovery (MTTR) after critical failure < 15 minutes
- Database backup recovery point objective (RPO) < 1 hour
- All secrets rotated without service interruption

## 1.5 Repository Owners — GitHub Repository Administrators

### Responsibilities
- Grant repository access to the DevSecOps Agent GitHub App
- Configure branch protection rules that accept AI-generated PRs
- Review and merge AI-generated PRs into target branches
- Configure required status checks (must pass before merge)
- Manage repository secrets (Docker Hub credentials, cloud provider keys) that the generated workflows reference
- Define CODEOWNERS and required reviewers for AI-generated changes
- Monitor PR merge frequency and reject patterns for anomaly detection

### Interactions with System
1. Install the GitHub App on target repositories (one-time setup)
2. Receive GitHub notification when an AI-generated PR is opened
3. Review PR diff in GitHub UI or the platform's built-in diff viewer
4. Observe required status checks running before merge is unblocked
5. Merge or close AI-generated PRs
6. Review automatic workflow execution results in the GitHub Actions tab
7. Report false positives or incorrect workflow steps via the platform feedback mechanism

### Success Criteria from Repository Owner Perspective
- AI-generated PR diff is readable and logically organized
- No sensitive tokens or secrets appear in generated workflow YAML
- Generated workflows respect existing `.github/workflows/` files (no destructive overwrite)
- PR description includes a summary of detected technologies and security requirements

## 1.6 Stakeholder Communication & Feedback Loops

```
Primary User  ──(feedback)──▶  AI Layer (LangGraph RLHF loop)
       │                              │
       │                              ▼
       │                    OpenRouter LLM Model
       │                              │
       ▼                              ▼
  GitHub PR  ◀──(automated)──  Workflow Generator Agent
```

### Feedback Mechanisms
1. **Explicit Feedback**: Users rate generated workflows (1-5 stars) and provide textual correction notes
2. **Implicit Feedback**: Merge/reject rate of AI-generated PRs; rejection signals are analyzed by the AI layer for self-improvement
3. **Administrative Feedback**: System administrators adjust agent temperature, token limits, and model selection via configuration files
4. **Audit Feedback**: Security auditors may override AI-determined risk scores with manual assessments, feeding back into the scoring calibration model

## 1.7 Stakeholder Conflict Resolution

| Conflict Scenario | Resolution Strategy |
|---|---|
| Primary user wants minimal security scans; secondary user requires comprehensive scans | System enforces configurable minimum baseline; user may add but not remove mandatory scans |
| Repository owner denies PR merge; primary user wants to merge | System respects repository owner authority; escalates notification to primary user with explanation |
| Administrator rate-limits OpenRouter; users experience delays | Queue-based throttling with user-facing estimated wait time; administrators can provision burst capacity |
| Security auditor marks a finding as false positive; AI insists it is a true positive | System records both assessments; final disposition decided by human with audit trail |
