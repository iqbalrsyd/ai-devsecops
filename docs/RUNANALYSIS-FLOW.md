# RunAnalysis - Security Analysis Page

## Overview

`RunAnalysis` adalah halaman dedicated yang menampilkan hasil security analysis dari pipeline run. Halaman ini fokus pada:
- Security scores visualization
- Findings breakdown
- Compliance mapping
- Recommendations

**URL:** `/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId/analysis`

---

## Data Flow

```
User navigates to RunAnalysis page
       ↓
useRunAnalysis(runId) - Fetch from /api/v1/runs/:runId/analysis
       ↓
Backend checks pipeline_analyses table
       ↓
If exists → Return cached analysis
If not exists → Trigger AI analysis via LangGraph
       ↓
AI Service pipeline:
  - security_analyzer (scan findings)
  - risk_assessor (calculate risk score)
  - compliance_mapper (map to compliance standards)
  - recommendation_gen (generate recommendations)
  - response_formatter (format output)
       ↓
Store in pipeline_analyses table
       ↓
Return to frontend

┌─────────────────────────────────────────────────────────────────────────┐
│                        AI ANALYSIS PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────┘

security_analyzer_node
       ↓
  - Parse scan results (trivy, semgrep, gitleaks)
  - Categorize findings by severity
  - Identify vulnerable dependencies
  - Detect secrets/credentials exposed
       ↓
risk_assessor_node
       ↓
  - Calculate risk score (0-100)
  - Factor in: severity, count, exploitability
  - Generate risk level (low/medium/high/critical)
       ↓
compliance_mapper_node
       ↓
  - Map findings to OWASP Top 10
  - Map to CIS Benchmarks
  - Map to SOC2 controls
  - Calculate compliance score
       ↓
recommendation_gen_node
       ↓
  - Generate actionable recommendations
  - Prioritize by risk level
  - Provide remediation steps
       ↓
response_formatter_node
       ↓
  - Format unified response
  - Include explanations
  - Add metadata
```

---

## Components Structure

```
RunAnalysis
├── Header (breadcrumbs)
│
├── Summary Section
│   ├── Risk Score Gauge
│   ├── Compliance Score
│   ├── Security Coverage
│   └── Workflow Quality
│
├── Severity Breakdown
│   ├── Critical (count)
│   ├── High (count)
│   ├── Medium (count)
│   └── Low (count)
│
├── Findings Summary
│   ├── By Scanner (trivy, semgrep, gitleaks, etc.)
│   ├── By Type (vulnerability, secret, misconfig)
│   └── By File (grouped by file location)
│
├── Compliance Mapping
│   ├── OWASP Top 10
│   ├── CIS Benchmarks
│   └── Custom Controls
│
├── Recommendations
│   ├── High Priority
│   ├── Medium Priority
│   └── Low Priority
│
└── AI Explanation
    └── Detailed analysis text
```

---

## Score Calculation

### Risk Score
```python
# Simplified calculation
base_score = 0

for finding in findings:
    severity_weight = {
        "critical": 40,
        "high": 25,
        "medium": 15,
        "low": 5
    }
    base_score += severity_weight.get(finding.severity, 10)

# Normalize to 0-100
risk_score = min(base_score / len(findings) * 10, 100) if findings else 0

# Factors:
# - Number of findings
# - Severity distribution
# - Exploitability (based on CVSS if available)
# - Attack complexity
```

### Compliance Score
```python
# Based on compliance mappings
total_controls = len(all_controls)
passed_controls = len([c for c in controls if c.status == "passed"])

compliance_score = (passed_controls / total_controls * 100) if total_controls > 0 else 0

# Mapped frameworks:
# - OWASP Top 10 (web security)
# - CIS Benchmarks (system hardening)
# - SOC2 (security, availability)
# - GDPR (data protection)
```

### Security Coverage
```python
# Based on security controls in workflow
required_controls = ["sast", "secret_scan", "dep_scan", "container_scan"]
implemented_controls = [c for c in required_controls if pipeline_has(c)]

coverage = len(implemented_controls) / len(required_controls) * 100
```

### Workflow Quality
```python
# Based on workflow configuration
quality_factors = {
    "actions_pinned": 25,      # SHA pinning
    "permissions_minimal": 25, # Least privilege
    "fail_fast_false": 15,     # Complete all jobs
    "timeout_configured": 15,   # Prevent hung jobs
    "concurrency_set": 10,     # Prevent duplicate runs
    "validation_passed": 10    # YAML valid
}

quality_score = sum(quality_factors.values())
```

---

## Severity Thresholds

| Level | Score Range | Color | Action |
|-------|------------|-------|--------|
| Critical | 70-100 | Red | Immediate fix required |
| High | 40-69 | Orange | Fix within 1 week |
| Medium | 20-39 | Yellow | Fix within 2 weeks |
| Low | 0-19 | Green | Fix when possible |

---

## Findings Categories

### By Scanner
| Scanner | Purpose | Detects |
|---------|---------|---------|
| Trivy | Container & filesystem scan | Vulnerabilities, misconfigs |
| Semgrep | SAST | Code security issues |
| Gitleaks | Secret detection | Exposed credentials |
| CodeQL | Security analysis | Vulnerabilities, code smells |
| Checkov | IaC scanning | Terraform/K8s issues |

### By Type
| Type | Description |
|------|-------------|
| vulnerability | Known CVE in dependencies |
| secret | API keys, passwords, tokens exposed |
| misconfiguration | Security misconfiguration |
| code_quality | Code that could lead to issues |
| license | License compliance issues |

---

## Compliance Mapping

### OWASP Top 10 (2021)
| Category | Mapped Controls |
|----------|-----------------|
| A01 | Broken Access Control → SAST |
| A02 | Cryptographic Failures → Container Scan |
| A03 | Injection → SAST, Dependency Scan |
| A04 | Insecure Design → SAST |
| A05 | Security Misconfiguration → IaC Scan |
| A06 | Vulnerable Components → Dependency Scan |
| A07 | Auth Failures → Secret Scan |
| A08 | Data Integrity Failures → SBOM |
| A09 | Logging Failures → Workflow Quality |
| A10 | Server-Side Request Forgery → SAST |

### CIS Benchmarks
| Control | Description |
|---------|-------------|
| CIS 1.1 | Filesystem permissions |
| CIS 2.1 | Secrets management |
| CIS 3.1 | Network configuration |
| CIS 4.1 | Container security |

---

## Recommendations Priority

### High Priority
- Critical severity findings
- Secrets exposure
- Known CVEs with exploits available

### Medium Priority
- High severity findings
- Misconfigurations with security impact
- Outdated dependencies

### Low Priority
- Code quality issues
- Minor misconfigurations
- Informational findings

---

## Hook: useRunAnalysis

```typescript
// frontend/src/hooks/usePipelinesV2.ts

export function useRunAnalysis(runId: string | undefined) {
  return useQuery({
    queryKey: ["run-analysis", runId],
    queryFn: async () => {
      const res = await api.get(`/runs/${runId}/analysis`)
      return res.data
    },
    enabled: !!runId,
    retry: 2,
  })
}
```

**Response:**
```json
{
  "risk_score": 45.5,
  "risk_level": "medium",
  "compliance_score": 85.0,
  "security_coverage_score": 78.0,
  "workflow_quality_score": 92.0,
  "findings_summary": [
    {
      "scanner": "trivy",
      "severity": "high",
      "type": "vulnerability",
      "title": "CVE-2024-1234 in lodash@4.17.20",
      "explanation": "...",
      "recommendation": "Upgrade to lodash@4.17.21"
    }
  ],
  "severity_breakdown": {
    "critical": 4,
    "high": 4,
    "medium": 2,
    "low": 0
  },
  "recommendations": [
    {
      "title": "Upgrade vulnerable dependencies",
      "description": "...",
      "remediation": "npm audit fix",
      "priority": "high"
    }
  ],
  "compliance_mappings": [
    {
      "framework": "OWASP",
      "control_id": "A01",
      "control_name": "Broken Access Control",
      "status": "failed"
    }
  ],
  "ai_explanation": "The pipeline detected 10 security findings..."
}
```

---

## Database Schema

### pipeline_analyses
```sql
CREATE TABLE pipeline_analyses (
  id UUID PRIMARY KEY,
  pipeline_run_id UUID REFERENCES pipeline_runs(id) UNIQUE,
  
  -- Scores
  risk_score FLOAT,
  security_posture FLOAT,
  compliance_score FLOAT,
  workflow_quality_score FLOAT,
  security_coverage_score FLOAT,
  
  -- Analysis data
  findings_summary JSONB,        -- Array of finding objects
  severity_breakdown JSONB,      -- {critical: n, high: n, ...}
  recommendations JSONB,        -- Array of recommendation objects
  compliance_mappings JSONB,      -- Array of compliance mappings
  
  -- AI output
  ai_explanation TEXT,
  raw_scan_data JSONB,          -- Raw scan results
  
  created_at TIMESTAMP
);
```

---

## File Locations

| File | Path | Description |
|------|------|-------------|
| Page | `frontend/src/pages/RunAnalysis.tsx` | Analysis page component |
| Hooks | `frontend/src/hooks/usePipelinesV2.ts` | useRunAnalysis hook |
| Backend | `ai-service/app/services/pipeline_service.py` | Analysis generation |
| AI Nodes | `ai-service/app/agents/nodes/` | Security analyzer, risk assessor, etc. |

---

## Related Pages

| Page | URL | Description |
|------|-----|-------------|
| RunDetail | `/runs/:runId` | Job execution details |
| RunAnalysis | `/runs/:runId/analysis` | Security analysis (current) |
| PipelineVersionDetail | `/pipelines/:version` | Pipeline overview |

---

## Common Issues

### "Analysis not found"
- Run might not have completed
- Analysis might still be generating
- Check pipeline_analyses table in DB

### Scores show 0.0
- Analysis not generated yet
- Check /api/v1/runs/:runId/analysis endpoint
- Verify AI service is running

### "No findings"
- Pipeline might not have security scanning
- Check if security controls are implemented
- Verify scan tools ran successfully