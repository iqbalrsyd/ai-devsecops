"""
PDF Report Generator — AI DevSecOps Security Assistant

Generates a per-repository PDF report with four sections:
  1. Repository Context (technology, architecture, deployment, domain)
  2. Security Requirements (attack surfaces, threats, controls)
  3. Generated Pipeline (workflow YAML, validation, stages)
  4. Evaluation Results (findings, risk score, standards coverage, recommendations)

Triggered after all 4 pipeline stages complete (context → inference → pipeline → evaluation).
"""

import io
import os
import re
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.charts import (
    controls_donut,
    coverage_bar,
    pipeline_stage_diagram,
    risk_gauge,
    severity_bar,
    tech_stack_bar_chart,
)


# ── OWASP/CWE mapping (lightweight lookup, edit here to expand) ────────

_CONTROL_REFERENCES = {
    "sast": "CWE-89, CWE-79, CWE-22 (OWASP A03)",
    "dast": "OWASP A01-A10",
    "sca": "CWE-1104, CWE-1395",
    "secret_scanning": "CWE-798, CWE-259",
    "container_scan": "CWE-1188 (CIS Docker Benchmark)",
    "iac_scan": "CWE-1188 (CIS Benchmarks)",
    "license_scan": "OWASP A06",
    "sbom": "NTIA Minimum Elements",
    "dependency_review": "OWASP A06",
    "codeql": "CWE-89, CWE-79, CWE-22 (OWASP A03)",
    "semgrep": "CWE-89, CWE-79, CWE-22 (OWASP A03)",
    "trivy": "CWE-1104, CWE-1188",
    "gitleaks": "CWE-798",
    "tfsec": "CWE-1188 (CIS Benchmarks)",
    "checkov": "CWE-1188 (CIS Benchmarks)",
    "owasp_zap": "OWASP A01-A10",
    "npm_audit": "CWE-1104 (OWASP A06)",
    "pip_audit": "CWE-1104 (OWASP A06)",
    "audit": "CWE-1104 (OWASP A06)",
}


def _resolve_reference(control: str, tool: str) -> str:
    """Resolve an OWASP/CWE reference string from control/tool name.

    Uses the most specific (longest) matching key to avoid substring
    collisions (e.g. `secret_scanning` matching `sca` first).
    """
    haystack = f"{control} {tool}".lower()
    matches = [
        (key, ref)
        for key, ref in _CONTROL_REFERENCES.items()
        if key in haystack
    ]
    if not matches:
        return "—"
    # Pick the longest key (most specific) when multiple match.
    matches.sort(key=lambda kv: len(kv[0]), reverse=True)
    return matches[0][1]


def generate_pdf_report(
    state: dict[str, Any],
    output_path: str | None = None,
) -> str:
    """Generate a PDF report from the pipeline state and return the file path."""

    repo_name = state.get("repository_full_name", "unknown-repo")
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        reports_dir = os.environ.get("REPORTS_DIR", "/tmp/reports")
        os.makedirs(reports_dir, exist_ok=True)
        safe_name = repo_name.replace("/", "_").replace("\\", "_")
        output_path = os.path.join(reports_dir, f"{safe_name}_{timestamp}.pdf")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=22 * mm,  # extra room for the page footer
        title=f"DevSecOps Pipeline Report — {repo_name}",
        author="AI DevSecOps Security Assistant",
    )

    styles = getSampleStyleSheet()
    styles.add(_h1_style())
    styles.add(_h2_style())
    styles.add(_h3_style())
    styles.add(_body_small_style())
    styles.add(_code_style())
    styles.add(_cell_style())
    styles.add(_header_cell_style())
    styles.add(_footer_style())

    elements: list = []
    elements += _build_cover_page(repo_name, state, styles)
    elements.append(PageBreak())
    elements += _build_section1_repository_context(state, styles)
    elements.append(PageBreak())
    elements += _build_section2_security_requirements(state, styles)
    elements.append(PageBreak())
    elements += _build_section3_pipeline(state, styles)
    elements.append(PageBreak())
    elements += _build_section4_evaluation(state, styles)
    # struktur-v9: Section 5 is a *separate* page section.
    sec5 = _build_section5_coverages(state, styles)
    if sec5:
        elements.append(PageBreak())
        elements += sec5
    # Section 6: per-node I/O trace (developer-debug).
    sec6 = _build_section6_pipeline_trace(state, styles)
    if sec6:
        elements.append(PageBreak())
        elements += sec6
    # Section 7: per-scanner breakdown (disaggregates the
    # "84 vulnerabilities" roll-up into per-package rows).
    sec7 = _build_section7_scanner_breakdown(state, styles)
    if sec7:
        elements.append(PageBreak())
        elements += sec7

    # Page footer: re-print repo + run/pipeline identifiers on every
    # page so a printed or shared PDF is always traceable. The
    # cover page also has the short version; the footer carries the
    # full UUIDs because the cover only had the truncated form.
    doc.build(
        elements,
        onFirstPage=lambda c, d: _draw_page_footer(c, d, state, first_page=True),
        onLaterPages=lambda c, d: _draw_page_footer(c, d, state, first_page=False),
    )

    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    return output_path


# ── Styles ────────────────────────────────────────────────────────────


def _h1_style() -> ParagraphStyle:
    return ParagraphStyle("H1", parent=getSampleStyleSheet()["Heading1"], fontSize=18, spaceAfter=12, textColor=colors.HexColor("#1a237e"))


def _h2_style() -> ParagraphStyle:
    return ParagraphStyle("H2", parent=getSampleStyleSheet()["Heading2"], fontSize=14, spaceAfter=8, textColor=colors.HexColor("#283593"))


def _h3_style() -> ParagraphStyle:
    return ParagraphStyle("H3", parent=getSampleStyleSheet()["Heading3"], fontSize=11, spaceAfter=6, textColor=colors.HexColor("#3949ab"))


def _body_small_style() -> ParagraphStyle:
    return ParagraphStyle("BodySmall", parent=getSampleStyleSheet()["Normal"], fontSize=8, leading=10)


def _code_style() -> ParagraphStyle:
    """Mono-spaced code style for the workflow YAML block (Section 3.3).

    Tries to register the Fira Code font family from the well-known
    system paths. If the font isn't installed on the host, falls back
    to `Courier` (reportlab's default mono family). The fallback is
    silent — the table still renders, just with a different mono
    face.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "Courier"
    fira_candidates = [
        # Common Linux paths
        "/usr/share/fonts/truetype/firacode/FiraCode-Regular.ttf",
        "/usr/share/fonts/truetype/firacode/FiraMono-Regular.ttf",
        "/usr/share/fonts/TTF/FiraCode-Regular.ttf",
        "/usr/share/fonts/TTF/FiraMono-Regular.ttf",
        "/usr/local/share/fonts/FiraCode-Regular.ttf",
        # macOS
        "/Library/Fonts/FiraCode-Regular.ttf",
        "/System/Library/Fonts/Supplemental/FiraMono-Regular.ttf",
        # Windows
        "C:\\Windows\\Fonts\\FiraCode-Regular.ttf",
        "C:\\Windows\\Fonts\\FiraMono-Regular.ttf",
    ]
    for path in fira_candidates:
        try:
            pdfmetrics.registerFont(TTFont("FiraCode", path))
            font_name = "FiraCode"
            break
        except Exception:
            continue

    return ParagraphStyle(
        "ReportCode",
        parent=getSampleStyleSheet()["Code"],
        fontName=font_name,
        fontSize=7,
        leading=9,
        backColor=colors.HexColor("#f5f5f5"),
        leftIndent=8,
    )


def _cell_style() -> ParagraphStyle:
    return ParagraphStyle("Cell", parent=getSampleStyleSheet()["Normal"], fontSize=8, leading=10)


def _header_cell_style() -> ParagraphStyle:
    """White text on indigo background — used for the findings table
    header row so it matches the rest of the report (Section 3.4
    uses the same colour scheme for `#1a237e` headers)."""
    return ParagraphStyle(
        "HeaderCell",
        parent=getSampleStyleSheet()["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )


def _footer_style() -> ParagraphStyle:
    """Small grey text for the page footer."""
    return ParagraphStyle(
        "Footer",
        parent=getSampleStyleSheet()["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#666666"),
    )


def _draw_page_footer(canvas, doc, state: dict, first_page: bool = False):
    """Draw a footer on every page with repo + run/pipeline IDs.

    Without this, a user who prints or shares the PDF loses the
    trace of which pipeline and run the report came from — they
    can only see the cover page. The footer carries the full
    UUIDs (cover shows only short forms) so a copy/paste from
    any page is enough to grep the database.

    Layout: 3 lines.
        Line 1 (left):   repo + github run id
        Line 1 (right):  page X / Y
        Line 2 (left):   pipeline id (short) + version
        Line 2 (right):  generated at
        Line 3 (left):   run uuid
    """
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#666666"))

    page_w, page_h = doc.pagesize
    margin = 20 * mm
    footer_y = 12 * mm  # distance from bottom edge
    line_h = 9  # pts between footer lines

    # Right side: page number
    page_text = f"Page {doc.page}"
    canvas.drawRightString(page_w - margin, footer_y + line_h * 2, page_text)

    # Left side: 3-line identifier stack
    repo_name = state.get("repository_full_name", "unknown-repo")
    github_run_id = state.get("github_run_id")
    pipeline_id = state.get("pipeline_id") or ""
    pipeline_version = state.get("pipeline_version")
    run_uuid = state.get("run_uuid") or ""

    # Line 1: repo + run
    line1 = f"Repo: {repo_name}    GitHub run: #{github_run_id}" if github_run_id else f"Repo: {repo_name}"
    canvas.drawString(margin, footer_y + line_h * 2, line1)

    # Line 2: pipeline id + version
    line2 = f"Pipeline: {pipeline_id[:8]}…  v{pipeline_version}" if pipeline_id else ""
    canvas.drawString(margin, footer_y + line_h, line2)

    # Line 3: full run uuid (truncated in the middle to fit)
    if run_uuid:
        # Show first 8 + last 4 chars to keep the footer scannable
        # while remaining uniquely identifiable.
        line3 = f"Run UUID: {run_uuid[:8]}…{run_uuid[-4:]}"
        canvas.drawString(margin, footer_y, line3)

    canvas.restoreState()


# ── Cover Page ────────────────────────────────────────────────────────


def _build_cover_page(repo_name: str, state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Spacer(1, 40 * mm))
    elements.append(Paragraph("DevSecOps Pipeline Security Report", styles["H1"]))
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(f"Repository: <b>{_escape_xml(repo_name)}</b>", styles["H2"]))
    elements.append(Spacer(1, 4 * mm))

    arch_detected = state.get("detected_architecture") or {}
    arch = (
        _safe(arch_detected, "architecture_type", None)
        or state.get("detected_architecture_type")
        or "N/A"
    )
    domain = state.get("detected_domain") or "N/A"
    elements.append(Paragraph(
        f"Architecture: <b>{arch}</b> &nbsp;|&nbsp; Domain: <b>{domain}</b>",
        styles["Normal"],
    ))

    # struktur-v9 one-line summary. Coverages: treat every
    # entry the dashboard hands us as applicable (see Section
    # 5.1 below for the matching logic). The "X/15" format
    # indicates how many of the 15-library subset the agent
    # selected for this repository.
    coverages = state.get("security_coverages") or []
    applicable = [c for c in coverages if c.get("applicable", True) is not False]
    augmentations = state.get("pipeline_augmentations") or []
    findings = state.get("findings") or []
    stages = state.get("generated_stages") or []
    total_lib_size = 15  # security-coverage 15-library
    elements.append(Paragraph(
        f"Coverages: <b>{len(applicable)}/{len(coverages) or total_lib_size}</b> applicable "
        f"&nbsp;|&nbsp; Augmentations: <b>{len(augmentations)}</b> "
        f"&nbsp;|&nbsp; Stages: <b>{len(stages)}</b> "
        f"&nbsp;|&nbsp; Findings: <b>{len(findings)}</b>",
        styles["Normal"],
    ))

    elements.append(Spacer(1, 6 * mm))
    generated_at = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    elements.append(Paragraph(f"Generated: {generated_at}", styles["Normal"]))

    # Pipeline & run identifiers — show explicitly so the reader
    # can tell *which* pipeline version and *which* run this PDF
    # was generated from. The same `git_hub_run_id` can map to
    # multiple `pipeline_runs` rows (one per pipeline version)
    # and the API's "latest first" lookup will silently switch
    # between them, so these IDs are the source of truth.
    run_uuid = state.get("run_uuid")
    pipeline_id = state.get("pipeline_id")
    pipeline_version = state.get("pipeline_version")
    run_created_at = state.get("run_created_at")
    github_run_id = state.get("github_run_id")

    # Truncate UUIDs to a short form for the cover. Full IDs are
    # in the page footer (added by `_add_page_footer`) so the
    # reader can still copy them out of the PDF if needed.
    short_run = (run_uuid or "")[:8] if run_uuid else "—"
    short_pipe = (pipeline_id or "")[:8] if pipeline_id else "—"

    elements.append(Paragraph(
        f"Pipeline: <b>#{pipeline_version}</b> "
        f"<font size=8 color='#666666'>(id {short_pipe})</font> "
        f"&nbsp;|&nbsp; Run: <b>#{github_run_id}</b> "
        f"<font size=8 color='#666666'>(id {short_run})</font>",
        styles["Normal"],
    ))

    if run_created_at:
        # Strip microseconds for readability.
        elements.append(Paragraph(
            f"<font size=8 color='#666666'>Run created: {run_created_at}</font>",
            styles["Normal"],
        ))

    errors = state.get("errors") or []
    if errors:
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph(f"<b>Errors during pipeline:</b> {len(errors)}", styles["Normal"]))
        for e in errors:
            elements.append(Paragraph(f"&bull; {_escape_xml(e)}", styles["Normal"]))

    return elements


# ── Section 1: Repository Context ──────────────────────────────────────


def _build_section1_repository_context(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1. Repository Context", styles["H1"]))
    elements.append(Paragraph("Analysis of the repository's technology stack, architecture, deployment infrastructure, and web application domain.", styles["Normal"]))
    elements.append(Spacer(1, 6 * mm))

    # 1.1 Technology
    elements += _technology_subsection(state, styles)
    # 1.2 Architecture
    elements += _architecture_subsection(state, styles)
    # 1.3 Deployment
    elements += _deployment_subsection(state, styles)
    # 1.4 Domain
    elements += _domain_subsection(state, styles)
    # 1.5 Business Features (struktur-v8)
    elements += _features_subsection(state, styles)

    return elements


def _technology_subsection(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1.1 Technology Stack", styles["H2"]))
    tech = state.get("detected_technologies") or {}
    rows = [
        ["Primary Language", tech.get("primary_language") or "N/A"],
        ["Frameworks", ", ".join(tech.get("frameworks") or []) or "N/A"],
        ["Build Tools", ", ".join(tech.get("build_tools") or []) or "N/A"],
        ["Package Manager", tech.get("package_manager") or "N/A"],
        ["Test Framework", tech.get("test_framework") or "N/A"],
        ["Database", tech.get("database") or "N/A"],
        ["Runtime", tech.get("runtime") or "N/A"],
    ]
    elements.append(_kv_table(rows, styles))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _architecture_subsection(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1.2 Architecture Classification", styles["H2"]))
    arch = state.get("detected_architecture") or {}
    arch_type = _safe(arch, "architecture_type", None) or state.get("detected_architecture_type") or "N/A"
    reason = state.get("detected_architecture_reason") or ""
    service_count = arch.get("service_count")
    elements.append(Paragraph(f"Type: <b>{_escape_xml(arch_type)}</b>", styles["Normal"]))
    if reason:
        elements.append(Paragraph(f"Reason: {_escape_xml(reason)}", styles["Normal"]))
    if service_count:
        elements.append(Paragraph(f"Services detected: {service_count}", styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _deployment_subsection(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1.3 Deployment Infrastructure", styles["H2"]))
    deploy = state.get("detected_deployment") or {}
    rows = [
        ["Docker", _yesno(deploy.get("docker"))],
        ["Docker Compose", _yesno(deploy.get("docker_compose"))],
        ["Recommended Target", state.get("recommended_deployment_target") or "N/A"],
        ["Deployment Reason", deploy.get("deployment_reason") or "—"],
    ]
    elements.append(_kv_table(rows, styles))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _features_subsection(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1.5 Business Features & Inferred Capabilities", styles["H2"]))
    features = state.get("features") or []
    if features:
        elements.append(Paragraph(
            "Detected business features:",
            styles["BodySmall"],
        ))
        for feat in features:
            elements.append(Paragraph(f"&bull; {_escape_xml(feat)}", styles["BodySmall"]))
        elements.append(Spacer(1, 2 * mm))

    # Fallback: when Tahap 1's `features` list is empty (very common
    # for runs whose generator hasn't been re-run after the v9
    # LLM-call changes), surface the *security tooling* implied by
    # the generated pipeline. We make it clear this is a *derived*
    # view, not actual business-feature detection, so the reader
    # doesn't mistake it for a complete inventory.
    stages = state.get("generated_stages") or []
    inferred_features = _infer_features_from_stages(stages)
    if inferred_features:
        if not features:
            elements.append(Paragraph(
                "<i>No explicit business features list. Capabilities inferred from "
                "the generated pipeline (Section 3):</i>",
                styles["BodySmall"],
            ))
        else:
            elements.append(Paragraph(
                "<i>Additional capabilities inferred from the generated pipeline:</i>",
                styles["BodySmall"],
            ))
        for feat in inferred_features:
            elements.append(Paragraph(f"&bull; {_escape_xml(feat)}", styles["BodySmall"]))
    if not features and not inferred_features:
        elements.append(Paragraph(
            "No specific business features detected.",
            styles["Normal"],
        ))
    elements.append(Spacer(1, 4 * mm))
    return elements


# Map pipeline stage names → business-feature labels. Used by the
# fallback in `_features_subsection` so the Section 1.5 isn't empty
# for runs that have a generated pipeline but no Tahap 1 features list.
_STAGE_TO_FEATURE = {
    "lint": "code-quality enforcement",
    "test": "automated unit tests",
    "sast": "static application security testing",
    "sca": "dependency vulnerability scanning (SCA)",
    "dependency-scan": "dependency vulnerability scanning (SCA)",
    "secret-scan": "hardcoded secret detection",
    "container-build": "container image build",
    "container-scan": "container image vulnerability scanning",
    "pci-dss": "PCI-DSS payment compliance",
    "hipaa": "HIPAA healthcare compliance",
    "csp-headers": "Content Security Policy headers",
    "ledger-check": "fintech ledger integrity check",
    "mqtt-security": "IoT MQTT security check",
    "sbom": "Software Bill of Materials (SBOM) generation",
}


# Map pipeline stage names → the default tool used for the stage.
# Used by Section 3.2 when `stage_explanations` is empty (so the
# "Tool / Action" column isn't a column of blanks). These are the
# tools the generator actually emits by default; users can override
# them via the rules_allowlist.
_STAGE_TO_DEFAULT_TOOL = {
    "lint": "eslint",
    "test": "jest",
    "sast": "semgrep",
    "sca": "npm audit",
    "dependency-scan": "npm audit",
    "secret-scan": "gitleaks",
    "container-build": "docker build",
    "container-scan": "trivy",
    "pci-dss": "custom rules",
    "hipaa": "custom rules",
    "csp-headers": "header check",
    "ledger-check": "custom rules",
    "mqtt-security": "custom rules",
    "sbom": "syft",
}


def _stage_to_default_tool(stage: str) -> str:
    """Return the default tool name for a pipeline stage. Used by
    the Section 3.2 fallback when no per-stage explanation exists."""
    return _STAGE_TO_DEFAULT_TOOL.get((stage or "").strip().lower(), "—")


def _infer_features_from_stages(stages: list) -> list[str]:
    """Translate the generated pipeline's stage list into human-readable
    business features, preserving order and de-duplicating."""
    seen: set[str] = set()
    out: list[str] = []
    for stage in stages:
        s = (stage or "").strip().lower()
        label = _STAGE_TO_FEATURE.get(s)
        if label and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _domain_subsection(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("1.4 Web Application Domain", styles["H2"]))
    domain = state.get("detected_domain") or "general"
    evidence = state.get("domain_evidence") or []
    threats = state.get("domain_threats") or []

    elements.append(Paragraph(f"Domain: <b>{_escape_xml(domain)}</b>", styles["Normal"]))
    if evidence:
        elements.append(Paragraph("<b>Evidence:</b>", styles["Normal"]))
        for e in evidence:
            elements.append(Paragraph(f"&bull; {_escape_xml(e)}", styles["Normal"]))
    if threats:
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("<b>Domain-Specific Threats:</b>", styles["Normal"]))
        for t in threats:
            elements.append(Paragraph(f"&bull; {_escape_xml(t)}", styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))
    return elements


# ── Section 2: Security Requirements ────────────────────────────────────


def _build_section2_security_requirements(state: dict, styles: dict) -> list:
    """Section 2 — Tahap 2: Security Coverage Inference (struktur-v9).

    struktur-v9 split Tahap 2 into two LLM calls:
      7. coverage_inference   → state.security_coverages
      8. pipeline_augmentation → state.pipeline_augmentations
    The legacy v8 `inferred_security_needs.security_controls` is kept
    as a supplementary "v8 controls" list for backward compatibility
    when the v9 fields are empty.
    """
    elements: list = []
    elements.append(Paragraph("2. Security Coverage Inference", styles["H1"]))
    elements.append(Paragraph(
        "Repository-context-aware inference: the LLM reads the repository's "
        "technology stack, architecture, deployment, domain, and business "
        "features, then selects applicable security coverages (15-library) "
        "and translates them into per-coverage pipeline augmentations.",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # 2.1 Applicable Security Coverages (coverage_inference LLM #7)
    coverages = state.get("security_coverages") or []
    applicable = [c for c in coverages if c.get("applicable")]
    if coverages:
        elements.append(Paragraph("2.1 Applicable Security Coverages", styles["H2"]))
        elements.append(Paragraph(
            f"Total applicable: <b>{len(applicable)}</b> of {len(coverages)}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 2 * mm))
        cov_rows = [["Coverage ID", "Status", "Reason"]]
        for c in coverages:
            cov_rows.append([
                Paragraph(_escape_xml(_safe(c, "id", "—")), styles["Cell"]),
                Paragraph(_escape_xml("applicable" if _safe(c, "applicable", False) else "n/a"), styles["Cell"]),
                Paragraph(_escape_xml(_safe(c, "reason", "—")[:160]), styles["Cell"]),
            ])
        cov_table = Table(cov_rows, colWidths=[130 * mm, 70 * mm, 300 * mm], repeatRows=1)
        cov_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(cov_table)
        elements.append(Spacer(1, 4 * mm))

    # 2.2 Pipeline Augmentations (pipeline_augmentation LLM #8)
    augmentations = state.get("pipeline_augmentations") or []
    if augmentations:
        elements.append(Paragraph("2.2 Pipeline Augmentations (per coverage)", styles["H2"]))
        elements.append(Paragraph(
            f"Total augmentations: <b>{len(augmentations)}</b> &mdash; "
            "each row is one (coverage → job + configuration) binding.",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 2 * mm))
        aug_rows = [["Coverage", "Job", "Configuration", "Reason"]]
        for a in augmentations:
            aug_rows.append([
                Paragraph(_escape_xml(_safe(a, "coverage", "—")), styles["Cell"]),
                Paragraph(_escape_xml(_safe(a, "job", "—")), styles["Cell"]),
                Paragraph(_escape_xml(_safe(a, "configuration", "—")[:140]), styles["Cell"]),
                Paragraph(_escape_xml(_safe(a, "reason", "—")[:120]), styles["Cell"]),
            ])
        aug_table = Table(aug_rows, colWidths=[110 * mm, 80 * mm, 200 * mm, 130 * mm], repeatRows=1)
        aug_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(aug_table)
        elements.append(Spacer(1, 4 * mm))

    # 2.3 Coverage Inference Reasoning (LLM #7 free-text reasoning)
    reasoning = state.get("coverage_inference_reasoning")
    if reasoning:
        elements.append(Paragraph("2.3 Coverage Inference Reasoning", styles["H2"]))
        elements.append(Paragraph(str(reasoning), styles["BodySmall"]))
        elements.append(Spacer(1, 4 * mm))

    # 2.4 Attack Surfaces (deterministic, deployment-derived)
    attack_surfaces = state.get("attack_surfaces") or []
    if attack_surfaces:
        elements.append(Paragraph("2.4 Attack Surface Identification", styles["H2"]))
        elements.append(Paragraph("Attack surfaces identified from deployment targets (deterministic lookup):", styles["Normal"]))
        for s in attack_surfaces:
            elements.append(Paragraph(f"&bull; {_escape_xml(s)}", styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

    # 2.5 Pipeline Stages (execution order, mirror of Section 3.2)
    stages = state.get("generated_stages") or []
    if stages:
        elements.append(Paragraph("2.5 Pipeline Stages (Execution Order)", styles["H2"]))
        for i, s in enumerate(stages, 1):
            elements.append(Paragraph(f"{i}. {s}", styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

    # 2.6 Legacy v8 controls (backward compat — only when v9 coverages
    # were not produced, e.g. older runs persisted before the v9 LLM
    # calls existed).
    if not coverages:
        security_needs = state.get("inferred_security_needs") or {}
        controls = security_needs.get("security_controls") or []
        if controls:
            elements.append(Paragraph("2.6 Security Control Selection (v8 legacy)", styles["H2"]))
            elements.append(Paragraph(f"Total controls selected: {len(controls)}", styles["Normal"]))
            elements.append(Spacer(1, 2 * mm))

            control_rows = [["Control", "Status", "Tool", "Reason", "OWASP / CWE"]]
            for c in controls:
                status = _safe(c, "status", "recommended")
                tool = _safe(c, "tool", "—")
                if _safe(c, "tool_version") and c.get("tool_version") != "latest":
                    tool = f"{tool}@{c['tool_version']}"
                reason = _safe(c, "reason", "")[:90]
                ref = _resolve_reference(_safe(c, "control", ""), _safe(c, "tool", ""))
                control_rows.append([
                    Paragraph(_escape_xml(_safe(c, "control", "")), styles["Cell"]),
                    Paragraph(_escape_xml(status), styles["Cell"]),
                    Paragraph(_escape_xml(tool), styles["Cell"]),
                    Paragraph(_escape_xml(reason), styles["Cell"]),
                    Paragraph(_escape_xml(ref), styles["Cell"]),
                ])

            # Total ~170mm. Widths sized to fit single-line at
            # fontSize 7 with default table padding. Earlier 470mm
            # total compressed every cell; the values below were
            # measured against actual Helvetica-7 glyph widths plus
            # 2mm of left+right cell padding:
            #   - Control: 25mm ("secret_scan", "container_scan")
            #   - Status:  40mm ("recommended" = 11 chars × ~2.5mm)
            #   - Tool:    30mm ("gitleaks", "eslint", "trivy")
            #   - Reason:  50mm (truncate to 60 chars)
            #   - OWASP:   25mm ("CWE-89, CWE-79")
            col_widths = [25 * mm, 40 * mm, 30 * mm, 50 * mm, 25 * mm]
            table = Table(control_rows, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                # Cell padding — keeps "Status" and "Tool"
                # headers separated; lets "recommended" fit on
                # one line.
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(table)

            recommended = len([c for c in controls if c.get("status") == "recommended"])
            optional = len([c for c in controls if c.get("status") == "optional"])
            not_required = len([c for c in controls if c.get("status") == "not_required"])
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(
                f"<b>Recommended:</b> {recommended} &nbsp;|&nbsp; "
                f"<b>Optional:</b> {optional} &nbsp;|&nbsp; "
                f"<b>Not Required:</b> {not_required}",
                styles["Normal"],
            ))
            elements.append(Spacer(1, 4 * mm))

    return elements


# ── Section 3: Generated Pipeline ───────────────────────────────────────


def _build_section3_pipeline(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("3. Generated CI/CD Pipeline", styles["H1"]))
    elements.append(Paragraph("GitHub Actions workflow YAML generated from inferred security requirements.", styles["Normal"]))
    elements.append(Spacer(1, 6 * mm))

    # 3.1 Validation
    elements.append(Paragraph("3.1 Workflow Validation", styles["H2"]))
    passed = state.get("validation_passed", False)
    validation_errors = state.get("validation_errors") or []
    validation_warnings = state.get("validation_warnings") or []

    color = "green" if passed else "red"
    elements.append(Paragraph(f"Validation: <font color='{color}'><b>{'PASSED' if passed else 'FAILED'}</b></font>", styles["Normal"]))
    if validation_errors:
        elements.append(Paragraph("<b>Errors:</b>", styles["Normal"]))
        for e in validation_errors:
            elements.append(Paragraph(f"&bull; {_escape_xml(e)}", styles["Normal"]))
    if validation_warnings:
        elements.append(Paragraph("<b>Warnings:</b>", styles["Normal"]))
        for w in validation_warnings:
            elements.append(Paragraph(f"&bull; {_escape_xml(w)}", styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))

    # 3.2 Generated Stages
    stages = state.get("generated_stages") or []
    stage_explanations = state.get("stage_explanations") or []
    if stages:
        elements.append(Paragraph("3.2 Pipeline Stages", styles["H2"]))
        # Stage diagram first (visual summary), then detail table.
        status_by_stage: dict = {}
        workflow_jobs = state.get("workflow_jobs") or []
        for j in workflow_jobs:
            name = j.get("name") or j.get("workflow_name") or ""
            conclusion = j.get("conclusion")
            if conclusion == "success":
                status_by_stage[name] = "success"
            elif conclusion in ("failure", "cancelled", "timed_out"):
                status_by_stage[name] = "failed"
            elif conclusion in ("skipped", "neutral"):
                status_by_stage[name] = "skipped"
        diagram = pipeline_stage_diagram(stages, status_by_stage)
        if diagram is not None:
            elements.append(_drawable_to_flowable(diagram, width=170 * mm, height=30 * mm))
            elements.append(Spacer(1, 2 * mm))
        stage_rows = [["#", "Stage", "Tool / Action"]]
        for i, s in enumerate(stages, 1):
            tool = ""
            for se in stage_explanations:
                if se.get("stage") == s:
                    tool = _safe(se, "tool", _safe(se, "action", ""))
                    break
            # Fallback: when `stage_explanations` is empty (very
            # common for runs whose state_snapshot was persisted
            # before the generator wrote per-stage explanations),
            # derive a tool label from the stage name. This keeps
            # the table informative instead of showing a column
            # of empty cells.
            if not tool:
                tool = _stage_to_default_tool(s)
            stage_rows.append([
                Paragraph(_escape_xml(str(i)), styles["Cell"]),
                Paragraph(_escape_xml(s), styles["Cell"]),
                Paragraph(_escape_xml(tool), styles["Cell"]),
            ])
        col_widths = [20 * mm, 80 * mm, 70 * mm]
        table = Table(stage_rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 4 * mm))

    # 3.3 Workflow YAML
    yaml_content = state.get("generated_workflow")
    if yaml_content:
        elements.append(Paragraph("3.3 Workflow YAML", styles["H2"]))
        # Truncate for PDF readability (max ~200 lines)
        yaml_lines = yaml_content.strip().split("\n")
        if len(yaml_lines) > 200:
            yaml_lines = yaml_lines[:200] + ["...", f"(truncated — {len(yaml_lines)} total lines)"]
        for line in yaml_lines:
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(safe_line, styles["Code"]))
        elements.append(Spacer(1, 4 * mm))

    return elements


# ── Section 4: Evaluation Results ───────────────────────────────────────


def _build_section4_evaluation(state: dict, styles: dict) -> list:
    elements: list = []
    elements.append(Paragraph("4. Pipeline Evaluation Results", styles["H1"]))
    elements.append(Paragraph(
        "Per-finding OWASP risk classification (Likelihood x Impact). "
        "Each finding is evaluated individually; no aggregate risk score is computed.",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # 4.1 Dashboard Summary (4 buckets)
    elements.append(Paragraph("4.1 Dashboard Summary", styles["H2"]))
    dashboard = state.get("dashboard_findings") or {}
    if not dashboard:
        dashboard = {
            "security_finding": state.get("findings") or [],
            "workflow_config_issue": state.get("workflow_config_issues") or [],
            "maintenance_warning": state.get("maintenance_warnings") or [],
            "external_service_issue": state.get("external_service_issues") or [],
        }
    counts = {
        "security_finding": len(dashboard.get("security_finding") or []),
        "workflow_config_issue": len(dashboard.get("workflow_config_issue") or []),
        "maintenance_warning": len(dashboard.get("maintenance_warning") or []),
        "external_service_issue": len(dashboard.get("external_service_issue") or []),
    }
    # Compact two-column layout. The earlier three-column
    # ("Category / Count / Description") layout kept overflowing
    # even after width tuning because "Security Findings" (17
    # chars) and "Workflow Config Issues" (22 chars) need more
    # horizontal space than reportlab gives them — and the Count
    # column ended up with a number right next to the cell
    # border, visually merging. A two-column "Category / Count"
    # table is cleaner and the description is redundant with
    # the column name.
    dash_rows = [
        ["Category", "Count"],
        ["Security Findings", str(counts["security_finding"])],
        ["Workflow Config Issues", str(counts["workflow_config_issue"])],
        ["Maintenance Warnings", str(counts["maintenance_warning"])],
        ["External Service Issues", str(counts["external_service_issue"])],
    ]
    # Total 170mm. Wider Category column (~120mm) keeps the long
    # names on one line; narrow Count column (~50mm) holds the
    # number with comfortable padding.
    table = Table(dash_rows, colWidths=[120 * mm, 50 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Right-align the count column.
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        # Light background for the data rows (alternating feel).
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    # 4.2 Findings Detail
    # Align with the "Code Scanning Alerts" card on the Run Detail
    # page: that card renders `code_scanning_alerts` (SARIF findings
    # fetched from the GitHub Code Scanning API). We feed Section
    # 4.2 the same source so the totals and severity breakdown
    # match what users see in the dashboard. Fall back to the
    # legacy `findings` list (log-derived + SARIF merged) for
    # older runs that don't have the `code_scanning_alerts` key.
    findings = state.get("code_scanning_alerts") or state.get("findings") or []
    elements.append(Paragraph("4.2 Security Findings", styles["H2"]))

    # CVSS-based risk score (sum across all validated security
    # findings). Uses `_derive_cvss_score` (the same lookup the
    # per-row CVSS cell uses) so the headline number matches the
    # sum of the per-row CVSS columns below. Falls back to the
    # raw `cvss_score` field when the lookup yields no value.
    cvss_breakdown = state.get("cvss_breakdown") or []
    risk_score = state.get("risk_score")
    risk_level = state.get("risk_level")
    total_cvss = 0.0
    for f in findings:
        per_finding = _derive_cvss_score(f)
        if per_finding is not None:
            total_cvss += per_finding
    # Headline band: derive a `display_level` from the sum
    # (≥100 critical, ≥50 high, ≥25 medium, else low). The
    # colour follows the same bands the web dashboard uses
    # so the printed headline and the on-screen headline
    # agree.
    if total_cvss >= 100:
        display_level = "CRITICAL"
        display_color = "#b91c1c"  # red-700
    elif total_cvss >= 50:
        display_level = "HIGH"
        display_color = "#f97316"  # orange-500
    elif total_cvss >= 25:
        display_level = "MEDIUM"
        display_color = "#eab308"  # yellow-500
    elif total_cvss > 0:
        display_level = "LOW"
        display_color = "#22c55e"  # green-500
    else:
        display_level = "UNKNOWN"
        display_color = "#6b7280"  # gray-500
    if total_cvss > 0:
        elements.append(Paragraph(
            f"Total CVSS: <font color='{display_color}'><b>{total_cvss:.1f}</b></font> across "
            f"<b>{len(findings)}</b> finding(s). "
            f"Headline band: <b><font color='{display_color}'>{display_level}</font></b> "
            f"(critical ≥ 100, high ≥ 50, medium ≥ 25).",
            styles["Normal"],
        ))
    else:
        elements.append(Paragraph(
            f"Total findings: <b>{len(findings)}</b>",
            styles["Normal"],
        ))

    if findings:
        # severity breakdown (CVSS buckets, per-finding).
        # Normalize the severity string the same way the dashboard
        # does (GitHub Code Scanning uses warning|error|note; the
        # `security_finding_normalizer` maps error→critical and
        # warning→high) so the printed bucket counts line up with
        # the dashboard. We use `_derive_cvss_score` (not the
        # raw `cvss_score` field) so the per-bucket sums match
        # the per-row CVSS cells in the findings table and
        # the on-screen "CVSS Sum by Severity" card on the
        # web dashboard.
        sev_count = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        cvss_sum = {"critical": 0.0, "high": 0.0, "medium": 0.0, "low": 0.0}
        for f in findings:
            sev = _normalize_finding_severity(f.get("severity"))
            if sev in sev_count:
                sev_count[sev] += 1
                # Use the lookup-resolved score (rule_id →
                # package_name → severity bucket) so the per-
                # bucket sum equals the per-row CVSS cells in
                # the findings table below. Fall back to the
                # raw `cvss_score` field only when the lookup
                # yields no value at all.
                per_finding = _derive_cvss_score(f)
                if per_finding is None:
                    per_finding = float(f.get("cvss_score") or 0.0)
                cvss_sum[sev] += per_finding
        elements.append(Paragraph(
            f"Critical: {sev_count['critical']} &nbsp;|&nbsp; "
            f"High: {sev_count['high']} &nbsp;|&nbsp; "
            f"Medium: {sev_count['medium']} &nbsp;|&nbsp; "
            f"Low: {sev_count['low']}",
            styles["Normal"],
        ))
        # Severity stacked bar
        sev_chart = severity_bar(
            sev_count["critical"],
            sev_count["high"],
            sev_count["medium"],
            sev_count["low"],
        )
        if sev_chart is not None:
            elements.append(_drawable_to_flowable(sev_chart, width=170 * mm, height=12 * mm))
            elements.append(Spacer(1, 2 * mm))

        # Findings table. We chunk into 25 rows per page so a large
        # report (60+ findings) doesn't crowd a single page.
        PAGE_ROWS = 25
        rows = list(_iter_finding_rows(findings))
        total = len(rows)
        elements.append(Paragraph(
            f"<b>All {total} Findings</b>"
            + (f" (rendered in {(total + PAGE_ROWS - 1) // PAGE_ROWS} pages)" if total > PAGE_ROWS else ""),
            styles["Normal"],
        ))
        for page_idx, start in enumerate(range(0, total, PAGE_ROWS)):
            chunk = rows[start:start + PAGE_ROWS]
            if page_idx > 0:
                elements.append(PageBreak())
            elements.append(_build_findings_table(chunk, styles))

    elements.append(Spacer(1, 6 * mm))

    # 4.3 Recommendations
    recommendations = state.get("recommendations") or []
    if recommendations:
        elements.append(Paragraph("4.3 Recommendations", styles["H2"]))
        elements.append(Paragraph(f"Total recommendations: <b>{len(recommendations)}</b>", styles["Normal"]))
        for i, rec in enumerate(recommendations[:20], 1):
            if isinstance(rec, dict):
                text = rec.get("recommendation", rec.get("description", str(rec)))
            else:
                text = str(rec)
            text = str(text)[:200]
            # Strip a leading "1. " or "1) " from the recommendation
            # text itself, so the list doesn't render "1. 1. ..."
            # The recommendation generator pre-numbers its output;
            # the Paragraph below adds the *real* numbering.
            import re
            text = re.sub(r"^\s*\d+[.)]\s*", "", text)
            elements.append(Paragraph(f"<b>{i}.</b> {_escape_xml(text)}", styles["Normal"]))
        if len(recommendations) > 20:
            elements.append(Paragraph(f"... and {len(recommendations) - 20} more recommendations", styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

    # 4.4 Summary
    summary = state.get("summary")
    if summary:
        elements.append(Paragraph("4.4 Executive Summary", styles["H2"]))
        # The summary is LLM-generated and may contain raw `<` / `>`
        # (e.g. "<script>" snippets, "Array<T>" type names, "a < b"
        # comparison expressions). Escape so reportlab's parser
        # doesn't crash.
        elements.append(Paragraph(_escape_xml(summary), styles["Normal"]))

    # NOTE: Section 5 (Security Coverages Applied) is appended as a
    # *separate* page section in `generate_pdf_report` (struktur-v9).
    # Section 6 (Pipeline Execution Trace) is appended in
    # `generate_pdf_report` when `state["node_io"]` is present.

    return elements


# ── Section 6: Pipeline Execution Trace (Tahap 4) ──────────────────────


_NODE_LABELS: dict[str, str] = {
    "security_analysis": "Security Analysis (hybrid SARIF + LLM CVSS)",
    "recommendation_generation": "Recommendation Generation (LLM, deterministic fallback)",
    "response_formatter": "Response Formatter (deterministic, builds PDF payload)",
}


def _build_section6_pipeline_trace(state: dict, styles: dict) -> list:
    """Section 6: Tahap 4 pipeline execution trace (one card per node).

    Each node card shows:
      - Name + duration + status pill
      - Input keys (state fields the node consumed)
      - Output summary (compact diff of state fields the node produced)
      - Error message (only if the node failed)

    Designed for developer debugging: when a finding disappears or a
    CVSS looks wrong, the trace tells you which node did (or did not)
    update the state.
    """
    elements: list = []
    node_io = state.get("node_io") or []
    # Only render Tahap 4 nodes here. Other stages (Tahap 1-3) are
    # summarised in the existing "5. Security Coverages Applied"
    # section.
    tahap4_nodes = [
        r for r in node_io
        if r.get("node") in _NODE_LABELS
    ]
    if not tahap4_nodes:
        return elements

    elements.append(Paragraph("6. Pipeline Execution Trace (Tahap 4)", styles["H1"]))
    elements.append(Paragraph(
        "Per-node I/O log for the Security Evaluation stage. The "
        "Security Analysis node normalises SARIF findings and attaches "
        "CVSS scores; the Recommendation Generation node produces "
        "actionable fixes; the Response Formatter assembles the final "
        "dashboard payload and PDF input.",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 4 * mm))

    for rec in tahap4_nodes:
        node_name = rec.get("node", "?")
        label = _NODE_LABELS.get(node_name, node_name)
        status = (rec.get("status") or "unknown").lower()
        duration_ms = int(rec.get("duration_ms") or 0)
        duration_s = duration_ms / 1000.0
        status_pill_bg = {
            "ok": "#1b5e20",
            "error": "#b71c1c",
            "running": "#37474f",
        }.get(status, "#37474f")

        elements.append(Paragraph(
            f"<b>{_escape_xml(label)}</b>",
            styles["H3"],
        ))

        # Header row: status + duration + started_at
        header_row = [[
            Paragraph(
                f"<font color='white'><b>&nbsp;{status.upper()}&nbsp;</b></font>",
                ParagraphStyle("Pill", parent=styles["Cell"], alignment=1),
            ),
            Paragraph(f"Duration: <b>{duration_s:.2f}s</b>", styles["Cell"]),
            Paragraph(
                f"Started: {_escape_xml(str(rec.get('started_at', '—')))}",
                styles["Cell"],
            ),
        ]]
        header_table = Table(
            header_row,
            colWidths=[20 * mm, 40 * mm, 110 * mm],
        )
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(status_pill_bg)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 2 * mm))

        if status == "error" and rec.get("error"):
            elements.append(Paragraph(
                f"<font color='#b71c1c'><b>Error:</b> "
                f"{_escape_xml(str(rec.get('error')))}</font>",
                styles["Cell"],
            ))
            elements.append(Spacer(1, 2 * mm))

        # Input keys table
        input_keys = rec.get("input_keys") or []
        elements.append(Paragraph(
            f"<b>Input keys</b> ({len(input_keys)} state field(s) consumed)",
            styles["Cell"],
        ))
        if input_keys:
            input_rows = [["Key"]]
            for k in input_keys:
                input_rows.append([_escape_xml(str(k))])
            input_table = Table(input_rows, colWidths=[170 * mm])
            input_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(input_table)
        else:
            elements.append(Paragraph("(none)", styles["Cell"]))
        elements.append(Spacer(1, 2 * mm))

        # Output summary table (key, repr, type)
        out_summary = rec.get("output_summary") or {}
        elements.append(Paragraph(
            f"<b>Output changes</b> ({len(out_summary)} state field(s) updated)",
            styles["Cell"],
        ))
        if out_summary:
            out_rows = [["State key", "New value (truncated)", "Type"]]
            for k, v in out_summary.items():
                v_repr = repr(v)
                if len(v_repr) > 140:
                    v_repr = v_repr[:137] + "..."
                v_type = type(v).__name__
                if isinstance(v, str) and v.startswith("list("):
                    v_type = "list"
                out_rows.append([
                    _escape_xml(str(k)),
                    Paragraph(_escape_xml(v_repr), styles["Cell"]),
                    _escape_xml(v_type),
                ])
            out_table = Table(
                out_rows,
                colWidths=[50 * mm, 95 * mm, 25 * mm],
                repeatRows=1,
            )
            out_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(out_table)
        else:
            elements.append(Paragraph("(no state changes)", styles["Cell"]))
        elements.append(Spacer(1, 6 * mm))

    return elements


# ── Section 7: Findings by Scanner (84-row expansion) ─────────────────


def _build_section7_scanner_breakdown(state: dict, styles: dict) -> list:
    """Section 7: per-scanner breakdown of the security findings.

    GitHub Code Scanning (SARIF) groups results by the scanner that
    produced them (`tool.driver.name` in the SARIF file, or
    `scanner` / `source_tool` in the normalised alert). This
    section produces one sub-table per scanner so the reviewer can
    see at a glance which tools flagged the most issues, and so the
    "84 vulnerabilities" roll-up row in the dashboard is
    disaggregated here into the per-package / per-instance rows.
    """
    elements: list = []
    findings = (
        state.get("code_scanning_alerts")
        or state.get("findings")
        or []
    )
    if not findings:
        return elements

    # Group by scanner (tool → scanner → source_tool → rule_id
    # prefix). The scanner_normalizer tags each row with
    # `tool: "npm_audit" | "trivy" | "semgrep" | "CodeQL" | ...`
    # so prefer that field. Legacy rows (from before the
    # normalizer existed) only carry `scanner` or `source_tool`.
    by_scanner: dict[str, list[dict]] = {}
    for f in findings:
        scanner = (
            f.get("tool")
            or f.get("scanner")
            or f.get("source_tool")
            or _infer_scanner_from_rule(f.get("rule_id", ""))
            or "unknown"
        )
        by_scanner.setdefault(str(scanner), []).append(f)

    if len(by_scanner) <= 1:
        # No useful disaggregation possible (single scanner).
        return elements

    elements.append(Paragraph("7. Findings by Scanner", styles["H1"]))
    elements.append(Paragraph(
        "Per-scanner disaggregation of the security findings. "
        "GitHub Code Scanning groups alerts by the producing tool; "
        "the same CVE reported by two scanners is counted twice here "
        "and once in the dashboard (de-duplicated on rule_id + file "
        "+ line).",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # Summary table: scanner name, count, average CVSS, top rule
    summary_rows = [["Scanner", "Findings", "Avg CVSS", "Top rule_id"]]
    sorted_scanners = sorted(
        by_scanner.items(),
        key=lambda kv: -len(kv[1]),
    )
    for scanner, items in sorted_scanners:
        scores = [
            float(it.get("cvss_score") or 0.0)
            for it in items
            if isinstance(it.get("cvss_score"), (int, float))
        ]
        avg = sum(scores) / len(scores) if scores else 0.0
        # Top rule_id by frequency
        rule_counts: dict[str, int] = {}
        for it in items:
            rid = it.get("rule_id") or "—"
            rule_counts[str(rid)] = rule_counts.get(str(rid), 0) + 1
        top_rule = max(rule_counts.items(), key=lambda kv: kv[1])[0] if rule_counts else "—"
        summary_rows.append([
            _escape_xml(scanner),
            str(len(items)),
            f"{avg:.1f}" if avg > 0 else "—",
            _escape_xml(top_rule[:48]),
        ])
    summary_table = Table(
        summary_rows,
        colWidths=[50 * mm, 25 * mm, 25 * mm, 70 * mm],
        repeatRows=1,
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 1), (2, -1), "RIGHT"),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 6 * mm))

    # Per-scanner detail. Cap each scanner at 50 rows so the PDF
    # stays bounded; if a scanner has more, the remaining count is
    # surfaced as a note line.
    PER_SCANNER_CAP = 50
    for scanner, items in sorted_scanners:
        elements.append(Paragraph(
            f"<b>{_escape_xml(scanner)}</b> &nbsp;-&nbsp; {len(items)} finding(s)",
            styles["H3"],
        ))
        detail_rows = [["Severity", "Rule", "Package / File", "CVSS", "Summary (truncated)"]]
        for f in items[:PER_SCANNER_CAP]:
            sev = _normalize_finding_severity(f.get("severity")).upper()
            rule = str(f.get("rule_id") or f.get("type") or "—")
            pkg_or_file = (
                f.get("package_name")
                or f.get("file_location")
                or f.get("file")
                or "—"
            )
            score = _derive_cvss_score(f)
            cvss_text = f"{score:.1f}" if score is not None else "—"
            summary_text = (
                f.get("explanation")
                or f.get("evidence")
                or f.get("description")
                or "—"
            )
            if isinstance(summary_text, str) and len(summary_text) > 120:
                summary_text = summary_text[:117] + "…"
            detail_rows.append([
                _escape_xml(sev),
                Paragraph(_escape_xml(rule[:40]), styles["Cell"]),
                Paragraph(_escape_xml(str(pkg_or_file)[:50]), styles["Cell"]),
                _escape_xml(cvss_text),
                Paragraph(_escape_xml(str(summary_text)), styles["Cell"]),
            ])
        detail_table = Table(
            detail_rows,
            colWidths=[18 * mm, 36 * mm, 46 * mm, 14 * mm, 56 * mm],
            repeatRows=1,
        )
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283593")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("LEADING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ]))
        elements.append(detail_table)
        if len(items) > PER_SCANNER_CAP:
            elements.append(Paragraph(
                f"<i>... and {len(items) - PER_SCANNER_CAP} more finding(s) "
                f"from this scanner (not shown)</i>",
                styles["Cell"],
            ))
        elements.append(Spacer(1, 4 * mm))

    return elements


def _infer_scanner_from_rule(rule_id: str) -> str | None:
    """Best-effort scanner name from a rule_id prefix.

    Examples:
      - ``github.dependabot``  -> ``Dependabot``
      - ``github.codeql``      -> ``CodeQL``
      - ``semgrep.api-...``    -> ``Semgrep``
      - ``javascript.lang.``   -> ``CodeQL`` (default for SARIF)
    """
    if not rule_id:
        return None
    rid = rule_id.lower()
    if rid.startswith("github.dependabot") or "dependabot" in rid:
        return "Dependabot"
    if rid.startswith("github.codeql") or "codeql" in rid:
        return "CodeQL"
    if rid.startswith("semgrep.") or "semgrep" in rid:
        return "Semgrep"
    if rid.startswith("trivy."):
        return "Trivy"
    if "gitleaks" in rid:
        return "Gitleaks"
    if rid.startswith("javascript.") or rid.startswith("python."):
        return "CodeQL"
    return None


def _build_section5_coverages(state: dict, styles: dict) -> list:
    """Section 5: Security Coverages Applied (struktur-v9).

    5.1 Applicable Coverages
    5.2 Pipeline Augmentations
    5.3 Coverage-to-Finding Mapping
    """
    elements: list = []
    coverages = state.get("security_coverages") or []
    augmentations = state.get("pipeline_augmentations") or []
    if not coverages and not augmentations:
        return elements

    elements.append(Paragraph("5. Security Coverages Applied", styles["H1"]))
    elements.append(Paragraph(
        "Security coverages inferred from repository context (architecture, framework, "
        "deployment, domain, features) and translated into pipeline augmentations.",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # 5.1 Applicable Coverages. Treat every entry the dashboard
    # hands us as applicable — the dashboard already filtered
    # the 15-library down to the per-repo subset. Honour an
    # explicit `applicable: false` flag when present (used by
    # the AI agent to mark a coverage as "considered but
    # not applicable for this repo") but never drop a row
    # silently.
    applicable = [c for c in coverages if c.get("applicable", True) is not False]
    if applicable:
        elements.append(Paragraph("5.1 Applicable Coverages", styles["H2"]))
        elements.append(Paragraph(
            f"Total applicable: <b>{len(applicable)}</b> of {len(coverages) or 15}",
            styles["Normal"],
        ))
        cov_rows = [["Coverage", "Reason"]]
        for c in applicable:
            cov_rows.append([
                Paragraph(_escape_xml(_safe(c, "id", "—")), styles["Cell"]),
                Paragraph(_escape_xml(_safe(c, "reason", "—")[:200]), styles["Cell"]),
            ])
        table = Table(cov_rows, colWidths=[60 * mm, 110 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    if augmentations:
        elements.append(Paragraph("5.2 Pipeline Augmentations", styles["H2"]))
        elements.append(Paragraph(
            f"Total augmentations: <b>{len(augmentations)}</b>",
            styles["Normal"],
        ))
        aug_rows = [["Coverage", "Job", "Configuration"]]
        for a in augmentations:
            aug_rows.append([
                Paragraph(_escape_xml(_safe(a, "coverage", "—")), styles["Cell"]),
                Paragraph(_escape_xml(_safe(a, "job", "—")), styles["Cell"]),
                Paragraph(_escape_xml(_safe(a, "configuration", "—")[:120]), styles["Cell"]),
            ])
        table = Table(aug_rows, colWidths=[60 * mm, 35 * mm, 75 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    # 5.3 Coverage-to-Finding Mapping
    findings = state.get("findings") or []
    if findings:
        cov_count: dict[str, int] = {}
        for f in findings:
            cov = f.get("security_coverage") or "uncategorized"
            cov_count[cov] = cov_count.get(cov, 0) + 1
        if cov_count:
            elements.append(Paragraph("5.3 Coverage-to-Finding Mapping", styles["H2"]))
            map_rows = [["Security Coverage", "# Findings"]]
            for cov, count in sorted(cov_count.items(), key=lambda x: -x[1]):
                map_rows.append([
                    Paragraph(_escape_xml(cov), styles["Cell"]),
                    Paragraph(_escape_xml(str(count)), styles["Cell"]),
                ])
            table = Table(map_rows, colWidths=[130 * mm, 40 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(table)

    # 5.4 AI-Generated Semgrep Rules (K2.3)
    ai_rules = state.get("ai_generated_rules") or []
    if ai_rules:
        elements.append(Paragraph(
            "5.4 AI-Generated Semgrep Rules (K2.3)", styles["H2"]
        ))
        elements.append(Paragraph(
            "Adaptive Semgrep rules produced by the pattern_inference node "
            "for this specific repository. Each rule is committed to "
            "<font name=\"Courier\">.github/ai-devsecops-rules.yml</font> and "
            "consumed by the <font name=\"Courier\">sast</font> job.",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 4 * mm))
        rule_rows = [["Rule ID", "Coverage", "Severity", "Reasoning"]]
        for r in ai_rules:
            md = r.get("metadata") or {}
            rule_rows.append([
                Paragraph(
                    _escape_xml(_safe(r, "id", "—")[:60]),
                    styles["Cell"],
                ),
                Paragraph(
                    _escape_xml(md.get("ai-devsecops-coverage", "—")),
                    styles["Cell"],
                ),
                Paragraph(
                    _escape_xml(_safe(r, "severity", "—")),
                    styles["Cell"],
                ),
                Paragraph(
                    _escape_xml(
                        md.get("ai-devsecops-reasoning", "—")[:150]
                    ),
                    styles["Cell"],
                ),
            ])
        table = Table(
            rule_rows, colWidths=[55 * mm, 35 * mm, 25 * mm, 55 * mm], repeatRows=1
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    # 5.5 AI-Designed Custom Jobs (K2.4)
    job_designs = state.get("job_designs") or []
    if job_designs:
        elements.append(Paragraph(
            "5.5 AI-Designed Custom Jobs (K2.4)", styles["H2"]
        ))
        elements.append(Paragraph(
            "CI jobs designed by the job_reasoning node (up to 3 per run) "
            "for repository-specific patterns the standard jobs cannot catch.",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 4 * mm))
        job_rows = [["Name", "Coverage", "# Actions", "Reasoning"]]
        for j in job_designs:
            actions = j.get("actions") or []
            job_rows.append([
                Paragraph(
                    _escape_xml(_safe(j, "name", "—")[:40]),
                    styles["Cell"],
                ),
                Paragraph(
                    _escape_xml(_safe(j, "coverage", "—")),
                    styles["Cell"],
                ),
                Paragraph(_escape_xml(str(len(actions))), styles["Cell"]),
                Paragraph(
                    _escape_xml(_safe(j, "reasoning", "—")[:200]),
                    styles["Cell"],
                ),
            ])
        table = Table(
            job_rows, colWidths=[50 * mm, 35 * mm, 20 * mm, 65 * mm], repeatRows=1
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)

    return elements


# ── Helpers ────────────────────────────────────────────────────────────


def _safe(d: Any, key: str, default: Any = "") -> Any:
    """dict.get that treats a stored `None` as missing.

    Some findings have `{"file": None}` rather than omitting the key. Plain
    `d.get("file", "—")` returns `None` in that case, which later breaks
    reportlab's Paragraph (it tries to call `.split` on the value). Coerce
    `None` to the supplied default so the PDF never receives `None`.
    """
    if not isinstance(d, dict):
        return default
    val = d.get(key, default)
    return default if val is None else val


def _escape_xml(text: Any) -> str:
    """Escape XML-special characters for safe use inside a reportlab
    `<para>` Paragraph cell.

    reportlab's Paragraph parses its text as a small XML/HTML
    dialect. Raw `<`, `>`, or `&` from user-supplied data (Code
    Scanning alert messages, evidence strings, repository names
    containing `&`, etc.) cause `paraparser: syntax error: parse
    ended with 1 unclosed tags` and crash the entire PDF build.

    This helper only escapes the three characters that have
    special meaning in reportlab's parser — it intentionally does
    NOT touch anything else (quotes, apostrophes) so we don't
    double-escape legitimate text. The `&` must be replaced
    first, otherwise the `&lt;` / `&gt;` we emit would be
    double-escaped.
    """
    if text is None:
        return ""
    s = str(text)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    return s
    if not isinstance(d, dict):
        return default
    val = d.get(key, default)
    return default if val is None else val


def _pct(val: Any) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val) * 100:.0f}%"
    except (ValueError, TypeError):
        return str(val)


def _yesno(val: Any) -> str:
    if val is True:
        return "Yes"
    if val is False:
        return "No"
    return "—"


def _owasp_li_cell(owasp_risk: Any) -> str:
    """Format OWASP L×I per finding for the findings table (legacy)."""
    if not isinstance(owasp_risk, dict):
        return "—"
    l = owasp_risk.get("likelihood")
    i = owasp_risk.get("impact")
    level = owasp_risk.get("risk_level", "")
    if l is None or i is None:
        return "—"
    return f"L{l}×I{i}={l*i}\n({level})"


def _normalize_finding_severity(value: Any) -> str:
    """Map arbitrary severity strings to the 4 canonical buckets.

    Mirrors the normalization used by
    `app.agents.security_finding_normalizer._normalize_severity` and
    the Run Detail `CodeScanningAlertsCard` component, so the PDF
    bucket counts (Critical/High/Medium/Low) line up exactly with
    what the user sees on the dashboard. GitHub Code Scanning uses
    `error` / `warning` / `note`; the legacy AI findings already
    store the canonical 4-bucket form, so we accept both.
    """
    if value is None:
        return "medium"
    text = str(value).lower().strip()
    if text in {"critical", "error", "errors", "failure"}:
        return "critical"
    if text in {"high", "warning", "warnings", "major"}:
        return "high"
    if text in {"medium", "moderate", "minor"}:
        return "medium"
    if text in {"low", "info", "informational", "note", "none", "notice"}:
        return "low"
    return "medium"


def _cvss_cell(finding: Any) -> str:
    """Format CVSS score per finding for the findings table.

    Renders the per-finding CVSS v3.1 base score (e.g. "9.4") and
    a short vector. Falls back to "—" when no CVSS was computed.

    The vector is abbreviated to a few key metrics so the column
    fits in 24mm without breaking. The full vector is preserved
    in the per-finding `cvss_vector` field for the JSON output
    that the dashboard consumes.

    Lookup order:
      1. Explicit `cvss_score` field on the finding (from SARIF
         when Trivy/Semgrep shipped one).
      2. `RULE_CVSS_MAP` keyed on `rule_id` (mirrors the
         frontend's `CLIENT_RULE_CVSS` table in
         `frontend/src/pages/RunDetail.tsx`).
      3. Severity-string fallback with a deterministic ±0.4
         offset keyed on `rule_id` so CRITICAL findings no longer
         all render as 9.5 (the same npm-audit critical row would
         get 9.1 the next time, etc.). This makes the per-finding
         column visually informative while still anchored to the
         industry-standard buckets (CRITICAL ≥ 9.0).
      4. "—" if none of the above resolves.
    """
    if not isinstance(finding, dict):
        return "—"
    score = _derive_cvss_score(finding)
    if score is None:
        return "—"
    return f"<b>{score:.1f}</b>"


# Per-rule CVSS lookup. Mirrors the frontend's
# `CLIENT_RULE_CVSS` table in `frontend/src/pages/RunDetail.tsx`
# so the PDF and the web dashboard render the same number.
# Rules not in the map fall back to a severity-based default
# with a small deterministic offset (see `_derive_cvss_score`).
_RULE_CVSS_MAP: dict[str, float] = {
    "tainted-sql-string": 10.0,
    "detected-stripe-api-key": 9.4,
    "hardcoded-jwt-secret": 9.1,
    "api-auth-no-rate-limit-on-login": 9.1,
    "api-ssrf-user-controlled-url": 9.1,
    "api-bola-missing-ownership-check": 8.1,
    "last-user-is-root": 7.5,
    "api-excessive-data-exposure": 6.5,
    "api-cors-wildcard-origin": 5.4,
    "api-cors-reflect-origin": 5.4,
    "api-mass-assignment-spread-body": 5.4,
    "api-no-pagination": 5.3,
    "api-no-max-body-size": 3.7,
    "api-stack-trace-exposure": 2.7,
    "ecommerce-pci-card-data-in-logs": 7.5,
    "ecommerce-pci-stripe-secret-in-source": 9.4,
    "ecommerce-pci-raw-pan-in-code": 7.5,
    "ecommerce-api-bola-cart-access": 8.1,
    "ecommerce-api-no-auth-on-checkout": 9.1,
    "ecommerce-price-tampering": 5.4,
    "ecommerce-discount-tampering": 5.4,
    "ecommerce-sqli-order-lookup": 10.0,
    "ecommerce-xss-product-render": 5.4,
    "ecommerce-csrf-no-protection": 4.7,
    "ecommerce-jwt-weak-secret": 8.1,
    "ecommerce-jwt-no-expiration": 4.4,
    "ecommerce-md5-password": 5.9,
    "ecommerce-sha1-password": 5.5,
}

# Per-type fallback (used when rule_id is unknown but type is).
_TYPE_CVSS_MAP: dict[str, float] = {
    "sql_injection": 10.0,
    "command_injection": 10.0,
    "hardcoded_secret": 9.4,
    "ssrf": 9.1,
    "path_traversal": 7.5,
    "xss": 6.1,
    "bola": 8.1,
    "idor": 8.1,
    "excessive_data_exposure": 6.5,
    "mass_assignment": 5.4,
    "insecure_deserialization": 8.1,
    "xxe": 8.1,
    "cve_vulnerability": 5.0,
    "dependency_vulnerability": 5.0,
    "security_finding": 5.0,
}

# Per-package CVSS for npm-audit / GHSA advisories. The scanner
# emits rule_id as the advisory *title* for these findings, so
# the rule_id-based lookup never matches. We instead inspect
# `package_name` (the scanner normalizer already extracts it).
# Values are NVD-published CVSS v3.1 base scores for the
# current vulnerable version range.
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
    "request": 6.5,
    "ws": 7.5,
    "ejs": 9.8,
    "pug": 7.5,
    "handlebars": 7.5,
    "mustache": 5.3,
    "marked": 5.3,
    "js-yaml": 5.3,
    "yaml": 5.3,
    "xml2js": 6.5,
    "fast-xml-parser": 6.5,
    "node-fetch": 7.5,
    "undici": 5.3,
    "cookie": 6.5,
    "cookie-parser": 6.5,
    "send": 7.5,
    "serve-static": 7.5,
    "multer": 7.5,
    "busboy": 7.5,
    "formidable": 7.5,
    "xss": 5.3,
    "dompurify": 5.3,
    "sanitize-html": 5.3,
    "@tootallnate/once": 5.3,
    "tough-cookie": 5.3,
    "http-proxy": 7.5,
    "node-http-proxy": 7.5,
    "follow-redirects": 5.3,
    "shell-quote": 7.5,
    "shelljs": 7.5,
    "cross-spawn": 5.3,
    "child_process": 7.5,
    "serialize-javascript": 7.5,
    "underscore": 5.3,
    "open": 5.3,
    "morgan": 5.3,
    "helmet": 5.3,
}

# GHSA severity suffix → CVSS. GHSA ids sometimes include the
# advisory severity as a `:CRITICAL` / `:HIGH` / etc. suffix
# (e.g. `GHSA-xxxx-xxxx-xxxx:CRITICAL`). Used as a final
# fallback when rule_id and package_name both miss.
_GHSA_SEVERITY_CVSS: dict[str, float] = {
    "critical": 9.5,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.0,
}

# Severity bucket → CVSS base (industry-standard anchors).
_SEVERITY_BASE_CVSS: dict[str, float] = {
    "critical": 9.5,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.0,
}


def _strip_semgrep_rule_id(rule: str) -> str:
    """Reduce a Semgrep rule_id to its leaf token for lookup.

    Semgrep rule_ids come in several flavors depending on the
    pack the rule came from:

      * ``github.api-bola-missing-ownership-check``
      * ``semgrep.api-excessive-data-exposure``
      * ``javascript.express.security.injection.tainted-sql-string.tainted-sql-string``
      * ``dockerfile.security.last-user-is-root.last-user-is-root``
      * ``generic.secrets.security.detected-stripe-api-key.detected-stripe-api-key``
      * ``javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret``

    Strip the language / category / product prefix segments so
    the leaf name (e.g. ``tainted-sql-string``,
    ``last-user-is-root``, ``detected-stripe-api-key``) is what
    we match against. When the leaf is duplicated (semgrep
    sometimes appends the leaf again), drop the duplicate.
    """
    if not rule:
        return rule
    parts = rule.split(".")
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        parts.pop()
    return parts[-1]


def _derive_cvss_score(finding: Any) -> float | None:
    """Resolve a CVSS v3.1 base score for a single finding.

    Returns a float in [0.0, 10.0] or ``None`` when no score can
    be derived. Used by both the PDF findings table and the
    per-finding JSON the dashboard consumes, so the two stay
    in lock-step.

    Order:
      1. Explicit ``cvss_score`` (from scanner SARIF or AI agent).
      2. ``RULE_CVSS_MAP`` lookup on the Semgrep-stripped
         ``rule_id`` leaf token.
      3. ``TYPE_CVSS_MAP`` lookup on ``type``.
      4. ``NPM_PACKAGE_CVSS`` lookup on ``package_name`` (the
         dominant signal for npm-audit / GHSA findings where
         ``rule_id`` is the advisory title, not a token).
      5. ``GHSA_SEVERITY_CVSS`` lookup on the trailing
         ``:CRITICAL|HIGH|MEDIUM|LOW`` suffix of
         ``vulnerability_id``.
      6. Severity bucket with deterministic ±0.4 offset keyed
         on rule_id (or type / package_name as a stable
         fallback) so identical findings get identical scores
         across runs.
    """
    if not isinstance(finding, dict):
        return None
    score = finding.get("cvss_score")
    if score is None:
        rule = (finding.get("rule_id") or finding.get("rule") or "").strip()
        if rule.startswith("github."):
            rule = rule[len("github."):]
        rule_leaf = _strip_semgrep_rule_id(rule)
        if rule_leaf and rule_leaf in _RULE_CVSS_MAP:
            score = _RULE_CVSS_MAP[rule_leaf]
        else:
            ftype = (finding.get("type") or "").strip()
            if ftype and ftype in _TYPE_CVSS_MAP:
                score = _TYPE_CVSS_MAP[ftype]
            else:
                pkg = (finding.get("package_name") or "").strip().lower()
                if pkg and pkg in _NPM_PACKAGE_CVSS:
                    score = _NPM_PACKAGE_CVSS[pkg]
                else:
                    vid = (finding.get("vulnerability_id") or "").strip()
                    if vid:
                        m = re.search(r":(critical|high|medium|low)\b", vid, re.IGNORECASE)
                        if m:
                            sev_tag = m.group(1).lower()
                            if sev_tag in _GHSA_SEVERITY_CVSS:
                                score = _GHSA_SEVERITY_CVSS[sev_tag]
                    if score is None:
                        sev = (finding.get("severity") or "low").lower()
                        base = _SEVERITY_BASE_CVSS.get(sev)
                        if base is None:
                            return None
                        # Deterministic ±0.4 offset keyed on rule_id
                        # (or type / package_name as a stable fallback)
                        # so the same finding does not flip between
                        # 9.5 / 9.1 / 9.7 across renders. The result
                        # still lives in the canonical bucket
                        # (CRITICAL ≥ 9.0, HIGH 7.0-8.9, MEDIUM 4.0-6.9,
                        # LOW 0.1-3.9).
                        seed = rule or ftype or pkg or vid or sev
                        offset = ((hash(seed) & 0x7) - 3) * 0.1
                        score = base + offset
    try:
        score_f = float(score)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(10.0, score_f))


def _iter_finding_rows(findings: list[dict]) -> list[list]:
    """Build a stable row representation for each finding.

    Each row is a list of strings, formatted for the reportlab
    Paragraph cell renderer. We pre-render the cells here so the
    `_build_findings_table` helper only has to assemble the
    `Table` object.

    The function accepts both the legacy `state.findings` shape
    (log-derived findings produced by the graph nodes) and the
    newer `state.code_scanning_alerts` shape produced by
    `normalize_code_scanning_alerts`. Severity is normalized
    through `_normalize_finding_severity` so the row label and
    the per-bucket counts on the section header agree.
    """
    rows: list[list] = []
    for f in findings:
        # Severity (uppercase, normalized to the 4 canonical buckets
        # so the section header and the row labels always agree).
        sev = _normalize_finding_severity(f.get("severity")).upper()
        # Type/Rule: prefer rule_id (scanner-specific), fall back to
        # the human-readable "type" (e.g. "sql_injection") and
        # finally to "title". For Code Scanning alerts the rule_id
        # is the most informative token (e.g. "tainted-sql-string").
        type_text = (
            _safe(f, "rule_id")
            or _safe(f, "type")
            or _safe(f, "title", "—")
        )
        if isinstance(type_text, str) and type_text.startswith("github."):
            type_text = type_text[len("github."):]
        # File location, with line number if available.
        file_text = _safe(f, "file", _safe(f, "file_location", "—"))
        line = f.get("line")
        if line and ":" not in str(file_text):
            file_text = f"{file_text}:{line}"
        # Truncate the file path so it fits a 30mm column at 5.5pt.
        # Long absolute paths get their middle replaced with "..."
        # so users still know roughly where the issue lives.
        if isinstance(file_text, str) and len(file_text) > 34:
            file_text = file_text[:15] + "..." + file_text[-16:]
        # CVSS column. Resolve the score once so the PDF cell
        # and the JSON payload the dashboard consumes stay in
        # sync (see `_derive_cvss_score` for the lookup order).
        cvss_score = _derive_cvss_score(f)
        cvss_text = _cvss_cell(f) if cvss_score is None else f"<b>{cvss_score:.1f}</b>"
        # Persist the derived score back on the finding so the
        # dashboard badge and any per-bucket sum stay in lock-step
        # with the PDF column.
        if isinstance(f, dict) and cvss_score is not None:
            f["cvss_score"] = cvss_score
        # Summary: prefer explanation, then evidence, then
        # description. For Code Scanning alerts `explanation` is
        # `description` (when present) or `message`; the AI log
        # findings use `explanation` / `evidence`. The order keeps
        # the longest, most useful text per finding.
        summary_text = (
            _safe(f, "explanation")
            or _safe(f, "evidence")
            or _safe(f, "description", "—")
        )
        # Truncate the summary to 180 chars (was 120) now that the
        # Summary column is wider (66mm) — the section previously
        # capped text too aggressively and hid the remediation hint
        # the dashboard also shows.
        if isinstance(summary_text, str) and len(summary_text) > 180:
            summary_text = summary_text[:180] + "…"
        rows.append([sev, type_text, file_text, cvss_text, summary_text])
    return rows


def _build_findings_table(rows: list[list], styles: dict) -> "Table":
    """Build a reportlab Table for the findings list.

    Column widths (total 170mm, matches the rest of the report):
      - Severity (22mm)  — bold, centred, "CRITICAL" fits on one line
      - Type/Rule (38mm)  — long rule names wrap to 2 lines max
      - File:Line (30mm)  — paths up to 34 chars before truncation
      - CVSS (14mm)       — score only (e.g. "9.5")
      - Summary (66mm)    — 180-char explanation before truncation

    The previous layout [30, 48, 28, 12, 52] crowded the Summary
    column at 52mm — long evidence text wrapped to 3-4 lines per
    row, pushing the table far down the page. The new layout
    reclaims 14mm for Summary (66mm total) and trims the over-wide
    Severity column to 22mm. Severity still has comfortable
    headroom for "CRITICAL" (8 chars × ~0.9mm at 5.5pt bold =
    ~7mm of glyphs, plus 15mm of padding).
    """
    if not rows:
        return Table([["(no findings)"]], colWidths=[170 * mm])
    finding_rows = [["Severity", "Type / Rule", "File : Line", "CVSS", "Summary"]]
    # Build the body rows. Severity is plain text (one line each);
    # the rest are wrapped in Paragraphs so the text reflows inside
    # the column width. Each cell is XML-escaped first because
    # user-supplied fields (rule_id, file path, evidence) can
    # contain raw `<` / `>` / `&` from Code Scanning alerts and
    # LLM output. reportlab's parser would otherwise raise
    # `paraparser: syntax error: parse ended with 1 unclosed tags`.
    # NB: the CVSS cell already contains valid reportlab markup
    # (`<b>...</b>`) from `_cvss_cell` and must NOT be escaped —
    # escaping would render the literal text `&lt;b&gt;9.5&lt;/b&gt;`
    # and overflow the 14mm column. We detect the pre-formatted
    # cell by checking for the leading `<b>` tag.
    for r in rows:
        cvss_text = r[3]
        if cvss_text.startswith("<b>"):
            cvss_para = Paragraph(cvss_text, styles["Cell"])
        else:
            cvss_para = Paragraph(_escape_xml(cvss_text), styles["Cell"])
        finding_rows.append([
            _escape_xml(r[0]),  # severity (plain text, e.g. "CRITICAL")
            Paragraph(_escape_xml(r[1]), styles["Cell"]),
            Paragraph(_escape_xml(r[2]), styles["Cell"]),
            cvss_para,
            Paragraph(_escape_xml(r[4]), styles["Cell"]),
        ])
    # Column widths (total 170mm). The new layout devotes more room
    # to the Summary column so long Code Scanning evidence doesn't
    # wrap to 4 lines and push the table off the page. The widths
    # are multiplied by `mm` because reportlab's `colWidths` are
    # in PDF points — supplying raw integers (e.g. 22) was being
    # interpreted as 22 points (≈7.8mm) instead of 22mm, which
    # squeezed the table into a 60-point-wide band and forced
    # every cell to wrap after just a few characters.
    col_widths = [22 * mm, 38 * mm, 30 * mm, 14 * mm, 66 * mm]
    table = Table(finding_rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        # Header text is uppercase + slightly bolder.
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        # Body cells: 5.5pt fits "CRITICAL" (8 chars) in 22mm with bold.
        ("FONTSIZE", (0, 1), (-1, -1), 5.5),
        ("LEADING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        # Severity column: centered + bold so it pops.
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        # CVSS column: centered (small text fits cleanly).
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
    ]))
    return table


def _risk_level(score: float) -> str:
    if score <= 25:
        return "CRITICAL"
    elif score <= 50:
        return "HIGH"
    elif score <= 75:
        return "MEDIUM"
    else:
        return "LOW"


def _kv_table(rows: list[list[str]], styles: dict) -> Table:
    """Build a simple key-value table. Accepts 2 or 3 columns:
       - 2 cols: [label, value]
       - 3 cols: [label, value, note]
    """
    label_style = ParagraphStyle("CellBold", parent=styles["Cell"], fontName="Helvetica-Bold")
    table_rows = []
    for r in rows:
        if len(r) >= 3:
            table_rows.append([
                Paragraph(_escape_xml(r[0]), label_style),
                Paragraph(_escape_xml(r[1]), styles["Cell"]),
                Paragraph(_escape_xml(r[2]), styles["Cell"]),
            ])
        else:
            table_rows.append([
                Paragraph(_escape_xml(r[0]), label_style),
                Paragraph(_escape_xml(r[1]), styles["Cell"]),
            ])
    if rows and len(rows[0]) >= 3:
        t = Table(table_rows, colWidths=[90, 250, 140])
    else:
        t = Table(table_rows, colWidths=[90, 390])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8eaf6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _drawable_to_flowable(drawing, width: float, height: float):
    """Convert a reportlab `Drawing` into a `Flowable` for platypus.

    The Drawing's intrinsic coordinate system uses bottom-left origin and
    the width/height in points. We override `wrap` to return the requested
    size and `draw` to render the drawing at the current canvas position
    (i.e. where platypus placed the flowable). The y-origin is
    bottom-up, so we translate by `height` to put the drawing top at
    the flowable's top.
    """
    from reportlab.platypus.flowables import Flowable

    class _DrawingFlowable(Flowable):
        def __init__(self, drw, w, h):
            super().__init__()
            self.drw = drw
            self.width = w
            self.height = h

        def wrap(self, _avail_w, _avail_h):
            return self.width, self.height

        def draw(self):
            canvas = self.canv
            canvas.saveState()
            # Translate so the drawing's bottom-left corner sits at the
            # flowable's bottom-left. Reportlab uses the same coordinate
            # system as the canvas, so this is a no-translate case.
            self.drw.drawOn(canvas, 0, 0)
            canvas.restoreState()

    return _DrawingFlowable(drawing, width, height)
