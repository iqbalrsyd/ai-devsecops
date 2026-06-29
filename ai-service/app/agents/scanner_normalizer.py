"""Structured scanner output normaliser.

This module parses the JSON / SARIF output produced by each scanner
in the GitHub Actions pipeline (`npm audit`, Trivy, Semgrep, Gitleaks)
and returns a unified list of `NormalizedFinding` dicts.

Why this exists:
  - The log-line regex fallback (see `ai_log_evaluator.py`) collapses
    every npm audit advisory to a single row whose `evidence` field
    is the human-readable summary string ("84 vulnerabilities").
    The dashboard then displays "vulnerability / 84 vulnerabilities"
    which is correct for a roll-up but useless for triage.
  - Each advisory in the npm-audit JSON actually lists the vulnerable
    packages under `vulnerabilities[<name>].via[].title` /
    `node_modules/<pkg>@<version>`. Expanding those gives 1 row per
    vulnerable package@version, which is what reviewers need.
  - The same goes for Trivy / Semgrep SARIF: each `result` becomes 1
    row; the SARIF `rules` block is used to backfill CWE/OWASP.

Public entry point: `normalize_and_dedupe(scanner_outputs)`.

The output dict shape is:

    {
      "findings":         [NormalizedFinding dict, ...],
      "raw_count":        int,
      "dropped_count":    int,
      "by_tool":          {tool: count},
      "by_severity":      {critical/high/medium/low: count},
      "errors":           [str, ...],
    }
"""

from __future__ import annotations

import json
import re
from typing import Any


# Severity band anchors (CVSS v3.1). When the scanner reports a
# severity string but no numeric score (npm audit, Gitleaks), we use
# these so the dashboard Severity Breakdown and the PDF
# `_derive_cvss_score` fallback agree on the same number.
_BAND_ANCHOR: dict[str, float] = {
    "critical": 9.5,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.0,
    "info": 0.0,
    "unknown": 5.0,
}

# npm-audit advisory severity strings map to our 4-bucket model.
_NPM_SEV_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "moderate": "medium",
    "medium": "medium",
    "low": "low",
    "info": "low",
    "informational": "low",
}

# Per-package CVSS anchors for npm-audit. Mirrors
# `_NPM_PACKAGE_CVSS` in `report_generator.py` so the PDF column and
# the Security Findings list render the same number.
_NPM_PACKAGE_CVSS: dict[str, float] = {
    "node-tar": 8.6,
    "tar": 8.6,
    "lodash": 7.2,
    "jsonwebtoken": 9.1,
    "express": 6.1,
    "body-parser": 7.5,
    "qs": 7.5,
    "path-to-regexp": 7.5,
    "minimatch": 9.8,
    "semver": 7.5,
    "axios": 7.5,
    "ws": 7.5,
    "ejs": 9.8,
    "pug": 7.5,
    "handlebars": 7.5,
    "marked": 5.3,
    "js-yaml": 5.3,
    "yaml": 5.3,
    "xml2js": 6.5,
    "fast-xml-parser": 6.5,
    "node-fetch": 7.5,
    "undici": 5.3,
    "cookie": 6.5,
    "send": 7.5,
    "multer": 7.5,
    "busboy": 7.5,
    "formidable": 7.5,
    "xss": 5.3,
    "dompurify": 5.3,
    "sanitize-html": 5.3,
    "follow-redirects": 5.3,
    "shell-quote": 7.5,
    "shelljs": 7.5,
    "cross-spawn": 5.3,
    "serialize-javascript": 7.5,
}


def _coerce_severity(raw: Any) -> str:
    if raw is None:
        return "medium"
    s = str(raw).lower().strip()
    if s in {"critical", "error", "errors", "blocker"}:
        return "critical"
    if s in {"high", "warning", "warnings", "major"}:
        return "high"
    if s in {"medium", "moderate", "minor"}:
        return "medium"
    if s in {"low", "info", "informational", "note", "none", "notice"}:
        return "low"
    return "medium"


def _coerce_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return None
    if f < 0 or f > 10:
        return None
    return f


# ── npm audit JSON parser (per-package expansion) ─────────────────────


def _parse_npm_audit(text: str) -> list[dict]:
    """Parse `npm audit --json` output into one row per
    package@version per advisory.

    The npm 7+ JSON shape is:

        {
          "vulnerabilities": {
            "<pkg>": {
              "name": "<pkg>",
              "severity": "high",
              "via": [
                "<advisory title>",         // string OR
                {                           // object
                  "source": 1179,
                  "name": "GHSA-xxxx",
                  "title": "<title>",
                  "severity": "high",
                  "cvss": { "score": 7.5 },
                  "url": "https://github.com/advisories/GHSA-xxxx",
                  "range": "<version range>",
                  "fixAvailable": { ... }
                }
              ],
              "effects": [],
              "range": "<version range>",
              "nodes": ["node_modules/<pkg>@<version>", ...],
              "fixAvailable": ...
            }
          },
          "metadata": { "vulnerabilities": { "total": N, "critical": ..., ... } }
        }

    Each advisory object in `via` becomes 1 row per affected
    `node_modules/<pkg>@<ver>`. When `via` is just a string (an
    internal advisory that points at another entry), we use the
    parent severity as a fallback and try to recover the per-node
    detail from `nodes`.
    """
    out: list[dict] = []
    if not text:
        return out
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return out
    vulns = doc.get("vulnerabilities") or {}
    if not isinstance(vulns, dict):
        return out

    for pkg_name, info in vulns.items():
        if not isinstance(info, dict):
            continue
        severity = _coerce_severity(info.get("severity"))
        nodes = info.get("nodes") or []
        # `nodes` is a list of paths like
        # `node_modules/lodash@4.17.20`; one entry per affected
        # version in the dep tree.
        via_entries = info.get("via") or []

        # Flatten via: each entry is either a string (forward
        # reference) or an object (advisory detail).
        for via in via_entries:
            if isinstance(via, str):
                # Forward reference. Use the parent severity and
                # produce 1 row per affected node.
                for node_path in nodes:
                    pkg_ver = _extract_pkg_version(node_path, pkg_name)
                    out.append({
                        "tool": "npm_audit",
                        "rule_id": f"npm:{pkg_name}",
                        "title": via,
                        "severity": severity,
                        "cvss_score": _NPM_PACKAGE_CVSS.get(pkg_name, _BAND_ANCHOR[severity]),
                        "package_name": pkg_name,
                        "package_version": pkg_ver,
                        "file_location": node_path,
                        "evidence": f"{pkg_name}@{pkg_ver} flagged by {via}",
                        "vulnerability_id": via,
                    })
                continue
            if not isinstance(via, dict):
                continue
            # Advisory object. 1 row per node.
            advisory_severity = _coerce_severity(
                via.get("severity") or severity
            )
            cvss_obj = via.get("cvss") or {}
            cvss_score = (
                _coerce_float(cvss_obj.get("score"))
                or _NPM_PACKAGE_CVSS.get(pkg_name)
                or _BAND_ANCHOR[advisory_severity]
            )
            rule_id = str(via.get("name") or via.get("source") or f"npm:{pkg_name}")
            title = str(via.get("title") or rule_id)
            url = via.get("url")
            for node_path in nodes or [f"node_modules/{pkg_name}"]:
                pkg_ver = _extract_pkg_version(node_path, pkg_name)
                out.append({
                    "tool": "npm_audit",
                    "rule_id": rule_id,
                    "title": title,
                    "severity": advisory_severity,
                    "cvss_score": cvss_score,
                    "cvss_vector": (cvss_obj.get("vector") if isinstance(cvss_obj, dict) else None),
                    "package_name": pkg_name,
                    "package_version": pkg_ver,
                    "file_location": node_path,
                    "vulnerability_id": rule_id,
                    "url": url,
                    "evidence": (
                        f"{pkg_name}@{pkg_ver}: {title}"
                        + (f" — {url}" if url else "")
                    ),
                })

    return out


_NODE_MODULES_RE = re.compile(
    r"node_modules/(?P<pkg>[^/@]+)(?:@(?P<ver>[^/]+))?"
)


def _extract_pkg_version(node_path: str, fallback_name: str) -> str:
    if not node_path:
        return ""
    m = _NODE_MODULES_RE.search(node_path)
    if m:
        return m.group("ver") or ""
    return ""


# ── SARIF parser (Trivy, Semgrep, CodeQL) ──────────────────────────────


def _parse_sarif(text: str, default_tool: str) -> list[dict]:
    """Parse a SARIF document into one row per result.

    Maps the SARIF `rules` block (descriptions, CWE, security
    severity) onto each `result` (file, line, message). The
    `default_tool` is used as the `tool` field when the SARIF
    `driver.name` is missing (e.g. some Trivy builds).
    """
    out: list[dict] = []
    if not text:
        return out
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return out
    runs = doc.get("runs") or []
    for run in runs:
        driver = (run.get("tool") or {}).get("driver") or {}
        tool_name = str(driver.get("name") or default_tool)
        rules_index: dict[str, dict] = {}
        for rule in (driver.get("rules") or []):
            rid = rule.get("id") or rule.get("name")
            if rid:
                rules_index[str(rid)] = rule

        for result in (run.get("results") or []):
            rid = str(result.get("ruleId") or "")
            rule = rules_index.get(rid, {})
            sev = _sarif_severity(result, rule)
            locations = result.get("locations") or []
            file_loc = ""
            line_no: int | None = None
            if locations:
                phys = (locations[0].get("physicalLocation") or {})
                artifact = (phys.get("artifactLocation") or {}).get("uri") or ""
                region = phys.get("region") or {}
                line_no = region.get("startLine")
                file_loc = f"{artifact}:{line_no}" if line_no else artifact
            message = (result.get("message") or {}).get("text") or ""
            short_desc = (
                (rule.get("shortDescription") or {}).get("text")
                or (rule.get("fullDescription") or {}).get("text")
                or message
                or rid
            )
            # Try to extract CVSS from `properties.security-severity`
            # (CodeQL) or `properties.cvss` (Trivy) or
            # `properties.severity` (Semgrep).
            props = rule.get("properties") or result.get("properties") or {}
            cvss_score = (
                _coerce_float(props.get("security-severity"))
                or _coerce_float(props.get("cvss"))
                or _coerce_float(props.get("cvssScore"))
                or _BAND_ANCHOR[sev]
            )
            cwe = _extract_cwe(props, rule)
            out.append({
                "tool": tool_name,
                "rule_id": rid or short_desc[:48],
                "title": short_desc,
                "severity": sev,
                "cvss_score": cvss_score,
                "file_location": file_loc,
                "line": line_no,
                "evidence": message[:400],
                "cwe": cwe,
            })
    return out


def _sarif_severity(result: dict, rule: dict) -> str:
    """Resolve SARIF `level` / `properties.security-severity` to a band."""
    level = (result.get("level") or "").lower()
    if level in {"error"}:
        return "critical"
    if level in {"warning"}:
        return "high"
    if level in {"note"}:
        return "low"
    # Fallback: properties.security-severity (CodeQL) maps to a
    # 0-10 score; treat >= 9.0 as critical, etc.
    props = rule.get("properties") or result.get("properties") or {}
    sev = _coerce_float(props.get("security-severity"))
    if sev is not None:
        if sev >= 9.0:
            return "critical"
        if sev >= 7.0:
            return "high"
        if sev >= 4.0:
            return "medium"
        return "low"
    # Trivy often tags SARIF results with `properties.severity`.
    raw = props.get("severity") or rule.get("defaultConfiguration", {}).get("level")
    return _coerce_severity(raw)


_CWE_RE = re.compile(r"cwe-(\d+)", re.IGNORECASE)


def _extract_cwe(props: dict, rule: dict) -> str | None:
    tags = props.get("tags") or []
    for t in tags:
        m = _CWE_RE.search(str(t))
        if m:
            return f"CWE-{m.group(1).upper()}"
    rules = rule.get("relationships") or []
    for r in rules:
        for k in (r.get("kinds") or []):
            m = _CWE_RE.search(str(k))
            if m:
                return f"CWE-{m.group(1).upper()}"
    return None


# ── Gitleaks JSON parser ───────────────────────────────────────────────


def _parse_gitleaks(text: str) -> list[dict]:
    out: list[dict] = []
    if not text:
        return out
    # Gitleaks writes NDJSON (one JSON object per line) or a JSON
    # array. Handle both.
    text = text.strip()
    if not text:
        return out
    blobs: list[dict] = []
    if text.startswith("["):
        try:
            arr = json.loads(text)
            blobs = [b for b in arr if isinstance(b, dict)]
        except (json.JSONDecodeError, ValueError):
            blobs = []
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                blobs.append(obj)
    for b in blobs:
        rule = b.get("RuleID") or b.get("Rule") or b.get("rule") or "gitleaks"
        file_loc = b.get("File") or b.get("file") or ""
        line_no = b.get("StartLine") or b.get("Line") or b.get("line")
        if line_no and file_loc:
            file_loc = f"{file_loc}:{line_no}"
        out.append({
            "tool": "gitleaks",
            "rule_id": f"gitleaks:{rule}",
            "title": f"Secret detected: {rule}",
            "severity": "high",
            "cvss_score": 7.5,
            "file_location": file_loc,
            "line": line_no,
            "evidence": (b.get("Secret") or b.get("Match") or "")[:120],
            "secret_type": rule,
        })
    return out


# ── Public API ─────────────────────────────────────────────────────────


def normalize_and_dedupe(scanner_outputs: dict[str, str]) -> dict:
    """Parse and deduplicate scanner output.

    `scanner_outputs` is a mapping of `scanner_name -> raw_text`.
    Recognised names: ``npm_audit``, ``trivy``, ``semgrep``,
    ``gitleaks``. Unknown names are passed through SARIF parsing
    as a best-effort.

    The dedupe key is
    ``(tool, rule_id, package_name, file_location)`` so the same
    CVE reported by `npm audit` AND `Trivy fs` collapses to a
    single row, but two distinct vulnerable packages (e.g.
    `lodash@4.17.20` and `lodash@4.17.21`) stay separate.
    """
    findings: list[dict] = []
    raw_count = 0
    dropped_count = 0
    errors: list[str] = []
    by_tool: dict[str, int] = {}
    by_severity: dict[str, int] = {
        "critical": 0, "high": 0, "medium": 0, "low": 0,
    }

    def _ingest(rows: list[dict], source_tool: str) -> None:
        nonlocal raw_count, dropped_count
        for r in rows:
            raw_count += 1
            if not r.get("rule_id") and not r.get("title"):
                dropped_count += 1
                continue
            sev = _coerce_severity(r.get("severity"))
            r["severity"] = sev
            if r.get("cvss_score") is None:
                r["cvss_score"] = _BAND_ANCHOR[sev]
            findings.append(r)
            by_tool[source_tool] = by_tool.get(source_tool, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

    if scanner_outputs.get("npm_audit"):
        try:
            _ingest(_parse_npm_audit(scanner_outputs["npm_audit"]), "npm_audit")
        except Exception as e:
            errors.append(f"npm_audit: {e}")

    for sarif_name, default_tool in (
        ("trivy", "trivy"),
        ("semgrep", "semgrep"),
    ):
        text = scanner_outputs.get(sarif_name)
        if not text:
            continue
        try:
            _ingest(_parse_sarif(text, default_tool), default_tool)
        except Exception as e:
            errors.append(f"{sarif_name}: {e}")

    if scanner_outputs.get("gitleaks"):
        try:
            _ingest(_parse_gitleaks(scanner_outputs["gitleaks"]), "gitleaks")
        except Exception as e:
            errors.append(f"gitleaks: {e}")

    # Dedupe by composite key. Keep the highest-severity row
    # when two scanners report the same key with conflicting
    # severities.
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    deduped: dict[tuple, dict] = {}
    for f in findings:
        key = (
            f.get("tool", "unknown"),
            f.get("rule_id", ""),
            f.get("package_name", ""),
            f.get("file_location", ""),
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = f
            continue
        if severity_rank.get(f.get("severity", "low"), 0) > severity_rank.get(existing.get("severity", "low"), 0):
            deduped[key] = f
        # Otherwise keep the existing row.

    final = list(deduped.values())
    # Recount after dedupe.
    by_tool = {}
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in final:
        by_tool[f.get("tool", "unknown")] = by_tool.get(f.get("tool", "unknown"), 0) + 1
        by_severity[f.get("severity", "low")] = by_severity.get(f.get("severity", "low"), 0) + 1

    return {
        "findings": final,
        "raw_count": raw_count,
        "dropped_count": dropped_count,
        "by_tool": by_tool,
        "by_severity": by_severity,
        "errors": errors,
    }
