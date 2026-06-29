"""OWASP Risk Rating (simplified 3-dim).

This module computes an OWASP-based risk score for a list of validated
security findings. The score is on a 0-100 scale, where 0 = highest
risk and 100 = lowest risk.

The implementation follows the OWASP Risk Rating Methodology
(https://owasp.org/www-community/risks-information/owasp-risk-rating-methodology/)
but simplifies the original 5 dimensions into 3 aggregated dimensions
that map cleanly to the standard OWASP factors:

    TAF = Threat Agent Factors (skill, motive, opportunity, population)
    VF  = Vulnerability Factors (ease of discovery, exploit, awareness,
          intrusion detection)
    BI  = Business / Technical Impact (confidentiality, integrity,
          availability)

Likelihood (L) = (TAF + VF) / 2     # range 1.0 - 5.0
Impact (I)     = BI                  # range 1.0 - 5.0
Risk (R)       = L × I              # range 1.0 - 25.0

RiskScore      = max(0, 100 - (ΣR / (n × 25)) × 100)

Level:
    ≤25  -> "critical" (highest risk)
    ≤50  -> "high"
    ≤75  -> "medium"
    >75  -> "low"    (lowest risk)
"""
from app.agents.finding_categories import (
    CATEGORY_SECURITY,
    CATEGORY_WORKFLOW_CONFIG,
    CATEGORY_MAINTENANCE,
    CATEGORY_EXTERNAL,
    classify,
    filter_security,
    is_security_finding,
)
from app.agents.pipeline_state import PipelineEngineerState
from app.agents.pipeline_schemas import SecurityFinding


# OWASP Risk Rating: severity modifier (1-5 scale dimension shift)
SEVERITY_MODIFIER = {"critical": 1.0, "high": 0.0, "medium": -0.5, "low": -1.0}


# Mapping: vulnerability type keyword -> (TAF, VF, BI) base values.
#
# These values follow the OWASP Risk Rating example tables and the
# Common Vulnerability Scoring System (CVSS) v3.1 qualitative
# severity mapping. Each tuple is (Threat Agent Factors,
# Vulnerability Factors, Business Impact) on a 1-5 scale.
#
# Reference:
#   - https://owasp.org/www-community/risks-information/owasp-risk-rating-methodology/
#   - https://www.first.org/cvss/v3.1/specification-document
_OWASP_3DIM_TYPE_MAP: dict[str, tuple[int, int, int]] = {
    # Highest risk: secrets, credentials, RCE, SQLi
    "secret":            (4, 5, 5),
    "credential":        (4, 5, 5),
    "password":          (4, 5, 5),
    "token":             (4, 5, 5),
    "key":               (4, 5, 5),
    "rce":               (5, 4, 4),
    "command_inj":       (5, 4, 4),
    "sqli":              (5, 4, 4),
    "sql_injection":     (5, 4, 4),
    "xss":               (4, 5, 3),
    "csrf":              (4, 5, 3),
    "idor":              (4, 4, 4),
    "path_traversal":    (4, 4, 4),
    "ssrf":              (4, 4, 4),
    "weak_jwt":          (3, 3, 4),
    "weak_crypto":       (3, 3, 4),
    "excessive":         (3, 5, 3),  # excessive_data_exposure
    "cve":               (3, 3, 3),
    "vulnerability":     (3, 3, 3),
    "dependency":        (3, 3, 3),
    "debug":             (2, 4, 2),
    "resource":          (2, 3, 5),
    "timeout":           (2, 3, 5),
    # other / unknown
    "":                  (2, 2, 2),
}

# Default dimensions when type does not match any keyword above.
_DEFAULT_DIMS = (2, 2, 2)


def _clamp(value: float, low: float = 1.0, high: float = 5.0) -> float:
    return max(low, min(high, value))


def _infer_severity(finding: dict) -> str:
    """Map a finding's severity to one of: critical/high/medium/low.

    Handles Code Scanning severities (error/warning/note) and standard
    OWASP severities (critical/high/medium/low) uniformly.
    """
    raw = finding.get("severity", "")
    sev = str(raw).lower().strip() if raw else ""
    if sev in {"critical", "high", "medium", "low"}:
        return sev
    # Map Code Scanning / Semgrep severities to the OWASP 4-level scale.
    if sev == "error":
        return "critical"
    if sev == "warning":
        return "high"
    if sev == "note":
        return "low"
    if sev in {"info", "informational"}:
        return "low"
    if sev in {"moderate", "minor"}:
        return "medium"
    if sev in {"major", "warnings"}:
        return "high"
    if sev in {"errors"}:
        return "critical"

    # Fallback: infer from finding type when severity is missing.
    ftype = finding.get("type", "").lower()
    if any(k in ftype for k in ("secret", "credential", "password", "token", "key")):
        return "critical"
    if any(k in ftype for k in ("injection", "rce", "sqli", "xss", "auth", "cve")):
        return "high"
    return "medium"


def _map_dimensions(finding: dict) -> dict:
    """Map a finding to the 3 OWASP-aggregated dimensions (1-5 scale).

    The output is:
        taf: Threat Agent Factors
        vf:  Vulnerability Factors
        bi:  Business / Technical Impact

    Each dimension is computed as base + severity_modifier, then clamped
    to the [1, 5] range.
    """
    ftype = finding.get("type", "").lower()
    sev = _infer_severity(finding)
    mod = SEVERITY_MODIFIER.get(sev, 0.0)

    base_taf, base_vf, base_bi = _DEFAULT_DIMS
    for key, dims in _OWASP_3DIM_TYPE_MAP.items():
        if key and key in ftype:
            base_taf, base_vf, base_bi = dims
            break

    return {
        "taf": _clamp(base_taf + mod),
        "vf":  _clamp(base_vf + mod),
        "bi":  _clamp(base_bi + mod),
    }


def _calculate_risk_score(findings: list[dict]) -> tuple[float, str, dict]:
    """Pipeline-level risk score from a list of security findings.

    Bab 5.13.3: when findings carry a CVSS base score (filled in by
    `cvss_mapper.score_finding` or by the LLM CVSS estimator), the
    score is computed as the normalised sum of CVSS values. This is
    consistent with the OWASP Risk Rating methodology but produces
    a more accurate number when the SARIF artifacts / Code Scanning
    alerts already supply a CVSS.

    Formula:
        pipeline_risk = 100 - (Σ CVSS_i / (n × 10)) × 100

    Higher score = lower risk (safer pipeline).

    When no finding has a CVSS score, we fall back to the legacy
    OWASP 3-dim heuristic (TAF + VF + BI) so the dashboard still
    surfaces a number for log-derived findings.

    IMPORTANT: `findings` MUST be the security-only subset. The risk
    score must NEVER be influenced by workflow config issues,
    maintenance warnings, or external service outages.
    """
    # Defensive: drop any non-security finding even if a caller hands
    # us the full findings list.
    security_only = [f for f in (findings or []) if is_security_finding(f)]
    findings = security_only

    if not findings:
        return 100.0, "low", {"critical": 0, "high": 0, "medium": 0, "low": 0}

    breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_cvss = 0.0
    n_with_cvss = 0

    for f in findings:
        # Make sure cvss_score / cvss_severity are present
        score = f.get("cvss_score")
        band = (f.get("cvss_severity") or "").lower()
        if not isinstance(score, (int, float)) or not band:
            try:
                from app.agents.cvss_mapper import score_finding
                score_finding(f)
                score = f.get("cvss_score")
                band = (f.get("cvss_severity") or "").lower()
            except Exception:
                score = None
                band = ""

        if isinstance(score, (int, float)) and band:
            total_cvss += float(score)
            n_with_cvss += 1
            if band in breakdown:
                breakdown[band] += 1
            # Normalise severity from cvss_severity for the dashboard.
            if not f.get("severity"):
                f["severity"] = band
        else:
            sev = _infer_severity(f)
            f["severity"] = sev
            if sev in breakdown:
                breakdown[sev] += 1

    if n_with_cvss > 0:
        # Bab 5.13.3: average CVSS across findings, then map to a
        # 0-100 risk score where 100 = no risk and 0 = max risk.
        avg_cvss = total_cvss / n_with_cvss
        risk_score = max(0.0, 100.0 - (avg_cvss / 10.0) * 100.0)
    else:
        # Legacy 3-dim OWASP heuristic for findings without CVSS.
        total_risk = 0.0
        for f in findings:
            dims = _map_dimensions(f)
            likelihood = (dims["taf"] + dims["vf"]) / 2.0
            impact = dims["bi"]
            total_risk += likelihood * impact
        avg_risk = total_risk / len(findings)
        risk_score = max(0.0, 100.0 - (avg_risk / 25.0) * 100.0)

    risk_score = round(risk_score, 1)

    # Risk level: higher score = lower risk
    if risk_score <= 25:
        risk_level = "critical"
    elif risk_score <= 50:
        risk_level = "high"
    elif risk_score <= 75:
        risk_level = "medium"
    else:
        risk_level = "low"

    return risk_score, risk_level, breakdown


def _normalize_finding(f) -> dict | None:
    """Convert a finding to a plain dict, handling pydantic models and strings."""
    if isinstance(f, dict):
        return f
    if hasattr(f, "model_dump"):
        return f.model_dump()
    if hasattr(f, "dict"):
        return f.dict()
    return None


# Patterns that must NEVER contribute to the risk score regardless of how
# they were originally tagged upstream. If any of these substrings appear
# in a finding's message, the finding is unconditionally reclassified as
# external_service_issue.
_LEAKED_EXTERNAL_PATTERNS = (
    "request failed with status code 502",
    "request failed with status code 503",
    "request failed with status code 504",
    "service unavailable",
    "gateway timeout",
    "bad gateway",
    "timeout exceeded",
    "timed out waiting",
    "connection refused",
    "connection reset",
    "econnrefused",
    "rate limit exceeded",
    "api rate limit",
    "github api rate limit",
    "github 502",
    "github 503",
    "github timeout",
    "upstream 5xx",
    "name or service not known",
    "ai_service_unavailable",
    "llmprovidererror",
    "llm unavailable",
    "llmprovider",
    "no route to host",
)


def _is_leaked_external(text: str) -> bool:
    text_l = (text or "").lower()
    return any(p in text_l for p in _LEAKED_EXTERNAL_PATTERNS)


def _ensure_security_category(finding: dict) -> dict:
    """Force a finding into a single category using the available signals.

    Re-runs the category classifier so that misclassified findings (e.g.
    a scanner that tagged a 502 as 'security') end up in the right
    bucket. This is critical for risk_assessor — only security findings
    contribute to the score.
    """
    cat = classify(finding)
    if cat != CATEGORY_SECURITY:
        # The classify() heuristic might have been misled; try harder by
        # scanning the free text for external service outage patterns
        # which sometimes get mislabelled as 'security'.
        text = " ".join(
            str(finding.get(k, "") or "")
            for k in ("message", "evidence", "explanation", "title", "type")
        )
        if _is_leaked_external(text):
            finding["category"] = CATEGORY_EXTERNAL
        elif cat in (CATEGORY_WORKFLOW_CONFIG, CATEGORY_MAINTENANCE):
            finding["category"] = cat
        else:
            finding["category"] = cat
    else:
        finding.setdefault("category", CATEGORY_SECURITY)
    return finding


def risk_assessor_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Compute the OWASP risk score from security findings.

    Reviewer feedback: the score must NEVER be influenced by
    non-security findings. The function below defensively re-categorises
    every finding before scoring to guarantee that.
    """
    findings = [_normalize_finding(f) for f in (state.get("findings") or [])]
    findings = [f for f in findings if f]

    # Re-categorise to drop config/maintenance/external issues.
    security_findings: list[dict] = []
    for f in findings:
        f = _ensure_security_category(f)
        cat = f.get("category") or classify(f)
        if cat == CATEGORY_SECURITY:
            security_findings.append(f)
        elif cat == CATEGORY_WORKFLOW_CONFIG:
            state["workflow_config_issues"] = state.get("workflow_config_issues", []) + [f]
        elif cat == CATEGORY_MAINTENANCE:
            state["maintenance_warnings"] = state.get("maintenance_warnings", []) + [f]
        elif cat == CATEGORY_EXTERNAL:
            state["external_service_issues"] = state.get("external_service_issues", []) + [f]

    risk_score, risk_level, breakdown = _calculate_risk_score(security_findings)

    state["findings"] = security_findings
    state["risk_score"] = risk_score
    state["severity_breakdown"] = breakdown
    state["risk_level"] = risk_level
    state["risk_score_metadata"] = {
        "source": "validated security findings (SARIF, npm audit, Trivy, Gitleaks, GitHub annotations)",
        "reference": "OWASP Risk Rating Methodology (3-dim: TAF, VF, BI)",
        "exclusion_note": "Workflow configuration issues, maintenance warnings, and external service issues are excluded from this score.",
    }

    return state
