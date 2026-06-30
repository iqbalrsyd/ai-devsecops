"""Job Reasoning Node (K2.4 - struktur-v9.2 / rev. 3-domain & 2-arch).

The LLM analyses the repository's actual source code, business
features, and applicable security coverages, then DESIGNS custom
CI/CD pipeline jobs that are specific to the codebase. This is
qualitatively different from `pipeline_augmentation_node` (which
maps a coverage_id to a static augmentation template) and from the
domain-specific template jobs in `workflow_generator` (which pick
one of `_build_hipaa_job` / `_build_pci_dss_job` / ... by domain).

v9.3 revisi 3-domain & 2-arch:
  Domain yang didukung hanya e-commerce, blog, iot. AI TIDAK boleh
  berhalusinasi keluar dari 3 domain ini. Job yang didesain harus
  sesuai dengan business features dan patterns yang benar-benar ada
  di source code.

The reasoning cite concrete file paths, library usages, and
vulnerabilities. Each design carries:
  - name        : stable kebab-case job name
  - coverage    : which applicable coverage it serves
  - reasoning   : 2-4 sentence justification that cites findings
  - actions     : list of concrete CI actions
  - configuration : timeout, continue_on_error, etc.

Reads:
  - detected_technologies
  - detected_architecture
  - detected_domain / domain_threats / features
  - security_coverages (applicable ones)
  - source_files
  - findings (from source scan)
  - pipeline_augmentations (already decided)

Writes:
  - state.job_designs (list of validated design dicts)
  - state.job_designs_reasoning
  - state.job_designs_valid_count
"""
import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


JOB_REASONING_PROMPT = """You are a senior DevSecOps Pipeline Architect.

Analyse the repository's source code and design custom CI/CD pipeline
jobs that are SPECIFIC to the codebase — not generic domain templates.

## SCOPE (skripsi Bab 3, revisi 3-domain & 1-architecture)

Supported domains: e-commerce, blog, iot (+ general fallback).
Supported architectures: monolithic (saja).
DO NOT invent custom jobs for unsupported domains such as healthcare,
fintech, education, or microservices. Map the repository to one of
the three supported domains and stay within that scope. Arsitektur
bukan variabel eksperimen (batasan B7).

## Repository Context

Language: {language}
Frameworks: {frameworks}
Architecture: {architecture}
Domain: {domain}
Sub-type: {sub_type}
Deployment: {deployment}

## Business Features

{features}

## Applicable Security Coverages (from coverage_inference)

{coverages}

## Findings from Source Scan (from repository_scan)

{findings}

## Sample Source Code Snippets (priority files only)

```
{source_sample}
```

## Task

For each applicable coverage, decide whether a CUSTOM pipeline job
is warranted BEYOND the standard jobs (lint, test, sast,
secret-scan, dependency-scan, container-scan) that are always emitted.

For each custom job you decide to create:
  1. Cite SPECIFIC file paths, libraries, and patterns from the
     source code (NOT generic boilerplate like "ensure JWT is
     secure").
  2. Provide at least 2 concrete actions (shell commands, Semgrep
     rules, file checks) that would actually detect a vulnerability
     in THIS codebase.
  3. Include one `sarif_upload` action so findings appear in GitHub
     Code Scanning.
  4. Cite at least one finding OR source pattern in the `reasoning`
     field — be specific.

Action types you can use (one per action):
  - `shell_check`         : a `run:` script that exits non-zero on bad pattern
  - `semgrep_rule`        : inline Semgrep rule
  - `python_script`       : run a small inline Python check (sarif output)
  - `sarif_upload`        : upload the prior step's SARIF file

## Hard Constraints

- DO NOT create a job that duplicates a standard job.
- Each job MUST have at least 2 actions.
- Each job MUST include exactly one `sarif_upload` action.
- Job name MUST be kebab-case, start with a letter, ≤ 40 chars.
- If the repo has no clear custom-job-worthy pattern, return
  `job_designs: []` — empty is a valid answer.
- Maximum 3 job designs per run (focus on the highest-risk coverage).
- DO NOT design jobs specific to healthcare (PHI/HIPAA/FHIR),
  fintech (ledger/transfer), education (LMS/SCORM), or pure
  microservices. Those domains are out of scope.

## Return ONLY valid JSON

{{
  "job_designs": [
    {{
      "name": "kebab-case-name",
      "coverage": "<coverage_id>",
      "reasoning": "Found <file>:<line> uses <library> in a way that <risk>. This job scans for <pattern> and reports SARIF findings.",
      "actions": [
        {{
          "type": "shell_check",
          "name": "<step name>",
          "script": "<bash script>"
        }},
        {{
          "type": "sarif_upload",
          "category": "<sarif category>"
        }}
      ],
      "configuration": {{
        "continue_on_error": true,
        "timeout_minutes": 10
      }}
    }}
  ]
}}
"""


# ── Structural Validation ──────────────────────────────────────────────
# Same philosophy as pattern_inference_node: lightweight structural
# checks; we don't execute the YAML or run shell commands. The
# downstream workflow_generator + workflow_validator do the heavy
# validation.

REQUIRED_FIELDS = {"name", "coverage", "actions", "reasoning"}
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
STANDARD_JOBS = {
    "lint", "test", "sast", "secret-scan", "dependency-scan",
    "container-scan", "container-build", "build", "sbom",
    "docker-compose-validate", "dependency-scan-per-service",
    "per-service-sast", "per-service-dep-scan", "detect-services",
    "k8s-scan", "terraform-scan", "kube-bench", "cve-scan",
}
VALID_ACTION_TYPES = {"shell_check", "semgrep_rule", "python_script", "sarif_upload"}


def _validate_job_design(job: dict) -> bool:
    if not isinstance(job, dict):
        return False
    if not REQUIRED_FIELDS.issubset(job.keys()):
        return False
    name = job.get("name", "")
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        return False
    if name in STANDARD_JOBS:
        return False
    coverage = job.get("coverage", "")
    if not isinstance(coverage, str) or not coverage:
        return False
    reasoning = job.get("reasoning", "")
    if not isinstance(reasoning, str) or len(reasoning) < 30:
        return False
    actions = job.get("actions", [])
    if not isinstance(actions, list) or len(actions) < 2:
        return False
    has_sarif = False
    for a in actions:
        if not isinstance(a, dict):
            return False
        atype = a.get("type", "")
        if atype not in VALID_ACTION_TYPES:
            return False
        if atype == "sarif_upload":
            has_sarif = True
    if not has_sarif:
        return False
    return True


def _parse_llm_response(content: str) -> dict:
    from app.agents.llm_response_parser import (
        parse_llm_json_object, parse_llm_json_array,
    )
    obj = parse_llm_json_object(content)
    if obj is not None:
        return obj
    arr = parse_llm_json_array(content)
    return arr if arr is not None else {}


def _extract_source_sample(source_files: list, max_chars: int = 6000) -> str:
    if not source_files:
        return "(no source files available)"
    priority_keywords = [
        "auth", "jwt", "secret", "password", "token", "session",
        "payment", "checkout", "order", "cart", "billing",
        "post", "comment", "markdown", "render",
        "device", "sensor", "telemetry", "mqtt", "firmware",
        "controller", "handler", "route", "middleware", "model",
        "server", "app", "main", "index",
    ]
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()
    for entry in source_files:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or entry.get("name") or "").lower()
        content = entry.get("content", "")
        if not content or path in seen:
            continue
        seen.add(path)
        score = 0.0
        for kw in priority_keywords:
            if kw in path:
                score += 2.0
        if any(kw in content.lower() for kw in priority_keywords):
            score += 1.0
        if "test" in path or "spec" in path or "node_modules" in path:
            score -= 5.0
        if 200 < len(content) < 4000:
            score += 1.0
        snippet = f"// {path}\n{content[:1200]}"
        scored.append((score, snippet))
    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    total = 0
    for _, snippet in scored:
        if total + len(snippet) > max_chars:
            out.append(snippet[: max_chars - total] + "\n// ... (truncated)")
            break
        out.append(snippet)
        total += len(snippet)
    return "\n\n".join(out) if out else "(no source files available)"


def _format_findings(findings: list) -> str:
    if not findings:
        return "(no findings from source scan)"
    lines = []
    for f in findings[:15]:
        if not isinstance(f, dict):
            continue
        ftype = f.get("type") or f.get("title") or "finding"
        sev = (f.get("severity") or "medium").upper()
        file_ = f.get("file") or f.get("file_location") or "?"
        line = f.get("line") or "?"
        expl = (f.get("explanation") or f.get("evidence") or "")[:120]
        lines.append(f"- [{sev}] {ftype} in {file_}:{line} — {expl}")
    return "\n".join(lines) if lines else "(no findings)"


def _format_coverages(coverages: list) -> str:
    applicable = [c for c in coverages if c.get("applicable")]
    if not applicable:
        return "(none)"
    return "\n".join(
        f"- {c.get('id')}: {c.get('reason', '')} (confidence={c.get('confidence', 0)})"
        for c in applicable
    )


def _llm_design_jobs(signals: dict) -> list[dict]:
    try:
        prompt = JOB_REASONING_PROMPT.format(
            language=signals.get("primary_language") or "unknown",
            frameworks=", ".join(signals.get("frameworks", []) or []) or "(none)",
            architecture=signals.get("architecture_type") or "monolithic",
            domain=signals.get("detected_domain") or "general",
            sub_type=signals.get("sub_type") or "none",
            deployment=json.dumps(signals.get("deployment", {})),
            features=json.dumps(signals.get("features", [])),
            coverages=_format_coverages(signals.get("coverages", [])),
            findings=_format_findings(signals.get("findings", [])),
            source_sample=signals.get("source_sample", "(no source available)"),
        )
        llm = get_llm()
        response = llm.invoke(prompt)
        result = _parse_llm_response(response.content)
        return result.get("job_designs") or []
    except Exception as e:
        print(f"[job_reasoning] LLM call failed: {e}")
        return []


def _fallback_design_from_coverages(coverages: list, detected_domain: str | None) -> list[dict]:
    """Deterministic fallback when LLM fails or returns no valid designs.

    The fallback is intentionally simpler than the AI-generated path:
    it produces a single job design that mirrors one of the static
    domain-specific templates but expressed as a `job_design` so the
    downstream `workflow_generator` can merge it into the YAML
    uniformly with the AI-generated path.

    v9.3 revisi 3-domain: only the 3 supported domains (e-commerce,
    blog, iot) get a domain-specific fallback. Any other (legacy)
    detected domain falls back to the highest-confidence applicable
    coverage.
    """
    applicable = [c for c in coverages if c.get("applicable")]
    if not applicable:
        return []
    target_coverage = None
    if detected_domain == "e-commerce" and any(c["id"] == "payment_security" for c in applicable):
        target_coverage = "payment_security"
    elif detected_domain == "blog" and any(c["id"] == "cms_security" for c in applicable):
        target_coverage = "cms_security"
    elif detected_domain == "iot" and any(c["id"] == "iot_security" for c in applicable):
        target_coverage = "iot_security"
    else:
        # Pick the highest-confidence applicable coverage.
        applicable.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        target_coverage = applicable[0]["id"]

    fallback = {
        "name": f"{target_coverage.replace('_', '-')}-check",
        "coverage": target_coverage,
        "reasoning": (
            f"Deterministic fallback for {target_coverage} coverage "
            f"(domain={detected_domain or 'general'}). LLM reasoning "
            f"was unavailable, so this design uses the standard "
            f"coverage-specific check pattern."
        ),
        "actions": [
            {
                "type": "shell_check",
                "name": f"Run {target_coverage} check",
                "script": (
                    "echo '::notice::Deterministic fallback for "
                    + target_coverage
                    + " — LLM reasoning unavailable.'\n"
                      "exit 0"
                ),
            },
            {
                "type": "sarif_upload",
                "category": target_coverage,
            },
        ],
        "configuration": {
            "continue_on_error": True,
            "timeout_minutes": 10,
        },
    }
    if _validate_job_design(fallback):
        return [fallback]
    return []


# ── Per-domain template designs ──────────────────────────────────────────
# v9.3 revisi 3-domain: setiap domain (e-commerce, blog, iot) punya 3
# deterministic template designs yang selalu di-emit untuk menjamin
# custom file punya cukup job. Template ini melengkapi AI-generated
# jobs (K2.4) ketika LLM tidak menghasilkan cukup designs.
#
# Naming: <domain>-<aspect>-<check> (kebab-case, ≤ 40 chars)
# Each design punya 2 actions (shell_check + sarif_upload) dan merujuk
# concrete code patterns untuk repo e-commerce/blog/iot.

_DOMAIN_TEMPLATE_DESIGNS: dict[str, list[dict]] = {
    "e-commerce": [
        {
            "name": "ecommerce-payment-stripe-webhook-verify",
            "coverage": "payment_security",
            "reasoning": (
                "Stripe webhook handler must verify the Stripe-Signature header "
                "using stripe.webhooks.constructEvent(). Without this, attacker "
                "can forge payment events and mark orders as paid. Targets "
                "src/routes/webhook.js atau src/controllers/payment.js."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-stripe-webhook-handler",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check webhook handler exists\n"
                        "if ! grep -rnE 'stripe\\.webhooks\\.constructEvent' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/routes/webhook.js::Stripe webhook signature not verified — use stripe.webhooks.constructEvent()'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Check Stripe API key loaded from env, not hardcoded\n"
                        "if grep -rnE 'sk_(live|test)_[A-Za-z0-9]{20,}' src/ 2>/dev/null | grep -v process.env | grep -q .; then\n"
                        "  echo '::error file=src/config/stripe.js::Hardcoded Stripe key found in source — move to process.env.STRIPE_SECRET_KEY'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-payment-stripe-webhook",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "ecommerce-cart-bola-ownership",
            "coverage": "api_security",
            "reasoning": (
                "Cart/order endpoints dengan path parameter :id rawan BOLA — "
                "attacker bisa akses cart customer lain dengan iterasi ID. "
                "Pastikan ada ownership check (userId match) sebelum return data."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-cart-order-ownership",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Find GET /cart/:id or GET /orders/:id routes\n"
                        "for route in cart orders; do\n"
                        "  if grep -rnE \"router\\.(get|post)\\s*\\(\\s*['\\\"]\\/?$route\\/:id\" src/ 2>/dev/null | grep -q .; then\n"
                        "    # Check if ownership verification is present in same file\n"
                        "    if ! grep -rnE '(req\\.user\\.id|userId|ownerId|verifyOwnership)' src/routes/$route.js 2>/dev/null | grep -q .; then\n"
                        "      echo \"::error file=src/routes/$route.js::$route route uses :id parameter without ownership verification — vulnerable to BOLA/IDOR\"\n"
                        "      fail=1\n"
                        "    fi\n"
                        "  fi\n"
                        "done\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-cart-bola",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "ecommerce-checkout-price-server-validate",
            "coverage": "payment_security",
            "reasoning": (
                "Harga di checkout harus dari database (product.price), bukan "
                "dari req.body.price. Attacker bisa kirim {price: 0} dan checkout "
                "murah. Cek endpoint POST /checkout dan pastikan price lookup server-side."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-checkout-price-from-body",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Look for direct req.body.price/amount usage in checkout logic\n"
                        "if grep -rnE 'req\\.body\\.(price|amount|total|grand_total)' src/routes/checkout.js src/controllers/checkout.js 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/routes/checkout.js::Price/amount read from req.body — fetch from DB (Product.findById(id).price) instead'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-checkout-price",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "ecommerce-pci-card-data-no-logging",
            "coverage": "payment_security",
            "reasoning": (
                "PCI DSS Req 3.2: nomor kartu kredit (PAN) tidak boleh di-log, "
                "di-print, atau di-store dalam bentuk cleartext. Cek console.log, "
                "logger.info, atau storage yang menerima req.body.card / pan."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-pci-card-data-leak",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Detect card-like fields passed to loggers or stored in plaintext\n"
                        "if grep -rnE '(console\\.log|logger\\.(info|debug|warn)|winston\\.log)\\s*\\([^)]*(card[_-]?number|pan|cvv|cvc)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/payments/log.ts::Card data (PAN/CVV) passed to logger — strip before logging (PCI DSS 3.2)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Detect card number variable in plain-text storage (localStorage, plaintext write)\n"
                        "if grep -rnE 'localStorage\\.setItem\\s*\\(\\s*[\"\\'][^\"\\']*(card|pan)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/checkout/cart.ts::Card data persisted to localStorage — never store PAN client-side'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-pci-card-logging",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "ecommerce-inventory-race-condition",
            "coverage": "api_security",
            "reasoning": (
                "Stock decrement tanpa atomic operation (SELECT FOR UPDATE / "
                "findOneAndUpdate dengan kondisi stock > 0) rentan race "
                "condition. Dua request paralel bisa menjual 1 barang yang sama "
                "berkali-kali. Target src/routes/checkout.js dan order placement."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-inventory-atomic-decrement",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Look for naive stock update without guard\n"
                        "if grep -rnE 'product\\.stock\\s*[-]=' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/services/inventory.ts::Stock decremented without atomic guard — use Product.findOneAndUpdate({stock:{$gt:0}}, {$inc:{stock:-1}})'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Look for read-then-write pattern (TOCTOU)\n"
                        "if grep -rnE 'await\\s+Product\\.findById.*\\n.*\\.stock' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/routes/checkout.js::Read-then-write stock check detected — race condition (CWE-367)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-inventory-race",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "ecommerce-refund-idor-protection",
            "coverage": "api_security",
            "reasoning": (
                "Endpoint POST /refund/:orderId dan POST /order/:id/cancel "
                "harus verify ownership dan status order (paid). Tanpa itu, "
                "attacker bisa refund order orang lain atau cancel pesanan "
                "lawan. Target src/routes/refund.js dan order cancellation."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-refund-ownership",
                    "script": (
                        "set -e\nfail=0\n"
                        "for route in refund cancel order; do\n"
                        "  if grep -rnE \"router\\.(post|put|delete)\\s*\\(\\s*['\\\"]\\/?$route\\/:id\" src/ 2>/dev/null | grep -q .; then\n"
                        "    if ! grep -rnE '(req\\.user\\.id|order\\.userId|verifyOwner|checkOwnership)' src/routes/ 2>/dev/null | grep -q .; then\n"
                        "      echo \"::error file=src/routes/$route.js::$route/:id endpoint missing ownership check — IDOR allows refund/cancel of other users' orders\"\n"
                        "      fail=1\n"
                        "    fi\n"
                        "  fi\n"
                        "done\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "ecommerce-refund-idor",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
    ],
    "blog": [
        {
            "name": "blog-markdown-sanitize",
            "coverage": "cms_security",
            "reasoning": (
                "Markdown rendering untuk post/comment harus pakai sanitizer "
                "(DOMPurify, sanitize-html) untuk mencegah stored XSS. "
                "Cek marked(content) atau marked.parse() tanpa DOMPurify.sanitize."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-markdown-no-sanitize",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Find marked() or markdown-it usage\n"
                        "if grep -rnE 'marked\\s*\\(' src/ 2>/dev/null | grep -vE 'DOMPurify|sanitize' | grep -q .; then\n"
                        "  echo '::error file=src/utils/markdown.js::marked() called without DOMPurify.sanitize — XSS via markdown'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Find innerHTML with user content\n"
                        "if grep -rnE 'innerHTML\\s*=\\s*\\$\\{?\\s*(content|post|comment|body)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/routes/posts.js::innerHTML assigned from user content — use textContent or DOMPurify'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-markdown-xss",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "blog-comment-csrf-auth",
            "coverage": "api_security",
            "reasoning": (
                "POST /comments dan /posts harus pakai CSRF protection dan "
                "authentication middleware untuk mencegah spam dan impersonation."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-comment-csrf-auth",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check CSRF middleware present\n"
                        "if ! grep -rnE '(csurf|csrf\\(\\)|doubleCsrf)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::warning file=src/server.js::No CSRF protection detected — install csurf or double-submit cookie pattern'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-csrf",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "blog-csp-security-headers",
            "coverage": "cms_security",
            "reasoning": (
                "Blog harus serve Content-Security-Policy header untuk mitigasi "
                "XSS. Cek helmet() middleware atau manual CSP header di server."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-csp-headers",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check helmet middleware\n"
                        "if ! grep -rnE 'helmet\\s*\\(' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::warning file=src/server.js::helmet() middleware missing — CSP/HSTS/X-Frame-Options not set'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-csp",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "blog-multer-upload-hardening",
            "coverage": "file_upload_security",
            "reasoning": (
                "Endpoint /upload (avatar, post image) rentan RCE dan DoS "
                "jika tidak ada filter tipe file, validasi MIME, dan size "
                "limit. Cek multer usage: harus pakai fileFilter, limits."
                "fileSize, dan storage yang tidak mengeksekusi upload."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-multer-config",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check multer config: fileFilter present\n"
                        "if grep -rnE \"multer\\s*\\(\" src/ 2>/dev/null | grep -q .; then\n"
                        "  if ! grep -rnE 'fileFilter' src/ 2>/dev/null | grep -q .; then\n"
                        "    echo '::error file=src/middleware/upload.js::multer() missing fileFilter — accepts any file type, risk of RCE via polyglot file'\n"
                        "    fail=1\n"
                        "  fi\n"
                        "  # Check size limit\n"
                        "  if ! grep -rnE 'limits.*fileSize' src/ 2>/dev/null | grep -q .; then\n"
                        "    echo '::warning file=src/middleware/upload.js::multer() missing limits.fileSize — no DoS protection on large uploads'\n"
                        "    fail=1\n"
                        "  fi\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-multer-hardening",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "blog-jwt-auth-hardening",
            "coverage": "authentication",
            "reasoning": (
                "JWT secret harus loaded dari env, di-sign dengan algoritma "
                "yang kuat (RS256/HS256 dengan secret >= 32 char), dan "
                "memvalidasi exp/aud. Cek jsonwebtoken.sign dan jwt.verify."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-jwt-weak-secret",
                    "script": (
                        "set -e\nfail=0\n"
                        "# JWT secret must come from env, not literal\n"
                        "if grep -rnE 'jwt\\.sign\\s*\\([^,]+,\\s*[\"\\'][A-Za-z0-9]{1,31}[\"\\']' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/auth/jwt.ts::JWT signed with short/hardcoded secret — use process.env.JWT_SECRET (>= 32 bytes)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# 'none' algorithm forbidden\n"
                        "if grep -rnE 'algorithm.*none|algorithms.*\\[.*none' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/auth/jwt.ts::JWT verify accepts alg=none — algorithm confusion attack (CVE-2015-9235)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-jwt-hardening",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "blog-open-redirect-prevention",
            "coverage": "cms_security",
            "reasoning": (
                "Login redirect (?next=, ?returnTo=) rawan open-redirect "
                "yang dipakai untuk phishing. Cek res.redirect(req.query.next) "
                "tanpa whitelist host."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-open-redirect",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Look for direct res.redirect(req.query.*) without validation\n"
                        "if grep -rnE 'res\\.redirect\\s*\\(\\s*req\\.query\\.(next|returnTo|redirect|url)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/routes/auth.js::res.redirect uses unvalidated user input — open-redirect phishing vector (CWE-601)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "blog-open-redirect",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
    ],
    "iot": [
        {
            "name": "iot-mqtt-tls-required",
            "coverage": "iot_security",
            "reasoning": (
                "MQTT broker connection HARUS pakai TLS (mqtts:// port 8883). "
                "mqtt:// tanpa TLS = data sensor terekspos di network. "
                "Cek client.connect() di semua device publisher/subscriber."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-mqtt-cleartext",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Find mqtt.connect('mqtt://...') without TLS\n"
                        "if grep -rnE 'mqtt\\.connect\\s*\\(\\s*[\"\\']mqtt://' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/mqtt-client.js::MQTT broker connected over cleartext (mqtt://) — use mqtts://port 8883'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Find paho-mqtt with mqtt://\n"
                        "if grep -rnE 'paho-mqtt.*\"mqtt://' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/device.js::paho-mqtt client uses cleartext mqtt:// — use ssl/tls context'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-mqtt-tls",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "iot-device-default-credentials",
            "coverage": "iot_security",
            "reasoning": (
                "Device provisioning tidak boleh hardcode default credentials "
                "(admin/admin, device/1234). Cek koneksi ke MQTT broker / device API."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-default-credentials",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Look for default credential patterns\n"
                        "if grep -rnE '[\"\\']admin[\"\\']\\s*:\\s*[\"\\']admin[\"\\']' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/provision.ts::Default admin/admin credentials hardcoded — load from secure provisioning'\n"
                        "  fail=1\n"
                        "fi\n"
                        "if grep -rnE '[\"\\']device[\"\\']\\s*:\\s*[\"\\']1234[\"\\']' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/provision.ts::Default device/1234 credentials hardcoded — use per-device certs'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-default-creds",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "iot-firmware-update-signature",
            "coverage": "iot_security",
            "reasoning": (
                "Firmware update endpoint harus verify signature sebelum flash. "
                "Cek path traversal di filename (firmware_path dari user input) "
                "dan HTTPS-only untuk download."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-firmware-update-path",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check for signature verification in firmware update path\n"
                        "if ! grep -rnE '(verify\\s*\\(|crypto\\.verify|ed25519\\.verify)' src/iot/firmware 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/firmware/update.ts::Firmware signature not verified before flash — use crypto.verify or ed25519'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Check for HTTP (not HTTPS) firmware download\n"
                        "if grep -rnE 'fetch\\s*\\(\\s*[\"\\']http://' src/iot/firmware 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/firmware/update.ts::Firmware downloaded over HTTP — use HTTPS only'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-firmware-update",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "iot-telemetry-encryption",
            "coverage": "iot_security",
            "reasoning": (
                "Telemetry data yang dikirim device ke cloud harus di-encrypt "
                "in transit (TLS, mqtts) dan sensor payload tidak boleh "
                "berisi PII atau credential cleartext. Cek publisher.publish() "
                "dan emit pattern untuk field sensitif."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-telemetry-pii",
                    "script": (
                        "set -e\nfail=0\n"
                        "# Check for PII fields in published payloads\n"
                        "if grep -rnE 'publish\\s*\\([^)]*(ssn|nik|phone|email|password|token)' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/telemetry.ts::Telemetry payload contains PII/credential fields — strip or encrypt before publish'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# Check that telemetry uses TLS port (8883/443) not 1883\n"
                        "if grep -rnE \"publish\\s*\\(\\s*['\\\"][^'\\\"]*://[^:]*:1883\" src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/telemetry.ts::Telemetry published to port 1883 (cleartext MQTT) — use mqtts://port 8883'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-telemetry-encryption",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "iot-command-injection-device",
            "coverage": "iot_security",
            "reasoning": (
                "Device command handler (shell exec, system call) rentan "
                "command injection jika input dari user (deviceId, firmwarePath, "
                "configName) di-interpolate langsung. OWASP IoT Top 10 #1. "
                "Cek child_process.exec, os.system, dan subprocess shell=True."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-device-cmd-injection",
                    "script": (
                        "set -e\nfail=0\n"
                        "# child_process.exec with template literal / concat\n"
                        "if grep -rnE 'child_process\\.(exec|execSync)\\s*\\(\\s*[`\\\"][^`\\\"]*\\$\\{' src/iot 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/command.ts::child_process.exec uses template interpolation — command injection (CWE-78)'\n"
                        "  fail=1\n"
                        "fi\n"
                        "# os.system / subprocess with shell=True and user input\n"
                        "if grep -rnE '(os\\.system|subprocess\\.call).*shell\\s*=\\s*True' src/iot 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/command.ts::subprocess call with shell=True — vulnerable to command injection'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-command-injection",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
        {
            "name": "iot-device-cert-rotation",
            "coverage": "iot_security",
            "reasoning": (
                "Device certificate / token tidak boleh hardcoded dan harus "
                "di-rotate. Cek long-lived static API key, sertifikat yang "
                "tidak ada expiry check, dan private key yang ter-commit. "
                "OWASP IoT Top 10 #2 — insecure network services."
            ),
            "actions": [
                {
                    "type": "shell_check",
                    "name": "scan-cert-hardcoded",
                    "script": (
                        "set -e\nfail=0\n"
                        # PEM private key in source
                        "if grep -rnE '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' src/ 2>/dev/null | grep -q .; then\n"
                        "  echo '::error file=src/iot/cert.ts::Private key embedded in source — use cert pinning + secure element, never commit keys'\n"
                        "  fail=1\n"
                        "fi\n"
                        # long-lived static token (>= 40 char literal)
                        "if grep -rnE '[\"\\'][A-Za-z0-9_-]{40,}[\"\\']' src/iot 2>/dev/null | grep -q .; then\n"
                        "  echo '::warning file=src/iot/device.ts::Long-lived static token literal detected — use short-lived JWT or cert with rotation'\n"
                        "  fail=1\n"
                        "fi\n"
                        "exit $fail\n"
                    ),
                },
                {
                    "type": "sarif_upload",
                    "category": "iot-cert-rotation",
                },
            ],
            "configuration": {
                "continue_on_error": True,
                "timeout_minutes": 10,
                "needs": ["sast"],
            },
        },
    ],
}


def _domain_template_designs(detected_domain: str | None) -> list[dict]:
    """Return the deterministic template designs for the detected domain.

    v9.3 revisi 3-domain: always returns 3 designs per supported domain.
    Each design is structurally valid (passes `_validate_job_design`)
    so the downstream `workflow_generator` will emit them.
    """
    if not detected_domain:
        return []
    templates = _DOMAIN_TEMPLATE_DESIGNS.get(detected_domain, [])
    return [dict(d) for d in templates if _validate_job_design(d)]


def job_reasoning_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """K2.4: LLM designs custom pipeline jobs tailored to this repository.

    Reads:
      - detected_technologies, detected_domain, features
      - security_coverages (applicable)
      - source_files
      - findings (source-scan findings)
      - pipeline_augmentations (already decided)

    Writes:
      - state.job_designs (validated list)
      - state.job_designs_reasoning
      - state.job_designs_valid_count
    """
    if state.get("errors"):
        print(
            f"[job_reasoning] running with prior errors: "
            f"{state['errors'][:2]}"
        )

    coverages = state.get("security_coverages") or []
    applicable = [c for c in coverages if c.get("applicable")]
    if not applicable:
        state["job_designs"] = []
        state["job_designs_reasoning"] = (
            "No applicable coverages — skipping AI job reasoning"
        )
        state["job_designs_valid_count"] = 0
        return state

    technologies = state.get("detected_technologies") or {}
    deployment = state.get("detected_deployment") or {}

    signals = {
        "primary_language": technologies.get("primary_language"),
        "frameworks": technologies.get("frameworks", []),
        "architecture_type": state.get("detected_architecture_type") or "monolithic",
        "detected_domain": state.get("detected_domain"),
        "sub_type": state.get("domain_sub_type"),
        "deployment": deployment,
        "features": state.get("features", []),
        "coverages": applicable,
        "findings": state.get("findings", []) or [],
        "source_sample": _extract_source_sample(state.get("source_files", []) or []),
    }

    raw_designs = _llm_design_jobs(signals)

    validated: list[dict] = []
    rejected: list[dict] = []
    seen_names: set[str] = set()
    for design in raw_designs:
        if _validate_job_design(design) and design["name"] not in seen_names:
            validated.append(design)
            seen_names.add(design["name"])
        else:
            rejected.append(design)

    # v9.3 revisi 3-domain: gabungkan AI-generated designs dengan
    # per-domain template designs (3 templates per domain) supaya
    # custom file selalu punya minimal 3 job designs. Template
    # jobs diberi suffix deterministik dan di-skip kalau namanya
    # sudah ada di validated (no duplicate).
    detected_domain = state.get("detected_domain")
    template_designs = _domain_template_designs(detected_domain)
    templates_added = 0
    for tpl in template_designs:
        if tpl["name"] in seen_names:
            continue
        validated.append(tpl)
        seen_names.add(tpl["name"])
        templates_added += 1

    # Cap total at 10 designs (AI up to 3 + templates up to 3, but
    # duplicates collapse so the cap is rarely hit). This keeps the
    # PR diff readable while ensuring meaningful coverage.
    validated = validated[:10]

    # Legacy fallback (single design) when nothing else applied.
    fallback_used = False
    if not validated:
        fallback = _fallback_design_from_coverages(
            applicable, state.get("detected_domain")
        )
        if fallback:
            validated = fallback
            fallback_used = True

    state["job_designs"] = validated
    state["job_designs_reasoning"] = (
        f"LLM produced {len(raw_designs)} raw job designs; "
        f"{len(validated)} valid ({len(rejected)} rejected). "
        f"Domain: {state.get('detected_domain') or 'general'}, "
        f"applicable coverages: {len(applicable)}. "
        f"Domain templates added: {templates_added}. "
        + ("Legacy fallback path used." if fallback_used else "")
    ).strip()
    state["job_designs_valid_count"] = len(validated)

    return state
