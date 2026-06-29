# Migration Plan: Penyesuaian Prototype ke struktur-v6

> **Acuan utama:** [`struktur-v6.md`](../struktur-v6.md) — *Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices*, versi Pasca-Bimbingan 17 Juni 2026.
>
> **Prinsip migrasi:**
> 1. Sesuaikan prototype yang ada — **tanpa redesign total**.
> 2. Perubahan **minimal** agar node LangGraph, state, dan alur konsisten dengan struktur-v6.
> 3. Pertahankan komponen yang masih relevan, hanya tambah yang benar-benar diperlukan.
> 4. Threat modeling (STRIDE/PASTA) **hanya landasan konseptual** di Bab 2 — tidak diimplementasikan.
> 5. Tidak menambah kembali node remediation / workflow repair / workflow_config_*.

---

## 1. Latar Belakang Migrasi

struktur-v6 memperkenalkan **3 kontribusi utama** dengan **21 node** (bukan 26 atau 23 seperti implementasi lama):

| Kontribusi | Cakupan | Node |
|------------|---------|------|
| **K1** Repository Context Analysis | 4 dimensi konteks (technologies, architecture, deployment, **domain**) | 7 node |
| **K2** Context-Aware Security Requirement Inference | Context → Attack Surface → Threat → Controls (5 langkah) | 1 node (+ helper) |
| **K3** Adaptive DevSecOps Pipeline Generation & Evaluation | Generation → Validation → Deploy → Execute → Scoring | 13 node |
| Utility | Error handling | 1 node |
| **Total** | | **21 node** |

Perubahan terminologi utama:
- `compliance_score` → **`security_standards_coverage_score`**
- Tambah **`detected_domain`** + `domain_threats[]` ke alur K1→K2
- Tambah **`attack_surfaces[]`** sebagai lookup table deterministik di K2
- Hapus node yang terkait **remediation chain** (Flow F) — bukan kontribusi skripsi
- Hapus **`workflow_repair_node`** — bukan kontribusi skripsi
- Hapus **`workflow_config_issue_node`** & **`workflow_config_remediation_node`** — bukan kontribusi skripsi

---

## 2. Gap Analysis

### 2.1 Komparasi Node (struktur-v6 vs prototype)

| Node struktur-v6 | Status di Prototype | Aksi |
|------------------|---------------------|------|
| **K1 — Repository Context Analysis (7)** | | |
| `repository_connection` | ✅ Ada, dipakai | Pertahankan |
| `repository_scan` | ✅ Ada, dipakai | Pertahankan |
| `vulnerability_scan` | ✅ Ada, dipakai | Pertahankan |
| `technology_detection` | ✅ Ada, dipakai | Pertahankan |
| `architecture_detection` | ✅ Ada, dipakai | Pertahankan |
| `deployment_detection` | ✅ Ada, dipakai | Pertahankan |
| **`domain_detection`** | ❌ **Tidak ada** | **TAMBAH (P1.1)** |
| **K2 — Inference (1 node utama)** | | |
| `security_requirement_inference` | ✅ Ada, dipakai | **Refactor prompt (P1.4)** + tambah attack surface lookup (P1.3) |
| **K3 — Generation (2)** | | |
| `workflow_generation` | ✅ Ada, dipakai | Pertahankan + update prompt (P2.4) |
| `workflow_validation` | ✅ Ada, dipakai | Pertahankan |
| **K3 — Deployment (5)** | | |
| `auto_deploy_check` | ✅ Ada di graph | Pertahankan |
| `github_branch_creation` | ✅ Ada, dipakai | Pertahankan |
| `pull_request_creation` | ✅ Ada, dipakai | Pertahankan |
| `workflow_execution` | ✅ Ada, dipakai | Pertahankan |
| `execution_monitor` | ⚠️ Ada tapi dead code | Pertahankan (per struktur-v6) — wire ke pipeline |
| **K3 — Scoring (5)** | | |
| `security_analysis` | ✅ Ada, dipakai | **Tambah domain-aware (P1.5)** |
| `risk_assessment` | ✅ Ada, dipakai | Pertahankan |
| `compliance_mapper` | ✅ Ada, dipakai | **Rename output (P2.1)** |
| `recommendation_generation` | ✅ Ada, dipakai | Pertahankan |
| `response_formatter` | ✅ Ada, dipakai | Pertahankan |
| **Utility (1)** | | |
| `error_handler` | ✅ Ada | Pertahankan |
| **Node berlebih di prototype (HAPUS)** | | |
| `workflow_repair_node` | ⚠️ Dipakai di Flow A/C | **HAPUS (P3.1)** |
| `execution_log_collection_node` | ⚠️ Dipakai di Flow F | **HAPUS (P3.2)** |
| `workflow_failure_analysis_node` | ⚠️ Dipakai di Flow F | **HAPUS (P3.2)** |
| `root_cause_detection_node` | ⚠️ Dipakai di Flow F | **HAPUS (P3.2)** |
| `workflow_remediation_generation_node` | ⚠️ Dipakai di Flow F | **HAPUS (P3.2)** |
| `remediation_pr_creation_node` | ⚠️ Dipakai di Flow F | **HAPUS (P3.2)** |
| `workflow_config_issue_node` | ⚠️ Ada di graph | **HAPUS (P3.3)** |
| `workflow_config_remediation_node` | ⚠️ Ada di graph | **HAPUS (P3.3)** |

### 2.2 Komparasi State Fields

| Field struktur-v6 | Status di Prototype | Aksi |
|------------------|---------------------|------|
| `detected_technologies` | ✅ Ada | Pertahankan |
| `detected_architecture` (+ type/conf/reason) | ✅ Ada | Pertahankan |
| `detected_deployment` | ✅ Ada | Pertahankan |
| **`detected_domain`** | ❌ **Tidak ada** | **TAMBAH (P1.2)** |
| **`domain_confidence`** | ❌ **Tidak ada** | **TAMBAH (P1.2)** |
| **`domain_evidence[]`** | ❌ **Tidak ada** | **TAMBAH (P1.2)** |
| **`domain_threats[]`** | ❌ **Tidak ada** | **TAMBAH (P1.2)** |
| **`attack_surfaces[]`** | ❌ **Tidak ada** | **TAMBAH (P1.2)** |
| `inferred_security_needs` | ✅ Ada | Pertahankan + update payload |
| `compliance_score` | ✅ Ada | **Rename ke `security_standards_coverage_score` (P2.1)** |
| `security_coverage_score` | ✅ Ada | Pertahankan |
| `risk_score` | ✅ Ada | Pertahankan |
| `remediation_*` fields | ⚠️ Ada | **Hapus (P3.2)** |
| `failure_*` fields | ⚠️ Ada | **Hapus (P3.2)** |

---

## 3. Daftar Perubahan (Berprioritas)

### 🔴 PRIORITAS 1 — Wajib (Kontributor Inti)

#### P1.1 — Tambah Node `domain_detection`
- **File baru:** `ai-service/app/agents/nodes/domain_detection_node.py`
- **Fungsi:** Deteksi tema/domain webapp (e-commerce, healthcare, fintech, blog, IoT, education, general).
- **Input:** `repository_scan` (file tree, package manifests) + `technology_detection` (libraries).
- **Alur 3 langkah** (sesuai struktur-v6 §3.5.3):
  1. **Deterministik** — ekstrak sinyal: nama project, deskripsi, library keywords (Stripe/FHIR/MQTT), entity naming patterns (Product/Patient/Device).
  2. **LLM** — klasifikasi domain → `{domain, confidence, evidence[], domain_threats[]}`.
  3. **Fallback** — jika `confidence < 0.50` → "general".
- **Output ke state:** `detected_domain`, `domain_confidence`, `domain_evidence`, `domain_threats`.

**Domain & library indicators (lookup):**
| Domain | Library | Entity |
|--------|---------|--------|
| e-commerce | stripe, paypal, braintree | Order, Product, Cart, Payment |
| healthcare | fhir, hl7, epic | Patient, Appointment, Prescription |
| fintech | plaid, open-banking | Account, Transaction, Ledger |
| blog/content | marked, showdown, sanitize-html | Post, Comment, Tag |
| iot backend | mqtt, amqp, paho-mqtt | Device, Sensor, Telemetry |
| education | moodle-sdk, scorm | Course, Enrollment, Quiz |
| general | — | — |

#### P1.2 — Tambah State Fields
- **File:** `ai-service/app/agents/pipeline_state.py`
  ```python
  detected_domain: str | None
  domain_confidence: float | None
  domain_evidence: list[str]
  domain_threats: list[str]
  attack_surfaces: list[str]
  ```
- **File:** `ai-service/app/services/pipeline_service.py` → `_get_default_state()` (inisialisasi).

#### P1.3 — Attack Surface Identification (Lookup Table Deterministik)
- **Lokasi:** helper function di dalam `security_requirement_inference_node.py` (atau file baru `attack_surface_identification.py`).
- **Bukan LLM** — deterministic lookup (`deployment_target` → `attack_surfaces[]`).

| Deployment | Attack Surfaces |
|------------|-----------------|
| `docker` | Container Image, Dockerfile Config, Image Layer Secrets |
| `kubernetes` | RBAC, Container Images, Ingress, Service Accounts, Pod Security |
| `terraform` | S3 ACL, IAM Roles, Security Groups |
| `code-only` | Source Code, Dependencies, Secrets in Code |

- **Tujuan:** Jaminan determinisme + jembatan antara deployment dan kontrol (sesuai struktur-v6 §3.7.3).

#### P1.4 — Update `security_requirement_inference_node` ke Alur 5-Langkah
- **File:** `ai-service/app/agents/nodes/security_requirement_inference_node.py`
- Implementasi urutan (struktur-v6 §3.7.2):
  1. **Repository Context** (dari K1: technologies + architecture + deployment + **domain**)
  2. **Attack Surface Identification** (lookup P1.3)
  3. **Threat Inference** (LLM, dengan `{domain}` + `{domain_threats}` + `{attack_surfaces}`)
  4. **Security Control Selection** (LLM, dari 17 kontrol — sesuai struktur-v6 §3.7.5 prompt)
  5. **Output** → `security_needs[]` untuk `workflow_generation`
- **Tambah field prompt:** `{domain}`, `{domain_confidence}`, `{domain_threats}`, `{attack_surfaces}`.

#### P1.5 — Domain-Aware Security Analyzer
- **File:** `ai-service/app/agents/nodes/security_analyzer.py`
- Tambah prompt domain-aware (struktur-v6 §3.11):
  - **e-commerce:** payment findings → CRITICAL, checkout/auth → HIGH
  - **healthcare:** patient data exposure → CRITICAL, auth-bypass → HIGH
  - **blog:** XSS content injection → HIGH, file upload bypass → HIGH
  - **iot:** device auth bypass → CRITICAL, MQTT → HIGH
  - **general:** standard severity
- Output: risk score per finding, dengan bobot sesuai prioritas domain.

---

### 🟡 PRIORITAS 2 — Penyelarasan dengan struktur-v6

#### P2.1 — Rename `compliance_score` → `security_standards_coverage_score`
- **Files:**
  - `ai-service/app/agents/pipeline_state.py` (state field)
  - `ai-service/app/agents/nodes/compliance_mapper.py` (output)
  - `ai-service/app/services/pipeline_service.py` (mapping)
  - `ai-service/app/agents/pipeline_schemas.py` (Pydantic)
  - `ai-service/app/api/pipeline.py` (response)
- **DB column:** tetap `compliance_score` untuk backward compatibility.
- **API field:** expose sebagai `security_standards_coverage_score`.
- **Tambah disclaimer** di metadata (struktur-v6 §2.2.8 catatan):
  > "Skor ini adalah indikator cakupan kontrol terhadap referensi standar, BUKAN bukti kepatuhan organisasi/regulatoris."
- Update label di frontend & `ARCHITECTURE.md`.

#### P2.2 — Rebuild `pipeline_graph.py` ke 21 Node
- **File:** `ai-service/app/agents/pipeline_graph.py`
- Susun ulang node persis sesuai tabel struktur-v6 §3.3:
  - **K1 (7):** `repository_connection`, `repository_scan`, `vulnerability_scan`, `technology_detection`, `architecture_detection`, `deployment_detection`, **`domain_detection`**
  - **K2 (1):** `security_requirement_inference`
  - **K3 Generation (2):** `workflow_generation`, `workflow_validation`
  - **Deployment (5):** `auto_deploy_check`, `github_branch_creation`, `pull_request_creation`, `workflow_execution`, `execution_monitor`
  - **Scoring (5):** `security_analysis`, `risk_assessment`, `compliance_mapper`, `recommendation_generation`, `response_formatter`
  - **Utility (1):** `error_handler`

#### P2.3 — Sinkronkan `pipeline_service._invoke_graph_phase`
- **File:** `ai-service/app/services/pipeline_service.py`
- Flow A/B/C (`run_repo_pipeline`, `run_repo_analyze`, `run_repo_generate`): tambah `domain_detection` setelah `deployment_detection` (sebelum `security_requirement_inference`).
- Update imports & `node_map`.
- Hapus referensi ke `workflow_repair_node` (P3.1) dan 5 node remediation (P3.2).

#### P2.4 — Update Vignette Prompts di `workflow_generator`
- **File:** `ai-service/app/agents/nodes/workflow_generator.py`
- Tambah ke system prompt: `detected_domain`, `domain_confidence`, `domain_threats`.
- Tambah **insert prompt per arsitektur** (struktur-v6 §3.8.3):
  - **Monolith:** "Single workflow, sequential pipeline, single build artifact."
  - **Microservices:** "{service_count} services at {service_paths} — each needs own workflow. Use matrix strategy. Include service mesh & API gateway."

---

### 🟢 PRIORITAS 3 — Bersih-bersih (Hapus yang Tidak Relevan)

#### P3.1 — Hapus Workflow Repair Logic
- **File:** `ai-service/app/services/pipeline_service.py`
- Hapus `workflow_repair_node` dari graph.
- Hapus loop `[validation_errors] → repair → validation` di Flow A/C.
- Validasi jadi single pass: jika gagal → set `errors` dan `validation_passed=False`.

#### P3.2 — Hapus Remediation Chain (Flow F)
- **Files:**
  - `ai-service/app/services/pipeline_service.py` — hapus `run_execution_analysis`.
  - `ai-service/app/agents/nodes/execution_log_collection_node.py` — **HAPUS file**
  - `ai-service/app/agents/nodes/workflow_failure_analysis_node.py` — **HAPUS file**
  - `ai-service/app/agents/nodes/root_cause_detection_node.py` — **HAPUS file**
  - `ai-service/app/agents/nodes/workflow_remediation_generation_node.py` — **HAPUS file**
  - `ai-service/app/agents/nodes/remediation_pr_creation_node.py` — **HAPUS file**
- **API:** hapus/deprecate `POST /pipeline/analyze-execution/:run_id`.
- **Frontend:** hapus tombol "Fix Failed Workflow" di `RunDetail.tsx`.
- **Hapus state fields:** `remediation_*`, `failure_*`, `failed_jobs`, `failed_steps`, `failure_logs`, `failure_analysis`, `root_cause`.

#### P3.3 — Hapus `workflow_config_issue` & `workflow_config_remediation`
- **File:** `ai-service/app/agents/pipeline_graph.py`
- Hapus kedua node (bukan bagian dari 21 node struktur-v6).
- Pertahankan hanya `compliance_mapper` → `recommendation_generation` → `response_formatter` di scoring chain.
- Hapus state fields: `workflow_config_issues`, `maintenance_warnings`, `external_service_issues`, `workflow_annotations`, `remediation_recommendations`, `remediation_yaml_patches` (atau tetap simpan di bucket, tapi jangan di node graph).

#### P3.4 — Hapus atau Wire `execution_monitor`
- **Opsi A (disarankan):** Wire `execution_monitor` ke Flow A setelah `workflow_execution` (sesuai struktur-v6: "monitoring pipeline selesai → trigger security_analysis").
- **Opsi B:** Hapus jika monitoring tidak relevan (tapi struktur-v6 mempertahankannya, jadi lebih baik di-wire).

#### P3.5 — Update `ARCHITECTURE.md`
- **File:** `ai-service/ARCHITECTURE.md`
- Tabel "Dipakai" → **21 node** (bukan 23).
- Hapus Flow F (remediation).
- Hapus `workflow_repair` dari flow.
- Update label metric Tabel 3: `compliance_score` → `security_standards_coverage_score`.
- Update §3 Allowed Dashboard Metrics: tambahkan disclaimer "indikator, bukan bukti kepatuhan".

---

### 🔵 PRIORITAS 4 — Dokumentasi & Konsistensi Narasi

#### P4.1 — Tabel Orkestrasi SDLC (struktur-v6 §3.12)
- **File baru:** `docs/sdlc_orchestration_table.md`
- Pemetaan setiap fase SDLC ke node AI Service.

| Fase SDLC | Aktivitas | AI / Node |
|-----------|-----------|-----------|
| Requirements | Deteksi domain webapp | `domain_detection` (LLM) |
| Requirements | Inferensi kebutuhan keamanan | `security_requirement_inference` (LLM + lookup) |
| Design | Klasifikasi arsitektur | `architecture_detection` (LLM + heuristics) |
| Development | Vulnerability scan source code | `vulnerability_scan` (LLM-based SAST) |
| Testing | Generate workflow YAML | `workflow_generation` (deterministic builder) |
| Testing | Validasi YAML | `workflow_validation` (no LLM) |
| Testing | Eksekusi pipeline | `workflow_execution` + `execution_monitor` (no LLM) |
| Testing | Analisis hasil + scoring | `security_analysis` + `risk_assessment` + `compliance_mapper` (LLM) |
| Deployment | Deploy PR | `github_branch_creation` + `pull_request_creation` (no LLM) |
| Monitoring | Continuous security | Pipeline terinstal → trigger ulang scan per push |

#### P4.2 — Update `ai-service/README.md` (jika ada) & `ARCHITECTURE.md`
- Narasi node mengikuti 3 kontribusi utama (sesuai BAB 5 struktur-v6).
- Hapus narasi remediation.
- Tambah narasi `domain_detection` sebagai node ke-7 K1.

#### P4.3 — Update `finding_categories.py` & Dashboard
- Pastikan 4-bucket dashboard tidak lagi memuat kategori yang terkait workflow_config remediation.
- Tambah **domain badge** (mis. "e-commerce", "healthcare") di header hasil analisis.

#### P4.4 — Update Root `README.md`
- **File:** `README.md` (root project)
- Tambah section ringkas tentang migrasi ke struktur-v6 + link ke dokumen ini.

---

## 4. Urutan Eksekusi

```
FASE 1 — Fondasi Domain & Attack Surface (P1.1–P1.2)
   ├─ P1.2  Tambah state fields (domain_* + attack_surfaces)
   └─ P1.1  Buat node domain_detection_node.py + register di graph

FASE 2 — Inference 5-Langkah (P1.3–P1.4)
   ├─ P1.3  Lookup table attack surface
   └─ P1.4  Refactor security_requirement_inference ke 5-langkah

FASE 3 — Domain-Aware Scoring (P1.5)
   └─ P1.5  Update security_analyzer dengan prioritas domain

FASE 4 — Rebuild Graph (P2.1–P2.4)
   ├─ P2.1  Rename compliance_score → security_standards_coverage_score
   ├─ P2.2  Susun ulang pipeline_graph.py (21 node)
   ├─ P2.3  Sinkronkan _invoke_graph_phase di pipeline_service
   └─ P2.4  Update vignette prompts di workflow_generator

FASE 5 — Pembersihan (P3.1–P3.5)
   ├─ P3.1  Hapus workflow_repair dari graph & service
   ├─ P3.2  Hapus 5 node remediation + Flow F
   ├─ P3.3  Hapus workflow_config_issue/remediation
   ├─ P3.4  Wire execution_monitor
   └─ P3.5  Update ARCHITECTURE.md

FASE 6 — Dokumentasi (P4.1–P4.4)
   ├─ P4.1  Buat sdlc_orchestration_table.md
   ├─ P4.2  Update narasi AI service
   ├─ P4.3  Update dashboard & finding_categories
   └─ P4.4  Update root README.md
```

---

## 5. Verifikasi Pasca-Migrasi

### 5.1 Checks
- [ ] Total node di graph = **21** (sesuai struktur-v6 §3.3).
- [ ] `pipeline_service._invoke_graph_phase` line lists → urutan sesuai K1→K2→K3.
- [ ] Tidak ada referensi ke `workflow_repair`, `remediation_*`, `workflow_config_*`, `failure_*` di graph.
- [ ] `detected_domain` terisi untuk semua flow analyze/generate/pipeline.
- [ ] `attack_surfaces` terisi untuk semua flow.
- [ ] `security_standards_coverage_score` exposed di API (bukan `compliance_score`).
- [ ] Metadata disclaimer "indikator, bukan bukti kepatuhan" muncul di response.

### 5.2 Test
- [ ] `pytest ai-service/tests/` → semua test lama pass.
- [ ] Tambah test baru:
  - `test_domain_detection.py` — verifikasi klasifikasi domain & fallback.
  - `test_attack_surface_lookup.py` — verifikasi deterministic mapping.
  - `test_inference_5step.py` — verifikasi alur 5-langkah.
- [ ] Manual smoke test: jalankan `run_repo_analyze` pada repo e-commerce, healthcare, blog → cek `detected_domain` benar.

### 5.3 Kontrak API
Pastikan response `POST /pipeline/repo/analyze` (dan `/generate`, `/repo/pipeline`) menyertakan:
- `detected_domain`, `domain_confidence`, `domain_threats`
- `attack_surfaces`
- `security_standards_coverage_score` (bukan `compliance_score`)

---

## 6. Catatan Penting

1. **TIDAK mengubah** kontribusi skripsi — hanya menyelaraskan prototype dengan struktur-v6.
2. **TIDAK menambah** threat modeling (STRIDE/PASTA) sebagai fitur — hanya konsep di Bab 2.
3. **TIDAK menambah** DAST runtime testing, pipeline versioning, self-healing — masuk BAB 6 saran.
4. **TIDAK menyentuh** `backend/` (Go) kecuali kalau ada perubahan terminologi yang perlu di-propagasi.
5. **DB schema** tidak berubah — `compliance_score` column tetap di DB, hanya API label yang rename.

---

**Status:** DRAFT — menunggu eksekusi bertahap sesuai FASE 1–6.
**Owner:** AI Service (Python + LangGraph).
**Tanggal:** 18 Juni 2026.
