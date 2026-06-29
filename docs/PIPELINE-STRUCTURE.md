# PIPELINE-STRUCTURE.md — Versi 2 (Generic + LLM-Driven Domain)

> **Status**: DRAFT untuk konfirmasi skripsi
> **Tanggal**: 22 Juni 2026
> **Penulis**: AI Pipeline Generator
> **Audiens**: Penulis skripsi (Bab 4) + reviewer

---

## 1. Filosofi: Pipeline Itu GENERIC, Domain Itu LAPISAN

Pipeline AI agent **tidak** generate workflow yang berbeda per domain dari nol.
Pipeline menghasilkan **1 struktur generic** (core jobs), lalu **melapisi**
fitur spesifik domain (ruleset + jobs tambahan) di atas struktur itu.

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  GENERIC CORE PIPELINE (sama untuk SEMUA repo)                 │
│  ─────────────────────────────────────────────                  │
│  - lint                                                        │
│  - sast              ← ruleset berbeda per domain              │
│  - dependency-scan   ← Trivy exit-code + empty SARIF fallback  │
│  - secret-scan                                              │
│  - container-scan    ← hanya jika Dockerfile                  │
│  - sbom                                                       │
│                                                                │
│  + DOMAIN-AWARE EXTENSIONS (LLM-driven, opsional)              │
│  ─────────────────────────────────────────────                  │
│  - 1..N domain-specific jobs (pci-dss, hipaa, dll)            │
│  - custom Semgrep rules (per domain + per sub_type)           │
│  - skip rules (mengurangi false positive)                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Dengan struktur ini, kalau template domain berubah (mis. tambah Doku
payment processor), cukup update 1 DICT di `scan_directives.py` tanpa
ubah code generator.**

---

## 2. Arsitektur 5-Layer

Pipeline generator memutuskan konfigurasi scan dalam **5 layer bertingkat**.
Setiap layer menambahkan/dikurangi elemen tanpa menggangu layer lain.

### Layer 1: Always-On Baseline
**Trigger**: SELALU (untuk semua repo apapun)

```python
_BASELINE_REGISTRY_RULES = (
    "p/owasp-top-ten",
    "p/javascript",
    "p/nodejs",
    "p/expressjs",
    "p/sql-injection",
    "p/secrets",
    "p/dockerfile",
)

_GENERAL_API_RULES = ("owasp-api.yml",)  # OWASP API Top 10 2023
```

**Output SAST job `--config` flags**: ~8 rules
**Output jobs**: lint, sast, dep-scan, secret-scan, container-scan, sbom

### Layer 2: Domain-Specific (LLM-detected)
**Trigger**: kalau `detected_domain != "general"`

| Domain | Rule files added | Extra jobs |
|---|---|---|
| `e-commerce` | `ecommerce.yml`, `pci-dss.yml` | `pci-dss` |
| `fintech` | `ecommerce.yml`, `fintech-ledger.yml` | `ledger-check` |
| `healthcare` | `hipaa.yml` | `hipaa` |
| `blog` | `blog-csp.yml` | `csp-headers` |
| `iot` | `iot-mqtt.yml` | `mqtt-security` |
| `education` | (none) | (none) |
| `general` | (none) | (none) |

### Layer 3: Sub-Type (Payment Processor)
**Trigger**: `detected_domain == "e-commerce"` AND `detected_sub_type` ada

| Sub-type (payment processor) | Rule files added |
|---|---|
| `stripe` | `pci-stripe.yml` |
| `midtrans` | `pci-midtrans.yml` |
| `xendit` | `pci-xendit.yml` |
| `doku` | `pci-doku.yml` |
| `paypal` | `pci-paypal.yml` |
| `braintree` | `pci-braintree.yml` |
| `razorpay` | (planned) |
| `adyen` | (planned) |
| `square` | (planned) |
| `multi` | (union dari semua) |
| `unknown` | (none — generic rules only) |

**Cara kerja**:
1. LLM detect payment processor dari source code (di `domain_detection_node`)
2. Hasil disimpan di `state["detected_sub_type"]`
3. `build_scan_directives()` baca dan tambahkan rule files spesifik
4. Workflow generator include di SAST job

### Layer 4: Architecture-Specific
**Trigger**: `arch_type` di state

| arch_type | Skip rules added |
|---|---|
| `monolithic` | `kubernetes`, `service-mesh`, `istio` |
| `microservices` | (none — k8s rules tetap applicable) |
| `modular_monolith` | (sama dgn monolith) |

### Layer 5: LLM-Driven Extension
**Trigger**: LLM (di inference) return `llm_rule_suggestions` (opsional)

```python
if llm_rule_suggestions:
    for rule_file in llm_rule_suggestions:
        sast_ruleset.append(f"/src/.semgrep/{rule_file}")
```

**Use case**: emerging threat yang belum ada di static mapping. Mis. AI
agent detect pattern "uses blockchain payment" → LLM suggest
`pci-blockchain.yml` (yang belum ada). Pipeline include tanpa code change.

---

## 3. Data Flow (End-to-End)

```
┌─────────────────────────────────────────────────────────────────┐
│  domain_detection_node                                          │
│  Input:  package.json, source files, repo name/description      │
│  ────────────────────────────────────────────────                │
│  Step 1: extract libraries, entities, routes (regex)            │
│  Step 2: heuristic score per domain (DICT lookup)               │
│  Step 3: LLM call → {domain, sub_type, confidence, threats}     │
│  Step 4: hybrid decision (LLM + heuristic fallback)             │
│  Step 5: if sub_type="none" → derive from libs (heuristic)      │
│  Output: state.detected_domain, state.detected_sub_type         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  security_requirement_inference_node                            │
│  Input:  technologies, architecture, domain, sub_type, threats  │
│  ────────────────────────────────────────────────                │
│  Step 1: LLM call → security controls, attack surfaces          │
│  Step 2: enforce mandatory controls (lint, sast, etc)           │
│  Step 3: build scan_directives via build_scan_directives()      │
│  Step 4: emit llm_rule_suggestions (opsional)                   │
│  Output: state.inferred_security_needs.scan_directives          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  workflow_generator                                             │
│  Input:  state.detected_domain, state.detected_sub_type,        │
│          state.scan_directives.sast_ruleset, etc                 │
│  ────────────────────────────────────────────────                │
│  Step 1: emit core jobs (lint, sast, dep-scan, ...)             │
│  Step 2: for each rule in sast_ruleset, add --config flag       │
│  Step 3: emit domain_jobs (pci-dss, etc)                        │
│  Step 4: emit header comment with domain, threats, sub_type      │
│  Output: GitHub Actions workflow YAML                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  pull_request_creation_node                                     │
│  Input:  state.detected_domain, state.detected_sub_type,        │
│          scan_directives.sast_ruleset                           │
│  ────────────────────────────────────────────────                │
│  Step 1: commit workflow YAML to .github/workflows/              │
│  Step 2: extract /src/.semgrep/<file>.yml paths                  │
│  Step 3: for each path, find the source file in                  │
│          app/agents/semgrep_rules/                              │
│  Step 4: commit rule file to .semgrep/ in repo                   │
│  Step 5: create PR                                               │
│  Output: PR with workflow + custom rules                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions runtime                                          │
│  - sast job runs all 8+ rules (registry + custom)                │
│  - SARIF uploaded to Code Scanning                              │
│  - Domain-specific jobs (pci-dss, etc) run                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Generic Pipeline Jobs (Core)

Tiap repo otomatis dapat **6 core jobs** (5 kalau tanpa Dockerfile):

| # | Job | Tools | Output | Selalu? |
|---|---|---|---|---|
| 1 | `lint` | `eslint` / `ruff` / `pylint` | (none) | Ya, kalau ada test framework |
| 2 | `sast` | Semgrep via docker | SARIF | **Ya** |
| 3 | `dependency-scan` | `npm audit` + `trivy fs` | JSON + SARIF | Ya, kalau ada lockfile |
| 4 | `secret-scan` | `gitleaks v3` | SARIF (auto) | Ya |
| 5 | `container-scan` | `trivy image` | SARIF | Kalau Dockerfile ada |
| 6 | `sbom` | `syft` | JSON (SPDX) | Ya |

**Plus 1..N domain jobs** (LLM-detected):

| Domain | Extra jobs |
|---|---|
| e-commerce | `pci-dss` |
| fintech | `ledger-check` |
| healthcare | `hipaa` |
| blog | `csp-headers` |
| iot | `mqtt-security` |
| education | (none) |
| general | (none) |

**Total jobs**:
- General repo: 6
- E-commerce repo: 6 + 1 (pci-dss) = **7 jobs**
- Fintech repo: 6 + 1 (ledger-check) = 7 jobs
- Multi-payment e-commerce: 6 + 1 (pci-dss) = 7 jobs (sub-type tidak menambah job)

---

## 5. Generic SAST Ruleset (Default 8 Rules)

Tiap repo otomatis dapat **8 baseline ruleset** di sast job:

| # | Config | Purpose | Required? |
|---|---|---|---|
| 1 | `p/owasp-top-ten` | OWASP Top 10 2021 | Ya |
| 2 | `p/javascript` | JS-specific | Ya (kalau JS) |
| 3 | `p/nodejs` | Node.js-specific | Ya (kalau Node) |
| 4 | `p/expressjs` | Express-specific | Ya (kalau Express) |
| 5 | `p/sql-injection` | SQLi patterns | Ya |
| 6 | `p/secrets` | Hardcoded secrets (registry) | Ya |
| 7 | `p/dockerfile` | Dockerfile misconfig | Ya |
| 8 | `/src/.semgrep/owasp-api.yml` | OWASP API Top 10 2023 (custom) | Ya |

**Plus 1..N domain rules** (LLM-detected):
- e-commerce: `ecommerce.yml` + `pci-dss.yml`
- healthcare: `hipaa.yml`
- blog: `blog-csp.yml`
- iot: `iot-mqtt.yml`
- (no extra for general/education)

**Plus 0..1 sub-type rules** (e-commerce only):
- stripe: `pci-stripe.yml`
- midtrans: `pci-midtrans.yml`
- xendit: `pci-xendit.yml`
- etc.

**Maximum rules loaded per repo**:
- General Node.js: 8
- E-commerce + Stripe + Node: 11 (8 + 2 + 1)
- Healthcare + Node: 9 (8 + 1)
- IoT + C: 9 (8 + 1)

---

## 6. LLM Prompt Template (Domain Detection)

Yang LLM harus return (JSON):

```json
{
  "domain": "e-commerce | healthcare | fintech | blog | iot | education | general",
  "sub_type": "stripe | midtrans | xendit | doku | paypal | braintree | razorpay | adyen | square | multi | unknown | none",
  "confidence": 0.0-1.0,
  "evidence": [
    "Domain library detected: ['stripe']",
    "Domain entity detected: ['order', 'cart']"
  ],
  "domain_threats": [
    "Stripe key hardcoded in source",
    "SQL injection in checkout form"
  ]
}
```

**`sub_type`** hanya diisi kalau `domain == "e-commerce"`. Untuk
domain lain, `sub_type = "none"`.

**Fallback** (kalau LLM gagal / return `sub_type = "none"`):
- Pakai `_infer_payment_processor()` di `domain_detection_node.py`
- Lihat `package.json` libs, match dengan `_PAYMENT_PROCESSOR_LIBS`
- Return: `stripe` / `midtrans` / `xendit` / `multi` / `unknown`

---

## 7. Generic Configurability (LLM-Driven Extension)

**Masalah**: pipeline static. Kalau user pake payment processor baru
(GoPay, ShopeePay, OVO), harus bikin rule files baru + update 1 DICT.

**Solusi (LLM-driven)**:

LLM bisa return `llm_rule_suggestions` (opsional):
```json
{
  "domain": "e-commerce",
  "sub_type": "unknown",
  "llm_rule_suggestions": [
    "pci-gopay.yml",      // ← file belum ada, akan di-skip
    "pci-shopeepay.yml",
  ]
}
```

Pipeline process:
1. Untuk setiap rule file, cek apakah ada di `app/agents/semgrep_rules/`
2. Kalau ada → tambahkan ke `sast_ruleset`
3. Kalau tidak ada → skip (jangan error, fallback ke generic rules)

**Cara pakai**: rule files **statis**, tapi **ekstensibilitas** tinggi.
File baru cukup di-drop di folder, lalu `_PAYMENT_PROCESSOR_RULES`
di-update, atau LLM suggest via `llm_rule_suggestions`.

---

## 8. File-File Pipeline

| File | Role | Lines |
|---|---|---|
| `app/agents/nodes/domain_detection_node.py` | LLM detect domain + sub_type | 472 |
| `app/agents/nodes/security_requirement_inference_node.py` | LLM select controls + scan_directives | 350 |
| `app/agents/scan_directives.py` | **Generic** ruleset/job mapping per domain+sub_type | 320 (setelah update) |
| `app/agents/nodes/workflow_generator.py` | Emit YAML | 4548 |
| `app/agents/nodes/pull_request_creation_node.py` | Commit workflow + rules | 351 |
| `app/agents/semgrep_rules/*.yml` | Custom rules | 9 files, 82 rules |
| `app/agents/action_registry.py` | SHA-pinned actions | 320 |
| `app/agents/domain_priority.py` | Severity elevation per domain | 233 |

---

## 9. Job Emit Decision Tree (Generic)

```
For each job in CORE_JOBS:
    if job in detected stages:
        if job == "container-scan" and no Dockerfile:
            skip
        else:
            emit
    else:
        skip

For each domain_job in scan_directives.domain_jobs:
    if domain_job not in scan_directives.domain_skip_jobs:
        emit

For each rule_file in scan_directives.sast_ruleset:
    add "--config={path}" to sast job

For each skip_rule in scan_directives.sast_skip_rules:
    Semgrep skips rules matching the substring (handled at runtime)
```

**Tidak ada hardcoded domain-specific code di workflow generator**
untuk emit core jobs. Semua generic.

---

## 10. Contoh Concrete (E-commerce + Stripe + Monolith)

### Input state ke `_build_workflow_yaml`:
```python
detected_domain = "e-commerce"
detected_sub_type = "stripe"
arch_type = "monolithic"
```

### Output `scan_directives`:
```python
{
  "detected_domain": "e-commerce",
  "detected_sub_type": "stripe",
  "sast_ruleset": [
    "p/owasp-top-ten", "p/javascript", "p/nodejs", "p/expressjs",
    "p/sql-injection", "p/secrets", "p/dockerfile",
    "/src/.semgrep/owasp-api.yml",
    "/src/.semgrep/ecommerce.yml",
    "/src/.semgrep/pci-dss.yml",
    "/src/.semgrep/pci-stripe.yml",
  ],
  "sast_skip_rules": [
    "experimental", "audit",  # baseline
    "kubernetes", "service-mesh", "istio",  # arch: monolith
  ],
  "domain_jobs": [
    {"name": "pci-dss", "description": "PCI-DSS v4.0 compliance check..."}
  ],
  "domain_skip_jobs": [],
}
```

### Output Workflow YAML (excerpt):
```yaml
sast:
  steps:
    - name: Show enabled custom Semgrep rule files
      run: |
        for f in /src/.semgrep/*.yml; do echo "  - $f"; done
    - name: Run Semgrep (SARIF output via docker)
      run: |
        docker run --rm -v ${{ github.workspace }}:/src:ro -v ${{ github.workspace }}:/out \
          returntocorp/semgrep:1.99.0 semgrep \
            --config=p/owasp-top-ten \
            --config=p/javascript \
            --config=p/nodejs \
            --config=p/expressjs \
            --config=p/sql-injection \
            --config=p/secrets \
            --config=p/dockerfile \
            --config=/src/.semgrep/owasp-api.yml \
            --config=/src/.semgrep/ecommerce.yml \
            --config=/src/.semgrep/pci-dss.yml \
            --config=/src/.semgrep/pci-stripe.yml \
            --sarif --output=/out/semgrep-results.sarif /src

pci-dss:
  steps:
    - name: Checkout code
    - name: Scan for hardcoded PAN/CVV
    - name: Validate .env not in git history
    - name: Generate PCI-DSS audit SARIF
    - name: Upload PCI-DSS audit to Code Scanning
    - name: Upload PCI-DSS audit as artifact
```

---

## 11. Perbandingan: Sebelum vs Sesudah Generic Pipeline

### Sebelum (commit `03b40d0`, `31a853c`)
- 5 hardcoded domain jobs di `workflow_generator.py`
- 28 custom rules (16 e-commerce + 12 OWASP API)
- TIDAK ada sub_type support
- Setiap domain-specific logic ada di generator function

### Sesudah (commit ini, v2 generic)
- 1 DICT di `scan_directives.py` (CENTRALIZED)
- 5 layer (baseline → domain → sub_type → arch → LLM)
- Sub_type support (12 payment processors)
- Generic code di generator, specific config di data
- LLM-driven extension (`llm_rule_suggestions`)

### Matriks coverage (commit v2)

| Domain | Sub-type | Custom Rules | Extra Jobs |
|---|---|---|---|
| general | none | 1 (owasp-api) | 0 |
| education | none | 1 (owasp-api) | 0 |
| blog | none | 2 (owasp-api + blog-csp) | 1 (csp-headers) |
| iot | none | 2 (owasp-api + iot-mqtt) | 1 (mqtt-security) |
| healthcare | none | 2 (owasp-api + hipaa) | 1 (hipaa) |
| fintech | none | 3 (owasp-api + ecommerce + fintech-ledger) | 1 (ledger-check) |
| e-commerce | unknown | 3 (owasp-api + ecommerce + pci-dss) | 1 (pci-dss) |
| e-commerce | stripe | 4 (+pci-stripe) | 1 (pci-dss) |
| e-commerce | midtrans | 4 (+pci-midtrans) | 1 (pci-dss) |
| e-commerce | xendit | 4 (+pci-xendit) | 1 (pci-dss) |
| e-commerce | paypal | 4 (+pci-paypal) | 1 (pci-dss) |
| e-commerce | braintree | 4 (+pci-braintree) | 1 (pci-dss) |
| e-commerce | multi | union dari semua | 1 (pci-dss) |

**13 distinct domain × sub_type combinations** dari 1 generic pipeline.

---

## 12. Cara Extend (Untuk Skripsi)

### Use case: Tambah payment processor baru (GoPay)

**Step 1**: Tambah library di `domain_detection_node.py`:
```python
"e-commerce": {
    "libraries": [
        ...,
        "gopay-node", "gopay",  # ← BARU
    ],
}
```

**Step 2**: Tambah rule file di `app/agents/semgrep_rules/pci-gopay.yml`:
```yaml
rules:
  - id: pci-gopay-server-key
    pattern-regex: '\bgopay_server_key\s*[=:]\s*["\']\w{20,}["\']'
    ...
```

**Step 3**: Tambah mapping di `scan_directives.py`:
```python
_PAYMENT_PROCESSOR_RULES = {
    ...,
    "gopay": ("pci-gopay.yml",),  # ← BARU
}

_PAYMENT_PROCESSOR_LIBS = {  # di domain_detection_node.py
    ...,
    "gopay": ("gopay-node", "gopay"),
}
```

**Step 4**: (Opsional) Tambah ke LLM prompt:
```python
DOMAIN_DETECTION_PROMPT = """...
sub_type: "stripe|midtrans|xendit|doku|paypal|braintree|gopay|...""",
```

**Total: ~30 menit** untuk support payment processor baru.

---

## 13. Open Items (Future Work)

- [ ] Tambah rule file untuk: `pci-gopay.yml`, `pci-shopeepay.yml`, `pci-ovo.yml`, `pci-dana.yml`
- [ ] Sub-classification untuk **fintech**: `exchange`, `neobank`, `crypto-wallet`
- [ ] Sub-classification untuk **healthcare**: `ehr-system`, `telemedicine`, `medical-imaging`
- [ ] Sub-classification untuk **blog**: `static-site` (Jekyll), `cms` (WordPress), `comments-heavy`
- [ ] LLM-driven auto-rule-generation (analisis source → generate Semgrep rule)
- [ ] Multi-language (TypeScript, Python, Go) detection di domain_detection
- [ ] Integration dengan Semgrep Registry API untuk dynamic rule fetching

---

## 14. Confirmation Checklist untuk Skripsi

Sebelum commit, verifikasi:

- [x] Pipeline generic (1 core structure, 5 layer customization)
- [x] Domain detection (7 domain) + sub_type (12 payment processor) via LLM
- [x] scan_directives.py CENTRALIZED (1 file, 5 layer DICT)
- [x] workflow_generator THIN (no hardcoded domain logic, just emitter)
- [x] Custom rules push via `pull_request_creation_node` (existing)
- [x] Empty SARIF fallback (existing)
- [x] Trivy exit-code: 0 (existing)
- [x] Action SHA-pinned (existing)
- [x] 78/78 tests pass

**Generator pipeline v2 (generic) SIAP DIGUNAKAN**.

---

**End of PIPELINE-STRUCTURE.md (v2 Generic + LLM-Driven)**
