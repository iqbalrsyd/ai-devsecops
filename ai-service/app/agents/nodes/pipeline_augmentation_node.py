"""Pipeline Augmentation Node (K2.2 - struktur-v9).

Given applicable security coverages, determine which controls/jobs to
add to the pipeline and their configuration.

Outputs state.pipeline_augmentations: list[{
    coverage: str,           # coverage id
    job: str,                # control/job type
    configuration: str,      # job-specific configuration
    reason: str,             # why this augmentation
}]
"""
import json

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


# ── Default Augmentation Library ────────────────────────────────────────
# Used as a fallback when LLM is unavailable. Per coverage, list of
# default control augmentations to merge into the workflow YAML.

DEFAULT_AUGMENTATIONS: dict[str, list[dict]] = {
    "authentication_security": [
        {"job": "sast", "configuration": "p/secrets, p/owasp-top-ten (auth rules)"},
        {"job": "secret_scan", "configuration": "focus: JWT, OAuth, session tokens"},
    ],
    "api_security": [
        {"job": "sast", "configuration": "p/owasp-top-ten, p/javascript, p/nodejs"},
        {"job": "sast", "configuration": ".semgrep/owasp-api.yml custom rules"},
    ],
    "data_security": [
        {"job": "sast", "configuration": "p/sql-injection, p/javascript"},
        {"job": "sca", "configuration": "DB driver CVE check"},
    ],
    "payment_security": [
        {"job": "sast", "configuration": "ecommerce.yml custom rules"},
        {"job": "secret_scan", "configuration": "focus: stripe, midtrans, xendit, paypal keys"},
        {"job": "sca", "configuration": "payment gateway library CVEs"},
    ],
    "container_security": [
        {"job": "container_scan", "configuration": "trivy image + Dockerfile best-practices"},
    ],
    "iot_security": [
        {"job": "sast", "configuration": "iot-mqtt.yml custom rules (MQTT no-TLS, default creds)"},
        {"job": "secret_scan", "configuration": "focus: device credentials, certificates"},
    ],
    "logging_security": [
        {"job": "sast", "configuration": "sensitive-data-in-logs.yml custom rules"},
        {"job": "sca", "configuration": "logging library CVEs"},
    ],
    "file_upload_security": [
        {"job": "sast", "configuration": "path-traversal.yml, file-upload-bypass.yml"},
        {"job": "sast", "configuration": "p/javascript (file handling)"},
    ],
    "cms_security": [
        {"job": "sast", "configuration": "blog-csp.yml, xss-prevention.yml"},
        {"job": "sca", "configuration": "markdown/sanitizer library CVEs"},
    ],
    "dependency_security": [
        {"job": "sca", "configuration": "npm audit / pip-audit / govulncheck"},
    ],
}


PIPELINE_AUGMENTATION_PROMPT = """You are an Adaptive DevSecOps Pipeline Composer.

Given applicable security coverages, determine which controls/jobs to
add to the pipeline and their configuration.

## SCOPE (skripsi Bab 3, revisi 3-domain & 1-architecture)

Supported domains: e-commerce, blog, iot (+ general fallback).
Supported architectures: monolithic (saja).
Do NOT invent augmentations for unsupported domains (healthcare /
fintech / education / microservices). Stay within the supported
3-domain scope. Arsitektur bukan variabel eksperimen (batasan B7).

## Repository Context

Primary Language: {language}
Package Manager: {package_manager}
Architecture: {architecture}
Deployment: {deployment}
Detected Domain: {domain}

## Applicable Security Coverages

{coverages}

## Available Controls / Jobs

- sast (Semgrep, with ruleset configuration)
- sca (dependency scan, with ecosystem-specific tool)
- secret_scan (gitleaks, with focus list)
- container_scan (trivy image + Dockerfile)
- iac_scan (trivy config + checkov)
- compliance_check (legacy, only when a relevant coverage is applicable)
- docker_compose_validate

## Task

For each applicable coverage, determine:
1. Which control/job to add.
2. The configuration (ruleset, focus list, etc.).
3. Why this augmentation makes sense for the repo context.

Be specific. For example, for payment_security with Stripe detected,
the secret_scan should focus on stripe, midtrans, xendit keys.

## Return ONLY valid JSON

{{
  "pipeline_augmentations": [
    {{
      "coverage": "<coverage_id>",
      "job": "<control>",
      "configuration": "<specific config>",
      "reason": "<why this augmentation>"
    }}
  ]
}}
"""


def _format_coverages_for_prompt(coverages: list[dict]) -> str:
    applicable = [c for c in coverages if c.get("applicable")]
    if not applicable:
        return "(none)"
    lines: list[str] = []
    for c in applicable:
        lines.append(f"- **{c.get('id')}**: {c.get('reason', '')}")
    return "\n".join(lines)


def _fallback_augmentations(coverages: list[dict]) -> list[dict]:
    """When LLM is unavailable, use default augmentation library."""
    augmentations: list[dict] = []
    for c in coverages:
        if not c.get("applicable"):
            continue
        cov_id = c.get("id")
        for aug in DEFAULT_AUGMENTATIONS.get(cov_id, []):
            augmentations.append({
                "coverage": cov_id,
                "job": aug["job"],
                "configuration": aug["configuration"],
                "reason": f"Default augmentation for {cov_id} coverage",
            })
    return augmentations


def _parse_llm_response(content: str) -> dict:
    from app.agents.llm_response_parser import (
        parse_llm_json_object, parse_llm_json_array,
    )
    obj = parse_llm_json_object(content)
    if obj is not None:
        return obj
    arr = parse_llm_json_array(content)
    return arr if arr is not None else {}


def _llm_augment(
    signals: dict,
    coverages: list[dict],
) -> list[dict]:
    applicable = [c for c in coverages if c.get("applicable")]
    if not applicable:
        return []
    try:
        prompt = PIPELINE_AUGMENTATION_PROMPT.format(
            language=signals.get("language") or "(unknown)",
            package_manager=signals.get("package_manager") or "(unknown)",
            architecture=signals.get("architecture_type") or "monolithic",
            deployment=json.dumps(signals.get("deployment", {})),
            domain=signals.get("detected_domain") or "general",
            coverages=_format_coverages_for_prompt(applicable),
        )
        llm = get_llm()
        response = llm.invoke(prompt)
        result = _parse_llm_response(response.content)
        return result.get("pipeline_augmentations") or []
    except Exception:
        return []


def pipeline_augmentation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """K2.2: Compose pipeline augmentations from applicable coverages.

    Reads:
      - state.security_coverages (from coverage_inference_node)
      - detected_technologies (for language + package_manager context)

    Writes:
      - state.pipeline_augmentations (list of {coverage, job, configuration, reason})
      - state.inferred_security_needs (backward-compat container)
    """
    # v9 fix: removed `if state.errors: return state` so the node
    # still runs even if an upstream node (e.g. repository_scan)
    # reported an error. The coverages/augmentations produced here
    # are the primary data the PDF Section 2 needs; without them
    # the report comes out empty.
    coverages = state.get("security_coverages") or []
    if not coverages:
        state["pipeline_augmentations"] = []
        state["inferred_security_needs"] = {
            "security_controls": [],
            "required_tools": [],
            "pipeline_stages": [],
        }
        return state

    technologies = state.get("detected_technologies") or {}
    deployment = state.get("detected_deployment") or {}
    arch_type = (
        state.get("detected_architecture_type")
        or (state.get("detected_architecture") or {}).get("architecture_type")
        or "monolithic"
    )

    signals = {
        "language": technologies.get("primary_language"),
        "package_manager": technologies.get("package_manager"),
        "architecture_type": arch_type,
        "deployment": deployment,
        "detected_domain": state.get("detected_domain"),
    }

    applicable = [c for c in coverages if c.get("applicable")]

    # struktur-v9: LLM call covers all applicable coverages. For each
    # coverage that LLM did NOT return an augmentation for, fall back
    # to the deterministic augmentation library. This ensures 1:1
    # mapping between applicable coverages and augmentations.
    llm_augmentations = _llm_augment(signals, applicable) or []
    llm_covered: set[str] = set()
    for a in llm_augmentations:
        if isinstance(a, dict) and a.get("coverage"):
            llm_covered.add(a["coverage"])

    augmentations: list[dict] = list(llm_augmentations)
    for cov in applicable:
        cov_id = cov.get("id", "")
        if cov_id and cov_id not in llm_covered:
            for aug in DEFAULT_AUGMENTATIONS.get(cov_id, []):
                augmentations.append({
                    "coverage": cov_id,
                    "job": aug["job"],
                    "configuration": aug["configuration"],
                    "reason": f"Default augmentation for {cov_id} coverage (LLM did not produce one)",
                })

    # Validate and normalize
    valid_jobs = {
        "sast", "sca", "secret_scan", "container_scan",
        "compliance_check", "docker_compose_validate",
        "dependency_scan_per_service",
    }
    normalized: list[dict] = []
    for a in augmentations:
        if not isinstance(a, dict):
            continue
        job = a.get("job", "").lower()
        if job not in valid_jobs:
            continue
        normalized.append({
            "coverage": a.get("coverage", ""),
            "job": job,
            "configuration": a.get("configuration", ""),
            "reason": a.get("reason", ""),
        })

    state["pipeline_augmentations"] = normalized

    # Derive security_controls from augmentations + base controls.
    security_controls: list[dict] = []
    seen: set[str] = set()
    for cov in applicable:
        for aug in [a for a in normalized if a["coverage"] == cov["id"]]:
            control_name = aug["job"]
            if control_name in seen:
                continue
            seen.add(control_name)
            security_controls.append({
                "control": control_name,
                "status": "recommended",
                "reason": f"Required for {cov['id']} coverage: {cov.get('reason', '')}",
                "tool": "",
                "tool_version": "latest",
            })

    # Always include base controls
    base_controls = [
        {"control": "lint", "status": "recommended", "reason": "code quality", "tool": "eslint", "tool_version": "latest"},
        {"control": "sast", "status": "recommended", "reason": "static analysis", "tool": "semgrep", "tool_version": "latest"},
        {"control": "secret_scan", "status": "recommended", "reason": "credential leak detection", "tool": "gitleaks", "tool_version": "latest"},
    ]
    for c in base_controls:
        if c["control"] not in seen:
            security_controls.insert(0, c)
            seen.add(c["control"])

    # Required tools (deduplicated by job)
    required_tools: list[dict] = []
    tool_seen: set[str] = set()
    for aug in normalized:
        job = aug["job"]
        tool = {
            "sast": "semgrep",
            "sca": "npm audit",
            "secret_scan": "gitleaks",
            "container_scan": "trivy",
            "compliance_check": "custom",
            "docker_compose_validate": "docker compose",
            "dependency_scan_per_service": "trivy",
        }.get(job, "generic")
        if tool not in tool_seen:
            tool_seen.add(tool)
            required_tools.append({
                "name": tool,
                "purpose": f"for {job}",
                "language": technologies.get("primary_language", "generic"),
            })

    # Pipeline stages (ordered)
    # Arsitektur bukan variabel eksperimen (batasan B7). Semua arsitektur
    # diperlakukan sebagai monolitik tradisional. docker_compose_validate
    # hanya ditambahkan jika ada evidence deployment docker-compose.
    pipeline_stages: list[str] = ["lint"]
    if any(d in str(deployment).lower() for d in ["docker-compose", "docker_compose", "compose"]):
        pipeline_stages.append("docker_compose_validate")
    pipeline_stages.extend(["test", "sast", "sca", "secret_scan"])
    if any(c.get("id") in {"container_security", "dependency_security"} for c in applicable):
        pipeline_stages.append("container_scan")
    if any(c.get("id") == "container_security" for c in applicable):
        pipeline_stages.append("container_build")

    state["inferred_security_needs"] = {
        "security_controls": security_controls,
        "required_tools": required_tools,
        "pipeline_stages": pipeline_stages,
        "security_coverages": applicable,
        "pipeline_augmentations": normalized,
    }

    return state
