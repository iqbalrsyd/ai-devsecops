# Struktur Naskah v9.3 — Repository-Context-Aware Security Coverage Pipeline

**Versi:** 26 Juni 2026 — struktur v9.3 (sinkron penuh dengan runtime `ai-service/app/agents/`)
**Arsitektur:** 4 Tahapan, 18 Node Compiled, 11 LLM Calls
**Kontribusi (K2 v9.1 + v9.2):** Repository-Context-Aware Security Coverage Pipeline — dari konteks repositori → 15 security coverages → 4 generative LLM steps (augmentation + pattern + job design + workflow) → deterministic YAML emitter → PR → security scoring.

---

## Ringkasan Perubahan dari v8 → v9 → v9.3

| Aspek | v8 | v9 (23 Juni) | v9.3 (sekarang) |
|---|---|---|---|
| Jumlah node compiled | 16 | 18 (+2) | 18 (sama) |
| Tahapan | 4 | 4 | 4 |
| LLM calls | 8 | 9 (+1) | **11** (+2) |
| Tahap 2 logic | 1 prompt gabung controls+stages+tools | 2 LLM terpisah | **4 LLM** (coverage + pattern + augmentation + job_reasoning) |
| Coverage concept | Tidak ada | 15 security coverages composable | 15 security coverages composable |
| Augmentation concept | Tidak ada | Per-coverage job+configuration | Per-coverage job+configuration |
| AI-generated Semgrep rules | Tidak ada | Tidak ada | **K2.3** `pattern_inference` (LLM-generated repo-specific rules) |
| AI-generated CI jobs | Tidak ada | Tidak ada | **K2.4** `job_reasoning` (LLM-designed custom jobs beyond standard 8) |
| Node name | `security_requirement_inference` | `coverage_inference` + `pipeline_augmentation` | **+ `pattern_inference` + `job_reasoning`** |
| Finding metadata | `security_coverage: None` | `security_coverage: <coverage_id>` per finding | Sama |
| Custom Semgrep rules | Static (Tier 1) | Static (Tier 1) | **Tier 1 + K2.3 LLM-generated** merged ke `.github/ai-devsecops-rules.yml` |
| PDF report | 4 sections | 5 sections | 5 sections (+ Section 5: Coverages Applied) |

---

## Empat Tahapan (18 node, 11 LLM calls)

```
Tahap 1: Repository Context Analysis        (6 node, 4 LLM)
Tahap 2: Security Coverage Inference       (4 node, 4 LLM) ← DIUBAH dari v9 (2 node)
Tahap 3: Pipeline Generation & Deployment   (5 node, 1 LLM dormant)
Tahap 4: Security Evaluation                (3 node, 2 LLM)
```

### Tahap 1: Repository Context Analysis (6 node, 4 LLM)

| # | Node | Tipe | LLM? |
|---|------|------|------|
| 1 | `repository_connection` | Deterministic | — |
| 2 | `repository_scan` | Deterministic | — |
| 3 | `technology_detection` | LLM + extension fallback | ✅ |
| 4 | `architecture_detection` | LLM only | ✅ |
| 5 | `deployment_detection` | Hybrid (file scan + LLM) | ✅ |
| 6 | `domain_detection` | Hybrid (heuristic + LLM) | ✅ |

Output Tahap 1: `detected_technologies`, `detected_architecture`, `detected_architecture_type`, `detected_deployment`, `recommended_deployment_target`, `detected_domain`, `domain_sub_type`, `domain_confidence`, `domain_evidence`, **`domain_threats[]`**, **`features[]`**.

### Tahap 2: Security Coverage Inference (4 node, 4 LLM) ← DIUBAH dari v9

| # | Node | Tipe | Fungsi |
|---|------|------|--------|
| 7 | `coverage_inference` | LLM + heuristic fallback | Repo context → applicable security coverages (15 types) |
| 8 | `pattern_inference` (K2.3) | LLM + structural validation | Repo-specific Semgrep rules (from source sample + static rules avoidance) |
| 9 | `pipeline_augmentation` | LLM + static library fallback | Coverages → control augmentations (job + configuration) |
| 10 | `job_reasoning` (K2.4) | LLM + deterministic fallback | Coverages → custom CI job designs (kebab-case, SARIF-upload, max 3 jobs) |

**Urutan eksekusi:** `coverage_inference → pattern_inference → pipeline_augmentation → job_reasoning`

Alasan urutan: `pattern_inference` (K2.3) perlu hasil `coverage_inference` (untuk prefix `ai-{cov}-{slug}`) + `pipeline_augmentation` (untuk augmentations) memberi daftar job + configuration. `job_reasoning` (K2.4) menjadi yang terakhir karena butuh `ai_generated_rules` + `pipeline_augmentations` + `findings` (jika ada) untuk design custom job yang complementary.

#### Coverage Library (15 coverages)

| ID | Deskripsi | Sinyal Deteksi |
|----|---|----|
| `authentication_security` | Auth, session, JWT, OAuth | libs: passport, jsonwebtoken, jwt, bcrypt, auth0, oauth; routes: /login, /signup, /auth; entities: user, session |
| `api_security` | REST/GraphQL, OWASP API Top 10 | libs: express, fastify, nestjs, koa, graphql, apollo; routes: /api, /v1/, /graphql; entities: controller, endpoint |
| `data_security` | Database, ORM, SQL injection | libs: sequelize, prisma, mongoose, typeorm, mysql, pg, sqlite, mongodb; entities: db, model, schema |
| `payment_security` | Payment, PCI-DSS | libs: stripe, midtrans, xendit, doku, paypal, braintree, razorpay, adyen; routes: /checkout, /payment, /billing; entities: order, invoice, transaction |
| `container_security` | Docker, image | deployment: docker, docker_compose |
| `iot_security` | MQTT, sensor, firmware | libs: mqtt, paho-mqtt, amqp, coap, modbus; entities: device, sensor, telemetry |
| `logging_security` | App logging | libs: winston, bunyan, pino, log4j, logrus, morgan |
| `file_upload_security` | Multipart upload | libs: multer, formidable, busboy, sharp; routes: /upload, /files |
| `healthcare_security` | PHI, FHIR, HIPAA | libs: fhir, hl7, hapi-fhir; entities: patient, prescription, ehr; domain=healthcare |
| `fintech_security` | Ledger, banking, KYC | libs: plaid, open-banking, dwolla; entities: ledger, transfer, wallet, kyc |
| `cms_security` | Blog post, comment | libs: marked, dompurify, ghost; entities: post, comment, article; domain=blog |
| `education_security` | LMS, course | libs: moodle-sdk, scorm, canvas-lms; entities: course, enrollment, quiz; domain=education |
| `microservice_security` | Service-to-service, mTLS | architectures: microservices, modular_monolith; libs: istio, linkerd |
| `csp_security` | Content Security Policy | libs: helmet, csp, express-helmet |
| `dependency_security` | SCA, CVEs | package_managers: npm, yarn, pip, go mod, cargo |

#### Augmentation Library (per coverage)

| Coverage | Augmentations (job, configuration) |
|----------|-------------------------------------|
| `authentication_security` | sast (p/secrets), secret_scan (focus: JWT/OAuth) |
| `api_security` | sast (p/owasp-top-ten, p/javascript, p/nodejs, owasp-api.yml) |
| `data_security` | sast (p/sql-injection), sca (DB driver CVE) |
| `payment_security` | sast (pci-dss.yml), secret_scan (focus: stripe/midtrans/xendit) |
| `container_security` | container_scan (trivy image + Dockerfile) |
| `iot_security` | sast (iot-mqtt.yml), secret_scan (device creds) |
| `logging_security` | sast (sensitive-data-in-logs.yml), sca |
| `file_upload_security` | sast (path-traversal.yml, file-upload-bypass.yml) |
| `healthcare_security` | sast (hipaa.yml), secret_scan (FHIR keys) |
| `fintech_security` | sast (fintech-ledger.yml), secret_scan (banking keys) |
| `cms_security` | sast (blog-csp.yml), sca (markdown CVEs) |
| `education_security` | sast (education-lms.yml) |
| `microservice_security` | docker_compose_validate, dependency_scan_per_service |
| `csp_security` | sast (csp-header-check.yml) |
| `dependency_security` | sca (npm audit / pip-audit / govulncheck) |

### Tahap 3: Pipeline Generation & Deployment (5 node, 1 LLM)

| # | Node | Tipe | Fungsi |
|---|------|------|--------|
| 11 | `workflow_generation` | **Deterministic** | Compose YAML dari standard 8 jobs + domain jobs + AI-generated jobs (dari `job_reasoning`) |
| 12 | `workflow_validation` | Deterministic | Pre-flight checks (action pinning, permissions, concurrency) — non-blocking |
| 13 | `workflow_repair` | LLM (dormant) | Auto-repair invalid YAML (short-circuit kalau `validation_errors` kosong) |
| 14 | `github_branch_creation` | Deterministic | Buat branch `ai-devsecops/generate-workflow-{ts}` |
| 15 | `pull_request_creation` | Deterministic | Commit workflow + `.github/ai-devsecops-rules.yml` (custom Semgrep) + buka PR |

**Standard 8 jobs (library):** lint, test, build, sast, dependency-scan, secret-scan, container-build, container-scan

**Domain-specific jobs (ALLOWED_STAGES):** pci-dss, hipaa, ledger-check, csp-headers, mqtt-security, docker-compose-validate, dependency-scan-per-service

**AI-generated jobs (dari `job_reasoning`):** kebab-case name, max 3 per run, setiap job punya ≥ 2 actions + 1 `sarif_upload`.

**Custom Semgrep rules (`.github/ai-devsecops-rules.yml`):**
- Tier 1: static `.yml` (owasp-api, ecommerce, pci-dss, hipaa, fintech-ledger, iot-mqtt, blog-csp) — dipilih via `domain_detection`.
- K2.3 (LLM-generated): `ai-{cov}-{slug}` rules dari `pattern_inference_node`.
- Merger: `_collect_merged_semgrep_rules()` di `workflow_generator.py:2405` → 1 file YAML di-commit terpisah (untuk hindari 21K char limit per expression di workflow YAML).

### Tahap 4: Security Evaluation (3 node, 2 LLM)

| # | Node | Tipe | Fungsi |
|---|------|------|--------|
| 16 | `security_analysis` | Hybrid (deterministic + LLM enrichment) | Normalisasi SARIF findings + OWASP L×I + `security_coverage` per finding + domain priority elevation |
| 17 | `recommendation_generation` | LLM + fallback | Actionable fix recommendations + before/after code examples |
| 18 | `response_formatter` | Deterministic | Unified response + PDF report (5 sections) |

---

## Detail Setiap Node: Input + Output + Prompt

> **Catatan:** Semua node baca dari TypedDict `PipelineEngineerState` (lihat `app/agents/pipeline_state.py`). Semua LLM pakai `get_llm()` dari `app/services/llm_service.py` (provider configurable via `LLM_PROVIDER` env: openai/anthropic/openrouter/opencode/google).

---

### TAHAP 1

#### Node 1: `repository_connection`
- **File:** `nodes/repository_connection_node.py`
- **Type:** Deterministic
- **LLM:** N/A
- **Input:** `repository_full_name`, `github_token`
- **Output:** `repository_url`, `repository_default_branch`, `repository_description`, `repository_name`, `raw_io` (init `{}`), `errors`/`error_stage="connection"` (on failure)
- **Prompt:** N/A
- **Fallback:** No LLM. Append `errors` if missing fields, `f"GitHub connection failed: {e}"` on API exception.

#### Node 2: `repository_scan`
- **File:** `nodes/repository_scan_node.py`
- **Type:** Deterministic
- **LLM:** N/A
- **Input:** `repository_full_name`, `github_token`, `errors` (short-circuit if non-empty)
- **Output:** `repository_structure` (tree), `repository_files` (key files dict), `existing_workflows`, `source_files` (capped 30 files × 50KB each)
- **Prompt:** N/A
- **Fallback:** Per-helper `try/except` returns `[]` / `{}`. Top-level → `f"Repository scan failed: {e}"` to `errors`, `error_stage="scan"`.

#### Node 3: `technology_detection` (LLM #1)
- **File:** `nodes/technology_detection_node.py`
- **Type:** LLM + extension-based fallback
- **LLM:** `get_llm()` (configurable provider)
- **Input:** `repository_structure`, `repository_files`, `existing_workflows`
- **Output:** `detected_technologies` (dict: `primary_language`, `primary_language_confidence`, `primary_language_reason`, `frameworks`, `framework_confidences`, `build_tools`, `package_manager`, `package_manager_confidence`, `test_framework`, `database`, `runtime`)
- **Prompt (verbatim):**
```
You are a DevSecOps engineer analyzing a GitHub repository.

Given the repository files and structure below, identify the technology stack with confidence scores.

Repository structure:
{structure}

Key files found:
{files}

Existing workflows:
{workflows}

Analyze the files and identify:
- primary_language: the main programming language (e.g. "TypeScript", "Python", "Go", "Java", "Rust")
- primary_language_confidence: confidence score 0.0-1.0 based on evidence (file counts, build configs)
- primary_language_reason: brief explanation of why this language was detected
- frameworks: list of web/app frameworks detected (e.g. ["React", "Express", "Django"])
- framework_confidences: confidence scores for each framework 0.0-1.0
- build_tools: list of build tools detected (e.g. ["Vite", "npm", "tsc", "webpack"])
- package_manager: the package manager used (e.g. "npm", "pip", "go mod", "maven")
- package_manager_confidence: confidence score 0.0-1.0
- test_framework: the testing framework (e.g. "Vitest", "Jest", "pytest") or null if not detected
- database: primary database if detected (e.g. "PostgreSQL", "MongoDB", "Redis") or null
- runtime: runtime environment if detected (e.g. "Node.js 20", "Python 3.11", "Go 1.22") or null

Return ONLY valid JSON matching this schema. Be precise based on actual files.
```
- **Fallback (2 layers):** (a) If LLM `primary_language` empty → `_detect_from_extensions()` (extension-based, confidence ≤ 0.6). (b) On JSON parse fail after 3 retries → extension-only fallback. Else → `warnings` only.

#### Node 4: `architecture_detection` (LLM #2)
- **File:** `nodes/architecture_detection_node.py`
- **Type:** LLM only
- **LLM:** `get_llm()`
- **Input:** `repository_structure`, `detected_technologies`
- **Output:** `detected_architecture` (dict), `detected_architecture_type`, `detected_architecture_confidence`, `detected_architecture_reason`
- **Prompt (verbatim):**
```
You are a DevSecOps engineer analyzing application architecture.

Given the repository structure and detected technologies, determine the application architecture with confidence scores.

Repository structure:
{structure}

Detected technologies:
{technologies}

Analyze the architecture and return JSON with:
- architecture_type: one of "monolithic", "frontend_backend", "microservices", "modular_monolith", "serverless", "library"
- architecture_confidence: confidence score 0.0-1.0 based on evidence
- architecture_reason: explanation of why this architecture was chosen
- service_count: number of distinct services/applications detected (integer, null if unknown)
- service_names: list of service names if microservices/modular_monolith detected, null otherwise
- has_api_gateway: boolean
- has_message_queue: boolean
- has_database_config: boolean
- is_containerized: boolean
- has_shared_libraries: boolean (true if multiple services share common libraries/packages)

Key distinction for modular_monolith:
- Multiple services/directories exist but share database or are deployed together
- NOT microservices (no independent deployment, no service mesh)
- Has clear separation of concerns but tight coupling
- Example: backend/api + frontend + worker all in one repo with shared DB

Return ONLY valid JSON. No markdown.
```
- **Fallback:** No hard deterministic. On JSON fail → `warnings` only. `detected_architecture` stays at default `"monolithic"`.

#### Node 5: `deployment_detection` (LLM #3, hybrid)
- **File:** `nodes/deployment_detection_node.py`
- **Type:** Hybrid (deterministic file scan + LLM enrichment)
- **LLM:** `get_llm()`
- **Input:** `repository_structure`, `repository_files`, `existing_workflows`
- **Output:** `detected_deployment` (dict: `docker`, `docker_confidence`, `docker_reason`, `docker_compose`, `docker_compose_confidence`, `recommended_deployment_target`, `alternative_deployment_targets`, `deployment_reason`), `recommended_deployment_target`
- **Prompt (verbatim):**
```
You are a DevSecOps engineer analyzing deployment infrastructure.

Given the repository structure and files, detect DOCKER presence only (struktur-v8).

Repository structure:
{structure}

Key files:
{files}

Existing workflows:
{workflows}

Analyze and return JSON with:
- docker: boolean, true if Dockerfile detected
- docker_confidence: confidence score 0.0-1.0
- docker_reason: explanation of Docker detection
- docker_compose: boolean, true if docker-compose.yml detected
- docker_compose_confidence: confidence score 0.0-1.0
- recommended_deployment_target: "docker" if Dockerfile present, "generic" otherwise
- alternative_deployment_targets: ["docker-compose"] if both docker + compose present, else []
- deployment_reason: explanation

Note (struktur-v8 scope): Only Docker and Docker Compose are in scope.
Kubernetes, Terraform, and Helm are NOT detected by this node.

Return ONLY valid JSON. No markdown.
```
- **Fallback:** `_detect_from_files()` runs first → file-pattern result. If LLM fails (JSON decode or other), file-based result kept verbatim, warning appended. On LLM success, LLM dict merged on top via `{**file_result, **llm_result}`.

#### Node 6: `domain_detection` (LLM #4, hybrid)
- **File:** `nodes/domain_detection_node.py`
- **Type:** Hybrid (deterministic heuristic + LLM classification, multi-layer fallback)
- **LLM:** `get_llm()`
- **Input:** `repository_name`, `repository_full_name`, `repository_description`, `repository_files` (for library extraction), `source_files` (for entity/route extraction)
- **Output:** `detected_domain`, `domain_sub_type`, `domain_confidence`, `domain_evidence`, `domain_threats`, `features`
- **Prompt (verbatim):**
```
You are classifying the web application domain of a GitHub repository.

Based on the following signals, classify the domain into ONE of:
- e-commerce
- healthcare
- fintech
- blog
- iot
- education
- general (fallback when no clear domain signal)

When domain is "e-commerce", also identify the payment processor (sub_type):
- "stripe"   - Stripe, @stripe/stripe-js, stripe-node
- "midtrans" - midtrans-client, @midtrans/midtrans-node (Indonesia)
- "xendit"   - xendit-node, xendit (Indonesia)
- "doku"     - doku-node (Indonesia)
- "paypal"   - paypal-rest-sdk, paypal
- "braintree" - braintree
- "razorpay" - razorpay (India)
- "adyen"    - adyen
- "square"   - square
- "multi"    - multiple payment processors detected
- "unknown"  - e-commerce but cannot determine processor
- "none"     - not e-commerce

ALSO identify the business features present in the application.
Available features (choose any that match the codebase):
- authentication (login, signup, session, JWT, OAuth)
- catalog (product listing, search, browse)
- shopping_cart (add-to-cart, cart management)
- checkout (checkout flow, order summary)
- payment (payment processing, payment gateway integration)
- order_management (order history, order tracking)
- database (DB models, migrations, ORM usage)
- file_upload (file/image upload, multipart handling)
- mqtt (MQTT pub/sub, paho-mqtt)
- telemetry (sensor data, telemetry stream)
- firmware (firmware update, device flashing)
- device_management (device registration, provisioning)
- patient_records (PHI, EHR, medical records)
- appointment_scheduling (booking, calendar)
- prescription (e-prescription, drug management)
- course_management (course CRUD, syllabus)
- enrollment (course enrollment, registration)
- quiz_assessment (quiz, exam, grading)
- blog_posting (post creation, article management)
- comment_system (comments, replies)
- transaction (transfer, payment transaction)
- ledger (ledger, accounting, balance)

Repository name: {repo_name}
Repository description: {repo_description}

Detected libraries (top 50): {libraries}
Detected entity/model names (top 30): {entities}
Detected route hints (top 30): {routes}

Candidate domain scores from deterministic signal matching:
{scores}

Return ONLY valid JSON:
{{
  "domain": "e-commerce|healthcare|fintech|blog|iot|education|general",
  "sub_type": "stripe|midtrans|xendit|doku|paypal|braintree|razorpay|adyen|square|multi|unknown|none",
  "confidence": 0.0-1.0,
  "evidence": ["evidence 1", "evidence 2", ...],
  "domain_threats": ["threat 1 specific to this domain", ...],
  "features": ["authentication", "checkout", ...]
}}
```
- **Fallback (7 layers):** (1) LLM exception → `_llm_classify` returns `{}`. (2) LLM confidence < 0.5 OR failed → check `_score_domain_raw()`. If raw ≥ 1.0 → use that domain with confidence `min(1.0, max(0.55, raw*0.3+0.4))`. If 0 < raw < 1.0 → use domain with confidence 0.55. Else → `"general"` with confidence 1.0. (3) LLM said "general" but heuristic strong → override. (4) Disagreement + low LLM confidence + strong heuristic → trust heuristic. (5) `domain_threats` → fallback to `DOMAIN_LIBRARY_INDICATORS` static list. (6) `sub_type` → `_infer_payment_processor()` deterministic library scan. (7) `features` → `_fallback_features()` heuristic.

> **GAP v9.3:** `domain_threats[]` di-generate di Node 6 tapi **tidak dipakai** oleh `pattern_inference_node` (K2.3) atau node lain. Ini kandidat ekstensi prompt K2.3 di v9.4.

---

### TAHAP 2

#### Node 7: `coverage_inference` (LLM #5)
- **File:** `nodes/coverage_inference_node.py`
- **Type:** Hybrid (deterministic scoring + LLM, with deterministic fallback)
- **LLM:** `get_llm()`
- **Input:** `repository_full_name`, `detected_technologies`, `detected_architecture`, `detected_architecture_type`, `detected_deployment`, `detected_domain`, `domain_confidence`, `features`, `repository_files` (package manifests), `source_files`, `repository_name`, `repository_description`
- **Output:** `security_coverages` (15-element list, each `{id, applicable, reason, confidence}`), `coverage_inference_reasoning`
- **Prompt (verbatim):**
```
You are a Security Coverage Inference Engine.

Given the repository context, determine which security coverages apply.

## Repository Context

Architecture: {architecture}
Framework: {framework}
Deployment: {deployment}
Detected Domain: {domain} (confidence: {domain_confidence})
Business Features: {features}
Libraries (top 30): {libraries}
Entities (top 20): {entities}
Routes (top 20): {routes}

## Available Security Coverages

{coverage_library}

## Heuristic Scores (from deterministic signal matching)

{heuristic_scores}

## Task

For each coverage, decide:
1. Is it applicable to this repository?
2. Why (cite concrete signals: library, entity, route, deployment)?

Be strict. Only mark a coverage as applicable if you can cite a clear
signal. When in doubt, mark it as not applicable.

## Return ONLY valid JSON

{{
  "security_coverages": [
    {{
      "id": "<coverage_id>",
      "applicable": true,
      "reason": "concrete evidence (e.g. 'Stripe SDK in dependencies, /checkout route detected')"
    }},
    {{
      "id": "<coverage_id>",
      "applicable": false,
      "reason": "no signal (e.g. 'no MQTT library, no sensor entity')"
    }}
  ]
}}
```
- **Fallback:** `_fallback_coverages_from_heuristic()` — if heuristic score ≥ 1.0, mark coverage applicable with `confidence = min(1.0, score*0.2+0.5)`. Otherwise not applicable. Output always normalised to 15-element list.

#### Node 8: `pattern_inference` (LLM #6, K2.3) ← BARU v9.1
- **File:** `nodes/pattern_inference_node.py`
- **Type:** LLM with structural validation
- **LLM:** `get_llm()`
- **Input:** `detected_technologies`, `detected_domain`, `features`, `security_coverages` (only applicable), `domain_sub_type`, `detected_architecture_type`, `source_files`
- **Output:** `ai_generated_rules` (validated list), `pattern_inference_reasoning`, `pattern_inference_valid_count`
- **Prompt (verbatim):**
```
You are a Semgrep rule author specialising in
{domain} web application security.

Generate adaptive Semgrep rules tailored to THIS repository's patterns.
The static rules already cover generic OWASP API + domain patterns, so
focus on project-specific patterns that the static library cannot catch.

## Repository Context

Language: {language}
Frameworks: {frameworks}
Domain: {domain}
Sub-type: {sub_type}
Package Manager: {package_manager}
Architecture: {architecture}

## Business Features (from domain_detection)

{features}

## Applicable Security Coverages

{coverages}

## Sample Routes (extracted from source)

{routes_sample}

## Sample Source Code Snippets

{source_sample}

## Static Rules Already Committed (do NOT duplicate these)

{static_rules}

## Task

Generate adaptive Semgrep rules that target THIS repository's
project-specific patterns. The rules should catch vulnerabilities
that the static library cannot, such as:

1. **Project-specific URL routing patterns** (e.g. NestJS decorators,
   FastAPI path parameters, Express middleware chains)
2. **Custom authentication/authorization logic** (e.g. custom JWT
   verification, custom role checks, custom session handling)
3. **Project-specific business logic vulnerabilities** (e.g. custom
   pricing logic, custom discount calculations, custom payment
   processing)
4. **Library-specific misuse patterns** (e.g. incorrect usage of
   Stripe SDK, Sequelize transactions, Mongoose queries)
5. **Domain-specific data flow** (e.g. PHI in error messages, PII
   in logs, payment data in cookies)

Each rule MUST have:
- id: `ai-{coverage_id}-{slug}` (e.g. `ai-payment-stripe-charge-no-idempotency`)
- message: clear description of what the rule detects
- severity: ERROR | WARNING | INFO
- languages: list of languages
- patterns: Semgrep pattern syntax (pattern-either / pattern / pattern-regex)
- metadata.cwe: CWE id
- metadata.owasp: OWASP category
- metadata.ai-devsecops-coverage: which security coverage this rule supports
- metadata.ai-devsecops-reasoning: 1-sentence explanation of why this
  rule is needed for this repo

## Constraints

- DO NOT duplicate any rule from the static library
- DO NOT invent vulnerabilities that don't apply to this repo
- Each rule MUST be syntactically valid Semgrep YAML
- Pattern MUST match real code in the repository (when possible)
- Be conservative — better to generate 3 good rules than 10 noisy ones

## Return ONLY valid JSON

{{
  "ai_generated_rules": [
    {{
      "id": "ai-{coverage}-{slug}",
      "message": "...",
      "severity": "ERROR",
      "languages": ["javascript"],
      "patterns": [
        {{"pattern": "..."}}
      ],
      "metadata": {{
        "cwe": "CWE-XXX",
        "owasp": "A0X:2021",
        "ai-devsecops-coverage": "...",
        "ai-devsecops-reasoning": "..."
      }}
    }}
  ]
}}
```
- **Source extraction:** `_extract_sample_routes()` (regex `@(Get|Post|...)(...)` dari source) + `_extract_source_sample()` (prioritas file dengan keyword `route/controller/handler/auth/middleware/...`, max 8KB chars).
- **Static rules avoidance:** `_list_static_rule_ids()` baca semua `.yml` di `app/agents/semgrep_rules/`, kirim list ID ke LLM.
- **Validation:** `_validate_ai_generated_rule()` (id pattern `^ai-[a-z_]+-[a-z0-9-]+$`, severity in `ERROR/WARNING/INFO/INFORMATION`, non-empty languages/patterns, message ≥ 10 chars).
- **Fallback:** If no applicable coverages → skip (return empty). On LLM exception → `_fallback_empty()`. Invalid rules silently rejected (counter incremented).

#### Node 9: `pipeline_augmentation` (LLM #7)
- **File:** `nodes/pipeline_augmentation_node.py`
- **Type:** LLM + static library fallback per coverage
- **LLM:** `get_llm()`
- **Input:** `security_coverages` (only applicable), `detected_technologies` (language, package_manager), `detected_architecture_type`, `detected_deployment`, `detected_domain`
- **Output:** `pipeline_augmentations` (list of `{coverage, job, configuration, reason}`), `inferred_security_needs` (dict: `security_controls`, `required_tools`, `pipeline_stages`, `security_coverages`, `pipeline_augmentations`)
- **Prompt (verbatim):**
```
You are an Adaptive DevSecOps Pipeline Composer.

Given applicable security coverages, determine which controls/jobs to
add to the pipeline and their configuration.

## Repository Context

Primary Language: {language}
Package Manager: {package_manager}
Architecture: {architecture}
Deployment: {deployment}
Detected Domain: {domain}

## Applicable Security Coverages

{coverages}

## Available Controls / Jobs

- sast (Semgrep, with ruleset configuration)
- sca (dependency scan, with ecosystem-specific tool)
- secret_scan (gitleaks, with focus list)
- container_scan (trivy image + Dockerfile)
- iac_scan (trivy config + checkov)
- compliance_check (PCI-DSS, HIPAA, etc.)
- docker_compose_validate
- dependency_scan_per_service (matrix strategy)

## Task

For each applicable coverage, determine:
1. Which control/job to add.
2. The configuration (ruleset, focus list, etc.).
3. Why this augmentation makes sense for the repo context.

Be specific. For example, for payment_security with Stripe detected,
the secret_scan should focus on stripe, midtrans, xendit keys.

## Return ONLY valid JSON

{{
  "pipeline_augmentations": [
    {{
      "coverage": "<coverage_id>",
      "job": "<control>",
      "configuration": "<specific config>",
      "reason": "<why this augmentation>"
    }}
  ]
}}
```
- **Fallback (2 layers):** (1) LLM returns no augmentation for a coverage → static `DEFAULT_AUGMENTATIONS` dict (15 coverage keys × predefined job/config tuples) consulted, reason `"Default augmentation for {cov_id} coverage (LLM did not produce one)"`. (2) After LLM+default merge, augmentations validated against `valid_jobs = {"sast", "sca", "secret_scan", "container_scan", "compliance_check", "docker_compose_validate", "dependency_scan_per_service"}` — anything outside dropped. Base controls (`lint`, `sast`, `secret_scan`) always prepended.

#### Node 10: `job_reasoning` (LLM #8, K2.4) ← BARU v9.2
- **File:** `nodes/job_reasoning_node.py`
- **Type:** LLM + deterministic fallback
- **LLM:** `get_llm()`
- **Input:** `security_coverages` (only applicable), `detected_technologies`, `detected_architecture_type`, `detected_deployment`, `detected_domain`, `domain_sub_type`, `features`, `findings`, `source_files`
- **Output:** `job_designs` (validated list, capped at 3), `job_designs_reasoning`, `job_designs_valid_count`
- **Prompt (verbatim):**
```
You are a senior DevSecOps Pipeline Architect.

Analyse the repository's source code and design custom CI/CD pipeline
jobs that are SPECIFIC to the codebase — not generic domain templates.

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
        "timeout_minutes": 10,
        "needs": ["sast"]
      }}
    }}
  ]
}}
```
- **Fallback:** `_fallback_design_from_coverages()` — pick target coverage based on domain (`payment_security` for e-commerce, `healthcare_security` for healthcare, `fintech_security` for fintech), else highest-confidence applicable coverage. Emit single deterministic job with `shell_check` (echo + exit 0) + `sarif_upload`. Validated by `_validate_job_design()` (name regex `^[a-z][a-z0-9-]{1,39}$`, name not in `STANDARD_JOBS`, reasoning ≥ 30 chars, ≥ 2 actions, exactly one `sarif_upload`). Capped at 3 designs.

---

### TAHAP 3

#### Node 11: `workflow_generation` (Deterministic) ← `LLM prompt defined tapi tidak pernah dipanggil`
- **File:** `nodes/workflow_generator.py` (5808 baris)
- **Type:** Deterministic (despite importing `get_llm` + defining `WORKFLOW_GEN_PROMPT`)
- **Input:** `detected_technologies`, `detected_architecture`, `detected_architecture_type`, `detected_deployment`, `inferred_security_needs`, `findings`, `repository_structure`, `repository_files`, `detected_domain`, `domain_confidence`, `domain_threats`, `pipeline_augmentations`, `security_coverages`, `ai_generated_rules`, `job_designs`
- **Output:** `generated_workflow` (YAML text), `generated_stages` (list of job names), `stage_explanations` (list of dicts), `generation_explanation`, `vignette_context`, `invalid_workflow_stages`, `skipped_jobs`, `workflow_config_issues`, `auto_fixes`, `external_service_issues`, `errors`/`error_stage="workflow_generation"`, `custom_semgrep_rules_yaml`, `custom_semgrep_rules_path`
- **Composition:** Static job templates (e.g. `_build_pci_dss_job`, `_build_hipaa_job`, `_build_ledger_check_job`, `_build_csp_headers_job`, `_build_mqtt_security_job`, `_build_docker_compose_validate_job`, `_build_dependency_scan_per_service_job`, `_build_ai_job_from_design`), filtered by `_select_relevant_stages()`, `_filter_stages_by_evidence()`, `_validate_pipeline_prerequisites()`, `_validate_pipeline_consistency()`, `_auto_fix_all()`, validated by `_validate_workflow_yaml()`.
- **Custom Semgrep merger:** `_collect_merged_semgrep_rules(detected_domain, pipeline_augmentations, applicable_coverages, ai_generated_rules)` → list of rule dicts combining Tier 1 static + K2.3 AI-generated → YAML string written to `state["custom_semgrep_rules_yaml"]` + `state["custom_semgrep_rules_path"] = ".github/ai-devsecops-rules.yml"`.
- **Fallback:** On YAML errors → `"Invalid workflow: ..."` to `errors`, `error_stage="workflow_generation"`. Pre-flight SHA cache check (`_validate_pinned_actions()`) aborts early if any cache SHA invalid.

#### Node 12: `workflow_validation`
- **File:** `nodes/workflow_validator.py`
- **Type:** Deterministic
- **Input:** `generated_workflow`, `repository_full_name`, `inferred_security_needs.required_stages`
- **Output:** `validation_errors` (always `[]` — non-blocking by design), `validation_passed` (always `True`), `validation_warnings`, `validation_findings` (list of `{type, rule, message, optional action, current_ref, job, line}`), `auto_fixes`
- **Prompt:** N/A
- **Fallback:** If `generated_workflow` empty → `"No workflow YAML to validate — skipped"` to `auto_fixes`, `validation_passed=True`. On YAML parse error → warning + finding of type `warning`/`yaml_syntax`, still `passed=True`. Checks: `check_permissions`, `check_concurrency`, `check_actions_pinned` (compliance-tier aware: `strict`/`moderate`/`permissive`), `check_persist_credentials`, `check_if_conditions`, plus `detect_stages` comparison against `required_stages`. `_is_sha_valid` does `httpx` GET to GitHub with `_SHA_CACHE`; on network failure **assumes valid** (non-blocking).

#### Node 13: `workflow_repair` (LLM #9, dormant) ← v9.3 dormant
- **File:** `nodes/workflow_repair_node.py`
- **Type:** LLM (via `analyze_structured` with `WorkflowFix` pydantic schema)
- **LLM:** `get_llm()`
- **Input:** `errors` (short-circuit if non-empty), `generated_workflow`, `validation_findings`, `validation_errors`, `detected_technologies`
- **Output:** `remediation_suggestions` (appended with `WorkflowFix` model dump), `generated_workflow` (replaced via `workflow.replace(before, after)` if both non-empty + different + `before` found in `workflow`), `summary` (set to `"Workflow repaired: {fix.reasoning[:200]}"`), `errors` (appended `"Workflow repair failed: {e}"`), `error_stage="workflow_repair"`
- **Prompt (verbatim):**
```
You are an expert DevSecOps Workflow Repair Agent.

Your task is to repair an existing GitHub Actions workflow based on validation findings.

CRITICAL RULES

1. Preserve the original workflow structure whenever possible.
2. Fix only the issues identified by the validator.
3. Do not remove existing jobs unless they are invalid.
4. Do not invent frameworks, tools, package managers, or technologies not detected in the repository.
5. Do not generate placeholder values.
6. Do not generate fake commit SHAs.
7. If an exact SHA cannot be verified, use the official stable action tag instead.
8. Ensure the workflow remains executable on GitHub Actions.
9. Ensure the workflow remains valid YAML.
10. Ensure the workflow contains exactly one YAML document.
11. Remove any explanations, markdown, comments, analysis, notes, or prose outside YAML.
12. Preserve security controls already present in the workflow.
13. Preserve existing jobs, stages, triggers, permissions, concurrency settings, and timeouts unless they contain validation issues.
14. If actions/checkout is used and Git push is not required, set: with: persist-credentials: false
15. If validator requires SHA pinning:
    * Replace action tags with verified SHAs only if provided in validator findings.
    * Never invent SHA values.
    * If no verified SHA is provided, keep the official version tag and add a warning in the repair report.

Repository Analysis:
{technologies}

Original Workflow:
{workflow}

Validation Findings:
{findings}

Return ONLY the corrected workflow YAML as a WorkflowFix model with:
- before: the problematic section
- after: the corrected section
- reasoning: what was fixed
- risk: low/medium/high
```
- **Catatan v9.3:** Node ini dormant di runtime — short-circuit kalau `validation_errors` kosong. Validator selalu set `validation_errors = []`, jadi repair tidak pernah terpanggil kecuali `errors` diisi di tempat lain.

#### Node 14: `github_branch_creation`
- **File:** `nodes/github_branch_creation_node.py`
- **Type:** Deterministic
- **Input:** `errors` (short-circuit if non-empty), `validation_passed` (must be `True`), `repository_full_name`, `github_token`, `repository_default_branch`
- **Output:** `github_branch` (e.g. `"ai-devsecops/generate-workflow-{timestamp}"`), `errors` (appended on failure)
- **Prompt:** N/A
- **Fallback:** Short-circuits if `validation_passed=False` (appends `"Validation failed, cannot create branch"`). On `create_branch()` returns `False` → `f"Failed to create branch '{branch_name}'"`. Branch name: `f"ai-devsecops/generate-workflow-{int(time.time())}"`.

#### Node 15: `pull_request_creation`
- **File:** `nodes/pull_request_creation_node.py`
- **Type:** Deterministic
- **Input:** `errors`, `generated_workflow`, `github_branch`, `repository_full_name`, `github_token`, `repository_default_branch`, `detected_technologies`, `detected_architecture`, `detected_architecture_type`, `inferred_security_needs`, `pipeline_version`, `custom_semgrep_rules_yaml`, `custom_semgrep_rules_path`, `detected_domain`, `security_coverages`, `pipeline_augmentations`, `ai_generated_rules`, `workflow_config_issues`, `maintenance_warnings`, `external_service_issues`, `remediation_recommendations`
- **Output:** `workflow_config_issues` (appended), `warnings`, `workflow_file` (e.g. `".github/workflows/ai-devsecops-v{version}.yml"`), `github_commit_sha`, `custom_semgrep_rules` (list of committed rule file paths), `removed_legacy_workflows`, `errors`, `github_pr_number`, `github_pr_url`
- **Prompt:** N/A. Static `PR_TITLE_TEMPLATE = "[AI DevSecOps] Add secure CI/CD pipeline"` + `PR_BODY_TEMPLATE` (multi-section markdown with tech/stages/cleanup/config/maintenance/external/remediation sections).
- **Blocker logic:** Transient upstream errors (`502`, `503`, `504`, `bad gateway`, `service unavailable`, `gateway timeout`, `request failed with status code`, `connection refused`, `connection reset`, `timed out`) explicitly excluded from blockers. Blocker keywords: `no workflow yaml`, `no branch`, `auth`, `authentication`, `unauthorized`, `forbidden`, `token`, `not found`, `invalid`, `parse error`, `yaml syntax`, `commit failed`, `create branch`, `create pull request`.
- **Fallback:** If `custom_semgrep_rules_yaml` empty but workflow references the file → `_collect_merged_semgrep_rules()` from `workflow_generator` invoked to regenerate. If commit fails → warning (PR still proceeds with registry rules only). If legacy workflow removal partial → warnings, PR still proceeds.

---

### TAHAP 4

#### Node 16: `security_analysis` (Hybrid: deterministic + LLM enrichment)
- **File:** `nodes/security_analyzer.py`
- **Type:** Hybrid
- **LLM:** `get_llm()` (only in `_enrich_with_llm()`)
- **Input:** `scan_results` (`scanner_output.semgrep_results`, `trivy_results`, `gitleaks_results`, `npm_audit_results`), `findings` (legacy), `workflow_logs`, `repository_full_name`, `workflow_run_id`, `github_token`, `detected_domain`
- **Output:** `workflow_annotations` (raw dari GitHub), `findings` (security-only list, each enriched with `owasp_risk`, `security_coverage`), `workflow_config_issues`, `maintenance_warnings`, `external_service_issues`, `domain_context` (dict: `detected_domain`, `domain_confidence`, `domain_threats`, `severity_boosted_findings`), `summary`
- **LLM Enrichment Prompt (verbatim):**
```
You are a DevSecOps security analyst.

You are given a list of evidence-based security findings that were already
extracted from scanner outputs (SARIF, npm audit, Trivy, Gitleaks) and GitHub
check-run annotations.

Your task: enrich each finding with additional context. Do NOT add new
findings. Do NOT invent issues. Do NOT classify workflow configuration errors,
deprecation notices, or external service outages as security findings.

Return a JSON array with the same number of items, in the same order, where
each object contains these fields when available:
- type: short identifier (hardcoded_secret, sql_injection, xss, command_injection, dependency_vulnerability, cve_vulnerability, insecure_config, etc.)
- severity: critical/high/medium/low
- scanner: semgrep/trivy/gitleaks/npm-audit/ai/github_annotation
- file: affected file path
- line: line number (integer or null)
- code_snippet: relevant code snippet
- package_name: if dependency issue, the package name
- installed_version: if dependency issue, the installed version
- fixed_version: if dependency issue, the fixed version
- cve: CVE identifier if applicable
- cwe: CWE identifier if applicable
- owasp: OWASP category if applicable
- explanation: clear explanation of the security issue
- impact: business/security impact
- recommendation: how to fix it

Findings to enrich:
{findings}

Return ONLY valid JSON array.
```
- **Fallback:** GitHub data fetch exception → log + continue with empty annotations/logs. LLM enrichment exception → log + keep original findings unchanged. Only **additive** fields (`cwe`, `owasp`, `type`, `recommendation`, `explanation`, `impact`, `severity`) merged in `_merge_enrichment()` — never overwrites hard evidence (`file`, `line`, `code_snippet`). Domain priority (`apply_domain_priority`) + OWASP L×I attachment (`_attach_owasp_li` via `_owasp_li_for_finding` and `_infer_security_coverage` with static `_TYPE_TO_COVERAGE` keyword map) fully deterministic. Final guard: `classify()` re-run on every finding to ensure non-security items never remain in the security list.

#### Node 17: `recommendation_generation` (LLM #10)
- **File:** `nodes/recommendation_gen.py`
- **Type:** LLM + hardcoded fallback
- **LLM:** `get_llm()`
- **Input:** `findings` (truncated 6000 chars for prompt), `risk_score`, `report`
- **Output:** `recommendations` (list of strings), `report` (gets `fix_examples` key), `errors` (on failure)
- **Prompt (verbatim):**
```
You are a DevSecOps engineer. Given the following security findings and risk assessment, generate actionable fix recommendations.

Findings:
{findings}

Risk Score: {risk_score}

For each finding, provide:
1. A clear code-level fix recommendation
2. A before/after code example if applicable
3. Package update command if it's a dependency issue

Return a JSON object with:
- recommendations: list of recommendation strings
- fix_examples: list of {{"finding_type": str, "before": str, "after": str}}

Return ONLY valid JSON.
```
- **Fallback:** Hardcoded recommendations list per finding type (`hardcoded_secret` → rotate credentials + use env var; `sql_injection` → parameterized query; etc.) when LLM fails.

#### Node 18: `response_formatter`
- **File:** `nodes/response_formatter.py`
- **Type:** Deterministic
- **Input:** Full state (semua output dari node sebelumnya)
- **Output:** `summary` (final response), `pdf_report_path`, `errors`
- **Prompt:** N/A
- **Fallback:** No LLM. On exception → log + return state with `error_stage` set.

---

## State v9.3

Tambah ke `pipeline_state.py`:
```python
# Tahap 1 outputs (sama dengan v9)
detected_technologies: dict | None
detected_architecture: dict | None
detected_architecture_type: str | None
detected_deployment: dict | None
detected_domain: str | None
domain_sub_type: str | None
domain_threats: list                              # ← di-generate tapi belum dipakai K2.3 (gap v9.3)
features: list

# Tahap 2 outputs (DIUBAH dari v9)
security_coverages: list                          # 15-element list, {id, applicable, reason, confidence}
ai_generated_rules: list                          # K2.3 (BARU v9.1)
pattern_inference_reasoning: str | None
pattern_inference_valid_count: int
pipeline_augmentations: list                      # [{coverage, job, configuration, reason}]
inferred_security_needs: dict | None
job_designs: list                                 # K2.4 (BARU v9.2)
job_designs_reasoning: str | None
job_designs_valid_count: int

# Tahap 3 outputs (sama)
generated_workflow: str | None
custom_semgrep_rules_yaml: str | None             # Tier 1 + K2.3 merged
custom_semgrep_rules_path: str | None             # default ".github/ai-devsecops-rules.yml"
custom_semgrep_rules: list                        # committed rule file paths
workflow_file: str | None                         # ".github/workflows/ai-devsecops-v{N}.yml"
github_branch: str | None
github_commit_sha: str | None
github_pr_number: int | None
github_pr_url: str | None

# Tahap 4 outputs (sama)
findings: list                                    # enriched findings, [{..., security_coverage, owasp_risk}]
domain_context: dict | None
recommendations: list
summary: str | None
pdf_report_path: str | None
```

Tambah ke `findings[]`:
```python
findings[].security_coverage: str | None  # "payment_security" dll (dari _infer_security_coverage)
findings[].owasp_risk: dict | None        # {likelihood, impact, risk_level}
findings[].domain_boosted: bool           # severity elevation dari domain_priority
```

---

## PDF Report v9.3 (5 sections)

1. Repository Context (1.1 Tech, 1.2 Arch, 1.3 Deploy, 1.4 Domain, 1.5 Features)
2. Security Requirements (2.1 Attack Surfaces, 2.2 Controls, 2.3 Pipeline Stages)
3. Generated Pipeline (3.1 Validation, 3.2 Stages, 3.3 Workflow YAML, **3.4 Custom Semgrep Rules** ← Tier 1 + K2.3 merged)
4. Pipeline Evaluation (4.1 Dashboard, 4.2 Findings + OWASP L×I, 4.3 Recommendations, 4.4 Summary)
5. **Security Coverages Applied**
   - 5.1 Applicable Coverages (table: id, reason)
   - 5.2 Pipeline Augmentations (table: coverage, job, configuration)
   - 5.3 Coverage-to-Finding Mapping (table: coverage, # findings)
   - **5.4 AI-Generated Semgrep Rules** (table: id, coverage, severity, reasoning) ← BARU v9.3
   - **5.5 AI-Designed Custom Jobs** (table: name, coverage, action count) ← BARU v9.3

---

## Compiled Graph v9.3

```
Tahap 1 (6) → Tahap 2 (4) → Tahap 3 (5) → Tahap 4 (3) = 18 node | 11 LLM calls
```

```
[ENTRY] → repository_connection → repository_scan
       → technology_detection (LLM 1) → architecture_detection (LLM 2)
       → deployment_detection (LLM 3) → domain_detection (LLM 4)
       → coverage_inference (LLM 5)
       → pattern_inference (LLM 6) ← K2.3 NEW
       → pipeline_augmentation (LLM 7)
       → job_reasoning (LLM 8) ← K2.4 NEW
       → workflow_generation (deterministic; WORKFLOW_GEN_PROMPT dormant)
       → workflow_validation
       → workflow_repair (LLM 9 — dormant karena validation_errors selalu [])
       → github_branch_creation
       → pull_request_creation
       → workflow_execution
       → security_analysis (LLM 10 enrichment)
       → recommendation_generation (LLM 11)
       → response_formatter → [END]
```

Validation gate: `workflow_validation` → `passed` (selalu True) → lanjut ke deployment. `failed` → ke `response_formatter`.

---

## Mapping Node → File

| # | Node | File |
|---|------|------|
| 1 | repository_connection | `nodes/repository_connection_node.py` |
| 2 | repository_scan | `nodes/repository_scan_node.py` |
| 3 | technology_detection | `nodes/technology_detection_node.py` |
| 4 | architecture_detection | `nodes/architecture_detection_node.py` |
| 5 | deployment_detection | `nodes/deployment_detection_node.py` |
| 6 | domain_detection | `nodes/domain_detection_node.py` |
| 7 | **coverage_inference** | `nodes/coverage_inference_node.py` ← v9 |
| 8 | **pattern_inference** | `nodes/pattern_inference_node.py` ← **v9.1 K2.3** |
| 9 | **pipeline_augmentation** | `nodes/pipeline_augmentation_node.py` ← v9 |
| 10 | **job_reasoning** | `nodes/job_reasoning_node.py` ← **v9.2 K2.4** |
| 11 | workflow_generation | `nodes/workflow_generator.py` |
| 12 | workflow_validation | `nodes/workflow_validator.py` |
| 13 | workflow_repair | `nodes/workflow_repair_node.py` |
| 14 | github_branch_creation | `nodes/github_branch_creation_node.py` |
| 15 | pull_request_creation | `nodes/pull_request_creation_node.py` |
| 16 | workflow_execution | `nodes/workflow_execution.py` |
| 17 | security_analysis | `nodes/security_analyzer.py` |
| 18 | recommendation_generation | `nodes/recommendation_gen.py` |
| 19 | response_formatter | `nodes/response_formatter.py` |

---

## LLM Provider Configuration

Semua LLM call melalui `app/services/llm_service.py:get_llm()`. Provider configurable via env:

| Env var | Nilai | Default |
|---|---|---|
| `LLM_PROVIDER` | `openai` / `anthropic` / `openrouter` / `opencode` / `google` | (required) |
| `LLM_MODEL` | Model ID per provider | (required per provider) |
| `LLM_API_KEY` | API key per provider | (required per provider) |

Provider implementations di `llm_service.py`:
- `openai` → `langchain_openai.ChatOpenAI`
- `anthropic` → `langchain_anthropic.ChatAnthropic`
- `openrouter` → `ChatOpenAI(base_url="https://openrouter.ai/api/v1")`
- `opencode` → `ChatOpenAI(base_url="https://opencode.ai/api/v1")`
- `google` → `langchain_google_genai.ChatGoogleGenerativeAI`

---

## Frontend (PipelineGenerator.tsx) — NEW

Tambah section "Security Coverages" di UI sebelum Security Controls card:
- Tampilkan `applicable_coverages` saja (filter `applicable: true`)
- Tiap coverage: badge biru dengan id + reason
- Counter "N applicable"

**Tambahan v9.3:**
- Section "AI-Generated Semgrep Rules" — list rule dengan `id`, `coverage`, `severity`, `reasoning` dari `ai_generated_rules`.
- Section "AI-Designed Custom Jobs" — list `job_designs` dengan nama, jumlah action, badge coverage.

---

## Test

File: `ai-service/tests/test_tahap3_generator.py`

Mock state untuk repo `iqbalrsyd/eccomerce-monolith-vuln`:
- 6 applicable coverages dari 15
- 10 pipeline augmentations
- 3-5 AI-generated Semgrep rules (K2.3)
- 1-3 AI-designed custom jobs (K2.4)
- Output: YAML 14461 chars, 394 lines
- 6 stage: `lint, test, sast, secret-scan, container-scan, pci-dss`
- Custom Semgrep file: `.github/ai-devsecops-rules.yml` (~22KB Tier 1 + K2.3 merged)
- Validation: PASSED, 0 errors

---

## Gap Analysis v9.3 (untuk v9.4)

| # | Gap | Lokasi | Rencana v9.4 |
|---|---|---|---|
| G1 | `domain_threats[]` di-generate tapi tidak dipakai downstream | `pipeline_state.domain_threats` | Extend prompt `pattern_inference_node` agar `domain_threats` jadi constraint tambahan (LLM generate rule yang address threat spesifik) |
| G2 | `workflow_repair_node` dormant (short-circuit karena `validation_errors` selalu `[]`) | `nodes/workflow_repair_node.py` | Hapus dari graph atau ubah trigger ke `validation_warnings` non-empty |
| G3 | `workflow_execution` lookup hardcoded `ci-cd.yml`, bukan `ai-devsecops-v{N}.yml` | `nodes/workflow_execution.py` | Update lookup ke `state["workflow_file"]` |
| G4 | `workflow_generator` punya `WORKFLOW_GEN_PROMPT` tapi tidak pernah dipanggil | `nodes/workflow_generator.py:13-128` | Hapus dead code atau aktifkan sebagai fallback kalau deterministic emitter gagal |
| G5 | `domain_sub_type` (payment processor) tidak dipakai K2.3 atau K2.4 | `pipeline_state.domain_sub_type` | Pass ke prompt `pattern_inference` (sudah dipakai) + `job_reasoning` (belum) |
| G6 | `ENABLE_LLM_GENERATED_RULES` (Tier 3 dead code) | `semgrep_rules/llm_generation_config.py` + `llm_generation_prompt.py` | Hapus atau refactor jadi ekstensi K2.3 (pakai `domain_threats`) |
| G7 | Tidak ada `semgrep --validate` step di SAST job | `nodes/workflow_generator.py` (SAST job) | Tambah step `semgrep --validate --config=.github/ai-devsecops-rules.yml` dengan `continue-on-error: true` |
| G8 | `coverage_inference` 15-element output list tapi `pattern_inference` cuma baca applicable | `nodes/pattern_inference_node.py` | Filter by applicable di K2.3 (sudah dilakukan) — tidak ada gap |
