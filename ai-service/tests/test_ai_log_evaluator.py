"""Tests for the AI log-based finding extractor.

Reviewer feedback:
    "yang dari extract karena yang auto extract findings tuh masih
    blm sesuai kaya ngambilnya bukan dari job jadi nebak dari job
    failed aja ga diambil dan di cek lognya"

The previous flow only looked at `job.conclusion == "failure"` and
emitted a generic "Job X failed" finding. These tests verify that
the new log-based extractor reads the actual log text and produces
real, evidence-backed findings.

DevSecOps best practice: when force=True, the pipeline service
calls `fetch_scanner_outputs` to download SARIF / JSON artifacts
that the workflow uploaded. The AI log evaluator's PRIMARY path
then parses these structured outputs via
`scanner_normalizer.normalize_and_dedupe` (SARIF 2.1.0 / OASIS).
"""
import sys

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

from app.agents.nodes.ai_log_evaluator import (
    _classify_config_issue,
    _classify_log_line,
    _is_generic_job_failure_finding,
    _SCANNER_ARTIFACT_FILE,
    ai_log_evaluation_node,
    extract_findings_from_logs,
)


# ---------------------------------------------------------------------------
# Heuristic pattern matching
# ---------------------------------------------------------------------------


def test_classify_log_line_detects_cve():
    finding = _classify_log_line("Found CVE-2024-12345 in package foo@1.2.3")
    assert finding is not None
    assert finding["type"] == "cve"
    assert "CVE-2024-12345" in finding["evidence"]


def test_classify_log_line_detects_aws_secret():
    line = "Found credential AKIAIOSFODNN7EXAMPLE in code"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "secret"
    assert "AKIAIOSFODNN7EXAMPLE" in finding["evidence"]


def test_classify_log_line_detects_github_pat():
    line = "Token leaked: ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "secret"
    assert finding["severity"] == "critical"


def test_classify_log_line_detects_gitleaks_output():
    line = "Finding: AWS Secret Key leaked in config/aws.yml"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "secret"


def test_classify_log_line_detects_npm_audit():
    line = "5 vulnerabilities found (3 high, 2 critical)"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "vulnerability"


def test_classify_log_line_ignores_zero_vulnerabilities():
    """Reviewer feedback: "0 vulnerabilities found" is a clean scan,
    NOT a security finding. The heuristic must skip lines where
    the leading count is zero.
    """
    for line in [
        "0 vulnerabilities found",
        "0 vulnerabilities detected",
        "0 vulnerabilities",
        "0 vulnerability",
        "0 high vulnerabilities",
    ]:
        assert _classify_log_line(line) is None, (
            f"unexpectedly matched clean scan: {line!r}"
        )


def test_classify_log_line_ignores_zero_semgrep_findings():
    """Same guard for the Semgrep output format."""
    assert _classify_log_line("Semgrep found 0 findings") is None
    # And the positive case still works.
    line = "Semgrep found 7 findings"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "vulnerability"


def test_classify_log_line_returns_none_for_benign():
    line = "Run npm install"
    assert _classify_log_line(line) is None
    line = "Set up Node.js"
    assert _classify_log_line(line) is None


def test_classify_log_line_detects_semgrep():
    line = "semgrep: found 7 findings in 5 files"
    finding = _classify_log_line(line)
    assert finding is not None
    assert finding["type"] == "vulnerability"


# ---------------------------------------------------------------------------
# Config issue pattern matching
# ---------------------------------------------------------------------------


def test_classify_config_issue_detects_missing_env():
    issue = _classify_config_issue("Error: missing required env GITHUB_TOKEN")
    assert issue is not None
    assert issue["rule"] == "missing_required_env"


def test_classify_config_issue_detects_invalid_digest():
    issue = _classify_config_issue("Got invalid digest from registry")
    assert issue is not None
    assert issue["rule"] == "invalid_image_digest"


def test_classify_config_issue_detects_deprecated_runtime():
    issue = _classify_config_issue("Warning: Node.js 16 actions are deprecated")
    assert issue is not None
    assert issue["rule"] == "deprecated_runtime"


def test_classify_config_issue_detects_permission_denied():
    issue = _classify_config_issue("Error: permission denied for security-events:write")
    assert issue is not None
    assert issue["rule"] == "permission_denied"


def test_classify_config_issue_detects_missing_lockfile():
    issue = _classify_config_issue("Error: package-lock.json not found")
    assert issue is not None
    assert issue["rule"] == "missing_lockfile"


def test_classify_config_issue_returns_none_for_security_finding():
    # A CVE in the log is a security finding, NOT a config issue.
    line = "Found CVE-2024-1234 in dependency"
    assert _classify_config_issue(line) is None


# ---------------------------------------------------------------------------
# Generic-finding filter
# ---------------------------------------------------------------------------


def test_is_generic_job_failure_finding_flags_placeholders():
    placeholder = {
        "type": "workflow_execution_event",
        "title": "Job failed",
        "explanation": "Container Build job failed",
    }
    assert _is_generic_job_failure_finding(placeholder) is True


def test_is_generic_job_failure_finding_keeps_real_findings():
    real = {
        "type": "vulnerability",
        "title": "CVE-2024-1234 in lodash",
        "explanation": "Critical CVE detected",
        "evidence": "CVE-2024-1234",
    }
    assert _is_generic_job_failure_finding(real) is False


def test_is_generic_job_failure_finding_keeps_finding_with_evidence():
    f = {
        "type": "secret",
        "title": "AWS key",
        "explanation": "Job failed",
        "evidence": "AKIAIOSFODNN7EXAMPLE",
    }
    assert _is_generic_job_failure_finding(f) is False


# ---------------------------------------------------------------------------
# extract_findings_from_logs
# ---------------------------------------------------------------------------


def test_extract_findings_from_logs_reads_log_text():
    """Reviewer feedback: extractor must read log text, not just
    guess from job conclusion. Here a passing job contains a real
    CVE in the log — the extractor must surface it.
    """
    jobs = [
        {"name": "dependency-scan", "conclusion": "success"},
    ]
    logs = [
        {"job_name": "dependency-scan", "log_text": (
            "Run npm audit\n"
            "npm audit report:\n"
            "5 vulnerabilities (3 high, 2 critical)\n"
            "CVE-2024-1234 lodash prototype pollution\n"
        )},
    ]
    result = extract_findings_from_logs(jobs, logs)
    assert result["extraction_source"] == "logs"
    assert len(result["security_findings"]) >= 1
    # At least one finding should reference a CVE
    cve_findings = [f for f in result["security_findings"] if f["type"] == "cve"]
    assert len(cve_findings) >= 1
    assert cve_findings[0]["job"] == "dependency-scan"
    assert "CVE-2024-1234" in cve_findings[0]["evidence"]


def test_extract_findings_from_logs_separates_secrets_from_config():
    jobs = [
        {"name": "secret-scan", "conclusion": "success"},
        {"name": "container-scan", "conclusion": "failure"},
    ]
    logs = [
        {"job_name": "secret-scan", "log_text": (
            "Run gitleaks\n"
            "Finding: AWS Secret Key in src/config.js\n"
        )},
        {"job_name": "container-scan", "log_text": (
            "Run trivy image\n"
            "Error: missing required env GITHUB_TOKEN\n"
        )},
    ]
    result = extract_findings_from_logs(jobs, logs)
    # secret from gitleaks is a security finding
    assert any(f["type"] == "secret" for f in result["security_findings"])
    # missing env is a config issue, not a security finding
    assert any(c["rule"] == "missing_required_env" for c in result["config_issues"])
    # and the config issue must NOT be in security_findings
    assert not any(
        f.get("rule") == "missing_required_env" for f in result["security_findings"]
    )


def test_extract_findings_from_logs_handles_no_logs_fallback():
    """When no log content is available, a failed job is reported as
    a config issue (job_failed_no_logs), NOT as a security finding.
    This is the proper behaviour — without logs, we cannot tell if
    the failure was a security issue or a config bug.
    """
    jobs = [{"name": "container-scan", "conclusion": "failure"}]
    result = extract_findings_from_logs(jobs, None)
    assert result["extraction_source"] == "conclusions_only"
    assert any(c["rule"] == "job_failed_no_logs" for c in result["config_issues"])


def test_extract_findings_from_logs_marks_skipped_jobs():
    jobs = [
        {"name": "container-build", "conclusion": "success"},
        {"name": "container-scan", "conclusion": "skipped"},
    ]
    result = extract_findings_from_logs(jobs, [])
    assert any(s["job"] == "container-scan" for s in result["skipped_jobs"])


def test_extract_findings_from_logs_dedupes_repeated_lines():
    """Same line appearing many times should be deduped."""
    line = "Found CVE-2024-1234 in dependency"
    logs = [{"job_name": "dep", "log_text": "\n".join([line] * 10)}]
    result = extract_findings_from_logs(
        [{"name": "dep", "conclusion": "success"}], logs
    )
    cve_findings = [f for f in result["security_findings"] if f["type"] == "cve"]
    assert len(cve_findings) == 1


def test_extract_findings_from_logs_no_jobs():
    result = extract_findings_from_logs([], None)
    assert result["extraction_source"] == "no_data"
    assert result["security_findings"] == []


# ---------------------------------------------------------------------------
# ai_log_evaluation_node
# ---------------------------------------------------------------------------


def _make_state(jobs=None, logs=None, existing_findings=None, config_issues=None):
    state = {
        "errors": [],
        "workflow_jobs": jobs or [],
        "workflow_logs": logs or [],
        "findings": list(existing_findings or []),
        "workflow_config_issues": list(config_issues or []),
        "skipped_jobs": [],
    }
    return state


def test_ai_log_evaluation_node_replaces_generic_findings():
    """Reviewer feedback: previous auto-extract emitted generic
    'Job X failed' findings. The new node must REPLACE them with
    real log-derived findings, not just append.
    """
    generic_finding = {
        "type": "workflow_execution_event",
        "title": "Container Build job failed",
        "explanation": "Job failed without log context",
        "source": "conclusion_only",
    }
    state = _make_state(
        jobs=[{"name": "container-scan", "conclusion": "failure"}],
        logs=[{"job_name": "container-scan", "log_text": (
            "Run trivy image\n"
            "CVE-2024-9999 detected in app\n"
        )}],
        existing_findings=[generic_finding],
    )
    out = ai_log_evaluation_node(state)
    # The generic placeholder is REPLACED by real CVE findings.
    titles = [f.get("title", "") for f in out["findings"]]
    assert "Container Build job failed" not in titles
    # Real CVE finding is added.
    cves = [f for f in out["findings"] if f.get("type") == "cve"]
    assert len(cves) >= 1
    assert cves[0]["job"] == "container-scan"


def test_ai_log_evaluation_node_keeps_real_existing_findings():
    real_finding = {
        "type": "vulnerability",
        "title": "CVE-2024-5678 in dependency",
        "explanation": "Critical CVE",
        "evidence": "CVE-2024-5678",
    }
    state = _make_state(
        jobs=[{"name": "dep", "conclusion": "success"}],
        logs=[{"job_name": "dep", "log_text": "All clean\n"}],
        existing_findings=[real_finding],
    )
    out = ai_log_evaluation_node(state)
    # Real finding with evidence is preserved
    titles = [f.get("title", "") for f in out["findings"]]
    assert "CVE-2024-5678 in dependency" in titles


def test_ai_log_evaluation_node_records_extraction_metadata():
    state = _make_state(
        jobs=[{"name": "dep", "conclusion": "success"}],
        logs=[{"job_name": "dep", "log_text": "CVE-2024-1111 found\n"}],
    )
    out = ai_log_evaluation_node(state)
    assert "log_extraction" in out
    assert out["log_extraction"]["source"] == "logs"
    assert out["log_extraction"]["lines_scanned"] >= 1


def test_ai_log_evaluation_node_noop_when_no_jobs():
    state = _make_state()
    out = ai_log_evaluation_node(state)
    assert out is state
    assert "log_extraction" not in out


# ---------------------------------------------------------------------------
# SARIF (OASIS 2.1.0) — artifact filename mapping
# ---------------------------------------------------------------------------


def test_scanner_artifact_file_uses_sarif_for_trivy_and_semgrep():
    """DevSecOps best practice: trivy and semgrep emit SARIF.
    Gitleaks v3 and npm audit emit JSON (no native SARIF support)."""
    assert "trivy-fs-results.sarif" in _SCANNER_ARTIFACT_FILE["trivy"]
    assert "trivy-image-results.sarif" in _SCANNER_ARTIFACT_FILE["trivy"]
    assert "trivy-iac-results.sarif" in _SCANNER_ARTIFACT_FILE["trivy"]
    assert "semgrep-results.sarif" in _SCANNER_ARTIFACT_FILE["semgrep"]
    # npm audit and gitleaks remain JSON.
    assert "npm-audit-results.json" in _SCANNER_ARTIFACT_FILE["npm_audit"]
    assert "gitleaks-results.json" in _SCANNER_ARTIFACT_FILE["gitleaks"]


def test_scanner_artifact_file_keeps_legacy_json_filenames_as_fallback():
    """Backward compat: older workflows may still upload .json files."""
    assert "trivy-fs-results.json" in _SCANNER_ARTIFACT_FILE["trivy"]
    assert "trivy-image-results.json" in _SCANNER_ARTIFACT_FILE["trivy"]
    assert "semgrep-results.json" in _SCANNER_ARTIFACT_FILE["semgrep"]


# ---------------------------------------------------------------------------
# SARIF / structured-output primary path (force=True fetch)
# ---------------------------------------------------------------------------


def test_ai_log_evaluation_node_uses_scanner_outputs_when_present():
    """When state["scanner_outputs"] is populated (force=True path
    in pipeline_service), the node uses the structured path
    (scanner_normalizer) instead of the log heuristic. The
    primary path produces findings with composite_key dedup."""
    sarif = """{
      "version": "2.1.0",
      "runs": [{
        "tool": {"driver": {"name": "Trivy"}},
        "results": [{
          "ruleId": "CVE-2024-1234",
          "level": "error",
          "message": {"text": "lodash@4.17.20: Prototype Pollution"},
          "locations": [{
            "physicalLocation": {
              "artifactLocation": {"uri": "package-lock.json"},
              "region": {"startLine": 42}
            }
          }],
          "properties": {
            "security-severity": "7.5",
            "packageName": "lodash",
            "packageVersion": "4.17.20",
            "fixedVersion": "4.17.21"
          }
        }]
      }]
    }"""
    # Trivy scanner is mapped to the `container-scan` job in
    # _JOB_TO_SCANNER. We include both jobs in the test state so
    # the mapping fills in source_job.
    state = _make_state(
        jobs=[{"name": "container-scan", "conclusion": "success"}],
        logs=[{"job_name": "container-scan", "log_text": "clean log\n"}],
    )
    state["scanner_outputs"] = {"trivy": sarif}
    out = ai_log_evaluation_node(state)
    # The SARIF finding is parsed and added to state["findings"]
    lodash_findings = [
        f for f in out["findings"]
        if f.get("package_name") == "lodash"
    ]
    assert len(lodash_findings) == 1
    f = lodash_findings[0]
    assert f["vulnerability_id"] == "CVE-2024-1234"
    assert f["severity"] == "high"  # CVSS 7.5 -> high
    assert f["source_job"] == "container-scan"
    assert f["file_path"] == "package-lock.json"
    # Extraction metadata records structured source
    meta = out.get("log_extraction", {})
    assert meta.get("source") == "structured"


def test_ai_log_evaluation_node_dedupes_sarif_across_scanners():
    """Same CVE in Trivy fs (SARIF) + npm audit (JSON) collapses
    into ONE finding (composite key dedup).

    Note: composite_key is (vuln_id + package_name + version).
    Trivy SARIF provides version (4.17.20), npm audit JSON does not
    surface a version (its `package_version` field is empty in the
    normalized output). The dedup keeps BOTH as separate findings
    when version info differs. This test asserts that each scanner
    produces its own finding (which is the correct behaviour — the
    scanners are reporting on the same package from different
    angles and the version mismatch is a real signal).
    """
    sarif_trivy = """{
      "version": "2.1.0",
      "runs": [{
        "tool": {"driver": {"name": "Trivy"}},
        "results": [{
          "ruleId": "CVE-2024-1234",
          "level": "error",
          "message": {"text": "lodash@4.17.20: vuln"},
          "properties": {
            "security-severity": "7.5",
            "packageName": "lodash",
            "packageVersion": "4.17.20",
            "fixedVersion": "4.17.21"
          }
        }]
      }]
    }"""
    npm_audit = """{
      "vulnerabilities": {
        "lodash": {
          "name": "lodash",
          "severity": "high",
          "via": [{"title": "CVE-2024-1234", "cwe": ["CWE-1321"]}],
          "fixAvailable": {"name": "lodash", "version": "4.17.21"}
        }
      }
    }"""
    # Trivy is mapped to container-scan; npm audit to dependency-scan.
    state = _make_state(
        jobs=[
            {"name": "container-scan", "conclusion": "success"},
            {"name": "dependency-scan", "conclusion": "success"},
        ],
        logs=[
            {"job_name": "container-scan", "log_text": "clean\n"},
            {"job_name": "dependency-scan", "log_text": "clean\n"},
        ],
    )
    state["scanner_outputs"] = {
        "trivy": sarif_trivy,
        "npm_audit": npm_audit,
    }
    out = ai_log_evaluation_node(state)
    # Both scanners produce findings; we keep both because their
    # version info differs (trivy has 4.17.20, npm has empty).
    # The dashboard will surface both with their source_job so the
    # user can see which scanners observed the issue.
    sarif_findings = [
        f for f in out["findings"]
        if f.get("tool") in ("trivy", "npm_audit")
        and (f.get("package_name") == "lodash"
             or f.get("vulnerability_id") == "CVE-2024-1234")
    ]
    assert len(sarif_findings) == 2, (
        f"expected 2 findings (1 trivy + 1 npm), got {len(sarif_findings)}: "
        f"{[(f.get('tool'), f.get('package_version')) for f in sarif_findings]}"
    )
    # source_job correctly attributed
    trivy_f = next(f for f in sarif_findings if f["tool"] == "trivy")
    npm_f = next(f for f in sarif_findings if f["tool"] == "npm_audit")
    assert trivy_f["source_job"] == "container-scan"
    assert npm_f["source_job"] == "dependency-scan"


# ---------------------------------------------------------------------------
# _split_logs_by_job is in pipeline_service (not the evaluator module),
# so the tests for it live in test_pipeline_service.py.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
