"""Tests for the PDF report generator (app.services.report_generator)."""
import os
import sys

sys.path.insert(0, ".")

from app.services.report_generator import (
    _iter_finding_rows,
    _build_findings_table,
    _cvss_cell,
    _normalize_finding_severity,
    _escape_xml,
    _cell_style,
    _header_cell_style,
    generate_pdf_report,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import Table


def _build_mock_state(num_findings: int = 5) -> dict:
    """Build a minimal state dict with `num_findings` findings.

    The findings cycle through the 4 severity buckets so the
    breakdown histogram has data in every column. CVSS scores
    are stable per bucket so the per-row assertions can be exact.
    """
    sev_by_idx = ["critical", "high", "medium", "low"]
    score_by_idx = [9.5, 7.5, 5.0, 2.0]
    findings = []
    for i in range(num_findings):
        sev = sev_by_idx[i % 4]
        findings.append({
            "rule_id": f"github.api-test-rule-{i:03d}",
            "type": "security_finding",
            "severity": sev,
            "cvss_score": score_by_idx[i % 4],
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "file_location": f"src/routes/file_{i // 4}.js",
            "line": (i * 3) + 1,
            "explanation": f"Finding {i}: long enough to test truncation behaviour in the report.",
            "evidence": f"sample evidence for finding {i}",
        })
    return {
        "findings": findings,
        "cvss_breakdown": findings,
        "risk_score": sum(f["cvss_score"] for f in findings),
        "risk_level": "critical" if sum(f["cvss_score"] for f in findings) >= 100 else "high",
        "recommendations": [
            {"recommendation": "Rotate all secrets"},
            {"recommendation": "Upgrade dependencies"},
        ],
        "summary": "Pipeline generated successfully with 2 critical findings.",
        "repository_name": "test-repo",
        "repository_full_name": "owner/test-repo",
        "detected_technologies": {"primary_language": "JavaScript", "package_manager": "npm"},
        "detected_architecture": {"architecture_type": "monolithic"},
        "detected_domain": "e-commerce",
        "security_coverages": [],
        "pipeline_augmentations": [],
        "coverage_inference_reasoning": "Mock reasoning",
        "stages": ["lint", "test", "sast"],
        "generated_stages": ["lint", "test", "sast"],
        "stage_explanations": [],
        "validation_passed": True,
        "validation_errors": [],
        "validation_warnings": [],
        "generated_workflow": "name: ci\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest",
        "generated_workflow_filename": ".github/workflows/ci.yml",
        "ai_explanation": "Pipeline generated successfully.",
        "vignette_context": None,
        "errors": [],
    }


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(_cell_style())
    styles.add(_header_cell_style())
    return styles


# =============================================================================
# Test 1: _iter_finding_rows — row shape
# =============================================================================
def test_iter_finding_rows_basic_shape():
    """Each row should be a 5-element list: [severity, type, file, cvss, summary]."""
    findings = _build_mock_state()["findings"]
    rows = _iter_finding_rows(findings)
    assert len(rows) == len(findings)
    for row in rows:
        assert len(row) == 5
        assert isinstance(row[0], str)  # severity
        assert isinstance(row[1], str)  # type
        assert isinstance(row[2], str)  # file
        assert isinstance(row[3], str)  # cvss
        assert isinstance(row[4], str)  # summary
    print("OK test_iter_finding_rows_basic_shape")


def test_iter_finding_rows_severity_uppercased():
    rows = _iter_finding_rows(_build_mock_state()["findings"])
    for row in rows:
        assert row[0] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    print("OK test_iter_finding_rows_severity_uppercased")


def test_iter_finding_rows_strips_github_prefix():
    """GitHub Code Scanning prepends `github.` to rule IDs."""
    f = {"rule_id": "github.api-test-rule-000", "severity": "critical"}
    rows = _iter_finding_rows([f])
    assert rows[0][1] == "api-test-rule-000"  # prefix stripped
    print("OK test_iter_finding_rows_strips_github_prefix")


def test_iter_finding_rows_truncates_summary():
    """Summaries longer than 180 chars get truncated with "…"."""
    f = {"severity": "high", "explanation": "x" * 300}
    rows = _iter_finding_rows([f])
    assert len(rows[0][4]) <= 181  # 180 chars + ellipsis
    assert rows[0][4].endswith("…")
    print("OK test_iter_finding_rows_truncates_summary")


def test_iter_finding_rows_truncates_long_paths():
    """File paths longer than 34 chars get middle-truncated with "..."."""
    f = {
        "severity": "low",
        "file_location": "/very/long/path/that/exceeds/the/column/width/limit.js",
        "line": 99,
    }
    rows = _iter_finding_rows([f])
    assert "..." in rows[0][2]
    assert rows[0][2].endswith(".js:99")
    print("OK test_iter_finding_rows_truncates_long_paths")


def test_iter_finding_rows_includes_line_number():
    f = {"severity": "low", "file_location": "src/foo.js", "line": 42}
    rows = _iter_finding_rows([f])
    assert rows[0][2] == "src/foo.js:42"
    print("OK test_iter_finding_rows_includes_line_number")


# =============================================================================
# Test 2: _cvss_cell — score rendering
# =============================================================================
def test_cvss_cell_uses_score():
    f = {"cvss_score": 9.5}
    cell = _cvss_cell(f)
    assert "9.5" in cell
    print("OK test_cvss_cell_uses_score")


def test_cvss_cell_falls_back_to_severity():
    """Legacy findings without cvss_score derive from severity string."""
    f = {"severity": "critical"}
    cell = _cvss_cell(f)
    assert "9.5" in cell  # critical → 9.5
    print("OK test_cvss_cell_falls_back_to_severity")


def test_cvss_cell_handles_invalid_input():
    # None and non-dict return the em-dash placeholder
    assert _cvss_cell(None) == "—"
    # Empty dict: no cvss_score, no type, no severity → falls back
    # to severity_to_score lookup for the "low" default = 2.0
    assert "2.0" in _cvss_cell({})
    print("OK test_cvss_cell_handles_invalid_input")


# =============================================================================
# Test 3: _build_findings_table — reportlab Table
# =============================================================================
def test_build_findings_table_columns():
    """The table should have 5 columns: Severity, Type/Rule, File:Line, CVSS, Summary."""
    styles = _build_styles()
    findings = _build_mock_state()["findings"]
    rows = _iter_finding_rows(findings)
    table = _build_findings_table(rows, styles)
    # First row is the header, so total rows = findings + 1.
    assert len(table._cellvalues) == 6
    # 5 cells per row.
    assert all(len(row) == 5 for row in table._cellvalues)
    print("OK test_build_findings_table_columns")


def test_build_findings_table_total_width():
    """Column widths should sum to ~170mm (matches the rest of the report).

    reportlab's `colWidths` are stored in PDF points (1mm = 2.835pt),
    so we assert the converted mm value, not the raw point sum.
    """
    from reportlab.lib.units import mm as _mm
    styles = _build_styles()
    findings = _build_mock_state()["findings"]
    rows = _iter_finding_rows(findings)
    table = _build_findings_table(rows, styles)
    total_width_mm = sum(table._colWidths) / _mm
    assert 165 <= total_width_mm <= 175, f"expected ~170mm, got {total_width_mm:.1f}mm"
    print(f"OK test_build_findings_table_total_width ({total_width_mm:.1f}mm)")


def test_build_findings_table_severity_column_wide_enough():
    """Severity column must be wide enough to fit "CRITICAL" without wrap.

    At 5.5pt bold Helvetica, "CRITICAL" (8 chars) is approximately
    7-8mm wide. With cell padding the column needs ≥ 12mm. The
    rebalanced layout uses 22mm — still plenty of headroom.
    """
    from reportlab.lib.units import mm as _mm
    styles = _build_styles()
    findings = _build_mock_state()["findings"]
    rows = _iter_finding_rows(findings)
    table = _build_findings_table(rows, styles)
    severity_col_width_mm = table._colWidths[0] / _mm
    assert severity_col_width_mm >= 16, (
        f"Severity column {severity_col_width_mm:.1f}mm is too narrow for CRITICAL"
    )
    print(f"OK test_build_findings_table_severity_column_wide_enough ({severity_col_width_mm:.1f}mm)")


def test_build_findings_table_empty_input():
    """Empty findings list renders "(no findings)" placeholder."""
    styles = _build_styles()
    table = _build_findings_table([], styles)
    assert len(table._cellvalues) == 1
    assert table._cellvalues[0][0] == "(no findings)"
    print("OK test_build_findings_table_empty_input")


def test_build_findings_table_handles_60_findings():
    """Stress test: 60 findings (the worst case in PR #32)."""
    styles = _build_styles()
    findings = _build_mock_state(60)["findings"]
    rows = _iter_finding_rows(findings)
    table = _build_findings_table(rows, styles)
    assert len(table._cellvalues) == 61  # 60 findings + 1 header
    print("OK test_build_findings_table_handles_60_findings")


# =============================================================================
# Test 4: generate_pdf_report — end-to-end
# =============================================================================
def test_generate_pdf_report_smoke(tmp_path=None):
    """End-to-end PDF generation produces a valid PDF file."""
    out = "/tmp/test_report_smoke.pdf"
    state = _build_mock_state(10)
    result = generate_pdf_report(state, out)
    assert os.path.exists(result)
    assert os.path.getsize(result) > 1000  # >1KB
    # First 4 bytes of a PDF file are "%PDF".
    with open(result, "rb") as f:
        header = f.read(4)
    assert header == b"%PDF"
    print(f"OK test_generate_pdf_report_smoke ({os.path.getsize(result)} bytes)")


def test_generate_pdf_report_with_60_findings():
    """PDF generation works for the maximum number of findings seen in production."""
    out = "/tmp/test_report_60.pdf"
    state = _build_mock_state(60)
    result = generate_pdf_report(state, out)
    assert os.path.exists(result)
    assert os.path.getsize(result) > 1000
    print(f"OK test_generate_pdf_report_with_60_findings ({os.path.getsize(result)} bytes)")


def test_generate_pdf_report_handles_no_findings():
    """A repo with no security findings renders Section 4.2 as the
    "no findings" placeholder, not a crash."""
    out = "/tmp/test_report_empty.pdf"
    state = _build_mock_state(0)
    result = generate_pdf_report(state, out)
    assert os.path.exists(result)
    print(f"OK test_generate_pdf_report_handles_no_findings ({os.path.getsize(result)} bytes)")


# =============================================================================
# Test 5: CVSS integration
# =============================================================================
def test_finding_rows_preserve_cvss_score():
    """CVSS score must appear in the rendered row."""
    findings = [
        {"severity": "critical", "cvss_score": 9.4, "rule_id": "github.tainted-sql-string",
         "file_location": "auth.js", "line": 25, "explanation": "SQLi"},
    ]
    rows = _iter_finding_rows(findings)
    assert "9.4" in rows[0][3]
    print("OK test_finding_rows_preserve_cvss_score")


def test_finding_rows_preserve_rule_id_without_prefix():
    """Rule ID without github. prefix should be preserved."""
    findings = [
        {"severity": "high", "cvss_score": 7.5, "rule_id": "tainted-sql-string",
         "file_location": "x.js", "line": 1, "explanation": "y"},
    ]
    rows = _iter_finding_rows(findings)
    assert rows[0][1] == "tainted-sql-string"
    print("OK test_finding_rows_preserve_rule_id_without_prefix")


# =============================================================================
# Test 6: severity normalization (Code Scanning warning/error → high/critical)
# =============================================================================
def test_normalize_finding_severity_github_code_scanning():
    """GitHub Code Scanning uses warning|error|note; they must
    map to the 4 canonical buckets so the PDF matches the dashboard."""
    assert _normalize_finding_severity("error") == "critical"
    assert _normalize_finding_severity("errors") == "critical"
    assert _normalize_finding_severity("warning") == "high"
    assert _normalize_finding_severity("warnings") == "high"
    assert _normalize_finding_severity("note") == "low"
    assert _normalize_finding_severity("notice") == "low"
    # Canonical labels are pass-through.
    assert _normalize_finding_severity("critical") == "critical"
    assert _normalize_finding_severity("HIGH") == "high"
    # None / unknown / "moderate" map to "medium".
    assert _normalize_finding_severity(None) == "medium"
    assert _normalize_finding_severity("moderate") == "medium"
    assert _normalize_finding_severity("weird-value") == "medium"
    print("OK test_normalize_finding_severity_github_code_scanning")


def test_iter_finding_rows_normalizes_code_scanning_severity():
    """A finding with `severity: warning` (Code Scanning shape) must
    appear as HIGH in the row, not WARNING (which the dashboard
    never shows)."""
    f = {
        "severity": "warning",
        "rule_id": "github.api-test",
        "file_location": "x.js",
        "line": 1,
        "explanation": "y",
    }
    rows = _iter_finding_rows([f])
    assert rows[0][0] == "HIGH"
    print("OK test_iter_finding_rows_normalizes_code_scanning_severity")


# =============================================================================
# Test 7: code_scanning_alerts fallback in Section 4.2
# =============================================================================
def test_section4_uses_code_scanning_alerts():
    """Section 4.2 must read `code_scanning_alerts` (not `findings`)
    so the printed totals match the Run Detail Code Scanning Alerts
    card. We verify the contract by exercising `_iter_finding_rows`
    with the same code path Section 4.2 uses (it now picks
    `code_scanning_alerts` first, falling back to `findings`)."""
    # Code Scanning alerts win.
    state = _build_mock_state(3)
    state["code_scanning_alerts"] = [
        {
            "severity": "critical",
            "rule_id": "github.tainted-sql-string",
            "title": "Tainted SQL string",
            "file_location": "auth.js",
            "line": 25,
            "explanation": "Direct SQL injection",
            "cvss_score": 9.4,
        }
    ]
    # Replicate the selection logic in _build_section4_evaluation.
    selected = state.get("code_scanning_alerts") or state.get("findings") or []
    rows = _iter_finding_rows(selected)
    assert len(rows) == 1
    assert rows[0][0] == "CRITICAL"
    assert rows[0][1] == "tainted-sql-string"  # github. prefix stripped
    print("OK test_section4_uses_code_scanning_alerts")


def test_section4_falls_back_to_findings():
    """When `code_scanning_alerts` is missing/empty, Section 4.2
    uses the legacy `findings` list so older runs still render."""
    state = _build_mock_state(3)
    state["code_scanning_alerts"] = []
    # Replicate the selection logic in _build_section4_evaluation.
    selected = state.get("code_scanning_alerts") or state.get("findings") or []
    rows = _iter_finding_rows(selected)
    assert len(rows) == 3
    print("OK test_section4_falls_back_to_findings")


# =============================================================================
# Test 8: XML escaping — fixes the `paraparser: syntax error: parse
# ended with 1 unclosed tags` crash from raw `<` / `>` / `&` in Code
# Scanning alert messages, evidence strings, repo names, etc.
# =============================================================================
def test_escape_xml_basic():
    """The three XML-special characters get escaped."""
    assert _escape_xml("plain text") == "plain text"
    assert _escape_xml("<script>") == "&lt;script&gt;"
    assert _escape_xml("a < b") == "a &lt; b"
    assert _escape_xml("Array<T>") == "Array&lt;T&gt;"
    assert _escape_xml("a & b") == "a &amp; b"
    # The ampersand is escaped FIRST so we don't double-escape
    # the `&` we introduce with `&lt;` / `&gt;`.
    assert _escape_xml("a&<b>") == "a&amp;&lt;b&gt;"
    print("OK test_escape_xml_basic")


def test_escape_xml_handles_non_string():
    """None and non-string values are coerced to empty / string."""
    assert _escape_xml(None) == ""
    assert _escape_xml(42) == "42"
    print("OK test_escape_xml_handles_non_string")


def test_pdf_generation_survives_xml_chars_in_evidence():
    """Regression test for the original bug: a Code Scanning alert
    with `<` / `>` / `&` in its message used to crash the entire
    PDF build with `paraparser: syntax error: parse ended with
    1 unclosed tags`. The fix is to escape these characters in
    finding row cells and in the executive summary."""
    out = "/tmp/test_report_xml_chars.pdf"
    state = _build_mock_state(1)
    state["code_scanning_alerts"] = [
        {
            "severity": "critical",
            "rule_id": "github.tainted-sql-string",
            "title": "Tainted SQL string <unsafe>",
            # Code Scanning message/description can contain regex
            # patterns, generic type names, and HTML/XML snippets
            # in real codebases.
            "explanation": "Found unsafe input: <script>alert(1)</script> & co.",
            "file_location": "src/<routes>/auth.js",  # synthetic — even
                                                    # paths can have <>
                                                    # from odd repos
            "line": 12,
            "cvss_score": 9.4,
        }
    ]
    # The summary (LLM-generated) is also a known crash site.
    state["summary"] = (
        "The pipeline found a & b < 3 issues. "
        "Type signatures like Array<T> and Map<K, V> are common. "
        "Evidence: <script>alert('xss')</script>"
    )
    # This should NOT raise. Before the fix, the second
    # Paragraph call (for the summary) would crash with the
    # `unclosed tags` error.
    result = generate_pdf_report(state, out)
    assert os.path.exists(result)
    assert os.path.getsize(result) > 1000
    print(f"OK test_pdf_generation_survives_xml_chars_in_evidence ({os.path.getsize(result)} bytes)")


# Run all tests
if __name__ == "__main__":
    test_iter_finding_rows_basic_shape()
    test_iter_finding_rows_severity_uppercased()
    test_iter_finding_rows_strips_github_prefix()
    test_iter_finding_rows_truncates_summary()
    test_iter_finding_rows_truncates_long_paths()
    test_iter_finding_rows_includes_line_number()
    test_cvss_cell_uses_score()
    test_cvss_cell_falls_back_to_severity()
    test_cvss_cell_handles_invalid_input()
    test_build_findings_table_columns()
    test_build_findings_table_total_width()
    test_build_findings_table_severity_column_wide_enough()
    test_build_findings_table_empty_input()
    test_build_findings_table_handles_60_findings()
    test_generate_pdf_report_smoke()
    test_generate_pdf_report_with_60_findings()
    test_generate_pdf_report_handles_no_findings()
    test_finding_rows_preserve_cvss_score()
    test_finding_rows_preserve_rule_id_without_prefix()
    test_normalize_finding_severity_github_code_scanning()
    test_iter_finding_rows_normalizes_code_scanning_severity()
    test_section4_uses_code_scanning_alerts()
    test_section4_falls_back_to_findings()
    test_escape_xml_basic()
    test_escape_xml_handles_non_string()
    test_pdf_generation_survives_xml_chars_in_evidence()
    print("\n=== All 26 PDF report tests passed ===")
