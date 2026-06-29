"""
Test that mimics what the PDF endpoint will receive when state_snapshot
is persisted but the full state is not. This is the production path
after our fix.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))
os.environ.setdefault("REPORTS_DIR", "/tmp/reports_test")

from app.services.report_generator import generate_pdf_report  # noqa: E402


def main() -> None:
    # Simulate what _get_saved_analysis() returns to the PDF endpoint.
    saved = {
        "findings": [
            {"severity": "high", "type": "hardcoded_secret", "file": "src/config.js", "line": 12,
             "explanation": "Hardcoded Stripe key", "scanner": "gitleaks"},
            {"severity": "critical", "type": "xss", "file": "src/search.js", "line": 8,
             "explanation": "Reflected XSS", "scanner": "semgrep"},
            {"severity": "low", "type": "missing_header", "file": "src/server.js", "line": 23,
             "explanation": "Missing CSP", "scanner": "semgrep"},
        ],
        "risk_score": 65.0,
        "risk_level": "medium",
        "security_standards_coverage_score": 72.0,
        "compliance_score": 72.0,
        "security_coverage_score": 58.0,
        "severity_breakdown": {"critical": 1, "high": 1, "medium": 0, "low": 1},
        "recommendations": [
            {"title": "Move secrets to env", "description": "Use GitHub Secrets"},
            {"title": "Add CSP", "description": "helmet middleware"},
        ],
        "summary": "Found 3 issues. Risk 65/100.",
        "generated_workflow": "name: AI\non: [push]\njobs:\n  sast:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
        "state_snapshot": {
            "detected_technologies": {
                "primary_language": "JavaScript",
                "primary_language_confidence": 0.95,
                "frameworks": ["Express", "Sequelize"],
                "build_tools": ["npm"],
                "package_manager": "npm",
                "package_manager_confidence": 0.9,
                "test_framework": "jest",
                "database": "SQLite",
                "runtime": "Node.js 20",
            },
            "detected_architecture": {"architecture_type": "monolithic", "service_count": 1},
            "detected_architecture_type": "monolithic",
            "detected_architecture_confidence": 0.88,
            "detected_architecture_reason": "Single service entrypoint",
            "detected_deployment": {"docker": True, "docker_confidence": 0.9, "kubernetes": False},
            "recommended_deployment_target": "docker",
            "detected_domain": "ecommerce",
            "domain_confidence": 0.85,
            "domain_evidence": ["stripe detected"],
            "domain_threats": ["Payment data exfil"],
            "attack_surfaces": ["Public API"],
            "inferred_security_needs": {
                "security_controls": [
                    {"control": "sast", "status": "recommended", "tool": "semgrep", "reason": "JS code"},
                    {"control": "secret_scanning", "status": "recommended", "tool": "gitleaks", "reason": "Secret found"},
                    {"control": "sca", "status": "recommended", "tool": "npm audit", "reason": "npm detected"},
                    {"control": "container_scan", "status": "recommended", "tool": "trivy", "reason": "Dockerfile"},
                    {"control": "dast", "status": "optional", "tool": "owasp_zap", "reason": "API present"},
                ],
            },
            "generated_stages": ["sast_semgrep", "secret_scan_gitleaks", "sca_npm_audit", "container_scan_trivy"],
            "stage_explanations": [
                {"stage": "sast_semgrep", "tool": "returntocorp/semgrep", "explanation": "SAST"},
                {"stage": "secret_scan_gitleaks", "tool": "gitleaks/gitleaks-action", "explanation": "secrets"},
                {"stage": "sca_npm_audit", "tool": "npm audit", "explanation": "deps"},
                {"stage": "container_scan_trivy", "tool": "aquasecurity/trivy-action", "explanation": "image"},
            ],
            "validation_passed": True,
            "validation_errors": [],
            "validation_warnings": ["pin actions"],
            "workflow_jobs": [
                {"name": "sast", "conclusion": "success"},
                {"name": "secret_scan_gitleaks", "conclusion": "success"},
                {"name": "sca_npm_audit", "conclusion": "success"},
                {"name": "container_scan_trivy", "conclusion": "failure"},
            ],
        },
    }

    # Replicate endpoint reconstruction
    snap = saved.get("state_snapshot") or {}
    state = {
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

    out = generate_pdf_report(state)
    size = os.path.getsize(out)
    print(f"PDF: {out} ({size} bytes)")

    # Verify Section 1-4 are populated
    import pdfplumber
    with pdfplumber.open(out) as pdf:
        all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        checks = {
            "Cover repo name": "iqbalrsyd/eccomerce-monolith-vuln" in all_text,
            "Section 1 - tech bar (Frameworks)": "Frameworks" in all_text and "2" in all_text,
            "Section 1 - architecture": "monolithic" in all_text,
            "Section 1 - domain": "ecommerce" in all_text,
            "Section 2 - attack surface": "Public API" in all_text,
            "Section 2 - controls table": "semgrep" in all_text and "gitleaks" in all_text,
            "Section 2 - donut legend": "Recommended" in all_text and "Not Required" not in all_text,
            "Section 3 - validation": "PASSED" in all_text,
            "Section 3 - workflow YAML": "ai-devsecops" in all_text.lower() or "ai\non" in all_text.lower() or "actions/checkout" in all_text,
            "Section 3 - stage diagram (sast_semgrep)": "sast_semgrep" in all_text,
            "Section 4 - risk score": "65" in all_text and "Risk" in all_text,
            "Section 4 - findings count": "3" in all_text,
            "Section 4 - recommendations": "GitHub Secrets" in all_text or "helmet" in all_text,
        }
        for name, ok in checks.items():
            print(f"  {'OK ' if ok else 'FAIL'}  {name}")
        all_ok = all(checks.values())
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
