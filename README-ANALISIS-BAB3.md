# Analisis Bab III Berdasarkan Codebase Aktual

## Konteks

Dosbing memberi masukan bahwa Bab III "terlalu implementatif" dan harusnya menjelaskan **bagaimana eksperimen dilakukan**, bukan **bagaimana coding dilakukan**. Sarannya: pindahkan sebagian besar ke Bab IV, Bab III cukup `Input → Proses → Output` per tahap.

Setelah aku baca codebase-mu secara menyeluruh (18 node, 4 tahap, 97 state fields, 6947 baris workflow generator, 1208 baris job reasoning), **pendapatku berbeda dari dosbing**. Masalahnya bukan tentang "terlalu implementatif", tapi tentang **apa yang dianggap sebagai metodologi dalam penelitian AI-agent-based system**.

---

## Masalah Sebenarnya

Di skripsi S1 rekayasa perangkat lunak, Bab III adalah **metode penelitian + perancangan sistem**. Dua hal ini sering digabung. Untuk penelitian berbasis AI agent seperti milikmu, **desain agent (node, prompt, workflow) adalah bagian dari metode**, karena:

1. **Prompt engineering adalah instrumen penelitian.** Sama seperti kuesioner di penelitian sosial, prompt yang kamu desain menentukan output penelitian. Ini harus ada di Bab III.
2. **State graph (18 node, routing logika) adalah desain eksperimen.** Rantai pemrosesan yang kamu rancang menentukan validitas inferensi. Ini harus ada di Bab III.
3. **Fallback mechanism (deterministic heuristic di setiap LLM node) adalah kontrol kualitas.** Ini adalah keputusan metodologis, bukan implementasi.

**Yang harus dipindahkan ke Bab IV/Lampiran hanyalah detail yang benar-benar engineering murni**, seperti:
- Kode spesifik (contoh: implementasi `_build_semgrep_sast_job()`)
- Konfigurasi Docker/NGINX/deployment
- Detail koneksi database
- Setup CI/CD untuk development

---

## Struktur Bab III yang Aku Sarankan (Berdasarkan Codebase)

### 3.1 Desain Penelitian

Jelaskan pendekatan: **Design Science Research** atau **Experimental Research**.

```
Penelitian ini menggunakan pendekatan eksperimental dengan empat tahap:
  1. Repository Context Analysis (RQ1)
  2. Security Coverage Inference (RQ1)
  3. Pipeline Generation & Deployment (RQ1)
  4. Security Evaluation (RQ2)
```

Sertakan diagram alir 4 tahap (bisa pakai Mermaid/flowchart yang sama dari `pipeline_graph.py`).

### 3.2 Arsitektur Sistem

Jelaskan 3-tier architecture secara konseptual:
- **Frontend**: antarmuka pengguna untuk memicu pipeline, melihat hasil
- **Backend (Go)**: orkestrasi, autentikasi, persistensi data
- **AI Service (Python)**: mesin inferensi berbasis LLM + LangGraph

Gambar diagram arsitektur konseptual (bukan deployment diagram).

### 3.3 Tahap 1: Repository Context Analysis

Ini menjawab: **bagaimana sistem memahami repositori?**

#### 3.3.1 Input
- URL repositori GitHub
- Token akses
- File source code (hasil clone + scan)

#### 3.3.2 Proses (6 node)

| Node | Metode | Output |
|------|--------|--------|
| Repository Connection | GitHub API clone | Struktur direktori, file tree |
| Repository Scan | Source code analysis | Package manifests, file contents |
| Technology Detection | **LLM inference** | Bahasa, framework, build tools |
| Architecture Detection | **LLM inference** | Tipe arsitektur |
| Deployment Detection | **Hybrid (LLM + deterministic)** | Docker/K8s/docker-compose |
| Domain Detection | **Hybrid (LLM + heuristic)** | e-commerce/blog/iot/general |

#### 3.3.3 Bagaimana LLM Digunakan di Tahap 1

**Jelaskan pattern yang digunakan, jangan jelaskan kode.** Contoh:

```
Technology Detection Node menggunakan structured prompt dengan skema JSON output.
LLM diberikan konteks berupa:
  - Daftar file package manifest (package.json, requirements.txt, go.mod)
  - Daftar 50 library teratas yang terdeteksi
  - Struktur direktori

LLM diminta mengembalikan JSON dengan field:
  - primary_language, confidence, frameworks, build_tools,
    package_manager, test_framework, database, runtime

Fallback: jika LLM gagal atau confidence < threshold (0.50),
sistem menggunakan heuristic berbasis ekstensi file dan file konfigurasi.
```

**Pola yang sama berlaku untuk node Architecture Detection dan Deployment Detection.**

#### 3.3.4 Bagaimana Domain Detection Bekerja (Ini Paling Penting untuk RQ1)

Ini adalah node paling kompleks (653 baris) dan paling kritis untuk novelty-mu. Layak dapat subbab sendiri:

```
Domain Detection Node menggunakan hybrid classifier:
  1. Heuristic layer: mencocokkan library, entity, dan route dengan
     domain_knowledge_base (e-commerce: Stripe/Midtrans, Order/Payment,
     /checkout; blog: marked/sanitize-html, Post/Comment, /posts; iot:
     MQTT/paho-mqtt, Device/Sensor, /telemetry)

  2. LLM layer: LLM diberi structured few-shot prompt dengan:
     - Nama dan deskripsi repositori
     - Top 50 library, top 30 entity, top 30 route
     - Heuristic scores dari layer 1
     - Hanya 3 domain yang diizinkan (+ general fallback)

  3. Arbitration: jika heuristic score >= threshold dan LLM confidence
     >= threshold, gunakan hasil LLM. Jika heuristic score < threshold,
     fallback ke "general" (veto mechanism mencegah LLM over-weighting
     sinyal lemah).
```

### 3.4 Tahap 2: Security Coverage Inference

Ini adalah **novelty utama** — menjawab RQ1.

#### 3.4.1 Security Coverage Library

Jelaskan 15 security coverage yang didefinisikan di `coverage_library.py`. Buat tabel:

| ID | Nama Coverage | OWASP Mapping | Sinyal Kunci |
|----|---------------|---------------|-------------|
| dependency_scanning | Dependency Scanning | A06:2021 | lockfile, package.json |
| secret_detection | Secret Detection | A07:2021 | .env, config files |
| container_security | Container Security | — | Dockerfile |
| payment_security | Payment Security | A01:2021, A02:2021 | Stripe, Midtrans, PCI-DSS |
| cms_security | CMS Security | A03:2021, A07:2021 | sanitize-html, marked, komentar |
| iot_security | IoT Security | A07:2021 | MQTT, broker, device auth |
| ...       | ... | ... | ... |

#### 3.4.2 Proses Inferensi (4 node)

| Node | Metode | Input | Output |
|------|--------|-------|--------|
| Coverage Inference | **LLM inference** | Konteks repo, heuristic scores | 15 coverage → applicable/not + reason |
| Pattern Inference | **LLM inference** | Source code | Aturan Semgrep kustom |
| Pipeline Augmentation | **LLM inference** | Coverage + arsitektur + deployment | Konfigurasi augmentasi per coverage |
| Job Reasoning | **LLM inference** | Fitur bisnis + coverage + source code | Desain custom CI job (maks 3) |

#### 3.4.3 Bagaimana LLM Digunakan di Tahap 2

```
Coverage Inference Node menggunakan LLM untuk menentukan applicability
15 coverage berdasarkan:

Input ke LLM:
  1. Konteks repositori (bahasa, framework, arsitektur, deployment, domain)
  2. Fitur bisnis (dari domain detection)
  3. Library, entity, route (top 30/20/20)
  4. Heuristic scores dari deterministic signal matching
  5. Daftar 15 coverage beserta deskripsi dan sinyal kuncinya

Output LLM (JSON terstruktur):
   [
     { "id": "payment_security", "applicable": true,
       "reason": "Stripe SDK terdeteksi, endpoint /checkout ada" },
     { "id": "iot_security", "applicable": false,
       "reason": "tidak ada MQTT atau sensor entity" },
     ...
   ]

Fallback: jika LLM gagal, setiap coverage dengan heuristic score >= 1.0
ditandai applicable secara otomatis.
```

**Pola yang sama berlaku untuk Pattern Inference, Pipeline Augmentation, dan Job Reasoning.**

### 3.5 Tahap 3: Pipeline Generation & Deployment

#### 3.5.1 Workflow Generation

**Ini penting: jelaskan bahwa YAML pipeline dihasilkan secara DETERMINISTIK, bukan oleh LLM.**

```
Workflow Generator (6947 baris) membangun GitHub Actions YAML secara
deterministik berdasarkan hasil Tahap 1 dan 2:

1. Stage selection: memilih job berdasarkan bukti file
   - Selalu: lint, sast, dependency-scan, secret-scan
   - Kondisional: test (jika test framework terdeteksi),
     container-scan (jika Dockerfile terdeteksi),
     container-build (jika Docker terdeteksi)

2. Domain-adaptive jobs: menambahkan job spesifik domain
   - pci-dss untuk e-commerce
   - blog-csp untuk blog
   - iot-mqtt untuk iot

3. Custom jobs: job dari LLM Job Reasoning (maks 3, min 0)

4. Tool selection: Semgrep, Trivy, Gitleaks sebagai baseline;
   aturan Semgrep tambahan berdasarkan domain

5. Post-processing: SHA pinning untuk semua GitHub Actions,
   validasi permission, cleanup, konsistensi
```

#### 3.5.2 Workflow Validation

```
Validator memeriksa:
  - Validitas sintaks YAML
  - Ketersediaan action (SHA terverifikasi)
  - Permission minimum
  - Struktur job (continue-on-error, timeout)
  - Tidak ada duplikasi stage

Jika validasi gagal → Workflow Repair (LLM memperbaiki YAML).
```

#### 3.5.3 Deployment (3 node)

| Node | Fungsi |
|------|--------|
| GitHub Branch Creation | Membuat branch baru di repo target |
| Pull Request Creation | Membuat PR berisi workflow YAML |
| Workflow Execution | Menjalankan pipeline via GitHub Actions API |

### 3.6 Tahap 4: Security Evaluation

| Node | Metode | Output |
|------|--------|--------|
| Security Analysis | Hybrid (scanner + normalizer) | Findings, severity breakdown |
| Recommendation Generation | **LLM inference** | Rekomendasi mitigasi |
| Response Formatter | Deterministic | Response JSON terstruktur |

#### 3.6.1 Metrik Evaluasi (RQ2)

```
Security Coverage Score:
  SCS = (jumlah coverage yang applicable DAN terdeteksi) /
        (jumlah coverage yang applicable)
  Range: 0.0 - 1.0

CVSS Aggregate Risk Score:
  CVSS_agg = Σ(severity_weight × count) / total_findings
  severity_weight: critical=9.0, high=7.0, medium=5.0, low=3.0

Penilaian:
  - SCS >= 0.80: Excellent
  - SCS 0.60-0.79: Good
  - SCS 0.40-0.59: Fair
  - SCS < 0.40: Poor
```

### 3.7 State Management

Jelaskan konsep shared state antar node:

```
Setiap node membaca dan menulis ke shared state (PipelineEngineerState,
97 field). State bertindak sebagai "papan tulis" (blackboard) yang
membawa konteks dari Tahap 1 ke Tahap 4. Setiap node hanya membaca
field yang dibutuhkan dan menulis field yang menjadi output-nya. 
Ini memastikan setiap keputusan ditraceable dan reproducible.
```

### 3.8 LLM Configuration

Sebutkan konfigurasi yang digunakan sebagai **parameter eksperimen**:

| Parameter | Nilai | Alasan |
|-----------|-------|--------|
| LLM Provider | OpenAI / Anthropic / OpenRouter | Multi-provider untuk fleksibilitas |
| Model | GPT-4o / Claude 3.5 Sonnet / DeepSeek V4 | Reasoning capability untuk inferensi |
| Temperature | 0.0 - 0.1 | Deterministic output untuk reproducibility |
| Request timeout | 120s per call | Batas reasonable untuk reasoning kompleks |
| Pipeline deadline | 600s | Total time budget untuk satu pipeline |
| Domain confidence threshold | 0.50 | Threshold klasifikasi domain |
| Heuristic score threshold | 3.0 | Minimum untuk override LLM di domain detection |

### 3.9 Metode Validasi & Ground Truth

```
Ground truth untuk setiap repositori target disusun melalui:
  1. Analisis manual oleh peneliti (membaca dokumentasi, source code,
     arsitektur, README, Dockerfile)
  2. Verifikasi dependency melalui package manifest
  3. Identifikasi CVE historis (versi lama yang memiliki kerentanan
     diketahui)
  4. Mapping CVE ke file dan baris kode spesifik

Hasil prediksi AI dibandingkan dengan ground truth untuk menghitung:
  - Precision: TP / (TP + FP)
  - Recall: TP / (TP + FN)
  - F1-Score: harmonic mean Precision dan Recall
  - Coverage Accuracy: coverage yang tepat / total coverage yang
    diprediksi applicable
```

### 3.10 Variabel Eksperimen

| Variabel | Nilai | Tipe |
|----------|-------|------|
| Domain repositori | e-commerce, blog, iot, general | Variabel bebas |
| Security coverage yang diinferensi | 15 coverage × applicable/not | Variabel terikat (RQ1) |
| Jumlah dan jenis temuan keamanan | CWE/CVE per severity | Variabel terikat (RQ2) |
| Security Coverage Score | 0.0-1.0 | Variabel terikat (RQ2) |
| CVSS Aggregate Score | 0.0-10.0 | Variabel terikat (RQ2) |
| Bahasa pemrograman | Python, Node.js, Java | Variabel kontrol |
| Arsitektur | Monolithic (fixed) | Variabel kontrol (batasan) |
| Deployment | Docker/Docker Compose | Variabel kontrol |

---

## Perbandingan: Yang Ada di Codebase vs Yang Harus di Bab III

| Elemen | Di Codebase | Di Bab III |
|--------|------------|------------|
| Prompt LLM | String literal dalam kode Python | Narasi: "apa yang diberikan ke LLM, apa format outputnya, apa fallback-nya" |
| 18 node | Fungsi Python (`domain_detection_node()`) | Tabel: nama node, input, output, metode (LLM/deterministic/hybrid) |
| State graph | LangGraph `StateGraph` + edge definitions | Diagram alir + penjelasan kenapa node dirantai seperti itu |
| 97 state fields | Python `TypedDict` | Tabel ringkasan: field kunci yang mengalir antar tahap |
| Action registry | 914 baris dict Python dengan SHA | Narasi: "GitHub Actions dipilih berdasarkan evidence file, SHA diverifikasi via GitHub API" |
| Domain library | `DOMAIN_LIBRARY_INDICATORS` dict | Tabel: 3 domain × (library + entity + route + threat) |
| Coverage library | `COVERAGES` list | Tabel: 15 coverage dengan deskripsi dan sinyal |
| Workflow generator | 6947 baris fungsi `_build_*_job()` | Alur: stage selection → job construction → validation → post-processing (diagram) |
| Fallback mechanism | `try/except` + heuristic fallback di setiap LLM node | Narasi: "jika LLM gagal, confidence rendah, atau JSON tidak valid, sistem fallback ke heuristic" |
| CVSS mapper | `cvss_mapper.py` | Rumus dan klasifikasi severity |

---

## Prinsip Penulisan Bab III untuk Skripsi AI Agent

```
Yang ditulis di Bab III:                    Yang ditulis di Bab IV/Lampiran:
─────────────────────────                  ──────────────────────────────
✓ Apa yang dilakukan node ini              ✗ Kode Python spesifik
✓ Kenapa node ini ada di sini              ✗ Detail variabel lokal
✓ Input apa yang dibaca                    ✗ Handler error spesifik
✓ Output apa yang dihasilkan               ✗ Detail koneksi API
✓ Metode: LLM / deterministic / hybrid     ✗ Konfigurasi library
✓ Bagaimana LLM digunakan (prompt pattern) ✗ Implementasi fungsi helper
✓ Bagaimana fallback bekerja               ✗ Logging dan tracing
✓ Kenapa threshold dipilih segitu          ✗ Detail deployment (docker-compose, NGINX, CI/CD internal)
✓ Apa keputusan desain kunci               ✗ Detail persistence (GORM, SQLAlchemy)
✓ Diagram dan tabel                        ✗ Setup environment variables selain yang relevan ke eksperimen
```

---

## Jawaban untuk Pertanyaan Kamu

### "Biasanya skripsi tipe kaya gini gimana?"

Skripsi S1 berbasis AI agent system biasanya menggabungkan **metode penelitian + perancangan sistem** di Bab III. Contoh dari skripsi sejenis yang pernah aku lihat:

**Pola umum skripsi AI/ML S1:**
```
Bab III:
  3.1 Desain Penelitian
  3.2 Arsitektur Sistem
  3.3 [Komponen 1]: Metode dan Perancangan
      3.3.1 Input
      3.3.2 Proses (dengan prompt pattern / algoritma / heuristik)
      3.3.3 Output
  3.4 [Komponen 2]: ...
  3.5 [Komponen N]: ...
  3.6 Metrik Evaluasi
  3.7 Setup Eksperimen (dataset, parameter, environment)

Bab IV:
  4.1 Hasil [Komponen 1]
  4.2 Hasil [Komponen 2]
  4.3 ...
  4.4 Pembahasan (diskusi, perbandingan, implikasi)
```

### "Aku pengen jelasin apa aja yg dilakukan di node"

Ini valid dan perlu. Tapi **jangan jelasin kode**. Jelaskan **logika dan keputusan desain**. Contoh perbandingan:

**❌ Cara implementatif (jangan):**
```
Fungsi _score_coverage_heuristic() melakukan iterasi terhadap COVERAGES,
mengambil libraries menggunakan _extract_libraries(state), lalu
menghitung score = matches / len(signals).
```

**✅ Cara metodologis (lakukan):**
```
Setiap coverage memiliki sinyal heuristik (library, entity, route,
deployment). Sistem mencocokkan sinyal ini dengan data yang ditemukan
di repositori. Coverage dengan heuristic score >= 1.0 dianggap memiliki
cukup bukti untuk ditandai applicable jika LLM gagal.
```

---

## Rekomendasi Final

Menurutku, struktur Bab III yang optimal untuk skripsimu adalah:

```
3.1  Desain Penelitian
3.2  Arsitektur Sistem (3-tier: Frontend, Backend, AI Service)
3.3  Tahap 1: Repository Context Analysis
     3.3.1 Technology Detection
     3.3.2 Architecture Detection
     3.3.3 Deployment Detection
     3.3.4 Domain Detection
3.4  Tahap 2: Security Coverage Inference  ← NOVELTY UTAMA, kasih ruang lebih
     3.4.1 Coverage Library
     3.4.2 Coverage Inference
     3.4.3 Pattern Inference
     3.4.4 Pipeline Augmentation
     3.4.5 Job Reasoning
3.5  Tahap 3: Pipeline Generation & Deployment
     3.5.1 Workflow Generation (deterministic, stage selection, tool selection)
     3.5.2 Workflow Validation & Repair
     3.5.3 Deployment Automation
3.6  Tahap 4: Security Evaluation
     3.6.1 Security Analysis
     3.6.2 Metrik Evaluasi (SCS, CVSS Aggregate, Precision/Recall/F1)
3.7  State Management (shared state, blackboard pattern)
3.8  LLM Configuration (parameter eksperimen)
3.9  Metode Validasi & Ground Truth
3.10 Variabel Eksperimen
```

**Ini sekitar 20-25 halaman**, yang normal untuk Bab III skripsi S1.

Dosbing bilang "pindahkan sebagian besar ke Bab IV". Menurutku itu terlalu ekstrem. Yang dipindahkan ke Bab IV cukup:
- Detail deployment (branch creation, PR creation → jadi bagian 4.3 "Hasil Deployment")
- Detail teknis workflow generation (stage selection → jadi bagian 4.4 "Pipeline yang Dihasilkan")
- Response formatter → jadi bagian 4.6 "Output Sistem"

Tapi **prompt design, node logic, coverage library, domain library, fallback mechanism, dan metrik evaluasi** harus tetap di Bab III karena itu adalah **instrumen penelitian**, bukan implementasi.

---

## "Kurang, Cukup, atau Berlebihan?"

Kalau kamu ikuti struktur di atas: **CUKUP**. Tidak kurang, tidak berlebihan. Pas untuk S1.

Kalau kamu ikuti saran dosbing sepenuhnya (pindahkan hampir semua ke Bab IV): **Bab III akan terlalu TIPIS** (~8-10 halaman) dan penguji akan tanya "metodenya di mana?"

Kalau kamu tetap dengan struktur sekarang (node + prompt + kode): **Bab III akan terlalu TEBAL dan IMPLEMENTATIF** (~40+ halaman) dan dosbing benar untuk menegur.

**Rekomendasi praktis:** ambil jalan tengah. 18 node dijelaskan dengan narasi + tabel, prompt pattern dijelaskan dengan format input → output, fallback dijelaskan dengan logika, diagram untuk setiap tahap. Simpan kode dan detail deployment untuk Bab IV dan Lampiran.
