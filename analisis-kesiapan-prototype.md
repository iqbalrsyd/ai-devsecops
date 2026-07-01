# Analisis Kesiapan Prototype terhadap Rencana Pengujian Bimbingan 1 Juli 2026

> **Acuan:** `README-BIMBINGAN.md` (ringkasan bimbingan 1 Juli 2026, 18m 10s, Pembimbing: Ridi Ferdiana)
> **Tanggal analisis:** 1 Juli 2026
> **Status prototype:** Docker containers aktif (backend, ai-service, frontend, postgres, redis, nginx)

---

## A. Ringkasan Rencana Pengujian Baru (dari Bimbingan)

| Aspek | Spesifikasi |
|-------|-------------|
| Jumlah pengujian | **3 kali** dengan kategori teknologi berbeda |
| Jumlah domain | **4 domain** |
| Domain | Internet System (e-commerce), Business System, Information System, General |
| Sampling | Random sampling — bahasa pemrograman **tidak disamakan** |
| Jumlah repo | **1 per domain** (total 4 repositori) |
| Kriteria repo | **Well-known system** yang banyak digunakan |
| Contoh | E-commerce → Shopify; Business → source code model; Information System → WordPress; General → aplikasi sendiri |
| Ground truth | Gunakan **versi LAMA** source code (belum di-patch) |
| Evaluasi | Coverage, konsistensi, rekomendasi benar/salah, code coverage, sistem jalan/tidak |

---

## B. Status Prototype Saat Ini

### Arsitektur & Infrastruktur: ✅ SIAP
| Komponen | Status | Detail |
|----------|--------|--------|
| Docker Compose | ✅ Running | 6 container (postgres, redis, backend, ai-service, frontend, nginx) |
| Backend (Go/Gin) | ✅ Running | 40+ API endpoint, JWT auth, CRUD, GitHub integration |
| AI Service (Python/FastAPI) | ✅ Running | 18 node LangGraph, 11 LLM calls, 4 tahapan |
| Frontend (React/Vite) | ✅ Running | 15 halaman, 26 komponen |
| Database (PostgreSQL) | ✅ Running | Migration SQL tersedia, GORM AutoMigrate |
| Queue (Redis) | ✅ Running | | 

### Fitur Inti: ✅ TERSEDIA

| Tahapan | Node | Status | Keterangan |
|---------|------|--------|------------|
| **Tahap 1:** Repo Context | 6 node (repo_connection, repo_scan, technology_detection, architecture_detection, deployment_detection, domain_detection) | ✅ | Hybrid LLM + heuristic fallback |
| **Tahap 2:** Coverage Inference | 4 node (coverage_inference, pattern_inference, pipeline_augmentation, job_reasoning) | ✅ | 15 coverages (perlu dikerucutkan ke 10) |
| **Tahap 3:** Pipeline Gen | 5 node (workflow_generation, workflow_validation, workflow_repair, github_branch_creation, pull_request_creation) | ✅ | Deterministic YAML builder, SHA pinning |
| **Tahap 4:** Security Eval | 3 node (security_analysis, recommendation_generation, response_formatter) | ✅ | OWASP 3-dim scoring, 4-bucket classification |

---

## C. Kesenjangan (Gap) terhadap Rencana Pengujian Baru

### C.1 Gap KRITIS — Harus Diperbaiki Sebelum Pengujian

| # | Kesenjangan | Kondisi Sekarang | Yang Dibutuhkan | Dampak |
|---|-------------|-----------------|-----------------|--------|
| 1 | **Dataset: 40 repo → 4 repo** | Sistem & dokumen merujuk 15-18 repo (3 domain) atau 40 repo (7 domain) | **4 repositori well-known** × 3 pengujian = 12 run total | CRITICAL — seluruh desain eksperimen berubah |
| 2 | **Domain: 3 → 4** | Coverage library punya 15 coverages untuk 7 domain; dataset rencana 3 domain (e-commerce, blog, IoT) | **4 domain**: Internet System (e-commerce), Business System, Information System, General | CRITICAL — perlu domain baru "Information System" |
| 3 | **Kriteria repo: well-known** | Repo uji saat ini `test-repo/` adalah aplikasi dummy buatan sendiri | **Shopify, WordPress, model source code, aplikasi sendiri** — versi lama (unpatched) | CRITICAL — ground truth bergantung pada versi lama |
| 4 | **Ground truth: versi lama unpatched** | Belum ada prosedur version rollback atau koleksi versi lama | **Prosedur version rollback** + labeling manual pada versi lama | CRITICAL — validasi rekomendasi benar/salah |
| 5 | **Bahasa: tidak disamakan** | Dataset merujuk JS/TS homogen sebagai variabel kontrol | **Random sampling** — bahasa pemrograman heterogen | HIGH — perlu menghapus kontrol bahasa dari desain |
| 6 | **Focus: domain (bukan arsitektur)** | Sistem masih mendeteksi arsitektur (monolith, modular_monolith) sebagai output node | Arsitektur tetap dideteksi tapi **bukan variabel eksperimen** — hanya konteks | MEDIUM — narasi Bab 1-3 harus diubah |

### C.2 Gap TEKNIS pada Codebase

| # | Kesenjangan | File/Lokasi | Perbaikan |
|---|-------------|-------------|-----------|
| 7 | **`domain_priority.py` hilang** | Dirujuk di 38 tempat, diimpor oleh `simulate_domains.py`, didokumentasikan di `score-risk-v2.md` tapi **file tidak ada** | BUAT file ini — severity elevation module deterministic untuk domain-aware risk scoring |
| 8 | **Coverage library: 15 → perlu disesuaikan** | `coverage_library.py` — 15 coverages termasuk healthcare, fintech, education, microservice, csp | Untuk 4 domain baru, beberapa coverage tidak relevan (healthcare, fintech, education) |
| 9 | **Domain detection: 7 → 4 domain** | `domain_detection_node.py` mendukung 7 domain (e-commerce, healthcare, fintech, blog, iot, education, general) | Perlu menambah "Information System" dan menyesuaikan prompt LLM |
| 10 | **Workflow generator: 5 domain jobs → 3-4** | `workflow_generator.py` (6947 baris) punya 5 domain job (pci-dss, hipaa, ledger-check, csp-headers, mqtt-security) | Sesuaikan dengan 4 domain baru — mungkin perlu job baru untuk Information System |
| 11 | **AI-generated rules: perlu validasi cross-domain** | `pattern_inference_node.py` — aturan Semgrep AI-generated belum diuji akurasi untuk domain baru | Perlu validasi TPR (≥0.60), FPR (≤0.30), syntactic validity 100% |
| 12 | **PDF report: hardcode 15 coverages** | `coverage_library.py` baris 29 — jumlah hardcode "15" | Gunakan `len(COVERAGES)` dinamis |

### C.3 Gap pada Naskah (Bab 1-5)

| # | Gap | Tindakan |
|---|-----|----------|
| 13 | Bab 1: Masih menekankan arsitektur (monolith vs microservices) | Ubah ke fokus domain + otomasi security assessment |
| 14 | Bab 3: Desain eksperimen masih 40 repo (20+20) | Ubah ke 4 domain × 1 repo × 3 pengujian |
| 15 | Bab 5: Masih berisi implementasi | Pindahkan ke akhir Bab 4, Bab 5 jadi kesimpulan |
| 16 | Struktur makalah belum sesuai | Sesuaikan dengan 6-section: Pendahuluan, Existing Solutions, Proposed Solution, Metode, Hasil, Manfaat |

---

## D. Penilaian Kesiapan per Komponen Pengujian

### D.1 Kesiapan untuk "3 Kali Pengujian dengan Teknologi Berbeda"

| Teknologi | Kesiapan Sistem | Catatan |
|-----------|----------------|---------|
| **SAST (Semgrep)** | ✅ Siap | Static rules (Tier 1) + AI-generated rules (K2.3), multi-language support (8 bahasa) |
| **SCA (Trivy)** | ✅ Siap | `dependency-scan` job di workflow generator, CVE mapping |
| **Secret Scan (Gitleaks)** | ✅ Siap | `secret-scan` job dengan fokus per domain, entropy filtering |

### D.2 Kesiapan untuk 4 Domain

| Domain | Kategori | Deteksi Domain | Coverage Spesifik | Domain Job | Ground Truth |
|--------|----------|----------------|-------------------|------------|-------------|
| **Internet System (e-commerce)** | McConnell | ✅ `e-commerce` + sub_type payment | ✅ `payment_security` | ✅ `pci-dss-check` | ❌ Perlu repo well-known + versi lama |
| **Business System** | McConnell | ⚠️ Perlu dipetakan: fintech/healthcare/education → Business System | ⚠️ Perlu coverage baru | ❌ Belum ada job spesifik | ❌ Perlu repo well-known + versi lama |
| **Information System** | McConnell | ❌ Tidak ada di domain_detection | ❌ Belum ada coverage | ❌ Belum ada job | ❌ Perlu repo (WordPress) |
| **General** | — | ✅ Ada sebagai fallback | ✅ 7 coverage generik | ✅ Standard 8 jobs | ⚠️ Aplikasi sendiri perlu dipersiapkan |

### D.3 Kesiapan Metrik Evaluasi

| Dimensi Evaluasi | Kesiapan | Modul | Keterangan |
|-----------------|----------|-------|------------|
| **Coverage** | ✅ | `coverage_inference_node.py` | Coverage precision/recall/F1 siap dihitung |
| **Konsistensi** | ⚠️ | Parsial di `security_analyzer.py` | Consistency antar domain perlu dihitung manual |
| **Rekomendasi benar/salah** | ⚠️ | `recommendation_gen.py` | Belum ada mekanisme validasi terhadap ground truth versi lama |
| **Code coverage** | ❌ | Tidak ada | Perlu menambahkan code coverage metric dari test job |
| **Sistem jalan/tidak** | ✅ | `workflow_execution.py` + `execution_monitor.py` | Pipeline execution monitoring tersedia |

### D.4 Kesiapan Ground Truth

| Kebutuhan | Status | Keterangan |
|-----------|--------|------------|
| Labeling domain manual | ✅ Siap | Bisa dilakukan manual via CSV |
| Labeling coverage expected | ✅ Siap | Prosedur di `rencana-pengujian-dataset.md` §B |
| Labeling arsitektur manual | ✅ Siap | Dataset homogen monolitik |
| **Versi lama source code** | ❌ BELUM | Tidak ada prosedur version rollback |
| **Validasi rekomendasi benar/salah** | ❌ BELUM | Perlu prosedur: bandingkan temuan di versi lama vs baru |

---

## E. Skor Kesiapan Keseluruhan

| Aspek | Skor (0-100%) | Status |
|-------|---------------|--------|
| **Infrastruktur & Deployment** | 95% | ✅ Docker running, semua service up |
| **Pipeline Generation (Tahap 1-3)** | 85% | ✅ 18 node berfungsi, YAML valid |
| **Security Evaluation (Tahap 4)** | 70% | ⚠️ OWASP 3-dim siap, tapi `domain_priority.py` hilang |
| **Domain Coverage (4 domain baru)** | 40% | ❌ Information System & Business System belum ada |
| **Dataset & Ground Truth** | 10% | ❌ Repo well-known belum dikumpulkan, versi lama belum ada |
| **Metrik Evaluasi Lengkap** | 50% | ⚠️ Coverage siap, konsistensi & rekomendasi belum |
| **Naskah (Bab 1-5)** | 30% | ❌ Masih merujuk desain lama 40 repo |
| **KESELURUHAN** | **~55%** | ⚠️ Butuh 1-2 hari kerja focused |

---

## F. Action Items Prioritas (Urutan Eksekusi)

### Fase 1: Codebase Fix (estimasi 4-6 jam) — SEBELUM pengujian

| # | Item | File Target | Estimasi |
|---|------|-------------|----------|
| 1 | **BUAT `domain_priority.py`** | `ai-service/app/agents/domain_priority.py` | 1 jam |
| 2 | **Tambah domain "information_system"** | `domain_detection_node.py`, `coverage_library.py` | 2 jam |
| 3 | **Sesuaikan domain jobs** (pci-dss → ecommerce, hapus hipaa/ledger, tambah IS job jika perlu) | `workflow_generator.py` | 1 jam |
| 4 | **Sesuaikan coverage library** (15 → 10 coverages yang relevan untuk 4 domain) | `coverage_library.py` | 30 menit |
| 5 | **Fix hardcode 15 di PDF report** | `coverage_library.py` / `response_formatter.py` | 15 menit |
| 6 | **Update prompt LLM di semua node** (domain 4 baru, arsitektur bukan variabel) | 8+ file prompt | 1 jam |

### Fase 2: Dataset & Ground Truth (estimasi 3-4 jam) — SEBELUM pengujian

| # | Item | Estimasi |
|---|------|----------|
| 7 | Cari & clone **Shopify versi lama** (atau alternatif e-commerce well-known) | 1 jam |
| 8 | Cari & clone **WordPress versi lama** (Information System) | 30 menit |
| 9 | Cari & clone **Business System source code model** | 1 jam |
| 10 | Siapkan **aplikasi sendiri** sebagai domain General | 30 menit |
| 11 | Labeling manual: domain, expected coverages, arsitektur | 1 jam |
| 12 | Prosedur version rollback untuk ground truth | 30 menit |

### Fase 3: Eksekusi Pengujian (estimasi 4-6 jam)

| # | Item | Estimasi |
|---|------|----------|
| 13 | Run pengujian 4 repo × Teknologi 1 (SAST) | 1 jam |
| 14 | Run pengujian 4 repo × Teknologi 2 (SCA) | 1 jam |
| 15 | Run pengujian 4 repo × Teknologi 3 (Secret Scan) | 1 jam |
| 16 | Kumpulkan & validasi hasil (coverage, konsistensi, rekomendasi) | 2 jam |
| 17 | Bandingkan hasil dengan ground truth versi lama | 1 jam |

### Fase 4: Naskah (estimasi 6-8 jam) — PARALEL dengan pengujian

| # | Item | Estimasi |
|---|------|----------|
| 18 | Revisi Bab 1: fokus domain | 1 jam |
| 19 | Revisi Bab 3: desain eksperimen 4×1×3 | 2 jam |
| 20 | Pindahkan implementasi Bab 5 → akhir Bab 4 | 2 jam |
| 21 | Tulis Bab 5 baru (kesimpulan) | 2 jam |
| 22 | Rapikan naskah + draft makalah | 2 jam |

---

## G. Catatan Penting

### Yang Sudah Kuat (Jangan Diubah Terlalu Jauh)
1. **Workflow generator 6947 baris** — deterministic, SHA-pinned, sudah production-grade
2. **18 node LangGraph** — arsitektur solid, tinggal sesuaikan prompt
3. **OWASP 3-dim scoring** — formula sudah benar, severity modifier sesuai
4. **Multi-language support** (8 bahasa) — baik untuk random sampling bahasa
5. **PDF report 5-section** — tinggal tambah section cross-domain validation

### Yang Masih Berisiko
1. **`domain_priority.py` hilang** — blocker untuk risk scoring yang domain-aware (dirujuk di 38 tempat!)
2. **Information System domain** — baru, belum ada di library manapun
3. **Versi lama source code** — syarat mutlak untuk validasi rekomendasi
4. **LLM non-determinism** — temperature 0.3 masih bervariasi, perlu rerun untuk konsistensi
5. **Deadline sangat ketat** — revisi hari ini (1 Juli), review besok (2 Juli), approve sebelum jam 12:00

### Rekomendasi Strategis
1. **Prioritaskan Fase 1 (codebase fix) + Fase 2 (dataset)** — ini blocking untuk pengujian
2. **Mulai pengujian begitu 4 repo siap**, sembari revisi naskah
3. **Gunakan MiniMax-m3** (sudah dikonfigurasi) untuk biaya rendah — penting untuk justifikasi §4.8
4. **Jangan ubah workflow generator terlalu banyak** — sudah stabil, hanya tambah domain job baru
5. **Dokumentasikan setiap gap sebagai "batasan penelitian"** di Bab I (B1-B8) — selaras dengan rekomendasi R5

---

## H. Verifikasi Cepat

```bash
# Cek service berjalan
docker compose ps

# Cek domain_priority.py (seharusnya ERROR — file tidak ada)
ls -la ai-service/app/agents/domain_priority.py

# Cek test repo
ls -la test-repo/

# Cek hasil pengujian terakhir
cat ai-service/ecommerce_pipeline_result.json | python3 -m json.tool | head -50
```

---

> **Kesimpulan:** Prototype secara teknis **~55% siap** untuk rencana pengujian bimbingan baru. Infrastruktur dan pipeline generation solid, tetapi ada gap signifikan pada:
> 1. Dataset & ground truth (repo well-known + versi lama belum ada)
> 2. Domain baru (Information System & Business System)
> 3. Module `domain_priority.py` yang hilang
> 4. Naskah yang masih merujuk desain lama (40 repo, 7 domain)
>
> Estimasi total: **17-24 jam kerja** untuk menyelesaikan semua gap dan siap sidang.
