"""Static node metadata for the 18 v9.3 pipeline nodes.

This module powers the FE `Pipeline Nodes` panel (PipelineDetail for
Tahap 1-3, RunDetail for Tahap 4). Each entry contains:

  - id         (str): node id used in the LangGraph graph
  - name       (str): human-readable name
  - tahap      (int): 1 / 2 / 3 / 4
  - type       (str): "deterministic" | "llm" | "hybrid"
  - function   (str): one-sentence description of what the node does
  - inputs     (list[str]): state fields read by the node
  - outputs    (list[str]): state fields written by the node
  - prompt     (str|None): abbreviated LLM prompt (Bab 5.13 spec)
  - fallback   (str|None): one-sentence deterministic fallback
  - file       (str): relative path to the implementation
  - line_count (int): implementation file line count (approx)
  - spec_ref   (str): struktur-v9.md reference

The metadata is curated by hand so the FE renders consistent
information. To refresh after a node refactor, update the
`inputs` / `outputs` / `prompt` fields here.
"""

from __future__ import annotations

from typing import Optional

NodeType = str  # "deterministic" | "llm" | "hybrid"


# ── Tahap 1: Repository Context Analysis (6 nodes) ──────────────────────
NODES_T1: list[dict] = [
    {
        "id": "repository_connection",
        "name": "Repository Connection",
        "tahap": 1,
        "type": "deterministic",
        "function": "Connect to GitHub via token, fetch repo metadata (default branch, description, URL).",
        "inputs": ["repository_full_name", "github_token"],
        "outputs": ["repository_url", "repository_default_branch", "errors", "error_stage"],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/repository_connection_node.py",
        "line_count": 29,
        "spec_ref": "struktur-v9.md §Node 1",
    },
    {
        "id": "repository_scan",
        "name": "Repository Scan",
        "tahap": 1,
        "type": "deterministic",
        "function": "Fetch repo file tree, manifest files (package.json, etc.), source files, existing workflows.",
        "inputs": ["repository_full_name", "github_token", "errors"],
        "outputs": [
            "repository_structure",
            "repository_files",
            "existing_workflows",
            "source_files",
        ],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/repository_scan_node.py",
        "line_count": 293,
        "spec_ref": "struktur-v9.md §Node 2",
    },
    {
        "id": "technology_detection",
        "name": "Technology Detection",
        "tahap": 1,
        "type": "llm",
        "function": "LLM identifies primary language, frameworks, build tools, package manager, test framework, database, runtime.",
        "inputs": ["repository_structure", "repository_files", "existing_workflows"],
        "outputs": [
            "detected_technologies",
            "primary_language",
            "primary_language_confidence",
            "frameworks",
            "package_manager",
        ],
        "prompt": (
            "You are a DevSecOps engineer analyzing a GitHub repository. "
            "Identify the technology stack (primary language, frameworks, "
            "build tools, package manager, test framework, database, runtime) "
            "with confidence scores 0.0-1.0."
        ),
        "fallback": (
            "If LLM fails, _detect_from_extensions() uses file extension "
            "counting (confidence <= 0.6)."
        ),
        "file": "app/agents/nodes/technology_detection_node.py",
        "line_count": 254,
        "spec_ref": "struktur-v9.md §Node 3",
    },
    {
        "id": "architecture_detection",
        "name": "Architecture Detection",
        "tahap": 1,
        "type": "llm",
        "function": "LLM classifies architecture: monolithic (only). (v9.5 revisi 3-domain & 1-arch per R2.1).",
        "inputs": ["repository_structure", "detected_technologies"],
        "outputs": [
            "detected_architecture",
            "detected_architecture_type",
            "detected_architecture_confidence",
            "detected_architecture_reason",
        ],
        "prompt": (
            "You are a DevSecOps engineer analyzing application architecture. "
            "Determine architecture_type (monolithic only) with confidence "
            "0.0-1.0 and explain. Always return 'monolithic' per R2.1."
        ),
        "fallback": (
            "If LLM JSON parse fails, default to 'monolithic'. "
            "Arsitektur bukan variabel eksperimen — _resolve_arch_type() "
            "selalu mengembalikan 'monolithic' (tidak ada upgrade ke "
            "modular_monolith)."
        ),
        "file": "app/agents/nodes/architecture_detection_node.py",
        "line_count": 87,
        "spec_ref": "struktur-v9.md §Node 4",
    },
    {
        "id": "deployment_detection",
        "name": "Deployment Detection",
        "tahap": 1,
        "type": "hybrid",
        "function": "File-based detection (Dockerfile, docker-compose) + LLM enrichment of deployment recommendation.",
        "inputs": ["repository_structure", "repository_files", "existing_workflows"],
        "outputs": ["detected_deployment", "recommended_deployment_target"],
        "prompt": (
            "You are a DevSecOps engineer analyzing deployment infrastructure. "
            "Detect DOCKER presence with confidence 0.0-1.0. "
            "Recommend 'docker' if Dockerfile found, 'generic' otherwise."
        ),
        "fallback": (
            "_detect_from_files() returns the file-pattern result verbatim. "
            "On LLM failure, the file-based result is kept."
        ),
        "file": "app/agents/nodes/deployment_detection_node.py",
        "line_count": 200,
        "spec_ref": "struktur-v9.md §Node 5",
    },
    {
        "id": "domain_detection",
        "name": "Domain Detection",
        "tahap": 1,
        "type": "hybrid",
        "function": "Heuristic scoring (libraries, entities, routes) + LLM classification of webapp domain (e-commerce | blog | iot | general). (v9.3 revisi 3-domain & 2-arch).",
        "inputs": [
            "repository_full_name",
            "repository_description",
            "repository_files",
            "source_files",
        ],
        "outputs": [
            "detected_domain",
            "domain_sub_type",
            "domain_confidence",
            "domain_evidence",
            "domain_threats",
            "features",
        ],
        "prompt": (
            "You are classifying the web application domain of a GitHub "
            "repository. Classify into one of: e-commerce, blog, iot, general. "
            "Identify the payment processor (sub_type) and business features."
        ),
        "fallback": (
            "7-layer fallback: (1) LLM exception -> empty. (2) LLM confidence "
            "< 0.5 -> heuristic. (3) LLM 'general' but heuristic strong -> "
            "override. (4) Disagreement -> trust heuristic. (5) domain_threats "
            "fallback to DOMAIN_LIBRARY_INDICATORS. (6) sub_type from "
            "_infer_payment_processor(). (7) features from _fallback_features()."
        ),
        "file": "app/agents/nodes/domain_detection_node.py",
        "line_count": 711,
        "spec_ref": "struktur-v9.md §Node 6",
    },
]

# ── Tahap 2: Security Coverage Inference (4 nodes) ──────────────────────
NODES_T2: list[dict] = [
    {
        "id": "coverage_inference",
        "name": "Coverage Inference",
        "tahap": 2,
        "type": "llm",
        "function": "Mark each of the 15 security coverages applicable or not with a concrete reason + confidence.",
        "inputs": [
            "repository_full_name",
            "detected_technologies",
            "detected_architecture",
            "detected_deployment",
            "detected_domain",
            "domain_confidence",
            "features",
            "repository_files",
            "source_files",
        ],
        "outputs": ["security_coverages", "coverage_inference_reasoning"],
        "prompt": (
            "You are a Security Coverage Inference Engine. Given repository "
            "context, determine which of the 15 security coverages apply. "
            "Be strict. Only mark a coverage as applicable if you can cite a "
            "clear signal (library, entity, route, deployment)."
        ),
        "fallback": (
            "_fallback_coverages_from_heuristic(): if heuristic score >= 1.0, "
            "mark coverage applicable with confidence = min(1.0, score*0.2+0.5)."
        ),
        "file": "app/agents/nodes/coverage_inference_node.py",
        "line_count": 300,
        "spec_ref": "struktur-v9.md §Node 7",
    },
    {
        "id": "pattern_inference",
        "name": "Pattern Inference (K2.3)",
        "tahap": 2,
        "type": "llm",
        "function": "Generate repo-specific Semgrep rules from source sample, avoiding overlap with static library.",
        "inputs": [
            "detected_technologies",
            "detected_domain",
            "domain_sub_type",
            "detected_architecture_type",
            "features",
            "security_coverages",
            "source_files",
        ],
        "outputs": [
            "ai_generated_rules",
            "pattern_inference_reasoning",
            "pattern_inference_valid_count",
        ],
        "prompt": (
            "You are a Semgrep rule author specialising in <domain> web "
            "application security. Generate adaptive Semgrep rules targeted to "
            "THIS repository's project-specific patterns. Each rule id must "
            "match `ai-{coverage}-{slug}` and have a metadata.ai-devsecops-coverage."
        ),
        "fallback": (
            "_validate_ai_generated_rule() checks id pattern, severity, "
            "languages/patterns presence. Invalid rules silently rejected. "
            "If no applicable coverages, return empty list."
        ),
        "file": "app/agents/nodes/pattern_inference_node.py",
        "line_count": 485,
        "spec_ref": "struktur-v9.md §Node 8",
    },
    {
        "id": "pipeline_augmentation",
        "name": "Pipeline Augmentation",
        "tahap": 2,
        "type": "llm",
        "function": "Translate applicable coverages into per-coverage {job, configuration} bindings.",
        "inputs": [
            "security_coverages",
            "detected_technologies",
            "detected_architecture_type",
            "detected_deployment",
            "detected_domain",
        ],
        "outputs": ["pipeline_augmentations", "inferred_security_needs"],
        "prompt": (
            "You are an Adaptive DevSecOps Pipeline Composer. For each "
            "applicable coverage, decide which control/job (sast, sca, "
            "secret_scan, container_scan, etc.) to add with its configuration. "
            "Be specific (e.g. payment_security + Stripe -> sast p/secrets)."
        ),
        "fallback": (
            "2 layers: (1) LLM returns no augmentation -> static "
            "DEFAULT_AUGMENTATIONS dict (15 coverage keys x predefined tuples). "
            "(2) Validate against valid_jobs set, drop anything outside. Base "
            "controls (lint, sast, secret_scan) always prepended."
        ),
        "file": "app/agents/nodes/pipeline_augmentation_node.py",
        "line_count": 359,
        "spec_ref": "struktur-v9.md §Node 9",
    },
    {
        "id": "job_reasoning",
        "name": "Job Reasoning (K2.4)",
        "tahap": 2,
        "type": "llm",
        "function": "Design up to 3 custom CI jobs (kebab-case, >= 2 actions, exactly 1 sarif_upload) beyond the standard 8 jobs.",
        "inputs": [
            "security_coverages",
            "detected_technologies",
            "detected_architecture_type",
            "detected_deployment",
            "detected_domain",
            "domain_sub_type",
            "features",
            "findings",
            "source_files",
        ],
        "outputs": [
            "job_designs",
            "job_designs_reasoning",
            "job_designs_valid_count",
        ],
        "prompt": (
            "You are a senior DevSecOps Pipeline Architect. For each applicable "
            "coverage, decide whether a CUSTOM pipeline job is warranted beyond "
            "the standard 8. Cite specific file paths/libraries/patterns from "
            "source code. Each job MUST have >= 2 actions, exactly 1 "
            "sarif_upload, kebab-case name, max 3 per run."
        ),
        "fallback": (
            "_fallback_design_from_coverages(): pick target coverage by domain "
            "(payment_security for e-commerce, cms_security for blog, "
            "iot_security for iot) or highest-confidence. Emit single "
            "deterministic job with shell_check + sarif_upload."
        ),
        "file": "app/agents/nodes/job_reasoning_node.py",
        "line_count": 432,
        "spec_ref": "struktur-v9.md §Node 10",
    },
]

# ── Tahap 3: Pipeline Generation & Deployment (5 nodes) ────────────────
NODES_T3: list[dict] = [
    {
        "id": "workflow_generation",
        "name": "Workflow Generation",
        "tahap": 3,
        "type": "deterministic",
        "function": "Compose YAML from standard 8 jobs + domain jobs + AI-generated jobs (job_designs).",
        "inputs": [
            "detected_technologies",
            "detected_architecture",
            "detected_deployment",
            "inferred_security_needs",
            "findings",
            "repository_structure",
            "repository_files",
            "detected_domain",
            "ai_generated_rules",
            "job_designs",
        ],
        "outputs": [
            "generated_workflow",
            "generated_workflow_generic",
            "generated_workflow_custom",
            "generated_workflow_files",
            "generated_stages",
            "generated_stages_general",
            "generated_stages_custom",
            "custom_semgrep_rules_yaml",
            "custom_semgrep_rules_path",
        ],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/workflow_generator.py",
        "line_count": 6638,
        "spec_ref": "struktur-v9.md §Node 11",
    },
    {
        "id": "workflow_validation",
        "name": "Workflow Validation",
        "tahap": 3,
        "type": "deterministic",
        "function": "Pre-flight checks: action SHA pinning, permissions, concurrency. Non-blocking (warnings only).",
        "inputs": [
            "generated_workflow",
            "inferred_security_needs",
            "errors",
        ],
        "outputs": [
            "validation_errors",
            "validation_passed",
            "validation_warnings",
            "validation_findings",
            "auto_fixes",
        ],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/workflow_validator.py",
        "line_count": 271,
        "spec_ref": "struktur-v9.md §Node 12",
    },
    {
        "id": "workflow_repair",
        "name": "Workflow Repair",
        "tahap": 3,
        "type": "llm",
        "function": "Auto-repair invalid YAML using validator findings (dormant in v9.3 because validation_errors is always []).",
        "inputs": [
            "errors",
            "generated_workflow",
            "validation_findings",
            "validation_errors",
            "detected_technologies",
        ],
        "outputs": [
            "remediation_suggestions",
            "generated_workflow",
            "summary",
        ],
        "prompt": (
            "You are an expert DevSecOps Workflow Repair Agent. Repair the "
            "existing GitHub Actions workflow based on validation findings. "
            "Preserve original structure, fix only identified issues, never "
            "invent SHAs."
        ),
        "fallback": None,
        "file": "app/agents/nodes/workflow_repair_node.py",
        "line_count": 242,
        "spec_ref": "struktur-v9.md §Node 13",
    },
    {
        "id": "github_branch_creation",
        "name": "GitHub Branch Creation",
        "tahap": 3,
        "type": "deterministic",
        "function": "Create `ai-devsecops/generate-workflow-{timestamp}` branch in the target repo.",
        "inputs": [
            "errors",
            "validation_passed",
            "repository_full_name",
            "github_token",
            "repository_default_branch",
        ],
        "outputs": ["github_branch", "errors"],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/github_branch_creation_node.py",
        "line_count": 30,
        "spec_ref": "struktur-v9.md §Node 14",
    },
    {
        "id": "pull_request_creation",
        "name": "Pull Request Creation",
        "tahap": 3,
        "type": "deterministic",
        "function": "Commit workflow files + custom Semgrep rules + open PR. Custom file is committed FIRST so the generic file's workflow_call reference resolves on first run.",
        "inputs": [
            "errors",
            "generated_workflow",
            "github_branch",
            "repository_full_name",
            "github_token",
            "repository_default_branch",
            "custom_semgrep_rules_yaml",
            "custom_semgrep_rules_path",
        ],
        "outputs": [
            "workflow_file",
            "github_commit_sha",
            "github_pr_number",
            "github_pr_url",
            "custom_semgrep_rules",
        ],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/pull_request_creation_node.py",
        "line_count": 605,
        "spec_ref": "struktur-v9.md §Node 15",
    },
]

# ── Tahap 4: Security Evaluation (3 nodes) ────────────────────────────
NODES_T4: list[dict] = [
    {
        "id": "security_analysis",
        "name": "Security Analysis",
        "tahap": 4,
        "type": "hybrid",
        "function": "Normalise SARIF findings, attach CVSS via 3-tier lookup, attach security_coverage per finding, apply domain priority elevation, recompute dashboard scores.",
        "inputs": [
            "scan_results",
            "findings",
            "workflow_logs",
            "repository_full_name",
            "workflow_run_id",
            "github_token",
            "detected_domain",
        ],
        "outputs": [
            "findings",
            "domain_context",
            "risk_score",
            "security_coverage_score",
            "compliance_score",
            "severity_breakdown",
            "summary",
        ],
        "prompt": (
            "You are a DevSecOps security analyst. Enrich each finding with "
            "additional context (type, severity, scanner, file, line, "
            "code_snippet, package, CVE, CWE, OWASP, explanation, impact, "
            "recommendation). Do NOT add new findings or invent issues."
        ),
        "fallback": (
            "Bab 5.13.3: tag every finding with CVSS via 3-tier lookup "
            "(RULE_CVSS_MAP -> TYPE_CVSS_FALLBACK -> SEVERITY_DEFAULT). "
            "Recompute risk_score = 100 - (avg(CVSS)/10)*100. coverage_score "
            "= applicable/15. compliance_score = matched/len(applicable)."
        ),
        "file": "app/agents/nodes/security_analyzer.py",
        "line_count": 207,
        "spec_ref": "struktur-v9.md §Node 16",
    },
    {
        "id": "recommendation_gen",
        "name": "Recommendation Generation",
        "tahap": 4,
        "type": "llm",
        "function": "Generate actionable fix recommendations with before/after code examples and update commands.",
        "inputs": ["findings", "risk_score", "report"],
        "outputs": ["recommendations", "report", "errors"],
        "prompt": (
            "You are a DevSecOps engineer. Given security findings and risk "
            "assessment, generate actionable fix recommendations with "
            "code-level fixes, before/after examples, and package update commands."
        ),
        "fallback": (
            "Hardcoded recommendations list per finding type (hardcoded_secret "
            "-> rotate credentials, sql_injection -> parameterized query, etc.) "
            "when LLM fails."
        ),
        "file": "app/agents/nodes/recommendation_gen.py",
        "line_count": 76,
        "spec_ref": "struktur-v9.md §Node 17",
    },
    {
        "id": "response_formatter",
        "name": "Response Formatter",
        "tahap": 4,
        "type": "deterministic",
        "function": "Build unified response + PDF report (5 sections + 5.4 K2.3 + 5.5 K2.4).",
        "inputs": [
            "findings",
            "risk_score",
            "security_posture",
            "compliance_score",
            "severity_breakdown",
            "recommendations",
            "detected_technologies",
            "detected_architecture",
            "detected_architecture_confidence",
            "detected_architecture_reason",
            "detected_deployment",
            "recommended_deployment_target",
            "detected_domain",
            "domain_sub_type",
            "domain_confidence",
            "domain_threats",
            "features",
            "security_coverages",
            "ai_generated_rules",
            "pipeline_augmentations",
            "job_designs",
            "generated_workflow",
            "generated_stages",
            "validation_passed",
            "validation_errors",
            "validation_warnings",
            "auto_deploy",
            "errors",
            "error_stage",
        ],
        "outputs": [
            "summary",
            "pdf_report_path",
            "unified_response",
            "repository_analysis",
            "security_explanation",
            "deployment_explanation",
            "security_coverages",
        ],
        "prompt": None,
        "fallback": None,
        "file": "app/agents/nodes/response_formatter.py",
        "line_count": 222,
        "spec_ref": "struktur-v9.md §Node 18",
    },
]


# ── Public API ────────────────────────────────────────────────────────

ALL_NODES: list[dict] = NODES_T1 + NODES_T2 + NODES_T3 + NODES_T4


def get_nodes(tahap: Optional[int] = None) -> list[dict]:
    """Return the list of node metadata, optionally filtered by tahap."""
    if tahap is None:
        return list(ALL_NODES)
    return [n for n in ALL_NODES if n.get("tahap") == tahap]


def get_node_spec(node_id: str) -> Optional[dict]:
    """Return the metadata for a single node id, or None if not found."""
    for n in ALL_NODES:
        if n.get("id") == node_id:
            return n
    return None
