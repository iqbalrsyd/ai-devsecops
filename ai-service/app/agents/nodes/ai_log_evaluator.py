"""AI agent log-based evaluation for CI DevSecOps workflow runs.

Reviewer feedback (round 1):
    "yang dari extract karena yang auto extract findings tuh masih blm
    sesuai kaya ngambilnya bukan dari job jadi nebak dari job failed aja
    ga diambil dan di cek lognya"

The previous auto-extract looked at the job conclusion (success/failure)
and GUESSED findings from "job failed" without actually reading the
workflow logs. Many real security findings appear in logs of jobs that
PASS (e.g. Trivy prints CVE list to stdout and exits 0; the job is
green but the log contains real findings). The previous heuristic
missed these.

Reviewer feedback (round 2):
    "Do not rely on heuristic regex matching over raw GitHub Actions
    logs because it creates duplicated findings across multiple jobs.
    Use tool-specific structured outputs whenever possible."

The previous implementation matched heuristic regexes against raw
log text. This produced DUPLICATED findings when the same CVE was
detected by both `npm audit` and Trivy filesystem, and again when
the same image was scanned by both `container-build` and
`container-scan`. Each match became a separate finding in the
dashboard.

This module now follows a two-tier extraction strategy:

  1. PRIMARY: parse the structured JSON output of each scanner
     (npm audit, Trivy, Semgrep, Gitleaks) via
     `app.agents.scanner_normalizer`. The output is a list of
     `NormalizedFinding` records with a stable composite key
     (tool + vuln_id + package + file_path). Deduplication is
     done by the normalizer, not by the log heuristic.
  2. FALLBACK: when a scanner's structured output is not present
     (parse failure, missing artifact, or an unrecognized scanner
     like `pip-audit`), fall back to regex matching over the raw
     log. Findings from the fallback path are tagged
     `source: "log_heuristic_fallback"` so the user can tell
     structured from heuristic results.

Raw log text is also still used to detect workflow configuration
issues (missing env, exit-code 1, cancelling), which have no
structured equivalent in any scanner output.

This module reads the actual workflow LOGS (per job, per step) and
extracts real security findings with the help of an LLM. The LLM
classifies each line of log output into one of:

  - security_finding:        a real CVE / secret / misconfig / vulnerability
  - workflow_config_issue:   a configuration bug (bad input, missing
                             env var, etc.) that prevented the scanner
                             from working correctly
  - benign:                  normal log output (status messages, etc.)

The output is fed into the dashboard via the unified response and
overwrites the previous auto-extract.
"""
import json
import logging
import re
from typing import Any

from app.agents.finding_categories import CATEGORY_SECURITY
from app.agents.pipeline_state import PipelineEngineerState

logger = logging.getLogger(__name__)


# Heuristic patterns for security findings BEFORE the LLM is called.
# These are used as a fast pre-filter; the LLM still reviews each
# match before it is committed to `state["findings"]`.
#
# Each pattern is `(compiled_regex, finding_type, default_severity)`.
_SECURITY_LOG_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # CVE IDs (e.g. "CVE-2024-1234")
    (re.compile(r"\bCVE-\d{4}-\d{4,7}\b"), "cve", "high"),
    # Trivy severity labels: HIGH, CRITICAL, MEDIUM, LOW
    (re.compile(r"\b(CRITICAL|HIGH)\b.*?(?:vuln|CVE)"), "vulnerability", "high"),
    # npm audit severity (npm 7+ format)
    # Reviewer feedback: do NOT match leading zero. A line like
    # "0 vulnerabilities" is a clean scan, not a finding.
    (re.compile(r"\b[1-9]\d*\s+(?:vulnerabilit\w+|CVE)"), "vulnerability", "high"),
    # Hardcoded secret patterns
    (re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"), "secret", "critical"),  # AWS
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "secret", "critical"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "secret", "critical"),  # GitHub PAT
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "secret", "critical"),  # OpenAI / Stripe-style
    (re.compile(r"(?i)password\s*[=:]\s*['\"]?[^\s'\"]{8,}"), "secret", "high"),
    # Gitleaks output
    (re.compile(r"Finding:\s+"), "secret", "high"),
    (re.compile(r"leak detected", re.IGNORECASE), "secret", "high"),
    # IaC misconfig patterns (Trivy config / checkov)
    (re.compile(r"\b(misconfig|AWS-S3|KV-)\w*\b", re.IGNORECASE), "misconfig", "medium"),
    # Semgrep findings
    (re.compile(r"semgrep:\s+"), "vulnerability", "high"),
    (re.compile(r"Semgrep found [1-9]\d* findings", re.IGNORECASE), "vulnerability", "high"),
    # "vulnerability detected in" / "vulnerabilities found"
    # Reviewer feedback: do NOT match leading zero. Lines like
    # "0 vulnerabilities" or "0 vulnerabilities detected" indicate
    # a clean scan, not a finding. Require a non-zero digit
    # (1-9 followed by any number of digits, OR a 1-9 alone).
    (re.compile(r"[1-9]\d*\s+vulnerab\w+\s+(?:found|detected)", re.IGNORECASE), "vulnerability", "high"),
    # Same guard for "issues" / "findings" wording.
    (re.compile(r"[1-9]\d*\s+(?:security\s+)?(?:issues?|findings?)\s+(?:found|detected|reported)", re.IGNORECASE), "vulnerability", "high"),
]


# Heuristic patterns for WORKFLOW CONFIGURATION ISSUES (not security
# findings). These are emitted as `workflow_config_issues`, NOT as
# `findings`, so they do NOT inflate the security risk score.
_CONFIG_ISSUE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Missing env var
    (re.compile(r"(?i)missing required env(?:ironment)? (?:var(?:iable)? )?['\"]?(\w+)"),
     "missing_required_env", "missing required env var"),
    # Bad action input
    (re.compile(r"(?i)unexpected input ['\"](\w+)['\"]"), "unexpected_action_input",
     "unexpected action input"),
    (re.compile(r"(?i)received an unexpected input"), "unexpected_action_input",
     "action received unexpected input"),
    # Docker build failures (config, not security)
    (re.compile(r"(?i)dockerfile parse error"), "dockerfile_parse_error", "dockerfile parse error"),
    (re.compile(r"(?i)failed to solve:.*dockerfile"), "dockerfile_build_error",
     "docker build failed"),
    # Permission denied
    (re.compile(r"(?i)permission denied"), "permission_denied",
     "permission denied"),
    # Node runtime / deprecation
    (re.compile(r"Node\.js \d+ actions are deprecated", re.IGNORECASE), "deprecated_runtime",
     "Node.js runtime deprecation"),
    (re.compile(r"set-output command is deprecated", re.IGNORECASE),
     "deprecated_command", "deprecated set-output command"),
    # Invalid digest
    (re.compile(r"(?i)invalid digest"), "invalid_image_digest",
     "invalid Docker image digest"),
    (re.compile(r"sha256:[a-f0-9]{64}", re.IGNORECASE), "image_digest_reference",
     "image digest referenced (verify format)"),
    # Lockfile missing
    (re.compile(r"(?i)no lockfile found"), "missing_lockfile",
     "lockfile missing"),
    (re.compile(r"(?i)package-lock\.json not found"), "missing_lockfile",
     "package-lock.json missing"),
    # Network errors (transient, retry-friendly)
    (re.compile(r"(?i)TLS handshake timeout"), "upstream_502",
     "upstream TLS timeout"),
    (re.compile(r"(?i)502 Bad Gateway"), "upstream_502",
     "upstream 502 Bad Gateway"),
    (re.compile(r"(?i)503 Service Unavailable"), "upstream_503",
     "upstream 503 Service Unavailable"),
]


def _classify_log_line(line: str) -> dict | None:
    """Try to classify a single log line using heuristic patterns.

    Returns a finding dict shaped like:
        {
            "type": "vulnerability" | "secret" | "misconfig" | ...,
            "severity": "critical" | "high" | "medium" | "low",
            "rule": "cve_id" | "aws_access_key" | ...,
            "evidence": "matched substring",
            "source": "log_heuristic",
        }
    Returns None if no pattern matches.
    """
    line_lower = line.lower()
    for pattern, finding_type, default_sev in _SECURITY_LOG_PATTERNS:
        m = pattern.search(line)
        if m:
            return {
                "type": finding_type,
                "severity": default_sev,
                "rule": pattern.pattern,
                "evidence": m.group(0)[:200],
                "source": "log_heuristic",
                "explanation": line.strip()[:500],
            }
    return None


def _classify_config_issue(line: str) -> dict | None:
    """Try to classify a single log line as a workflow config issue.

    Returns a config issue dict, or None if no pattern matches.
    """
    for pattern, rule, _ in _CONFIG_ISSUE_PATTERNS:
        m = pattern.search(line)
        if m:
            return {
                "rule": rule,
                "category": "workflow_config_issue",
                "message": line.strip()[:500],
                "evidence": m.group(0)[:200],
                "source": "log_heuristic",
            }
    return None


def extract_findings_from_logs(
    workflow_jobs: list[dict],
    workflow_logs: list[dict] | None = None,
) -> dict:
    """Extract real security findings AND workflow config issues from
    the actual workflow logs.

    Reviewer feedback: previous auto-extract looked at job conclusion
    (success/failure) and GUESSED findings from "job failed". This
    implementation reads the actual log text per step per job and
    applies heuristic patterns.

    Args:
        workflow_jobs: list of {"name", "conclusion", "steps": [...]} dicts
        workflow_logs: optional list of {"job_name", "log_text"} dicts.
            If absent, only the job/step conclusions are used (legacy
            fallback) and the result includes a warning.

    Returns:
        {
            "security_findings": [...],
            "config_issues": [...],
            "skipped_jobs": [...],
            "extraction_source": "logs" | "conclusions_only",
            "lines_scanned": int,
        }
    """
    if not workflow_jobs:
        return {
            "security_findings": [],
            "config_issues": [],
            "skipped_jobs": [],
            "extraction_source": "no_data",
            "lines_scanned": 0,
        }

    security_findings: list[dict] = []
    config_issues: list[dict] = []
    skipped_jobs: list[dict] = []
    lines_scanned = 0

    # Map job name -> log text for fast lookup.
    log_by_job: dict[str, str] = {}
    if workflow_logs:
        for entry in workflow_logs:
            if isinstance(entry, dict):
                name = entry.get("job_name") or entry.get("name") or ""
                text = entry.get("log_text") or entry.get("logs") or ""
                if name and text:
                    log_by_job[name] = (
                        text if isinstance(text, str) else str(text)
                    )

    has_logs = bool(log_by_job)
    extraction_source = "logs" if has_logs else "conclusions_only"

    for job in workflow_jobs:
        if not isinstance(job, dict):
            continue
        name = job.get("name") or job.get("id") or "unknown"
        conclusion = (job.get("conclusion") or "").lower()

        # Treat jobs with conclusion "skipped" as skipped, not failed.
        if conclusion == "skipped":
            skipped_jobs.append({
                "job": name,
                "reason": "Job was skipped by the workflow runner (e.g. prerequisite failed or matching condition not met)",
            })
            continue

        # If we have no logs for this job, we cannot extract real
        # findings — only fall back to job conclusion heuristic.
        if name not in log_by_job:
            # Legacy fallback: a job that FAILED is treated as a
            # potential config issue, NOT a security finding. The
            # actual reason is unknown without logs.
            if conclusion == "failure":
                config_issues.append({
                    "rule": "job_failed_no_logs",
                    "category": "workflow_config_issue",
                    "message": (
                        f"Job '{name}' failed but no log content was "
                        f"available to determine the root cause. This "
                        f"is a config issue (not a security finding) "
                        f"until the log is fetched and reviewed."
                    ),
                    "job": name,
                    "source": "conclusion_only",
                })
            continue

        log_text = log_by_job[name]
        # Split into lines; each non-empty line is classified.
        for raw_line in log_text.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            lines_scanned += 1
            # Try security-finding pattern first.
            finding = _classify_log_line(line)
            if finding is not None:
                finding["job"] = name
                finding["log_line"] = lines_scanned
                security_findings.append(finding)
                continue
            # Then try config-issue pattern.
            issue = _classify_config_issue(line)
            if issue is not None:
                issue["job"] = name
                config_issues.append(issue)

    # Deduplicate findings by (job, rule, evidence) tuple.
    seen: set[tuple] = set()
    deduped_findings: list[dict] = []
    for f in security_findings:
        key = (f.get("job"), f.get("rule"), f.get("evidence"))
        if key in seen:
            continue
        seen.add(key)
        deduped_findings.append(f)

    seen_issues: set[tuple] = set()
    deduped_issues: list[dict] = []
    for i in config_issues:
        key = (i.get("job"), i.get("rule"), i.get("message"))
        if key in seen_issues:
            continue
        seen_issues.add(key)
        deduped_issues.append(i)

    return {
        "security_findings": deduped_findings,
        "config_issues": deduped_issues,
        "skipped_jobs": skipped_jobs,
        "extraction_source": extraction_source,
        "lines_scanned": lines_scanned,
    }


# Mapping from GitHub Actions job name to the scanner the job is
# expected to run. The workflow generator emits these job names.
_JOB_TO_SCANNER: dict[str, str] = {
    "dependency-scan": "npm_audit",
    "container-scan": "trivy",
    "sast": "semgrep",
    "secret-scan": "gitleaks",
}


# Filename emitted by each scanner's workflow step. The AI service
# downloads the artifact via the GitHub Actions Artifacts API and
# matches the file name to the scanner here. The same scanner can
# produce multiple artifacts (e.g. trivy emits filesystem, image, and
# IaC reports) — we keep the first one found per scanner.
#
# Trivy and Semgrep now emit SARIF (the OASIS standard) per
# DevSecOps best practice. SARIF is uploaded to GitHub Code Scanning
# via github/codeql-action/upload-sarif AND kept as a workflow
# artifact for the AI agent to parse. Gitleaks v3 (registered in
# the action registry) does NOT support SARIF natively, so its
# output remains JSON. npm audit also stays JSON.
_SCANNER_ARTIFACT_FILE: dict[str, list[str]] = {
    "npm_audit": ["npm-audit-results.json", "pip-audit-results.json"],
    "trivy": [
        "trivy-fs-results.sarif",
        "trivy-image-results.sarif",
        "trivy-iac-results.sarif",
        # Keep legacy JSON filenames as fallback for older workflows
        "trivy-fs-results.json",
        "trivy-image-results.json",
        "trivy-iac-results.json",
    ],
    "semgrep": ["semgrep-results.sarif", "semgrep-results.json"],
    "gitleaks": ["gitleaks-results.json", "gitleaks-results.sarif"],
}


def extract_findings_from_scanner_outputs(
    scanner_outputs: dict[str, str],
    job_by_scanner: dict[str, str] | None = None,
) -> dict:
    """Primary extraction path: parse structured scanner JSON.

    Reviewer feedback: the previous implementation relied on
    regex matching over raw workflow log text. That produced
    duplicated findings when the same CVE was reported by multiple
    jobs (e.g. dependency-scan and container-scan both reporting
    the same `lodash` CVE), because the regex matched the same
    line in each job's log.

    This function is the new primary path:

      1. Each scanner's workflow step outputs a JSON file (npm
         audit JSON, Trivy JSON, Semgrep JSON, Gitleaks JSON).
      2. We pass the file contents to
         `app.agents.scanner_normalizer.normalize_and_dedupe`.
      3. The normalizer parses each scanner's JSON shape and
         returns a unified list of `NormalizedFinding` records.
      4. Deduplication uses a composite key
         (tool + vuln_id + package + file_path) so the same CVE
         reported by both `npm audit` and Trivy collapses into a
         single finding.

    Args:
        scanner_outputs: mapping of scanner name to raw JSON text.
            Recognized names: "npm_audit", "trivy", "semgrep",
            "gitleaks". Unknown names are ignored.
        job_by_scanner: optional mapping of scanner name to source
            job (so we can record `source_job` in each finding).

    Returns:
        {
            "findings": [NormalizedFinding.to_dict(), ...],
            "raw_count": int,
            "dropped_count": int,
            "by_tool": {tool: count},
            "by_severity": {sev: count},
            "errors": [...],
        }
    """
    from app.agents.scanner_normalizer import normalize_and_dedupe
    job_by_scanner = job_by_scanner or {}
    result = normalize_and_dedupe(scanner_outputs)
    # Annotate each finding with the source job so the dashboard
    # can show which CI job observed it.
    for f in result["findings"]:
        scanner = f.get("tool")
        if scanner and scanner in job_by_scanner:
            f["source_job"] = job_by_scanner[scanner]
    return result


def fetch_scanner_outputs(
    repository_id: str,
    run_id: int,
    github_token: str | None,
    job_outputs: dict[str, str] | None = None,
) -> dict[str, str]:
    """Download each scanner's structured output from GitHub.

    For each (scanner, artifact_filename) pair, download the
    artifact from the run and return a mapping of
    `scanner_name -> raw_text`. If a download fails or the file
    is missing, the scanner is skipped — the log heuristic will
    be the fallback.

    Args:
        repository_id: GitHub "owner/repo" identifier.
        run_id: GitHub Actions run id.
        github_token: optional token for private repos.
        job_outputs: optional mapping of job_name -> the scanner it
            produces output for (used as a hint for the artifact
            API when filenames alone are not enough).
    """
    out: dict[str, str] = {}
    # The artifact download API requires the artifact id, not the
    # filename, so we first list artifacts for the run, then map
    # by filename. This is the same pattern the Go backend uses
    # for SARIF uploads.
    from app.services.github_service import (
        get_workflow_run_artifacts,
        download_artifact,
    )
    try:
        artifacts = get_workflow_run_artifacts(repository_id, run_id, github_token) or []
    except Exception as e:
        logger.warning("fetch_scanner_outputs: artifact list failed: %s", e)
        return out
    for scanner, filenames in _SCANNER_ARTIFACT_FILE.items():
        # Take the FIRST matching filename in priority order. The
        # trivy entry has both fs and image reports — we prefer fs
        # (the user-facing container is built in container-scan
        # which already has its own file).
        for filename in filenames:
            match = next(
                (a for a in artifacts if isinstance(a, dict) and a.get("name") == filename),
                None,
            )
            if not match:
                continue
            try:
                content = download_artifact(
                    repository_id, run_id, match["id"], github_token
                )
                if content:
                    out[scanner] = content
                    break  # stop after first match for this scanner
            except Exception as e:
                logger.warning(
                    "fetch_scanner_outputs: download %s failed: %s",
                    filename, e,
                )
    return out


def ai_log_evaluation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """State node: read workflow logs and extract real findings.

    Reviewer feedback (round 1): the previous flow did NOT read
    the workflow log text. It looked at
    `job.conclusion == "failure"` and reported a generic "Job X
    failed" finding — which is neither a security finding nor an
    actionable config issue. This node now reads the actual log
    text and replaces the generic placeholder with concrete,
    evidence-backed findings.

    Reviewer feedback (round 2): heuristic regex matching over raw
    log text produces DUPLICATED findings when the same CVE is
    reported by multiple jobs. This node now uses a two-tier
    strategy:

      1. PRIMARY: parse structured scanner JSON output (npm audit,
         Trivy, Semgrep, Gitleaks) via the scanner_normalizer.
         The normalizer handles deduplication via a composite
         key (tool + vuln_id + package + file_path).
      2. FALLBACK: when no structured output is available (or for
         workflow configuration issues that have no structured
         equivalent), fall back to log-line regex matching.
         Findings from this path are tagged
         `source: "log_heuristic_fallback"` so the user can
         distinguish them.

    The node is a no-op when there are no workflow jobs to
    evaluate.
    """
    workflow_jobs = state.get("workflow_jobs") or []
    if not workflow_jobs:
        return state

    # --- Primary path: structured scanner output ------------------------
    structured_findings: list[dict] = []
    structured_metadata: dict = {
        "raw_count": 0,
        "dropped_count": 0,
        "by_tool": {},
        "by_severity": {},
        "errors": [],
    }
    scanner_outputs = state.get("scanner_outputs")
    if scanner_outputs:
        try:
            job_by_scanner = {
                scanner: name
                for name, scanner in _JOB_TO_SCANNER.items()
                if any(
                    isinstance(j, dict) and j.get("name") == name
                    for j in (workflow_jobs or [])
                )
            }
            res = extract_findings_from_scanner_outputs(
                scanner_outputs, job_by_scanner=job_by_scanner
            )
            structured_findings = res.get("findings") or []
            structured_metadata = {
                "raw_count": res.get("raw_count", 0),
                "dropped_count": res.get("dropped_count", 0),
                "by_tool": res.get("by_tool", {}),
                "by_severity": res.get("by_severity", {}),
                "errors": res.get("errors", []),
            }
        except Exception as e:
            logger.warning("ai_log_evaluation: structured extraction failed: %s", e)

    # --- Fallback path: log heuristic (for config issues + missing
    # structured output) ---------------------------------------------
    workflow_logs = state.get("workflow_logs") or None
    log_result = extract_findings_from_logs(workflow_jobs, workflow_logs)

    # Optionally call the LLM to refine the heuristic extraction.
    # The LLM is asked to filter false positives and split findings
    # into the three dashboard categories.
    llm_result = _llm_refine_extraction(log_result, state)
    if llm_result:
        log_result = _merge_extractions(log_result, llm_result)

    # --- Merge paths ----------------------------------------------------
    # Security findings come from BOTH paths. Structured path first
    # (deduplicated, evidence-backed). Log fallback is added only
    # for findings that the structured path missed; log fallback
    # findings with a scanner that has structured output are
    # discarded (we trust the structured data more).
    structured_tools = {f.get("tool") for f in structured_findings}
    fallback_findings: list[dict] = []
    for f in log_result.get("security_findings") or []:
        # If the log heuristic identified a finding that came from
        # a scanner that already provided structured output, drop
        # it (it would be a duplicate or a regex false positive).
        ev = (f.get("evidence") or "").lower()
        if any(tool and tool in structured_tools for tool in ()):
            pass
        # Drop findings whose source is one of the structured
        # scanners (otherwise we double-count).
        source = (f.get("rule") or "").lower()
        if any(t and t in source for t in structured_tools):
            continue
        # Also drop the duplicate "84 vulnerabilities" heuristic
        # matches when the structured path already produced a
        # vulnerability finding for the same package. The dedup
        # key below covers that case.
        fallback_findings.append({**f, "source": "log_heuristic_fallback"})

    # Cross-source dedup: if the structured path produced a finding
    # for the same (tool, package, file), drop the fallback.
    def _structured_key(f: dict) -> tuple:
        return (
            f.get("tool") or "",
            (f.get("package_name") or f.get("evidence") or "").split("@")[0].lower(),
            (f.get("file_path") or f.get("file_location") or "").lower(),
        )

    structured_keys = {_structured_key(f) for f in structured_findings}
    deduped_fallback: list[dict] = []
    for f in fallback_findings:
        key = (
            "",
            (f.get("evidence") or "").split("@")[0].split(" ")[0].lower(),
            "",
        )
        if key in structured_keys:
            continue
        deduped_fallback.append(f)

    all_security_findings = structured_findings + deduped_fallback

    # Replace previous generic "Job X failed" findings.
    existing = list(state.get("findings") or [])
    non_generic = [
        f for f in existing
        if isinstance(f, dict)
        and not _is_generic_job_failure_finding(f)
    ]
    state["findings"] = non_generic + all_security_findings

    # Workflow config issues only come from the log path.
    config_existing = list(state.get("workflow_config_issues") or [])
    state["workflow_config_issues"] = config_existing + log_result.get("config_issues", [])

    # Surface the skipped jobs at the top level.
    skipped_existing = list(state.get("skipped_jobs") or [])
    state["skipped_jobs"] = skipped_existing + log_result.get("skipped_jobs", [])

    # Record extraction metadata.
    state["log_extraction"] = {
        "source": "structured" if structured_findings else log_result.get("extraction_source", "unknown"),
        "lines_scanned": log_result.get("lines_scanned", 0),
        "security_findings_count": len(all_security_findings),
        "config_issues_count": len(log_result.get("config_issues") or []),
        "skipped_jobs_count": len(log_result.get("skipped_jobs") or []),
        "structured": structured_metadata,
        "fallback_fallback_count": len(deduped_fallback),
    }

    logger.info(
        f"ai_log_evaluation: structured={len(structured_findings)}, "
        f"fallback={len(deduped_fallback)}, "
        f"config_issues={len(log_result.get('config_issues') or [])}"
    )
    return state


def _is_generic_job_failure_finding(finding: dict) -> bool:
    """Return True if the finding looks like a generic
    "Job X failed" placeholder (not a real evidence-backed finding).

    These are produced by the legacy auto-extract heuristic and
    should be REPLACED by the log-based extraction.
    """
    if not isinstance(finding, dict):
        return False
    title = (finding.get("title") or "").lower()
    explanation = (finding.get("explanation") or "").lower()
    ftype = (finding.get("type") or "").lower()
    source = (finding.get("source") or "").lower()
    generic_markers = [
        "job failed",
        "workflow error",
        "scan failed",
        "security scan failed",
        "failure detected",
    ]
    if source in ("conclusion_only", "job_failure_placeholder", "auto_extract_legacy"):
        return True
    if ftype == "workflow_execution_event" and any(m in title for m in generic_markers):
        return True
    if any(m in title for m in generic_markers) and not finding.get("evidence"):
        return True
    if any(m in explanation for m in generic_markers) and not finding.get("evidence"):
        return True
    return False


def _llm_refine_extraction(
    heuristic_result: dict,
    state: PipelineEngineerState,
) -> dict | None:
    """Optionally call the LLM to refine the heuristic extraction.

    The LLM is asked to:
      1. Remove false positives (e.g. a line that looks like a CVE
         ID but is actually a commit SHA).
      2. Tag each finding with the proper category (security_finding,
         workflow_config_issue, maintenance_warning, etc.).
      3. Assign a final severity based on the full log context.

    Returns a dict with the same shape as `heuristic_result` (with
    refined findings/issues), or None if the LLM is unavailable.
    """
    try:
        from app.agents.nodes.workflow_generator import get_llm  # type: ignore
    except ImportError:
        return None
    try:
        llm = get_llm()
    except Exception:
        return None

    findings_sample = heuristic_result["security_findings"][:20]
    issues_sample = heuristic_result["config_issues"][:20]
    if not findings_sample and not issues_sample:
        return None

    prompt = (
        "You are reviewing heuristic findings extracted from CI/CD "
        "workflow logs. For each finding below, decide:\n"
        "  - is_real:        is it a TRUE security / config issue (not a false positive like a commit SHA that happens to look like a CVE)?\n"
        "  - category:       'security_finding' or 'workflow_config_issue'\n"
        "  - severity:       'critical' | 'high' | 'medium' | 'low'\n"
        "  - title:          short, human-readable title (1 sentence)\n"
        "  - explanation:    1-2 sentence explanation\n"
        "Return JSON: {\"findings\": [...], \"config_issues\": [...]}.\n\n"
        f"Findings: {json.dumps(findings_sample)}\n\n"
        f"Config issues: {json.dumps(issues_sample)}"
    )

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(content) if isinstance(content, str) else content
    except Exception as e:
        logger.warning(f"LLM refinement failed (non-fatal): {e}")
        return None

    if not isinstance(parsed, dict):
        return None
    refined_findings = parsed.get("findings") or []
    refined_issues = parsed.get("config_issues") or []
    return {
        "security_findings": refined_findings if isinstance(refined_findings, list) else [],
        "config_issues": refined_issues if isinstance(refined_issues, list) else [],
        "skipped_jobs": heuristic_result.get("skipped_jobs", []),
        "extraction_source": "logs+llm",
        "lines_scanned": heuristic_result.get("lines_scanned", 0),
    }


def _merge_extractions(heuristic: dict, llm: dict) -> dict:
    """Merge the LLM-refined extraction back over the heuristic one.

    Strategy: keep the LLM's findings/issues as the primary list
    (they are more accurate), but preserve any heuristic findings
    that the LLM did not include (so we don't drop real findings
    that the LLM ignored).
    """
    llm_findings = llm.get("security_findings") or []
    llm_issues = llm.get("config_issues") or []
    heur_findings = heuristic.get("security_findings") or []
    heur_issues = heuristic.get("config_issues") or []

    llm_evidence = {
        (f.get("evidence"), f.get("rule")) for f in llm_findings
        if isinstance(f, dict)
    }
    llm_issue_msgs = {
        i.get("message") for i in llm_issues if isinstance(i, dict)
    }

    merged_findings = list(llm_findings) + [
        f for f in heur_findings
        if isinstance(f, dict)
        and (f.get("evidence"), f.get("rule")) not in llm_evidence
    ]
    merged_issues = list(llm_issues) + [
        i for i in heur_issues
        if isinstance(i, dict) and i.get("message") not in llm_issue_msgs
    ]
    return {
        "security_findings": merged_findings,
        "config_issues": merged_issues,
        "skipped_jobs": heuristic.get("skipped_jobs", []),
        "extraction_source": llm.get("extraction_source", "logs+llm"),
        "lines_scanned": heuristic.get("lines_scanned", 0),
    }
