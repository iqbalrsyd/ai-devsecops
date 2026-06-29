"""
Evidence-based security finding normalizer.

This module turns raw scanner outputs into a normalized finding schema. It is
the single source of truth for converting:

    - GitHub Check Run Annotations
    - SARIF results (Semgrep, CodeQL, etc.)
    - npm audit JSON
    - Trivy JSON
    - Gitleaks findings

into dashboard-ready security findings.

Design principles:
    1. No findings are created from job names, stage names, or job failures.
    2. Every security finding MUST be backed by actual evidence.
    3. Non-security items are returned as `workflow_config_issue`,
       `maintenance_warning`, or `external_service_issue` so they never feed
       the risk score.
    4. Findings are deduplicated by (source_tool, title, file, line).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.finding_categories import classify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalized schema helpers
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


def _normalize_severity(value: Any) -> str:
    """Map arbitrary severity strings to critical/high/medium/low."""
    if value is None:
        return "medium"
    text = str(value).lower().strip()
    if text in {"critical", "error", "errors"}:
        return "critical"
    if text in {"high", "warning", "warnings", "major"}:
        return "high"
    if text in {"medium", "moderate", "minor"}:
        return "medium"
    if text in {"low", "info", "informational", "note", "none"}:
        return "low"
    return "medium"


def _coerce_int(value: Any) -> int | None:
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
    except (ValueError, TypeError):
        pass
    return None


def _first_truthy(*values: Any) -> Any:
    for v in values:
        if v:
            return v
    return None


def _make_finding(
    *,
    title: str,
    source_tool: str,
    severity: str,
    evidence: str,
    file_location: str | None = None,
    line: int | None = None,
    remediation_recommendation: str,
    finding_type: str,
    code_snippet: str | None = None,
    cwe: str | None = None,
    owasp: str | None = None,
    cve: str | None = None,
    package_name: str | None = None,
    installed_version: str | None = None,
    fixed_version: str | None = None,
    rule_id: str | None = None,
) -> dict:
    """Return a normalized finding dict with the canonical field set.

    `rule_id` is the scanner-specific rule identifier (e.g.
    "github.api-excessive-data-exposure", "tainted-sql-string").
    It is preserved so the dashboard can dedupe correctly and so
    `code_scanning_alerts` (which only includes results whose
    ruleId matches) keeps consistent with the raw SARIF count.
    """
    return {
        "title": (title or f"{source_tool} finding").strip(),
        "source_tool": source_tool.strip().lower(),
        "severity": _normalize_severity(severity),
        "evidence": (evidence or "").strip(),
        "file_location": (file_location or "").strip() or None,
        "line": _coerce_int(line),
        "remediation_recommendation": (remediation_recommendation or "").strip(),
        "type": finding_type.strip().lower() or "security_finding",
        "code_snippet": (code_snippet or "").strip() or None,
        "cwe": (cwe or "").strip() or None,
        "owasp": (owasp or "").strip() or None,
        "cve": (cve or "").strip() or None,
        "package_name": (package_name or "").strip() or None,
        "installed_version": (installed_version or "").strip() or None,
        "fixed_version": (fixed_version or "").strip() or None,
        "rule_id": (rule_id or "").strip() or None,
        "scanner": source_tool.strip().lower(),
        "explanation": (evidence or "").strip(),
        "recommendation": (remediation_recommendation or "").strip(),
    }


def _is_security_finding(finding: dict) -> bool:
    """Return True only for findings that look like real security issues."""
    if not isinstance(finding, dict):
        return False
    cat = classify(finding)
    return cat == "security_finding"


def _annotation_remediation(text: str) -> str:
    """Return a markdown-formatted remediation for an annotation-derived
    security finding. Falls back to a short generic line for unknown
    finding types. The output is rendered as markdown by the frontend
    (FindingsTable).
    """
    lower = (text or "").lower()

    if "user root" in lower:
        return _DOCKER_USER_ROOT_REMEDIATION

    if ".env" in lower and ("git history" in lower or "rotate" in lower):
        return _ENV_IN_HISTORY_REMEDIATION

    return "Review the annotation details and fix the reported security issue."


_DOCKER_USER_ROOT_REMEDIATION = """**Switch to a non-root USER in your Dockerfile.**

Running as root inside the container means any code-injection vulnerability
grants the attacker full container privileges (CWE-250, OWASP A05:2021).

**Steps**
1. Create a dedicated user near the top of the Dockerfile.
2. Drop privileges with `USER` before the `CMD`/`ENTRYPOINT`.
3. Make sure `/app` (or your workdir) is owned by that user.

**Before**
```dockerfile
FROM node:20
WORKDIR /app
COPY . .
RUN npm ci --omit=dev
USER root
CMD ["node", "server.js"]
```

**After**
```dockerfile
FROM node:20
WORKDIR /app
COPY --chown=node:node . .
RUN npm ci --omit=dev
USER node
CMD ["node", "server.js"]
```

Reference: <https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user>
"""


_ENV_IN_HISTORY_REMEDIATION = """**Remove .env from history and rotate every committed secret.**

Files matching `.env` contain credentials. Once committed, they are
visible in the git history forever, even after deletion in HEAD
(CWE-798, OWASP A02:2021).

**Steps**
1. Add `.env` to `.gitignore` *first* so it is never re-tracked.
```gitignore
# Local environment files — never commit
.env
.env.*
!.env.example
```
2. Strip the file from history with `git filter-repo`:
```bash
git filter-repo --path .env --invert-paths
git push origin --force --all
```
3. **Rotate every secret that was ever stored in that file** —
   database passwords, API keys, JWT signing keys, third-party
   tokens. The old values must be considered compromised.
4. Add `gitleaks` to a pre-commit hook to prevent regressions.

Reference: <https://github.com/gitleaks/gitleaks#pre-commit-hook>
"""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _extract_cve(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"CVE-\d{4}-\d{4,}", text, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_cwe(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"CWE-\d+", text, re.IGNORECASE)
    return match.group(0).upper() if match else None


def parse_sarif(data: dict | str) -> list[dict]:
    """Parse SARIF output (Semgrep, CodeQL, etc.) into normalized findings."""
    findings: list[dict] = []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return findings
    if not isinstance(data, dict):
        return findings

    runs = data.get("runs", []) or []
    if not runs and "results" in data:
        runs = [{"results": data.get("results", []), "tool": data.get("tool", {})}]

    for run in runs:
        if not isinstance(run, dict):
            continue
        tool_info = run.get("tool", {}) or {}
        driver = tool_info.get("driver", {}) or {}
        tool_name = driver.get("name", "sarif")
        rules: dict[str, dict] = {}
        for rule in (driver.get("rules", []) or []):
            if isinstance(rule, dict) and rule.get("id"):
                rules[rule["id"]] = rule

        for result in run.get("results", []) or []:
            if not isinstance(result, dict):
                continue
            rule_id = result.get("ruleId", "")
            rule = rules.get(rule_id, {})
            message = result.get("message", {}) or {}
            text = message.get("text", "") or ""

            locations = result.get("locations", []) or []
            loc = locations[0] if locations else {}
            physical = loc.get("physicalLocation", {}) or {}
            artifact = physical.get("artifactLocation", {}) or {}
            region = physical.get("region", {}) or {}

            file_path = artifact.get("uri", "")
            line = region.get("startLine")
            snippet = (region.get("snippet", {}) or {}).get("text", "")

            rule_props = rule.get("properties", {}) or {}
            severity = (
                result.get("level")
                or rule.get("defaultConfiguration", {}).get("level")
                or rule_props.get("security-severity")
                or rule_props.get("precision")
                or "medium"
            )
            cwe = _extract_cwe(text) or _extract_cwe(str(rule.get("fullDescription", {}).get("text", "")))
            cve = _extract_cve(text)

            remediation = rule.get("help", {}).get("text", "") or rule.get("helpUri", "")
            if not remediation:
                remediation = f"Review the {tool_name} rule '{rule_id}' and fix the reported issue."

            finding = _make_finding(
                title=f"{tool_name}: {rule_id}",
                source_tool=tool_name,
                severity=severity,
                evidence=text or f"SARIF rule {rule_id} triggered.",
                file_location=file_path,
                line=line,
                remediation_recommendation=remediation,
                finding_type=_map_sarif_rule_type(rule_id, text),
                code_snippet=snippet,
                cwe=cwe,
                owasp=_map_to_owasp(rule_id, text),
                cve=cve,
                rule_id=rule_id,
            )
            findings.append(finding)

    return findings


def parse_semgrep(data: dict | str) -> list[dict]:
    """Parse Semgrep JSON output into normalized findings."""
    findings = parse_sarif(data)
    for f in findings:
        f["source_tool"] = "semgrep"
        f["scanner"] = "semgrep"
    return findings


def parse_trivy(data: dict | str) -> list[dict]:
    """Parse Trivy JSON output into normalized findings."""
    findings: list[dict] = []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return findings
    if not isinstance(data, dict):
        return findings

    results = data.get("Results", []) or []
    for target in results:
        if not isinstance(target, dict):
            continue
        target_path = target.get("Target", "")
        for vuln in (target.get("Vulnerabilities", []) or []):
            if not isinstance(vuln, dict):
                continue
            pkg = vuln.get("PkgName", "")
            installed = vuln.get("InstalledVersion", "")
            fixed = vuln.get("FixedVersion", "")
            severity = vuln.get("Severity", "medium")
            cve = vuln.get("VulnerabilityID", "")
            title = vuln.get("Title", "")
            description = vuln.get("Description", "")
            references = vuln.get("References", []) or []

            evidence_parts = [description or title]
            if pkg:
                evidence_parts.append(f"Package: {pkg}")
            if installed:
                evidence_parts.append(f"Installed: {installed}")
            if fixed:
                evidence_parts.append(f"Fixed in: {fixed}")
            if cve:
                evidence_parts.append(f"Identifier: {cve}")
            evidence = "\n".join(p for p in evidence_parts if p)

            remediation = f"Upgrade {pkg} to {fixed}." if (pkg and fixed) else "Review Trivy output and apply the vendor patch."
            if references:
                remediation += f" See {references[0]}."

            findings.append(_make_finding(
                title=f"Trivy: {title or cve or 'vulnerability'}",
                source_tool="trivy",
                severity=severity,
                evidence=evidence,
                file_location=target_path,
                remediation_recommendation=remediation,
                finding_type="dependency_vulnerability" if pkg else "cve_vulnerability",
                cve=cve if cve.startswith("CVE-") else _extract_cve(cve),
                package_name=pkg,
                installed_version=installed,
                fixed_version=fixed,
                rule_id=f"trivy:{pkg}:{cve}" if pkg else f"trivy:{cve}",
            ))

    return findings


def parse_gitleaks(data: dict | str | list) -> list[dict]:
    """Parse Gitleaks JSON output into normalized findings."""
    findings: list[dict] = []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return findings
    if isinstance(data, dict):
        items = data.get("findings", []) or data.get("results", []) or []
    elif isinstance(data, list):
        items = data
    else:
        return findings

    for item in items:
        if not isinstance(item, dict):
            continue
        description = item.get("Description", item.get("RuleID", "hardcoded secret"))
        match = item.get("Match", item.get("Secret", ""))
        file_path = item.get("File", "")
        line = item.get("StartLine", item.get("Line", None))
        commit = item.get("Commit", "")
        rule_id = item.get("RuleID", "")

        evidence = f"{description}: {match}"
        if commit:
            evidence += f" (commit {commit})"

        findings.append(_make_finding(
            title=f"Gitleaks: {description}",
            source_tool="gitleaks",
            severity="critical",
            evidence=evidence,
            file_location=file_path,
            line=line,
            remediation_recommendation="Rotate the exposed credential immediately and move secrets to a vault or GitHub Secrets. Add Gitleaks to pre-commit hooks.",
            finding_type="hardcoded_secret",
            code_snippet=match,
            cwe="CWE-798",
            owasp="A2: Broken Authentication",
            rule_id=f"gitleaks:{rule_id}" if rule_id else None,
        ))

    return findings


def parse_npm_audit(data: dict | str) -> list[dict]:
    """Parse `npm audit --json` output into normalized findings."""
    findings: list[dict] = []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return findings
    if not isinstance(data, dict):
        return findings

    advisories = data.get("advisories", {}) or {}
    if not advisories and "vulnerabilities" in data:
        advisories = data["vulnerabilities"]

    for key, vuln in advisories.items():
        if not isinstance(vuln, dict):
            continue
        module_name = vuln.get("module_name", vuln.get("name", key))
        severity = vuln.get("severity", "medium")
        overview = vuln.get("overview", vuln.get("via", ""))
        if isinstance(overview, list) and overview:
            overview = overview[0] if isinstance(overview[0], str) else overview[0].get("title", "")
        if isinstance(overview, dict):
            overview = overview.get("title", "")
        cves = vuln.get("cves", []) or []
        cve = cves[0] if cves else _extract_cve(str(overview))
        findings_range = vuln.get("findings", []) or []
        installed = ""
        for finding in findings_range:
            if isinstance(finding, dict):
                installed = finding.get("version", "")
                break
        fixed = ""
        if isinstance(vuln.get("patched_versions"), str):
            fixed = vuln["patched_versions"]
        elif vuln.get("range"):
            fixed = vuln.get("range", "")

        evidence_parts = [str(overview)]
        if module_name:
            evidence_parts.append(f"Package: {module_name}")
        if installed:
            evidence_parts.append(f"Installed: {installed}")
        if fixed:
            evidence_parts.append(f"Patched versions: {fixed}")
        if cve:
            evidence_parts.append(f"CVE: {cve}")

        remediation = f"Run `npm audit fix` or upgrade `{module_name}` to a patched version."
        findings.append(_make_finding(
            title=f"npm audit: {module_name}",
            source_tool="npm-audit",
            severity=severity,
            evidence="\n".join(p for p in evidence_parts if p),
            remediation_recommendation=remediation,
            finding_type="dependency_vulnerability",
            cve=cve,
            package_name=module_name,
            installed_version=installed,
            fixed_version=fixed,
            rule_id=f"npm:{module_name}:{cve}" if cve else f"npm:{module_name}",
        ))

    return findings


def parse_annotations(annotations: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Parse GitHub check-run annotations.

    Returns four lists: (security_findings, workflow_config_issues,
    maintenance_warnings, external_service_issues).
    """
    security: list[dict] = []
    config: list[dict] = []
    maintenance: list[dict] = []
    external: list[dict] = []

    for ann in annotations or []:
        if not isinstance(ann, dict):
            continue
        message = ann.get("message", "") or ""
        title = ann.get("title", "") or ""
        text = f"{title} {message}".strip()
        if not text:
            continue

        # Filter out generic noise from GitHub step summaries. These
        # are emitted by the runner (e.g. "Process completed with
        # exit code 1.") and do NOT represent a security finding —
        # they are status messages from a step that happened to
        # fail. Classifying them as `security_finding` would inflate
        # the risk score with non-actionable noise.
        lower_text = text.lower()
        if any(needle in lower_text for needle in (
            "process completed with exit code",
            "process completed with error",
            "step completed with exit code",
            "step was canceled",
        )):
            continue

        # Reviewer feedback: "scanner found 0 findings / generating
        # empty SARIF" notices emitted by the upload-sarif fallback
        # step are GitHub Actions runner output, not real security
        # findings. Drop them entirely so they do not inflate the
        # dashboard count. (See backend/internal/handlers/
        # annotation_dashboard.go for the matching Go filter.)
        if any(needle in lower_text for needle in (
            "found 0 findings",
            "generating empty sarif",
            "did not produce a sarif file",
            "no vulnerabilities found",
            "no issues found",
        )):
            continue

        cat = classify({"type": "", "message": text, "explanation": text})
        base = {
            "message": text,
            "path": ann.get("path", ""),
            "line": _coerce_int(ann.get("line") or ann.get("start_line")),
            "level": ann.get("level", "notice"),
            "check_name": ann.get("check_name", ""),
            "source": "github_annotation",
        }

        if cat == "security_finding":
            # Only promote to a security finding when the annotation
            # has a real check_name AND points to a real file. Without
            # a file path this is almost certainly a runner status
            # message that escaped the noise filter above (e.g. a
            # generic "Annotation: see logs" notice).
            if not ann.get("check_name") or not ann.get("path"):
                cat = "workflow_config_issue"
        if cat == "security_finding":
            security.append(_make_finding(
                title=f"Annotation: {title or message[:80]}",
                source_tool=ann.get("check_name", "github_annotation"),
                severity=ann.get("level", "medium"),
                evidence=text,
                file_location=ann.get("path"),
                line=base["line"],
                remediation_recommendation=_annotation_remediation(text),
                finding_type="security_finding",
                rule_id=f"annotation:{ann.get('check_name', '')}",
            ))
        elif cat == "workflow_config_issue":
            config.append({**base, "category": "workflow_config_issue", "rule": "github_annotation"})
        elif cat == "maintenance_warning":
            maintenance.append({**base, "category": "maintenance_warning", "rule": "github_annotation"})
        elif cat == "external_service_issue":
            external.append({**base, "category": "external_service_issue", "rule": "github_annotation"})

    return security, config, maintenance, external


# ---------------------------------------------------------------------------
# Tool output discovery from raw logs
# ---------------------------------------------------------------------------

def _looks_like_json(text: str) -> bool:
    text = text.strip()
    return text.startswith(("{", "[")) and text.endswith(("}", "]"))


def extract_tool_outputs(logs: str) -> dict[str, Any]:
    """Try to find embedded JSON blobs for known tools inside workflow logs."""
    outputs: dict[str, Any] = {}
    if not logs:
        return outputs

    # Gitleaks often emits compact JSON arrays
    for match in re.finditer(r'\[\s*\{[^}]*"Description"[^}]*\}\s*\]', logs, re.DOTALL):
        snippet = match.group(0)
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, list) and parsed and "Description" in parsed[0]:
                outputs.setdefault("gitleaks", []).extend(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    # npm audit
    for match in re.finditer(r'\{\s*"advisories"\s*:\s*\{', logs, re.DOTALL):
        snippet = logs[match.start():]
        # Try to consume until the matching close brace of the advisories object.
        # A robust but simple heuristic: find the first top-level closing brace.
        try:
            parsed = json.loads(_extract_balanced_json(snippet))
            if parsed.get("advisories") or parsed.get("vulnerabilities"):
                outputs["npm_audit"] = parsed
                break
        except (json.JSONDecodeError, TypeError):
            pass

    # Trivy / SARIF - look for lines that start with { and contain tool markers
    for line in logs.splitlines():
        line = line.strip()
        if not _looks_like_json(line):
            continue
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            if "Results" in parsed and any("Vulnerabilities" in str(r) for r in parsed.get("Results", [])):
                outputs.setdefault("trivy", parsed)
            elif parsed.get("$schema", "").lower().startswith("http") and "runs" in parsed:
                outputs.setdefault("sarif", parsed)
            elif parsed.get("tool", {}).get("driver", {}).get("name"):
                outputs.setdefault("sarif", parsed)

    return outputs


def _extract_balanced_json(text: str) -> str:
    """Return the longest JSON object/array prefix that parses."""
    depth = 0
    in_string = False
    escape = False
    start = 0
    for i, ch in enumerate(text):
        if not in_string:
            if ch in "{[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return text[start:i + 1]
                    except Exception:
                        pass
        if escape:
            escape = False
            continue
        if ch == '"' and not escape:
            in_string = not in_string
        if ch == "\\":
            escape = True
    return text


# ---------------------------------------------------------------------------
# Normalization entry point
# ---------------------------------------------------------------------------

def normalize_security_findings(
    *,
    logs: str | None = None,
    annotations: list[dict] | None = None,
    sarif: dict | str | None = None,
    npm_audit: dict | str | None = None,
    trivy: dict | str | None = None,
    gitleaks: dict | str | list | None = None,
) -> dict:
    """Normalize all evidence sources into the four-category dashboard.

    Returns:
        {
            "security_findings": [...],
            "workflow_config_issues": [...],
            "maintenance_warnings": [...],
            "external_service_issues": [...],
            "message": str,
        }
    """
    security: list[dict] = []
    config: list[dict] = []
    maintenance: list[dict] = []
    external: list[dict] = []

    # 1. Explicit tool outputs
    if sarif:
        security.extend(parse_sarif(sarif))
    if npm_audit:
        security.extend(parse_npm_audit(npm_audit))
    if trivy:
        security.extend(parse_trivy(trivy))
    if gitleaks:
        security.extend(parse_gitleaks(gitleaks))

    # 2. Logs may contain embedded tool outputs
    tool_outputs = extract_tool_outputs(logs or "")
    if "gitleaks" in tool_outputs:
        security.extend(parse_gitleaks(tool_outputs["gitleaks"]))
    if "npm_audit" in tool_outputs:
        security.extend(parse_npm_audit(tool_outputs["npm_audit"]))
    if "trivy" in tool_outputs:
        security.extend(parse_trivy(tool_outputs["trivy"]))
    if "sarif" in tool_outputs:
        security.extend(parse_sarif(tool_outputs["sarif"]))

    # 3. Annotations
    ann_security, ann_config, ann_maint, ann_external = parse_annotations(annotations or [])
    security.extend(ann_security)
    config.extend(ann_config)
    maintenance.extend(ann_maint)
    external.extend(ann_external)

    # 4. Filter: only keep evidence-based security findings
    security = [f for f in security if _is_security_finding(f)]

    # 5. Deduplicate security findings
    security = deduplicate_findings(security)

    # 6. Empty-state message
    message = ""
    if not security:
        message = "No validated security findings detected. Workflow issues may still exist."

    return {
        "security_findings": security,
        "workflow_config_issues": config,
        "maintenance_warnings": maintenance,
        "external_service_issues": external,
        "message": message,
    }


def deduplicate_findings(findings: list[dict]) -> list[dict]:
    """Deduplicate findings by (source_tool, rule_id, file_location, line).

    Reviewer feedback: the previous key included `title` which
    collapsed legitimate findings of the same rule at different
    locations (e.g. `api-excessive-data-exposure` showing up in
    auth.js, checkout.js, orders.js, products.js, server.js — five
    distinct files — was deduped down to a single "excessive data
    exposure" entry because they shared the same generated title).
    We now key on `rule_id` (the actual scanner rule identifier)
    which is a more precise signal: same rule + same file + same
    line = duplicate, anything else is a separate finding.

    When duplicates are found, keep the highest-severity occurrence.
    """
    seen: dict[tuple, dict] = {}
    for f in findings:
        key = (
            f.get("source_tool", ""),
            f.get("rule_id", ""),
            f.get("file_location") or "",
            f.get("line"),
        )
        existing = seen.get(key)
        if existing is None:
            seen[key] = f
        else:
            if SEVERITY_ORDER.get(f.get("severity", "medium"), 99) < SEVERITY_ORDER.get(existing.get("severity", "medium"), 99):
                seen[key] = f
            elif f.get("evidence") and len(str(f.get("evidence"))) > len(str(existing.get("evidence"))):
                seen[key] = f
    return list(seen.values())


# ---------------------------------------------------------------------------
# Type mapping helpers
# ---------------------------------------------------------------------------

def _map_sarif_rule_type(rule_id: str, message: str) -> str:
    text = f"{rule_id} {message}".lower()
    if any(k in text for k in ("secret", "password", "token", "key", "credential")):
        return "hardcoded_secret"
    if any(k in text for k in ("sqli", "sql.injection", "sql_injection", "sql-injection")):
        return "sql_injection"
    if "xss" in text:
        return "xss"
    if any(k in text for k in ("command injection", "command_injection", "rce")):
        return "command_injection"
    if "path traversal" in text:
        return "path_traversal"
    if any(k in text for k in ("cve", "vulnerability", "vuln")):
        return "dependency_vulnerability"
    return "security_finding"


def _map_to_owasp(rule_id: str, message: str) -> str | None:
    text = f"{rule_id} {message}".lower()
    if any(k in text for k in ("sqli", "sql.injection", "command injection", "rce")):
        return "A1: Injection"
    if any(k in text for k in ("secret", "password", "token", "credential")):
        return "A2: Broken Authentication"
    if "xss" in text:
        return "A7: Cross-Site Scripting"
    if any(k in text for k in ("crypto", "hash", "md5", "sha1")):
        return "A3: Sensitive Data Exposure"
    if any(k in text for k in ("access control", "permission", "authorization")):
        return "A5: Broken Access Control"
    if any(k in text for k in ("dependency", "cve", "vulnerable component")):
        return "A6: Vulnerable Components"
    return None
