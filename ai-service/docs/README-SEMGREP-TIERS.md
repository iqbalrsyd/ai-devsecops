# README — Semgrep Pipeline: Generic + Domain (Tier 1 + Tier 3)

> **Audiens**: Penulis skripsi (Bab 4 §4.4) + maintainer pipeline.
> **Status**: IMPLEMENTASI. Tier 1 statis selalu ON. Tier 3 LLM-generated opt-in via env var.
> **Single source of truth**: `ai-service/app/agents/semgrep_rules/llm_generation_config.py` + `scan_directives.py` + `semgrep_rules/index.yml`.
> **Desain final (sesuai keputusan user)**: hanya 2 tier — Tier 1 (statis per domain) + Tier 3 (LLM-generated, opt-in). Sub-type payment processor rules TIDAK dipakai. Tier 1 + Tier 3 digabung jadi SATU file `.yml` per pipeline run.

---

## 1. Posisi Semgrep di Pipeline Besar (4 Tahap)

Pipeline AI agent punya **4 tahap** (lihat `docs/PIPELINE-STRUCTURE.md` &
`docs/README-DOMAIN-AWARE-PIPELINE.md`):

```
┌────────────────────────────────────────────────────────────────────────────┐
│  TAHAP 1: K1 — Repository Context Analysis (7 node)                        │
│  Tahap output: detected_domain, threats, technologies, dll.                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  repository_connection → repository_scan → vulnerability_scan →      │  │
│  │  technology_detection → architecture_detection → deployment_detection│  │
│  │  → domain_detection  ←── TIER 3 INSERT di sini (K1.5)               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                             │
│  TAHAP 2: K2 — Security Requirement Inference (1 node)                     │
│  Tahap output: scan_directives (ruleset + jobs + skip)                    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  security_requirement_inference                                      │  │
│  │    → baca state.llm_generated_rules_filename (dari Tier 3)          │  │
│  │    → build_scan_directives(llm_rule_suggestions=[merged_filename]) │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                             │
│  TAHAP 3: K3 — Generation + Deployment (11 node)                           │
│  Tahap output: workflow YAML + .semgrep/<domain>-combined-<hash>.yml di-PR│
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  workflow_generation    ←─ consume scan_directives (Tier 1 + 3)     │  │
│  │  workflow_validation                                                   │  │
│  │  github_branch_creation                                                │  │
│  │  pull_request_creation  ←─ commit 1 file merged .yml (Tier 1+3)     │  │
│  │  workflow_execution     ←─ SAST job: validate → run semgrep          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                             │
│  TAHAP 4: K3 — Scoring (5 node)                                            │
│  Tahap output: risk_score, recommendation, response                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  security_analysis → risk_assessment → compliance_mapper →           │  │
│  │  recommendation_generation → response_formatter                       │  │
│  │  (Tier 3 tidak aktif di sini — Semgrep rule dipakai di Tahap 3)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Singkatnya**:
- **Tier 3 (LLM-generated)** di-trigger di **akhir Tahap 1** (node K1.5 `semgrep_llm_generation`, setelah `domain_detection`), karena butuh `domain + threats + primary_language` yang baru tersedia di situ.
- **Tier 1 (statis)** + **Tier 3 (LLM)** dibaca di **Tahap 2** lewat `build_scan_directives()`. Tier 3 rule filenames di-append ke `sast_ruleset` sebagai `Layer 4`.
- **Kedua tier dipakai** sebagai `--config` flags di **SAST job Tahap 3**, dan file `.yml`-nya di-merge jadi **1 file** `.semgrep/<domain>-combined-<hash>.yml` lalu di-commit di `pull_request_creation_node`.

---

## 2. Tabel Perbedaan Per Domain (untuk skripsi)

> Selaras dengan `scan_directives._DOMAIN_RULES` + `_DOMAIN_SKIP_JOBS` + `llm_generation_config.LLM_GENERATION_DOMAINS`.
> **Desain final**: TIDAK ADA sub-type (payment processor) rules. Cukup 1 ruleset per domain. Tier 1 + Tier 3 digabung jadi 1 file `.yml`.

| Domain      | Tier 1: Static `.yml` (Selalu Aktif)        | Tier 3: LLM-Generated Scope (Opt-In)         | File Hasil di `.semgrep/`                       | Domain Jobs   | Skip Jobs                                       |
|-------------|----------------------------------------------|----------------------------------------------|------------------------------------------------|---------------|-------------------------------------------------|
| e-commerce  | `ecommerce.yml`, `pci-dss.yml`               | ON — payment, BOLA cart, price tampering, webhook forgery | `e-commerce-combined-<hash>.yml`               | `pci-dss`     | —                                               |
| fintech     | `ecommerce.yml`, `fintech-ledger.yml`        | ON — ledger integrity, KYC bypass, replay, transfer tamper | `fintech-combined-<hash>.yml`                  | `ledger-check`| —                                               |
| healthcare  | `hipaa.yml`                                  | ON — PHI exposure, weak auth medical, audit log gaps | `healthcare-combined-<hash>.yml`                | `hipaa`       | `command-injection`                             |
| blog        | `blog-csp.yml`                               | ON — XSS comment, file upload bypass, content injection md | `blog-combined-<hash>.yml`                      | `csp-headers` | `container-scan`, `idor`, `ssrf`, `jwt`, `rate-limiting` |
| iot         | `iot-mqtt.yml`                               | ON — device auth bypass, MQTT no-encrypt, firmware tamper, default creds | `iot-combined-<hash>.yml`                       | `mqtt-security`| —                                              |
| education   | — (kosong)                                   | ON — student data leak, cheating bypass, grade tamper, weak access | `education-combined-<hash>.yml`                 | —             | `ssrf`, `rate-limiting`                         |
| general     | `owasp-api.yml` (sama dengan baseline)       | **OFF** — tidak di-generate                  | `owasp-api.yml` saja (Tier 1)                  | —             | `pci-dss`, `hipaa`, `ledger-check`, `csp-headers`, `mqtt-security` |

**Batasan Tier 3 (wajib):**
- ❌ **TIDAK** generate untuk domain `general` (kalau tidak ada sinyal domain, jangan generate rule baru).
- ❌ **TIDAK** generate sub-type rules (stripe, midtrans, dll) — semua disatukan di ruleset domain.
- ❌ **TIDAK** generate untuk arsitektur `kubernetes` / `service-mesh` (sudah di-skip di Layer 3 `scan_directives.py`).
- ✅ Hanya generate dari `domain_threats` (output `domain_detection_node`), **bukan** dari rules registry.
- ✅ Confidence threshold: rule LLM dengan confidence `< 0.7` di-drop, **tidak** masuk workflow.
- ✅ Severity default `WARNING` (bukan `ERROR`) di first generation — biar tidak break build user.

**Storage:** file `.yml` hasil merge di-commit ke `.semgrep/<domain>-combined-<hash>.yml` di repo target via PR. Hash 8 char dari SHA-256 input (domain, threats, primary_language, frameworks) → diff minimal antar run.

---

## 3. Step-by-Step Eksekusi (10 Step)

### Step 1 — ✅ Config Tier 3
**File**: `ai-service/app/agents/semgrep_rules/llm_generation_config.py`
- `ENABLE_LLM_GENERATED_RULES` (env var, default `false`)
- `LLM_GENERATION_DOMAINS` (6 domain utama, TIDAK termasuk `general`)
- `MIN_LLM_CONFIDENCE` (default `0.7`)
- `MAX_RULES_PER_DOMAIN` (default `5`)
- ID prefix wajib: `{domain}-custom-{slug}`
- Cache key: SHA-256 dari `(domain, threats, primary_language, frameworks)`
- Filename merged: `{domain}-combined-{short_hash}.yml` (1 file per pipeline run untuk Tier 1 + Tier 3)

### Step 2 — ✅ Prompt LLM
**File**: `ai-service/app/agents/semgrep_rules/llm_generation_prompt.py`
- Input: `domain`, `domain_threats[]`, `primary_language`, `frameworks[]`
- Output: list of Semgrep rule spec (id, languages, severity, message, pattern, metadata)
- Constraint: WAJIB ID prefix, severity TIDAK `ERROR` di first iterasi, output `confidence` 0.0-1.0 per rule

### Step 3 — ✅ Node Tier 3
**File**: `ai-service/app/agents/nodes/semgrep_llm_generator_node.py`
- Cek `is_domain_eligible(detected_domain)` (fitur flag + scope 6 domain)
- Cache get via `compute_cache_key()` → kalau hit, return
- Cache miss → invoke LLM, parse output, filter by confidence, cap di `MAX_RULES_PER_DOMAIN`
- Tulis ke `state["llm_generated_rules"]`, `state["llm_generated_rules_filename"]`, `state["llm_generated_rules_source"]`

### Step 4 — ✅ Insert node di `pipeline_graph.py`
- Tambah `workflow.add_node("semgrep_llm_generation", semgrep_llm_generator_node)`
- Tambah edge: `domain_detection → semgrep_llm_generation → security_requirement_inference`

### Step 5 — ✅ Update `scan_directives.py`
- Hapus `_PAYMENT_PROCESSOR_RULES` + `_SUB_TYPE_JOBS` (Tier 2 sub-type tidak dipakai)
- `build_scan_directives()` parameter `sub_type` masih diterima (backward-compat) tapi **tidak menambah rule**
- Wire `llm_rule_suggestions` → ditambahkan ke `sast_ruleset` sebagai Layer 4

### Step 6 — ✅ Update `security_requirement_inference_node.py`
- Baca `state["llm_generated_rules"]` dan `state["llm_generated_rules_filename"]`
- Pass ke `build_scan_directives(llm_rule_suggestions=[filename])`

### Step 7 — ✅ Update `pull_request_creation_node.py` (merge Tier 1+3)
- Jika Tier 3 ON dan ada rules → baca semua static `.yml` → merge `rules: []` ke 1 dokumen YAML → commit sebagai `.semgrep/<domain>-combined-<hash>.yml`
- Jika Tier 3 OFF atau no rules → legacy path: commit setiap static file `.yml` terpisah (backward compat)

### Step 8 — ✅ Tambah `semgrep --validate` step di workflow generator
**File**: `ai-service/app/agents/nodes/workflow_generator.py`
- Tambah step `Validate custom Semgrep rules` SEBELUM `Run semgrep` di job `sast`
- Loop semua file di `.semgrep/*.yml`, jalankan `semgrep --validate` via docker
- `continue-on-error: true` — kalau rule invalid, log warning tapi workflow tetap jalan

### Step 9 — ✅ Tabel markdown
**File**: `ai-service/docs/domain-rules-table.md`

### Step 10 — ✅ README (file ini)

---

## 4. Urutan Pemanggilan (Sequence)

```
[Tahap 1: K1]
  domain_detection_node
    └─ output: state.detected_domain, state.domain_threats[]

  semgrep_llm_generator_node  ← K1.5 (kondisional: ENABLE_LLM_GENERATED_RULES=true)
    ├─ input: detected_domain, domain_threats, primary_language, frameworks
    ├─ cache check (key = SHA-256 dari 4 input di atas)
    ├─ kalau miss → LLM call → parse → filter by confidence
    └─ output: state.llm_generated_rules = [{id, languages, severity, pattern, metadata, ...}, ...]
              state.llm_generated_rules_filename = "<domain>-combined-<8char>.yml"

[Tahap 2: K2]
  security_requirement_inference_node
    ├─ baca state.llm_generated_rules_filename
    ├─ build_scan_directives(
    │     detected_domain=...,
    │     llm_rule_suggestions=[filename],  ← Tier 3
    │   )
    │   # di dalam build_scan_directives:
    │   #   Layer 1: baseline (p/owasp-top-ten, p/javascript, ...)
    │   #   Layer 2: general-api (owasp-api.yml) + domain-specific (ecommerce.yml, pci-dss.yml, ...)
    │   #   Layer 3: arch-specific skip rules
    │   #   Layer 4: LLM-driven (filename Tier 3)
    └─ output: state.inferred_security_needs.scan_directives

[Tahap 3: K3 Generation]
  workflow_generator
    ├─ baca scan_directives.sast_ruleset
    ├─ untuk setiap file .yml di sast_ruleset, emit:
    │     --config=.semgrep/<file>.yml
    └─ output: workflow YAML dengan SAST job

[Tahap 3: K3 Deployment]
  pull_request_creation_node
    ├─ cek state.llm_generated_rules
    ├─ JIKA ada:
    │   ├─ baca static .yml files dari app/agents/semgrep_rules/
    │   ├─ extract rules: [] dari masing-masing
    │   ├─ gabung dengan llm_generated_rules
    │   ├─ serialize ke 1 dokumen YAML
    │   └─ commit ke .semgrep/<domain>-combined-<hash>.yml
    └─ JIKA TIDAK (legacy): commit setiap static file .yml terpisah

  workflow_execution
    └─ jalankan workflow YAML di GitHub Actions:
         step 1: Show enabled custom Semgrep rule files
         step 2: Validate custom Semgrep rules  ← BARU
           semgrep --validate --config=.semgrep/<file>
         step 3: Run semgrep (SARIF output)
           semgrep ci --config=...

[Tahap 4: K3 Scoring]
  security_analysis → ... → response_formatter
    └─ (Semgrep rule TIDAK di sini, tapi finding SARIF dari step sast di-scrape
         dan di-score di security_analysis)
```

---

## 5. File-File yang Diubah / Dibuat

| Step | Aksi | Path |
|------|------|------|
| 1 | buat | `ai-service/app/agents/semgrep_rules/llm_generation_config.py` ✅ |
| 2 | buat | `ai-service/app/agents/semgrep_rules/llm_generation_prompt.py` ✅ |
| 3 | buat | `ai-service/app/agents/nodes/semgrep_llm_generator_node.py` ✅ |
| 4 | edit | `ai-service/app/agents/pipeline_graph.py` (tambah node K1.5) ✅ |
| 5 | edit | `ai-service/app/agents/scan_directives.py` (hapus Tier 2, wire `llm_rule_suggestions`) ✅ |
| 6 | edit | `ai-service/app/agents/nodes/security_requirement_inference_node.py` (pass `llm_rule_suggestions`) ✅ |
| 7 | edit | `ai-service/app/agents/nodes/pull_request_creation_node.py` (merge Tier 1+3 → 1 file) ✅ |
| 8 | edit | `ai-service/app/agents/nodes/workflow_generator.py` (tambah `semgrep --validate` step) ✅ |
| 9 | buat | `ai-service/docs/domain-rules-table.md` ✅ |
| 10 | buat | `ai-service/docs/README-SEMGREP-TIERS.md` (file ini) ✅ |

State tambahan di `ai-service/app/agents/pipeline_state.py`:
- `llm_generated_rules: list`
- `llm_generated_rules_cache_key: str | None`
- `llm_generated_rules_filename: str | None`
- `llm_generated_rules_source: str | None`

---

## 6. Trade-off Singkat (untuk reviewer)

| Aspek | Tier 1 (statis) | Tier 3 (LLM) |
|---|---|---|
| Token cost | 0 | ~1-2K / pipeline run (kalau cache miss) |
| Konsistensi output | Deterministik | Non-deterministic (mitigasi: cache by hash, temperature=0) |
| Akurasi | Tinggi (manual curate) | Sedang (LLM bisa hallucinate Semgrep syntax → mitigasi: `semgrep --validate` di CI) |
| Coverage | 6 domain dasar | Domain eligible + ancaman baru emerging |
| Cocok untuk skripsi | Reproducible ✅ | Perlu jelaskan batasan (Section 2) |

---

## 7. Risiko & Mitigasi

1. **LLM hallucinate Semgrep syntax**
   → Mitigasi: `semgrep --validate` di workflow CI step `Validate custom Semgrep rules`. Rule invalid di-skip (`continue-on-error: true`).
2. **Token cost naik**
   → Mitigasi: cache by SHA-256 input. Key = `(domain, threats, primary_language, frameworks)`.
3. **PR jadi noisy** (file `.yml` baru tiap run)
   → Mitigasi: filename include 8-char hash → kalau rule content berubah, file baru, file lama di-rewrite di commit berikutnya.
4. **Confidence rendah / LLM ngaco**
   → Mitigasi: threshold `MIN_LLM_CONFIDENCE = 0.7`. Rule di-drop, di-log di state untuk observability.
5. **Severity `ERROR` bikin build fail di first run**
   → Mitigasi: `DEFAULT_LLM_RULE_SEVERITY = "WARNING"` di first generation. Maintainer promote ke `ERROR` setelah review PR.

---

## 8. Konfigurasi Env Var

```bash
# Enable/disable Tier 3 (default: false = OFF, backward compat)
ENABLE_LLM_GENERATED_RULES=true

# Confidence threshold (default: 0.7)
MIN_LLM_CONFIDENCE=0.7

# Max rules per domain (default: 5)
MAX_RULES_PER_DOMAIN=5
```

TIDAK ada env var untuk Tier 1 — selalu ON (statis di code).
