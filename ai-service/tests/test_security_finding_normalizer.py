"""Tests for the evidence-based security finding normalizer."""
import json

import pytest

from app.agents.security_finding_normalizer import (
    deduplicate_findings,
    extract_tool_outputs,
    normalize_security_findings,
    parse_gitleaks,
    parse_npm_audit,
    parse_sarif,
    parse_trivy,
)


def test_parse_sarif_semgrep():
    sarif = {
        "runs": [{
            "tool": {"driver": {"name": "semgrep"}},
            "results": [{
                "ruleId": "sql-injection",
                "message": {"text": "Possible SQL injection"},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": "src/app.py"},
                        "region": {"startLine": 42, "snippet": {"text": "cursor.execute(query)"}},
                    }
                }],
            }],
        }]
    }
    findings = parse_sarif(sarif)
    assert len(findings) == 1
    f = findings[0]
    assert f["source_tool"] == "semgrep"
    assert f["title"] == "semgrep: sql-injection"
    assert f["file_location"] == "src/app.py"
    assert f["line"] == 42
    assert f["type"] == "sql_injection"
    assert f["severity"] == "medium"


def test_parse_trivy_dependency():
    trivy = {
        "Results": [{
            "Target": "package-lock.json",
            "Vulnerabilities": [{
                "PkgName": "lodash",
                "InstalledVersion": "4.17.19",
                "FixedVersion": "4.17.21",
                "Severity": "high",
                "VulnerabilityID": "CVE-2021-23337",
                "Title": "Command injection",
                "Description": "foo",
            }]
        }]
    }
    findings = parse_trivy(trivy)
    assert len(findings) == 1
    f = findings[0]
    assert f["source_tool"] == "trivy"
    assert f["cve"] == "CVE-2021-23337"
    assert f["package_name"] == "lodash"
    assert f["fixed_version"] == "4.17.21"
    assert f["severity"] == "high"


def test_parse_gitleaks_secret():
    data = [{"Description": "AWS Access Key", "Match": "AKIAIOSFODNN7EXAMPLE", "File": "config.yml", "StartLine": 5}]
    findings = parse_gitleaks(data)
    assert len(findings) == 1
    f = findings[0]
    assert f["source_tool"] == "gitleaks"
    assert f["type"] == "hardcoded_secret"
    assert f["severity"] == "critical"
    assert f["file_location"] == "config.yml"
    assert f["line"] == 5


def test_parse_npm_audit():
    npm = {
        "advisories": {
            "123": {
                "module_name": "minimist",
                "severity": "high",
                "overview": "Prototype pollution",
                "cves": ["CVE-2021-44906"],
                "findings": [{"version": "1.2.5"}],
                "patched_versions": ">=1.2.6",
            }
        }
    }
    findings = parse_npm_audit(npm)
    assert len(findings) == 1
    f = findings[0]
    assert f["source_tool"] == "npm-audit"
    assert f["package_name"] == "minimist"
    assert f["cve"] == "CVE-2021-44906"
    assert f["severity"] == "high"


def test_normalize_no_evidence_returns_message():
    result = normalize_security_findings(logs="", annotations=[])
    assert result["security_findings"] == []
    assert result["message"] == "No validated security findings detected. Workflow issues may still exist."


def test_normalize_filters_workflow_config_annotation():
    annotations = [{
        "path": ".github/workflows/ci.yml",
        "start_line": 12,
        "annotation_level": "warning",
        "message": "GITHUB_TOKEN is now required",
        "title": "Missing permissions",
    }]
    result = normalize_security_findings(annotations=annotations)
    assert len(result["security_findings"]) == 0
    assert len(result["workflow_config_issues"]) == 1
    assert result["message"] == "No validated security findings detected. Workflow issues may still exist."


def test_deduplicate_keeps_highest_severity():
    findings = [
        {"source_tool": "trivy", "title": "lodash", "file_location": "package.json", "line": 1, "severity": "medium", "evidence": "x"},
        {"source_tool": "trivy", "title": "lodash", "file_location": "package.json", "line": 1, "severity": "high", "evidence": "x"},
    ]
    result = deduplicate_findings(findings)
    assert len(result) == 1
    assert result[0]["severity"] == "high"


# ---------------------------------------------------------------------------
# Round 5: reviewer feedback — the previous dedup key included
# `title`, which collapsed legitimate findings of the same rule at
# different (file, line) pairs. The new key is (source_tool, rule_id,
# file_location, line) so each distinct location stays a distinct
# finding. These tests assert the fix and guard against regression.
# ---------------------------------------------------------------------------


def test_deduplicate_keeps_distinct_locations_of_same_rule():
    """7 findings of the same rule at 5 distinct locations must stay 5."""
    findings = []
    for file, line in [
        ("auth.js", 38),
        ("checkout.js", 25),
        ("orders.js", 47),
        ("products.js", 12),
        ("server.js", 8),
        # Two duplicates — should be removed.
        ("auth.js", 38),
        ("checkout.js", 25),
    ]:
        findings.append({
            "source_tool": "semgrep",
            "rule_id": "github.api-excessive-data-exposure",
            "title": "semgrep: github.api-excessive-data-exposure",
            "file_location": file,
            "line": line,
            "severity": "error",
            "evidence": "x",
        })
    result = deduplicate_findings(findings)
    assert len(result) == 5
    # All 5 distinct locations must be present.
    locations = {(f["file_location"], f["line"]) for f in result}
    assert locations == {
        ("auth.js", 38),
        ("checkout.js", 25),
        ("orders.js", 47),
        ("products.js", 12),
        ("server.js", 8),
    }


def test_deduplicate_collapses_same_rule_same_file_same_line():
    """The dedup still collapses true duplicates (same rule, file, line)."""
    findings = [
        {
            "source_tool": "semgrep",
            "rule_id": "github.api-cors-wildcard-origin",
            "title": "semgrep: github.api-cors-wildcard-origin",
            "file_location": "server.js",
            "line": 19,
            "severity": "error",
            "evidence": "evidence A",
        },
        {
            "source_tool": "semgrep",
            "rule_id": "github.api-cors-wildcard-origin",
            "title": "semgrep: github.api-cors-wildcard-origin",
            "file_location": "server.js",
            "line": 19,
            "severity": "error",
            "evidence": "evidence B (longer, should win)",
        },
    ]
    result = deduplicate_findings(findings)
    assert len(result) == 1
    # When severity ties, the entry with the longer evidence wins.
    assert result[0]["evidence"] == "evidence B (longer, should win)"


def test_deduplicate_keeps_separate_source_tools():
    """Same rule_id in semgrep and a CodeQL-like tool stay separate."""
    findings = [
        {
            "source_tool": "semgrep",
            "rule_id": "tainted-sql-string",
            "title": "x",
            "file_location": "auth.js",
            "line": 1,
            "severity": "error",
            "evidence": "a",
        },
        {
            "source_tool": "codeql",
            "rule_id": "tainted-sql-string",
            "title": "x",
            "file_location": "auth.js",
            "line": 1,
            "severity": "error",
            "evidence": "b",
        },
    ]
    result = deduplicate_findings(findings)
    # Different source_tool means different scanner — keep both.
    assert len(result) == 2


def test_make_finding_includes_rule_id():
    """`_make_finding` must persist `rule_id` for downstream dedup."""
    from app.agents.security_finding_normalizer import _make_finding
    f = _make_finding(
        title="semgrep: github.api-cors-wildcard-origin",
        source_tool="semgrep",
        severity="error",
        evidence="x",
        file_location="server.js",
        line=19,
        remediation_recommendation="r",
        finding_type="security_finding",
        rule_id="github.api-cors-wildcard-origin",
    )
    assert f["rule_id"] == "github.api-cors-wildcard-origin"


def test_parse_sarif_preserves_rule_id():
    """`parse_sarif` must propagate the SARIF ruleId into the finding."""
    sarif = {
        "runs": [{
            "tool": {"driver": {"name": "semgrep", "rules": []}},
            "results": [
                {
                    "ruleId": "github.api-bola-missing-ownership-check",
                    "level": "error",
                    "message": {"text": "BOLA"},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": "src/routes/orders.js"},
                            "region": {"startLine": 5},
                        },
                    }],
                },
            ],
        }],
    }
    findings = parse_sarif(sarif)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "github.api-bola-missing-ownership-check"
    assert findings[0]["file_location"] == "src/routes/orders.js"
    assert findings[0]["line"] == 5


def test_extract_tool_outputs_from_logs():
    gitleaks_output = json.dumps([{"Description": "AWS", "Match": "AKIA", "File": "x", "StartLine": 1}])
    logs = f"some log prefix\n{gitleaks_output}\nsuffix"
    outputs = extract_tool_outputs(logs)
    assert "gitleaks" in outputs
    assert len(outputs["gitleaks"]) == 1


# ---------------------------------------------------------------------------
# Round 4: empty-SARIF noise filter + markdown remediation
# ---------------------------------------------------------------------------


def test_normalize_drops_empty_sarif_noise():
    """Annotations like "X found 0 findings. Generating empty SARIF..."
    are GitHub Actions runner output, not real security findings.
    They must be dropped from every bucket so the dashboard count
    stays accurate on clean runs."""
    annotations = [
        {
            "path": ".github/workflows/ci.yml",
            "start_line": 25,
            "annotation_level": "notice",
            "title": "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "message": "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "check_name": "container-scan",
        },
        {
            "path": ".github/workflows/ci.yml",
            "start_line": 25,
            "annotation_level": "notice",
            "title": "Gitleaks found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "message": "Gitleaks found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "check_name": "secret-scan",
        },
        {
            "path": ".github/workflows/ci.yml",
            "start_line": 25,
            "annotation_level": "notice",
            "title": "Trivy found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "message": "Trivy found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
            "check_name": "dependency-scan",
        },
    ]
    result = normalize_security_findings(annotations=annotations)
    assert result["security_findings"] == [], f"empty-SARIF noise should be dropped, got {result['security_findings']}"
    assert result["workflow_config_issues"] == []
    assert result["maintenance_warnings"] == []
    assert result["external_service_issues"] == []
    assert result["message"] == "No validated security findings detected. Workflow issues may still exist."


def test_normalize_user_root_annotation_has_markdown_remediation():
    """The 'USER root detected' annotation is a real security finding
    (CWE-250, A05:2021). It must carry a markdown-formatted
    remediation with a before/after Dockerfile snippet, not the
    previous generic single-liner."""
    annotations = [{
        "path": "./Dockerfile",
        "start_line": 1,
        "annotation_level": "failure",
        "title": "USER root detected — should use non-root user",
        "message": "USER root detected — should use non-root user",
        "check_name": "container-scan",
    }]
    result = normalize_security_findings(annotations=annotations)
    assert len(result["security_findings"]) == 1
    f = result["security_findings"][0]
    assert "**" in f["remediation_recommendation"], "remediation must be markdown"
    assert "```dockerfile" in f["remediation_recommendation"], "remediation must include Dockerfile snippet"
    assert "USER node" in f["remediation_recommendation"], "remediation must include the after snippet"
    assert "docs.docker.com" in f["remediation_recommendation"], "remediation must include reference"
    assert "Review the annotation details" not in f["remediation_recommendation"]


def test_normalize_env_in_history_has_markdown_remediation():
    """The '.env file found in git history' annotation is a real
    finding (CWE-798, A02:2021). It must carry a markdown
    remediation with a gitignore snippet and git filter-repo
    command, not the previous generic single-liner."""
    annotations = [{
        "path": ".github/workflows/ci.yml",
        "start_line": 10,
        "annotation_level": "failure",
        "title": ".env file found in git history. Rotate all secrets!",
        "message": ".env file found in git history. Rotate all secrets!",
        "check_name": "pci-dss",
    }]
    result = normalize_security_findings(annotations=annotations)
    assert len(result["security_findings"]) == 1
    f = result["security_findings"][0]
    assert "**" in f["remediation_recommendation"]
    assert "```gitignore" in f["remediation_recommendation"]
    assert "```bash" in f["remediation_recommendation"]
    assert "git filter-repo" in f["remediation_recommendation"]
    assert "Rotate" in f["remediation_recommendation"]
    assert "gitleaks" in f["remediation_recommendation"]
    assert "Review the annotation details" not in f["remediation_recommendation"]
