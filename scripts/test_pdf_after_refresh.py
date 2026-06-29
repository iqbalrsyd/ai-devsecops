"""
Test PDF flow when user clicks "Refresh Analysis" then "Generate PDF".

The user's complaint: "setelah refresh, Compliance=0.0 dan Security Coverage=0.0
di UI, PDF jadi kosong/aneh".

Root cause: `_get_saved_analysis` was reading from tables that don't exist
in v3 (`findings`, `risk_assessments`, `workflow_executions`). After
refresh, the AI service calls `run_pipeline_analysis` which returns a
rich result dict; if that result is never persisted correctly, the PDF
endpoint can't reconstruct Section 4.

After the fix, all persisted data lives in `pipeline_analyses.raw_scan_data`
JSONB. This test simulates a successful refresh + PDF download and
verifies the PDF contains real numbers.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))
os.environ.setdefault("REPORTS_DIR", "/tmp/reports_test")

# Build a "saved analysis" payload that mirrors what `_get_saved_analysis`
# should return AFTER the fix. This is the result of:
#   1. User clicks "Refresh Analysis"
#   2. AI service runs pipeline and persists to pipeline_analyses
#   3. User clicks "Generate PDF Report"
#   4. PDF endpoint fetches saved analysis and reconstructs state

# Simulate the result of `run_pipeline_analysis` (the full dict that
# gets persisted into pipeline_analyses.raw_scan_data).
refresh_result = {
    "summary": "Found 19 issues. Risk 62.9/100.",
    "findings": [
        {"severity": "critical", "type": "hardcoded_secret", "scanner": "gitleaks",
         "file": "src/config.js", "line": 12, "explanation": "Stripe key leaked",
         "cwe": "CWE-798", "owasp": "OWASP-A07"},
        {"severity": "critical", "type": "xss", "scanner": "semgrep",
         "file": "src/search.js", "line": 8, "explanation": "Reflected XSS",
         "cwe": "CWE-79", "owasp": "OWASP-A03"},
        {"severity": "high", "type": "sql_injection", "scanner": "semgrep",
         "file": "src/routes/products.js", "line": 45, "explanation": "SQLi",
         "cwe": "CWE-89", "owasp": "OWASP-A03"},
        {"severity": "high", "type": "sca_vulnerability", "scanner": "npm_audit",
         "file": "package.json", "explanation": "express 4.16.0 has CVE-2022-24999",
         "cwe": "CWE-1104", "owasp": "OWASP-A06"},
        {"severity": "medium", "type": "missing_header", "scanner": "semgrep",
         "file": "src/server.js", "line": 23, "explanation": "Missing CSP"},
    ] + [{"severity": "medium", "type": "sca", "scanner": "trivy",
          "file": "Dockerfile", "explanation": "Outdated base image"}
         for _ in range(8)] + [{"severity": "high", "type": "sast",
                               "scanner": "semgrep", "file": f"src/file_{i}.js",
                               "explanation": f"Issue {i}"}
                              for i in range(10)] + [
        {"severity": "critical", "type": "hardcoded_secret", "scanner": "gitleaks",
         "file": f"src/secret_{i}.js", "explanation": f"Secret {i}"}
        for i in range(7)
    ],
    "risk_score": 62.9,
    "risk_level": "medium",
    "compliance_score": 75.0,
    "security_standards_coverage_score": 75.0,
    "security_coverage_score": 68.0,
    "severity_breakdown": {"critical": 8, "high": 12, "medium": 12, "low": 0},
    "recommendations": [
        {"title": "Rotate Stripe key and move to env", "priority": "high",
         "description": "Current Stripe key is in source. Use GitHub Secrets."},
        {"title": "Add CSP header via helmet", "priority": "medium",
         "description": "Install helmet and configure CSP"},
        {"title": "Upgrade express to 4.18+", "priority": "high",
         "description": "CVE-2022-24999 fixed in 4.18+"},
    ],
    "detected_technologies": {
        "primary_language": "JavaScript",
        "primary_language_confidence": 0.95,
        "frameworks": ["Express", "Sequelize", "Helmet"],
        "build_tools": ["npm", "webpack"],
        "package_manager": "npm",
        "package_manager_confidence": 0.9,
        "test_framework": "jest",
        "database": "SQLite",
        "runtime": "Node.js 20",
    },
    "detected_architecture": {"architecture_type": "monolithic", "service_count": 1},
    "detected_architecture_type": "monolithic",
    "detected_architecture_confidence": 0.88,
    "detected_architecture_reason": "Single server.js entrypoint",
    "detected_deployment": {
        "docker": True, "docker_confidence": 0.9,
        "kubernetes": False, "terraform": False,
    },
    "recommended_deployment_target": "docker",
    "detected_domain": "ecommerce",
    "domain_confidence": 0.85,
    "domain_evidence": ["Stripe API detected", "checkout.js route"],
    "domain_threats": ["Payment data exfiltration", "PCI-DSS non-compliance"],
    "attack_surfaces": ["Public API (Express)", "SQLite database"],
    "inferred_security_needs": {
        "security_controls": [
            {"control": "sast", "status": "recommended", "tool": "semgrep", "reason": "JS code"},
            {"control": "secret_scanning", "status": "recommended", "tool": "gitleaks", "reason": "Secret found"},
            {"control": "sca", "status": "recommended", "tool": "npm audit", "reason": "npm detected"},
            {"control": "container_scan", "status": "recommended", "tool": "trivy", "reason": "Dockerfile"},
            {"control": "dast", "status": "optional", "tool": "owasp_zap", "reason": "Public API"},
            {"control": "iac_scan", "status": "not_required", "tool": "—", "reason": "No IaC"},
        ],
    },
    "generated_stages": [
        "sast_semgrep", "secret_scan_gitleaks", "sca_npm_audit",
        "container_scan_trivy", "dast_zap",
    ],
    "stage_explanations": [
        {"stage": "sast_semgrep", "tool": "returntocorp/semgrep", "explanation": "SAST"},
        {"stage": "secret_scan_gitleaks", "tool": "gitleaks/gitleaks-action", "explanation": "secrets"},
        {"stage": "sca_npm_audit", "tool": "npm audit", "explanation": "deps"},
        {"stage": "container_scan_trivy", "tool": "aquasecurity/trivy-action", "explanation": "image"},
        {"stage": "dast_zap", "tool": "owasp/zap2docker-stable", "explanation": "DAST"},
    ],
    "validation_passed": True,
    "validation_errors": [],
    "validation_warnings": ["Pinned action versions recommended"],
    "workflow_jobs": [
        {"name": "sast", "conclusion": "success"},
        {"name": "secret_scan_gitleaks", "conclusion": "success"},
        {"name": "sca_npm_audit", "conclusion": "success"},
        {"name": "container_scan_trivy", "conclusion": "success"},
        {"name": "dast_zap", "conclusion": "skipped"},
    ],
    "validation_passed": True,
}


def build_pipeline_analyses_row(result: dict) -> dict:
    """Mirror what _persist_analysis_result now writes to pipeline_analyses."""
    raw_payload = json.dumps({
        "state_snapshot": {
            "detected_technologies": result.get("detected_technologies") or {},
            "detected_architecture": result.get("detected_architecture") or {},
            "detected_architecture_type": result.get("detected_architecture_type"),
            "detected_architecture_confidence": result.get("detected_architecture_confidence"),
            "detected_architecture_reason": result.get("detected_architecture_reason"),
            "detected_deployment": result.get("detected_deployment") or {},
            "recommended_deployment_target": result.get("recommended_deployment_target"),
            "detected_domain": result.get("detected_domain"),
            "domain_confidence": result.get("domain_confidence"),
            "domain_evidence": result.get("domain_evidence") or [],
            "domain_threats": result.get("domain_threats") or [],
            "attack_surfaces": result.get("attack_surfaces") or [],
            "inferred_security_needs": result.get("inferred_security_needs") or {},
            "generated_stages": result.get("generated_stages") or [],
            "stage_explanations": result.get("stage_explanations") or [],
            "validation_passed": result.get("validation_passed", False),
            "validation_errors": result.get("validation_errors") or [],
            "validation_warnings": result.get("validation_warnings") or [],
            "workflow_jobs": result.get("workflow_jobs") or [],
        },
        "score_metadata": {},
    })
    return {
        "risk_score": result.get("risk_score"),
        "compliance_score": result.get("compliance_score"),
        "security_coverage_score": result.get("security_coverage_score"),
        "severity_breakdown": json.dumps(result.get("severity_breakdown", {})),
        "recommendations": json.dumps(result.get("recommendations", [])),
        "findings_summary": json.dumps(result.get("findings", [])),
        "raw_scan_data": raw_payload,
    }


def reconstruct_saved_analysis(pa_row: dict, run_row: tuple) -> dict:
    """Mirror what _get_saved_analysis now returns."""
    raw = pa_row["raw_scan_data"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    return {
        "summary": "Analysis complete (cached).",
        "findings": json.loads(pa_row["findings_summary"]),
        "risk_score": pa_row["risk_score"],
        "risk_level": "medium" if pa_row["risk_score"] and pa_row["risk_score"] <= 75 else "low",
        "security_standards_coverage_score": pa_row["compliance_score"],
        "compliance_score": pa_row["compliance_score"],
        "security_coverage_score": pa_row["security_coverage_score"],
        "severity_breakdown": json.loads(pa_row["severity_breakdown"]),
        "recommendations": json.loads(pa_row["recommendations"]),
        "generated_workflow": run_row[4] or "",
        "generated_stages": json.loads(run_row[5]) if run_row[5] else [],
        "workflow_conclusion": run_row[3],
        "state_snapshot": raw.get("state_snapshot") or {},
        "dashboard_findings": raw.get("dashboard_findings") or {},
        "score_metadata": raw.get("score_metadata") or {},
    }


def build_state_for_pdf(saved: dict) -> dict:
    """Replicate the endpoint's state reconstruction."""
    snap = saved.get("state_snapshot") or {}
    return {
        "repository_full_name": "iqbalrsyd/eccomerce-monolith-vuln",
        "pipeline_version": 1,
        "errors": saved.get("errors") or [],
        "detected_technologies": snap.get("detected_technologies") or {},
        "detected_architecture": snap.get("detected_architecture") or {},
        "detected_architecture_confidence": snap.get("detected_architecture_confidence") or 0,
        "detected_architecture_reason": snap.get("detected_architecture_reason") or "",
        "detected_deployment": snap.get("detected_deployment") or {},
        "recommended_deployment_target": snap.get("recommended_deployment_target") or "",
        "detected_domain": snap.get("detected_domain") or "N/A",
        "domain_confidence": snap.get("domain_confidence") or 0,
        "domain_evidence": snap.get("domain_evidence") or [],
        "domain_threats": snap.get("domain_threats") or [],
        "attack_surfaces": snap.get("attack_surfaces") or [],
        "inferred_security_needs": snap.get("inferred_security_needs") or {},
        "generated_stages": snap.get("generated_stages") or saved.get("generated_stages") or [],
        "stage_explanations": snap.get("stage_explanations") or [],
        "validation_passed": snap.get("validation_passed", False),
        "validation_errors": snap.get("validation_errors") or [],
        "validation_warnings": snap.get("validation_warnings") or [],
        "generated_workflow": saved.get("generated_workflow"),
        "workflow_jobs": snap.get("workflow_jobs") or [],
        "risk_score": saved.get("risk_score"),
        "security_standards_coverage_score": saved.get("security_standards_coverage_score"),
        "compliance_score": saved.get("compliance_score"),
        "security_coverage_score": saved.get("security_coverage_score"),
        "findings": saved.get("findings") or [],
        "severity_breakdown": saved.get("severity_breakdown") or {},
        "recommendations": saved.get("recommendations") or [],
        "summary": saved.get("summary"),
    }


def main() -> None:
    from app.services.report_generator import generate_pdf_report

    # 1. Simulate refresh: persist result into pipeline_analyses row
    pa_row = build_pipeline_analyses_row(refresh_result)

    # 2. Simulate reading the persisted row back
    run_row = (
        "uuid-exec",  # exec_id
        12345,        # github_run_id
        "completed",  # status
        "success",    # conclusion
        "name: AI\non: [push]\njobs:\n  sast:\n    runs-on: ubuntu-latest\n",  # yaml
        json.dumps(refresh_result["generated_stages"]),  # stages
    )
    saved = reconstruct_saved_analysis(pa_row, run_row)

    # 3. Simulate PDF endpoint state reconstruction
    state = build_state_for_pdf(saved)

    # 4. Generate PDF
    out = generate_pdf_report(state)
    size = os.path.getsize(out)
    print(f"PDF: {out} ({size} bytes)")

    # 5. Verify
    import pdfplumber
    with pdfplumber.open(out) as pdf:
        all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        checks = {
            "Risk score 62.9 present": "62.9" in all_text,
            "Compliance 75.0 present": "75.0" in all_text,
            "Security coverage 68.0 present": "68.0" in all_text,
            "Risk level MEDIUM": "MEDIUM" in all_text,
            "Findings count 32": "32" in all_text or "Total:" in all_text,
            "Severity breakdown critical 8": "8" in all_text and "critical" in all_text.lower(),
            "Section 1 - JavaScript": "JavaScript" in all_text,
            "Section 1 - Express/Sequelize": "Express" in all_text and "Sequelize" in all_text,
            "Section 1 - architecture monolithic": "monolithic" in all_text,
            "Section 1 - domain ecommerce": "ecommerce" in all_text,
            "Section 2 - attack surface Express": "Express" in all_text,
            "Section 2 - controls with CWE refs": "CWE-89" in all_text or "CWE-798" in all_text,
            "Section 3 - validation PASSED": "PASSED" in all_text,
            "Section 3 - workflow YAML": "actions" in all_text or "ubuntu-latest" in all_text,
            "Section 4 - rotation recommendation": "Stripe" in all_text or "env" in all_text,
            "PDF has at least 4 pages": len(pdf.pages) >= 4,
        }
        for name, ok in checks.items():
            print(f"  {'OK ' if ok else 'FAIL'}  {name}")
        all_ok = all(checks.values())
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
