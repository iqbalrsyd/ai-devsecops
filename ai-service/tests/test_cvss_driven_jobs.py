"""Unit test for cvss_driven_job_generation_node.

Tests the pure-Python functions without LLM (deterministic path) and
exercises the validation/gap-detection logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.nodes.cvss_driven_job_generation_node import (
    _compute_coverage_gap,
    _top_findings_by_coverage,
    _validate_job,
    _deterministic_fallback,
    STANDARD_JOB_COVERAGES,
    DOMAIN_JOB_COVERAGES,
)


# ── Mock state ─────────────────────────────────────────────────────
def _mock_state(applicable, covered_extras=None, findings=None, domain="blog"):
    coverages = [{"id": c, "applicable": True} for c in applicable]
    if covered_extras:
        coverages += [{"id": c, "applicable": True} for c in covered_extras]
    return {
        "security_coverages": coverages,
        "job_designs": [],
        "detected_domain": domain,
        "findings": findings or [],
    }


def test_gap_no_coverages():
    """If no applicable coverages, gap is empty."""
    state = _mock_state([])
    app, covered, gap = _compute_coverage_gap(state)
    assert app == set()
    assert gap == set()
    print("✓ test_gap_no_coverages")


def test_gap_standard_jobs_covered():
    """All standard-job coverages that are applicable are already covered."""
    state = _mock_state([
        "authentication_security", "api_security", "data_security",
        "dependency_security", "file_upload_security", "container_security",
    ])
    app, covered, gap = _compute_coverage_gap(state)
    assert "logging_security" not in app
    assert gap == set()
    print("✓ test_gap_standard_jobs_covered")


def test_gap_logging_uncovered():
    """logging_security is applicable but no standard job covers it."""
    state = _mock_state([
        "authentication_security", "api_security", "data_security",
        "dependency_security", "file_upload_security", "container_security",
        "logging_security",
    ], domain="blog")
    app, covered, gap = _compute_coverage_gap(state)
    assert "logging_security" in app
    assert "logging_security" in gap
    assert "logging_security" not in covered
    print("✓ test_gap_logging_uncovered")


def test_gap_blog_cms_covered_by_domain():
    """Blog domain adds cms_security to covered set."""
    state = _mock_state([
        "authentication_security", "api_security", "data_security",
        "dependency_security", "file_upload_security", "container_security",
        "logging_security", "cms_security",
    ], domain="blog")
    app, covered, gap = _compute_coverage_gap(state)
    assert "cms_security" in covered
    assert "logging_security" in gap
    assert "cms_security" not in gap
    print("✓ test_gap_blog_cms_covered_by_domain")


def test_top_findings_by_coverage():
    """Top findings per gap coverage sorted by CVSS desc."""
    findings = [
        {"security_coverage": "logging_security", "cvss_score": 5.0, "file": "a.js", "line": 10, "rule_id": "r1", "severity": "med"},
        {"security_coverage": "logging_security", "cvss_score": 9.5, "file": "b.js", "line": 20, "rule_id": "r2", "severity": "crit"},
        {"security_coverage": "logging_security", "cvss_score": 7.0, "file": "c.js", "line": 30, "rule_id": "r3", "severity": "high"},
        {"security_coverage": "api_security", "cvss_score": 6.0, "file": "d.js", "line": 40, "rule_id": "r4", "severity": "high"},
    ]
    result = _top_findings_by_coverage(findings, {"logging_security", "api_security"}, 3)
    assert "logging_security" in result
    assert result["logging_security"][0]["cvss_score"] == 9.5
    print("✓ test_top_findings_by_coverage")


def test_validate_job_minimal_valid():
    """A well-formed job passes validation."""
    job = {
        "name": "cms-content-api-sql-injection",
        "coverage": "cms_security",
        "reasoning": "Top finding ghost/api/content.js:142 CVSS=9.8 shows raw SQLi. Standard sast does not cover raw query because <reason>. This job adds <check>.",
        "cvss_justified_by": {"file": "content.js", "line": 142, "cvss": 9.8, "cve_or_rule": "CVE-2026-26980"},
        "actions": [
            {"type": "shell_check", "name": "check", "script": "echo"},
            {"type": "sarif_upload", "category": "cms-sqli"},
        ],
        "configuration": {"continue_on_error": True, "timeout_minutes": 10},
    }
    assert _validate_job(job) is True
    print("✓ test_validate_job_minimal_valid")


def test_validate_job_rejects_standard_name():
    """Standard job names like 'sast' must be rejected."""
    job = {
        "name": "sast",
        "coverage": "cms_security",
        "reasoning": "This is a test reasoning that is more than fifty characters in total.",
        "cvss_justified_by": {"file": "x.js", "line": 1, "cvss": 5.0, "cve_or_rule": "r"},
        "actions": [
            {"type": "shell_check", "name": "a", "script": "b"},
            {"type": "sarif_upload", "category": "c"},
        ],
    }
    assert _validate_job(job) is False
    print("✓ test_validate_job_rejects_standard_name")


def test_validate_job_rejects_missing_sarif():
    """A job without sarif_upload must be rejected."""
    job = {
        "name": "test-job",
        "coverage": "cms_security",
        "reasoning": "This is a test reasoning that is more than fifty characters in total.",
        "cvss_justified_by": {"file": "x.js", "line": 1, "cvss": 5.0, "cve_or_rule": "r"},
        "actions": [
            {"type": "shell_check", "name": "a", "script": "b"},
            {"type": "shell_check", "name": "c", "script": "d"},
        ],
    }
    assert _validate_job(job) is False
    print("✓ test_validate_job_rejects_missing_sarif")


def test_validate_job_rejects_short_reasoning():
    """A job with reasoning < 50 chars must be rejected."""
    job = {
        "name": "test-job",
        "coverage": "cms_security",
        "reasoning": "short",
        "cvss_justified_by": {"file": "x.js", "line": 1, "cvss": 5.0, "cve_or_rule": "r"},
        "actions": [
            {"type": "shell_check", "name": "a", "script": "b"},
            {"type": "sarif_upload", "category": "c"},
        ],
    }
    assert _validate_job(job) is False
    print("✓ test_validate_job_rejects_short_reasoning")


def test_fallback_picks_highest_priority():
    """Deterministic fallback picks the highest-priority gap with findings."""
    gap = {"logging_security", "data_security", "api_security"}
    top_findings_by_cov = {
        "logging_security": [{"file": "a.js", "line": 10, "cvss_score": 8.5, "severity": "high", "rule_id": "r"}],
        "data_security": [{"file": "c.js", "line": 30, "cvss_score": 9.0, "severity": "crit", "rule_id": "r"}],
        "api_security": [{"file": "b.js", "line": 20, "cvss_score": 6.0, "severity": "med", "rule_id": "r"}],
    }
    result = _deterministic_fallback(gap, top_findings_by_cov, set())
    assert len(result) == 1
    assert result[0]["coverage"] == "data_security"  # Highest priority with findings
    assert result[0]["cvss_justified_by"]["cvss"] == 9.0
    print("✓ test_fallback_picks_highest_priority")


def test_fallback_returns_empty_when_no_findings():
    """If no gap coverage has findings, fallback returns empty."""
    gap = {"logging_security"}
    top_findings_by_cov = {"logging_security": []}
    result = _deterministic_fallback(gap, top_findings_by_cov, set())
    assert result == []
    print("✓ test_fallback_returns_empty_when_no_findings")


# ── Main ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_gap_no_coverages()
    test_gap_standard_jobs_covered()
    test_gap_logging_uncovered()
    test_gap_blog_cms_covered_by_domain()
    test_top_findings_by_coverage()
    test_validate_job_minimal_valid()
    test_validate_job_rejects_standard_name()
    test_validate_job_rejects_missing_sarif()
    test_validate_job_rejects_short_reasoning()
    test_fallback_picks_highest_priority()
    test_fallback_returns_empty_when_no_findings()
    print()
    print("All 11 tests passed.")
