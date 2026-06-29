"""Shared reference data for the AI DevSecOps pipeline (v9.3 — rev. 3-domain & 2-arch).

Exposes:
  - DOMAINS: 3 webapp domains (e-commerce, blog, iot) + general
  - PAYMENT_SUBTYPES: payment-processor identifiers (e-commerce only)
  - COVERAGES: security coverages aligned with the 3 supported domains
  - DEFAULT_AUGMENTATIONS: per-coverage fallback (job, configuration)
  - STANDARD_JOBS: 8 always-emitted pipeline jobs
  - DOMAIN_THREATS: deterministic fallback for domain_threats
  - FEATURE_VOCAB: 14 features the domain classifier may surface
  - TYPE_TO_COVERAGE: keyword → coverage map for security_analyzer
  - infer_security_coverage(): map a finding to a coverage id
  - owasp_risk_level(): resolve (likelihood, impact) → risk_level
"""

from __future__ import annotations

from typing import Any

DOMAINS: list[str] = [
    "e-commerce", "blog", "iot", "general",
]

PAYMENT_SUBTYPES: list[str] = [
    "stripe", "midtrans", "xendit", "doku", "paypal", "braintree",
    "razorpay", "adyen", "square", "multi", "unknown", "none",
]

FEATURE_VOCAB: list[str] = [
    "authentication", "catalog", "shopping_cart", "checkout", "payment",
    "order_management", "database", "file_upload", "mqtt", "telemetry",
    "firmware", "device_management",
    "blog_posting", "comment_system",
]

DOMAIN_THREATS: dict[str, list[str]] = {
    "e-commerce": [
        "Credit-card data exfiltration via SQL injection in checkout",
        "Price tampering through insecure direct object references in cart",
        "Webhook spoofing against payment gateway callbacks",
    ],
    "blog": [
        "Stored XSS in comment system",
        "Markdown injection leading to cookie theft",
        "Author impersonation via weak session handling",
    ],
    "iot": [
        "Device-credential leakage in firmware",
        "MQTT broker takeover via default credentials",
        "Sensor data tampering on insecure transport",
    ],
    "general": [
        "Hardcoded secrets in repository",
        "Outdated dependencies with known CVEs",
        "Insufficient input validation on public endpoints",
    ],
}

COVERAGES: list[dict[str, Any]] = [
    {"id": "authentication_security", "description": "Auth, session, JWT, OAuth",
     "signals": {"libraries": ["passport", "jsonwebtoken", "jwt", "bcrypt", "auth0", "oauth"],
                 "routes": ["/login", "/signup", "/auth"], "entities": ["user", "session"]}},
    {"id": "api_security", "description": "REST/GraphQL, OWASP API Top 10",
     "signals": {"libraries": ["express", "fastify", "nestjs", "koa", "graphql", "apollo"],
                 "routes": ["/api", "/v1/", "/graphql"], "entities": ["controller", "endpoint"]}},
    {"id": "data_security", "description": "Database, ORM, SQL injection",
     "signals": {"libraries": ["sequelize", "prisma", "mongoose", "typeorm", "mysql", "pg", "sqlite", "mongodb"],
                 "entities": ["db", "model", "schema"]}},
    {"id": "payment_security", "description": "Payment, PCI-DSS",
     "signals": {"libraries": ["stripe", "midtrans", "xendit", "doku", "paypal", "braintree", "razorpay", "adyen"],
                 "routes": ["/checkout", "/payment", "/billing"],
                 "entities": ["order", "invoice", "transaction"]}},
    {"id": "container_security", "description": "Docker, image",
     "signals": {"deployment": ["docker", "docker_compose"]}},
    {"id": "iot_security", "description": "MQTT, sensor, firmware",
     "signals": {"libraries": ["mqtt", "paho-mqtt", "amqp", "coap", "modbus"],
                 "entities": ["device", "sensor", "telemetry"]}},
    {"id": "logging_security", "description": "App logging",
     "signals": {"libraries": ["winston", "bunyan", "pino", "log4j", "logrus", "morgan"]}},
    {"id": "file_upload_security", "description": "Multipart upload",
     "signals": {"libraries": ["multer", "formidable", "busboy", "sharp"],
                 "routes": ["/upload", "/files"]}},
    {"id": "cms_security", "description": "Blog post, comment",
     "signals": {"libraries": ["marked", "dompurify", "ghost"],
                 "entities": ["post", "comment", "article"], "domain": ["blog"]}},
    {"id": "dependency_security", "description": "SCA, CVEs",
     "signals": {"package_managers": ["npm", "yarn", "pip", "go mod", "cargo"]}},
]


def get_coverage(coverage_id: str) -> dict[str, Any] | None:
    for entry in COVERAGES:
        if entry["id"] == coverage_id:
            return entry
    return None


DEFAULT_AUGMENTATIONS: dict[str, list[dict[str, str]]] = {
    "authentication_security": [
        {"job": "sast", "configuration": "p/secrets"},
        {"job": "secret_scan", "configuration": "focus: jwt, oauth tokens"},
    ],
    "api_security": [
        {"job": "sast", "configuration": "p/owasp-top-ten, p/javascript, p/nodejs, owasp-api.yml"},
    ],
    "data_security": [
        {"job": "sast", "configuration": "p/sql-injection"},
        {"job": "sca", "configuration": "db-driver-cve-scan"},
    ],
    "payment_security": [
        {"job": "sast", "configuration": "ecommerce.yml"},
        {"job": "secret_scan", "configuration": "focus: stripe, midtrans, xendit"},
    ],
    "container_security": [
        {"job": "container_scan", "configuration": "trivy image + Dockerfile"},
    ],
    "iot_security": [
        {"job": "sast", "configuration": "iot-mqtt.yml"},
        {"job": "secret_scan", "configuration": "focus: device credentials"},
    ],
    "logging_security": [
        {"job": "sast", "configuration": "sensitive-data-in-logs.yml"},
        {"job": "sca", "configuration": "default"},
    ],
    "file_upload_security": [
        {"job": "sast", "configuration": "path-traversal.yml, file-upload-bypass.yml"},
    ],
    "cms_security": [
        {"job": "sast", "configuration": "blog-csp.yml"},
        {"job": "sca", "configuration": "markdown cve scan"},
    ],
    "dependency_security": [
        {"job": "sca", "configuration": "npm audit / pip-audit / govulncheck"},
    ],
}

STANDARD_JOBS: list[str] = [
    "lint", "test", "build", "sast", "dependency-scan",
    "secret-scan", "container-build", "container-scan",
]

ALLOWED_STAGES: list[str] = [
    # v9.3 revisi 3-domain: domain-specific compliance stages (pci-dss,
    # hipaa, ledger-check, csp-headers, mqtt-security) removed. Per-domain
    # custom jobs now come from LLM-driven job_reasoning_node (K2.4).
    "docker-compose-validate", "dependency-scan-per-service",
]

VALID_AUGMENTATION_JOBS: set[str] = {
    "sast", "sca", "secret_scan", "container_scan", "compliance_check",
    "docker_compose_validate", "dependency_scan_per_service",
}

BASE_CONTROLS: list[str] = ["lint", "sast", "secret_scan"]


TYPE_TO_COVERAGE: list[tuple[str, str]] = [
    ("hardcoded_secret", "authentication_security"),
    ("jwt", "authentication_security"),
    ("oauth", "authentication_security"),
    ("sql_injection", "data_security"),
    ("nosql_injection", "data_security"),
    ("xss", "api_security"),
    ("csrf", "api_security"),
    ("graphql", "api_security"),
    ("rest_api", "api_security"),
    ("stripe", "payment_security"),
    ("midtrans", "payment_security"),
    ("xendit", "payment_security"),
    ("payment", "payment_security"),
    ("dockerfile", "container_security"),
    ("docker_compose", "container_security"),
    ("container", "container_security"),
    ("mqtt", "iot_security"),
    ("firmware", "iot_security"),
    ("sensitive_data_log", "logging_security"),
    ("dompurify", "cms_security"),
    ("markdown", "cms_security"),
    ("vulnerable_dependency", "dependency_security"),
    ("cve", "dependency_security"),
    ("outdated_package", "dependency_security"),
    ("path_traversal", "file_upload_security"),
    ("file_upload", "file_upload_security"),
    # GitHub-specific rule id prefixes (Code Scanning default
    # ruleset uses `github.<topic>` as the rule id). Matching
    # the topic substring is enough — heuristic, not exact.
    ("github.api-", "api_security"),
    ("github.cors-", "api_security"),
    ("github.sql-", "data_security"),
    ("github.csrf-", "api_security"),
    ("github.xss-", "api_security"),
    ("github.secrets-", "authentication_security"),
    ("github.dependabot", "dependency_security"),
    ("github.workflows", "dependency_security"),
    ("github.container-", "container_security"),
    ("github.dockerfile", "container_security"),
    # node-tar / npm vulnerabilities land in dependency_security
    # because they are CVE-class findings on a package.
    ("node-tar", "dependency_security"),
    ("qs ", "dependency_security"),
    ("lodash", "dependency_security"),
    ("minimatch", "dependency_security"),
    ("semver", "dependency_security"),
    ("path-to-regexp", "api_security"),
    ("pino", "logging_security"),
    ("lodash.", "dependency_security"),
    ("axios", "api_security"),
    ("express", "api_security"),
    ("fastify", "api_security"),
    ("koa", "api_security"),
]


def infer_security_coverage(finding: dict) -> str | None:
    if not isinstance(finding, dict):
        return None
    type_field = (finding.get("type") or "").lower()
    scanner = (finding.get("scanner") or "").lower()
    file_field = (finding.get("file") or "").lower()
    rule_id = (finding.get("rule_id") or "").lower()
    haystacks = [type_field, scanner, file_field, rule_id]
    for keyword, coverage_id in TYPE_TO_COVERAGE:
        if any(keyword in h for h in haystacks if h):
            return coverage_id
    return None


OWASP_RISK_MATRIX: dict[tuple[str, str], str] = {
    ("high", "high"): "Critical", ("high", "medium"): "High", ("high", "low"): "Medium",
    ("medium", "high"): "High", ("medium", "medium"): "Medium", ("medium", "low"): "Low",
    ("low", "high"): "Medium", ("low", "medium"): "Low", ("low", "low"): "Note",
}


def owasp_risk_level(likelihood: str, impact: str) -> str:
    key = (likelihood.lower(), impact.lower())
    return OWASP_RISK_MATRIX.get(key, "Note")
