# Point-Point PPT: Flow, Fitur, dan Rencana Pengujian Prototype

> **Acuan Rencana Pengujian:** `struktur-v7.md` BAB 5 (Hasil dan Pembahasan)
> **Acuan Flow & Fitur:** `struktur-v9.md`, `README.md`, `ai-service/ARCHITECTURE.md`

---

## Slide 1 — Judul

- **Judul Skripsi:** Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices
- Nama / NIM
- Logo universitas

---

## Slide 2 — Pendahuluan: Masalah & Tujuan

- **Masalah:** Pipeline DevSecOps manual, tidak adaptif terhadap konteks repositori (arsitektur, domain, teknologi)
- **Gap:** Belum ada sistem terpadu yang menganalisis repo → klasifikasi arsitektur → inferensi keamanan → generate pipeline adaptif + aturan SAST kustom per domain + evaluasi kuantitatif
- **Tujuan:** Membangun model graph-based AI agent yang autonomous: generate, deploy, execute, evaluate pipeline GitHub Actions secara adaptif

---

## Slide 3 — Arsitektur Sistem (High-Level)

```
Browser → Nginx (:80)
  ├── /* → React Frontend (Vite :5173)
  ├── /api/* → Go/Gin Backend (:8080) → PostgreSQL + Redis
  └── /ai/* → Python/FastAPI AI Service (:8000) → LLM Providers
```

- **3 layanan microservice:** Frontend (React), Backend (Go), AI Service (Python)
- **LLM Provider:** OpenAI / Anthropic / Gemini / OpenRouter / OpenCode
- **Infrastruktur:** Docker Compose, Nginx reverse proxy, PostgreSQL 16, Redis 7

---

## Slide 4 — Flow Utama: 4 Tahapan AI Agent

```
Tahap 1: Repository Context Analysis (6 node)
  → Tahap 2: Security Coverage Inference (2 node)  ← KONTRIBUSI v9
  → Tahap 3: Pipeline Generation & Deployment (5 node)
  → Tahap 4: Security Evaluation (3 node)
Total: 18 node compiled | 9 LLM calls
```

- **3 kontribusi penelitian:** K1 (Repo Context), K2 (Coverage Inference), K3 (Pipeline Gen & Eval)
- **Bonus K1.5:** LLM-generated domain-specific SAST rules (Tier 3, opt-in)

---

## Slide 5 — Tahap 1: Repository Context Analysis (K1)

| Node | Fungsi |
|------|--------|
| `repository_connection` | Koneksi ke GitHub API, validasi token + scope |
| `repository_scan` | Scan file tree + struktur direktori |
| `technology_detection` | Deteksi bahasa, framework, build tools, package manager |
| `architecture_detection` | Klasifikasi **monolitik** (single arsitektur per R2.1) |
| `deployment_detection` | Dockerfile, K8s manifests, Terraform, Helm |
| `domain_detection` | Klasifikasi domain webapp (e-commerce, healthcare, fintech, blog, IoT, education) + payment processor (midtrans, xendit, stripe, dll) |

**Output:** `detected_technologies`, `detected_architecture`, `detected_deployment`, `detected_domain`

---

## Slide 6 — Tahap 2: Security Coverage Inference (K2 — v9)

- **15 security coverages** yang composable (authentication, API, data, payment, container, IoT, logging, file upload, healthcare, fintech, CMS, education, microservice, CSP, dependency)
- **2 node:**

| Node | Fungsi |
|------|--------|
| `coverage_inference` | Repo context → daftar security coverages yang applicable (beserta reason + confidence) |
| `pipeline_augmentation` | Coverages → augmentation (job + configuration per coverage) |

- **Contoh:** `payment_security` → SAST (PCI-DSS rules) + secret scan (stripe/midtrans keys)
- **Microservice** → docker-compose-validate + dependency-scan-per-service

---

## Slide 7 — Tahap 3: Pipeline Generation & Deployment (K3)

| Node | Tipe | Fungsi |
|------|------|--------|
| `workflow_generation` | Deterministik | Generate YAML dari decision tree (8 standard jobs + 5 domain-specific jobs) |
| `workflow_validation` | Deterministik | Validasi syntax (actionlint), SHA pinning, permissions scope, action registry |
| `github_branch_creation` | API | Buat deployment branch |
| `pull_request_creation` | API | Create PR dengan workflow YAML + rules Semgrep |
| `workflow_execution` | API | Trigger + monitor GitHub Actions run |

**Fitur generator:**
- **Deterministik** (non-LLM): SHA-pinned actions, action registry 20+ actions, evidence-based guards
- **Decision tree:** auto-drop stage yang tidak relevan (misal: iac-scan kalau tidak ada Terraform/K8s)
- **8 standard jobs:** lint, test, build, sast, dependency-scan, secret-scan, container-build, container-scan
- **5 domain-specific jobs:** pci-dss, hipaa, ledger-check, csp-headers, mqtt-security

---

## Slide 8 — Tahap 4: Security Evaluation (K3)

| Node | Fungsi |
|------|--------|
| `security_analysis` | Kumpulkan annotation/logs → normalisasi (scanner normalizer) → deduplikasi → LLM enrichment → klasifikasi 4-bucket findings |
| `recommendation_generation` | Generate rekomendasi remediasi per finding |
| `response_formatter` | Unified response + PDF report (5 sections) |

**4-bucket classification:**
1. **Critical** — harus langsung diperbaiki
2. **Confirmed** — temuan valid, perlu perbaikan
3. **Noise** — false positive
4. **Info** — informational

**PDF Report (5 sections):**
1. Repository Context
2. Security Requirements
3. Generated Pipeline
4. Pipeline Evaluation (Dashboard, Findings + OWASP L×I, Recommendations)
5. Security Coverages Applied

---

## Slide 9 — Frontend: 15 Halaman

| Halaman | Fungsi Utama |
|---------|-------------|
| Landing | Halaman awal |
| Login / Register | JWT auth |
| Dashboard | Statistik agregat semua project & repo |
| Project Detail | Manajemen project workspace |
| Repository Detail | Detail repo + scan history |
| Pipeline Generator | UI generate workflow adaptif |
| Pipeline History | Riwayat pipeline versions |
| Pipeline Version Detail | Detail YAML + validasi |
| Pipeline Compare | Side-by-side diff dua versi pipeline |
| Run Detail | Timeline eksekusi job + live log viewer |
| Run Analysis | Risk score gauge, 4-bucket dashboard, severity chart, AI explanation |
| Settings | Edit profile + change password |

**Komponen reusable:** CodeBlock, CodeDiff, YamlViewer, RiskScoreGauge, SeverityChart, FindingsTable, ExecutionTimeline, LiveLogViewer, RecommendationsList, ValidationResults

---

## Slide 10 — Fitur Unggulan

1. **Context-Aware Pipeline Generator** — Adaptive workflow berdasarkan arsitektur & domain
2. **Deterministic YAML Builder** — Bukan LLM-generated, pakai decision tree + action registry (reproducible)
3. **15 Security Coverages** — Composable, evidence-based, per-coverage augmentation
4. **Scanner Normalization Pipeline** — Ekstrak findings terstruktur dari berbagai output scanner
5. **OWASP 3-Dim Scoring** — TAF (Threat Agent Factor) × VF (Vulnerability Factor) × BI (Business Impact)
6. **4-Bucket Classification** — Pisahkan security findings dari noise
7. **PDF Report** — Multi-section report otomatis
8. **LLM-Generated SAST Rules** (Tier 3, opt-in) — Aturan Semgrep kustom per domain

---

## Slide 11 — Rencana Pengujian: Dataset & Setup Eksperimen

> **Acuan:** `struktur-v7.md` §5.1

- **40 repositori publik open-source** dari GitHub
  - **15–18 repositori monolitik** (3 domain × 5–6 repo)
- **7 domain:**
  - e-commerce, healthcare, fintech, blog/content, IoT, education, general
- **Ground truth:** label manual berdasarkan README, struktur direktori, dokumentasi repo
- **Tier 3 experiments:** subset repositori dengan `ENABLE_LLM_GENERATED_RULES=true`
- **Setup:** Docker Compose (backend + AI service + frontend + PostgreSQL + Redis)

---

## Slide 12 — Rencana Pengujian: Research Questions

**RQ1 — Akurasi Repository Context Analysis & Validitas Pipeline**

| Pertanyaan | Metrik |
|------------|--------|
| Seberapa akurat deteksi teknologi? | Precision, Recall, F1 |
| Seberapa akurat klasifikasi arsitektur? | Akurasi deteksi monolitik (sanity check) |
| Seberapa akurat deteksi domain? | Precision, Recall, F1 per domain |
| Seberapa akurat deteksi payment processor? | Akurasi sub-type detection |
| Apakah workflow syntax valid? | % lolos `actionlint` tanpa error |
| Apakah actions menggunakan SHA pin? | % SHA pinning compliance |
| Apakah permissions scope minimal? | % job dengan permissions minimal |
| Apakah pipeline adaptif terhadap arsitektur? | N/A — arsitektur bukan variabel eksperimen (R2.1) |
| Apakah kontrol sesuai domain? | Domain relevance score |

---

## Slide 13 — Rencana Pengujian: RQ1 Lanjutan & Tier 3

**Tier 3 Rule Quality (K1.5)**

| Metrik | Deskripsi |
|--------|-----------|
| True Positive Rate (TPR) | Aturan LLM mendeteksi vulnerability nyata |
| False Positive Rate (FPR) | Aturan LLM menghasilkan false alarm |
| Precision / Recall | Kualitas deteksi aturan Semgrep LLM-generated |

**Action Registry Compliance**

- % action yang terdaftar di `action_registry.py`
- % action dengan SHA commit hash (bukan versi tag)

**Threshold keberhasilan:** precision > 0.80

---

## Slide 14 — Rencana Pengujian: RQ2 — Kualitas Pipeline dari Eksekusi

> **Acuan:** `struktur-v7.md` §5.4

**Metrik Utama:**

| Metrik | Deskripsi |
|--------|-----------|
| **Risk Score (OWASP 3-dim)** | Distribusi skor risiko 0–100 (tinggi = risiko rendah) dari TAF × VF × BI |
| **Security Standards Coverage Score** | Cakupan kontrol terhadap OWASP CI/CD Top 10 + OWASP Top 10 + CIS K8s Benchmarks |
| **Security Coverage Score** | Cakupan OWASP CI/CD controls (8 controls) |

**Analisis Perbandingan:**

- Monolith vs Microservices → perbedaan risk score & coverage
- Perbandingan antar domain: e-commerce vs healthcare vs blog
- Pengaruh Tier 3: risk score + coverage dengan vs tanpa LLM-generated rules

---

## Slide 15 — Scoring Model: OWASP 3-Dim

**Rumus OWASP 3-Dim (v7):**

```
L = (TAF + VF) / 2      → Likelihood
I = BI                   → Impact
Risk = L × I             → dikali 100 untuk skala 0–100
```

| Dimensi | Komponen |
|---------|----------|
| **TAF** (Threat Agent Factor) | Skill level, motive, opportunity, size |
| **VF** (Vulnerability Factor) | Ease of discovery, ease of exploit, awareness, intrusion detection |
| **BI** (Business Impact) | Financial damage, reputation damage, non-compliance, privacy violation |

- **24 pre-mapped vulnerability types** dalam `_OWASP_3DIM_TYPE_MAP`
- **25+ leaked external patterns** yang di-exclude dari risk score (noise filter)
- **Severity modifier** untuk penyesuaian final

---

## Slide 16 — Kesimpulan & Kontribusi

**3 Kontribusi Utama (+1 Bonus):**

| Kode | Kontribusi | Output |
|------|-----------|--------|
| **K1** | Repository Context Analysis | 6 node: deteksi teknologi, arsitektur, deployment, domain |
| **K1.5** | LLM-Generated Domain-Specific SAST Rules (Tier 3) | Aturan Semgrep kustom per domain (opt-in) |
| **K2** | Security Coverage Inference (v9) | 15 composable coverages → pipeline augmentations |
| **K3** | Adaptive Pipeline Generation & Evaluation | Workflow YAML tervalidasi + multi-dimension scoring |

**Sistem menghasilkan:**
- 18 node compiled LangGraph agent
- 15 halaman frontend React
- 25+ endpoint REST API
- PDF report 5-section
- Kerangka evaluasi kuantitatif multi-dimensi

---

## Slide 17 — Penutup

- **Demo** (jika diperlukan)
- **Q&A**
- **Terima kasih**

---

## Catatan Tambahan untuk Pembicara

### Saat demo (opsional):
1. Login → Dashboard
2. Create project → Connect GitHub repo
3. Analyze repository → lihat hasil context analysis
4. Generate pipeline → lihat YAML + validasi
5. Deploy via PR → execute workflow
6. View Run Analysis → risk score gauge + 4-bucket findings
7. PDF Report generation

### Referensi file naskah (struktur):
- `struktur-v7.md` — Struktur naskah lengkap BAB 1–6 (versi terbaru sinkron codebase)
- `struktur-v9.md` — Struktur naskah v9 dengan coverage inference (K2 update)
- `PRD-v2.md` — Product Requirements Document (visi, user journey, domain model)
- `domain-aware-pipeline.md` — Konfigurasi pipeline berbasis domain
- `score-risk-v2.md` — Dokumentasi risk scoring
