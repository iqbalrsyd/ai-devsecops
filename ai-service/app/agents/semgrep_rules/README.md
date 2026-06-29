# `semgrep_rules/` — Custom Semgrep Rule Registry (Tier 1 + Tier 3 Generator)

> **Audiens**: Penulis skripsi (Bab 3 §3.5, Bab 4 §4.4) · Maintainer pipeline · Reviewer kode
> **Status**: IMPLEMENTASI · Tier 1 statis selalu ON · Tier 3 LLM-generated opt-in via env var
> **Single source of truth (SSoT)**: `llm_generation_config.py` + `scan_directives.py` (di folder `app/agents/`)
> **Dokumentasi cross-reference**:
> - `../../../docs/README-SEMGREP-TIERS.md` — arsitektur 2-tier + 10-step eksekusi
> - `../../../docs/domain-rules-table.md` — tabel perbandingan rule per domain
> - `../../../docs/README-DOMAIN-AWARE-PIPELINE.md` — pipeline domain-aware Bab 4 §4.4
> - `../../../../naskah/rekomendasi-judul.md` — judul baru + rasionalisasi 3-domain
> - `../../../../PROMPT-ENGINEERING-BAB3.md` — prompt engineering Bab 3

---

## Daftar Isi

1. [Posisi Folder di Pipeline 4 Tahap](#1-posisi-folder-di-pipeline-4-tahap)
2. [Peta File & Tanggung Jawab](#2-peta-file--tanggung-jawab)
3. [Dua Tier Aturan Semgrep](#3-dua-tier-aturan-semgrep)
4. [Domain yang Didukung (v9.4 — 3 Domain & 2 Arch)](#4-domain-yang-didukung-v94--3-domain--2-arch)
5. [Knowledge Base Ilmiah (CWE + OWASP Hybrid)](#5-knowledge-base-ilmiah-cwe--owasp-hybrid)
6. [Konvensi ID Rule, Severity, dan Filename](#6-konvensi-id-rule-severity-dan-filename)
7. [Generator Pipeline (K1.5) — Cara Kerja](#7-generator-pipeline-k15--cara-kerja)
8. [Konfigurasi Env Var](#8-konfigurasi-env-var)
9. [Batasan Penelitian (R5 Naskah)](#9-batasan-penelitian-r5-naskah)
10. [Cara Menambah Domain Baru (TODO/Opsi)](#10-cara-menambah-domain-baru-todoopsi)
11. [Validasi, Cache, dan Mitigasi Risiko](#11-validasi-cache-dan-mitigasi-risiko)
12. [Referensi Silang Naskah & Kode](#12-referensi-silang-naskah--kode)
13. [Lampiran A: Tier 1 — File Statis per Domain](#lampiran-a-tier-1--file-statis-per-domain)
14. [Lampiran B: Tier 3 — Aturan Wajib](#lampiran-b-tier-3--aturan-wajib)

---

## 1. Posisi Folder di Pipeline 4 Tahap

Folder ini adalah **Tahap 1.5 (K1.5)** dan konsumen langsung di **Tahap 2 (K2)** dan **Tahap 3 (K3)** pada pipeline 18-node LangGraph (lihat `struktur-v9.md`).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TAHAP 1: K1 — Repository Context Analysis (6 node)                       │
│   repository_connection → repository_scan → technology_detection →        │
│   architecture_detection → deployment_detection → domain_detection       │
│                              ↓                                            │
│  TAHAP 1.5: K1.5 — semgrep_llm_generation (KONDISIONAL, opt-in)         │
│   Input:  state.detected_domain, domain_threats[], primary_language,      │
│           frameworks[]                                                   │
│   Output: state.llm_generated_rules[], state.llm_generated_rules_filename │
│   Konsumen file di folder ini:                                            │
│     • domain_knowledge_base.yml (prompt konteks domain)                   │
│     • general_knowledge_base.yml (CWE lintas-domain)                      │
│     • llm_generation_prompt.py (template prompt)                          │
│     • llm_generation_config.py (knobs: domain scope, confidence, dll)     │
│     • index.yml (registry rule statis Tier 1)                             │
│                              ↓                                            │
│  TAHAP 2: K2 — Security Coverage Inference (2 node)                      │
│   coverage_inference → pipeline_augmentation                               │
│   (atau security_requirement_inference di versi lama)                     │
│     → baca llm_generated_rules_filename                                   │
│     → build_scan_directives(llm_rule_suggestions=[filename])              │
│     → emit state.inferred_security_needs.scan_directives                  │
│                              ↓                                            │
│  TAHAP 3: K3 — Pipeline Generation + Deployment                           │
│   workflow_generation: emit SAST job dengan --config=.semgrep/<file>.yml   │
│   pull_request_creation: commit .semgrep/<domain>-combined-<hash>.yml     │
│   workflow_execution:                                                     │
│     step 1: Show enabled rule files                                        │
│     step 2: Validate custom Semgrep rules (semgrep --validate)            │
│     step 3: Run semgrep ci --config=...                                    │
│                              ↓                                            │
│  TAHAP 4: K4 — Scoring & Reporting (tidak consume folder ini)             │
└──────────────────────────────────────────────────────────────────────────┘
```

> **Ringkas**: folder ini adalah **registry rule statis** (Tier 1) sekaligus **knowledge base + generator** (Tier 3). Folder ini **tidak** di-trigger di Tahap 4 (scoring); ia hanya menyiapkan aturan SAST yang akan dipakai di Tahap 3.

---

## 2. Peta File & Tanggung Jawab

| File | Tipe | Tier | Fungsi | Dipakai di node | Kapan diubah |
|------|------|------|--------|-----------------|---------------|
| `index.yml` | YAML | Tier 1 | Registry statis: domain → daftar file rule `.yml` | `semgrep_llm_generator_node`, `scan_directives.py` | Tambah/hapus domain |
| `domain_knowledge_base.yml` | YAML | Tier 3 (KB) | Knowledge base CWE + ancaman + rule_outlines per domain (e-commerce, blog, iot) | `llm_generation_prompt.build_prompt()` (via prompt builder) | Tambah domain / revisi ancaman |
| `general_knowledge_base.yml` | YAML | Tier 3 (KB) | CWE lintas-domain (BOLA, mass assignment, SSRF, CORS, rate limit) | `pattern_inference_node._load_knowledge_base()` (K2.3) | Tambah CWE universal |
| `ecommerce.yml` | Semgrep YAML | Tier 1 | Rule statis e-commerce: BOLA cart, price tampering, CSRF, JWT, PCI-DSS | `pull_request_creation_node` (Tier 1 only) | Tambah rule statis |
| `blog-csp.yml` | Semgrep YAML | Tier 1 | Rule statis blog: XSS, markdown sanitization, CSP, open redirect, IDOR post | `pull_request_creation_node` | Tambah rule statis |
| `iot-mqtt.yml` | Semgrep YAML | Tier 1 | Rule statis IoT: MQTT TLS, default creds, firmware signature, telnet | `pull_request_creation_node` | Tambah rule statis |
| `owasp-api.yml` | Semgrep YAML | Tier 1 (baseline) | Rule statis OWASP API Security Top 10 2023 — selalu aktif untuk semua domain | `pull_request_creation_node` | Update OWASP API |
| `llm_generation_config.py` | Python | Tier 3 (config) | Knob fitur: `ENABLE_LLM_GENERATED_RULES`, scope domain, `MIN_LLM_CONFIDENCE`, `MAX_RULES_PER_DOMAIN`, naming, cache key | `semgrep_llm_generator_node` | Naikin/turun confidence cap |
| `llm_generation_prompt.py` | Python | Tier 3 (prompt) | System + user prompt template; berisi `TIER1_RULE_IDS` dan `RECOMMENDED_COVERAGE` per domain | `semgrep_llm_generator_node` | Tambah hint kategori rule |

### 2.1 Aturan Hierarki File

1. **`*.yml` rule statis** (Tier 1): **tidak boleh** diedit sembarangan — setiap rule akan dipakai di SEMUA pipeline run untuk domain tersebut. Salah syntax → PR `pull_request_creation_node` gagal.
2. **`domain_knowledge_base.yml`** adalah sumber CWE yang **ilmiah dan referable** (MITRE CWE + OWASP + jurnal spesifik domain). Perubahan di sini = perubahan kontrak domain.
3. **`llm_generation_config.py`** adalah **knob SSoT** untuk Tier 3. Naikin `MAX_RULES_PER_DOMAIN` = PR makin rame.
4. **`index.yml`** dan **`scan_directives.py`** di folder parent HARUS tetap sinkron. Setiap domain baru = update **dua-duanya**.

---

## 3. Dua Tier Aturan Semgrep

Sesuai keputusan desain final (lihat `README-SEMGREP-TIERS.md` §1): **HANYA 2 tier**. Tidak ada sub-type payment processor rules.

| Aspek | Tier 1 — Statis | Tier 3 — LLM-Generated |
|------|------------------|-------------------------|
| **Sumber** | File `.yml` di folder ini | Output LLM dari `llm_generation_prompt.py` |
| **Siapa yang tulis** | Maintainer (manual curate) | LLM dengan prompt terstruktur |
| **Kapan ON** | Selalu aktif untuk domain terkait | Hanya jika `ENABLE_LLM_GENERATED_RULES=true` |
| **Confidence control** | n/a (sudah dikurasi) | `MIN_LLM_CONFIDENCE` (default 0.7) |
| **Max rule per run** | n/a (semua dipakai) | `MAX_RULES_PER_DOMAIN` (default 8) |
| **Severity default** | Bervariasi (WARNING/ERROR) | Selalu `WARNING` di first gen (mencegah break build) |
| **Validasi** | Linting di Code Review | `semgrep --validate` di workflow CI step |
| **Cache** | n/a | SHA-256 dari `(domain, threats, language, frameworks)` |
| **Storage** | File di folder ini | Merge dengan Tier 1 → `.semgrep/<domain>-combined-<hash>.yml` di repo target |
| **Onboarding cost** | Tinggi (manual review) | Rendah (auto) |
| **Risiko utama** | Outdated (perlu revisi manual) | LLM hallucinate syntax Semgrep |

### 3.1 Tabel Perbedaan Per Domain (3 domain aktif)

> Selaras dengan `scan_directives._DOMAIN_RULES` + `llm_generation_config.LLM_GENERATION_DOMAINS`.

| Domain | Tier 1 Statis (selalu ON) | Tier 3 LLM (opt-in) | File merged di `.semgrep/` | Domain-specific Job | Skip Jobs |
|--------|---------------------------|---------------------|----------------------------|---------------------|-----------|
| **e-commerce** | `ecommerce.yml` + `owasp-api.yml` | ON — BOLA cart, price tampering, mass assignment, webhook forgery, PCI-DSS, JWT expiry, currency float | `e-commerce-combined-<hash>.yml` | `pci-dss` | — |
| **blog** | `blog-csp.yml` + `owasp-api.yml` | ON — XSS comment, file upload bypass, content injection md, open redirect, IDOR post edit | `blog-combined-<hash>.yml` | `csp-headers` | `container-scan`, `idor`, `ssrf`, `jwt`, `rate-limiting` |
| **iot** | `iot-mqtt.yml` + `owasp-api.yml` | ON — device auth bypass, MQTT no-encrypt, firmware tamper, default creds, debug interface | `iot-combined-<hash>.yml` | `mqtt-security` | — |
| **general** | `owasp-api.yml` saja | **OFF** — tidak di-generate | `owasp-api.yml` saja | — | `pci-dss`, `csp-headers`, `mqtt-security` |

---

## 4. Domain yang Didukung (v9.4 — 3 Domain & 2 Arch)

Pipeline ini **secara sadar** membatasi dukungan hanya pada **3 domain** sesuai naskah `rekomendasi-judul.md` R2.2 (pengerucutan dari 7 → 3 domain) dan R2.1 (pengerucutan arsitektur dari 6 → 2 tipe):

```
e-commerce   ──┐
blog          ──┼── 3 domain aktif (Tier 1 + Tier 3)
iot           ──┘
general       ──── fallback (Tier 1 only, Tier 3 OFF)
```

### 4.1 Alasan Pengurangan Scope (v9.4 — Sinkron Naskah)

Domain **fintech, healthcare, education** sudah dihapus dari sistem pada revisi v9.4. Pertimbangannya (lihat naskah R2.2 + T3):

1. **Bukti empiris**: setiap domain memiliki profil ancaman yang berbeda (`meneely2013patch`). ENISA Threat Landscape 2024 juga mencatat variasi ancaman antar sektor.
2. **Overlap profil ancaman**: domain fintech/healthcare/education overlap dengan e-commerce/blog — sehingga pengerucutan tidak kehilangan variasi ancaman.
3. **Keterbatasan dataset**: dataset repositori publik yang memenuhi kriteria seleksi sangat terbatas untuk domain yang dihapus. Dataset total berkurang dari 40 → 15-18 repositori (lihat B5 naskah).
4. **Justifikasi akademis**: `matter2025context` (systematic review 75 studi context-aware security 2013-2024) mendukung pendekatan context-aware — tapi tidak mensyaratkan cakupan domain yang luas.

> **Konsekuensi**: AI agent **dilarang berhalusinasi** keluar dari 3 domain ini. Logic `is_domain_eligible()` di `llm_generation_config.py` adalah penjaganya.

### 4.2 Arsitektur yang Didukung (2 Arch — R2.1)

| Arsitektur | Contoh | Pengaruh pada SAST ruleset |
|------------|--------|-----------------------------|
| **Monolitik Tradisional** | Express monolith, single Dockerfile | Single SAST job, no matrix |
| **Modular Monolith** | Per-service Dockerfiles, API gateway, K8s manifests | Matrix SAST per-service, `per_service_sast`, `service_mesh_audit` |

> Arsitektur **Microservices murni, Service-Based, Event-Driven, Serverless** di-skip (lihat naskah R2.1 — pengerucutan dari 6 → 2 tipe). Alasan: microservices murni relatif jarang di repositori open-source JS/TS, dan dampaknya terhadap isolasi pemindaian SAST/SCA serupa dengan modular monolith.

---

## 5. Knowledge Base Ilmiah (CWE + OWASP Hybrid)

`domain_knowledge_base.yml` adalah **landasan ilmiah** Tier 3 — setiap entri CWE-nya dapat dirujuk ke taksonomi MITRE + OWASP + jurnal spesifik domain. Pendekatan hybrid sesuai naskah R4.2:

| Lapisan | Standar | Peran |
|---------|---------|-------|
| **Makro** (kategori risiko) | OWASP Top 10, OWASP API Top 10, OWASP IoT Top 10 | Payung kategori risiko tingkat tinggi |
| **Mikro** (aturan teknis) | CWE (Common Weakness Enumeration) | Acuan teknis untuk ruleset Semgrep |
| **Empiris** (bukti lapangan) | `meneely2013patch`, ENISA Threat Landscape 2024 | Variasi ancaman antar domain |
| **Akademis** (legitimasi) | `matter2025context` (systematic review 75 studi) | Fondasi context-aware security |
| **Spesifik** (jurnal) | `taherdoost2022payment`, `gupta2017sql`, `gupta2017xss`, `calzavara2020csp` | Justifikasi per domain |

### 5.1 E-commerce (20 CWE)

| CWE | Judul | Justifikasi (naskah R3) | Referensi |
|-----|-------|--------------------------|-----------|
| CWE-79 | Cross-site Scripting | OWASP A03:2021 — XSS di product review/comment | OWASP Top 10:2021 |
| CWE-89 | SQL Injection | OWASP A03:2021 — SQLi di /checkout, /orders | `gupta2017sql` |
| CWE-352 | CSRF | OWASP A01:2021 — CSRF di cart/checkout | OWASP Top 10:2021 |
| CWE-434 | Unrestricted Upload | File upload tanpa ext/MIME check | OWASP Top 10:2021 |
| CWE-602 | Client-Side Security | Trust on client validation | — |
| CWE-639 | BOLA / IDOR | OWASP API1:2023 — cart/order ownership | OWASP API Top 10:2023 |
| CWE-915 | Mass Assignment | OWASP API6:2023 — `Order.create({...req.body})` | OWASP API Top 10:2023 |
| CWE-532 | Sensitive Info in Log | PCI-DSS 3.4 — PAN/CVV in logs | PCI-DSS v4.0 |
| CWE-798 | Hardcoded Credentials | Stripe/PayPal/AWS keys | `taherdoost2022payment` |
| CWE-312 | Cleartext Storage | PCI-DSS 3.4 — PAN at-rest | PCI-DSS v4.0 |
| CWE-319 | Cleartext Transmission | HTTP vs HTTPS, no HSTS | — |
| CWE-327 | Broken Crypto Algorithm | MD5/SHA1 password, weak TLS | — |
| **CWE-918** 🆕 | Server-Side Request Forgery | Webhook URL / image fetch dari user input | OWASP API7:2023 |
| **CWE-770** 🆕 | No Rate Limit | /login, /checkout tanpa rate-limit | OWASP API4:2023 |
| **CWE-862** 🆕 | Missing Authorization | Endpoint tanpa middleware auth | OWASP API2:2023 |
| **CWE-345** 🆕 | Webhook Signature Verify | Webhook tanpa signature check | OWASP API8:2023 |
| **CWE-754** 🆕 | Idempotency Key | Payment tanpa idempotency | OWASP API4:2023 |
| **CWE-307** 🆕 | Brute Force Protection | /login tanpa rate-limit / lockout | OWASP API2:2023 |
| **CWE-209** 🆕 | Error Exposure | 500 page expose stack trace | OWASP API8:2023 |
| **CWE-613** 🆕 | JWT Expiry | JWT tanpa expiresIn | OWASP API2:2023 |

**Kategori McConnell**: Internet Systems (public). **Fokus mitigasi**: serangan eksternal/injeksi (SQLi, XSS), integritas transaksi, kebocoran API key payment gateway.

### 5.2 Blog (9 CWE)

| CWE | Judul | Justifikasi (naskah R3) | Referensi |
|-----|-------|--------------------------|-----------|
| CWE-1021 | Improper UI Layer Restriction | Clickjacking — butuh CSP frame-ancestors | `calzavara2020csp` |
| CWE-79 | XSS | Stored XSS di comment/markdown | `gupta2017xss` |
| CWE-601 | Open Redirect | `res.redirect(req.query.next)` | OWASP Top 10:2021 |
| CWE-434 | Unrestricted Upload | Image upload bypass → web shell | OWASP Top 10:2021 |
| **CWE-352** 🆕 | CSRF | Form submit komentar tanpa token | OWASP A01:2021 |
| **CWE-862** 🆕 | Missing Authorization | Comment edit tanpa ownership | OWASP A01:2021 |
| **CWE-770** 🆕 | No Rate Limit | Spam komentar | OWASP A04:2021 |
| **CWE-209** 🆕 | Error Exposure | Stack trace di 500 page | OWASP A05:2021 |
| **CWE-639** 🆕 | BOLA post/comment edit | Overlap dengan idor-post-edit | OWASP A01:2021 |

**Kategori McConnell**: Internet/Business (hybrid). **Fokus mitigasi**: Stored XSS, file upload, CSP headers, sanitasi input konten publik.

### 5.3 IoT (12 CWE)

| CWE | Judul | Justifikasi (naskah R3) | Referensi |
|-----|-------|--------------------------|-----------|
| CWE-319 | Cleartext Transmission | MQTT over `mqtt://` | OWASP IoT I3 |
| CWE-798 | Hardcoded Credentials | Default MQTT creds (admin/admin) | OWASP IoT I1 |
| CWE-295 | Improper Cert Validation | `tls_insecure_set(True)` | OWASP IoT I2 |
| CWE-22 | Path Traversal | Firmware path dari user input | — |
| CWE-311 | Missing Encryption | Telemetry tanpa TLS | OWASP IoT I5 |
| CWE-287 | Improper Authentication | Device ID sebagai satu-satunya credential | — |
| CWE-668 | Exposure to Wrong Sphere | Broker di 0.0.0.0:1883 | OWASP IoT I3 |
| CWE-494 | Download w/o Integrity Check | Firmware OTA tanpa signature | OWASP IoT I10 |
| **CWE-78** 🆕 | OS Command Injection | `os.system(sensorData)` di firmware | OWASP IoT I3 |
| **CWE-787** 🆕 | Out-of-bounds Write | Buffer overflow di C/C++ parser | OWASP IoT I3 |
| **CWE-125** 🆕 | Out-of-bounds Read | `arr[i]` tanpa bounds check | OWASP IoT I3 |
| **CWE-20** 🆕 | Improper Input Validation | Root cause banyak IoT bug | CWE VIEW 1357 |

**Kategori McConnell**: Internet/Business (hybrid). **Fokus mitigasi**: protokol M2M (MQTT/CoAP), firmware credentials, device authentication.

### 5.4 CWE Lintas-Domain (di `general_knowledge_base.yml`)

| CWE | Judul | Digunakan untuk |
|-----|-------|-----------------|
| CWE-639 | BOLA / IDOR | Semua API |
| CWE-915 | Mass Assignment | Semua API dengan ORM |
| CWE-213 | Excessive Data Exposure | Response API |
| CWE-770 | No Rate Limit / Pagination | Semua endpoint publik |
| CWE-285 | Function-Level Auth Missing | RBAC check |
| CWE-918 | SSRF | Outbound HTTP dari user input |
| CWE-942 | CORS Misconfig | API publik |
| CWE-209 | Stack Trace Exposure | Error handler |
| CWE-916 | Weak bcrypt Rounds | Password storage |
| CWE-307 | No Rate Limit on Login | Auth endpoint |

### 5.5 Konsistensi dengan Naskah

| Sumber Naskah | Merujuk ke sini |
|---------------|-----------------|
| `rekomendasi-judul.md` R2.1 (pengerucutan arsitektur 6→2) | §4.2 (Tabel 2 Arch) |
| `rekomendasi-judul.md` R2.2 (pengerucutan domain 7→3) | §4.1, §5.1-5.3 |
| `rekomendasi-judul.md` R3 (referensi jurnal spesifik domain) | §5 (kolom Referensi) |
| `rekomendasi-judul.md` R4.2 (justifikasi 15 coverages) | §5 (header Hybrid) |
| `struktur-v9.md` §3 (Bab 3) | 3 domain, 2 arch, 20/9/12 CWE selection (v9.5) |
| `PROMPT-ENGINEERING-BAB3.md` §3.5.2 | Domain-specific control prioritization per domain |
| `domain-aware-pipeline.md` §E (Bab 4 §4.4) | Severity elevation table per domain |
| `domain-rules-table.md` | Tier 1 + Tier 3 mapping |

---

## 6. Konvensi ID Rule, Severity, dan Filename

### 6.1 Rule ID Convention

| Tier | Format | Contoh |
|------|--------|--------|
| Tier 1 (statis) | Bebas, sesuai konvensi Semgrep | `ecommerce-pci-card-data-in-logs` |
| Tier 3 (LLM) | `{domain}-custom-{slug}` | `ecommerce-custom-price-tampering` |

**Aturan Tier 3** (wajib, di-enforce oleh `llm_generation_config.build_rule_id()`):
- Prefix: `{domain}-custom-`
- Slug: lowercase, alphanumeric + hyphen, max 40 char
- Contoh valid: `blog-custom-markdown-no-sanitize`
- Contoh invalid: `Blog_Custom.XSS`, `ecommerce-`, `custom-rule` (tanpa prefix domain)

### 6.2 Severity

| Tier | Boleh | Default |
|------|-------|---------|
| Tier 1 | INFO / WARNING / ERROR | per-rule (ditetapkan maintainer) |
| Tier 3 | INFO / WARNING **only** | `WARNING` (lihat `DEFAULT_LLM_RULE_SEVERITY`) |

> **Kenapa Tier 3 default WARNING?** Agar LLM-generated rule **tidak break build** di first run. Maintainer bisa promote ke `ERROR` setelah review PR.

### 6.3 Filename Pattern

Tier 1 + Tier 3 untuk 1 domain digabung jadi **SATU file** di `.semgrep/`:

```
<domain>-combined-<8-char-hash>.yml
```

Contoh:
```
.semgrep/e-commerce-combined-a1b2c3d4.yml
.semgrep/blog-combined-9e8f7g6h.yml
.semgrep/iot-combined-0x1y2z3w4.yml
```

Hash 8 char dari SHA-256(`(domain, threats, primary_language, frameworks)`) → diff minimal antar run.

---

## 7. Generator Pipeline (K1.5) — Cara Kerja

### 7.1 Sequence End-to-End

```
┌─────────────────────────────────────────────────────────────────────┐
│  K1 — domain_detection_node                                         │
│   output: state.detected_domain = "e-commerce"                      │
│           state.domain_threats = ["SQLi checkout", "BOLA cart",    │
│                                     "Stripe key hardcoded", ...]    │
│           state.detected_technologies.primary_language = "javascript"│
│           state.detected_technologies.frameworks = ["express"]      │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│  K1.5 — semgrep_llm_generation_node (KONDISIONAL)                   │
│   ┌─ is_domain_eligible("e-commerce")                               │
│   │   → cek ENABLE_LLM_GENERATED_RULES &&                           │
│   │     domain ∈ LLM_GENERATION_DOMAINS (3 domain aktif)            │
│   │   → True: lanjut, False: skip node, state kosong                │
│   ├─ cache_key = SHA256(domain, threats, lang, frameworks)          │
│   ├─ cache_get(key) → kalau hit, return cached                      │
│   ├─ cache miss:                                                    │
│   │   ├─ build_prompt(                                              │
│   │   │     domain="e-commerce",                                    │
│   │   │     domain_threats=[...],                                   │
│   │   │     primary_language="javascript",                          │
│   │   │     frameworks=["express"],                                 │
│   │   │     max_rules=MAX_RULES_PER_DOMAIN (8),                     │
│   │   │     min_confidence=MIN_LLM_CONFIDENCE (0.7)                 │
│   │   │   ) → return (system_prompt, user_prompt)                   │
│   │   ├─ LLM call dengan persona "Senior AppSec engineer"           │
│   │   ├─ parse_llm_response(content) → list[dict]                   │
│   │   ├─ validate per-rule:                                         │
│   │   │   ├─ id startswith "{domain}-custom-"                       │
│   │   │   ├─ severity in {INFO, WARNING}                            │
│   │   │   ├─ languages ⊆ [primary_language, extra_languages]        │
│   │   │   ├─ metadata.cwe valid "CWE-NNN"                           │
│   │   │   └─ confidence >= MIN_LLM_CONFIDENCE                      │
│   │   ├─ drop invalid rules                                         │
│   │   └─ cache_put(key, rules)                                      │
│   └─ output: state.llm_generated_rules = [...]                      │
│            state.llm_generated_rules_filename =                     │
│              "e-commerce-combined-a1b2c3d4.yml"                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│  K2 — security_requirement_inference_node                           │
│   baca state.llm_generated_rules_filename                           │
│   → build_scan_directives(llm_rule_suggestions=[filename])          │
│   output: state.inferred_security_needs.scan_directives             │
│           = {                                                       │
│               sast_ruleset: [                                       │
│                 "p/owasp-top-ten",       # Layer 1                   │
│                 "owasp-api.yml",         # Layer 1 (custom)         │
│                 "ecommerce.yml",         # Layer 2                   │
│                 "e-commerce-combined-a1b2c3d4.yml",  # Layer 4 (T3)  │
│               ],                                                    │
│               sast_skip_rules: ["experimental", "audit"]             │
│             }                                                        │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│  K3 — workflow_generation + pull_request_creation                   │
│   workflow_generation:                                              │
│     emit job `sast` dengan --config=.semgrep/<file>.yml (×N file)   │
│   pull_request_creation:                                            │
│     ├─ baca static .yml files (Tier 1) dari folder ini              │
│     ├─ baca state.llm_generated_rules (Tier 3)                      │
│     ├─ extract rules: [] dari masing-masing                          │
│     ├─ gabung jadi 1 dokumen YAML                                    │
│     └─ commit ke .semgrep/<domain>-combined-<hash>.yml              │
│   workflow_execution:                                               │
│     step 1: Show enabled rule files                                  │
│     step 2: semgrep --validate --config=.semgrep/<file>              │
│     step 3: semgrep ci --config=... --sarif                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Prompt Snapshot (lihat `llm_generation_prompt.py`)

System prompt:
```
You are a senior application security engineer who writes custom Semgrep
rules for a specific web application domain.

Methodological grounding (per skripsi Bab 2 Tinjauan Pustaka):
  * Domain context matters — vulnerabilities cluster by domain
    (meneely2013patch). Adapt coverage accordingly.
  * Context-aware security increases detection accuracy and reduces
    false positives vs one-size-fits-all (matter2025context).
  * Hybrid OWASP (macro) + CWE (micro) is the standard for SAST coverage
    mapping (naskah R4.2).

Supported domains ONLY (v9.4 — sinkron naskah R2.2):
  e-commerce, blog, iot. Do NOT invent rules for fintech, healthcare,
  education, or any other domain not in the input.

Hard constraints (MUST follow):
  1. Every rule id MUST start with the prefix `{domain}-custom-` ...
  2. Every rule severity MUST be INFO or WARNING. Do NOT emit ERROR ...
  3. Every rule MUST declare a languages list ...
  ...
```

User prompt template di-inject dengan: `domain`, `primary_language`, `frameworks`, `domain_threats`, `tier1_rule_ids` (supaya LLM tidak duplikasi), `recommended_coverage` (hybrid OWASP + CWE + jurnal spesifik domain).

---

## 8. Konfigurasi Env Var

Semua knob Tier 3 di `llm_generation_config.py`, baca dari env var:

| Env var | Default | Fungsi |
|---------|---------|--------|
| `ENABLE_LLM_GENERATED_RULES` | `false` | Master switch Tier 3 |
| `MIN_LLM_CONFIDENCE` | `0.7` | Threshold confidence rule yang di-keep |
| `MAX_RULES_PER_DOMAIN` | `8` | Cap rule LLM per pipeline run |

**Contoh `.env` lokal:**
```bash
# Opt-in Tier 3
ENABLE_LLM_GENERATED_RULES=true

# Naikin confidence threshold (lebih ketat)
MIN_LLM_CONFIDENCE=0.8

# Tambah headroom rule
MAX_RULES_PER_DOMAIN=10
```

> Tier 1 **tidak punya env var** — selalu ON (statis di code).

---

## 9. Batasan Penelitian (R5 Naskah)

Bagian ini mendokumentasikan batasan yang **langsung relevan** dengan folder `semgrep_rules/`. Teks lengkap batasan ada di naskah `rekomendasi-judul.md` R5 (8 butir B1–B8). Ringkasan yang relevan di sini:

| No | Batasan | Implikasi ke folder ini |
|----|---------|--------------------------|
| **B1** | Hanya repositori GitHub publik | n/a (folder ini tidak tergantung sumber repo) |
| **B2** | Pipeline khusus GitHub Actions YAML | File rule dipakai sebagai `--config` di job SAST |
| **B3** | Tidak sentuh deployment produksi | Folder ini hanya siapkan rule, tidak trigger deploy |
| **B4** | Evaluasi dari Semgrep, Trivy, Gitleaks | **Semgrep** memakai rule dari folder ini |
| **B5** | 15-18 repositori, 3 domain (e-commerce, blog, IoT) | **Justifikasi utama** kenapa folder ini hanya support 3 domain |
| **B6** | LLM Minimax-m3 via OpenCode (ganti Kimi 2.7) | Tier 3 generation prompt di sini kompatibel dengan LLM tersebut |
| **B7** | Arsitektur bukan variabel eksperimen utama | Arsitektur hanya konteks klasifikasi, tidak diubah-ubah |
| **B8** | Tools terbatas: Semgrep, Trivy, Gitleaks | **Hanya Semgrep** yang memakai rule dari folder ini |

> **Keterkaitan B5 ↔ folder ini**: B5 membatasi dataset ke 3 domain. Folder `semgrep_rules/` v9.4 menghapus domain fintech/healthcare/education dari `domain_knowledge_base.yml`, `general_knowledge_base.yml`, `llm_generation_config.LLM_GENERATION_DOMAINS`, dan `llm_generation_prompt.RECOMMENDED_COVERAGE` agar konsisten.

---

## 10. Cara Menambah Domain Baru (TODO/Opsi)

> **Status saat ini**: 3 domain aktif. Penambahan domain ke-4 harus melalui revisi mayor + justifikasi di naskah (saat ini pengerucutan sengaja dilakukan).

Jika di masa depan ingin menambah domain (mis. `healthcare`):

1. **Revisi naskah**: tambah justifikasi di `rekomendasi-judul.md` R2.2 — kenapa dataset diperluas, apakah profile ancaman baru benar-benar berbeda.

2. **Tambah ke `LLM_GENERATION_DOMAINS`** di `llm_generation_config.py`:
   ```python
   LLM_GENERATION_DOMAINS: frozenset[str] = frozenset({
       "e-commerce", "blog", "iot", "healthcare",  # ← tambah
   })
   ```

3. **Tambah section di `domain_knowledge_base.yml`** (template lihat 3 domain aktif):
   ```yaml
   domains:
     healthcare:
       cwe_focus: [...]
       threats: [...]
       rule_outlines: [...]
       frameworks: [...]
       skip_for: [...]
   ```

4. **Tambah file rule Tier 1** baru: `healthcare.yml` (atau nama domain-spesifik).

5. **Update `index.yml`**:
   ```yaml
   domain_rules:
     healthcare:
       - healthcare.yml
   ```

6. **Update `scan_directives.py`** (di folder parent): tambah `_DOMAIN_RULES["healthcare"]`, `_DOMAIN_SKIP_JOBS["healthcare"]`, dst.

7. **Tambah `TIER1_RULE_IDS["healthcare"]`** dan **`RECOMMENDED_COVERAGE["healthcare"]`** di `llm_generation_prompt.py`.

8. **Validasi**: jalankan pipeline pada 1 repo healthcare → cek Tier 1 file dipakai, Tier 3 rule di-generate sesuai KB.

9. **Update `domain-rules-table.md`** dan README ini.

> Setiap langkah di atas = PR terpisah agar bisa di-review. **Jangan lupa update naskah dulu** sebelum menambah domain.

---

## 11. Validasi, Cache, dan Mitigasi Risiko

### 11.1 Validasi Berlapis

| Layer | Mekanisme | Tujuan |
|-------|-----------|--------|
| LLM output parse | `parse_llm_response()` di `llm_generation_prompt.py` | Strip markdown fence, `json.loads`, return `rules[]` |
| Per-rule validate | `semgrep_llm_generator_node` | Cek ID prefix, severity ∈ allowed, languages valid, CWE format, confidence ≥ threshold |
| Semgrep syntax | `semgrep --validate --config=.semgrep/<file>` di workflow CI | Tangkap syntax error Semgrep asli |
| Workflow YAML | `actionlint` + structural check | Workflow GitHub Actions valid |

### 11.2 Cache

- **Backend**: in-process dict (`_CACHE` di `llm_generation_config.py`)
- **Lifetime**: selama proses `ai-service` hidup
- **Key**: SHA-256 dari `(domain, domain_threats, primary_language, frameworks)` — serialized sebagai compact JSON dengan sort_keys
- **Tidak persisted** ke disk/DB (sengaja, untuk hindari stale rules saat LLM upgrade)
- **Test helper**: `cache_clear()` di-test

### 11.3 Mitigasi Risiko

| Risiko | Mitigasi |
|--------|----------|
| LLM hallucinate Semgrep syntax | `semgrep --validate` di workflow CI step (`continue-on-error: true`) |
| Token cost naik | Cache by SHA-256 → cache hit hemat 100% token |
| PR noisy (file `.yml` baru tiap run) | Filename include 8-char hash → content sama = filename sama = no diff |
| LLM ngaco (confidence rendah) | `MIN_LLM_CONFIDENCE = 0.7` → drop rule, log di state |
| Severity ERROR break build | `DEFAULT_LLM_RULE_SEVERITY = "WARNING"` di first gen |
| Domain keluar dari 3 scope | `LLM_GENERATION_DOMAINS` frozenset → `is_domain_eligible()` return False |
| Tier 3 nyala tapi domain `general` | `is_domain_eligible("general")` → False (sengaja dikecualikan) |
| Coverage tidak sesuai ancaman domain | CWE + OWASP + jurnal spesifik domain (R3 + R4.2) di `domain_knowledge_base.yml` |

---

## 12. Referensi Silang Naskah & Kode

### 12.1 Ke Naskah Skripsi

| Elemen naskah | File/line | Disinkronkan ke |
|---------------|-----------|-----------------|
| Judul skripsi (Rekomendasi 1) | `rekomendasi-judul.md` line 22-31 | Header README ini |
| R2.1 — Pengerucutan arsitektur 6→2 | `rekomendasi-judul.md` line 240-246 | §4.2 README |
| R2.2 — Pengerucutan domain 7→3 | `rekomendasi-judul.md` line 247-258 | §4.1, §5.1-5.3 README |
| R3 — Referensi jurnal spesifik domain | `rekomendasi-judul.md` line 262-274 | §5 (kolom Referensi) |
| R4.1 — Perbedaan e-commerce vs blog | `rekomendasi-judul.md` line 282-296 | §3.1 README (konteks) |
| R4.2 — Justifikasi 15 coverages (OWASP+CWE) | `rekomendasi-judul.md` line 297-320 | §5 (header Hybrid) README |
| R5 — Batasan Penelitian B1-B8 | `rekomendasi-judul.md` line 743-825 | §9 README |
| Sitasi baru (matter2025context, dst) | `rekomendasi-judul.md` line 327-353 | §5 README (kolom Akademis) |
| T1-T5 — Teks yang perlu ditambahkan | `rekomendasi-judul.md` line 357-534 | (Untuk naskah Bab 2/3/4) |
| Bab 3 §3.5.2 (Prompt engineering domain) | `PROMPT-ENGINEERING-BAB3.md` §3.5 | §7 README |
| Bab 3 §3.6.3 (Domain-aware severity) | `domain-aware-pipeline.md` §E | (Konteks, lihat `domain_priority.py`) |
| Bab 4 §4.4 (Domain-aware pipeline) | `domain-aware-pipeline.md` §C, `domain-rules-table.md` | §3.1 README |
| Justifikasi CWE selection | Section 5 (domain_knowledge_base.yml header) | §5 README |

### 12.2 Ke Kode Pipeline

| Komponen kode | Path |
|---------------|------|
| Domain detection | `app/agents/nodes/domain_detection_node.py:251-279` |
| LLM generator (K1.5) | `app/agents/nodes/semgrep_llm_generator_node.py` |
| Pipeline graph (insert K1.5) | `app/agents/pipeline_graph.py` |
| Scan directives (Layer 1-4) | `app/agents/scan_directives.py` |
| Inference consumer | `app/agents/nodes/security_requirement_inference_node.py` |
| Workflow generator (validate step) | `app/agents/nodes/workflow_generator.py` |
| PR creation (merge Tier 1+3) | `app/agents/nodes/pull_request_creation_node.py` |
| Domain priority (post-process) | `app/agents/domain_priority.py:30-120` |
| Attack surface lookup | `app/agents/attack_surface_lookup.py:18-58` |
| State (T3 fields) | `app/agents/pipeline_state.py` (fields: `llm_generated_rules`, `llm_generated_rules_cache_key`, `llm_generated_rules_filename`, `llm_generated_rules_source`) |

### 12.3 Ke Standar & Jurnal

| Standar / Referensi | Cakupan di sini |
|---------------------|-----------------|
| **MITRE CWE** | Semua entri di `domain_knowledge_base.yml` + `general_knowledge_base.yml` |
| **OWASP Top 10:2021** | Severity elevation `domain_priority.py` |
| **OWASP API Top 10:2023** | Tier 3 prompt `RECOMMENDED_COVERAGE["e-commerce"]` |
| **OWASP IoT Top 10** | Tier 3 prompt `RECOMMENDED_COVERAGE["iot"]` |
| **PCI-DSS v4.0** | Tier 3 prompt `RECOMMENDED_COVERAGE["e-commerce"]` (pci_dss field) |
| `meneely2013patch` | Justifikasi "vulnerabilities cluster by domain" di naskah R1.2 + T1 |
| `matter2025context` | Justifikasi context-aware security (naskah R1.2, T1, G1) |
| `taherdoost2022payment` | Justifikasi payment gateway API key leak (naskah R3 e-commerce) |
| `gupta2017sql` | Justifikasi SQLi di /checkout (naskah R3 e-commerce) |
| `gupta2017xss` | Justifikasi XSS di blog (naskah R3 blog) |
| `calzavara2020csp` | Justifikasi CSP headers (naskah R3 blog) |

---

## Lampiran A: Tier 1 — File Statis per Domain

### A.1 `owasp-api.yml` (Baseline — Selalu ON)

File ini adalah **layer baseline** untuk SEMUA domain. Berisi rule OWASP API Security Top 10:2023 (API1 BOLA, API2 Broken Auth, API3 BOPLA, dst).

### A.2 `ecommerce.yml` (Tier 1 — e-commerce only)

Rule ID yang termasuk (lihat `llm_generation_prompt.TIER1_RULE_IDS["e-commerce"]`):

```
ecommerce-pci-card-data-in-logs       (CWE-532, PCI-DSS 3.4)
ecommerce-pci-stripe-secret-in-source  (CWE-798)
ecommerce-pci-raw-pan-in-code          (CWE-312)
ecommerce-api-bola-cart-access         (CWE-639, OWASP API1)
ecommerce-api-no-auth-on-checkout      (CWE-862)
ecommerce-price-tampering              (CWE-602)
ecommerce-discount-tampering           (CWE-602)
ecommerce-mass-assignment-admin        (CWE-915, OWASP API6)
ecommerce-sqli-order-lookup            (CWE-89)
ecommerce-xss-product-render           (CWE-79)
ecommerce-csrf-no-protection           (CWE-352)
ecommerce-jwt-weak-secret              (CWE-798)
ecommerce-jwt-no-expiration            (CWE-613)
ecommerce-log-sensitive-data           (CWE-532)
ecommerce-md5-password                 (CWE-327)
ecommerce-sha1-password                (CWE-327)
ecommerce-webhook-no-signature-check   (CWE-345)
ecommerce-order-amount-from-client     (CWE-602)
ecommerce-refund-without-original-charge (CWE-840)
ecommerce-currency-float-arithmetic    (CWE-682)
ecommerce-stock-decrement-without-lock (CWE-362)
ecommerce-idempotency-key-missing      (CWE-754)
ecommerce-pii-in-url                   (CWE-598)
ecommerce-shipping-address-trust-client (CWE-602)
ecommerce-test-card-in-source          (CWE-798)
ecommerce-secret-key-in-client         (CWE-798)
```

### A.3 `blog-csp.yml` (Tier 1 — blog only)

```
blog-markdown-sanitize          (CWE-79)
blog-comment-stored-xss         (CWE-79)
blog-javascript-link-markdown   (CWE-79)
blog-open-redirect-via-next     (CWE-601)
blog-cookie-no-httponly         (CWE-1004)
blog-user-enumeration           (CWE-204)
blog-idor-post-edit             (CWE-639)
```

### A.4 `iot-mqtt.yml` (Tier 1 — iot only)

```
iot-mqtt-tls-required             (CWE-319)
iot-device-default-credentials    (CWE-798)
iot-firmware-update-signature     (CWE-494)
iot-tls-cert-verify-disabled      (CWE-295)
iot-mqtt-broker-bind-wildcard     (CWE-668)
iot-firmware-no-signature-verify  (CWE-494)
iot-default-password-in-config    (CWE-798)
iot-sensor-data-no-encryption     (CWE-311)
iot-telnet-enabled                (CWE-319)
iot-debug-interface-exposed       (CWE-489)
iot-device-id-as-only-auth        (CWE-287)
iot-overall-tls-required          (CWE-319)
```

---

## Lampiran B: Tier 3 — Aturan Wajib

1. **Scope domain**: hanya **3 domain** (`e-commerce`, `blog`, `iot`) per naskah R2.2. `general` dikecualikan.
2. **Confidence threshold**: `MIN_LLM_CONFIDENCE = 0.7` (env-overridable).
3. **Max rules per domain**: `MAX_RULES_PER_DOMAIN = 8` (env-overridable).
4. **Severity default**: `WARNING` (bukan `ERROR`) di first generation.
5. **ID prefix wajib**: `{domain}-custom-{slug}`.
6. **Filename pattern**: `<domain>-combined-<8-char-hash>.yml` (Tier 1 + Tier 3 digabung).
7. **Cache key**: `SHA-256(domain, domain_threats, primary_language, frameworks)`.
8. **Validasi**: `semgrep --validate` di workflow CI step `Validate custom Semgrep rules` (continue-on-error: true).
9. **Feature flag**: `ENABLE_LLM_GENERATED_RULES=false` (default).
10. **Storage**: commit ke `.semgrep/<file>.yml` di repo target via PR.
11. **Batasan tambahan**: tidak generate untuk arsitektur `kubernetes` / `service-mesh` murni (sudah di-skip di Layer 3 `scan_directives.py`).
12. **CWE wajib** di metadata setiap rule. OWASP API / OWASP IoT / PCI-DSS **strongly recommended** bila applicable.
13. **Methodological grounding** (naskah R1.2 + R4.2): hybrid OWASP (makro) + CWE (mikro) + jurnal spesifik domain.

---

## Catatan Penutup

- Folder ini adalah **Tahap 1.5 + Tahap 2 (K2.3) + Tahap 3 (K3) consumer**. Folder ini **TIDAK** di-trigger di Tahap 4 (scoring).
- Tier 3 **opt-in**. Untuk demo skripsi (Bab 5) yang mengevaluasi efek Tier 3, set `ENABLE_LLM_GENERATED_RULES=true` lalu bandingkan dengan run baseline (false).
- Kode yang **JANGAN** diedit sembarangan: `index.yml`, `domain_knowledge_base.yml`, `llm_generation_config.py`. Ketiganya adalah kontrak domain.
- **3 domain aktif** adalah keputusan sadar (R2.2). Untuk extend, lihat **Section 10** (Cara Menambah Domain Baru) — tapi **WAJIB** revisi naskah dulu.

---

> **Last updated**: v9.5 (perluasan coverage CWE/OWASP) · 3 domain (e-commerce, blog, iot) · 2 arsitektur (monolitik tradisional, modular monolith) · 41 CWE total (20 e-commerce + 9 blog + 12 iot)
> **Judul skripsi**: Model Adaptive Security Assessment Pipeline Berbasis Analisis Domain-Aware Repository untuk Evaluasi Keamanan
> **Maintainer**: lihat `ai-service/app/agents/` (folder parent)
> **Lisensi**: Internal skripsi — bukan untuk distribusi publik
