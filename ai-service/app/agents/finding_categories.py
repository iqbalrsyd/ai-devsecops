"""
Unified finding category system.

A single finding in this system always carries a `category`. The four
categories the dashboard exposes are:

    - security_finding       : actual security issue (CVE, secret, injection, ...)
    - workflow_config_issue  : the generated YAML is structurally wrong or uses
                               actions/inputs/permissions/env vars that don't
                               exist or are no longer supported.
                               Examples: "GITHUB_TOKEN is now required",
                               "Unexpected input(s) 'args'", "permission denied:
                               write-all".
    - maintenance_warning    : deprecation / version drift that does not break
                               the workflow today but will soon. Examples:
                               "Node.js 20 actions are deprecated",
                               "actions/upload-artifact@v3 will be deprecated".
    - external_service_issue : a third-party service is unreachable / down.
                               Example: "Our services aren't available right
                               now" (GitHub status degradation), npm registry
                               5xx, Docker Hub pull failure, etc.

The risk score is computed ONLY from `security_finding` items. The other
three categories are surfaced in the dashboard and in PR remediation but
never affect `risk_score`.
"""
from __future__ import annotations

import re
from typing import Iterable

# The four dashboard categories.
CATEGORY_SECURITY = "security_finding"
CATEGORY_WORKFLOW_CONFIG = "workflow_config_issue"
CATEGORY_MAINTENANCE = "maintenance_warning"
CATEGORY_EXTERNAL = "external_service_issue"

ALL_CATEGORIES: tuple[str, ...] = (
    CATEGORY_SECURITY,
    CATEGORY_WORKFLOW_CONFIG,
    CATEGORY_MAINTENANCE,
    CATEGORY_EXTERNAL,
)


# Substrings that mean "this is not a security vulnerability, no matter
# what the LLM/heuristic tried to label it as." Used by `classify` to
# re-bucket findings that slipped into the security list.
WORKFLOW_CONFIG_RULES: tuple[tuple[str, str], ...] = (
    (r"githu[bp]_token is now required",                       "missing_github_token_requirement"),
    (r"github_token.*required",                                "missing_github_token_requirement"),
    (r"unexpected\s+input[s()']*",                               "unexpected_action_input"),
    (r"input[^:]*not.*supported",                                "unsupported_action_input"),
    (r"invalid input",                                         "invalid_action_input"),
    (r"unknown input",                                         "invalid_action_input"),
    (r"action does not exist",                                 "action_not_found"),
    (r"unable to resolve action",                              "action_not_found"),
    (r"invalid action parameter",                              "invalid_action_parameter"),
    (r"unsupported action version",                            "unsupported_action_version"),
    (r"action.*not.*supported in this version",                "unsupported_action_version"),
    (r"deprecated.*runtime",                                   "deprecated_runtime"),
    (r"node\.js.*actions are deprecated",                      "deprecated_runtime"),
    (r"invalid permission",                                    "invalid_permission"),
    (r"permission.*denied",                                    "invalid_permission"),
    (r"missing permission",                                    "missing_permission"),
    (r"permission.*write-all",                                 "invalid_permission"),
    (r"permission.*read-all",                                  "invalid_permission"),
    (r"missing environment variable",                          "missing_env_var"),
    (r"required env",                                          "missing_env_var"),
    (r"action input validation",                               "invalid_action_input"),
    (r"action version.*not.*found",                            "unsupported_action_version"),
    (r"action pinned to",                                      "invalid_action_pinning"),
    (r"sha.*does not exist",                                   "invalid_action_sha"),
    (r"action.*is not pinned",                                 "invalid_action_pinning"),
    (r"action.*@.*instead of commit",                          "invalid_action_pinning"),
    (r"invalid workflow yaml",                                 "invalid_workflow_yaml"),
    (r"yaml syntax",                                           "invalid_workflow_yaml"),
    (r"action_not_pinned",                                     "invalid_action_pinning"),
    (r"action_not_found",                                      "action_not_found"),
    (r"missing_permissions",                                   "missing_permission"),
    (r"permissions_too_broad",                                 "invalid_permission"),
    (r"missing_concurrency",                                   "workflow_config_issue"),
    (r"missing_persist_credentials",                           "workflow_config_issue"),
    (r"missing_if_condition",                                  "workflow_config_issue"),
    (r"missing_stage",                                         "missing_security_stage"),
    # GitHub step-summary / runner status messages emitted as
    # check-run annotations. These are NOT security findings — they
    # are noise from the runner itself. Listing them here prevents
    # `classify()` from falling through to `CATEGORY_SECURITY`.
    (r"process completed with (?:exit code|error)",            "runner_step_status"),
    (r"step (?:completed|canceled) with (?:exit code|error)",  "runner_step_status"),
    (r"^annotation: process completed",                        "runner_step_status"),
    (r"the operation was canceled",                            "runner_step_status"),
)

# Substrings that mean "this is a deprecation, not a security risk."
MAINTENANCE_RULES: tuple[tuple[str, str], ...] = (
    (r"actions/upload-artifact@v3.*deprecated",                "deprecated_action_version"),
    (r"actions/checkout@v1.*deprecated",                       "deprecated_action_version"),
    (r"actions/checkout@v2.*deprecated",                       "deprecated_action_version"),
    (r"actions/setup-node@v1.*deprecated",                     "deprecated_action_version"),
    (r"actions/setup-python@v1.*deprecated",                   "deprecated_action_version"),
    (r"node\.js\s*16.*deprecated",                             "deprecated_runtime"),
    (r"node\.js\s*20.*deprecated",                             "deprecated_runtime"),
    (r"set-output.*deprecated",                                "deprecated_command"),
    (r"save-state.*deprecated",                                "deprecated_command"),
    (r"::set-output",                                          "deprecated_command"),
    (r"::save-state",                                          "deprecated_command"),
    (r"::warning::.*deprecated",                               "deprecated_command"),
    (r"windows-2019.*deprecated",                              "deprecated_runner"),
    (r"macos-10.*deprecated",                                  "deprecated_runner"),
    (r"ubuntu-18\.04.*deprecated",                             "deprecated_runner"),
    (r"ubuntu-20.*deprecated",                                 "deprecated_runner"),
    (r"deprecation",                                           "deprecated_feature"),
    (r"will be removed",                                       "deprecated_feature"),
    (r"maintenance warning",                                   "deprecated_feature"),
    (r"runtime_version",                                       "runtime_drift"),
)

# Substrings that mean "this is a third-party service outage, not your fault."
# IMPORTANT: This list must match the exact text emitted by upstream HTTP
# clients (httpx, requests) when an upstream returns a 5xx. The
# generator pipeline calls `httpx.get(...)` against api.github.com;
# when GitHub's edge returns 502 Bad Gateway the exception text is
# literally "Request failed with status code 502" — that string must
# NEVER be classified as a security finding or a workflow configuration
# issue; it is an external service issue and the workflow should not be
# blocked by it.
EXTERNAL_SERVICE_RULES: tuple[tuple[str, str], ...] = (
    (r"our services aren't available right now",               "github_status_degraded"),
    (r"github services aren't available",                      "github_status_degraded"),
    (r"unable to connect to .*github\.com",                    "github_unreachable"),
    (r"connection to .* timed out",                            "network_timeout"),
    (r"econnrefused",                                          "connection_refused"),
    (r"request failed with status code\s*502",                 "upstream_502"),
    (r"request failed with status code\s*5\d\d",               "upstream_5xx"),
    (r"502 bad gateway",                                       "upstream_502"),
    (r"503 service unavailable",                               "upstream_503"),
    (r"500 internal server error",                             "upstream_5xx"),
    (r"504 gateway timeout",                                   "upstream_504"),
    (r"llmprovidererror|llm unavailable|ai_service_unavailable", "ai_service_unavailable"),
    (r"npm registry.*down",                                    "npm_registry_outage"),
    (r"registry-1\.docker\.io.*unavailable",                   "docker_hub_outage"),
    (r"rate limit exceeded",                                   "rate_limit"),
    (r"api rate limit exceeded for",                           "rate_limit"),
    (r"abuse detection mechanism",                             "github_abuse_detection"),
    (r"resource not accessible by integration",                "integration_permission_gap"),
    (r"the requested url returned error",                      "upstream_error"),
    (r"connection reset by peer",                              "connection_reset"),
)


# Helper used by the generator pipeline to translate a raw exception
# from `httpx.get(...)` or `llm.invoke(...)` into a structured
# external_service_issue finding. This is the canonical entry point for
# converting "Request failed with status code 502" into the right
# bucket — never raise or treat as a security finding.
def classify_httpx_exception(exc: Exception, source: str = "github_api") -> dict | None:
    """Map an httpx/requests exception to an external_service_issue.

    Returns None if the exception is not a transient external outage
    (e.g. a real validation error), in which case the caller is free to
    bubble the exception. The returned dict is shaped exactly like a
    `workflow_config_issue_node` finding so the dashboard buckets it
    consistently.

    Examples:
        httpx.HTTPStatusError("Client error '502 Bad Gateway' ...")
        requests.exceptions.HTTPError("Request failed with status code 502")
    """
    msg = str(exc) or ""
    msg_lower = msg.lower()

    if "status code 502" in msg or "bad gateway" in msg_lower:
        rule = "upstream_502"
    elif "status code 503" in msg or "service unavailable" in msg_lower:
        rule = "upstream_503"
    elif "status code 504" in msg or "gateway timeout" in msg_lower:
        rule = "upstream_504"
    elif "status code 5" in msg:
        rule = "upstream_5xx"
    elif "timeout" in msg_lower or "timed out" in msg_lower:
        rule = "network_timeout"
    elif "econnrefused" in msg_lower or "connection refused" in msg_lower:
        rule = "connection_refused"
    elif "connection reset" in msg_lower:
        rule = "connection_reset"
    elif "name or service not known" in msg_lower or "dns" in msg_lower:
        rule = "dns_resolution_failed"
    else:
        return None

    return {
        "category": CATEGORY_EXTERNAL,
        "rule": rule,
        "source": source,
        "message": (
            f"Upstream '{source}' returned a transient error: {msg[:300]}. "
            "This is an external service issue, NOT a security finding "
            "or a workflow configuration issue."
        ),
        "suggestion": (
            "Re-run the pipeline after a short delay. External 5xx errors do "
            "NOT require a code change. The risk score is unaffected. "
            "If this persists for more than a few minutes, check "
            "https://www.githubstatus.com/."
        ),
        "severity": "informational",
        "exception_type": type(exc).__name__,
    }


def _scan(rules: tuple[tuple[str, str], ...], text: str) -> str | None:
    for pattern, canonical in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return canonical
    return None


def _coerce_text(finding: dict) -> str:
    parts = [
        finding.get("type", ""),
        finding.get("rule", ""),
        finding.get("message", ""),
        finding.get("explanation", ""),
        finding.get("suggestion", ""),
        finding.get("recommendation", ""),
        finding.get("error", ""),
    ]
    return " ".join(str(p) for p in parts if p)


def classify(finding: dict) -> str:
    """Return the canonical category for a finding.

    The classification order is:
        1. external service outage rules
        2. maintenance / deprecation rules
        3. workflow-config / compatibility rules
        4. fallback = security_finding

    IMPORTANT: this function ALWAYS re-classifies from the finding's
    content text. It ignores any pre-existing `category` key so that
    downstream aggregation (partition, classify_many) produces a
    consistent, content-based bucket assignment.
    """
    if not isinstance(finding, dict):
        return CATEGORY_SECURITY

    text = _coerce_text(finding)
    if not text:
        return CATEGORY_SECURITY

    if _scan(EXTERNAL_SERVICE_RULES, text):
        return CATEGORY_EXTERNAL
    if _scan(MAINTENANCE_RULES, text):
        return CATEGORY_MAINTENANCE
    if _scan(WORKFLOW_CONFIG_RULES, text):
        return CATEGORY_WORKFLOW_CONFIG
    return CATEGORY_SECURITY


def classify_many(findings: Iterable[dict]) -> list[dict]:
    """Return a list copy with each finding tagged with `category`."""
    out: list[dict] = []
    for f in findings or []:
        if not isinstance(f, dict):
            out.append(f)
            continue
        copy = dict(f)
        copy["category"] = classify(f)
        out.append(copy)
    return out


def partition(findings: Iterable[dict]) -> dict[str, list[dict]]:
    """Bucket findings into the four dashboard categories."""
    buckets: dict[str, list[dict]] = {c: [] for c in ALL_CATEGORIES}
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        copy = dict(f)
        # Always re-classify so we don't trust stale `category` fields.
        # This ensures e.g. `deprecated_action_version` is correctly put
        # into the maintenance bucket even if an upstream validator set
        # it to workflow_config_issue.
        copy["category"] = classify(copy)
        buckets[copy["category"]].append(copy)
    return buckets


def is_security_finding(finding: dict) -> bool:
    return classify(finding) == CATEGORY_SECURITY


def filter_security(findings: Iterable[dict]) -> list[dict]:
    """Drop every non-security finding. Used by the risk assessor."""
    return [f for f in (findings or []) if is_security_finding(f)]


def empty_dashboard() -> dict:
    """Return a fresh dashboard with the four categories, all empty."""
    return {
        CATEGORY_SECURITY: [],
        CATEGORY_WORKFLOW_CONFIG: [],
        CATEGORY_MAINTENANCE: [],
        CATEGORY_EXTERNAL: [],
        "security_count": 0,
        "workflow_config_count": 0,
        "maintenance_count": 0,
        "external_count": 0,
        "total_count": 0,
    }


def build_dashboard(*sources: Iterable[dict] | None) -> dict:
    """Merge any number of finding lists into the four-category dashboard.

    `sources` may contain `state["findings"]`, `state["validation_findings"]`,
    and `result["log_analysis"]`. All are funneled through `classify_many()`
    and then partitioned. The output keys are the four category names plus
    convenience counts.
    """
    merged: list[dict] = []
    for src in sources:
        for f in src or []:
            if isinstance(f, dict):
                merged.append(f)

    bucketed = partition(merged)
    return {
        **bucketed,
        "security_count": len(bucketed[CATEGORY_SECURITY]),
        "workflow_config_count": len(bucketed[CATEGORY_WORKFLOW_CONFIG]),
        "maintenance_count": len(bucketed[CATEGORY_MAINTENANCE]),
        "external_count": len(bucketed[CATEGORY_EXTERNAL]),
        "total_count": sum(len(v) for v in bucketed.values()),
    }
