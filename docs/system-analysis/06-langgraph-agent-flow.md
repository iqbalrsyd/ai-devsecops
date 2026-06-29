# 6. LangGraph Agent Flow — Multi-Agent Architecture

## 6.1 Agent Architecture Overview

The system implements a **hierarchical multi-agent architecture** using LangGraph's StateGraph, where a central **Orchestrator Agent** coordinates eight specialized sub-agents. Communication follows a **blackboard pattern** via a shared `AgentState` dictionary, enabling both sequential and conditional agent execution.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR AGENT                                   │
│                   (LangGraph StateGraph)                                 │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SHARED STATE (AgentState)                     │    │
│  │  repository_id | file_tree | technologies | workflow_yaml       │    │
│  │  validation_errors | repair_attempts | findings | risk_score    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│        │              │              │              │                   │
│        ▼              ▼              ▼              ▼                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  Repo    │  │  Tech    │  │ Security │  │ Workflow │               │
│  │ Analyzer │─▶│ Detector │─▶│  Req     │─▶│ Generator│               │
│  │ Agent    │  │ Agent    │  │ Agent    │  │ Agent    │               │
│  └──────────┘  └──────────┘  └──────────┘  └─────┬────┘               │
│                                                   │                     │
│                                          ┌────────▼────────┐           │
│                                          │  Validator      │           │
│                                          │  Agent          │           │
│                                          └────┬───────┬────┘           │
│                                               │       │                │
│                                          Pass │       │ Fail           │
│                                               │       │                │
│                                    ┌──────────▼┐  ┌───▼──────────┐    │
│                                    │ PR Service │  │ Repair Agent │    │
│                                    │ (API Call) │  └───┬──────┬───┘    │
│                                    └────────────┘      │      │        │
│                                                   Pass │      │ Fail   │
│                                                        │  ┌───▼─────┐  │
│                           ┌────────────────────────────┘  │ Manual  │  │
│                           │ (loop back to Validator)      │ Review  │  │
│                           ▼                               └────┬────┘  │
│                    ┌──────────────┐                            │       │
│                    │  Risk        │◀───────────────────────────┘       │
│                    │  Assessment  │                                    │
│                    │  Agent       │                                    │
│                    └──────┬───────┘                                    │
│                           │                                            │
│                    ┌──────▼───────┐                                    │
│                    │ Recommend.   │                                    │
│                    │ Agent        │                                    │
│                    └──────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6.2 Agent Definitions

### 6.2.1 Repository Analyzer Agent

**Agent ID**: `repo_analyzer`

**Responsibilities**:
- Clone or fetch repository contents
- Scan directory structure recursively
- Build a structured file manifest
- Identify key manifest files (package.json, go.mod, etc.)
- Apply file exclusion patterns (.git/, node_modules/, etc.)
- Detect repository size and apply appropriate analysis strategy (clone vs. API-based)

**Inputs**:
```python
{
    "repository_url": str,       # GitHub URL
    "access_token": str,         # GitHub auth token
    "default_branch": str,       # "main" or "master"
    "analysis_depth": int = 1,   # 1 = shallow, 2+ = deeper
}
```

**Outputs**:
```python
{
    "clone_path": str,                # Local temp directory path
    "file_manifest": List[Dict],      # [{path, name, extension, size_bytes}]
    "language_distribution": Dict,    # {".tsx": 142, ".py": 45}
    "manifest_files": Dict,           # {"package.json": "{...}", "Dockerfile": "..."}
    "total_files": int,
    "total_size_bytes": int,
    "analysis_mode": "clone" | "api", # Strategy used
}
```

**LLM Usage**: STAGE 1 — No LLM. Pure deterministic file system operations.

---

### 6.2.2 Technology Detection Agent

**Agent ID**: `tech_detector`

**Responsibilities**:
- Classify programming languages from file extensions and manifest files
- Detect frameworks and their versions from manifest dependencies
- Identify build tools (npm, pip, Maven, Gradle, etc.)
- Detect testing frameworks (Jest, pytest, JUnit, etc.)
- Identify deployment configurations (Docker, K8s, Terraform, Serverless, etc.)
- Cross-validate LLM results against deterministic patterns
- Mark low-confidence results for user confirmation

**Inputs**:
```python
{
    "file_manifest": List[Dict],      # From Repo Analyzer
    "manifest_files": Dict,           # From Repo Analyzer
    "language_distribution": Dict,    # From Repo Analyzer
}
```

**Outputs**:
```python
{
    "languages": List[{name, version, confidence, evidence}],
    "frameworks": List[{name, version, confidence, evidence}],
    "build_tools": List[{name, confidence, evidence}],
    "test_frameworks": List[{name, confidence, evidence}],
    "deployment_configs": List[{type, files, confidence}],
    "uncertain_detections": List[{category, name, reason}],
}
```

**LLM Usage**: STAGE 2 — Uses `primary` model (complex multi-classification with structured JSON output). Prompt includes file tree structure, manifest contents, and extension distribution.

**Confidence Scoring Heuristic**:
```python
def adjust_confidence(initial_confidence, technology, evidence):
    """Cross-validate LLM output with deterministic checks."""
    adjustments = {
        ("Python", "requirements.txt not found"): -0.15,
        ("Python", "requirements.txt found"): +0.05,
        ("Node.js", "package.json not found"): -0.2,
        ("Docker", "Dockerfile not found"): -0.1,
        ("Any", "multiple manifest files found"): +0.05,
    }
    return clamp(initial_confidence + adjustments.get((technology, evidence), 0), 0, 1)
```

---

### 6.2.3 Security Requirement Agent

**Agent ID**: `security_requirement`

**Responsibilities**:
- Infer required security scanning stages based on technology stack
- Map languages/frameworks to compatible security tools
- Determine required GitHub repository secrets for the workflow
- Recommend severity thresholds per tool
- Apply organizational security baselines
- Generate the minimum viable security pipeline specification

**Inputs**:
```python
{
    "technologies": Dict,           # From Tech Detector
    "repository_metadata": Dict,    # {visibility, archived, language}
    "user_config": Dict,            # {enabled_tools, custom_thresholds}
    "org_policy": Dict | None,      # Organization-wide security baseline
}
```

**Outputs**:
```python
{
    "required_tools": List[{
        "tool": str,                # "semgrep", "gitleaks", "trivy", "codeql", "dependency_review"
        "reason": str,              # "Python project requires SAST", "All projects require secret scanning"
        "config": Dict,             # Tool-specific configuration
        "mandatory": bool,          # Can user disable this?
    }],
    "inferred_secrets": List[str],  # ["NPM_TOKEN", "DOCKER_HUB_USERNAME", ...]
    "severity_thresholds": {
        "block_merge": "critical",
        "require_review": "high",
        "notify": "medium",
    }
}
```

**LLM Usage**: STAGE 3 — Uses `primary` model. Prompt includes technology stack, security best practices knowledge base, OWASP Top 10 mapping.

**Tool-Technology Mapping Database** (embedded):
```python
TOOL_COMPATIBILITY = {
    "Python": {
        "sast": ["semgrep", "codeql"],
        "secret": ["gitleaks"],
        "dependency": ["trivy", "dependency_review"],
        "container": ["trivy"],
    },
    "JavaScript": {
        "sast": ["semgrep", "codeql"],
        "secret": ["gitleaks"],
        "dependency": ["trivy", "dependency_review", "npm_audit"],
        "container": ["trivy"],
    },
    "TypeScript": {  # Inherits from JavaScript + additional
        "sast": ["semgrep", "codeql"],
        "secret": ["gitleaks"],
        "dependency": ["trivy", "dependency_review", "npm_audit"],
        "container": ["trivy"],
    },
    # ... more languages
}
```

---

### 6.2.4 Workflow Generator Agent

**Agent ID**: `workflow_generator`

**Responsibilities**:
- Generate a complete, production-grade GitHub Actions workflow YAML
- Include checkout, setup, build, test, security scan, and deploy stages
- Pin all action versions to specific versions or SHAs
- Use `${{ secrets.* }}` syntax for all credentials
- Adapt workflow structure to detected technology stack
- Generate unique workflow filename
- Include inline comments for explainability

**Inputs**:
```python
{
    "technologies": Dict,              # From Tech Detector
    "security_requirements": Dict,     # From Security Requirement Agent
    "user_config": Dict,               # {triggers, target_branch, enabled_tools}
    "existing_workflows": List[Dict],  # Existing .github/workflows/*.yml
    "repository_metadata": Dict,
}
```

**Outputs**:
```python
{
    "workflow_yaml": str,           # The generated YAML content
    "filename": str,                # "devsecops-react-nextjs-1717800000.yml"
    "stages": List[{
        "name": str,                # "Build & Test"
        "steps_count": int,
        "tools_used": List[str],
    }],
    "explanations": List[{
        "target": str,              # "jobs.build-and-test.steps[2]"
        "text": str,                # "Runs 'npm test' because Jest was detected as the test framework"
        "confidence": float,
    }],
    "metadata": {
        "model_used": str,
        "tokens_used": int,
        "generation_time_ms": int,
    }
}
```

**LLM Usage**: STAGE 4 — Uses `secondary` model. Large structured output prompt. Temperature set low (0.2) to minimize variation.

**Prompt Engineering Strategy**:
```
SYSTEM PROMPT STRUCTURE:
├── Role Definition: "You are a DevSecOps expert..."
├── Context Injection: Technology stack, security requirements
├── Output Format Specification: Valid YAML only, no fences, 2-space indent
├── Constraints: Version pinning, secrets syntax, permission blocks
├── Quality Guardrails: "Do NOT hallucinate action names..."
└── Few-Shot Examples: 2-3 example (tech stack → workflow) pairs
```

---

### 6.2.5 Workflow Validator Agent

**Agent ID**: `workflow_validator`

**Responsibilities**:
- Parse YAML for syntax errors
- Validate against GitHub Actions JSON Schema
- Enforce security policies (pinned versions, secrets, permissions)
- Perform LLM-based semantic validation (logical correctness)
- Classify errors by severity (ERROR vs WARNING) and fixability
- Determine whether workflow is PR-ready

**Inputs**:
```python
{
    "workflow_yaml": str,
    "technology_context": Dict,
    "security_requirements": Dict,
    "policy_rules": List[Dict],     # From system configuration
}
```

**Outputs**:
```python
{
    "validation_passed": bool,
    "errors": List[{
        "type": str,                # "SYNTAX_ERROR" | "SCHEMA_ERROR" | "POLICY_VIOLATION" | "SEMANTIC_ERROR"
        "severity": "ERROR" | "WARNING",
        "location": str,            # "jobs.semgrep-sast.steps[1].uses"
        "message": str,
        "fixable": bool,
        "suggested_fix": str | None,
    }],
    "warnings": List[Dict],
    "semantic_issues": List[Dict],
}
```

**LLM Usage**: STAGE 5 — Uses `lightweight` model for semantic validation only. Syntax and schema validation are deterministic.

**Validation Pipeline**:
```
1. YAML Parsing (deterministic)
   ├── PASS → Step 2
   └── FAIL → Report SYNTAX_ERROR → Route to Repair

2. Schema Validation (deterministic, JSON Schema)
   ├── PASS → Step 3
   └── FAIL → Report SCHEMA_ERROR per violation → Route to Repair

3. Security Policy Validation (rule-based)
   ├── PASS → Step 4
   └── FAIL → Report POLICY_VIOLATION per violation → Route to Repair

4. Semantic Validation (LLM-based)
   ├── PASS → Return "validation_passed: true"
   └── FAIL → Report SEMANTIC_ERROR → Route to Repair
```

---

### 6.2.6 Workflow Repair Agent

**Agent ID**: `workflow_repair`

**Responsibilities**:
- Classify validation errors by category (syntax, schema, policy, semantic)
- Apply deterministic fixes for syntax and schema errors
- Apply template-based fixes for missing security tools
- Use LLM for complex semantic and logic fixes
- Track repair attempt count and prevent infinite loops
- Generate repair diff for user review

**Inputs**:
```python
{
    "workflow_yaml": str,              # The failing workflow
    "validation_errors": List[Dict],   # From Validator Agent
    "technology_context": Dict,
    "repair_attempts": int,            # Current attempt number (0-indexed)
    "repair_history": List[Dict],      # Previous repair attempts and outcomes
}
```

**Outputs**:
```python
{
    "repaired_yaml": str,
    "repair_status": "success" | "partial" | "failed" | "stuck",
    "attempts_used": int,
    "changes_made": List[{
        "type": str,                   # "syntax_fix" | "schema_fix" | "policy_fix" | "semantic_fix"
        "description": str,
        "location": str,
    }],
    "unfixable_errors": List[Dict],    # Errors that couldn't be fixed
    "hash": str,                       # For loop detection
}
```

**LLM Usage**: STAGE 6 (conditional) — Uses `secondary` model only for semantic/LLM-based repairs. Syntax and schema fixes are deterministic.

**Repair Strategy Matrix**:

| Error Category | Fix Method | LLM Needed? | Example Fix |
|---|---|---|---|
| Syntax (YAML parse error) | YAML auto-formatter + regex fixes | No | Fix indentation, close quotes |
| Schema (missing required field) | Default value insertion | No | Add `runs-on: ubuntu-latest` |
| Schema (wrong type) | Type coercion | No | Convert string to array for `on:` trigger |
| Policy (unpinned action) | Version lookup + replacement | No | `@master` → `@v4` |
| Policy (missing security tool) | Template insertion | No | Insert Gitleaks job block from template |
| Policy (missing permissions) | Block insertion | No | Add `permissions: {contents: read}` |
| Semantic (logic error) | LLM re-generation of affected job | Yes | Fix build command for wrong language |
| Semantic (structural issue) | LLM re-generation of entire workflow | Yes | Completely wrong workflow structure |

**Loop Prevention**:
```python
def detect_repair_loop(original_yaml, errors, repair_history):
    current_hash = hashlib.sha256(
        (original_yaml + json.dumps(errors, sort_keys=True)).encode()
    ).hexdigest()
    
    for past_attempt in repair_history:
        if past_attempt["hash"] == current_hash:
            return True  # Loop detected
    
    return False
```

---

### 6.2.7 Risk Assessment Agent

**Agent ID**: `risk_assessor`

**Responsibilities**:
- Aggregate security scan findings across all tools
- Calculate weighted severity risk score
- Normalize score to 0-100 scale
- Determine risk trend from historical data
- Generate qualitative risk assessment via LLM
- Identify top vulnerability patterns
- Assess compliance impact

**Inputs**:
```python
{
    "findings": List[Dict],           # All parsed findings from scan execution
    "repository_metadata": Dict,
    "historical_risk_scores": List[float],  # Previous risk scores (time series)
    "false_positive_triage": Dict,    # User-marked false positives
}
```

**Outputs**:
```python
{
    "risk_score": float,              # 0-100 normalized
    "risk_category": str,             # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "MINIMAL"
    "risk_trend": str,                # "improving" | "stable" | "worsening"
    "finding_counts": Dict[str, int],  # {"critical": 2, "high": 5, ...}
    "qualitative_assessment": {
        "overall_assessment": str,
        "key_concerns": List[str],
        "attack_surface": str,
        "compliance_impact": str | None,
        "urgency": "immediate" | "high" | "moderate" | "low",
    }
}
```

**LLM Usage**: STAGE 7 (conditional) — Uses `primary` model only when risk score >= 25. Low-risk repos skip LLM assessment.

---

### 6.2.8 Recommendation Agent

**Agent ID**: `recommendation`

**Responsibilities**:
- Group findings by category (dependency, code, secret, config, CI/CD)
- Generate deterministic upgrade commands for dependency findings
- Generate LLM-powered code fix suggestions for code findings
- Generate configuration fix recommendations
- Assess breaking change risk for each recommendation
- Calculate auto-fixability percentage
- Generate executive summary report

**Inputs**:
```python
{
    "findings": List[Dict],           # Filtered to HIGH and CRITICAL only
    "technology_context": Dict,
    "file_contents": Dict[str, str],  # {file_path: content} for code-fix findings
    "previous_recommendations": List[Dict],
}
```

**Outputs**:
```python
{
    "recommendations": List[{
        "type": str,                  # "dependency_update" | "code_fix" | "secret_removal" | "config_change" | "cicd_hardening"
        "priority": str,              # "critical" | "high" | "medium"
        "auto_fixable": bool,
        "breaking_change": bool,
        "explanation": str,
        "fix_code": str | None,       # Code diff for code fixes
        "command": str | None,        # CLI command for dependency updates
        "cwe_reference": str | None,
        "confidence": float,          # LLM confidence in the recommendation
    }],
    "summary": {
        "total": int,
        "auto_fixable": int,
        "requires_review": int,
    }
}
```

**LLM Usage**: STAGE 8 (conditional) — Uses `secondary` model for code fix generation and qualitative explanation. Dependency update recommendations are rule-based (no LLM).

---

## 6.3 Agent-to-Agent Communication

### Communication Protocol
All inter-agent communication occurs through the **shared AgentState dictionary**, which is the single source of truth during a LangGraph invocation. Agents read from and write to specific state keys.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       AGENT STATE (Blackboard)                       │
│                                                                     │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐    │
│  │ Key A    │     │ Key B    │     │ Key C    │     │ Key D    │    │
│  │ (Agent 1 │     │ (Agent 2 │     │ (Agent 3 │     │ (Agent 4 │    │
│  │  writes) │     │  reads,  │     │  reads,  │     │  reads)  │    │
│  │          │     │  writes) │     │  writes) │     │          │    │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘    │
│                                                                     │
│  Agents NEVER call each other directly.                              │
│  The Orchestrator Graph controls which agent runs when.              │
└─────────────────────────────────────────────────────────────────────┘
```

### State Key Ownership Matrix

| State Key | Writer Agent | Reader Agents |
|---|---|---|
| `file_manifest` | Repo Analyzer | Tech Detector |
| `manifest_files` | Repo Analyzer | Tech Detector |
| `clone_path` | Repo Analyzer | Tech Detector (optional) |
| `technologies` | Tech Detector | Security Req, Workflow Gen, Validator, Repair |
| `security_requirements` | Security Req | Workflow Gen, Validator, Repair |
| `workflow_yaml` | Workflow Gen, Repair | Validator, PR Service |
| `validation_errors` | Validator | Repair |
| `repair_attempts` | Repair | Orchestrator (for iteration control) |
| `findings` | Monitoring Worker | Risk Assessor, Recommendation |
| `risk_score` | Risk Assessor | Recommendation, Dashboard Service |
| `recommendations` | Recommendation | Dashboard Service, Report Service |

### Communication Sequence

```
[Repo Analyzer] ──writes──▶ state["file_manifest"] ──reads──▶ [Tech Detector]
[Tech Detector] ──writes──▶ state["technologies"]  ──reads──▶ [Security Req]
[Security Req]  ──writes──▶ state["security_requirements"] ──reads──▶ [Workflow Gen]
[Workflow Gen]  ──writes──▶ state["workflow_yaml"] ──reads──▶ [Validator]
[Validator]     ──writes──▶ state["validation_errors"] ──reads──▶ [Repair]
[Repair]        ──writes──▶ state["workflow_yaml"] ──reads──▶ [Validator] (loop)
```

---

## 6.4 State Transitions

The orchestration graph defines **conditional edges** that determine agent execution order based on state.

```python
from langgraph.graph import StateGraph, END

def build_orchestration_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    
    # Nodes (agents)
    graph.add_node("repo_analyzer", repo_analyzer_agent)
    graph.add_node("tech_detector", tech_detector_agent)
    graph.add_node("security_req", security_requirement_agent)
    graph.add_node("workflow_gen", workflow_generator_agent)
    graph.add_node("workflow_val", workflow_validator_agent)
    graph.add_node("workflow_repair", workflow_repair_agent)
    graph.add_node("create_pr", create_pr_service)       # Service, not agent
    graph.add_node("risk_assessor", risk_assessor_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("manual_review", manual_review_node)  # Human interaction node
    
    # Entry point
    graph.set_entry_point("repo_analyzer")
    
    # Sequential edges (happy path)
    graph.add_edge("repo_analyzer", "tech_detector")
    graph.add_edge("tech_detector", "security_req")
    graph.add_edge("security_req", "workflow_gen")
    graph.add_edge("workflow_gen", "workflow_val")
    
    # Conditional edges from validator
    graph.add_conditional_edges(
        "workflow_val",
        route_after_validation,
        {
            "pass": "create_pr",
            "repair": "workflow_repair",
            "fail": "manual_review",       # Unfixable errors
        }
    )
    
    # Conditional edges from repair
    graph.add_conditional_edges(
        "workflow_repair",
        route_after_repair,
        {
            "retry": "workflow_val",        # Re-validate repaired workflow
            "manual": "manual_review",      # Max attempts exceeded
        }
    )
    
    # After PR creation or manual review, proceed to risk & recommendation
    graph.add_edge("create_pr", "risk_assessor")
    graph.add_edge("manual_review", "risk_assessor")
    graph.add_edge("risk_assessor", "recommendation")
    graph.add_edge("recommendation", END)
    
    return graph.compile(checkpointer=SqliteSaver)
```

### Conditional Routing Functions

```python
def route_after_validation(state: AgentState) -> str:
    """Determine next node after workflow validation."""
    if state["validation_passed"]:
        return "pass"
    elif len(state["validation_errors"]) > 0:
        # Check if all errors are fixable
        all_fixable = all(e["fixable"] for e in state["validation_errors"])
        if all_fixable and state.get("repair_attempts", 0) < 3:
            return "repair"
        else:
            return "fail"  # Unfixable or exceeded attempts → manual review
    return "fail"

def route_after_repair(state: AgentState) -> str:
    """Determine next node after repair attempt."""
    if state.get("repair_status") == "success":
        return "retry"  # Go back to validator
    elif state["repair_attempts"] >= 3:
        return "manual"  # Exceeded maximum attempts
    else:
        return "retry"  # Try validation again with partial fix
```

### State Transition Diagram (Mermaid.js Compatible)

```
stateDiagram-v2
    [*] --> RepoAnalyzer
    RepoAnalyzer --> TechDetector
    TechDetector --> SecurityRequirement
    SecurityRequirement --> WorkflowGenerator
    WorkflowGenerator --> WorkflowValidator
    
    WorkflowValidator --> CreatePR: Validation Passed
    WorkflowValidator --> WorkflowRepair: Fixable Errors (attempt < 3)
    WorkflowValidator --> ManualReview: Unfixable / Max Attempts
    
    WorkflowRepair --> WorkflowValidator: Repair Success
    WorkflowRepair --> ManualReview: Max Attempts (3)
    
    CreatePR --> RiskAssessor
    ManualReview --> RiskAssessor
    RiskAssessor --> RecommendationAgent
    RecommendationAgent --> [*]
```

---

## 6.5 Failure Handling

### 6.5.1 Agent-Level Failure Modes

| Agent | Failure Mode | Detection | Recovery Strategy |
|---|---|---|---|
| Repo Analyzer | Clone timeout (> 120s) | Timeout exception | Fall back to GitHub Tree API; mark as "limited analysis" |
| Repo Analyzer | Auth failure (403) | HTTP response code | Retry with GitHub App token; if still failing, fail job |
| Tech Detector | LLM timeout (> 60s) | HTTP timeout | Retry with truncated prompt; after 3 retries, use heuristic-only mode |
| Tech Detector | LLM returns invalid JSON | JSON parse error | Retry with stricter prompt; after 2 retries, ask LLM to self-correct |
| Security Req | LLM returns incompatible tool mapping | Tool-compatibility check fails | Override with deterministic mapping; log mismatch for review |
| Workflow Gen | LLM output exceeds token limit | Token counter check | Split generation into stages; stitch results |
| Workflow Gen | LLM hallucinates non-existent action | Action not in known registry | Mark for repair; Validator will catch |
| Validator | YAML parser crash | Unhandled parse exception | Log raw YAML; mark as unfixable |
| Repair | Nth attempt produces same output | Hash comparison | Stop repair; mark as "stuck" |
| Risk Assessor | Division by zero (no findings) | ZeroDivisionError | Return risk_score = 0 with appropriate message |
| Recommendation | File not found for code fix | FileNotFoundError | Skip that recommendation; note "file deleted" |

### 6.5.2 Graph-Level Failure Handling

```python
# LangGraph provides built-in retry through `RetryPolicy`

from langgraph.pregel import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=3,
    initial_interval=1.0,      # seconds
    backoff_factor=2.0,        # exponential backoff
    max_interval=30.0,
    retry_on=(
        ConnectionError,
        TimeoutError,
        httpx.HTTPStatusError,  # OpenRouter API errors
    ),
)

graph = graph.compile(
    checkpointer=SqliteSaver(),
    interrupt_before=["manual_review"],  # Pause for human intervention
)

# Invoke with retry
result = await graph.ainvoke(
    initial_state,
    config={"retry_policy": retry_policy}
)
```

---

## 6.6 Retry Mechanisms

### 6.6.1 LLM Call Retry (Inner Loop)

```python
async def llm_call_with_retry(
    client: OpenRouterClient,
    model: str,
    messages: List[Dict],
    max_retries: int = 3,
    base_delay: float = 2.0
) -> Dict:
    """Retry LLM calls with exponential backoff."""
    
    for attempt in range(max_retries):
        try:
            response = await client.chat_completion(
                model=model,
                messages=messages,
                timeout=60.0
            )
            
            # Check for empty response
            if not response.get("choices"):
                raise ValueError("Empty LLM response")
            
            # Check for truncated response (finish_reason == "length")
            if response["choices"][0].get("finish_reason") == "length":
                # Truncated — retry with more tokens
                messages.append({
                    "role": "user",
                    "content": "Your previous response was truncated. Please continue."
                })
                continue
            
            return response
            
        except (TimeoutError, ConnectionError) as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit
                retry_after = int(e.response.headers.get("Retry-After", 30))
                await asyncio.sleep(retry_after)
            elif e.response.status_code >= 500:  # Server error
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(base_delay * (2 ** attempt))
            else:
                raise  # Non-retryable error
```

### 6.6.2 Model Fallback Strategy

```python
MODEL_FALLBACK_CHAIN = {
    "primary": ["secondary", "fallback"],    # If Claude fails, try GPT-4o, then Gemini
    "secondary": ["fallback", "lightweight"], # If GPT-4o fails, try Gemini, then Llama
    "fallback": ["lightweight"],              # If Gemini fails, try Llama
    "lightweight": [],                        # Llama is the last resort
}

async def llm_call_with_fallback(client, model_tier, messages):
    """Attempt LLM calls with model fallback chain."""
    
    tiers_to_try = [model_tier] + MODEL_FALLBACK_CHAIN.get(model_tier, [])
    
    for tier in tiers_to_try:
        model = client.MODELS[tier]
        try:
            return await llm_call_with_retry(client, model, messages, max_retries=2)
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}. Trying next tier...")
            continue
    
    raise RuntimeError("All model tiers exhausted")
```

### 6.6.3 Agent-Level Retry (Outer Loop)

The LangGraph StateGraph itself supports node-level retry:

```python
async def repo_analyzer_with_retry(state: AgentState) -> AgentState:
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            result = await analyze_repository(state)
            state.update(result)
            return state
        except CloneAuthError:
            if attempt < max_retries:
                # Try with different token (GitHub App install token)
                state["github_token"] = await refresh_github_token(state)
                continue
            else:
                state["status"] = "failed"
                state["errors"].append("Repository access failed after retries")
                return state
        except Exception as e:
            if attempt < max_retries:
                continue
            else:
                raise
```
