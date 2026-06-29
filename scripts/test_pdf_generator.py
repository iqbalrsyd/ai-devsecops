"""
Smoke test for the report generator with the new charts.

Runs the full pipeline (without actually invoking the AI service):
    - Builds a representative state dict (mirroring the run-time shape)
    - Calls `generate_pdf_report` directly
    - Verifies the PDF is non-empty and has the expected number of pages

This avoids needing a live DB or AI service.
"""

import os
import sys

# Make the ai-service importable without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))

# Pretend the repo's REPORTS_DIR is /tmp so we can find the file easily
os.environ.setdefault("REPORTS_DIR", "/tmp/reports_test")

from app.services.report_generator import generate_pdf_report  # noqa: E402


def main() -> None:
    state = {
        "repository_full_name": "iqbalrsyd/eccomerce-monolith-vuln",
        "pipeline_version": 2,
        "errors": [],
        "detected_architecture": {
            "architecture_type": "monolithic",
            "service_count": 1,
        },
        "detected_domain": "ecommerce",
        "detected_technologies": {
            "primary_language": "JavaScript",
            "primary_language_confidence": 0.95,
            "frameworks": ["Express", "Sequelize"],
            "build_tools": ["npm", "webpack"],
            "package_manager": "npm",
            "package_manager_confidence": 0.92,
            "test_framework": "jest",
            "database": "SQLite",
            "runtime": "Node.js 20",
        },
        "detected_architecture_confidence": 0.88,
        "detected_architecture_reason": "Single service entrypoint (server.js); no docker-compose services.",
        "detected_deployment": {
            "docker": True,
            "docker_confidence": 0.9,
            "docker_compose": False,
            "kubernetes": False,
            "terraform": False,
            "helm": False,
            "cloud_provider": None,
        },
        "recommended_deployment_target": "docker",
        "domain_confidence": 0.85,
        "domain_evidence": ["package.json contains stripe", "src/routes/checkout.js"],
        "domain_threats": ["Payment data exfiltration", "Cart manipulation"],
        "attack_surfaces": ["Public API (Express)", "Database (SQLite)"],
        "inferred_security_needs": {
            "security_controls": [
                {"control": "sast", "status": "recommended", "tool": "semgrep", "tool_version": "latest", "reason": "Detected JavaScript/Express codebase"},
                {"control": "sca", "status": "recommended", "tool": "npm audit", "tool_version": "latest", "reason": "npm package manager detected"},
                {"control": "secret_scanning", "status": "recommended", "tool": "gitleaks", "tool_version": "latest", "reason": "Detected hardcoded secret (Stripe key)"},
                {"control": "container_scan", "status": "recommended", "tool": "trivy", "tool_version": "latest", "reason": "Dockerfile detected"},
                {"control": "dast", "status": "optional", "tool": "owasp_zap", "tool_version": "latest", "reason": "Public API present"},
                {"control": "iac_scan", "status": "not_required", "tool": "—", "tool_version": "latest", "reason": "No Terraform/IaC detected"},
            ],
        },
        "generated_stages": [
            "sast_semgrep",
            "secret_scan_gitleaks",
            "sca_npm_audit",
            "container_scan_trivy",
        ],
        "stage_explanations": [
            {"stage": "sast_semgrep", "tool": "returntocorp/semgrep", "explanation": "Static analysis with custom rules"},
            {"stage": "secret_scan_gitleaks", "tool": "gitleaks/gitleaks-action", "explanation": "Detect hardcoded secrets"},
            {"stage": "sca_npm_audit", "tool": "npm audit", "explanation": "Scan npm dependencies for known CVEs"},
            {"stage": "container_scan_trivy", "tool": "aquasecurity/trivy-action", "explanation": "Scan container image for CVEs"},
        ],
        "validation_passed": True,
        "validation_errors": [],
        "validation_warnings": ["Pinned action versions recommended"],
        "generated_workflow": """name: AI DevSecOps
on: [push]
jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: semgrep ci
""",
        "risk_score": 72.5,
        "security_standards_coverage_score": 78.0,
        "compliance_score": 78.0,
        "security_coverage_score": 65.0,
        "findings": [
            {"severity": "high", "type": "hardcoded_secret", "title": "Stripe key leaked", "file": "src/config.js", "line": 12, "explanation": "Hardcoded Stripe live key committed", "scanner": "gitleaks"},
            {"severity": "medium", "type": "sql_injection", "title": "SQLi in /products", "file": "src/routes/products.js", "line": 45, "explanation": "User input concatenated into raw SQL", "scanner": "semgrep"},
            {"severity": "low", "type": "missing_header", "title": "Missing CSP header", "file": "src/server.js", "line": 23, "explanation": "Response missing Content-Security-Policy", "scanner": "semgrep"},
            {"severity": "critical", "type": "xss", "title": "Reflected XSS", "file": "src/routes/search.js", "line": 8, "explanation": "User input reflected without escaping", "scanner": "semgrep"},
        ],
        "severity_breakdown": {"critical": 1, "high": 1, "medium": 1, "low": 1},
        "recommendations": [
            {"recommendation": "Move Stripe key to GitHub Secrets and reference via ${{ secrets.STRIPE_KEY }}", "priority": "high"},
            {"recommendation": "Use parameterized queries (Sequelize) instead of raw SQL", "priority": "high"},
            {"recommendation": "Add helmet middleware to set security headers including CSP", "priority": "medium"},
        ],
        "summary": "Found 4 security issues. Risk score: 72.5/100 (low) [OWASP Risk Rating]. Security standards coverage: 78.0% [OWASP CI/CD, OWASP Top 10, CIS]. Security coverage: 65.0% [OWASP CI/CD Controls]. Generated 3 recommendation(s).",
    }

    out = generate_pdf_report(state)
    size = os.path.getsize(out)
    print(f"PDF generated: {out} ({size} bytes)")
    assert size > 5000, "PDF too small, likely empty"
    # crude page-count check
    with open(out, "rb") as f:
        data = f.read()
    pages = data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type/Page")
    print(f"Approx page count markers: {pages}")
    assert pages >= 4, f"Expected at least 4 pages (1 per section), got {pages}"


if __name__ == "__main__":
    main()
