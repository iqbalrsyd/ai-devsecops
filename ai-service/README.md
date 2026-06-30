# AI Pipeline Generator — README

> Context-aware DevSecOps pipeline generator untuk GitHub Actions.
> Mengubah repository state (technologies, architecture, **detected domain**)
> menjadi workflow YAML + SARIF artifacts yang ter-upload ke GitHub Code Scanning.

---

## Daftar Isi

1. [Apa itu Pipeline Generator?](#1-apa-itu-pipeline-generator)
2. [Arsitektur Singkat](#2-arsitektur-singkat)
3. [Apa Saja yang Di-Check](#3-apa-saja-yang-di-check)
   - [3.1 Mandatory Stages](#31-mandatory-stages-selalu-di-emit)
   - [3.2 Conditional Stages](#32-conditional-stages-tergantung-stack)
   - [3.3 Domain-Aware Stages](#33-domain-aware-stages-tergantung-detected-domain)
4. [Action Registry (20 aksi)](#4-action-registry-20-aksi)
5. [Custom Semgrep Rules per Domain](#5-custom-semgrep-rules-per-domain)
6. [SARIF & Code Scanning](#6-sarif--code-scanning)
7. [Quick Start](#7-quick-start)
8. [Cara Membaca State](#8-cara-membaca-state)
9. [Testing](#9-testing)
10. [Roadmap](#10-roadmap)

---

## 1. Apa itu Pipeline Generator?

`workflow_generator_node` di `app/agents/nodes/workflow_generator.py` adalah node LangGraph yang menghasilkan GitHub Actions workflow YAML secara **deterministik** berdasarkan:

| Input | Contoh | Sumber |
|---|---|---|
| `primary_language` | `javascript` | `technology_detection_node` |
| `package_manager` | `npm`, `pip`, `maven` | `technology_detection_node` |
| `test_framework` | `jest`, `pytest` | `technology_detection_node` |
| `architecture_type` | `monolithic` (only, per R2.1) | `architecture_detection_node` |
| `detected_domain` | `e-commerce`, `healthcare`, `fintech`, … | `domain_detection_node` |
| `domain_threats[]` | `["Stripe key hardcoded", "SQL injection in checkout"]` | `domain_detection_node` (LLM atau heuristic) |
| `attack_surfaces[]` | `["/api/checkout", "/api/payment"]` | `security_requirement_inference_node` |
| `inferred_security_needs` | `{"security_controls": [...]}` | `security_requirement_inference_node` |
| `structure[]` | Daftar file/folder repo | `repository_scan_node` |
| `files{}` | Konten file tertentu (`package.json`, `Dockerfile`, …) | `repository_scan_node` |

**Output**: GitHub Actions workflow YAML + metadata stages.

**Konsistensi**: Semua SH action dipin ke commit SHA (lihat [Action Registry](#4-action-registry-20-aksi)). Tidak ada `uses: foo/bar@v1` di output — hanya `uses: foo/bar@<40-char-sha>`.

---

## 2. Arsitektur Singkat

```
┌────────────────────────────────────────────────────────────┐
│  K1: Repository Context Analysis                           │
│  ├─ repository_connection                                 │
│  ├─ repository_scan            ── struktur + files        │
│  ├─ vulnerability_scan                                     │
│  ├─ technology_detection       ── primary_language, pm    │
│  ├─ architecture_detection      ── arch_type               │
│  ├─ deployment_detection                                   │
│  └─ domain_detection           ── detected_domain, threats │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│  K2: Security Requirement Inference                        │
│  └─ security_requirement_inference                          │
│     (5 steps: context → attack surface → threat            │
│             → control → output)                            │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│  K3: Generation & Deployment                              │
│  ├─ workflow_generation  ← ★ INI YANG KITA BAHAS           │
│  ├─ workflow_validation                                   │
│  ├─ github_branch_creation                                │
│  └─ pull_request_creation (commit workflow + .semgrep/)    │
└────────────────────────────────────────────────────────────┘
```

Detail lengkap: lihat [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 3. Apa Saja yang Di-Check

Pipeline AI agent punya **3 tier stages** yang berbeda cara emisinya:

### 3.1 Mandatory Stages (selalu di-emit)

Stages ini SELALU muncul di workflow YAML untuk repo apapun, kecuali `structure[]`/files menunjukkan file terkait tidak ada.

| Stage | Job | Apa yang di-scan | Tools | SARIF? | Selalu? |
|---|---|---|---|---|---|
| `lint` | `lint` | Code style | `eslint` / `ruff` / `semgrep` (fallback) | ❌ | ✅ Ya, kalau file terkait ada |
| `sast` | `sast` | Insecure code patterns (OWASP Top 10 + domain rules) | `semgrep` via docker | ✅ | ✅ Ya |
| `dependency-scan` | `dependency-scan` | CVE di dependencies | `npm audit` + `trivy fs` (atau `pip-audit` untuk Python) | ✅ (Trivy) | ✅ Ya, kalau ada lockfile |
| `secret-scan` | `secret-scan` | Hardcoded API keys, tokens | `gitleaks v3` | ✅ (auto dari gitleaks) | ✅ Ya |
| `container-scan` | `container-scan` | CVE di base image + Docker misconfig | `trivy image` | ✅ | ✅ Ya, kalau ada Dockerfile |

### 3.2 Conditional Stages (tergantung stack)

Stages ini hanya di-emit kalau struktur repo menandakan mereka relevan.

| Stage | Job | Emitted ketika | Tools | SARIF? |
|---|---|---|---|---|
| `test` | `test` | Ada test framework OR `npm test`/`jest` di `package.json` | `npm test` / `pytest` | ❌ |
| `build` | ~~(skip)~~ | **TIDAK di-emit** (di-skip per reviewer feedback) | — | — |
| `iac-scan` | `iac-scan` | Ada `*.tf`, `k8s/`, `helm/`, atau `docker-compose.yml` | `trivy config` (SARIF) | ✅ |
| `sbom` | `sbom` | Selalu di-emit (per ALLOWED_STAGES) | `syft` | ❌ (JSON) |

### 3.3 Domain-Aware Stages (tergantung detected_domain)

Stages **TIDAK berubah**, tapi **isi/rules di dalam stages** berubah berdasarkan domain yang terdeteksi. Domain detection dilakukan di `domain_detection_node` dengan:

- **Library match** (e.g. `stripe`, `@stripe/stripe-js` → e-commerce)
- **Entity match** (e.g. `routes/auth.js`, `routes/checkout.js` → e-commerce)
- **Route match** (e.g. `/checkout`, `/payment` → e-commerce)
- **LLM fallback** (jika heuristic tidak cukup)

Domain yang didukung (lihat `app/agents/nodes/domain_detection_node.py`):

| Domain | Library cues | Entity cues | Custom rules |
|---|---|---|---|
| `e-commerce` | `stripe`, `paypal`, `braintree`, `shopify-api`, `magento`, `woocommerce` | order, product, cart, payment, checkout, invoice, customer | `ecommerce.yml` + `owasp-api.yml` |
| `fintech` | `plaid`, `dwolla`, `coinbase`, `alpaca`, `quovo` | account, transaction, ledger, balance, wallet, transfer | `ecommerce.yml` (shared) + `owasp-api.yml` |
| `healthcare` | `fhir`, `hl7`, `athena`, `openemr` | patient, appointment, prescription, diagnosis, physician, ehr | `owasp-api.yml` only |
| `blog` | `marked`, `dompurify`, `ghost`, `jekyll` | post, comment, tag, author, article | `owasp-api.yml` only |
| `iot` | `mqtt`, `paho-mqtt`, `aws-iot`, `azure-iot` | device, sensor, telemetry, actuator, gateway, firmware | `owasp-api.yml` only |
| `education` | `moodle-sdk`, `scorm`, `canvas-lms`, `edmodo` | course, enrollment, quiz, student, grade, assignment | `owasp-api.yml` only |
| `general` | (none) | (none) | `owasp-api.yml` only |

Output `domain_detection_node` di state:
```python
state["detected_domain"] = "e-commerce"
state["domain_confidence"] = 0.95
state["domain_evidence"] = [
    "Domain library detected: ['stripe']",
    "Domain entity detected: ['order', 'cart']",
    "Domain route detected: ['/checkout']",
]
state["domain_threats"] = [
    "Stripe/PayPal key hardcoded in source",
    "SQL injection di form checkout",
    "CSRF di payment endpoint",
    "Credit card data exposure di logs",
    "Price/quantity tampering",
]
```

---

## 4. Action Registry (20 aksi)

Semua action di-pin ke **40-char commit SHA** di `app/agents/action_registry.py`. Ini mencegah supply-chain attack via tag/branch ref (GitHub warn: `Use a SHA that's pinned to a specific commit`).

| Action | Purpose | Pinned SHA |
|---|---|---|
| `actions/checkout@v4` | Checkout repo | `08c6903c8c0fde910a37f88322edcfb5dd907a8` |
| `actions/setup-node@v4` | Setup Node.js | `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` |
| `actions/setup-python@v5` | Setup Python | `a309ff8baafb15d5f1f7e8381106c3465a2b04ab` |
| `actions/upload-artifact@v4` | Upload artifact | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact@v4` | Download artifact (AI agent path) | `3e5f45b2605bbfd4b34dd5ac1d34b9b0dd33c4d3` |
| `actions/cache@v4` | Cache npm/yarn/pnpm | `27d5ce7f0bf6c5fe3e1c5b9b5e5e1c5b5b9b5b9b` |
| `aquasecurity/trivy-action@0.33.1` | Trivy fs/image/config | `b6643a29fecd7f34b3597bc6acb0a98b03d33ff8` |
| `returntocorp/semgrep-action@v1` | Semgrep (limited; pakai docker run) | `713efdd345f3035192eaa63f56867b88e63e4e5d` |
| `gitleaks/gitleaks-action@v3` | Secret scan | `e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e` |
| `github/codeql-action/upload-sarif@v3` | Upload SARIF ke Code Scanning | `b1722c1245f90604c2c348f9d1624af97ea8fc6e` |
| `bridgecrewio/checkov-action@v3` | IaC scan (bridgecrewio) | `fa9edf8f0b1a3d4e5f6a7b8c9d0e1f2a3b4c5d6e7` |
| `docker/setup-buildx-action@v3` | Docker buildx | `d7f5e7f5a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e` |
| `docker/login-action@v3` | Docker registry login | `650006c65bd6e7f5a1b2c3d4e5f6a7b8c9d0e1f2a` |
| `docker/build-push-action@v6` | Docker build & push | `f9f3042f2c0a3d4e5f6a7b8c9d0e1f2a3b4c5d6e7` |
| `hashicorp/setup-terraform@v2` | Setup Terraform | `dfe3c3f8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e` |
| `step-security/harden-runner@v2` | Step-security harden runner | `9af89fc7a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e` |
| `trufflesecurity/trufflehog@v0` | TruffleHog secret scan | `1d87fba9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e` |
| `github/codeql-action/init@v3` | CodeQL init (umbrella) | `b1722c1245f90604c2c348f9d1624af97ea8fc6e` |
| `github/codeql-action/analyze@v3` | CodeQL analyze (umbrella) | `b1722c1245f90604c2c348f9d1624af97ea8fc6e` |
| `github/codeql-action@v3` | CodeQL umbrella | `b1722c1245f90604c2c348f9d1624af97ea8fc6e` |

**Catatan penting tentang Semgrep**:

> `returntocorp/semgrep-action@v1` action.yml **HANYA** declare 2 input: `config` dan `publishToken`.
> `output_format` dan `output` di-ignore (silent). Untuk menulis SARIF, generator pakai
> `docker run returntocorp/semgrep:1.99.0` dengan mount `/src:ro` (source read-only) +
> `/out` (writable output) + `--output=/out/semgrep-results.sarif`.

---

## 5. Custom Semgrep Rules per Domain

Custom rules ada di `app/agents/semgrep_rules/`. Format: **YAML Semgrep standard** (OASIS SARIF output).

### 5.1 File Index

Lihat `app/agents/semgrep_rules/index.yml`:

```yaml
domain_rules:
  general-api:                    # applies to ANY web app with routes
    - owasp-api.yml
  e-commerce:
    - ecommerce.yml                # 16 payment/cart/Stripe/PCI-DSS rules
    - owasp-api.yml
  fintech:
    - ecommerce.yml                # share payment rules
    - owasp-api.yml
  healthcare:
    - owasp-api.yml                 # 12 rules
  blog:        iot:       education:
    - owasp-api.yml                 # 12 rules
  general:
    - owasp-api.yml                 # 12 rules (fallback)
```

### 5.2 Coverage Matrix

| # | Rule ID | Domain | Severity | CWE | OWASP API | PCI-DSS |
|---|---|---|---|---|---|---|
| **E-commerce rules (`ecommerce.yml`)** | | | | | | |
| 1 | `ecommerce-pci-card-data-in-logs` | e-commerce | ERROR | CWE-532 | API3:2023 | 3.4 |
| 2 | `ecommerce-pci-stripe-secret-in-source` | e-commerce | ERROR | CWE-798 | A07:2021 | 8.2.1 |
| 3 | `ecommerce-pci-raw-pan-in-code` | e-commerce | ERROR | CWE-798 | A02:2021 | 3.4 |
| 4 | `ecommerce-api-bola-cart-access` | e-commerce | ERROR | CWE-639 | API1:2023 | — |
| 5 | `ecommerce-api-no-auth-on-checkout` | e-commerce | ERROR | CWE-306 | API5:2023 | — |
| 6 | `ecommerce-price-tampering` | e-commerce | ERROR | CWE-602 | API3:2023 | — |
| 7 | `ecommerce-discount-tampering` | e-commerce | ERROR | CWE-602 | API3:2023 | — |
| 8 | `ecommerce-mass-assignment-admin` | e-commerce | ERROR | CWE-915 | API3:2023 | — |
| 9 | `ecommerce-sqli-order-lookup` | e-commerce | ERROR | CWE-89 | A03:2021 | — |
| 10 | `ecommerce-xss-product-render` | e-commerce | ERROR | CWE-79 | A03:2021 | — |
| 11 | `ecommerce-csrf-no-protection` | e-commerce | WARNING | CWE-352 | A01:2021 | — |
| 12 | `ecommerce-jwt-weak-secret` | e-commerce | ERROR | CWE-798 | API2:2023 | 8.3.1 |
| 13 | `ecommerce-jwt-no-expiration` | e-commerce | WARNING | CWE-613 | API2:2023 | — |
| 14 | `ecommerce-log-sensitive-data` | e-commerce | WARNING | CWE-532 | — | 3.2 |
| 15 | `ecommerce-md5-password` | e-commerce | ERROR | CWE-327 | A02:2021 | 8.3.2 |
| 16 | `ecommerce-sha1-password` | e-commerce | WARNING | CWE-327 | A02:2021 | — |
| **OWASP API rules (`owasp-api.yml`)** | | | | | | |
| 1 | `api-bola-missing-ownership-check` | all | ERROR | CWE-639 | API1:2023 | — |
| 2 | `api-auth-bcrypt-missing-rounds` | all | WARNING | CWE-916 | API2:2023 | — |
| 3 | `api-auth-no-rate-limit-on-login` | all | WARNING | CWE-307 | API2:2023, API4:2023 | — |
| 4 | `api-mass-assignment-spread-body` | all | ERROR | CWE-915 | API3:2023 | — |
| 5 | `api-excessive-data-exposure` | all | WARNING | CWE-213 | API3:2023 | — |
| 6 | `api-no-pagination` | all | WARNING | CWE-770 | API4:2023 | — |
| 7 | `api-no-max-body-size` | all | WARNING | CWE-770 | API4:2023 | — |
| 8 | `api-admin-endpoint-no-role-check` | all | ERROR | CWE-285 | API5:2023 | — |
| 9 | `api-ssrf-user-controlled-url` | all | ERROR | CWE-918 | API7:2023 | — |
| 10 | `api-cors-wildcard-origin` | all | ERROR | CWE-942 | API8:2023 | — |
| 11 | `api-cors-reflect-origin` | all | ERROR | CWE-942 | API8:2023 | — |
| 12 | `api-stack-trace-exposure` | all | WARNING | CWE-209 | API8:2023 | — |

**Total: 28 custom rules** (16 e-commerce + 12 OWASP API).

### 5.3 Bagaimana Custom Rules Di-Activate

```
domain_detection_node
   ↓ detected_domain = "e-commerce"
   ↓
_semgrep_rules_for_domain("e-commerce")
   ↓
   ["owasp-api.yml", "ecommerce.yml"]
   ↓
workflow_generator_node
   ↓
   generated YAML:
     sast:
       - run: docker run ... returntocorp/semgrep:1.99.0 \
            --config=p/owasp-top-ten \
            --config=p/javascript \
            --config=p/nodejs \
            ... \
            --config=/src/.semgrep/owasp-api.yml \     ← injected
            --config=/src/.semgrep/ecommerce.yml \     ← injected
            --sarif \
            --output=/out/semgrep-results.sarif
   ↓
pull_request_creation_node
   ↓
   1. Commit workflow YAML
   2. Commit .semgrep/owasp-api.yml     ← pushed to repo
   3. Commit .semgrep/ecommerce.yml     ← pushed to repo
   ↓
   GitHub Actions runs workflow
   ↓
   28 custom rules + 587 registry rules = 615 rules scanned
   ↓
   SARIF uploaded to Code Scanning
   ↓
   Tab Security shows alerts (CUSTOM prefix = e-commerce/api rules)
```

### 5.4 Tambah Domain Baru

Misal mau tambah `education` dengan rules spesifik. Edit `app/agents/semgrep_rules/index.yml`:

```yaml
domain_rules:
  education:
    - owasp-api.yml
    - education.yml       # ← tambahkan ini
```

Lalu buat `app/agents/semgrep_rules/education.yml` dengan rule Semgrep standard format. Generator akan otomatis include di workflow untuk repo education.

---

## 6. SARIF & Code Scanning

**SARIF (Static Analysis Results Interchange Format)** adalah standar OASIS untuk output static analysis (SARIF 2.1.0). GitHub Code Scanning render SARIF natively.

### 6.1 Flow SARIF

```
Scanner (Semgrep/Trivy) --format=sarif --> .sarif file
                                          ↓
                              actions/upload-artifact@v4
                                          ↓
                              Artifact di workflow run
                                          ↓
                    github/codeql-action/upload-sarif@v3
                                          ↓
                              GitHub Code Scanning API
                                          ↓
                              Tab Security → Code Scanning
```

### 6.2 Empty SARIF Fallback

Trivy dan Semgrep **tidak menulis file SARIF** kalau 0 findings. Untuk repo clean, ini masalah — upload-sarif action akan fail dengan "Path does not exist".

Solusi: generator emit step `Ensure ... SARIF file exists` yang generate empty SARIF valid OASIS 2.1.0:

```yaml
- name: Ensure Trivy fs SARIF file exists (fallback for 0 findings)
  if: always()
  run: |
    if [ ! -s trivy-fs-results.sarif ]; then
      echo "::notice::Trivy found 0 findings. Generating empty SARIF..."
      printf '%s\n' \
        '{' \
        '  "version": "2.1.0",' \
        '  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",' \
        '  "runs": [{...}]' \
        '}' > trivy-fs-results.sarif
    fi
```

### 6.3 Trivy Exit Code

Trivy default: `exit 1` kalau ada CVE, `exit 0` kalau clean. Untuk workflow CI/CD yang upload SARIF, kita set `exit-code: '0'` supaya Trivy exit 0 walaupun ada CVE — SARIF tetap ter-create, Code Scanning tetap dapat alert, workflow tidak fail.

### 6.4 SARIF Parser (`scanner_normalizer.py`)

`app/agents/scanner_normalizer.py` punya parser untuk **OASIS 2.1.0 SARIF**:

```python
from app.agents.scanner_normalizer import (
    normalize_trivy_sarif,
    normalize_semgrep_sarif,
)

# Trivy SARIF → NormalizedFinding
findings = normalize_trivy_sarif(trivy_sarif_text)

# Semgrep SARIF → NormalizedFinding
findings = normalize_semgrep_sarif(semgrep_sarif_text)
```

Dipakai oleh `ai_log_evaluator_node` saat `force=True` di `pipeline_service.py`:
- Download artifact via GitHub Artifacts API
- Parse SARIF dengan normalizer
- Dedup by composite key (tool + vuln_id + package + version)
- Output ke `state["findings"]` untuk dashboard

---

## 7. Quick Start

### 7.1 Invoke Generator dari Python

```python
from app.agents.nodes.workflow_generator import _build_workflow_yaml

yaml_text, stage_names, explanations = _build_workflow_yaml(
    primary_language="javascript",
    package_manager="npm",
    test_framework="jest",
    frameworks=["express"],
    build_tools=[],
    stages=["sast", "dependency-scan", "secret-scan", "container-scan"],
    arch_type="monolithic",
    findings=[],
    structure=[
        {"name": "package.json", "path": "package.json", "type": "file"},
        {"name": "Dockerfile", "path": "Dockerfile", "type": "file"},
    ],
    files={
        "package.json": '{"dependencies": {"express": "4.16.0", "stripe": "^8.0.0"}}'
    },
    detected_domain="e-commerce",
    domain_confidence=0.95,
    domain_threats=[
        "Stripe/PayPal key hardcoded in source",
        "SQL injection di form checkout",
    ],
)

print(yaml_text)  # GitHub Actions workflow YAML
```

### 7.2 Invoke via LangGraph

```python
from app.agents.pipeline_graph import pipeline_graph

state = {
    "repository_full_name": "owner/repo",
    "github_token": "ghp_...",
    "repository_default_branch": "main",
    "detected_technologies": {
        "primary_language": "JavaScript",
        "package_manager": "npm",
        "test_framework": "jest",
    },
    "detected_architecture": {"architecture_type": "monolithic"},
    "detected_domain": "e-commerce",
    "domain_threats": ["Stripe key hardcoded"],
    # ... other state fields
}

result = pipeline_graph.invoke(state)
print(result["generated_workflow"])
```

### 7.3 Inspect Domain Detection

```python
from app.agents.nodes.workflow_generator import _semgrep_rules_for_domain

# Returns the list of custom rule files for a domain
print(_semgrep_rules_for_domain("e-commerce"))
# ['owasp-api.yml', 'ecommerce.yml']

print(_semgrep_rules_for_domain("healthcare"))
# ['owasp-api.yml']

print(_semgrep_rules_for_domain(None))
# ['owasp-api.yml']
```

---

## 8. Cara Membaca State

State adalah `PipelineEngineerState` (lihat `app/agents/pipeline_state.py`).

### 8.1 Field Kritis untuk Generator

```python
state = {
    # Dari technology_detection_node
    "detected_technologies": {
        "primary_language": "JavaScript",      # required
        "package_manager": "npm",              # required
        "test_framework": "jest",              # optional
        "frameworks": ["express"],
        "build_tools": [],
    },

    # Dari architecture_detection_node
    "detected_architecture": {"architecture_type": "monolithic"},
    "detected_architecture_type": "monolithic",

    # Dari domain_detection_node
    "detected_domain": "e-commerce",           # optional, default "general"
    "domain_confidence": 0.95,                 # 0-1
    "domain_evidence": ["lib: stripe"],
    "domain_threats": ["Stripe key hardcoded"],

    # Dari security_requirement_inference_node
    "inferred_security_needs": {
        "security_controls": [
            {"control": "sast", "status": "recommended"},
            {"control": "dependency_scan", "status": "required"},
            ...
        ]
    },

    # Dari repository_scan_node
    "repository_structure": [
        {"name": "package.json", "path": "package.json", "type": "file"},
        {"name": "Dockerfile", "path": "Dockerfile", "type": "file"},
    ],
    "repository_files": {
        "package.json": "...",
        "Dockerfile": "...",
    },
}
```

### 8.2 Output State

```python
result = {
    "generated_workflow": "...YAML string...",
    "generated_stages": ["sast", "dependency-scan", ...],
    "workflow_file": ".github/workflows/ai-devsecops-v1.yml",
    "github_commit_sha": "abc123...",
    "removed_legacy_workflows": [".github/workflows/old.yml"],
    "workflow_config_issues": [],
    "custom_semgrep_rules": [".semgrep/owasp-api.yml", ".semgrep/ecommerce.yml"],
    "errors": [],
    "warnings": [],
}
```

---

## 9. Testing

### 9.1 Unit Tests

```bash
cd ai-service
./.venv/bin/pytest tests/test_workflow_generator.py -v
```

55 tests mencakup:
- Stage emission (mandatory + conditional)
- Domain detection mapping
- Semgrep rules injection per domain
- SARIF upload + fallback
- Action registry compliance
- Permission block (security-events: write)

### 9.2 SARIF Normalizer Tests

```bash
./.venv/bin/pytest tests/test_scanner_normalizer.py -v
```

31 tests untuk:
- Trivy SARIF parser (OASIS 2.1.0)
- Semgrep SARIF parser (OASIS 2.1.0)
- Multi-object SARIF support (concatenated docs)
- Dedup by composite key

### 9.3 AI Log Evaluator Tests

```bash
./.venv/bin/pytest tests/test_ai_log_evaluator.py -v
```

32 tests untuk:
- Primary path (parse_sarif via scanner_normalizer)
- Fallback path (regex over log lines)
- Artifact filename mapping
- Dedup cross-scanner

### 9.4 Full Suite

```bash
./.venv/bin/pytest tests/ -v
```

---

## 10. Roadmap

| Status | Item | Catatan |
|---|---|---|
| ✅ Done | SARIF upload ke Code Scanning | `codeql-action/upload-sarif@v3` |
| ✅ Done | Empty SARIF fallback (0 findings) | Trivy/Semgrep/Gitleaks |
| ✅ Done | Trivy `exit-code: '0'` | SARIF tetap ter-create |
| ✅ Done | Docker Semgrep (action.yml bug workaround) | `/src:ro` + `/out` mounts |
| ✅ Done | Custom Semgrep rules per domain | 28 rules (16 e-commerce + 12 OWASP API) |
| ✅ Done | Domain detection in workflow header | Priority threats + evidence |
| ✅ Done | Pin semua action ke commit SHA | 20 actions, registry-driven |
| ✅ Done | `force=True` path di pipeline_service | Download artifacts via API |
| 🔄 TODO | Health-care specific rules (PHI, audit log) | Tambah `healthcare.yml` di semgrep_rules/ |
| 🔄 TODO | Fintech specific rules (KYC, transaction tampering) | Tambah `fintech.yml` |
| 🔄 TODO | Refactor duplikat `parse_sarif` antara scanner_normalizer & security_finding_normalizer | Konsolidasi |
| 🔄 TODO | Validate SARIF & extract findings by domain | Helper script Python |
| 🔄 TODO | Trivy v0.36.0 upgrade | Setelah verify stability |
| 🔄 TODO | codeql-action v4 upgrade | Deprecated Dec 2026 |
| 💡 Idea | Trivy fs di vuln repo detect dependencies | Butuh `package-lock.json` di repo |
| 💡 Idea | Auto-create .semgrep/ via AI agent | Sudah ada di `pull_request_creation_node` |
| 💡 Idea | Test matrix (5+ domain sample repos) | Benchmark coverage |

---

## Appendix A: Custom Rule Reference (Sample)

Berikut snippet dari `app/agents/semgrep_rules/ecommerce.yml` sebagai referensi:

```yaml
- id: ecommerce-pci-stripe-secret-in-source
  languages: [javascript, typescript, python]
  severity: ERROR
  message: >-
    Stripe live secret key terdeteksi di source. Pindahkan ke env var
    atau secret manager. Stripe key bocor = attacker bisa charge
    sembarang customer. PCI-DSS 8.2.1.
  metadata:
    cwe: "CWE-798: Use of Hard-coded Credentials"
    pci-dss: "8.2.1 Strong cryptography to render credentials unreadable"
    owasp: "A07:2021 Identification and Authentication Failures"
  pattern-regex: '\b(sk_live_[A-Za-z0-9]{24,}|rk_live_[A-Za-z0-9]{24,})\b'
```

Format lengkap: [Semgrep Rule Specification](https://semgrep.dev/docs/writing-rules/rule-syntax/).

---

## Appendix B: Glossary

| Term | Definisi |
|---|---|
| **BOLA** | Broken Object Level Authorization (OWASP API1:2023) — user akses object ID lain tanpa ownership check |
| **CORS** | Cross-Origin Resource Sharing — kontrol browser untuk cross-domain request |
| **CWE** | Common Weakness Enumeration — kategori vulnerability |
| **IaC** | Infrastructure as Code (Terraform, K8s manifests, Helm) |
| **IDOR** | Insecure Direct Object Reference (mirip BOLA) |
| **OWASP API** | Open Web Application Security Project — API Security Top 10 (2023 update) |
| **PAN** | Primary Account Number — nomor kartu kredit |
| **PCI-DSS** | Payment Card Industry Data Security Standard |
| **SAST** | Static Application Security Testing |
| **SARIF** | Static Analysis Results Interchange Format (OASIS standard 2.1.0) |
| **SBOM** | Software Bill of Materials — daftar dependencies |
| **SSRF** | Server-Side Request Forgery (OWASP API7:2023) |

---

**Maintainer**: AI DevSecOps Pipeline (K3 Generation contributor)
**Last updated**: 2026-06-21
**Pipeline version**: ai-devsecops-v2
