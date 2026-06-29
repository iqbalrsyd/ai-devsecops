"""LLM prompt templates for Tier 3 Semgrep rule generation.

The prompt is intentionally narrow:

  * It only sees a curated input (domain, threats, language, frameworks).
  * It must emit a STRICT JSON shape (validated by the node).
  * It must respect the ID prefix and severity constraints enforced
    by llm_generation_config.

v9.4 (sinkron naskah baru) — per rekomendasi-judul.md:
  * 3 domain aktif (R2.2): e-commerce, blog, iot
  * Domain fintech/healthcare/education DIHAPUS dari TIER1_RULE_IDS +
    RECOMMENDED_COVERAGE
  * RECOMMENDED_COVERAGE sekarang hybrid OWASP (makro) + CWE (mikro)
    sesuai naskah R4.2
  * Domain-specific references (naskah R3):
      e-commerce → taherdoost2022payment, gupta2017sql
      blog → gupta2017xss, calzavara2020csp
      IoT → OWASP IoT Top 10 (I1–I10)
  * System prompt ditambah landasan metodologi (matter2025context)
    dan bukti empiris (meneely2013patch)

Reference: docs/README-SEMGREP-TIERS.md (Section 4 — Sequence).
Naskah source: naskah/rekomendasi-judul.md (R3, R4.2)
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """You are a senior application security engineer who writes \
custom Semgrep rules for a specific web application domain.

You produce ONLY valid Semgrep YAML rule definitions. You do NOT invent \
domain facts, threat descriptions, or framework names that were not given \
to you. If you do not know a pattern, you skip it rather than guess.

You are EXTENDING an existing Tier-1 static rule set (e.g. `ecommerce.yml`, \
`blog-csp.yml`, `iot-mqtt.yml`, `owasp-api.yml`) with code patterns that are \
specific to the concrete codebase at hand. Your output is merged with the \
static rules at deploy time — so you should focus on rules that the \
static set does NOT already cover.

Methodological grounding (per skripsi Bab 2 Tinjauan Pustaka):
  * Domain context matters — vulnerabilities cluster by domain \
(meneely2013patch). Adapt coverage accordingly.
  * Context-aware security increases detection accuracy and reduces \
false positives vs one-size-fits-all (matter2025context).
  * Hybrid OWASP (macro) + CWE (micro) is the standard for SAST coverage \
mapping (naskah R4.2).

Supported domains ONLY (v9.4 — sinkron naskah R2.2):
  e-commerce, blog, iot. Do NOT invent rules for fintech, healthcare, \
education, or any other domain not in the input.

Hard constraints (MUST follow):
  1. Every rule `id` MUST start with the prefix `{domain}-custom-` and \
use only lowercase letters, digits, and hyphens. Example: \
`ecommerce-custom-price-tampering`.
  2. Every rule `severity` MUST be one of: `INFO`, `WARNING`. \
Do NOT emit `ERROR` (a human will promote to `ERROR` after review).
  3. Every rule MUST declare a `languages` list. Pick from the languages \
listed in the user input.
  4. Every rule MUST include a `message` (1-3 sentences) that cites the \
specific threat being addressed and a brief remediation hint.
  5. Every rule MUST include `metadata` with at least: `cwe` (CWE-NNN), \
`domain_threat` (which input threat it addresses), and `generated_by: llm`. \
You SHOULD ALSO include `owasp_api` (one of API1:2023..API9:2023) when \
applicable. Web API rules should include `owasp_api`; OWASP IoT rules \
should include `owasp_iot` (I1..I10); e-commerce payment rules should \
include `pci_dss` (4.0 §N.M).
  6. Emit at most {max_rules} rules. Prefer fewer, higher-quality rules \
over many noisy ones. CATEGORIES the rules should cover (pick what is \
relevant for the input, do NOT force all):
       - **Authentication / Authorization**: BOLA, BOPLA, BFLA, missing \
auth, weak JWT, hardcoded credentials (CWE-287, CWE-639, CWE-798).
       - **Input validation**: SQLi, NoSQLi, XSS, command injection, \
SSRF, path traversal (CWE-89, CWE-79, CWE-78, CWE-918, CWE-22).
       - **Cryptography**: weak hash, weak RNG, hardcoded keys, missing \
TLS (CWE-327, CWE-338, CWE-798, CWE-319).
       - **Data exposure**: PII in logs, mass assignment, verbose errors \
(CWE-532, CWE-209, CWE-213, CWE-359).
       - **Resource / business logic**: race conditions, missing rate \
limit, missing pagination, missing idempotency (CWE-362, CWE-770, CWE-754).
  7. Use only the patterns you can express confidently as Semgrep \
`pattern`, `pattern-either`, `pattern-regex`, `metavariable-pattern`, or \
`patterns`. Do NOT invent Semgrep operators.
  8. For each rule, include a numeric `confidence` field (0.0-1.0) \
reflecting how certain you are that the rule will fire only on real \
vulnerabilities (no false positives) AND that the syntax is valid. \
Rules with confidence below {min_confidence} will be dropped.
  9. Output ONLY the JSON object described below. No prose, no markdown \
fences, no code comments.
"""


USER_PROMPT_TEMPLATE = """Generate custom Semgrep rules for the following context.

Domain: {domain}
Primary language: {primary_language}
Frameworks: {frameworks}

Domain-specific threats (from domain_detection_node):
{domain_threats}

Pre-existing Tier-1 static rules (DO NOT duplicate these — write
codebase-specific patterns the static set does not cover):
{tier1_rule_ids}

Recommended CWE / OWASP coverage for {domain} (pick the ones that
match the input threats; do not force all):
{recommended_coverage}

Mandatory rule constraints:
  - ID prefix: {domain}-custom-<slug>
  - Severity: INFO or WARNING only
  - Languages: pick from {primary_language}{extra_languages}
  - Maximum rules: {max_rules}
  - Minimum confidence: {min_confidence}
  - CWE identifier is REQUIRED in metadata
  - OWASP API / OWASP IoT / PCI-DSS tag is STRONGLY RECOMMENDED when
    the rule addresses that compliance framework

Return ONLY this JSON object:

{{
  "rules": [
    {{
      "id": "{domain}-custom-<short-slug>",
      "languages": ["{primary_language}"],
      "severity": "INFO" | "WARNING",
      "message": "Why this is a problem and how to fix it (1-3 sentences).",
      "pattern": "<single Semgrep pattern>",
      "metadata": {{
        "cwe": "CWE-NNN: <title>",
        "domain_threat": "<threat text from the input above>",
        "owasp_api": "API1:2023 .. API9:2023 (optional, web API rules)",
        "owasp_iot": "I1 .. I10 (optional, IoT rules)",
        "pci_dss": "4.0 §N.M (optional, e-commerce payment rules)",
        "generated_by": "llm"
      }},
      "confidence": 0.0
    }}
  ]
}}

Notes on pattern formats you can use (pick one per rule):
  - `pattern: <expression>`              — single AST pattern
  - `patterns: [...]`                    — boolean combination
  - `pattern-either: [...]`              — alternation
  - `pattern-regex: '<regex>'`           — textual regex
  - `metavariable-pattern: {{ ... }}`    — recursive sub-pattern

Keep patterns small and specific. If you cannot express a check safely, \
skip the rule. Focus on rules that the Tier-1 static set does NOT \
already cover.
"""


def _format_list(values: list[str] | None) -> str:
    if not values:
        return "(none)"
    return ", ".join(str(v) for v in values)


# Tier-1 static rule id prefixes per supported domain. Used to
# tell the LLM which patterns are already covered by the static
# rule set so the generated Tier-3 rules focus on codebase-
# specific gaps instead of duplicating the static check.
TIER1_RULE_IDS: dict[str, list[str]] = {
    "e-commerce": [
        "ecommerce-pci-card-data-in-logs",
        "ecommerce-pci-stripe-secret-in-source",
        "ecommerce-pci-raw-pan-in-code",
        "ecommerce-api-bola-cart-access",
        "ecommerce-api-no-auth-on-checkout",
        "ecommerce-price-tampering",
        "ecommerce-discount-tampering",
        "ecommerce-mass-assignment-admin",
        "ecommerce-sqli-order-lookup",
        "ecommerce-xss-product-render",
        "ecommerce-csrf-no-protection",
        "ecommerce-jwt-weak-secret",
        "ecommerce-jwt-no-expiration",
        "ecommerce-log-sensitive-data",
        "ecommerce-md5-password",
        "ecommerce-sha1-password",
        "ecommerce-webhook-no-signature-check",
        "ecommerce-order-amount-from-client",
        "ecommerce-refund-without-original-charge",
        "ecommerce-currency-float-arithmetic",
        "ecommerce-stock-decrement-without-lock",
        "ecommerce-idempotency-key-missing",
        "ecommerce-pii-in-url",
        "ecommerce-shipping-address-trust-client",
        "ecommerce-test-card-in-source",
        "ecommerce-secret-key-in-client",
    ],
    "blog": [
        "blog-markdown-sanitize",
        "blog-comment-stored-xss",
        "blog-javascript-link-markdown",
        "blog-open-redirect-via-next",
        "blog-cookie-no-httponly",
        "blog-user-enumeration",
        "blog-idor-post-edit",
    ],
    "iot": [
        "iot-mqtt-tls-required",
        "iot-device-default-credentials",
        "iot-firmware-update-signature",
        "iot-tls-cert-verify-disabled",
        "iot-mqtt-broker-bind-wildcard",
        "iot-firmware-no-signature-verify",
        "iot-default-password-in-config",
        "iot-sensor-data-no-encryption",
        "iot-telnet-enabled",
        "iot-debug-interface-exposed",
        "iot-device-id-as-only-auth",
        "iot-overall-tls-required",
    ],
}

# Recommended CWE + OWASP coverage per domain. The LLM uses this
# to know which compliance categories to consider. It does NOT
# force it to emit rules for every category — selection is based
# on the actual codebase threats and the patterns the LLM can
# express safely.
#
# v9.4 (sinkron naskah baru) — per rekomendasi-judul.md R3 + R4.2:
#   - 3 domain aktif (e-commerce, blog, iot). Domain
#     fintech/healthcare/education SUDAH DIHAPUS.
#   - Pendekatan hybrid: OWASP (makro) + CWE (mikro) + jurnal spesifik
#   - Reference jurnal per domain:
#       e-commerce → taherdoost2022payment (payment gateway),
#                    gupta2017sql (SQL injection)
#       blog       → gupta2017xss (XSS attacks),
#                    calzavara2020csp (Content Security Policy)
#       iot        → OWASP IoT Top 10 (I1–I10)
RECOMMENDED_COVERAGE: dict[str, str] = {
    "e-commerce": (
        "OWASP API Top 10 2023 (makro): API1 (BOLA), API2 (Broken "
        "Auth), API3 (BOPLA), API4 (Resource Consumption), API5 (BFLA), "
        "API6 (Mass Assignment), API7 (SSRF), API8 (Misconfig). "
        "Plus PCI-DSS 4.0 (mikro): §3.4 (PAN), §3.5.1 (keys), §6.4.3 "
        "(webhook), §8 (auth), §10 (logging). "
        "CWE focus (per naskah R3 + R4.2): 22, 79, 89, 287, 312, 319, "
        "327, 345, 352, 362, 532, 601, 602, 639, 754, 770, 798, 915. "
        "Domain-specific references: taherdoost2022payment (payment "
        "gateway API key leak), gupta2017sql (SQLi di /checkout)."
    ),
    "blog": (
        "OWASP Top 10:2021 (makro): A01 (Broken Access Control), A03 "
        "(Injection — XSS), A05 (Security Misconfiguration — CSP). "
        "CWE focus (per naskah R3 + R4.2): 79 (XSS), 204 (user "
        "enumeration), 434 (file upload), 601 (open redirect), 639 "
        "(BOLA post/comment edit), 1004 (sensitive cookie without "
        "HttpOnly), 1021 (clickjacking / CSP). "
        "Domain-specific references: gupta2017xss (XSS attacks & "
        "defense mechanisms), calzavara2020csp (Content Security "
        "Policy survey)."
    ),
    "iot": (
        "OWASP IoT Top 10 (makro): I1 (weak/hardcoded passwords), "
        "I2 (insecure network services), I3 (insecure ecosystem "
        "interfaces), I5 (lack of device management), I9 (insecure "
        "default settings), I10 (lack of physical hardening). "
        "CWE focus (per naskah R3 + R4.2): 22 (path traversal), "
        "287 (improper authentication), 295 (improper cert validation), "
        "311 (missing encryption), 319 (cleartext transmission), 494 "
        "(download without integrity check), 668 (exposure to wrong "
        "sphere), 798 (hardcoded credentials). "
        "Domain-specific reference: OWASP IoT Top 10 (I1–I10) — lihat "
        "https://owasp.org/www-project-internet-of-things/."
    ),
}


def build_prompt(
    domain: str,
    domain_threats: list[str],
    primary_language: str,
    frameworks: list[str] | None = None,
    extra_languages: list[str] | None = None,
    max_rules: int = 5,
    min_confidence: float = 0.7,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the LLM call.

    The two-prompt split keeps the system prompt constant (caching
    friendly) and the user prompt parameterised per pipeline run.

    `tier1_rule_ids` and `recommended_coverage` are injected so the
    LLM does NOT duplicate patterns already covered by the static
    rule set, and knows which CWE / OWASP categories are most
    relevant for the detected domain.
    """
    domain_n = (domain or "general").lower().strip()
    tier1 = TIER1_RULE_IDS.get(domain_n, [])
    tier1_text = (
        "\n".join(f"  - {rid}" for rid in tier1) if tier1 else "(no static rules yet)"
    )
    coverage_text = RECOMMENDED_COVERAGE.get(
        domain_n,
        "CWE-79, CWE-89, CWE-352, CWE-798, CWE-862 (general web API).",
    )
    sys_prompt = SYSTEM_PROMPT.format(
        domain=domain,
        max_rules=max_rules,
        min_confidence=min_confidence,
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        domain=domain,
        primary_language=primary_language or "javascript",
        frameworks=_format_list(frameworks),
        domain_threats=_format_list(domain_threats),
        max_rules=max_rules,
        min_confidence=min_confidence,
        extra_languages=(
            f", {', '.join(extra_languages)}" if extra_languages else ""
        ),
        tier1_rule_ids=tier1_text,
        recommended_coverage=coverage_text,
    )
    return sys_prompt, user_prompt


def parse_llm_response(content: str) -> list[dict[str, Any]]:
    """Parse and minimally validate the LLM JSON response.

    The LLM is instructed to return a top-level `rules` list. We:
      - Strip optional markdown fences.
      - json.loads the content.
      - Return the `rules` list (or [] if missing).

    More thorough validation (severity, ID prefix, confidence
    range) happens in semgrep_llm_generator_node.
    """
    import json

    if not content:
        return []
    c = content.strip()
    if c.startswith("```"):
        parts = c.split("\n", 1)
        c = parts[1] if len(parts) > 1 else ""
        if c.endswith("```"):
            c = c[:-3]
    try:
        data = json.loads(c.strip())
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    rules = data.get("rules")
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]
