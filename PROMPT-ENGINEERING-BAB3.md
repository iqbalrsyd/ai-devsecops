# Prompt Engineering untuk DevSecOps AI Agent — Analisis BAB 3

> **Dokumen pendukung penulisan BAB 3 (Metode Penelitian)**  
> **Topik:** Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices  
> **Fokus:** Prompt Engineering per Security Control + Domain Context-Aware Analysis

---

## Daftar Isi

1. [Ikhtisar Prompt Engineering](#1-ikhtisar-prompt-engineering)
2. [Klasifikasi Prompt per Pipeline Job](#2-klasifikasi-prompt-per-pipeline-job)
3. [Analisis Prompt Engineering per Security](#3-analisis-prompt-engineering-per-security)
4. [Analisis Prompt Engineering Domain Context-Aware](#4-analisis-prompt-engineering-domain-context-aware)
5. [Deterministic Safety Guards](#5-deterministic-safety-guards)
6. [Metodologi Prompt Engineering](#6-metodologi-prompt-engineering)
7. [Vignette: Efek Domain pada Output Pipeline](#7-vignette-efek-domain-pada-output-pipeline)
8. [Referensi File Implementasi](#8-referensi-file-implementasi)

---

## 1. Ikhtisar Prompt Engineering

Sistem DevSecOps AI Agent menggunakan **9 persona LLM yang berbeda** — masing-masing memiliki _system prompt_ terspesialisasi sesuai peran _domain expert_-nya. Desain ini bertujuan agar LLM mendapatkan _role anchoring_ yang kuat sehingga output tidak generik, melainkan sesuai kaidah keamanan software, arsitektur sistem, dan konteks domain aplikasi.

### 1.1 Prinsip Desain Prompt

| Prinsip | Penjelasan |
|---------|------------|
| **Persona anchoring** | Setiap prompt membuka dengan deklarasi peran (e.g., "You are a DevSecOps security engineer performing SAST...") |
| **Context injection** | Prompt menginjeksi hasil node sebelumnya (`detected_technologies`, `detected_architecture`, `detected_domain`, dll.) |
| **Structured output** | Setiap prompt meminta output JSON/YAML dengan schema terdefinisi (bukan teks bebas) |
| **Domain-aware branching** | Prompt menyertakan instruksi kondisional berdasarkan arsitektur (`monolithic` vs `microservices`) dan domain (`e-commerce` vs `healthcare` vs `fintech`) |
| **Deterministic fallback** | Setiap node LLM memiliki fallback deterministik (regex, lookup table, atau default rules) |
| **Invariant enforcement** | Guardrail di level kode (bukan prompt) untuk menjamin invariant (mis: mandatory control enforcement) |

### 1.2 Total Node dan Persentase LLM vs Deterministik

```
Total node dalam pipeline: 20 node
├── LLM-based nodes:     9 node  (45%)  — menggunakan prompt + persona LLM
├── Deterministic nodes: 11 node (55%)  — aturan lookup atau heuristik
│
9 LLM node:
  1. technology_detection_node       → Senior DevSecOps Stack Analyst
  2. architecture_detection_node    → Software Architect
  3. deployment_detection_node      → Cloud/Platform Engineer
  4. domain_detection_node          → Industry Analyst
  5. vulnerability_scan_node        → Application Security Engineer
  6. security_requirement_inference → DevSecOps Lead Architect
  7. workflow_generator (fallback)   → GitHub Actions Expert
  8. security_analyzer (enrichment)  → Security Analyst (read-only)
  9. recommendation_gen_node        → Senior Developer/Fixer

11 Deterministic node:
  1-3. repository_connection, repository_scan, source_file_extraction
  4.   attack_surface_lookup         → Lookup table (deployment → attack surface)
  5.   domain_priority               → Regex-based severity boost
  6.   workflow_generator (aktif)    → _build_workflow_yaml() deterministik
  7.   workflow_validator            → YAML + SHA pinning + permission validation
  8.   github_branch_creation        → GitHub API call
  9.   pull_request_creation         → GitHub API call
  10.  workflow_execution            → Polling GitHub Actions API
  11.  compliance_mapper             → Rule-based mapping ke OWASP/CIS
```

---

## 2. Klasifikasi Prompt per Pipeline Job

### 2.1 Tabel Ringkasan 12 Pipeline Job

| # | Node / Job | File | Persona LLM | Deterministik? | Fallback |
|---|------------|------|-------------|----------------|----------|
| 1 | `technology_detection` | `technology_detection_node.py:20-47` | Senior DevSecOps Stack Analyst | Tidak | `_detect_from_extensions()` (regex) |
| 2 | `architecture_detection` | `architecture_detection_node.py:8-37` | Software Architect | Tidak | Default `monolithic` |
| 3 | `deployment_detection` | `deployment_detection_node.py:7-44` | Cloud/Platform Engineer | Tidak | `_detect_from_files()` (deterministik) |
| 4 | `domain_detection` | `domain_detection_node.py:251-279` | Industry Analyst | Tidak | `_score_domain()` (heuristic) |
| 5 | `vulnerability_scan` | `vulnerability_scan_node.py:21-71` | App Security Engineer | Tidak | `PATTERN_RULES` (8 rule regex) |
| 6 | `security_requirement_inference` | `security_requirement_inference_node.py:11-97` | DevSecOps Lead Architect | Tidak | `_get_default_controls()` |
| 7 | `workflow_generator` (fallback) | `workflow_generator.py:13-155` | GitHub Actions Expert | — | — |
| 8 | `workflow_generator` (aktif) | `workflow_generator.py:1202-1737` | — | **Ya** | — |
| 9 | `security_analyzer` (enrichment) | `security_analyzer.py:33-65` | Security Analyst (read-only) | Tidak | Skip enrichment |
| 10 | `recommendation_gen` | `recommendation_gen.py:4-21` | Senior Developer/Fixer | Tidak | Generic recommendation |
| 11 | `domain_priority` (post-process) | `domain_priority.py:30-120` | — | **Ya** | — |
| 12 | `attack_surface_lookup` | `attack_surface_lookup.py:18-58` | — | **Ya** | — |

---

## 3. Analisis Prompt Engineering per Security

### 3.1 Prompt 1: Technology Detection — Stack Analyst

**File:** `ai-service/app/agents/nodes/technology_detection_node.py:20-47`  
**Persona:** _Senior DevSecOps stack analyst_  
**Tujuan keamanan:** Mendeteksi tech stack sebagai fondasi pemilihan tool keamanan.

```
You are a DevSecOps engineer analyzing a GitHub repository.

Given the repository files and structure below, identify the technology stack
with confidence scores.

Repository structure: {structure}
Key files found: {files}
Existing workflows: {workflows}

Analyze the files and identify:
- primary_language, primary_language_confidence, primary_language_reason
- frameworks[], framework_confidences[]
- build_tools[], package_manager, package_manager_confidence
- test_framework, database, runtime

Return ONLY valid JSON matching this schema. Be precise based on actual files.
```

**Analisis Security:**

| Aspek | Deskripsi |
|-------|-----------|
| **Mengapa LLM?** | Ekosistem bahasa modern memiliki signature file yang tidak bisa di-capture oleh regex sederhana. Contoh: `nuxt.config.ts` → Nuxt.js (RCE risk berbeda dengan Express), `pyproject.toml` dengan `[tool.poetry]` → Python (bandit rules), `go.mod` + `cmd/` → Go (CodeQL rules). |
| **Security implication** | Output menentukan tool SAST (bandit vs eslint vs codeql vs spotbugs), dependency scanner (pip-audit vs npm audit vs govulncheck), dan CVE scanner yang akan digunakan. |
| **Overfitting prevention** | Confidence score diwajibkan untuk setiap field, sehingga downstream node bisa melakukan _weighted decision_. |
| **Constraint** | `"Be precise based on actual files"` — mencegah LLM dari mengarang framework yang tidak terdeteksi. |

**Fallback deterministik:** `_detect_from_extensions()` menghitung bobot dari 40+ ekstensi file (`EXTENSION_MAP` di `technology_detection_node.py:8-18`). Jika `primary_language` kosong setelah 3 retry, fallback ke bahasa dengan file terbanyak.

---

### 3.2 Prompt 2: Architecture Detection — Software Architect

**File:** `ai-service/app/agents/nodes/architecture_detection_node.py:8-37`

```
You are a DevSecOps engineer analyzing application architecture.

Given the repository structure and detected technologies, determine the
application architecture with confidence scores.

Repository structure: {structure}
Detected technologies: {technologies}

Analyze the architecture and return JSON with:
- architecture_type: monolithic | frontend_backend | microservices |
                     modular_monolith | serverless | library
- architecture_confidence, architecture_reason
- service_count, service_names[]
- has_api_gateway, has_message_queue, has_database_config,
  is_containerized, has_shared_libraries

Key distinction for modular_monolith:
- Multiple services/directories exist but share database or are deployed
  together. NOT microservices. Has clear separation but tight coupling.

Return ONLY valid JSON. No markdown.
```

**Analisis Security per Arsitektur:**

| Architecture | Security Tools | Attack Surface | Prompt Instruction |
|-------------|---------------|----------------|--------------------|
| monolithic | Single SAST, single dep-scan | Source code, dependencies | "single linear workflow" |
| microservices | per-service SAST + matrix | Service mesh, API gateway, inter-service auth | "matrix strategy per service" |
| modular_monolith | per-service SAST + matrix | Shared DB risk, coupling | "matrix but treat as single deployment" |
| frontend_backend | Dual SAST (eslint + bandit) | CORS, CSP, XSS + SQLi | "matrix with two entries" |
| serverless | Function-level scan | Lambda config, IAM | (implicit) |
| library | Dependency audit only | Supply chain | (implicit) |

**Security implication kritis:** Arsitektur menentukan apakah pipeline perlu `per_service_sast`, `api_gateway_test`, dan `service_mesh_audit`. Kesalahan klasifikasi (mis: `modular_monolith` dianggap `monolithic`) akan melewatkan inter-service communication vulnerability.

---

### 3.3 Prompt 3: Deployment Detection — Platform Engineer

**File:** `ai-service/app/agents/nodes/deployment_detection_node.py:7-44`

```
You are a DevSecOps engineer analyzing deployment infrastructure.

Given the repository structure and files, detect deployment technologies
and recommend deployment target.

Repository structure: {structure}
Key files: {files}
Existing workflows: {workflows}

Analyze and return JSON with:
- docker, docker_confidence, docker_reason, docker_compose
- kubernetes, kubernetes_confidence, kubernetes_reason
- terraform, terraform_confidence, helm
- cloud_provider, recommended_deployment_target,
  alternative_deployment_targets, deployment_reason

Return ONLY valid JSON. No markdown.
```

**Analisis Security:**

| Deployment Target | Security Controls yang Dipicu | Attack Surfaces |
|------------------|------------------------------|-----------------|
| Docker | `container_scan`, `container_build`, `sbom`, `secret_scan` | Container Image, Dockerfile Config, Image Layer Secrets |
| Kubernetes | `iac_scan`, `service_mesh_audit`, `container_scan` | RBAC, Ingress, Pod Security, Service Accounts |
| Terraform | `iac_scan` | S3 Bucket ACL, IAM Role, Security Groups |
| code-only | `sast`, `dependency_scan`, `cve_scan`, `secret_scan` | Source Code, Dependencies, Secrets |

**Deterministic override (guardrail):** `_detect_from_files()` (`deployment_detection_node.py:138-231`) berjalan SEBELUM LLM dipanggil. Hasil LLM di-merge ke hasil deterministik. Override LLM terhadap `alternative_deployment_targets` dilakukan untuk mencegah halusinasi cloud provider (Railway, Render, AWS, Azure, GCP).

---

### 3.4 Prompt 4: Vulnerability Scan — App Security Engineer

**File:** `ai-service/app/agents/nodes/vulnerability_scan_node.py:21-71`

```
You are a DevSecOps security engineer performing static application security
testing (SAST) on source code.

ARCHITECTURE TYPE: {architecture_type}
DETECTED DOMAIN: {domain} (confidence: {domain_confidence})
DOMAIN-SPECIFIC THREATS: {domain_threats}

Source files: {source_files}
PRELIMINARY FINDINGS FROM PATTERN SCAN: {pattern_findings}

For each vulnerability found, return a JSON array with:
  type, severity (critical|high|medium|low), file, line, code_snippet,
  explanation, recommendation, cwe, owasp

IMPORTANT: verify each pattern match against the actual source code. Do
not report a finding unless you can confirm it in the source files.

━━━ STANDARD CHECKS (semua arsitektur & domain) ━━━
  1.  Hardcoded API keys, JWT secrets, AWS secrets, passwords, tokens
  2.  SQL injection
  3.  XSS
  4.  Command injection
  5.  Path traversal
  6.  IDOR
  7.  SSRF
  8.  Weak JWT configuration
  9.  Insecure cryptography
  10. Exposed debug/health endpoints
  11. Missing rate limiting
  12. Outdated dependencies with known vulnerabilities

━━━ IF ARCHITECTURE IS "microservices" or "frontend_backend", ADD: ━━━
  13. Hardcoded service URLs / service discovery addresses
  14. JWT forwarded between services without re-validation
  15. Service-to-service communication without authentication
  16. API gateway bypass
  17. Inconsistent auth between services
  18. Shared secrets across multiple services
  19. Missing input validation in inter-service API calls
  20. Insecure service mesh configuration

━━━ IF DOMAIN == "e-commerce", ADD (PRIORITIZE): ━━━
  21. SQL injection in /checkout, /orders, /payment endpoints (PCI-DSS 6.2.4)
  22. XSS in /products/:id/review, /comments, /search (reflected + stored)
  23. CSRF protection missing on cart/checkout POST endpoints
  24. Price tampering: client-supplied price not re-validated server-side
  25. Cardholder data exposure in logs, error messages, or responses
  26. Stripe/PayPal API key hardcoded (sk_live_, pk_live_, AKIA)
  27. Insecure cookies: missing httpOnly, secure, sameSite flags
  28. Weak password storage: plaintext, MD5, SHA1, no bcrypt/argon2/scrypt
  29. Missing rate limiting on /login, /register, /forgot-password
  30. Order/cart manipulation via direct object reference
  31. Inventory race condition (TOCTOU on stock check + deduct)
  32. Insecure HTTP: checkout pages served over HTTP (no HSTS)

━━━ IF DOMAIN == "healthcare", ADD: ━━━
  21. PHI exposure in logs, error messages, or unencrypted fields
  22. Weak authentication on patient/records endpoints (HIPAA 164.312(a))
  23. Missing audit log for PHI access (HIPAA 164.312(b))
  24. Insecure transmission of patient data (no TLS enforced)
  25. FHIR API exposed without OAuth2/SMART-on-FHIR
  26. IDOR on /patients/:id, /records/:id (cross-patient access)
  27. Hardcoded database credentials with PHI access
  28. Insecure deserialization of medical imaging data (DICOM)
  29. Backup/audit log without encryption-at-rest
  30. Session timeout missing or > 15 minutes for PHI access

━━━ IF DOMAIN == "fintech", ADD: ━━━
  21. Transaction tampering: client-modified amount/recipient not validated
  22. Race condition on balance transfer (double-spend)
  23. KYC bypass: identity verification endpoint without proper auth
  24. Replay attack: transaction without nonce/timestamp validation
  25. Insider threat: admin endpoint without audit trail
  26. Hardcoded API keys for Stripe Connect, Plaid, Alpaca
  27. Insecure direct object reference on /accounts/:id, /transactions/:id
  28. Negative amount accepted in transfer/deposit
  29. Decimal precision bug: using float for currency instead of Decimal
  30. Missing idempotency key on financial operations

━━━ IF DOMAIN == "blog", ADD: ━━━
  21. XSS in markdown/comment rendering (sanitize-html bypass)
  22. File upload bypass: .php.jpg, double extension, polyglot files
  23. Path traversal in upload directory (../../etc/passwd)
  24. RCE via SVG upload with embedded JavaScript
  25. Content injection in <style> or <script> via markdown
  26. SSRF via image URL fetch (og:image, avatar fetch)
  27. CSRF on comment submission, post creation
  28. Author impersonation via X-Forwarded-For manipulation
  29. Insecure default avatar path disclosure
  30. Comment moderation bypass via unicode normalization

━━━ IF DOMAIN == "iot", ADD: ━━━
  21. Device authentication bypass (default credentials, hardcoded password)
  22. MQTT/CoAP without TLS (plaintext telemetry)
  23. Firmware OTA update without signature verification
  24. Hardcoded device certificate / key in firmware
  25. Telemetry endpoint accepting unauthenticated commands
  26. mDNS/UPnP exposure revealing device capabilities
  27. Debug interface (JTAG, UART, serial) accessible in production
  28. Buffer overflow in C/C++ sensor parsing code
  29. Insecure pairing protocol (no Diffie-Hellman, no PIN verification)
  30. Cloud-to-device command without end-to-end encryption

━━━ IF DOMAIN == "education", ADD: ━━━
  21. Grade tampering: teacher-only endpoint accessible by student role
  22. Student data exposure: PII accessible cross-enrollment
  23. Quiz answer leak: client-side answer key in JS bundle
  24. Cheating bypass: time-limit enforced client-side only
  25. Submission manipulation: post-deadline upload accepted
  26. Proctoring data (video, screenshot) without encryption
  27. Insecure SCORM/xAPI data exchange
  28. Hardcoded API key for plagiarism detection service
  29. IDOR on /submissions/:id, /grades/:id
  30. Missing audit log for grade changes

Return ONLY a valid JSON array. If no vulnerabilities found, return [].
```

**Analisis Security:**

| Aspek | Deskripsi |
|-------|-----------|
| **Dual-mode scan** | Pattern scan (regex) berjalan dulu untuk catch 8 kategori. LLM memverifikasi pattern match + cari temuan tambahan. |
| **Architecture-aware checks** | 12 standard checks untuk semua arsitektur + 8 microservice-specific checks untuk `microservices`/`frontend_backend`. Ini **domain context-aware** di level arsitektur. |
| **False-positive reduction** | LLM diinstruksikan _"verify each pattern match against the actual source code. Do not report a finding unless you can confirm it."_ — pattern scan hanya sebagai preliminary signal. |
| **Structured output** | Setiap finding harus mencakup `cwe`, `owasp`, dan `recommendation` — untuk downstream OWASP compliance mapping. |

**Fallback deterministik:** `PATTERN_RULES` (`vulnerability_scan_node.py:82-188`) memiliki 8 kategori: `hardcoded_secret` (7 pattern), `sql_injection` (4 pattern), `command_injection` (2 pattern), `xss` (3 pattern), `path_traversal` (2 pattern), `ssrf` (2 pattern), `insecure_crypto` (3 pattern), `debug_endpoint` (2 pattern). Temuan pattern scan tetap disimpan meskipun LLM gagal parse.

---

### 3.5 Prompt 5: Security Requirement Inference — DevSecOps Lead Architect

**File:** `ai-service/app/agents/nodes/security_requirement_inference_node.py:11-97`

Ini adalah prompt **paling kompleks** dalam sistem karena menggabungkan 4 dimensi konteks + attack surface deterministik.

```
You are a DevSecOps engineer determining security requirements for a project.

Based on the detected technologies, architecture, deployment, AND DOMAIN,
determine which security controls are needed with detailed explanations.

Technologies: {technologies}
Architecture: {architecture}
Deployment: {deployment}

Domain Context:
- Detected Domain: {domain} (confidence: {domain_confidence})
- Domain-Specific Threats: {domain_threats}
- Domain Evidence: {domain_evidence}

Attack Surfaces to Protect (from deterministic lookup): {attack_surfaces}

Mandatory Controls (from attack surface coverage — must be included):
  {mandatory_controls}

Return a JSON object:
{
  "security_controls": [
    {
      "control": "lint | test | build | sast | dependency_scan | cve_scan |
                  secret_scan | container_scan | container_build | iac_scan |
                  license_check | sbom | deploy | per_service_sast |
                  per_service_dep_scan | api_gateway_test | service_mesh_audit |
                  csrf_check | auth_strength | session_security |
                  input_validation | cors_check | container_config_scan",
      "status": "recommended | optional | not_required",
      "reason": "Why this status — MUST reference the domain/architecture/
                 deployment context when relevant",
      "tool": "recommended tool name or null",
      "tool_version": "specific version or 'latest'"
    }
  ],
  "required_tools": [...],
  "pipeline_stages": [...]
}

━━━ PER-DOMAIN CONTROL PRIORITIZATION ━━━

IF DOMAIN == "e-commerce":
  PRIORITIZE the following controls (mark as "recommended"):
    - sast (OWASP Top 10 + Express/Node.js rules)
    - dependency_scan + cve_scan (HIGH/CRITICAL gate, PCI-DSS 6.3)
    - secret_scan (Stripe/PayPal/AWS keys)
    - container_build + container_scan + container_config_scan
    - csrf_check (custom Semgrep rules for express csrf middleware)
    - auth_strength (password storage audit, rate limiting)
    - session_security (cookie flags, JWT expiry)
    - input_validation (Joi/zod/express-validator)
    - cors_check (origin: '*' detection)
    - sbom (PCI-DSS 6.3.5 supply chain visibility)
  Mark as "optional":
    - license_check (legal risk for closed-source distribution)
  Mark as "not_required":
    - service_mesh_audit, api_gateway_test (monolith, not microservices)

IF DOMAIN == "healthcare":
  PRIORITIZE:
    - sast (HIPAA 164.312(a) access control, 164.312(c) integrity)
    - dependency_scan + cve_scan (FHIR/HL7 library CVEs)
    - secret_scan (FHIR API keys, DB credentials)
    - session_security (HIPAA session timeout < 15 min)
    - input_validation (PHI sanitization in logs/errors)
    - audit_logging (custom Semgrep check for access logging)
  Mark as "recommended":
    - container_build + container_scan
    - sbom (FDA cybersecurity guidance)
  Mark as "optional":
    - license_check, iac_scan (depends on infrastructure)

IF DOMAIN == "fintech":
  PRIORITIZE:
    - sast (transaction tampering, race conditions, KYC bypass)
    - dependency_scan + cve_scan (CRITICAL gate, financial compliance)
    - secret_scan (Plaid, Stripe Connect, Alpaca keys)
    - auth_strength (MFA enforcement, password policy)
    - input_validation (currency precision, idempotency keys)
    - session_security (financial session timeout)
  Mark as "recommended":
    - container_build + container_scan + container_config_scan
    - sbom (regulatory submission requirement)
  Mark as "optional":
    - license_check

IF DOMAIN == "blog":
  PRIORITIZE:
    - sast (XSS in comments/markdown, file upload bypass, path traversal)
    - dependency_scan (markdown-it, sanitize-html, dompurify)
    - secret_scan (CMS admin credentials, API keys)
    - input_validation (markdown sanitizer bypass)
  Mark as "optional":
    - container_build + container_scan (only if Dockerfile)
    - sbom
    - license_check

IF DOMAIN == "iot":
  PRIORITIZE:
    - sast (device auth bypass, MQTT/CoAP without TLS, hardcoded certs)
    - dependency_scan (paho-mqtt, azure-iot, modbus CVEs)
    - secret_scan (device certificates, factory default keys)
    - container_scan (firmware image scan)
    - iac_scan (cloud IoT infrastructure)
    - input_validation (sensor data parsing, buffer overflow check)
  Mark as "optional":
    - container_build (depends on deployment model)

IF DOMAIN == "education":
  PRIORITIZE:
    - sast (grade tampering, PII exposure, SCORM data security)
    - dependency_scan (Moodle, Canvas, SCORM libraries)
    - secret_scan (LMS admin, proctoring service keys)
    - auth_strength (role-based access: student/teacher/admin)
    - session_security (exam session timeout)
    - input_validation (submission file sanitization)

For microservices/modular_monolith: include per_service_* stages
For monolithic: use single scan approach

For {domain} webapps, PRIORITIZE controls that address the
domain-specific threats listed above. Map each threat to a specific control.

Return ONLY valid JSON. No markdown.
```

**Analisis Security — 5-Step Inference Process:**

| Step | Nama | Mekanisme | Deterministik? |
|------|------|-----------|----------------|
| 1 | Repository Context (K1) | Baca `detected_technologies`, `detected_architecture`, `detected_deployment`, `detected_domain` dari state | Ya (dari node sebelumnya) |
| 2 | Attack Surface Identification | `identify_attack_surfaces(deployment)` — lookup table | **Ya** |
| 3 | Threat Inference | LLM menerjemahkan domain_threats + attack_surfaces → ancaman relevan | Tidak |
| 4 | Control Selection | LLM memilih kontrol, `_enforce_mandatory_controls()` memastikan minimum coverage | Hybrid |
| 5 | Output ke state | `state.inferred_security_needs` → digunakan oleh workflow generator | Ya |

**Mandatory Control Enforcement (`_enforce_mandatory_controls`):**  
Kode di `security_requirement_inference_node.py:315-337` menjamin bahwa kontrol yang dipetakan dari `attack_surface_lookup` SELALU ada di output, meskipun LLM menghilangkannya. Ini adalah invariant yang ditegakkan oleh kode, bukan prompt.

**Microservice-specific injection:**  
Baris `security_requirement_inference_node.py:420-430` menambahkan `per_service_sast`, `per_service_dep_scan`, `api_gateway_test`, `service_mesh_audit`, `secret_scan_all` ke `pipeline_stages` ketika `arch_type ∈ {microservices, modular_monolith}`.

---

### 3.6 Prompt 6: Security Analyzer (Enrichment) — Security Analyst (Read-Only)

**File:** `ai-service/app/agents/nodes/security_analyzer.py:33-65`

```
You are a DevSecOps security analyst.

You are given a list of evidence-based security findings that were already
extracted from scanner outputs (SARIF, npm audit, Trivy, Gitleaks) and
GitHub check-run annotations.

Your task: enrich each finding with additional context. Do NOT add new
findings. Do NOT invent issues. Do NOT classify workflow configuration
errors, deprecation notices, or external service outages as security findings.

Return a JSON array with the same number of items, in the same order:
  type, severity, scanner, file, line, code_snippet, package_name,
  installed_version, fixed_version, cve, cwe, owasp, explanation,
  impact, recommendation

Findings to enrich: {findings}

Return ONLY valid JSON array.
```

**Analisis Security — Read-Only Constraint:**

| Invarian | Mekanisme |
|----------|-----------|
| Tidak boleh menambah finding | Prompt eksplisit + `_merge_enrichment()` hanya merge field non-evidence |
| Tidak boleh mengubah evidence | `file`, `line`, `code_snippet` di-lock, tidak boleh di-overwrite output LLM |
| Hanya enrichment | Hanya field `cwe`, `owasp`, `explanation`, `recommendation`, `severity` yang boleh di-merge |
| Finding harus evidence-based | Input harus sudah dari scanner tool (SARIF, Trivy, Gitleaks, check-run annotations) |

**Invarian yang dijaga oleh kode (bukan prompt):**
- `_merge_enrichment` (`security_analyzer.py:300-315`): field evidence (`file`, `line`, `code_snippet`) TIDAK boleh di-overwrite oleh output LLM.

---

### 3.7 Prompt 7: Recommendation Generation — Senior Developer / Fixer

**File:** `ai-service/app/agents/nodes/recommendation_gen.py:4-21`

```
You are a DevSecOps engineer. Given the following security findings and
risk assessment, generate actionable fix recommendations.

Findings: {findings}
Risk Score: {risk_score}

For each finding, provide:
1. A clear code-level fix recommendation
2. A before/after code example if applicable
3. Package update command if it's a dependency issue

Return a JSON object with:
  recommendations: list of recommendation strings
  fix_examples: list of {"finding_type": str, "before": str, "after": str}

Return ONLY valid JSON.
```

**Analisis Security:**

- **Actionability**: Prompt meminta _code-level fix_ dan _before/after examples_, bukan saran generik. Ini memastikan rekomendasi bisa langsung diimplementasikan developer.
- **Dependency specificity**: Prompt secara eksplisit meminta _package update command_ untuk dependency issues — bukan abstrak "update your dependencies".
- **Risk context**: `risk_score` di-inject agar LLM memprioritaskan rekomendasi sesuai tingkat risiko.

---

### 3.8 Prompt 8: Workflow Generator (Fallback) — GitHub Actions Expert

**File:** `ai-service/app/agents/nodes/workflow_generator.py:13-155`  
**Status:** Tidak aktif sejak revisi Juni 2026 — digantikan oleh `_build_workflow_yaml()` deterministik.

Prompt ini dipertahankan sebagai dokumentasi historis dan fallback darurat. Generator aktif sekarang adalah `_build_workflow_yaml` (`workflow_generator.py:1202-1737`) yang membangun YAML job-per-job dari stage yang dipilih oleh `_select_relevant_stages` + `_filter_stages_by_evidence`.

**Alasan beralih ke deterministik:**
1. Reproducibility — 10 run untuk input yang sama harus menghasilkan output identik
2. Audit-friendly — dapat di-trace tool apa yang digunakan untuk setiap job
3. SHA-pinning konsisten — tidak ada risiko LLM mengarang SHA hash
4. Tidak tergantung LLM availability — generator bisa jalan tanpa AI service

---

## 4. Analisis Prompt Engineering Domain Context-Aware

### 4.1 Bagaimana Domain Mempengaruhi Setiap Prompt

Domain aplikasi adalah **dimensi ke-4** dari repository context (bersama technology, architecture, deployment), dan menjadi kunci adaptasi pipeline. Berikut adalah bagaimana setiap node mengonsumsi konteks domain:

| Node | Bagaimana Domain Digunakan | Mekanisme |
|------|---------------------------|-----------|
| `domain_detection` | Mendeteksi domain via LLM + heuristic scoring | Lihat §4.2 |
| `security_requirement_inference` | Domain-specific threats di-inject ke prompt; LLM diminta mapping threat → control | `IMPORTANT: For {domain} webapps, PRIORITIZE controls... Map each threat to a specific control.` |
| `domain_priority` | Post-processing severity elevation berbasis keyword domain | Lihat §4.3 |
| `vulnerability_scan` | Architecture-aware (subset dari domain context) | Microservice-specific checks |
| `workflow_generator` | Stage selection berdasarkan domain-context dari inference | `_select_relevant_stages()` + vignette |

### 4.2 Prompt Domain Detection — Industry Analyst

**File:** `ai-service/app/agents/nodes/domain_detection_node.py:251-279`

```
You are classifying the web application domain of a GitHub repository.

Based on the following signals, classify the domain into ONE of:
  e-commerce | healthcare | fintech | blog | iot | education | general

Repository name: {repo_name}
Repository description: {repo_description}
Detected libraries (top 50): {libraries}
Detected entity/model names (top 30): {entities}
Detected route hints (top 30): {routes}
Candidate domain scores from deterministic signal matching: {scores}

━━━ PER-DOMAIN SIGNAL DICTIONARY ━━━

E-COMMERCE — typical signal patterns:
  Libraries: stripe, @stripe/stripe-js, paypal, braintree, square, shopify-api,
             woocommerce, @shopify/shopify-api, squareup, razorpay, midtrans
  Entities: order, orders, product, products, cart, cart_item, payment,
            checkout, invoice, shipment, refund, coupon, discount, customer,
            billing_address, shipping_address, line_item, inventory, sku
  Routes: /checkout, /cart, /payment, /orders, /products/:id, /shop,
          /invoice, /refund, /wishlist, /billing, /shipping
  Files: src/routes/checkout.js, src/controllers/payment.js,
         src/models/Order.js, src/models/Product.js, prisma/schema.prisma
         (with orderId/productId fields), migrations/orders_table.sql

HEALTHCARE — typical signal patterns:
  Libraries: fhir-kit, hapi-fhir, hl7apy, epic, cerner-fhir, smart-on-fhir,
             openmrs, dcm4che, orthanc, pydicom
  Entities: patient, patients, appointment, appointments, prescription,
            prescriptions, diagnosis, ehr, emr, medical_record, doctor,
            physician, clinic, hospital, treatment, medication
  Routes: /patients, /appointments, /prescriptions, /records, /ehr,
          /diagnosis, /medical-history, /clinic
  Files: Patient.java, Appointment.java, FHIR/Patient.json,
         HIPAA compliance docs

FINTECH — typical signal patterns:
  Libraries: plaid, alpaca-trade-api, ibkr, stripe-connect, square-connect,
             quickbooks, xero, yodlee, finicity
  Entities: account, accounts, transaction, transactions, ledger, wallet,
            balance, transfer, deposit, withdrawal, portfolio, holdings,
            trade, order_book, kyc, aml
  Routes: /accounts, /transactions, /ledger, /transfer, /balance,
          /portfolio, /trades, /wallet
  Files: Account.java, Transaction.java, LedgerEntry.java,
         Decimal/BigDecimal usage (currency precision)

BLOG — typical signal patterns:
  Libraries: marked, markdown-it, sanitize-html, dompurify, prismjs,
             highlight.js, gray-matter, hexo, gatsby, jekyll, wordpress
  Entities: post, posts, article, articles, comment, comments, tag, tags,
            category, author, authors, subscriber
  Routes: /posts, /articles, /blog, /comments, /tags, /archive,
          /author/:id
  Files: posts/*.md, articles/*.md, content/posts/, src/components/Post.tsx

IOT — typical signal patterns:
  Libraries: paho-mqtt, mqtt, amqp, coap, azure-iot-device-sdk, aws-iot,
             google-iot, modbus, modbus-serial, opc-ua, influxdb-client
  Entities: device, devices, sensor, sensors, telemetry, actuator,
            firmware, gateway, thing, shadow, command
  Routes: /devices, /telemetry, /sensors, /firmware, /shadow, /command
  Files: firmware/*.bin, device-sdk/*, src/devices/

EDUCATION — typical signal patterns:
  Libraries: moodle-sdk, canvas-lms, scorm, xapi, blackboard, edx-platform,
             open-edx
  Entities: course, courses, enrollment, enrollments, quiz, quizzes,
            student, students, grade, grades, assignment, submissions,
            instructor, teaching-assistant
  Routes: /courses, /enrollments, /quizzes, /grades, /submissions,
          /assignments, /students
  Files: Course.java, Enrollment.java, Quiz.java

━━━ DECISION RULES ━━━

1. EXACT match wins. If a library like "stripe" is detected, classify as
   e-commerce even if there are also signals for blog.

2. MULTIPLE signals stack. A repo with libraries [stripe, marked] is still
   e-commerce (payment is the primary business), but mention the blog
   component in evidence.

3. ROUTE patterns override entity names. A repo with /checkout, /orders,
   /products routes is e-commerce even if entity names are generic
   (item, thing).

4. If no domain-specific signal is found, classify as "general" with
   confidence 1.0.

5. Confidence reflects how CERTAIN you are:
   - 0.90-1.00: 3+ signals from at least 2 categories (library + entity + route)
   - 0.70-0.89: 2 signals from 2 categories
   - 0.50-0.69: 1 strong signal (e.g., only entity names, or only 1 library)
   - < 0.50: weak signal, classify as "general" instead

Return ONLY valid JSON:
{
  "domain": "...",
  "confidence": 0.0-1.0,
  "evidence": [
    "Library 'stripe' detected in package.json",
    "Route /checkout/* defined in src/routes/",
    "Entity 'Order' modeled in src/models/Order.js"
  ],
  "domain_threats": [
    "SQL injection in /checkout endpoint (PCI-DSS 6.2.4)",
    "Stripe API key hardcoded in source code",
    "CSRF protection missing on payment POST endpoints",
    "Price tampering via client-supplied price not re-validated",
    "Cardholder data exposure in logs (PCI-DSS 3.2)"
  ]
}
```

**Analisis Domain Context-Aware (Updated):**

| Domain | Library Indicators | Entity Indicators | Route Indicators | Unique Threats |
|--------|-------------------|-------------------|------------------|----------------|
| **e-commerce** | stripe, paypal, braintree, square, shopify-api, woocommerce, razorpay, midtrans | order, product, cart, payment, checkout, invoice, shipment, refund, sku | /checkout, /cart, /payment, /orders, /products/:id, /shop, /invoice, /refund | Stripe key hardcoded, SQLi checkout, CSRF payment, card data in logs, price tampering, race condition inventory |
| **healthcare** | fhir, hapi-fhir, hl7, epic, cerner, smart-on-fhir, openmrs, dcm4che, pydicom | patient, appointment, prescription, diagnosis, ehr, emr, medical_record, doctor, clinic | /patients, /appointments, /prescriptions, /records, /ehr, /diagnosis | PHI exposure, weak auth medical data, HIPAA audit failures, FHIR API without OAuth2, IDOR cross-patient |
| **fintech** | plaid, alpaca, ibkr, stripe-connect, quickbooks, xero, yodlee | account, transaction, ledger, wallet, balance, transfer, kyc, aml, portfolio | /accounts, /transactions, /ledger, /transfer, /balance, /portfolio, /wallet | Transaction tampering, double-spend race, KYC bypass, replay attack, insider threat, currency precision bug |
| **blog** | marked, markdown-it, sanitize-html, dompurify, prismjs, highlight.js, gray-matter, gatsby, jekyll | post, article, comment, tag, category, author, subscriber | /posts, /articles, /blog, /comments, /tags, /archive, /author/:id | XSS comment, file upload bypass, path traversal, RCE via SVG, markdown injection, SSRF image fetch |
| **iot** | paho-mqtt, mqtt, amqp, coap, azure-iot, aws-iot, modbus, opc-ua | device, sensor, telemetry, actuator, firmware, gateway, thing, shadow | /devices, /telemetry, /sensors, /firmware, /shadow, /command | Device auth bypass, MQTT no encryption, firmware tampering, default credentials, buffer overflow |
| **education** | moodle-sdk, canvas-lms, scorm, xapi, blackboard, edx-platform | course, enrollment, quiz, student, grade, assignment, submission, instructor | /courses, /enrollments, /quizzes, /grades, /submissions, /assignments | Grade tampering, PII exposure, cheating bypass, SCORM data leak, IDOR submissions |

**Hybrid Architecture (LLM + Deterministic Scoring):**

```
Step 1: Deterministic signal extraction
  → Extract library names from package.json/requirements.txt/go.mod
  → Extract entity names from model files
  → Extract route patterns from route handlers

Step 2: Deterministic scoring (_score_domain)
  → library match weight: 3.0
  → entity match weight:   2.0
  → route match weight:    1.5
  → Normalize 0.0–1.0

Step 3: LLM classification
  → Prompt includes candidate scores sebagai hint
  → Prompt includes per-domain signal dictionary (above)
  → LLM mengembalikan domain + confidence + evidence + threats

Step 4: Fallback & correction
  → Jika confidence < 0.50 → fallback ke "general"
  → Jika LLM pilih domain tapi heuristic scores lebih tinggi untuk domain lain
    DAN confidence LLM < 0.7 → override ke heuristic top
  → Jika domain == "general" → confidence = 1.0
```

### 4.3 Domain-Aware Severity Priority — Deterministic Post-Process

**File:** `ai-service/app/agents/domain_priority.py:30-120`

Bukan bagian dari prompt engineering (karena 100% deterministik), tetapi sangat relevan untuk analisis domain context-aware:

**Rules per Domain:**

| Domain | Critical Keywords | High Keywords | File Patterns |
|--------|-------------------|---------------|---------------|
| e-commerce | stripe, paypal, payment, credit_card, billing, checkout, transaction, price_tamper | order, cart, csrf, xss.payment, auth.bypass | checkout, payment, billing, cart |
| healthcare | patient.data, phi, medical_record, ehr, fhir, hl7, hipaa | appointment, auth.bypass, weak.auth, audit_log | patient, appointment, prescription, fhir, ehr |
| fintech | transaction.tamper, ledger, transfer, wallet, kyc.bypass, replay.attack, insider.threat | account, balance, settlement, brokerage | account, transaction, ledger, wallet |
| blog | file_upload.bypass, rce.upload, path_traversal.upload | xss, csrf, content_injection, sanitiz, markdown.inject | comment, post, article |
| iot | device.auth.bypass, firmware.tamper, default.credential | mqtt, amqp, coap, modbus, telemetry, tls.missing | device, sensor, telemetry |
| education | grade.tamper, student.data.exposure | student, course, enrollment, quiz, submission, cheating.bypass | course, enrollment, quiz, student |
| general | — | — | — (no boost) |

**Severity Bump Logic (dalam kode):**

```python
def _bump_severity(current: str, target: str) -> str:
    # Hanya naik, tidak pernah turun
    if SEVERITY_RANK.get(target, 0) > SEVERITY_RANK.get(current, 0):
        return target
    return current
```

**Traceability:** Setiap finding yang severity-nya di-boost mendapat metadata `severity_boost`:
```json
{
  "severity_boost": {
    "applied": true,
    "original_severity": "medium",
    "final_severity": "critical",
    "matched_rule": "file_pattern_match",
    "domain": "healthcare"
  }
}
```

### 4.4 Attack Surface → Control Mapping (Deterministic Lookup Table)

**File:** `ai-service/app/agents/attack_surface_lookup.py:18-58`

Jembatan deterministik antara deployment target dan kontrol keamanan:

| Deployment Target | Attack Surfaces | Implied Controls |
|-------------------|-----------------|------------------|
| docker | Container Image, Dockerfile Config, Image Layer Secrets | `container_scan`, `cve_scan`, `container_build`, `secret_scan` |
| kubernetes | RBAC, Container Images, Ingress, Service Accounts, Pod Security | `iac_scan`, `service_mesh_audit`, `container_scan` |
| terraform | S3 Bucket ACL, IAM Role Permissions, Security Group Rules | `iac_scan` |
| code-only | Source Code, Dependencies, Secrets in Code | `sast`, `dependency_scan`, `cve_scan`, `secret_scan` |

> **Catatan penting (revisi Juni 2026):** Pada revisi sebelumnya, `iac_scan` di-include
> di attack surface `Dockerfile Config` (sehingga Dockerfile saja sudah men-trigger
> `iac-scan` job). **Revisi sekarang memisahkan**: `iac_scan` strictly untuk
> Terraform / K8s / Helm. Dockerfile auditing di-cover oleh `container_scan`
> (Trivy image + config mode). Alasan: menghindari over-include `iac-scan` di
> repository yang hanya punya Dockerfile tapi tidak ada IaC files.

Tujuan: menjamin minimum control coverage tetap ada meskipun LLM melakukan kesalahan inferensi. Ini dijamin oleh `_enforce_mandatory_controls()`.

---

## 5. Deterministic Safety Guards

### 5.1 Tabel Guardrails per Node

| Node | Guardrail | Jenis | Efek |
|------|----------|-------|------|
| technology_detection | `_detect_from_extensions()` fallback jika `primary_language` kosong | Fallback | Pipeline tetap ada meskipun LLM gagal |
| architecture_detection | Default `monolithic` | Default | Tidak blocking pipeline |
| deployment_detection | `_detect_from_files()` deterministic + LLM merge | Override | Mencegah halusinasi deployment |
| deployment_detection | Override `alternative_deployment_targets` | Override | Mencegah halusinasi cloud provider (Railway, Render) |
| domain_detection | Heuristic scoring inject ke prompt + heuristic override jika confidence < 0.7 | Override | Domain tidak serampangan |
| domain_detection | Threshold 0.50 → fallback "general" | Fallback | Mencegah misklasifikasi |
| vulnerability_scan | Pattern scan regex sebagai baseline | Fallback | Temuan tetap ada meskipun LLM gagal |
| security_requirement_inference | `_enforce_mandatory_controls()` | Invariant | Minimum control coverage dijamin |
| security_requirement_inference | Microservice-specific stage injection jika `arch_type ∈ {microservices, modular_monolith}` | Invariant | arsitektur kompleks tidak kehilangan stage |
| security_analyzer | `_merge_enrichment()`: lock field evidence | Invariant | Tidak boleh overwrite `file`, `line`, `code_snippet` |
| workflow_generator (aktif) | `_filter_stages_by_evidence()`: drop stage tanpa bukti | Invariant | Tidak generate job yang tidak relevan |
| workflow_generator (aktif) | `_select_relevant_stages()`: test hanya jika test_framework detected | Invariant | Job tidak failure karena tool tidak ada |
| domain_priority | Severity boost hanya naik (tidak pernah turun) | Invariant | Mempertahankan severity original sebagai baseline |

### 5.2 Three-Tier Safety Architecture

```
Tier 1: Prompt-level constraint
  → Instruksi dalam prompt (e.g., "Do NOT add new findings")
  → Instructive guardrail — LLM bisa mengabaikan

Tier 2: Code-level invariant (post-LLM enforcement)
  → _enforce_mandatory_controls(), _merge_enrichment()
  → Procedural guardrail — tidak bisa diabaikan

Tier 3: Deterministic fallback (pre-LLM baseline)
  → _detect_from_files(), PATTERN_RULES, _score_domain()
  → Fallback guardrail — sistem tetap berjalan tanpa LLM
```

---

## 6. Metodologi Prompt Engineering

### 6.1 Prompt Design Principles

Setiap prompt dalam sistem mengikuti struktur:

```
1. PERSONA DECLARATION
   "You are a [role] doing [task]"
   
2. CONTEXT INJECTION
   Variables dari state: {technologies}, {architecture}, {deployment}, {domain}
   
3. TASK SPECIFICATION
   Daftar field yang harus di-output + format JSON/YAML
   
4. DOMAIN-BRANCHING INSTRUCTIONS (conditional)
   IF architecture == "microservices" → ADD checks
   For {domain} webapps → PRIORITIZE controls
   
5. OUTPUT CONSTRAINT
   "Return ONLY valid JSON/YAML. No markdown. No explanations."
```

### 6.2 Tabel Perbandingan Panjang Prompt per Node

| Node | Baris Prompt | Field Output | Kompleksitas |
|------|-------------|-------------|--------------|
| technology_detection | 28 baris | 11 field | Rendah |
| architecture_detection | 30 baris | 10 field | Rendah |
| deployment_detection | 37 baris | 11 field | Rendah |
| domain_detection | 28 baris | 4 field | Rendah |
| vulnerability_scan | 51 baris | 10 field per finding | **Tinggi** |
| security_requirement_inference | 87 baris | 17 kontrol + tools + stages | **Sangat Tinggi** |
| security_analyzer (enrichment) | 33 baris | 16 field per finding | Sedang |
| recommendation_gen | 17 baris | 2 array | Rendah |
| workflow_generator (fallback) | 142 baris | 1 YAML document | **Sangat Tinggi** |

### 6.3 Chain of Context (Context Provenance)

Tidak ada prompt yang berdiri sendiri — setiap prompt downstream bergantung pada output upstream:

```
repository_files ──→ technology_detection ──→ architecture_detection
                         │                          │
                         ├──────────────────────────┤
                         ↓                          ↓
                    deployment_detection      vulnerability_scan
                         │                     (architecture-aware)
                         │                          │
                         ├──────────────────────────┤
                         ↓                          ↓
                    domain_detection    security_requirement_inference
                         │               (technology + architecture +
                         │                deployment + domain + attack_surfaces)
                         ↓                          │
                    domain_priority                  ↓
                    (post-scan,               workflow_generator
                     per finding)            (stages dari inference)
                                                   │
                                                   ↓
                                             security_analyzer
                                             (findings dari vulnerability
                                              scan + scanner outputs)
                                                   │
                                                   ↓
                                            recommendation_gen
                                            (findings + risk_score)
```

---

## 7. Vignette: Efek Domain pada Output Pipeline

### 7.1 Aturan Umum

Pipeline output dihasilkan oleh **3 mekanisme叠加 (stacking)**:

1. **Mandatory controls** dari `attack_surface_lookup` (deployment → attack surface → control)
2. **Domain-specific controls** dari `security_requirement_inference` prompt
3. **File evidence filter** dari `_has_dockerfile()`, `_has_iac()`, `_has_test_framework()` di `workflow_generator.py`

Stage hanya di-emit jika **semua 3 kondisi** terpenuhi. Contoh:
- `iac-scan` ada di attack surface mapping (untuk `docker`), TAPI tidak lolos `_has_iac()` di workflow generator kalau repo hanya punya Dockerfile (tanpa `*.tf`, `Chart.yaml`, `k8s/`, `helm/`, `terraform/`) → **DROPPED, masuk `invalid_workflow_stages`**.
- `cve-scan` digabung ke `dependency-scan` job (tidak standalone).
- `per-service-sast` hanya muncul kalau `arch_type ∈ {microservices, modular_monolith}`.

### Vignette 1: E-Commerce Monolith (Node.js + Express + Dockerfile) — `eccomerce-monolith-vuln`

**Repository context:**
- `detected_technologies`: JavaScript, Express, Jest, npm, SQLite
- `detected_architecture`: monolithic (1 server, 1 DB)
- `detected_deployment`: docker=True, kubernetes=False, terraform=False
- `detected_domain`: e-commerce (confidence 0.85) — libraries=none detected, entities=[Order, Product, Cart, Payment], routes=[/checkout, /orders, /products/:id/review, /cart]
- `repository_files`: `Dockerfile`, `package.json`, `package-lock.json`, `src/routes/*.js`
- `inferred_security_needs`: 12 controls (sast, secret_scan, container_*, iac_scan, sbom, dll)

**Pipeline output (9 jobs, REAL generator output):**

```yaml
name: CI DevSecOps (javascript)
on: [push, pull_request, workflow_dispatch]
permissions: { contents: read }
concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }
jobs:
  lint:           # ESLint — primary_language=javascript, package_manager=npm
  test:           # Jest — test_framework detected
  build:          # npm run build
  sast:           # Semgrep 7 rule sets: p/owasp-top-ten, p/javascript, p/nodejs,
                  # p/expressjs, p/sql-injection, p/secrets, p/dockerfile
  dependency-scan: # npm audit (CVE HIGH) + Trivy fs scan
  secret-scan:    # Gitleaks full git history
  container-build: # docker build -t app:latest
  container-scan:  # Trivy image scan (depends: container-build)
  sbom:            # Syft SPDX
```

**Dropped stages (masuk `invalid_workflow_stages`):**

| Stage | Alasan drop | SSoT |
|---|---|---|
| `iac-scan` | No Terraform/K8s/Helm artifacts (Dockerfile alone not enough) | `_has_iac()` di workflow_generator.py |
| `service-mesh-audit` | No Istio/Linkerd/Consul/Kuma config | `attack_surface_lookup` |
| `api-gateway-test` | No nginx.conf / API gateway config | `attack_surface_lookup` |
| `per-service-sast` | Architecture monolithic, not microservices | `_get_arch_type()` |
| `per-service-dep-scan` | Architecture monolithic | `_get_arch_type()` |
| `license-check` | Status `optional`, default dropped | `security_requirement_inference` |
| `deploy` | No explicit CD platform config | `security_requirement_inference` |

**Efek domain e-commerce pada output:**
- `sast` rule sets spesifik: `p/sql-injection` + `p/javascript` + `p/nodejs` + `p/expressjs` (fokus SQLi di /checkout, XSS di /products/:id/review, CSRF middleware check, hardcoded JWT secret)
- `secret-scan` fokus: Stripe API key (`sk_live_`), PayPal, AWS access key
- `dependency-scan` CVE gate: `--audit-level=high` (PCI-DSS 6.3 minimum, tapi tidak separate critical-only job)
- `domain_priority` elevasi: finding dengan keyword "checkout", "payment", "stripe", "credit_card" → severity CRITICAL/HIGH
- `sbom` job: generate SPDX JSON, **TAPI TIDAK upload ke GitHub Dependency Graph** (gap PCI-DSS 6.3.5)

**Gap yang diketahui (future work):**
1. `cve-scan` (CRITICAL only) tidak standalone job — gabung ke `dependency-scan`
2. `container-config-scan` (Trivy config mode) tidak ada — Dockerfile misconfig di-cover Semgrep saja
3. `csrf-check`, `auth-strength`, `session-security`, `input-validation`, `cors-check` — custom Semgrep rules belum di-bundle
4. SBOM tidak auto-upload ke GitHub Dependency submission API

### Vignette 2: Healthcare Microservices (Python FastAPI + Kubernetes + Terraform)

**Repository context:**
- `detected_technologies`: Python, FastAPI, pytest, pip, PostgreSQL
- `detected_architecture`: microservices (5 services: patient-api, appointment-api, prescription-api, ehr-api, billing-api)
- `detected_deployment`: docker=True, kubernetes=True (manifests in `k8s/`), terraform=True (VPC + RDS)
- `detected_domain`: healthcare (confidence 0.92) — libraries=[hapi-fhir, fastapi], entities=[Patient, Appointment, Prescription, EHR], routes=[/patients, /appointments, /prescriptions]

**Pipeline output (13 jobs):**

```yaml
name: CI DevSecOps (python-microservices)
on: [push, pull_request, workflow_dispatch]
permissions: { contents: read }
concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }
jobs:
  lint:                # Ruff
  test:                # pytest
  build:               # python -m build / Docker build per service
  sast:                # Semgrep — fokus auth-bypass, injection, insecure-crypto,
                       # ditambah healthcare-specific: PHI exposure, FHIR API
                       # tanpa OAuth2, IDOR cross-patient
  dependency-scan:     # pip-audit — fokus FHIR/HL7 library CVEs
  secret-scan:         # Gitleaks — fokus FHIR API keys, DB credentials
  container-build:     # docker build per service (matrix)
  container-scan:      # Trivy image per service
  sbom:                # Syft SPDX per service
  # microservices-specific:
  per-service-sast:    # matrix build: scan each service directory
  per-service-dep-scan: # matrix build: pip-audit per service
  service-mesh-audit:  # check Istio/Linkerd mTLS, network policies
  api-gateway-test:    # validate Kong/nginx rate limit, CORS, auth
```

**Dropped stages:** `license-check` (optional), `deploy` (no CD config), `iac-scan` (TIDAK — di-include karena Terraform + K8s ada).

**Efek domain healthcare pada output:**
- `sast` rule sets: `p/python`, `p/flask`, `p/fastapi`, `p/owasp-top-ten`, ditambah custom healthcare rules
- `secret-scan` fokus: FHIR API tokens, DB credentials dengan PHI access
- `dependency-scan` gate: `pip-audit --strict` (CRITICAL only) — HIPAA data integrity
- `service-mesh-audit` WAJIB — HIPAA transmission security (164.312(e))
- `api-gateway-test` WAJIB — patient data access logging (HIPAA 164.312(b))
- `domain_priority` elevasi: "patient_data", "phi", "fhir", "hipaa" → CRITICAL

**Catatan penting:** `service_mesh_audit` dan `api_gateway_test` HANYA muncul di microservices
architecture. Untuk monolith, keduanya di-drop (lihat Vignette 1).

### Vignette 3: Blog Content Platform (Go)

**Repository context:**
- `detected_technologies`: Go, Gin, SQLite, no test framework
- `detected_architecture`: monolithic
- `detected_deployment`: code-only (no Dockerfile)
- `detected_domain`: blog (confidence 0.78) — libraries=[gin, markdown-it], entities=[Post, Comment, Tag], routes=[/posts, /comments, /tags]

**Pipeline output (6 jobs):**

```yaml
name: CI DevSecOps (go)
on: [push, pull_request, workflow_dispatch]
permissions: { contents: read }
concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }
jobs:
  lint:           # fallback ke Semgrep (Go tidak punya linter built-in di generator)
  build:          # go build
  sast:           # Semgrep OWASP Top 10 + p/go + p/golang —
                  # fokus XSS di markdown rendering, file upload bypass,
                  # path traversal di upload, SSRF image fetch
  dependency-scan: # Trivy fs — Go modules
  secret-scan:    # Gitleaks
```

**Dropped stages:**

| Stage | Alasan drop |
|---|---|
| `test` | No Go test files detected (`*_test.go`) |
| `container-build` | No Dockerfile |
| `container-scan` | No container (depends on container-build) |
| `sbom` | No container to SBOM |
| `iac-scan` | No K8s/Terraform |
| `service-mesh-audit`, `api-gateway-test`, `per-service-sast` | Monolith, not microservices |
| `license-check` | Optional, default dropped |

**Efek domain blog pada output:**
- `sast` rule sets: `p/owasp-top-ten` + `p/golang` + `p/security-audit` (XSS, path traversal, file upload bypass)
- `dependency-scan` gate: HIGH/CRITICAL only (no PCI-DSS / HIPAA constraint)
- `domain_priority` elevasi: "xss", "file_upload.bypass" → CRITICAL, "markdown.inject" → HIGH
- Tidak ada container stage (code-only deployment)

### Vignette 4: Fintech Microservices (Go + Stripe Connect + Kubernetes)

**Repository context:**
- `detected_technologies`: Go, Gin, PostgreSQL, no test framework
- `detected_architecture`: microservices (3 services: account-svc, transaction-svc, ledger-svc)
- `detected_deployment`: docker=True, kubernetes=True
- `detected_domain`: fintech (confidence 0.91) — libraries=[stripe-go, plaid-go], entities=[Account, Transaction, Ledger, Wallet], routes=[/accounts, /transactions, /transfer, /balance]

**Pipeline output (10 jobs):**

```yaml
name: CI DevSecOps (go-microservices)
on: [push, pull_request, workflow_dispatch]
jobs:
  lint:                # Semgrep fallback
  build:               # go build per service
  sast:                # fokus transaction tampering, race condition,
                       # KYC bypass, replay attack, currency precision
  dependency-scan:     # Trivy fs — go modules, fokus financial libraries
  secret-scan:         # Gitleaks — Stripe Connect keys, Plaid tokens
  container-build:     # docker build per service
  container-scan:      # Trivy image
  sbom:                # Syft — regulatory submission requirement
  per-service-sast:    # matrix
  per-service-dep-scan: # matrix
```

**Efek domain fintech pada output:**
- `sast` fokus: transaction tampering, KYC bypass, replay attack, currency precision (Decimal not float)
- `dependency-scan` CRITICAL gate: financial compliance
- `secret-scan` fokus: Stripe Connect (`sk_live_`, `pk_live_`), Plaid, Alpaca
- `domain_priority` elevasi: "transaction", "ledger", "wallet", "kyc" → CRITICAL
- TIDAK ada `service_mesh_audit` / `api_gateway_test` kalau tidak ada Istio/API gateway (gap, future work)

### Vignette 5: IoT Firmware (C++ + MQTT + AWS IoT)

**Repository context:**
- `detected_technologies`: C++, no test framework
- `detected_architecture`: monolithic (1 firmware binary)
- `detected_deployment`: docker=False, no Kubernetes, no Terraform
- `detected_domain`: iot (confidence 0.83) — libraries=[paho-mqtt, aws-iot-device-sdk], entities=[Device, Sensor, Telemetry, Firmware], routes=[]

**Pipeline output (4 jobs):**

```yaml
name: CI DevSecOps (cpp)
on: [push, pull_request, workflow_dispatch]
jobs:
  lint:                # Semgrep cpp rules
  sast:                # fokus device auth bypass, MQTT tanpa TLS,
                       # hardcoded device cert, buffer overflow
  dependency-scan:     # Trivy fs — C++ libraries
  secret-scan:         # Gitleaks — device certificates, factory keys
```

**Dropped stages:**

| Stage | Alasan drop |
|---|---|
| `test` | No C++ test framework detected |
| `build` | No `Makefile` / `CMakeLists.txt` at root detected |
| `container-build` | No Dockerfile |
| `container-scan` | Depends on container-build |
| `sbom` | No container |
| `iac-scan` | No K8s/Terraform |
| Semua microservices-specific | Monolith firmware |

**Efek domain iot pada output:**
- `sast` fokus: device auth bypass, hardcoded credentials, buffer overflow (CWE-120), MQTT plaintext
- `secret-scan` fokus: device certificates, factory default keys
- `domain_priority` elevasi: "device.auth", "firmware", "mqtt" → CRITICAL
- **Gap signifikan:** tidak ada binary scanning job (mis. `binwalk`, `checksec` untuk firmware analysis) — di luar scope generator saat ini

### Ringkasan Tabel: Stage Emission per Vignette

| Stage | E-Comm Monolith | Healthcare Microservices | Blog Go | Fintech Microservices | IoT C++ |
|---|---|---|---|---|---|
| `lint` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `test` | ✅ | ✅ | ❌ no framework | ❌ no framework | ❌ no framework |
| `build` | ✅ | ✅ | ✅ | ✅ | ❌ no Makefile |
| `sast` | ✅ 7 rulesets | ✅ + healthcare | ✅ + p/golang | ✅ + fintech | ✅ + p/cpp |
| `dependency-scan` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `secret-scan` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `container-build` | ✅ | ✅ | ❌ no Dockerfile | ✅ | ❌ |
| `container-scan` | ✅ | ✅ | ❌ | ✅ | ❌ |
| `sbom` | ✅ | ✅ | ❌ | ✅ | ❌ |
| `iac-scan` | ❌ no IaC | ✅ K8s+TF | ❌ | ✅ K8s | ❌ |
| `service-mesh-audit` | ❌ monolith | ✅ Istio | ❌ | ❌ no mesh | ❌ |
| `api-gateway-test` | ❌ monolith | ✅ | ❌ | ❌ | ❌ |
| `per-service-sast` | ❌ monolith | ✅ | ❌ | ✅ | ❌ monolith |
| `per-service-dep-scan` | ❌ monolith | ✅ | ❌ | ✅ | ❌ |
| `license-check` | ❌ optional | ❌ optional | ❌ optional | ❌ optional | ❌ optional |
| `deploy` | ❌ no CD | ❌ no CD | ❌ no CD | ❌ no CD | ❌ no CD |

**Total jobs:** 9 (e-comm), 13 (healthcare μS), 6 (blog), 10 (fintech μS), 4 (IoT)

---

## 8. Referensi File Implementasi

### 8.1 Prompt Source Files

| Node | File | Baris Prompt |
|------|------|-------------|
| technology_detection | `ai-service/app/agents/nodes/technology_detection_node.py` | 20-47 |
| architecture_detection | `ai-service/app/agents/nodes/architecture_detection_node.py` | 8-37 |
| deployment_detection | `ai-service/app/agents/nodes/deployment_detection_node.py` | 7-44 |
| domain_detection | `ai-service/app/agents/nodes/domain_detection_node.py` | 251-279 |
| vulnerability_scan | `ai-service/app/agents/nodes/vulnerability_scan_node.py` | 21-71 |
| security_requirement_inference | `ai-service/app/agents/nodes/security_requirement_inference_node.py` | 11-97 |
| security_analyzer (enrichment) | `ai-service/app/agents/nodes/security_analyzer.py` | 33-65 |
| recommendation_gen | `ai-service/app/agents/nodes/recommendation_gen.py` | 4-21 |
| workflow_generator (fallback) | `ai-service/app/agents/nodes/workflow_generator.py` | 13-155 |
| workflow_generator (deterministik aktif) | `ai-service/app/agents/nodes/workflow_generator.py` | 1202-1737 |

### 8.2 Deterministic Helper Files

| File | Fungsi |
|------|--------|
| `ai-service/app/agents/attack_surface_lookup.py` | Deployment → Attack Surface mapping |
| `ai-service/app/agents/domain_priority.py` | Domain-aware severity elevation |
| `ai-service/app/agents/security_finding_normalizer.py` | Normalisasi + deduplikasi findings |
| `ai-service/app/agents/finding_categories.py` | Klasifikasi finding (security vs non-security) |
| `ai-service/app/agents/pipeline_state.py` | Pipeline state TypedDict schema |
| `ai-service/app/agents/pipeline_schemas.py` | Pydantic schemas (SecurityFinding, dll.) |
| `ai-service/app/services/llm_service.py` | LLM invocation wrapper |
| `ai-service/app/utils/json_extractor.py` | Robust JSON extraction dari LLM output |

### 8.3 Dokumen Pendukung

| File | Deskripsi |
|------|-----------|
| `struktur-v6.md` | Struktur naskah BAB 1–6, §3.9 Prompt Engineering |
| `docs/system-analysis/06-langgraph-agent-flow.md` | LangGraph agent flow analysis |
| `docs/system-analysis/11-security-logic-flow.md` | Security logic flow |
| `docs/AI-AGENT-SECURITY-FINDINGS.md` | AI agent security findings bridge design |
| `ai-service/ARCHITECTURE.md` | AI service architecture |

---

## Appendiks: Checklist Menulis BAB 3 untuk Prompt Engineering

- [ ] **§3.9.1 — Klasifikasi Prompt:** Jelaskan 12 pipeline job dengan mapping persona + file
- [ ] **§3.9.2–§3.9.11 — Tiap Prompt:** Untuk setiap prompt, jelaskan:
  - [ ] Persona domain expert
  - [ ] Tujuan keamanan
  - [ ] Variabel yang di-inject
  - [ ] Output yang diharapkan
  - [ ] Fallback deterministik
  - [ ] Guardrail / invariant
- [ ] **§3.7 — Domain Context-Aware:** Jelaskan bagaimana domain mempengaruhi:
  - [ ] Prompt `domain_detection` (hybrid LLM + heuristic)
  - [ ] Prompt `security_requirement_inference` (domain_threats injection)
  - [ ] Post-process `domain_priority`
- [ ] **§3.7.3 — Attack Surface Lookup:** Jelaskan lookup table deployment → attack surface → control
- [ ] **§3.9.12–§3.9.13 — Dari Prompt ke Kode:** Jelaskan mekanisme mandatory control enforcement
- [ ] **§3.9.14–§3.9.16 — Vignette:** Tampilkan 3 contoh output pipeline untuk 3 domain berbeda
- [ ] **Tabel ringkasan:** 12-job table dengan kolom: node, persona, fungsi LLM, deterministik?, fallback
- [ ] **Diagram chain-of-context:** Tunjukkan informasi mengalir dari upstream → downstream node

---

## 9. Iterative Debugging Playbook (Failure Modes & Prompt Fixes)

Bagian ini merangkum **failure modes** yang ditemui saat validasi generator pipeline di lapangan, beserta **fix berlapis** di prompt engineering, code generator, dan log parser. Tujuannya: agar AI agent **men-generate workflow yang benar dari awal** dan **parser menampilkan vulnerability yang benar**, sehingga tidak perlu re-run workflow untuk validasi.

### 9.1 Failure Mode Catalogue

| ID | Failure Mode | Dampak | Lokasi Fix |
|---|---|---|---|
| FM-1 | Native module gagal compile di Node 24 (`CopyablePersistent`/`AccessorGetterCallback` error dari V8 API) | Semua job yang melakukan `npm install` fail | `workflow_generator.py` §3.5 + `log_finding_parser.go` |
| FM-2 | `actions/checkout@<SHA>` masih di-pin ke versi `using: node20` → warning deprecation muncul di setiap job | Runner log penuh warning, user bingung | `action_registry.py` + `workflow_generator.py` |
| FM-3 | `iac-scan` job di-emit untuk repo yang hanya punya Dockerfile (no Terraform/K8s/Helm) | Job `iac-scan` nothing-to-scan, misleading | `workflow_generator.py` (`_IAC_PATTERNS`) + `attack_surface_lookup.py` |
| FM-4 | `dependency-scan` tidak upload SARIF karena job fail sebelum scanner jalan | Code Scanning tab kosong, user lihat synthesized "config-error" | `log_finding_parser.go` + Code Scanning API integration |
| FM-5 | Security Controls panel advertise tool "eslint" tapi workflow pakai Semgrep | Tool mismatch → trust issue | `security_requirement_inference_node.py` |
| FM-6 | Merged controls (`cve_scan` → `dependency-scan`) hilang dari output | "No inconsistent stages detected" padahal ada mismatch | `workflow_generator.py` (`CONTROL_MERGED_INTO`) |
| FM-7 | "11 total" di Security Controls panel — confusing (recommended + optional tercampur) | UX issue | Frontend `PipelineGenerator.tsx` |
| FM-8 | `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` redundant (semua action sudah node24) | Workflow noise | `workflow_generator.py` (drop env var) |
| FM-9 | Scanner jobs fail tanpa parseable output, parser kasih generic "open the log" | User bingung, padahal SARIF sudah di-upload di Code Scanning tab | `log_finding_parser.go` (sarif-not-uploaded case) |

### 9.2 Prompt Engineering Fix per Failure Mode

#### FM-1: Native Module Build Failure

**Root cause**: Package lama (e.g. `better-sqlite3@7.4.3`) pakai V8 API yang dihapus di Node 24.

**Prompt engineering fix** (inject ke `security_requirement_inference_node.py:11`):

```
For JavaScript/TypeScript projects, when generating the `dependency-scan`,
`lint`, `test`, or `build` jobs, ALWAYS append `--ignore-scripts` to npm
install commands. Rationale: native modules (better-sqlite3, node-sass,
bcrypt, sharp) use V8 APIs that are removed in Node 22+. Skipping native
builds keeps the install deterministic; the scanner tools (npm audit,
Trivy, Semgrep) only need the lockfile, not a working node_modules.
```

**Code fix** (`workflow_generator.py:_node_setup_steps`):

```python
def _node_setup_steps(
    package_manager: str,
    has_lockfile: bool,
    node_version: str = "24",
    ignore_scripts: bool = False,  # NEW
) -> tuple[list[str], str]:
    # ...
    if ignore_scripts:
        install_cmd += " --ignore-scripts"
```

**Caller rule**: security-scan jobs (`sast`, `dependency-scan`, `secret-scan`) pass `ignore_scripts=True`. Real-CI jobs (`lint`, `test`, `build`) use default (no `--ignore-scripts`) karena butuh working modules.

**Log parser fix** (`log_finding_parser.go`):

```go
case strings.Contains(logText, "CopyablePersistent") || strings.Contains(logText, "AccessorGetterCallback"):
    title = "Native module build failure: outdated dependency"
    evidence = "..."
    remediation = "Upgrade the affected package to a version that supports the current Node.js runtime. For better-sqlite3, version 7.6.0+ supports Node 18+; version 8.x+ supports Node 22+. Alternatively, use `--ignore-scripts` to skip native builds."
    ruleID = "native-module-outdated"
    severity = "high"
```

#### FM-2: Node 20 Deprecation Warning

**Root cause**: Action SHAs pinned ke versi yang declare `using: node20` di `action.yml`.

**Prompt engineering fix** (inject ke `action_registry.py` — bukan LLM prompt, tapi reference table):

```
Action runtime compatibility is enforced by code, not prompt. Every action
in ACTION_REGISTRY has a `node_compatibility` field that mirrors the
`using:` declaration in the action's `action.yml` file:
  - `("node24",)` for actions whose action.yml declares `using: node24`
  - `("node20", "node24")` only if the action explicitly supports BOTH
  - `("composite",)` for actions that wrap Docker (e.g. trivy-action)
The registry is updated whenever a new major version of an action is
released. The legacy `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` env var is
NO LONGER emitted by the generator.
```

**Code fix** (`workflow_generator.py`): drop `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'` dari output YAML.

#### FM-3: iac-scan Over-Include

**Root cause**: `_IAC_PATTERNS` include `Dockerfile`. Repo yang hanya punya Dockerfile (no `*.tf`, `Chart.yaml`, `k8s/`) tetap men-trigger `iac-scan` job.

**Prompt engineering fix** (inject ke `workflow_generator.py:529-545` — dokumentasi internal):

```
The _IAC_PATTERNS glob list strictly matches Infrastructure-as-Code
files. A Dockerfile or docker-compose.yml is NOT IaC — it is a container
artifact. Auditing Dockerfile is the job of `container-scan` (Trivy
config mode) and `container-config-scan`, not `iac-scan`.

Acceptable patterns: *.tf, *.tfvars, *.tfstate, Chart.yaml, values.yaml
Acceptable directories: k8s/*, kubernetes/*, helm/*, terraform/*

A repo with only Dockerfile is NOT IaC-eligible.
```

**Code fix** (`workflow_generator.py`):

```python
_IAC_PATTERNS: tuple[str, ...] = (
    "*.tf", "*.tfvars", "*.tfstate",
    "Chart.yaml", "values.yaml",
)
_IAC_DIRECTORY_PATTERNS: tuple[str, ...] = (
    "k8s/*", "kubernetes/*", "helm/*", "terraform/*",
)
```

#### FM-4: Scanner Jobs Fail Before SARIF Upload

**Root cause**: Workflow configuration error di step sebelumnya (e.g. `npm install` gagal karena native module). Scanner tidak sempat run, SARIF tidak ter-upload.

**Prompt engineering fix** (inject ke `log_finding_parser.go`):

```go
isSarifScanner := scanner == "semgrep" || scanner == "trivy" ||
    scanner == "gitleaks" || scanner == "npm-audit" || scanner == "syft" ||
    scanner == "checkov"
if isSarifScanner && jobFailed {
    title = jobName + " failed before SARIF upload"
    evidence = "The {scanner} job exited with non-zero status before it could upload its SARIF report. This is almost always a workflow configuration problem (e.g. the job crashed, or an earlier step like `npm install` failed)."
    remediation = "Open the Code Scanning tab in this repository — alerts that were uploaded by EARLIER successful runs of this same workflow may still be listed there. Otherwise, fix the workflow (e.g. add `--ignore-scripts` to the failing npm install step) and trigger a new run so the scanner can complete and upload."
    ruleID = "sarif-not-uploaded"
    severity = "low"
}
```

**Backend integration** (`backend/internal/handlers/pipeline_handler.go:ExtractAllJobFindings`):

```go
// Tier 2: fetch Code Scanning alerts (canonical source of truth
// for SARIF-uploaded scanners). These exist even when the job
// failed before the log was emitted.
codeScanningAlerts, _ := svc.ListCodeScanningAlerts(decryptedToken, repo.FullName, 100)
for _, a := range codeScanningAlerts {
    // dedup against log-parsed findings
    // emit Finding with category=security_finding, type=code_scanning_alert
}
```

#### FM-5: SAST Tool Mismatch

**Root cause**: `_get_sast_tool()` return `"eslint"` untuk JavaScript, tapi workflow generator pakai Semgrep untuk semua bahasa.

**Prompt engineering fix** (`security_requirement_inference_node.py:_get_sast_tool`):

```python
def _get_sast_tool(technologies: dict) -> str:
    """SAST tool name. We use Semgrep for every language because:
    1. It has the broadest language coverage (JS/TS, Python, Go, Java, Ruby, Rust, C#, PHP)
    2. The workflow generator emits Semgrep (consistent across languages)
    3. Returning language-specific tools (eslint, bandit, spotbugs) creates
       a UI/workflow mismatch that erodes user trust.

    The displayed tool in the Security Controls panel MUST match the
    tool actually invoked in the generated YAML.
    """
    return "semgrep"
```

#### FM-6: Merged Controls Invisible

**Root cause**: Security controls yang di-merge ke job lain (e.g. `cve_scan` → `dependency-scan`) tidak di-track di output. User bingung "no inconsistent stages detected" padahal `cve_scan` listed di controls tapi tidak ada di generated stages.

**Prompt engineering fix** (`workflow_generator.py`):

```python
CONTROL_MERGED_INTO: dict[str, str] = {
    "cve_scan": "dependency-scan",
    "cve-scan": "dependency-scan",
    "per_service_sast": "sast",
    "per_service_dep_scan": "dependency-scan",
}

def _flag_merged_requested_controls(requested, generated) -> list[tuple[str, str]]:
    """Return (control, target_stage) for requested controls that are
    provided by another stage rather than a separate job."""
    # emit to workflow_config_issues so UI can render "cve_scan → dependency-scan"
```

#### FM-7: "11 total" Security Controls Count

**Root cause**: Frontend count "11 total" mencampur recommended + optional, confusing.

**Prompt engineering fix** (frontend `PipelineGenerator.tsx`):

```tsx
{(() => {
  const recommended = controls.filter(c => c.status === "recommended").length
  const optional = controls.filter(c => c.status === "optional").length
  return optional === 0 ? `${recommended} recommended` : `${recommended} recommended, ${optional} optional`
})()}
```

#### FM-8: Redundant `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`

**Prompt fix**: lihat FM-2.

#### FM-9: Generic "open the log" for Scanner Jobs

**Root cause**: Log parser kasih generic synthesized finding untuk scanner jobs yang fail. Padahal SARIF mungkin sudah upload, dan Code Scanning API bisa di-fetch langsung.

**Log parser fix** (sudah di §9.2 FM-4) + **Backend integration** untuk fetch Code Scanning API (FM-4 backend code).

### 9.3 Three-Tier Validation Stack

Setiap generated workflow harus lulus **3 tier validasi** sebelum di-deploy:

```
Tier 1: PROMPT-LEVEL CONSTRAINT (LLM guidance)
  ↓ e.g., "Use --ignore-scripts for security-scan jobs"
Tier 2: CODE-LEVEL INVARIANT (deterministic enforcement)
  ↓ e.g., `_node_setup_steps(ignore_scripts=True)` for security jobs
Tier 3: PARSER-LEVEL FALLBACK (log → findings)
  ↓ e.g., detect "CopyablePersistent" → emit native-module-outdated finding
```

Kalau tier 1 gagal (LLM hallucinate), tier 2 catch.
Kalau tier 2 gagal (code bug), tier 3 catch.
Kalau tier 3 gagal (regex miss), user lihat synthesized finding + manual debug.

### 9.4 Input Requirements untuk Debug

Untuk memperbaiki failure mode dengan tepat, butuh:

| Input | Required? | Contoh |
|---|---|---|
| Workflow YAML | Wajib | `.github/workflows/ai-devsecops-v31.yml` |
| Job log per failed job | Wajib | `dependency-scan` log dengan `CopyablePersistent` error |
| Repository file evidence | Wajib | `package.json`, `package-lock.json`, `Dockerfile` |
| Generator code | Wajib | `workflow_generator.py`, `action_registry.py` |
| Prompt doc | Optional | `PROMPT-ENGINEERING-BAB3.md` |
| Code Scanning alerts (if any) | Optional | `GET /repos/:owner/:repo/code-scanning/alerts` |
| LLM interaction log | Optional | response dari `security_requirement_inference_node` |

### 9.5 Output Schema (Generated Workflow)

Setiap generated YAML harus include header comments untuk **explainability**:

```yaml
# Domain: e-commerce (confidence: 0.85)
# Architecture: monolithic
# Priority threats: SQL injection in /checkout, /orders; XSS in /products/:id/review; Broken auth
# Generated by: ai-devsecops-ai-service v1.0
# Security scan jobs use --ignore-scripts to avoid native module build failures
# All actions pinned to SHA with using: node24
```

Comment ini membantu reviewer cepat paham keputusan generator tanpa harus trace code.

### 9.6 Validasi Matrix

Tabel cek apakah generated workflow sudah benar:

| Cek | Pass criteria |
|---|---|
| `actions/checkout@<SHA>` | SHA starts with action yang `using: node24` |
| `node-version` | `'24'` (bukan `'20'`) |
| `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` | TIDAK ADA di env block |
| `dependency-scan` install | `npm ci --no-audit --no-fund --ignore-scripts` |
| `lint/test/build` install | `npm ci --no-audit --no-fund` (no ignore-scripts, butuh modules) |
| `iac-scan` job | HANYA jika ada `*.tf` / `Chart.yaml` / `k8s/` di repo |
| `cve_scan` di Security Controls | Listed sebagai merged into `dependency-scan` di Debug panel |
| `sast` tool di panel | `semgrep` (bukan `eslint`) |
| Comment header | Includes domain + architecture + priority threats |

Kalau semua pass → workflow benar dari awal, tidak perlu re-run untuk validasi.
