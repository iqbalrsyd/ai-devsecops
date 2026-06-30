"""Shared reference data for the AI DevSecOps pipeline (v9.5 — rev. coverage mapping).

Exposes:
  - DOMAINS: 3 webapp domains (e-commerce, blog, iot) + general
  - PAYMENT_SUBTYPES: payment-processor identifiers (e-commerce only)
  - COVERAGES: 10 security coverages aligned with the 3 supported domains
  - RULE_TO_COVERAGE: Tier 1 Semgrep rule_id → primary coverage (v9.5 NEW)
  - CWE_TO_COVERAGE: CWE-XXX → primary coverage (v9.5 NEW)
  - OWASP_API_TO_COVERAGE: OWASP API Top 10:2023 → primary coverage (v9.5 NEW)
  - DEFAULT_AUGMENTATIONS: per-coverage fallback (job, configuration)
  - STANDARD_JOBS: 8 always-emitted pipeline jobs
  - DOMAIN_THREATS: deterministic fallback for domain_threats
  - FEATURE_VOCAB: 14 features the domain classifier may surface
  - TYPE_TO_COVERAGE: keyword → coverage map for security_analyzer
  - infer_security_coverage(): map a finding to a coverage id
  - resolve_coverage_for_rule(): map a Semgrep rule_id to coverage (v9.5 NEW)
  - resolve_coverage_for_cwe(): map a CWE-XXX to coverage (v9.5 NEW)
  - resolve_coverage_for_owasp_api(): map OWASP API to coverage (v9.5 NEW)
  - owasp_risk_level(): resolve (likelihood, impact) → risk_level

v9.5 changes (per rekomendasi-judul.md + PDF report gap analysis):
  * Coverage mapping ditambahkan (RULE_TO_COVERAGE, CWE_TO_COVERAGE,
    OWASP_API_TO_COVERAGE) — single-value (1 rule = 1 primary coverage).
  * 3 helper function untuk lookup dipakai oleh:
      - K1.5 semgrep_llm_generator (constraint LLM untuk emit coverage)
      - K2.3 pattern_inference (Tier 3 Semgrep rule coverage)
      - K4 security_analysis (findings[].security_coverage enrichment)
  * Number of coverages tetap 10 (sesuai coverage_library.COVERAGES
    existing). PDF report hardcoded "15" di line 1504 perlu di-update
    jadi `len(COVERAGES)` di iterasi selanjutnya.
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


# =============================================================================
# Coverage Mapping (v9.5 — C2 per rekomendasi-judul.md + PDF gap analysis)
# =============================================================================
# Single-value mapping: 1 rule_id / 1 CWE / 1 OWASP API → 1 primary coverage.
# Dipakai oleh:
#   - K1.5 semgrep_llm_generator: constraint LLM untuk emit coverage field
#   - K2.3 pattern_inference_node: Tier 3 Semgrep rule coverage link
#   - K4 security_analysis: enrich findings[].security_coverage
#   - PDF generator §3.4 + §5.4: narasi "Rule X meng-cover coverage Y"
#
# Single-value dipilih (bukan multi-value) untuk kesederhanaan:
#   - 1 rule punya 1 primary coverage; coverage sekunder tidak di-track
#   - Trade-off: rule overlap (mis. PCI + auth) pilih yang paling relevan

RULE_TO_COVERAGE: dict[str, str] = {
    # ===== E-commerce Tier 1 (26 rules) =====
    "ecommerce-pci-card-data-in-logs":         "payment_security",
    "ecommerce-pci-stripe-secret-in-source":   "payment_security",
    "ecommerce-pci-raw-pan-in-code":           "payment_security",
    "ecommerce-api-bola-cart-access":          "api_security",
    "ecommerce-api-no-auth-on-checkout":       "authentication_security",
    "ecommerce-mass-assignment-admin":         "api_security",
    "ecommerce-price-tampering":               "data_security",
    "ecommerce-discount-tampering":            "data_security",
    "ecommerce-order-amount-from-client":      "data_security",
    "ecommerce-sqli-order-lookup":             "data_security",
    "ecommerce-xss-product-render":            "api_security",
    "ecommerce-csrf-no-protection":            "api_security",
    "ecommerce-jwt-weak-secret":               "authentication_security",
    "ecommerce-jwt-no-expiration":             "authentication_security",
    "ecommerce-log-sensitive-data":            "logging_security",
    "ecommerce-md5-password":                  "authentication_security",
    "ecommerce-sha1-password":                 "authentication_security",
    "ecommerce-webhook-no-signature-check":    "payment_security",
    "ecommerce-refund-without-original-charge":"payment_security",
    "ecommerce-currency-float-arithmetic":     "payment_security",
    "ecommerce-stock-decrement-without-lock":  "data_security",
    "ecommerce-idempotency-key-missing":       "payment_security",
    "ecommerce-pii-in-url":                    "data_security",
    "ecommerce-shipping-address-trust-client": "data_security",
    "ecommerce-test-card-in-source":           "payment_security",
    "ecommerce-secret-key-in-client":          "authentication_security",
    # ===== Blog Tier 1 (7 rules) =====
    "blog-markdown-sanitize":                  "cms_security",
    "blog-comment-stored-xss":                 "cms_security",
    "blog-javascript-link-markdown":           "cms_security",
    "blog-open-redirect-via-next":             "api_security",
    "blog-cookie-no-httponly":                 "authentication_security",
    "blog-user-enumeration":                   "authentication_security",
    "blog-idor-post-edit":                     "cms_security",
    # ===== IoT Tier 1 (12 rules) =====
    "iot-mqtt-tls-required":                   "iot_security",
    "iot-device-default-credentials":          "iot_security",
    "iot-firmware-update-signature":           "iot_security",
    "iot-tls-cert-verify-disabled":            "iot_security",
    "iot-mqtt-broker-bind-wildcard":           "iot_security",
    "iot-firmware-no-signature-verify":        "iot_security",
    "iot-default-password-in-config":          "iot_security",
    "iot-sensor-data-no-encryption":           "iot_security",
    "iot-telnet-enabled":                      "iot_security",
    "iot-debug-interface-exposed":             "iot_security",
    "iot-device-id-as-only-auth":              "iot_security",
    "iot-overall-tls-required":                "iot_security",
    # ===== API baseline (owasp-api.yml) =====
    "api-bola-missing-ownership-check":        "api_security",
    "api-ssrf-user-controlled-url":            "api_security",
    "api-mass-assignment-spread-body":         "api_security",
    "api-excessive-data-exposure":             "api_security",
    "api-cors-wildcard-origin":                "api_security",
    "api-cors-reflect-origin":                 "api_security",
    "api-no-pagination":                       "api_security",
    "api-no-max-body-size":                    "api_security",
    "api-stack-trace-exposure":                "api_security",
    "api-auth-no-rate-limit-on-login":         "authentication_security",
}


CWE_TO_COVERAGE: dict[str, str] = {
    # OWASP API1 (BOLA) + API3 (BOPLA) + API5 (BFLA)
    "CWE-639": "authentication_security",
    "CWE-285": "authentication_security",
    "CWE-862": "authentication_security",
    # OWASP API2 (Broken Auth)
    "CWE-287": "authentication_security",
    "CWE-307": "authentication_security",
    "CWE-798": "authentication_security",
    "CWE-613": "authentication_security",
    "CWE-345": "payment_security",
    # OWASP API4 (Resource Consumption)
    "CWE-770": "api_security",
    "CWE-754": "payment_security",
    # OWASP API6 (Mass Assignment)
    "CWE-915": "api_security",
    # OWASP API7 (SSRF)
    "CWE-918": "api_security",
    # OWASP API8 (Misconfig)
    "CWE-209": "logging_security",
    # OWASP Top 10 A03 (Injection)
    "CWE-89":  "data_security",
    "CWE-79":  "api_security",
    "CWE-78":  "data_security",
    "CWE-77":  "data_security",
    "CWE-352": "api_security",
    "CWE-22":  "data_security",
    # OWASP Top 10 A04 (Insecure Design)
    "CWE-434": "api_security",
    # OWASP Top 10 A05 (Misconfig)
    "CWE-1021": "cms_security",
    "CWE-942":  "api_security",
    # PCI-DSS 3.4 (PAN protection)
    "CWE-532": "logging_security",
    "CWE-312": "payment_security",
    "CWE-319": "iot_security",
    "CWE-327": "authentication_security",
    "CWE-602": "data_security",
    # IoT-specific
    "CWE-295": "iot_security",
    "CWE-311": "iot_security",
    "CWE-668": "iot_security",
    "CWE-494": "iot_security",
    "CWE-20":  "iot_security",
    "CWE-125": "iot_security",
    "CWE-787": "iot_security",
    # Others
    "CWE-601": "api_security",
    "CWE-1004": "authentication_security",
    "CWE-204": "authentication_security",
}


OWASP_API_TO_COVERAGE: dict[str, str] = {
    "API1:2023": "authentication_security",   # BOLA
    "API2:2023": "authentication_security",   # Broken Auth
    "API3:2023": "api_security",               # BOPLA
    "API4:2023": "api_security",               # Resource Consumption
    "API5:2023": "authentication_security",   # BFLA
    "API6:2023": "api_security",               # Mass Assignment
    "API7:2023": "api_security",               # SSRF
    "API8:2023": "api_security",               # Misconfig
    "API9:2023": "api_security",               # Inventory
    "API10:2023": "api_security",              # Unsafe Consumption
}


def resolve_coverage_for_rule(rule_id: str) -> str | None:
    """Resolve a Semgrep rule_id to its primary security coverage.

    Single-value mapping (1 rule = 1 primary coverage). Used by:
      - K1.5 semgrep_llm_generator: validate LLM-emitted coverage
      - K2.3 pattern_inference_node: link Tier 3 rule to coverage
      - PDF generator §3.4 + §5.4: render "Coverage" column

    Lookup order:
      1. RULE_TO_COVERAGE[rule_id] (exact match)
      2. Extract CWE-XXX prefix from rule_id → CWE_TO_COVERAGE
      3. None (caller decides fallback)

    Args:
        rule_id: Semgrep rule id, e.g. "ecommerce-pci-card-data-in-logs"
                 or "github.codeql.cwe-089.tainted-sql-string".

    Returns:
        coverage id (string) or None if no mapping found.
    """
    if not rule_id:
        return None
    rid = rule_id.strip().lower()
    if rid in RULE_TO_COVERAGE:
        return RULE_TO_COVERAGE[rid]
    # Fallback: extract CWE-NNN from rule_id substring
    import re
    m = re.search(r"cwe-(\d+)", rid)
    if m:
        # Strip leading zeros to match canonical CWE format
        cwe = f"CWE-{int(m.group(1))}"
        return CWE_TO_COVERAGE.get(cwe)
    return None


def resolve_coverage_for_cwe(cwe_id: str) -> str | None:
    """Resolve a CWE-XXX identifier to its primary coverage.

    Args:
        cwe_id: e.g. "CWE-89", "CWE-639", or just "89".

    Returns:
        coverage id (string) or None if no mapping found.
    """
    if not cwe_id:
        return None
    s = str(cwe_id).strip().upper()
    if not s.startswith("CWE-"):
        s = f"CWE-{s}"
    return CWE_TO_COVERAGE.get(s)


def resolve_coverage_for_owasp_api(owasp_api: str) -> str | None:
    """Resolve an OWASP API Top 10:2023 reference to its primary coverage.

    Accepts "API1", "API1:2023", "API1:2023 BOLA" (parses first token).

    Returns:
        coverage id (string) or None if no mapping found.
    """
    if not owasp_api:
        return None
    s = str(owasp_api).strip().upper()
    # Extract "API1" or "API10" — match at start, optional ":2023"
    import re
    m = re.match(r"^(API\d{1,2})(?::\d{4})?", s)
    if not m:
        return None
    key = f"{m.group(1)}:2023"
    return OWASP_API_TO_COVERAGE.get(key)
