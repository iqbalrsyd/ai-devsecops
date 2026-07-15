"""CVSS-Driven Coverage Gap Job Generation Node (K2.4 - CVSS-Driven Jobs).

This node is run AFTER `security_analyzer` (Stage 4) and operates on the
FINAL findings list (which carries CVSS scores per finding). Its purpose
is NOT to inflate the number of custom jobs but to CLOSE the gap between
applicable security coverages and the coverages that are already
serviced by standard + domain + LLM-designed jobs from earlier stages.

For each uncovered coverage, the LLM proposes 1 custom job that is
JUSTIFIED by a top-CVSS finding in that coverage. The output is
appended to `state["cvss_driven_jobs"]` (separate field from
`state["job_designs"]` to keep the K2.4 metric traceable).

The "gap" is defined as:
    coverage_gap = applicable_coverages
                   minus (coverages served by standard jobs)
                   minus (coverages served by domain job)
                   minus (coverages served by job_reasoning designs)

Strategy (per K2.4 doc, README §9):
  - Cap at 2-3 custom jobs per run.
  - Each job MUST be justified by ≥1 top-CVSS finding.
  - Each job MUST cite its target coverage.
  - Each job MUST have ≥1 concrete action + 1 sarif_upload.
  - Job name MUST be kebab-case, prefix should reflect coverage
    (e.g. `cms-`, `data-`, `iot-`, `auth-`, `logging-`).

Reads:
  - findings (with cvss_score per finding)
  - security_coverages (with applicable flag)
  - detected_domain / domain_threats / features
  - primary_language / frameworks
  - job_designs (from job_reasoning node — already in state)

Writes:
  - state["cvss_driven_jobs"]         : list of validated design dicts
  - state["cvss_driven_jobs_reasoning"]: human-readable explanation
  - state["cvss_driven_jobs_count"]   : int
"""
import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


# ── Standard + domain job coverage map ──────────────────────────────
# These are the coverages that the standard and domain jobs already
# serve. The gap is the set difference applicable_coverages - these.
STANDARD_JOB_COVERAGES = {
    "authentication_security",  # sast + secret-scan
    "api_security",            # sast
    "data_security",           # sast + dep-scan
    "dependency_security",     # dep-scan
    "file_upload_security",    # sast
    "container_security",      # container-scan
}
DOMAIN_JOB_COVERAGES = {
    "e-commerce":  {"payment_security"},
    "blog":        {"cms_security"},
    "iot":         {"iot_security"},
}


# ── Prompt ─────────────────────────────────────────────────────────
CVSS_DRIVEN_JOB_PROMPT = """You are a senior DevSecOps Pipeline Architect.

## Goal

Generate 1-2 ADDITIONAL custom CI/CD jobs that CLOSE THE GAP between
applicable security coverages and the coverages already served by
standard + domain + earlier LLM-designed jobs.

## Repository Context

- Language: {language}
- Domain: {domain}
- Architecture: {architecture}

## Applicable Security Coverages (from coverage_inference)

{applicable_coverages}

## Coverages Already Served (by standard + domain + earlier job_reasoning designs)

{covered_coverages}

## Coverage Gap (the coverages we MUST close)

{coverage_gap}

## Top CVSS Findings (already scored in security_analyzer)

{top_findings}

## How to use these findings as JUSTIFICATION

Each custom job you propose MUST be justified by AT LEAST ONE top
finding. The justification field must cite:
  - The finding's `file:line` location
  - The CVSS score
  - Why the existing standard jobs do NOT cover this specific risk
  - What the new job adds that closes the gap

## Hard constraints

- Maximum 2 custom jobs (focus on highest-risk gap).
- Each job MUST target exactly one coverage_id from `coverage_gap`.
- Each job MUST cite ≥1 top finding in its `reasoning` field.
- Job name MUST be kebab-case, ≤ 40 chars.
- Job name prefix should reflect the coverage being closed
  (e.g. `cms-`, `data-`, `iot-`, `auth-`, `logging-`).
- DO NOT duplicate names of standard / domain / earlier LLM jobs.
- Each job MUST have ≥2 actions, including exactly one `sarif_upload`.
- If the coverage gap is empty, return `cvss_driven_jobs: []`.
- If there is no top finding in a gap coverage, skip that coverage.

## Return ONLY valid JSON

{{
  "cvss_driven_jobs": [
    {{
      "name": "kebab-case-name",
      "coverage": "<coverage_id from coverage_gap>",
      "reasoning": "Top finding <file>:<line> CVSS=<score> shows <risk>. Standard job `<std>` does not cover this because <reason>. This job adds <new check> that catches <specific pattern>.",
      "cvss_justified_by": {{
        "file": "<file>",
        "line": <int>,
        "cvss": <float>,
        "cve_or_rule": "<CVE-id or rule-id>"
      }},
      "actions": [
        {{"type": "shell_check", "name": "<step>", "script": "<bash>"}},
        {{"type": "sarif_upload", "category": "<sarif category>"}}
      ],
      "configuration": {{
        "continue_on_error": true,
        "timeout_minutes": 10
      }}
    }}
  ]
}}
"""


# ── Structural validation ──────────────────────────────────────────
REQUIRED_FIELDS = {"name", "coverage", "actions", "reasoning", "cvss_justified_by"}
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
VALID_ACTION_TYPES = {"shell_check", "semgrep_rule", "python_script", "sarif_upload"}
ALREADY_SERVED_KEYS = {
    "lint", "test", "sast", "secret-scan", "dependency-scan",
    "container-scan", "container-build", "build", "sbom",
    "pci-dss-check", "csp-headers", "mqtt-security",
}


def _validate_job(job: dict) -> bool:
    if not isinstance(job, dict):
        return False
    if not REQUIRED_FIELDS.issubset(job.keys()):
        return False
    name = job.get("name", "")
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        return False
    if name in ALREADY_SERVED_KEYS:
        return False
    coverage = job.get("coverage", "")
    if not isinstance(coverage, str) or not coverage:
        return False
    reasoning = job.get("reasoning", "")
    if not isinstance(reasoning, str) or len(reasoning) < 50:
        return False
    cvss_just = job.get("cvss_justified_by", {})
    if not isinstance(cvss_just, dict) or not cvss_just.get("file"):
        return False
    actions = job.get("actions", [])
    if not isinstance(actions, list) or len(actions) < 2:
        return False
    has_sarif = False
    for a in actions:
        if not isinstance(a, dict):
            return False
        atype = a.get("type", "")
        if atype not in VALID_ACTION_TYPES:
            return False
        if atype == "sarif_upload":
            has_sarif = True
    if not has_sarif:
        return False
    return True


def _parse_llm_json(content: str) -> dict:
    from app.agents.llm_response_parser import (
        parse_llm_json_object, parse_llm_json_array,
    )
    obj = parse_llm_json_object(content)
    if obj is not None:
        return obj
    arr = parse_llm_json_array(content)
    return arr if isinstance(arr, dict) else {}


def _compute_coverage_gap(state: PipelineEngineerState) -> tuple[set[str], set[str], set[str]]:
    """Return (applicable, already_served, gap)."""
    coverages = state.get("security_coverages") or []
    applicable = {c.get("id") for c in coverages if c.get("applicable") and c.get("id")}

    served = set(STANDARD_JOB_COVERAGES)
    served |= DOMAIN_JOB_COVERAGES.get(state.get("detected_domain") or "", set())

    for design in state.get("job_designs") or []:
        cvg = design.get("coverage")
        if cvg:
            served.add(cvg)

    gap = applicable - served
    return applicable, served, gap


def _top_findings_by_coverage(
    findings: list[dict], coverage_gap: set[str], limit_per_cov: int = 3
) -> dict[str, list[dict]]:
    """Return {coverage_id: [top findings sorted by CVSS desc]}.

    Pure function — accepts a list of finding dicts and a set of
    coverage_ids. Useful for both the node execution and unit testing.
    """
    by_cov: dict[str, list[dict]] = {c: [] for c in coverage_gap}
    for f in findings or []:
        cov = f.get("security_coverage")
        if cov in by_cov:
            by_cov[cov].append(f)
    for cov in by_cov:
        by_cov[cov].sort(
            key=lambda x: float(x.get("cvss_score") or 0.0),
            reverse=True,
        )
        by_cov[cov] = by_cov[cov][:limit_per_cov]
    return by_cov


def _format_findings_for_prompt(findings: list[dict]) -> str:
    if not findings:
        return "(no findings in this coverage)"
    lines = []
    for f in findings:
        lines.append(
            f"- {f.get('file', '?')}:{f.get('line', '?')} "
            f"rule={f.get('rule_id', '?')} "
            f"CVSS={f.get('cvss_score', 0.0)} "
            f"({f.get('severity', '?')}) "
            f"msg={f.get('message', '')[:80]}"
        )
    return "\n".join(lines)


def _llm_propose_jobs(
    signals: dict,
) -> list[dict]:
    try:
        prompt = CVSS_DRIVEN_JOB_PROMPT.format(
            language=signals.get("primary_language") or "unknown",
            domain=signals.get("detected_domain") or "general",
            architecture=signals.get("architecture_type") or "monolithic",
            applicable_coverages=", ".join(sorted(signals["applicable"])) or "(none)",
            covered_coverages=", ".join(sorted(signals["covered"])) or "(none)",
            coverage_gap=", ".join(sorted(signals["gap"])) or "(empty — no gap)",
            top_findings=signals["top_findings_text"],
        )
        llm = get_llm()
        response = llm.invoke(prompt)
        result = _parse_llm_json(response.content)
        return result.get("cvss_driven_jobs") or []
    except Exception as e:
        print(f"[cvss_driven_job_generation] LLM call failed: {e}")
        return []


def _deterministic_fallback(
    coverage_gap: set[str],
    top_findings_by_cov: dict[str, list[dict]],
    existing_names: set[str],
) -> list[dict]:
    """If LLM fails, generate 1 deterministic job from the top-CVSS
    finding in the highest-priority gap coverage. Priority order is
    hard-coded to prefer cms > data > auth > api > logging."""
    PRIORITY = [
        "cms_security", "data_security", "authentication_security",
        "api_security", "logging_security", "file_upload_security",
    ]
    chosen_cov = None
    for c in PRIORITY:
        if c in coverage_gap and top_findings_by_cov.get(c):
            chosen_cov = c
            break
    if not chosen_cov:
        return []
    top = top_findings_by_cov[chosen_cov][0]
    cov_prefix = chosen_cov.split("_")[0]
    name = f"{cov_prefix}-cvss-top-finding-check"
    if name in existing_names:
        return []
    return [{
        "name": name,
        "coverage": chosen_cov,
        "reasoning": (
            f"Top CVSS finding {top.get('file', '?')}:{top.get('line', '?')} "
            f"CVSS={top.get('cvss_score', 0.0)} ({top.get('severity', '?')}). "
            f"Standard jobs do not cover this because they are generic; "
            f"this fallback job explicitly checks for the pattern at the "
            f"top finding's location."
        ),
        "cvss_justified_by": {
            "file": top.get("file", "?"),
            "line": top.get("line", 0),
            "cvss": top.get("cvss_score", 0.0),
            "cve_or_rule": top.get("rule_id") or top.get("cve") or "?",
        },
        "actions": [
            {
                "type": "shell_check",
                "name": "check-top-finding-pattern",
                "script": f"echo 'checking {top.get('file', '?')}:{top.get('line', '?')}'",
            },
            {"type": "sarif_upload", "category": "cvss-fallback"},
        ],
        "configuration": {
            "continue_on_error": True,
            "timeout_minutes": 5,
        },
    }]


def cvss_driven_job_generation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    applicable, covered, gap = _compute_coverage_gap(state)

    if not gap:
        state["cvss_driven_jobs"] = []
        state["cvss_driven_jobs_reasoning"] = (
            f"No coverage gap detected. Applicable: {sorted(applicable)}, "
            f"Covered: {sorted(covered)}. Gap=∅ — system is already at "
            f"max applicable coverage."
        )
        state["cvss_driven_jobs_count"] = 0
        return state

    top_findings_by_cov = _top_findings_by_coverage(
        state.get("findings") or [], gap, limit_per_cov=3
    )
    gap_with_findings = {c for c in gap if top_findings_by_cov.get(c)}
    if not gap_with_findings:
        state["cvss_driven_jobs"] = []
        state["cvss_driven_jobs_reasoning"] = (
            f"Coverage gap detected ({sorted(gap)}) but no top CVSS "
            f"findings available in those coverages — cannot justify "
            f"custom jobs without empirical evidence."
        )
        state["cvss_driven_jobs_count"] = 0
        return state

    top_findings_lines = []
    for cov in sorted(gap_with_findings):
        top_findings_lines.append(f"\n[{cov}]")
        top_findings_lines.append(_format_findings_for_prompt(top_findings_by_cov[cov]))
    top_findings_text = "\n".join(top_findings_lines) or "(no findings)"

    technologies = state.get("detected_technologies") or {}
    signals = {
        "primary_language": technologies.get("primary_language"),
        "detected_domain": state.get("detected_domain"),
        "architecture_type": state.get("detected_architecture_type") or "monolithic",
        "applicable": applicable,
        "covered": covered,
        "gap": gap_with_findings,
        "top_findings_text": top_findings_text,
    }

    raw_jobs = _llm_propose_jobs(signals)

    existing_names = {d.get("name") for d in (state.get("job_designs") or [])}
    validated: list[dict] = []
    for j in raw_jobs:
        if _validate_job(j) and j["name"] not in existing_names and j["coverage"] in gap:
            validated.append(j)
            existing_names.add(j["name"])
        if len(validated) >= 2:
            break

    if not validated:
        validated = _deterministic_fallback(
            gap_with_findings, top_findings_by_cov, existing_names
        )

    state["cvss_driven_jobs"] = validated
    state["cvss_driven_jobs_reasoning"] = (
        f"Coverage gap analysis: applicable={sorted(applicable)}, "
        f"served={sorted(covered)}, gap={sorted(gap)}. "
        f"LLM produced {len(raw_jobs)} raw proposals; "
        f"{len(validated)} validated. "
        f"Justified by top CVSS findings in coverages: {sorted(gap_with_findings)}."
    )
    state["cvss_driven_jobs_count"] = len(validated)
    return state
