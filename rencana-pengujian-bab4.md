# Rencana Pengujian Bab IV — Diselaraskan dengan Struktur Baru v9.3 + Rekomendasi Judul

> **Tujuan dokumen:** Menjadi acuan revisi Bab IV agar selaras dengan perubahan struktural dari `rekomendasi-judul.md` (R1–R5), perubahan naskah v9.3 (Tahap 2: 4 node LLM), dan rekomendasi judul terpilih (Rekomendasi 1 — *Model Adaptive Security Assessment Pipeline Berbasis Analisis Domain-Aware Repository untuk Evaluasi Keamanan*).
>
> **Tanggal:** 30 Juni 2026
> **Acuan utama:**
> - `naskah/rekomendasi-judul.md` (rekomendasi judul + R1–R5)
> - `naskah/skripsi/contents/chapter-4/chapter-4-v5.tex` (baseline Bab IV v5)
> - `naskah/skripsi/contents/chapter-3/chapter-3.tex` (Bab III, alur penelitian 8 tahap)
> - `naskah/score-risk-v2-20.md` dan `docs/score-risk-v3.md` (scoring OWASP 3-dim)
> - `coba-4/ai-service/ARCHITECTURE.md` (runtime agent 4 tahap, 18 node)
> - `coba-4/ppt-prototype-pengujian.md` (rencana pengujian RQ1–RQ2)
> - `naskah/z-docs-lama/lampiran-rencana-bab4-20.md` (rencana sebelumnya, 7 sub-bab)
>
> **⚠️ Status dataset:** Dataset aktual masih placeholder (semua nilai 0). Bagian ini berisi **rencana** pengujian yang akan dilaksanakan, bukan laporan hasil.

---

## Ringkasan Perubahan Wajib dari Baseline v5

Bab IV v5 saat ini memiliki 7 sub-bab dengan semua tabel berisi 0 (placeholder) dan dataset **40 repositori / 7 domain**. Berdasarkan rekomendasi-judul.md, struktur baru mengharuskan perubahan substantif berikut:

| Aspek | Baseline v5 (sekarang) | Wajib di Versi Baru | Alasan |
|---|---|---|---|
| **Judul kontribusi** | "Adaptive DevSecOps Pipeline" | "Adaptive Security Assessment Pipeline" + "Analisis Domain-Aware Repository" | Rekomendasi 1 terpilih; kontribusi #1 (Repo Context) + #2 (Coverage Inference) dikemas ulang |
| **Dataset** | 40 repo / 7 domain (e-com, fintech, health, edu, blog, IoT, general) | **15–18 repo / 3 domain** (e-commerce, blog, IoT) | R2.1 + R2.2 — pengerucutan klasifikasi mengikuti McConnell |
| **Arsitektur** | 6 tipe (monolith, modular, microservices, service-based, event-driven, serverless) | **1 tipe** (monolitik tradisional) | R2.1 — microservices murni jarang di repo open-source JS/TS; dataset eksperimen Bab 4 homogen monolitik. Sistem internal tetap mendukung modular_monolith untuk generalisasi namun tidak diuji. |
| **Batasan** | 6 butir | 8 butir (B1–B8) | R5 — tambahkan batasan arsitektur non-variabel + pembatasan tool |
| **Frame kontribusi** | "DevSecOps untuk monolitik & microservices" | "Otomasi security assessment" | Pak Ridi menit 7:55 |
| **Jumlah coverages** | 15 (struktur v9) | **10** (v9.5 actual di `coverage_library.py:6`) | Konsolidasi untuk mengurangi noise; hapus healthcare/fintech/education/csp/microservice yang tidak applicable di 3 domain |
| **Section pembuka** | "Hasil Coverage Inference" langsung | Wajib ada paragraf teoretis: "Perbedaan pipeline bukan temuan baru" | T5 (Teks yang Perlu Ditambahkan) — untuk klarifikasi kontribusi |

---

## Struktur Bab IV yang Diusulkan (8 Sub-Bab)

Mengikuti R1–R5 dan lampiran-rencana-bab4-20.md, struktur Bab IV menjadi:

```
Bab IV — Hasil dan Pembahasan

  4.1  Justifikasi Pemilihan Tools Keamanan                      [dipertahankan dari v5]
  4.2  Hasil Repository Context Analysis                          [rename + refocus]
  4.3  Hasil Security Coverage Inference                          [dipertahankan, dirampingkan]
  4.4  Hasil Generasi Pipeline (Per Domain)                       [dipertahankan]
  4.5  Evaluasi Kualitas Pipeline Multi-Dimensi                   [REFACTOR — geser dari OWASP L×I ke OWASP 3-dim]
  4.6  Hasil Konten Generatif (Semgrep Rules + Custom Job)        [dipertahankan]
  4.7  Kendala Teknis dan Lessons Learned                         [dipertahankan]
  4.8  Penggunaan Token LLM dan Analisis Biaya                    [BARU — pindah dari v5 ke sub-bab eksplisit]
```

**Perubahan utama vs v5:**
- §4.2 diubah nama dari "Hasil Repository Analysis" → "Hasil Repository Context Analysis" untuk selaras dengan kontribusi #1
- §4.5 direfactor: ganti mekanisme skor dari "OWASP L×I" menjadi "OWASP 3-dim" (sesuai `score-risk-v3.md`) — ini selaras dengan terminologi naskah baru
- §4.8 BARU — Bab IV v5 sudah punya sub-bab "Penggunaan Token LLM", dipisahkan jadi sub-bab eksplisit karena menjadi bukti efisiensi penggunaan MiniMax-m3
- Sub-bab "Studi Kasus" dan "Pipeline Job Spesifik Domain" di v5 digabung ke §4.4 dan §4.5

---

## 4.1 Justifikasi Pemilihan Tools Keamanan

**Konten (dipertahankan dari v5, dengan 2 perbaikan):**

Tabel 4.1 — Justifikasi pemilihan tools (sama dengan v5, hanya perlu rujukan sitasi yang diperkuat).

**Perubahan substantif:**

1. **Tambah rujukan Zhou et al. (2024)** untuk justifikasi Semgrep vs CodeQL
   - Saat v5: pemilihan Semgrep hanya berdasarkan YAML-friendly dan multi-bahasa
   - Versi baru: tambahkan `\cite{zhou2024comparison}` setelah justifikasi Semgrep
   - Lokasi: paragraf "Pemilihan tools di atas bersifat modular..." (v5 baris 35)

2. **Tambah rujukan Benedetti et al. (2022) + Meli et al. (2019)** untuk klaim miskonfigurasi pipeline dan kebocoran kredensial
   - Saat v5: hanya menyebut "Container scanning pada repo tanpa Docker" sebagai contoh
   - Versi baru: sitasi bahwa ini adalah pola yang terukur di industri
   - Lokasi: paragraf di akhir §4.1

3. **Tambah sub-paragraf "Pemilihan tools bersifat modular & kontekstual"** (sudah ada di v5, tinggal dirapikan)

**Yang sudah benar di v5 (tidak perlu diubah):**
- Tabel justifikasi (Semgrep, Trivy, Gitleaks, GitHub Actions)
- Tiga kriteria pemilihan (open-source, cakupan deteksi, output terstruktur)
- Contoh perbedaan aktivasi tool per domain

**Risiko sidang yang harus dijawab di §4.1:**
- "Kenapa tidak CodeQL?" → Sudah ada di v5 (YAML-friendly). Tambah sitasi Zhou et al.
- "Kenapa tidak Snyk/SonarQube?" → Alternatif di tabel, proprietary/lisensi
- "Kenapa Gitleaks bukan TruffleHog?" → 150+ aturan, entropy filtering (v5 sudah jelas)

---

## 4.2 Hasil Repository Context Analysis

**Perubahan nama & fokus:** v5 sub-bab ini bernama "Hasil Repository Analysis" + "Hasil Klasifikasi Arsitektur" (terpisah). Versi baru menggabungkan keduanya karena Kontribusi #1 ("Analisis Domain-Aware Repository") mencakup dua hal sekaligus.

**Konten yang harus ada:**

### 4.2.1 Dataset Eksperimen

Tabel 4.2 — Distribusi dataset 15–18 repositori (R2.2):

| Domain | Kategori McConnell | Jumlah Repo | Arsitektur (Monolitik) |
|---|---|---|---|
| e-commerce | Internet Systems (public) | 5–6 | 5–6 |
| blog | Internet/Business (hybrid) | 5–6 | 5–6 |
| IoT | Internet/Business (hybrid) | 5–6 | 5–6 |
| **Total** | --- | **15–18** | **15–18 (homogen)** |

**Penjelasan:** Dataset berkurang dari 40 → 15–18 repo karena (a) pengerucutan domain 7→3 sesuai tabel McConnell, (b) keterbatasan dataset IoT open-source JS/TS yang stabil, (c) konsistensi bahasa JavaScript/TypeScript sebagai variabel kontrol (lihat Bab III §3.1).

**Justifikasi pengerucutan (R2.1 + R2.2):**
- Fintech, healthcare, education, general dihapus karena overlap profil ancaman dengan e-commerce/blog
- Microservices murni dihapus karena langka di repo open-source JS/TS. Modular_monolith tetap didukung sistem internal untuk generalisasi, namun dataset eksperimen Bab 4 hanya monolitik tradisional.
- Klasifikasi 3 domain menutup variasi "transactional" (e-com), "content-driven" (blog), "device-centric" (IoT) — cukup untuk uji adaptivitas

### 4.2.2 Akurasi Klasifikasi Domain (K1)

**Metrik:** Precision, Recall, F1 per domain; akurasi keseluruhan; confusion matrix 3×3.

**Threshold keberhasilan:**
- F1 ≥ 0.80 per domain
- Akurasi keseluruhan ≥ 0.85
- Tidak ada domain dengan recall < 0.70 (akan jadi false negative yang berbahaya)

**Tabel 4.3 — Confusion matrix klasifikasi domain:**

| Actual \ Predicted | e-commerce | blog | IoT | general (fallback) |
|---|---|---|---|---|
| **e-commerce** | a | b | c | d |
| **blog** | e | f | g | h |
| **IoT** | i | j | k | l |
| **general** | m | n | o | p |

Diagonal (a, f, k, p) = correct predictions.

**Catatan tentang fallback ke "general":**
Repositori yang tidak memiliki sinyal domain kuat (library, framework, repo general-purpose) akan di-fallback ke domain "general" jika `domain_confidence < 0.7`. Bab IV §4.2 harus melaporkan:
- Jumlah repo yang fallback
- Distribusi confidence scores (histogram)
- Analisis mengapa repo tertentu gagal (low signal)

**Referensi teori:** Meneely et al. (2013) untuk bukti bahwa kerentanan mengelompok per domain; Matter et al. (2025) untuk legitimasi context-aware security.

### 4.2.3 Akurasi Deteksi Teknologi & Arsitektur

**Metrik:** Precision, Recall, F1 untuk:
- Deteksi bahasa pemrograman
- Deteksi framework
- Deteksi arsitektur (monolitik tradisional)
- Deteksi deployment target (Docker, K8s, Terraform)

**Threshold:** F1 ≥ 0.80 (mengikuti ppt-prototype-pengujian.md RQ1)

**Confusion matrix arsitektur (1×1, monolitik):**

| Actual \ Predicted | Monolitik Tradisional |
|---|---|
| **Monolitik Tradisional** | a (selalu benar, dataset homogen) |

**Catatan khusus arsitektur:** Dataset homogen monolitik, sehingga tidak ada confusion matrix nontrivial. Yang dilaporkan di §4.2.3 hanya akurasi deteksi arsitektur sebagai sanity check kemampuan sistem (target F1 ≥ 0.90 karena dataset homogen — sistem hanya perlu mendeteksi "monolitik" dengan benar). Pengujian perbandingan pipeline monolith vs microservices (yang ada di v5) **dihapus** karena arsitektur bukan variabel eksperimen.

**Risiko sidang:** "Kenapa tidak uji modular_monolith?" — Jawab: (1) microservices murni jarang di repo open-source JS/TS (R2.1), (2) variasi monolitik vs modular_monolith akan memerlukan dataset terkontrol yang lebih besar (≥30 repo per arsitektur), (3) fokus penelitian adalah variasi domain, bukan variasi arsitektur. Sistem internal tetap mendukung modular_monolith untuk generalisasi, namun eksperimen Bab 4 cukup bukti konteks domain.

### 4.2.4 Narasi Studi Kasus: Klasifikasi Domain

Wajib ada minimal 1 studi kasus yang menunjukkan *bagaimana* sistem mendeteksi domain:

**Contoh:** Repo `eccomerce-monolith-vuln` (Node.js + Express + Stripe + PostgreSQL):
- Sinyal terdeteksi: library `stripe`, `express-session`; entity `Order`, `Invoice`; route `/checkout`, `/payment`
- Domain inferred: e-commerce (confidence 0.92)
- Domain-specific threats: payment fraud, API key leakage, SQLi di cart

**Sajian:** Potongan output `domain_detection` node (lihat `coba-4/ai-service/app/agents/nodes/domain_detection_node.py`).

---

## 4.3 Hasil Security Coverage Inference

**Struktur (sebagian dipertahankan dari v5):**

### 4.3.1 Coverage per Domain

**Tabel 4.4 — Coverage inference per domain (10 coverages × 3 domain + general fallback):**

| Coverage | e-commerce | blog | IoT | general |
|---|---|---|---|---|
| authentication_security | x | x | x | x |
| api_security | x | x | x | x |
| data_security | x | x | x | x |
| dependency_security | x | x | x | x |
| logging_security | x | x | x | x |
| file_upload_security | x | x | x | x |
| container_security | x (jika Docker) | x (jika Docker) | x (jika Docker) | x |
| **payment_security** | **✓** | — | — | — |
| **cms_security** | — | **✓** | — | — |
| **iot_security** | — | — | **✓** | — |

**Legenda:** ✓ = coverage spesifik domain (selalu applicable jika domain match), x = applicable jika evidence ada, — = tidak applicable.

**Konsistensi dengan R4.2:** payment_security ↔ e-commerce (justifikasi OWASP API8 + PCI DSS), cms_security ↔ blog, iot_security ↔ IoT. Selaras dengan R2.2 — cakupan 10 coverages sudah cukup untuk menguji adaptivitas sistem terhadap 3 domain yang representatif.

**Catatan penting:** Library di v9.5 (`coverage_library.py:6`) hanya memuat **10 coverages**. Domain-spesifik coverage (payment, cms, iot) ditambah pada daftar ini. healthcare, fintech, education, csp, microservice yang sebelumnya ada di struktur v9 (15 coverages) **sudah dihapus** karena (a) domain terkait tidak masuk dataset (R2.2), (b) konsolidasi untuk mengurangi noise dalam inferensi LLM.

**Rasio domain-spesifik vs generik:** 3 dari 10 (30%) = spesifik domain; 7 dari 10 (70%) = generik/cross-domain. Ini sesuai rekomendasi R4.2 yang menginginkan keseimbangan antara coverage generik (selalu applicable) dan coverage spesifik (hanya applicable jika domain match).

### 4.3.2 Metrik Validasi Coverage Inference (BARU)

**Metrik yang harus dilaporkan di v baru (tidak ada di v5):**

| Metrik | Formula | Target |
|---|---|---|
| **Coverage Precision** | TP / (TP + FP) — proporsi coverage yang applicable benar-benar dieksekusi tool | ≥ 0.85 |
| **Coverage Recall** | TP / (TP + FN) — proporsi tool yang harus applicable benar-benar di-infer | ≥ 0.80 |
| **Coverage F1** | harmonic mean | ≥ 0.82 |
| **Domain-specific coverage exclusivity** | Apakah `payment_security` pernah muncul di repo blog? | 0 false positive |

**Cara hitung:**
- **Ground truth:** Manual labeling oleh Iqbal — coverage mana yang harus applicable berdasarkan analisis statis kode (library, entity, route, deployment)
- **Prediksi sistem:** Output dari node `coverage_inference` (state["applicable_coverages"])
- **Per-repo matching:** Bandingkan ground truth vs prediksi, hitung TP/FP/FN per coverage

**Mengapa metrik ini penting:** Ini bukti kontribusi #2 (Security Coverage Inference). Selama v5 tidak punya metrik kuantitatif untuk coverage inference — hanya distribusi tabel saja.

**Risiko sidang:** "Coverage mana yang paling sering salah diprediksi?" — Siapkan tabel error analysis.

### 4.3.3 Fallback ke Coverage Default (Edge Case)

**Skenario:** Repo dengan `domain_confidence < 0.7` → fallback ke "general" → coverage yang applicable = subset generik (`authentication_security`, `api_security`, `data_security`, `dependency_security`, `logging_security`, `file_upload_security`, `container_security` jika ada Docker) — 6–7 coverage generik.

**Yang harus dilaporkan di §4.3.3:**
- Jumlah repo yang mengalami fallback
- Performa coverage inference pada repo general (jika ada)
- Diskusi: apakah fallback strategy berhasil atau menyebabkan under-coverage

### 4.3.4 Paragraf Teoretis (T5)

**WAJIB ada di awal §4.3** (sitasi T5 dari rekomendasi-judul.md):

> Perbedaan coverage antar domain yang disajikan di sub-bab ini bukanlah temuan yang mengejutkan — secara teoritis, domain aplikasi memang memiliki profil ancaman yang berbeda, sehingga mensyaratkan kontrol keamanan yang berbeda pula \cite{meneely2013patch, matter2025context}. Kontribusi penelitian ini adalah pada **otomatisasi inferensi** kontrol tersebut, bukan pada penemuan perbedaan domain itu sendiri.

Paragraf ini krusial untuk mencegah penguji mengkritik: "Temuan Anda sudah diketahui, novelty-nya apa?" — Jawabannya: novelty ada di **mekanisme inferensi otomatisnya**, bukan pada diskovery bahwa domain itu berbeda.

---

## 4.4 Hasil Generasi Pipeline (Per Domain)

**Konten (dipertahankan dari v5 dengan dua perubahan penting):**

### 4.4.1 Pipeline Job Spesifik Domain (3, bukan 5)

v5 punya 5 domain job (pci-dss, ledger-check, hipaa, csp-headers, mqtt-security). Versi baru hanya **3 domain job** karena domain sudah dikerucutkan:

| Domain Job | Domain Pemicu | Coverage Terkait | Standar Acuan |
|---|---|---|---|
| `pci-dss-check` | e-commerce | payment_security | PCI DSS v4.0, OWASP API Top 10 API8 |
| `csp-headers` | blog | cms_security, csp_security | OWASP Top 10 A5 (Misconfig), CSP RFC |
| `mqtt-security` | IoT | iot_security | OWASP IoT Top 10, NIST IR-8259 |

**Justifikasi pengurangan 5→3:**
- `hipaa` dihapus → domain healthcare tidak ada di dataset
- `ledger-check` dihapus → domain fintech tidak ada di dataset
- Tetap ada: `pci-dss-check`, `csp-headers`, `mqtt-security` (satu per domain)

**Tabel 4.5 — Frekuensi kemunculan domain job per domain:**

| Domain Job | e-commerce | blog | IoT | general |
|---|---|---|---|---|
| `pci-dss-check` | 5–6 / 5–6 (100%) | 0 | 0 | 0 |
| `csp-headers` | 0 | 4–5 / 5–6 (~83%) | 0 | 0 |
| `mqtt-security` | 0 | 0 | 4–5 / 5–6 (~83%) | 0 |

**Standar job (selalu ada, 8 job):** lint, test, build, sast, dependency-scan, secret-scan, container-build, container-scan (sama dengan v5, hanya nama yang dirapikan).

### 4.4.2 Validitas Workflow YAML

**Metrik (dipertahankan dari v5, dengan tambahan):**

| Metrik | Target |
|---|---|
| % YAML lolos `actionlint` (sintaks valid) | 100% |
| % action menggunakan SHA pinning (bukan tag) | ≥ 95% |
| % job dengan `permissions` minimal (least-privilege) | ≥ 90% |
| Rata-rata job per workflow | 8–14 (tergantung domain) |
| Rata-rata waktu generasi (detik) | < 60 detik |

**Metrik BARU yang harus ditambahkan (dari R1.3 + R5 B8):**

| Metrik BARU | Target | Alasan |
|---|---|---|
| % action yang ada di `action_registry.py` (allowlist) | 100% | Bukti reproducibility — semua action sudah diverifikasi |
| % workflow yang lulus `workflow_repair_node` tanpa retry | ≥ 90% | Kualitas prompt generation |
| % workflow yang tidak menggunakan action ber-tag mutable (`@v1`) | 100% | Security baseline |

### 4.4.3 Studi Kasus Pipeline: e-commerce vs blog (v5, dipertahankan)

**Konten sama dengan v5 §4.4.3 (sub-bab "Studi Kasus: E-commerce vs Blog").** Pastikan dua repositori pembanding menggunakan tech stack identik (Node.js + Express + PostgreSQL + Docker) untuk isolasi variabel domain.

**Sajian:**

- Listing 4.1 — Potongan workflow YAML e-commerce (snippet baris `secret-scan` priority CRITICAL, job `pci-dss-check`)
- Listing 4.2 — Potongan workflow YAML blog (snippet `csp-headers` job, secret-scan standard)
- Narasi: "meskipun tech stack identik, sistem menghasilkan 2 job tambahan berbeda karena coverage yang applicable berbeda"

**Tambahan baru:** Tampilkan juga snippet aturan Semgrep AI-generated (`ai-payment-*` untuk e-commerce, `ai-cms-*` untuk blog) — bukti kontribusi K2.3 (pattern_inference).

### 4.4.4 Paragraf Klarifikasi Kontribusi

**WAJIB ada di §4.4:**

> Perbedaan pipeline antar domain di §4.4 bukan merupakan temuan baru — secara intuitif, aplikasi e-commerce memang membutuhkan kontrol yang berbeda dari blog \cite{meneely2013patch}. Kontribusi penelitian ini adalah **mekanisme otomatis** yang menghasilkan perbedaan tersebut dari konteks repositori (kontribusi K2 + K3), bukan pada observation bahwa domain itu berbeda. Validasi klaim ini ada di §4.5.4 di mana kami menunjukkan korelasi positif antara confidence domain dengan konsistensi coverage yang di-infer.

---

## 4.5 Evaluasi Kualitas Pipeline Multi-Dimensi

**INI ADALAH SUB-BAB PALING BANYAK PERUBAHAN.** Versi v5 menggunakan kerangka "OWASP L×I" — versi baru menggunakan **OWASP 3-dim** (sesuai `score-risk-v3.md` yang sudah aktif sejak 22 Juni 2026).

### 4.5.1 Skema Scoring OWASP 3-Dim (BARU — RUMUS LENGKAP)

**Formula (harus ada verbatim di §4.5.1):**

```
Likelihood (L) = (TAF + VF) / 2      # range 1.0 - 5.0
Impact (I)     = BI                   # range 1.0 - 5.0
Risk (R)       = L × I                # range 1.0 - 25.0 (per finding)

Untuk setiap finding i:
  R_i = L_i × I_i
  ΣR = ΣR_i

RiskScore = max(0, 100 - (ΣR / (n × 25)) × 100)

Level:
  ≤25  → "critical"   (artinya: skor rendah = risiko tinggi)
  ≤50  → "high"
  ≤75  → "medium"
  >75  → "low"
```

**Severity modifier:**

| Severity | Modifier | Implementasi |
|---|---|---|
| critical | +1.0 | TAF/VF/BI +1, clip [1, 5] |
| high | +0.0 | tidak ada perubahan |
| medium | -0.5 | TAF/VF/BI -0.5, clip [1, 5] |
| low | -1.0 | TAF/VF/BI -1, clip [1, 5] |

**Domain priority elevation (deterministik, sebelum scoring):**
- Kata kunci finansial (`stripe`, `paypal`, `payment`, `credit_card`) → severity dinaikkan 1 level
- Kata kunci PHI (`patient`, `phi`, `hipaa`) → severity dinaikkan 1 level (tidak applicable di v baru karena healthcare dihapus, tapi logikanya tetap ada)
- Kata kunci M2M (`mqtt`, `coap`, `device`) → severity dinaikkan 1 level

### 4.5.2 Distribusi Severity per Domain

**Tabel 4.6 — Distribusi severity finding per domain (15–18 repo):**

| Domain | Total Finding | Critical | High | Medium | Low | Risk Score (mean) |
|---|---|---|---|---|---|---|
| e-commerce | - | - | - | - | - | - |
| blog | - | - | - | - | - | - |
| IoT | - | - | - | - | - | - |
| general (fallback) | - | - | - | - | - | - |
| **Rata-rata** | - | - | - | - | - | - |

**Hipotesis yang akan diuji (dan dilaporkan di §4.5.2):**
- H1: e-commerce memiliki proporsi critical+high tertinggi (>40% total finding) karena domain priority elevation untuk payment
- H2: blog memiliki proporsi critical terendah (<15%) karena tidak ada payment/PHI device
- H3: IoT memiliki proporsi critical medium (~25%) karena M2M elevation tapi tidak separah payment

**Tes statistik (jika n cukup):** Chi-square test untuk proporsi severity antar domain. Jika n kecil, gunakan **deskriptif** saja.

### 4.5.3 Pemetaan Finding ke Security Coverage

**Tabel 4.7 — Jumlah finding per coverage per domain (setelah repo digabung per domain):**

| Coverage | e-commerce | blog | IoT | general |
|---|---|---|---|---|
| authentication_security | - | - | - | - |
| api_security | - | - | - | - |
| data_security | - | - | - | - |
| dependency_security | - | - | - | - |
| logging_security | - | - | - | - |
| file_upload_security | - | - | - | - |
| container_security | - | - | - | - |
| **payment_security** | **-** | - | - | - |
| **cms_security** | - | **-** | - | - |
| **iot_security** | - | - | **-** | - |

**Konsistensi yang harus dibuktikan:**
- Sel-sel pada kolom domain lain di baris `payment_security` (selain e-commerce) = **0** (eksklusivitas)
- Sel-sel pada kolom domain lain di baris `cms_security` (selain blog) = **0**
- Sel-sel pada kolom domain lain di baris `iot_security` (selari IoT) = **0**
- Baris `dependency_security` tinggi di semua domain (dari Trivy CVE scan)

**Dua bukti yang harus disampaikan:**
1. **Coverage inference tidak false positive:** `payment_security` aktif di blog → 0 kasus (Tabel 4.4 + Tabel 4.7 konsisten)
2. **Security analysis konsisten:** Finding yang muncul di coverage tertentu selalu di-tag dengan coverage yang applicable

### 4.5.4 Korelasi Domain Confidence dengan Coverage Consistency (BARU)

**Metrik BARU yang tidak ada di v5** — bukti kontribusi utama kontribusi #1 + #2:

```
CoverageConsistency = proporsi coverage yang applicable dan menghasilkan finding / total coverage applicable

untuk setiap repo r:
  CC_r = (Σ coverage applicable yang punya ≥1 finding) / (Σ total coverage applicable)
```

**Hipotesis:** Repo dengan domain confidence tinggi (≥0.85) akan memiliki CC lebih tinggi daripada repo dengan confidence rendah (<0.7).

**Cara uji:**
- Hitung CC untuk setiap repo
- Kelompokkan repo menjadi 2 bin: high-confidence vs low-confidence
- Bandingkan rata-rata CC
- Visualisasi: scatter plot (confidence vs CC) + trendline

**Bukti kontribusi:** Jika korelasi positif dan signifikan → coverage inference bekerja lebih baik ketika domain detection akurat (sesuai desain). Ini bukti end-to-end sistem bekerja secara kohesif.

**Statistik:** Pearson correlation, Spearman (jika distribusi tidak normal). Target: r ≥ 0.5 dengan p < 0.05.

### 4.5.5 Analisis Komparatif Pipeline: e-commerce vs blog vs IoT

**Tabel 4.8 — Ringkasan komparatif antar domain (RATA-RATA per repo):**

| Metrik | e-commerce | blog | IoT | Selisih (max−min) |
|---|---|---|---|---|
| Jumlah coverage applicable | - | - | - | - |
| Jumlah job dalam workflow | - | - | - | - |
| Jumlah aturan Semgrep AI-generated | - | - | - | - |
| Total finding | - | - | - | - |
| % critical+high finding | - | - | - | - |
| Risk Score (mean) | - | - | - | - |
| Confidence domain (mean) | - | - | - | - |

**Visualisasi:** Bar chart grouped (3 domain × 6 metrik) untuk menunjukkan perbedaan profil setiap domain.

**Narasi:** "Meskipun jumlah coverage applicable serupa (~8–10 per repo), distribusi risk score berbeda secara signifikan antar domain, membuktikan bahwa mekanisme context-aware menghasilkan evaluasi yang sensitif terhadap domain, bukan evaluasi generik."

### 4.5.6 Validasi Cross-Domain: Apakah Pipeline dari Domain A Cocok untuk Domain B? (BARU — Studi Penting)

**WAJIB ada** untuk menjawab pertanyaan "Apa bedanya sistem ini dengan pipeline generik?"

**Desain eksperimen:**

1. **Setup:** Ambil 1 repo e-commerce, 1 repo blog, 1 repo IoT (pilih yang confidence-nya tinggi).
2. **Generate pipeline untuk masing-masing** (sesuai domainnya) → simpan sebagai P_eco, P_blog, P_iot.
3. **Cross-apply:** Jalankan P_eco di repo blog, P_blog di repo e-commerce, dst.
4. **Ukur:**
   - Berapa finding yang terlewat (false negative)?
   - Berapa false positive yang muncul (misalnya, P_eco memindai PCI-DSS di repo blog yang tidak relevan)?
   - Apakah ada job yang error karena dependency tidak ada (misalnya, mqtt-security di repo blog)?

**Tabel 4.9 — Hasil cross-domain application:**

| Pipeline ↓ applied to → | Repo e-com | Repo blog | Repo IoT |
|---|---|---|---|
| **P_eco (e-commerce)** | baseline | FNR=X, FPR=Y, ERR=Z | ... |
| **P_blog (blog)** | ... | baseline | ... |
| **P_iot (IoT)** | ... | ... | baseline |

**Ekspektasi:**
- Diagonal (P_eco → e-com repo) = baseline (terbaik)
- Off-diagonal = degradasi: FNR naik (finding terlewat) ATAU ERR naik (job gagal) ATAU FPR naik (kontrol tidak relevan)

**Kontribusi:** Ini bukti eksperimental paling kuat bahwa "one-size-fits-all pipeline tidak cukup" — selaras dengan argumen di Bab I.

---

## 4.6 Hasil Konten Generatif (Semgrep Rules + Custom Job)

**Konten (dipertahankan dari v5 §4.5):**

### 4.6.1 Aturan Semgrep Generatif (K2.3)

**Tabel 4.10 — Rata-rata jumlah aturan Semgrep AI-generated per domain:**

| Domain | Repo | Rata-rata Aturan | Std Dev | Repo Tanpa Aturan |
|---|---|---|---|---|
| e-commerce | 5–6 | - | - | - |
| blog | 5–6 | - | - | - |
| IoT | 5–6 | - | - | - |
| general | 0–3 | - | - | - |
| **Rata-rata** | **15–18** | - | - | - |

**Metrik validasi (BARU — untuk aturan Semgrep AI):**

| Metrik | Target | Cara Ukur |
|---|---|---|
| **Syntactic validity** | 100% | `semgrep --validate` sukses tanpa error |
| **Semantic relevance** | ≥ 80% | Manual review: apakah pattern relevan dengan domain? (binary) |
| **No-duplicate vs static library** | 100% | Bandingkan ID dengan `static_semgrep_rules.yml` |
| **True positive rate (TPR)** | ≥ 0.60 | Jalankan di repo uji, hitung finding valid / total finding |
| **False positive rate (FPR)** | ≤ 0.30 | Manual review: finding yang sebenarnya bukan vulnerability |

**Hipotesis:**
- H1: e-commerce menghasilkan aturan lebih banyak karena pola kode payment lebih spesifik (Stripe webhook, idempotency key)
- H2: blog menghasilkan aturan lebih sedikit karena pola XSS sudah ter-cover static library

### 4.6.2 Custom Job Generatif (K2.4)

**Tabel 4.11 — Rata-rata custom job AI-generated per domain:**

| Domain | Repo | Rata-rata Custom Job | Std Dev | Repo Tanpa Custom Job |
|---|---|---|---|---|
| e-commerce | 5–6 | - | - | - |
| blog | 5–6 | - | - | - |
| IoT | 5–6 | - | - | - |
| general | 0–3 | - | - | - |

**Metrik validasi:**
- **Structural validity:** 100% (kebab-case, ≤ 40 char, ≥ 2 actions, 1 sarif_upload)
- **Complementarity:** Custom job tidak duplikat dengan standard job atau domain job
- **Execution success:** % custom job yang lulus di `workflow_execution` (target ≥ 90%)

### 4.6.3 Trade-off Analysis: LLM-Generated vs Static

**Perbandingan yang harus ada:**

| Aspek | Static Library (Tier 1) | LLM-Generated (Tier 3) |
|---|---|---|
| Coverage | CWE/OWASP generik | Repo-spesifik |
| Maintenance | Manual update | Otomatis per-repo |
| Precision | Tinggi (rule dikurasi) | Lebih rendah (perlu validasi) |
| Recall | Rendah untuk pola baru | Lebih tinggi untuk pola custom |
| Biaya | $0 (gratis) | Biaya token LLM |

---

## 4.7 Kendala Teknis dan Lessons Learned

**Konten (dipertahankan dari `lampiran-rencana-bab4-20.md` dengan revisi):**

v5 sudah punya sub-bab "Kendala Teknis" yang menyebutkan 5 kendala. Versi baru mempertahankannya, dengan 2 perubahan:

1. **Sesuaikan jumlah repo dari 40 → 15–18** di semua narasi kendala
2. **Tambah 1 kendala baru:** Inkonsistensi output LLM untuk node `pattern_inference` (K2.3) — 2–3 repo menghasilkan aturan Semgrep yang tidak lolos `_validate_ai_generated_rule()`. Mitigasi: retry dengan prompt refinement.

**5 Kendala Final:**

1. Inkonsistensi generasi pipeline (LLM temperature 0,3 masih bervariasi)
2. Konflik dependensi antar job (Python 3.9 vs 3.11)
3. Keterbatasan deteksi domain (low confidence → fallback)
4. Rate limiting GitHub API (5000 req/jam)
5. Keterbatasan inferensi attack surface (lookup table)
6. Inkonsistensi validasi aturan Semgrep AI-generated (BARU)

**Lessons learned:** Wajib ada implikasi untuk v10 (pengembangan selanjutnya):
- LLM deterministik (temperature 0) untuk generation, LLM dengan temperature lebih tinggi untuk ideation
- Lookup table diperluas dengan kombinasi deployment
- Confidence threshold dinaikkan dari 0,7 → 0,75 untuk mengurangi false positive

---

## 4.8 Penggunaan Token LLM dan Analisis Biaya (BARU — Sub-Bab Eksplisit)

v5 sudah punya sub-bab "Penggunaan Token LLM AI Agent MiniMax M3 dan Analisis Biaya" sebagai sub-bab terakhir. Versi baru menjadikannya **sub-bab eksplisit** karena:
- Ini bukti efisiensi biaya (kontribusi praktis selain akademis)
- MiniMax-m3 baru aktif Juni 2026 (lihat rekomendasi-judul.md bagian "MiniMax-m3")
- Pergantian dari Kimi 2.7 Coder → MiniMax-m3 perlu justifikasi eksplisit

**Konten:**

### 4.8.1 Konsumsi Token per Tahapan

**Tabel 4.12 — Rata-rata konsumsi token MiniMax-m3 per tahapan per repo:**

| Tahapan | Node LLM | Token Input (mean) | Token Output (mean) | Biaya USD (mean) |
|---|---|---|---|---|
| Tahap 1 (Repo Context) | technology, architecture, deployment, domain | - | - | - |
| Tahap 2 (Coverage Inference) | coverage, pattern, augmentation, job_reasoning | - | - | - |
| Tahap 4 (Security Evaluation) | security_analysis, recommendation | - | - | - |
| **Total per repo** | 9 LLM calls | - | - | - |
| **Total 15–18 repo** | - | - | - | - |

**Pricing (verifikasi dari rekomendasi-judul.md):**
- Input: $0,30 / M token
- Output: $1,20 / M token
- Prompt caching read: $0,06 / M token

### 4.8.2 Perbandingan Biaya: LLM vs Template Generik

**Tabel 4.13 — Perbandingan biaya pipeline generasi:**

| Pendekatan | Biaya per Repo | Biaya 18 Repo | Coverage Quality | Adaptivitas |
|---|---|---|---|---|
| **Template generik (no LLM)** | $0 | $0 | Rendah | Tidak adaptif |
| **MiniMax-m3 (penelitian ini)** | $X | $Y | Tinggi | Adaptif |
| **GPT-4o (estimasi)** | $8X | $144X | Tinggi | Adaptif |
| **Claude 3.5 Sonnet (estimasi)** | $10X | $180X | Tinggi | Adaptif |

**Narasi:** "MiniMax-m3 dipilih karena biaya 8× lebih murah dari GPT-4o dengan kualitas setara (SWE-Bench Pro 59%). Trade-off: ketergantungan pada model proprietary yang sewaktu-waktu bisa berubah harga."

### 4.8.3 Sensitivitas Biaya terhadap Ukuran Repo

**Plot:** Biaya vs LOC (lines of code) dari 15–18 repo.

**Ekspektasi:** Korelasi positif (repo lebih besar → lebih banyak file → lebih banyak konteks → lebih banyak token). Regresi linear: y = a + b·LOC.

**Implikasi:** Untuk repo > 50k LOC, biaya mungkin tidak ekonomis. Untuk repo < 10k LOC, biaya sangat rendah (< $0.10).

---

## Pemetaan Kontribusi → Hasil Pengujian

**Tabel referensi silang untuk sidang (WAJIB ada di akhir Bab IV sebagai penutup):**

| Kontribusi (dari Bab I) | Dibuktikan di Bab IV | Metrik Kunci |
|---|---|---|
| **K1: Repository Context Analysis** | §4.2 | F1 klasifikasi domain ≥ 0.80, F1 arsitektur ≥ 0.80 |
| **K2: Security Coverage Inference** | §4.3 | Coverage Precision ≥ 0.85, Coverage Recall ≥ 0.80 |
| **K2.3: Pattern Inference (LLM-Generated Rules)** | §4.6.1 | TPR ≥ 0.60, syntactic validity 100% |
| **K2.4: Job Reasoning (Custom Jobs)** | §4.6.2 | Structural validity 100%, execution success ≥ 90% |
| **K3: Pipeline Generation** | §4.4 + §4.5.5 | % SHA pinning ≥ 95%, komparasi antar domain signifikan |
| **K3: Evaluation** | §4.5 | OWASP 3-dim scoring konsisten, Risk Score bervariasi per domain |
| **Efisiensi biaya** | §4.8 | Biaya per repo < $1 (estimasi) |

---

## Metodologi Pengujian (Bagian Pengantar Bab IV)

**WAJIB ada di awal Bab IV (sebelum §4.1)** sebagai sub-bab **"4.0 Metodologi Pengujian"** atau paragraf pengantar:

### 4.0.1 Desain Eksperimen

**Penelitian ini menggunakan metode Design Science Research (DSR)** \cite{hevner2004design, peffers2007design} dengan iterasi:

1. **Iteration 1 (eksplorasi):** 5 repo pilot untuk tuning prompt
2. **Iteration 2 (utama):** 15–18 repo dataset lengkap
3. **Iteration 3 (validasi):** 3 repo untuk studi kasus mendalam (cross-domain)

### 4.0.2 Variabel

| Variabel | Tipe | Sumber |
|---|---|---|
| **Independen:** Domain (e-commerce, blog, IoT) | Kategorik (3 level) | Manual labeling |
| **Independen:** Arsitektur (monolitik) | Kategorik (1 level) | Manual labeling |
| **Dependen:** Coverage applicable | Biner (per coverage) | Output `coverage_inference` |
| **Dependen:** Risk Score (0–100) | Kontinu | Output `risk_assessor` |
| **Dependen:** Jumlah job, % SHA pinning, dll | Kontinu / biner | Output `workflow_validation` |
| **Kontrol:** Bahasa pemrograman (JS/TS) | Kategorik | Seleksi dataset |
| **Kontrol:** Ukuran repo (LOC) | Kontinu | Tidak dikontrol (variasi alamiah) |

### 4.0.3 Alat Pengumpulan Data

- **Backend (Go/Gin):** Logging ke PostgreSQL via `pipeline_analyses` table
- **AI Service (Python/FastAPI):** Logging ke file JSON per run
- **GitHub Actions:** Workflow logs + SARIF output
- **Manual labeling:** CSV oleh Iqbal untuk ground truth (domain, arsitektur, expected coverage)

### 4.0.4 Prosedur Pengujian

```
Untuk setiap repo r ∈ Dataset:
  1. Jalankan Flow A (run_repo_pipeline) end-to-end
  2. Simpan seluruh output state ke DB
  3. Bandingkan prediksi dengan ground truth
  4. Hitung metrik (Precision/Recall/F1, Risk Score, dll)
  5. Verifikasi YAML via actionlint
  6. Trigger workflow execution di GitHub Actions (untuk sub-eksperimen tertentu)
  7. Kumpulkan SARIF findings untuk analisis §4.5
```

### 4.0.5 Validitas & Bias

| Ancaman | Mitigasi |
|---|---|
| **Selection bias:** Repo open-source lebih matang dari proprietary | Disebutkan sebagai **batasan B1** di Bab I |
| **LLM non-determinism:** Output LLM bisa beda tiap run | Temperature 0,3; rerun 2× untuk repo kritis; laporkan std dev |
| **Manual labeling bias:** Ground truth subjektif | Double-labeling oleh Iqbal + 1 reviewer; Cohen's κ ≥ 0.7 |
| **Sample size kecil (15–18):** Statistik inferensial terbatas | Gunakan statistik deskriptif + bootstrap CI; hindari overclaim |
| **Generalizability:** JS/TS only | Disebutkan sebagai **batasan** di Bab I |

---

## Catatan Perubahan dari v5 ke v Baru (Checklist)

| Sub-Bab v5 | Sub-Bab v Baru | Status | Perubahan Utama |
|---|---|---|---|
| (tidak ada) | §4.0 Metodologi Pengujian | **BARU** | Wajib untuk konteks pengujian |
| §4.1 Justifikasi Tools | §4.1 Justifikasi Tools | Dipertahankan | Tambah sitasi Zhou et al., Benedetti, Meli |
| §4.2 Hasil Coverage Inference (40 repo, 7 domain) | §4.2 Hasil Repository Context Analysis | **REVISI BESAR** | Ganti nama, refocus ke K1, dataset 15–18/3 domain, tambah confusion matrix |
| §4.3 Hasil Generasi Pipeline (40 repo, 7 domain) | §4.3 Hasil Security Coverage Inference | **REVISI BESAR** | Geser fokus ke K2, tambah metrik Precision/Recall coverage, tambah §4.3.4 paragraf teoretis |
| §4.3 (lanjutan) | §4.4 Hasil Generasi Pipeline | **REVISI** | 3 domain job (bukan 5), tambah metrik action_registry compliance |
| §4.4 Evaluasi Security per Domain | §4.5 Evaluasi Kualitas Pipeline Multi-Dimensi | **REVISI BESAR** | Ganti rumus dari OWASP L×I → OWASP 3-dim, tambah 3 sub-bab baru (4.5.4, 4.5.5, 4.5.6) |
| §4.5 Konten Generatif | §4.6 Hasil Konten Generatif | Dipertahankan | Tambah metrik TPR/FPR/Syntactic validity untuk Semgrep AI |
| §4.6 Validitas Workflow YAML | §4.4.2 (digabung) | **REFACTOR** | Pindah ke §4.4 karena lebih cocok di sub-bab pipeline |
| §4.7 Kendala Teknis | §4.7 Kendala Teknis | Dipertahankan | Update jumlah repo 40→15–18, tambah 1 kendala K2.3 |
| (tidak ada) | §4.8 Penggunaan Token LLM | **EKSPLISIT** | v5 sudah ada isinya, dijadikan sub-bab mandiri |
| (tidak ada, tersebar) | Tabel kontribusi→pengujian | **BARU** | Untuk memudahkan dosen memverifikasi klaim |

---

## Daftar Rujukan Baru yang Wajib Ada di `references.bib` (sitasi baru di Bab IV)

| Key | Referensi | Digunakan di § |
|---|---|---|
| `hevner2004design` | Hevner et al. (2004), MIS Quarterly | §4.0.1 |
| `peffers2007design` | Peffers et al. (2007), JMIS | §4.0.1 |
| `meneely2013patch` | Meneely et al. (2013), ESEM | §4.2.2, §4.3.4, §4.4.4 |
| `matter2025context` | Matter et al. (2025), Comp. Sci. Review | §4.2.2, §4.3.4, §4.4.4 |
| `trabelsi2025systematic` | Trabelsi et al. (2025) | §4.2.3 (justifikasi 2-tipe arsitektur) |
| `benedetti2022automatic` | Benedetti et al. (2022), ACM SCORED | §4.1 (justifikasi tools) |
| `meli2019secret` | Meli et al. (2019), NDSS | §4.1 (justifikasi tools) |
| `zhou2024comparison` | Zhou et al. (2024), arXiv | §4.1 (justifikasi Semgrep) |
| `owasp2021top10` | OWASP Foundation (2021) | §4.4, §4.5.1 |
| `cwe2024mitre` | MITRE (2024) | §4.4, §4.5.1 |
| `minimax2026m3` | MiniMax (2026) | §4.8 (pricing) |
| `opencode2025` | OpenCode (2025) | §4.8 (framework) |
| `owasp_risk_rating` | OWASP Risk Rating Methodology | §4.5.1 (rumus 3-dim) |
| `nist80030` | NIST SP 800-30 Rev. 1 | §4.5.1 (legitimasi risk methodology) |

**Yang sudah ada di v5 (tidak perlu ditambah):**
- `cheenepalli2025advancing` (di Bab I, dirujuk di §4.1)
- `manadhata2010attack` (di Bab II, bisa dirujuk di §4.2)

---

## Rencana Eksekusi Revisi

| No | Task | File Target | Estimasi | Prioritas |
|---|---|---|---|---|
| 1 | Buat `chapter-4-v6.tex` dengan struktur 8 sub-bab di atas | `naskah/skripsi/contents/chapter-4/` | 4–6 jam | **Wajib** |
| 2 | Update dataset tabel dari 40/7 → 15–18/3 domain | `chapter-4-v6.tex` §4.2.1 | 30 menit | **Wajib** |
| 3 | Tambah sub-bab §4.0 Metodologi Pengujian | `chapter-4-v6.tex` | 1 jam | **Wajib** |
| 4 | Refactor §4.5 dari OWASP L×I → OWASP 3-dim | `chapter-4-v6.tex` §4.5.1–§4.5.6 | 2 jam | **Wajib** |
| 5 | Tambah studi kasus cross-domain §4.5.6 | `chapter-4-v6.tex` | 1 jam | **Wajib** |
| 6 | Tambah paragraf teoretis di §4.3 dan §4.4 (T5) | `chapter-4-v6.tex` | 30 menit | **Wajib** |
| 7 | Update semua tabel placeholder (40→15–18) | `chapter-4-v6.tex` | 1 jam | **Wajib** |
| 8 | Tambah 14 sitasi baru | `references.bib` | 30 menit | **Wajib** |
| 9 | Update sitasi di dalam teks | `chapter-4-v6.tex` | 1 jam | **Wajib** |
| 10 | Run pdflatex, cek error | `main.tex` | 30 menit | **Wajib** |
| 11 | Cross-check dengan Bab I (kontribusi→pengujian) | `chapter-1.tex` + `chapter-4-v6.tex` | 1 jam | **Wajib** |
| 12 | Cross-check dengan Bab III (rencana→realisasi) | `chapter-3.tex` + `chapter-4-v6.tex` | 1 jam | **Wajib** |

**Total estimasi:** 14–18 jam kerja.

---

## Validasi Akhir (Self-Check Sebelum Submit)

Sebelum finalisasi, verifikasi checklist berikut:

- [ ] Judul di `main.tex` = Rekomendasi 1 ("Model Adaptive Security Assessment Pipeline...")
- [ ] Abstrak sudah menyebut "security assessment" bukan "DevSecOps"
- [ ] Batasan penelitian = 8 butir (B1–B8) di Bab I
- [ ] Dataset di Bab III = 15–18 repo / 3 domain
- [ ] Dataset di Bab IV = 15–18 repo / 3 domain (konsisten)
- [ ] Justifikasi 10 coverages = OWASP + CWE hybrid (ada di Bab III, dirujuk di Bab IV §4.3)
- [ ] Scoring di Bab IV = OWASP 3-dim (bukan L×I)
- [ ] Tiap kontribusi (K1, K2, K2.3, K2.4, K3) punya sub-bab bukti di Bab IV
- [ ] Paragraf teoretis "bukan temuan baru" ada di §4.3 dan §4.4
- [ ] Sitasi baru ada di `references.bib`
- [ ] Tabel kontribusi→pengujian ada di akhir Bab IV
- [ ] Sub-bab "Metodologi Pengujian" di awal Bab IV
- [ ] Studi kasus cross-domain §4.5.6 ada (justifikasi one-size-fits-all tidak cukup)

---

> **Catatan akhir:** Dokumen ini adalah acuan revisi, bukan naskah akhir. Eksekusi aktual memerlukan:
> 1. Eksekusi eksperimen 15–18 repo untuk mengisi semua tabel (saat ini masih 0)
> 2. Iterasi prompt LLM jika F1 klasifikasi < 0.80
> 3. Konfirmasi final ke Pak Ridi sebelum sidang
