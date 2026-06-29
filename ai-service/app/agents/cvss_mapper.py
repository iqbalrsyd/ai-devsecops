"""CVSS 3.1 risk scoring (Bab 5.13.3).

Implements the three-tier lookup table described in the skripsi:

  Tier 1: RULE_CVSS_MAP  – explicit rule_id → CVSS score + vector
  Tier 2: TYPE_CVSS_FALLBACK – finding type → CVSS score
  Tier 3: SEVERITY_DEFAULT – severity string → CVSS score

This module is the single source of truth for the CVSS score attached
to every finding in the pipeline. The frontend reads `cvss_score`,
`cvss_vector`, and `cvss_severity` from the AI service response and
renders them in the RunDetail / RunAnalysis finding cards.
"""

from __future__ import annotations

from typing import Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Tier 1: explicit rule_id → CVSS v3.1
# ──────────────────────────────────────────────────────────────────────

RULE_CVSS_MAP: dict[str, dict] = {
    # SQL injection family
    "sql-injection":                        {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "sql_injection":                        {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "p/sql-injection":                      {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    # XSS
    "xss.possible":                         {"score": 6.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"},
    "xss.reflected":                        {"score": 6.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"},
    "xss.stored":                           {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N"},
    # CSRF / SSRF / path-traversal
    "csrf":                                 {"score": 6.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N"},
    "ssrf":                                 {"score": 8.6, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N"},
    "path-traversal":                       {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    # Command injection / RCE
    "command-injection":                    {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "rce":                                  {"score": 9.9, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"},
    # Auth
    "hardcoded-secret":                     {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "hardcoded-credentials":                {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "jwt-none-alg":                         {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "weak-jwt-secret":                      {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    # Deserialization
    "deserialization":                      {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "unsafe-deserialization":               {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    # E-commerce / payment
    "ecommerce.unencrypted-card-data":      {"score": 9.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "ecommerce.weak-crypto":                {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    "ecommerce.missing-audit-log":          {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N"},
    # IoT / MQTT
    "iot-mqtt.default-credentials":         {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "iot-mqtt.no-tls":                      {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    # CMS / blog
    "blog-csp.missing-csp":                 {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N"},
    "blog-csp.unsafe-markdown":             {"score": 6.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"},
    # Container / IaC
    "dockerfile.user-root":                 {"score": 7.8, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H"},
    "dockerfile.latest-tag":                {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:L"},
    # Outdated dependency / CVE
    "vulnerable-dependency":                {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "outdated-package":                     {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"},
    "cve":                                  {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    # Generic Semgrep registry
    "p/secrets":                            {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "p/owasp-top-ten":                      {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "p/javascript":                         {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"},
    "p/nodejs":                             {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"},
    # Gitleaks / TruffleHog / credential scanning
    "gitleaks.stripe":                      {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "gitleaks.github":                      {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "gitleaks.aws":                         {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "gitleaks.generic-api-key":            {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "trufflehog":                           {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
}


# ──────────────────────────────────────────────────────────────────────
# Tier 2: type-level fallback
# ──────────────────────────────────────────────────────────────────────

TYPE_CVSS_FALLBACK: dict[str, dict] = {
    "hardcoded_secret":       {"score": 7.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
    "sql_injection":          {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "nosql_injection":        {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "xss":                    {"score": 6.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"},
    "csrf":                   {"score": 6.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N"},
    "command_injection":      {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "dependency_vulnerability": {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "cve_vulnerability":      {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "insecure_config":        {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N"},
    "mqtt_no_tls":            {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    "path_traversal":         {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    "deserialization":        {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"},
}


# ──────────────────────────────────────────────────────────────────────
# Tier 3: severity string fallback (Code Scanning API mapping)
# ──────────────────────────────────────────────────────────────────────

SEVERITY_DEFAULT: dict[str, dict] = {
    "critical":   {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
    "error":      {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "high":       {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
    "warning":    {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"},
    "medium":     {"score": 5.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"},
    "note":       {"score": 3.7, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"},
    "low":        {"score": 3.7, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"},
    "info":       {"score": 3.7, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"},
}


# ──────────────────────────────────────────────────────────────────────
# Severity bands (used by the FE to render a colored pill)
# ──────────────────────────────────────────────────────────────────────

_CVSS_BANDS: tuple[tuple[float, str], ...] = (
    (9.0, "CRITICAL"),
    (7.0, "HIGH"),
    (4.0, "MEDIUM"),
    (0.1, "LOW"),
)


def cvss_severity_band(score: float) -> str:
    """Map a numeric CVSS score to a band label."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "NONE"
    for threshold, label in _CVSS_BANDS:
        if s >= threshold:
            return label
    return "NONE"


# ──────────────────────────────────────────────────────────────────────
# Public scoring API
# ──────────────────────────────────────────────────────────────────────


def score_finding(finding: dict) -> dict:
    """Attach `cvss_score`, `cvss_vector`, and `cvss_severity` to a finding.

    Implements the 3-tier lookup described in Bab 5.13.3:

      1. RULE_CVSS_MAP  – exact rule_id match
      2. TYPE_CVSS_FALLBACK – finding type match
      3. SEVERITY_DEFAULT – severity string match
      4. (last resort) default 5.0

    Returns the same dict with three extra keys populated.
    """
    if not isinstance(finding, dict):
        return finding

    rule_id = (finding.get("rule_id") or "").strip()
    f_type = (finding.get("type") or "").strip().lower()
    severity = (finding.get("severity") or "").strip().lower()

    if rule_id and rule_id in RULE_CVSS_MAP:
        entry = RULE_CVSS_MAP[rule_id]
    elif f_type in TYPE_CVSS_FALLBACK:
        entry = TYPE_CVSS_FALLBACK[f_type]
    elif severity in SEVERITY_DEFAULT:
        entry = SEVERITY_DEFAULT[severity]
    else:
        entry = {"score": 5.0, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"}

    score = float(entry["score"])
    finding["cvss_score"] = round(score, 1)
    finding["cvss_vector"] = entry["vector"]
    finding["cvss_severity"] = cvss_severity_band(score)
    return finding


def score_findings(findings: list) -> list:
    """Apply `score_finding` to a list. Returns the same list (mutated in place)."""
    if not isinstance(findings, list):
        return findings
    for f in findings:
        score_finding(f)
    return findings


def pipeline_risk_score(findings: list) -> Tuple[float, dict]:
    """Compute the pipeline-level risk score from a list of findings.

    Bab 5.13.3 says "Risk score tingkat pipeline dihitung sebagai jumlah
    seluruh skor CVSS temuan". We sum every CVSS score attributed to
    findings that successfully classified as `security_finding`.

    Returns (total_score, breakdown_by_severity).
    """
    if not isinstance(findings, list):
        return 0.0, {"critical": 0, "high": 0, "medium": 0, "low": 0, "none": 0}
    total = 0.0
    breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0, "none": 0}
    for f in findings:
        if not isinstance(f, dict):
            continue
        category = f.get("category") or ""
        if category and category != "security_finding":
            continue
        score = f.get("cvss_score")
        if score is None:
            score_finding(f)
            score = f.get("cvss_score")
        try:
            s = float(score or 0.0)
        except (TypeError, ValueError):
            continue
        total += s
        band = f.get("cvss_severity") or cvss_severity_band(s)
        breakdown[str(band).lower()] = breakdown.get(str(band).lower(), 0) + 1
    return round(total, 1), breakdown
