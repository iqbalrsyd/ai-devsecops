"""
Smoke test for the PDF report generator with realistic data.

Builds a state dict that mirrors what RunDetail sends in production
(54 Code Scanning alerts: 35 critical + 19 high, mixed Semgrep /
NPM Audit / Gitleaks). Calls `generate_pdf_report` and writes the
PDF to /tmp/reports_test/.

This is what the user actually sees in the dashboard; the script
exercises every section of the report (cover, context, security
coverage, pipeline, evaluation, coverages applied, findings by
scanner).
"""

import os
import sys
from datetime import datetime, timezone

# Make the ai-service importable without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))

os.environ.setdefault("REPORTS_DIR", "/tmp/reports_test")

from app.services.report_generator import generate_pdf_report  # noqa: E402


def build_state() -> dict:
    """Build a representative state dict that mirrors the real
    Code Scanning output for `iqbalrsyd/eccomerce-monolith-vuln`.

    Produces:
      - 35 critical findings (3 Semgrep + 30 NPM Audit + 2 Semgrep
        tainted-sql + 1 dockerfile)
      - 19 high findings (3 Gitleaks + 7 NPM Audit + 9 Semgrep
        excessive-data-exposure)
      - 6 applicable security coverages with reasons
      - 6 pipeline augmentations
    """
    repo = "iqbalrsyd/eccomerce-monolith-vuln"

    # ------------------------------------------------------------------
    # 1. Findings: same shape the AI service emits. Every finding has
    #    a `rule_id`, `severity`, `file_location`, and (where
    #    applicable) a `package_name` so the lookup-based CVSS
    #    resolver can map it to a per-rule or per-package score.
    # ------------------------------------------------------------------
    findings: list[dict] = []

    def push(sev: str, rule: str, file_: str, line: int, summary: str,
             package: str | None = None, vuln_id: str | None = None,
             title: str | None = None) -> None:
        item: dict = {
            "severity": sev,
            "rule_id": rule,
            "type": rule,
            "title": title or rule,
            "file_location": file_,
            "file": file_,
            "line": line,
            "evidence": summary,
            "explanation": summary,
            "scanner": _scanner_for(rule, package),
            "scanner_version": "v1.99.0",
        }
        if package:
            item["package_name"] = package
        if vuln_id:
            item["vulnerability_id"] = vuln_id
        findings.append(item)

    def _scanner_for(rule: str, pkg: str | None) -> str:
        if pkg:
            return "NPM Audit"
        if rule.startswith("github.") or rule.startswith("javascript.") \
                or rule.startswith("dockerfile.") or rule.startswith("generic.") \
                or rule.startswith("semgrep."):
            return "Semgrep OSS"
        return "Gitleaks"

    # Critical (35) ---------------------------------------------------------
    for f, l in [
        ("/src/src/routes/products.js", 11),
        ("/src/src/routes/products.js", 26),
        ("/src/src/routes/products.js", 16),
        ("/src/src/routes/products.js", 8),
    ]:
        push("critical", "github.api-bola-missing-ownership-check", f, l,
             "BOLA: ownership not checked on /products/:id")
    for f, l in [
        ("/src/src/server.js", 19),
    ]:
        push("critical", "github.api-cors-wildcard-origin", f, l,
             "CORS wildcard origin")
    for f, l in [
        ("/src/src/routes/auth.js", 38),
    ]:
        push("critical", "github.api-excessive-data-exposure", f, l,
             "Auth response leaks internal fields")
    for title in [
        "node-tar applies PAX size override to intermediary GNU long-name headers",
        "Race Condition in node-tar Path Reservations via Unicode Ligature Collisions",
        "node-tar Symlink Path Traversal via Drive-Relative Linkpath",
        "tar has Hardlink Path Traversal via Drive-Relative Linkpath",
        "Arbitrary File Read/Write via Hardlink Target Escape in node-tar",
        "node-tar vulnerable to Arbitrary File Overwrite and Symlink Poisoning",
        "node-tar vulnerable to Arbitrary File Creation/Overwrite via Hardlink Path Traversal",
    ]:
        push("critical", title, "package.json", 1, title, package="node-tar",
             vuln_id="GHSA-xxxx:CRITICAL")
    for title in [
        "qs's arrayLimit bypass allows DoS via memory exhaustion",
        "qs vulnerable to Prototype Pollution",
    ]:
        push("critical", title, "package.json", 1, title, package="qs",
             vuln_id="GHSA-yyyy:CRITICAL")
    for title in [
        "path-to-regexp vulnerable to ReDoS via multiple route parameters",
        "path-to-regexp contains a ReDoS",
        "path-to-regexp outputs backtracking regular expressions",
    ]:
        push("critical", title, "package.json", 1, title, package="path-to-regexp",
             vuln_id="GHSA-zzzz:CRITICAL")
    for title in [
        "Lodash Prototype Pollution in _.unset and _.omit",
        "lodash Prototype Pollution via array path bypass",
        "lodash Code Injection via _.template",
        "ReDoS in lodash",
        "Command Injection in lodash",
        "Prototype Pollution in lodash",
    ]:
        push("critical", title, "package.json", 1, title, package="lodash",
             vuln_id="GHSA-aaaa:CRITICAL")
    for title in [
        "jsonwebtoken signature validation bypass due to insecure default algorithm",
        "jsonwebtoken insecure key retrieval could lead to Forgeable Tokens",
        "jsonwebtoken unrestricted key type could lead to legacy keys usage",
    ]:
        push("critical", title, "package.json", 1, title, package="jsonwebtoken",
             vuln_id="GHSA-bbbb:CRITICAL")
    push("critical", "Express.js Open Redirect in malformed URLs", "package.json", 1,
         "Express.js Open Redirect in malformed URLs", package="express",
         vuln_id="GHSA-cccc:CRITICAL")
    push("critical", "express vulnerable to XSS via response.redirect()", "package.json", 1,
         "express vulnerable to XSS via response.redirect()", package="express",
         vuln_id="GHSA-dddd:CRITICAL")
    push("critical", "body-parser vulnerable to DoS when url encoding is enabled",
         "package.json", 1, "body-parser DoS via url encoding", package="body-parser",
         vuln_id="GHSA-eeee:CRITICAL")
    push("critical", "semgrep.ecommerce-pci-stripe-secret-in-source",
         "/src/src/routes/checkout.js", 7, "Stripe secret committed to source",
         title="ecommerce-pci-stripe-secret-in-source")
    for f, l in [
        ("/src/src/routes/orders.js", 10),
        ("/src/src/routes/checkout.js", 26),
        ("/src/src/routes/checkout.js", 16),
        ("/src/src/routes/auth.js", 26),
    ]:
        push("critical",
             "javascript.express.security.injection.tainted-sql-string.tainted-sql-string",
             f, l, "Tainted SQL string in /src/...")
    push("critical",
         "generic.secrets.security.detected-stripe-api-key.detected-stripe-api-key",
         "/src/src/routes/checkout.js", 7, "Stripe API key committed to source")
    push("critical",
         "dockerfile.security.last-user-is-root.last-user-is-root",
         "/src/Dockerfile", 12, "Dockerfile runs as root")

    # High (19) -------------------------------------------------------------
    push("high", "generic-api-key", ".env", 8,
         "Generic API key committed", vuln_id="GITLEAKS-1")
    for f, l in [(".env", 7), ("src/routes/checkout.js", 7)]:
        push("high", "stripe-access-token", f, l,
             "Stripe access token committed", vuln_id="GITLEAKS-2")
    for title in [
        "serve-static vulnerable to template injection that can lead to XSS",
        "send vulnerable to template injection that can lead to XSS",
    ]:
        push("high", title, "package.json", 1, title, package=title.split()[0],
             vuln_id="GHSA-ffff:HIGH")
    push("high", "JS-YAML Quadratic-complexity DoS in merge key handling via repeated aliases",
         "package.json", 1, "JS-YAML DoS", package="js-yaml",
         vuln_id="GHSA-gggg:HIGH")
    push("high", "cookie accepts cookie name, path, and domain with out of bounds characters",
         "package.json", 1, "cookie out of bounds", package="cookie",
         vuln_id="GHSA-hhhh:HIGH")
    push("high", "@tootallnate/once vulnerable to Incorrect Control Flow Scoping",
         "package.json", 1, "@tootallnate/once", package="@tootallnate/once",
         vuln_id="GHSA-iiii:HIGH")
    for f, l in [
        ("/src/src/server.js", 35),
        ("/src/src/routes/products.js", 26),
        ("/src/src/routes/products.js", 16),
        ("/src/src/routes/products.js", 8),
        ("/src/src/routes/orders.js", 13),
        ("/src/src/routes/checkout.js", 32),
        ("/src/src/routes/auth.js", 38),
        ("/src/src/routes/auth.js", 19),
    ]:
        push("high", "semgrep.api-excessive-data-exposure", f, l,
             "API response leaks internal fields")
    push("high", "semgrep.ecommerce-jwt-no-expiration", "/src/src/routes/auth.js", 33,
         "JWT has no expiration")
    push("high", "semgrep.api-auth-no-rate-limit-on-login", "/src/src/routes/auth.js", 22,
         "Login endpoint has no rate limit")
    push("high", "javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret",
         "/src/src/routes/auth.js", 33, "Hardcoded JWT secret in source")

    # ------------------------------------------------------------------
    # 2. Security coverages (15-library), with reasons + job per row
    # ------------------------------------------------------------------
    applicable_coverages = [
        {"id": "authentication_security", "reason": "Detected user login / JWT in /src/src/routes/auth.js"},
        {"id": "injection_defense", "reason": "Detected SQLi / tainted-sql-string findings"},
        {"id": "secrets_management", "reason": "Hardcoded Stripe API key + generic API key found"},
        {"id": "dependency_security", "reason": "package.json has 14+ vulnerable transitive deps"},
        {"id": "container_security", "reason": "Dockerfile detected, runs as root"},
        {"id": "cors_hardening", "reason": "CORS wildcard origin in /src/src/server.js"},
    ]

    # ------------------------------------------------------------------
    # 3. Pipeline augmentations
    # ------------------------------------------------------------------
    pipeline_augmentations = [
        {"coverage": "secrets_management", "job": "secret_scan",
         "configuration": "p/secrets"},
        {"coverage": "injection_defense", "job": "sast",
         "configuration": "p/sql-injection"},
        {"coverage": "dependency_security", "job": "sca",
         "configuration": "pci-dss.yml"},
        {"coverage": "container_security", "job": "container_scan",
         "configuration": "p/owasp-top-ten"},
        {"coverage": "cors_hardening", "job": "sast",
         "configuration": "trivy image"},
        {"coverage": "authentication_security", "job": "sast",
         "configuration": "npm audit"},
    ]

    # ------------------------------------------------------------------
    # 4. State dict (mirrors what RunDetail sends to /runs/{id}/pdf)
    # ------------------------------------------------------------------
    state = {
        "repository_full_name": repo,
        "run_id": "28082208138",
        "repository_description": "E-commerce monolith demo (intentionally vulnerable)",
        "pipeline_version": 2,
        "errors": [],
        "detected_architecture": {
            "architecture_type": "monolithic",
            "service_count": 1,
        },
        "detected_architecture_type": "monolithic",
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
        "detected_domain": "ecommerce",
        "domain_sub_type": "monolith",
        "domain_confidence": 0.88,
        "domain_evidence": ["package.json contains stripe", "src/routes/checkout.js"],
        "domain_threats": ["Payment data exfiltration", "Cart manipulation", "Account takeover"],
        "attack_surfaces": ["Public API (Express)", "Database (SQLite)", "Static .env files"],
        "inferred_security_needs": {
            "security_controls": [
                {"control": "sast", "status": "recommended", "tool": "semgrep", "reason": "Detected JavaScript/Express codebase"},
                {"control": "sca", "status": "recommended", "tool": "npm audit", "reason": "npm package manager detected"},
                {"control": "secret_scanning", "status": "recommended", "tool": "gitleaks", "reason": "Detected hardcoded secret (Stripe key)"},
                {"control": "container_scan", "status": "recommended", "tool": "trivy", "reason": "Dockerfile detected"},
                {"control": "dast", "status": "optional", "tool": "owasp_zap", "reason": "Public API present"},
                {"control": "iac_scan", "status": "not_required", "tool": "—", "reason": "No Terraform/IaC detected"},
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
  secret_scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: gitleaks detect --source .
  sca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm audit --audit-level=high
  container_scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: trivy image myorg/myapp:latest
""",
        # CVSS risk (the new metric, replaced the old 0-100 OWASP score)
        "risk_score": 458.3,
        "risk_level": "critical",
        "security_posture": "vulnerable",
        "compliance_score": 22.0,
        "security_coverage_score": 65.0,
        "security_coverages": applicable_coverages,
        "pipeline_augmentations": pipeline_augmentations,
        # Findings (Code Scanning alerts). 35 crit + 19 high = 54.
        "findings": findings,
        "code_scanning_alerts": findings,  # same source — Code Scanning is the primary
        # Per-severity counts (matches the dashboard's chip strip)
        "severity_breakdown": {"critical": 35, "high": 19, "medium": 0, "low": 0},
        # Per-finding CVSS, in the same shape the AI service emits.
        "cvss_breakdown": [
            {"rule_id": f.get("rule_id", ""), "file": f.get("file_location"),
             "line": f.get("line"), "cvss_score": 0.0, "cvss_vector": "",
             "severity": f.get("severity", "low")}
            for f in findings
        ],
        "recommendations": [
            {"recommendation": "Move all secrets to GitHub Secrets and reference via ${{ secrets.* }}", "priority": "high"},
            {"recommendation": "Pin all action versions to a specific SHA (e.g. actions/checkout@b4b15b8c7c6ac21ea080f9f81cd0ad11cf9f4f1b)", "priority": "medium"},
            {"recommendation": "Replace raw SQL queries with the Sequelize ORM to prevent SQL injection", "priority": "high"},
            {"recommendation": "Add rate limiting on /auth/login to mitigate credential stuffing", "priority": "high"},
            {"recommendation": "Add a non-root USER directive in the Dockerfile", "priority": "medium"},
            {"recommendation": "Restrict CORS to an explicit allow-list of trusted origins", "priority": "medium"},
        ],
        "summary": (
            f"Found {len(findings)} security issues from Code Scanning. "
            f"Total CVSS sum: 458.3. Risk level: CRITICAL. "
            f"Compliance score: 22.0% [PCI-DSS 4.0, OWASP CI/CD, OWASP Top 10]."
        ),
    }
    return state


def main() -> None:
    state = build_state()
    out = generate_pdf_report(state)
    size = os.path.getsize(out)
    print(f"PDF generated: {out} ({size} bytes)")
    assert size > 5000, "PDF too small, likely empty"
    with open(out, "rb") as f:
        data = f.read()
    pages = data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type/Page")
    print(f"Approx page count: {pages}")
    # Now we expect at least 8 pages (cover + 5 sections + tables).
    assert pages >= 8, f"Expected at least 8 pages, got {pages}"


if __name__ == "__main__":
    main()
