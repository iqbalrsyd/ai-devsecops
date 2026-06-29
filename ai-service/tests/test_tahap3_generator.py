"""Test Tahap 3 (workflow_generation) dengan mock input dari Tahap 1+2.

Scenario: repo iqbalrsyd/eccomerce-monolith-vuln
- JavaScript / Express
- monolithic architecture
- Docker deployment
- Domain: e-commerce
- Features: authentication, checkout, payment, database
- Applicable coverages: 6 (auth, api, data, payment, container, dependency)
- Pipeline augmentations: 8

Usage:
  cd ai-service
  python -m tests.test_tahap3_generator
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.pipeline_state import PipelineEngineerState
from app.agents.nodes.workflow_generator import workflow_generator_node
from app.agents.nodes.workflow_validator import workflow_validator_node


def make_mock_state_for_eccomerce_monolith() -> PipelineEngineerState:
    """Mock state simulating Tahap 1+2 output for eccomerce-monolith-vuln."""
    return {
        # Request metadata
        "request_type": "generate",
        "github_token": "mock-token",
        "repository_url": "https://github.com/iqbalrsyd/eccomerce-monolith-vuln",
        "repository_full_name": "iqbalrsyd/eccomerce-monolith-vuln",
        "repository_default_branch": "main",
        "repository_name": "eccomerce-monolith-vuln",
        "repository_description": "Intentionally vulnerable e-commerce monolith for DevSecOps testing",

        # Tahap 1 output
        "detected_technologies": {
            "primary_language": "JavaScript",
            "primary_language_confidence": 0.95,
            "primary_language_reason": "package.json: express, jest, body-parser, jsonwebtoken",
            "frameworks": ["Express", "Jest"],
            "framework_confidences": [0.95, 0.90],
            "build_tools": ["npm"],
            "package_manager": "npm",
            "package_manager_confidence": 0.95,
            "test_framework": "Jest",
            "database": "SQLite",
            "runtime": "Node.js",
        },
        "detected_architecture": {
            "architecture_type": "monolithic",
            "architecture_confidence": 0.90,
            "service_count": 1,
            "service_names": ["eccomerce-monolith-vuln"],
            "has_api_gateway": False,
            "has_message_queue": False,
            "is_containerized": True,
        },
        "detected_architecture_type": "monolithic",
        "detected_architecture_confidence": 0.90,
        "detected_architecture_reason": "Single package.json, single src/, single Dockerfile",
        "detected_deployment": {
            "docker": True,
            "docker_confidence": 0.95,
            "docker_reason": "Detected 1 Dockerfile(s)",
            "docker_compose": False,
            "docker_compose_confidence": 0.0,
            "recommended_deployment_target": "docker",
            "alternative_deployment_targets": [],
            "deployment_reason": "Dockerfile detected - recommended deployment is Docker host",
        },
        "recommended_deployment_target": "docker",

        "detected_domain": "e-commerce",
        "domain_sub_type": "unknown",
        "domain_confidence": 0.85,
        "domain_evidence": [
            "Domain keyword in name: ecommerce",
            "Domain entity: order, product, checkout, payment",
            "Domain route: /checkout, /orders, /products",
        ],
        "domain_threats": [
            "Hardcoded API keys in source code",
            "SQL injection di form checkout",
            "CSRF di payment endpoint",
        ],
        "features": [
            "authentication",
            "checkout",
            "payment",
            "order_management",
            "database",
            "file_upload",
        ],
        "attack_surfaces": [
            "Container Image", "Dockerfile Config", "Source Code", "Dependencies", "Secrets in Code",
        ],

        # ── Tahap 2 output (K2.1 coverage_inference) ──────────────────
        "security_coverages": [
            {"id": "authentication_security", "applicable": True, "reason": "jsonwebtoken library, /auth route detected", "confidence": 0.9},
            {"id": "api_security", "applicable": True, "reason": "Express REST API detected", "confidence": 0.9},
            {"id": "data_security", "applicable": True, "reason": "better-sqlite3, db.prepare() calls, /db.js entity", "confidence": 0.9},
            {"id": "payment_security", "applicable": True, "reason": "ecommerce domain, /checkout route, /orders, payment entity", "confidence": 0.85},
            {"id": "container_security", "applicable": True, "reason": "Dockerfile detected", "confidence": 0.95},
            {"id": "logging_security", "applicable": False, "reason": "no logging library detected", "confidence": 0.0},
            {"id": "file_upload_security", "applicable": False, "reason": "no multer or upload route", "confidence": 0.0},
            {"id": "iot_security", "applicable": False, "reason": "no MQTT/sensor signal", "confidence": 0.0},
            {"id": "healthcare_security", "applicable": False, "reason": "no patient/PHI signal", "confidence": 0.0},
            {"id": "fintech_security", "applicable": False, "reason": "no ledger/transfer signal", "confidence": 0.0},
            {"id": "cms_security", "applicable": False, "reason": "no post/comment signal", "confidence": 0.0},
            {"id": "education_security", "applicable": False, "reason": "no course/quiz signal", "confidence": 0.0},
            {"id": "microservice_security", "applicable": False, "reason": "monolith, not microservices", "confidence": 0.0},
            {"id": "csp_security", "applicable": False, "reason": "no helmet library", "confidence": 0.0},
            {"id": "dependency_security", "applicable": True, "reason": "package manager detected (npm)", "confidence": 0.95},
        ],
        "coverage_inference_reasoning": "LLM-inferred from repository context with deterministic signal scoring.",

        # ── Tahap 2 output (K2.2 pipeline_augmentation) ───────────────
        "pipeline_augmentations": [
            {"coverage": "authentication_security", "job": "sast", "configuration": "p/secrets, p/owasp-top-ten (auth rules)", "reason": "JWT detected"},
            {"coverage": "authentication_security", "job": "secret_scan", "configuration": "focus: JWT, OAuth, session tokens", "reason": "JWT secret must be scanned"},
            {"coverage": "api_security", "job": "sast", "configuration": "p/owasp-top-ten, p/javascript, p/nodejs", "reason": "Express REST API"},
            {"coverage": "api_security", "job": "sast", "configuration": ".semgrep/owasp-api.yml custom rules", "reason": "OWASP API Top 10"},
            {"coverage": "data_security", "job": "sast", "configuration": "p/sql-injection, p/javascript", "reason": "SQLite with prepared statements"},
            {"coverage": "data_security", "job": "sca", "configuration": "DB driver CVE check", "reason": "better-sqlite3 CVEs"},
            {"coverage": "payment_security", "job": "sast", "configuration": "pci-dss.yml custom rules", "reason": "e-commerce + checkout"},
            {"coverage": "payment_security", "job": "secret_scan", "configuration": "focus: stripe, midtrans, xendit keys", "reason": "e-commerce"},
            {"coverage": "container_security", "job": "container_scan", "configuration": "trivy image + Dockerfile", "reason": "Dockerfile detected"},
            {"coverage": "dependency_security", "job": "sca", "configuration": "npm audit", "reason": "package manager npm"},
        ],

        "inferred_security_needs": {
            "security_controls": [
                {"control": "lint", "status": "recommended", "reason": "code quality", "tool": "eslint", "tool_version": "latest"},
                {"control": "sast", "status": "recommended", "reason": "static analysis", "tool": "semgrep", "tool_version": "latest"},
                {"control": "secret_scan", "status": "recommended", "reason": "credential leak detection", "tool": "gitleaks", "tool_version": "latest"},
                {"control": "sca", "status": "recommended", "reason": "dependency CVE check", "tool": "npm audit", "tool_version": "latest"},
                {"control": "container_scan", "status": "recommended", "reason": "Dockerfile detected", "tool": "trivy", "tool_version": "latest"},
            ],
            "required_tools": [
                {"name": "eslint", "purpose": "code linting", "language": "javascript"},
                {"name": "semgrep", "purpose": "static analysis", "language": "generic"},
                {"name": "gitleaks", "purpose": "secret scan", "language": "generic"},
                {"name": "npm audit", "purpose": "dependency CVE", "language": "javascript"},
                {"name": "trivy", "purpose": "container scan", "language": "generic"},
            ],
            "pipeline_stages": ["lint", "test", "sast", "sca", "secret_scan", "container_scan"],
            "security_coverages": [],
            "pipeline_augmentations": [],
        },

        "repository_structure": [
            {"name": ".env", "type": "file"},
            {"name": "Dockerfile", "type": "file"},
            {"name": "README.md", "type": "file"},
            {"name": "package.json", "type": "file"},
            {"name": "src", "type": "dir"},
            {"name": "tests", "type": "dir"},
        ],
        "repository_files": {
            "package.json": json.dumps({
                "name": "ecommerce-monolith-vuln",
                "dependencies": {
                    "express": "4.16.0",
                    "better-sqlite3": "7.4.3",
                    "lodash": "4.17.4",
                    "jsonwebtoken": "8.3.0",
                },
                "devDependencies": {"jest": "27.0.0"},
            }),
            "Dockerfile": "FROM node:18\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD [\"node\", \"src/server.js\"]\n",
        },
        "source_files": [],
        "existing_workflows": [],

        # Defaults
        "findings": [],
        "validation_errors": [],
        "validation_warnings": [],
        "validation_passed": False,
        "warnings": [],
        "removed_legacy_workflows": [],
        "workflow_config_issues": [],
        "maintenance_warnings": [],
        "external_service_issues": [],
        "workflow_annotations": [],
        "remediation_recommendations": [],
        "remediation_yaml_patches": [],
        "skipped_jobs": [],
        "execution_results": {},
        "github_branch": None,
        "github_commit_sha": None,
        "github_pr_number": None,
        "github_pr_url": None,
        "workflow_run_id": None,
        "workflow_status": None,
        "workflow_conclusion": None,
        "workflow_logs": [],
        "workflow_jobs": [],
        "workflow_duration_seconds": None,
        "raw_logs": None,
        "scan_results": None,
        "domain_context": None,
        "severity_breakdown": None,
        "recommendations": [],
        "summary": None,
        "errors": [],
        "error_stage": None,
        "auto_deploy": True,
        "pipeline_version": 9,
        "workflow_file": "ci-cd.yml",
        "pdf_report_path": None,
    }


def main():
    print("=" * 80)
    print("TEST TAHAP 3 — WORKFLOW GENERATION")
    print("=" * 80)
    print()
    print("Input: Mock state dari Tahap 1+2 untuk repo iqbalrsyd/eccomerce-monolith-vuln")
    print()

    state = make_mock_state_for_eccomerce_monolith()

    print("── INPUT ──")
    print(f"Repository:    {state['repository_full_name']}")
    print(f"Language:      {state['detected_technologies']['primary_language']}")
    print(f"Framework:     {', '.join(state['detected_technologies']['frameworks'])}")
    print(f"Architecture:  {state['detected_architecture_type']}")
    print(f"Deployment:    docker={state['detected_deployment']['docker']}, compose={state['detected_deployment']['docker_compose']}")
    print(f"Domain:        {state['detected_domain']} (confidence: {state['domain_confidence']})")
    print(f"Features:      {state['features']}")
    print()
    print(f"Applicable Coverages: {sum(1 for c in state['security_coverages'] if c.get('applicable'))} of 15")
    for c in state['security_coverages']:
        if c.get('applicable'):
            print(f"  - {c['id']}: {c['reason']}")
    print()
    print(f"Pipeline Augmentations: {len(state['pipeline_augmentations'])}")
    for a in state['pipeline_augmentations']:
        print(f"  - [{a['coverage']:30}] {a['job']:15} {a['configuration'][:60]}")
    print()

    print("── RUNNING workflow_generator_node ──")
    result = workflow_generator_node(state)
    print()
    print("── RUNNING workflow_validator_node ──")
    result = workflow_validator_node(result)
    print()

    print("── OUTPUT ──")
    print(f"validation_passed: {result.get('validation_passed')}")
    print(f"validation_errors: {result.get('validation_errors')}")
    print(f"validation_warnings: {result.get('validation_warnings')}")
    print(f"generated_stages ({len(result.get('generated_stages') or [])}): {result.get('generated_stages')}")
    print()
    print("stage_explanations:")
    for ex in result.get('stage_explanations') or []:
        print(f"  - {ex.get('name')}: {ex.get('reason', '')[:120]}")
    print()
    print("skipped_jobs:", result.get('skipped_jobs'))
    print()

    print("── GENERATED YAML ──")
    print("=" * 80)
    yaml_text = result.get('generated_workflow', '')
    print(yaml_text)
    print("=" * 80)
    print()
    print(f"YAML length: {len(yaml_text)} chars, {yaml_text.count(chr(10))} lines")

    if result.get('errors'):
        print()
        print("── ERRORS ──")
        for e in result.get('errors', []):
            print(f"  - {e}")


if __name__ == "__main__":
    main()
