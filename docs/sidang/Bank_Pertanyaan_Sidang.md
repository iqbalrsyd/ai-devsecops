# BANK PERTANYAAN SIDANG SKRIPSI

> **Judul:** AI-Powered Adaptive DevSecOps Pipeline Engineer untuk Automasi CI/CD Security Workflow berbasis Repository Context
> **Mahasiswa:** Iqbal Rasyad
> **Tanggal Terakhir Update:** 14 Juli 2026
> **Jumlah Pertanyaan:** 125
> **Progress Latihan:** 60% (prioritas HIGH sudah dipersiapkan)

---

## STATISTIK PER KATEGORI

| # | Kategori | Jumlah | Prioritas |
|---|---|---|---|
| 1 | Pertanyaan Umum Sidang | 27 | HIGH: 17, MEDIUM: 7, LOW: 3 |
| 2 | BAB I — Pendahuluan | 5 | HIGH: 4, MEDIUM: 1 |
| 3 | BAB II — Tinjauan Pustaka | 8 | HIGH: 5, MEDIUM: 3 |
| 4 | BAB III — Metodologi | 9 | HIGH: 6, MEDIUM: 3 |
| 5 | BAB IV — Implementasi & Hasil | 13 | HIGH: 8, MEDIUM: 4, LOW: 1 |
| 6 | BAB V — Kesimpulan | 4 | HIGH: 3, MEDIUM: 1 |
| 7 | Source Code | 6 | HIGH: 1, MEDIUM: 1, LOW: 4 |
| 8 | Prototype | 6 | HIGH: 1, MEDIUM: 2, LOW: 3 |
| 9 | Demo | 3 | HIGH: 2, MEDIUM: 1 |
| 10 | DevSecOps | 7 | HIGH: 4, MEDIUM: 3 |
| 11 | AI / LLM | 7 | HIGH: 2, MEDIUM: 5 |
| 12 | Security | 5 | HIGH: 1, MEDIUM: 4 |
| 13 | Penguji Iseng | 10 | HIGH: 4, MEDIUM: 5, LOW: 1 |
| 14 | Software Engineering | (merged ke Source Code) | - |
| 15 | Critical Questions | 15 | HIGH: 15 |

## TINGKAT KESULITAN

| Level | Jumlah |
|---|---|
| ⭐ (Mudah) | 3 |
| ⭐⭐ (Menengah) | 38 |
| ⭐⭐⭐ (Sulit) | 46 |
| ⭐⭐⭐⭐ (Sangat Sulit) | 19 |
| ⭐⭐⭐⭐⭐ (Kritis) | 19 |

## REKOMENDASI LATIHAN SIDANG

1. **Prioritas pertama:** Critical Questions (Q115-Q125) — ini pertanyaan yang bisa menjatuhkan.
2. **Prioritas kedua:** BAB IV (Q061-Q074) — pertanyaan tentang hasil dan data.
3. **Prioritas ketiga:** BAB III (Q052-Q060) — metodologi dan design decisions.
4. **Prioritas keempat:** BAB II (Q042-Q051) — teori dan literature review.
5. **Prioritas kelima:** Penguji Iseng (Q105-Q114) — pertanyaan jebakan yang umum.

**Tips latihan:** Latih jawaban singkat (30 detik) dulu. Setelah lancar, baru latih jawaban detail (3 menit).

---

## Q028

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa yang terjadi jika LLM provider down? Apakah sistem masih berfungsi?

**Jawaban Ideal:**
Setiap node LLM memiliki fallback deterministik:

1. **Fallback berfungsi penuh:** `technology_detection` → extension-based detection (akurasi ~0.6). `deployment_detection` → file-pattern scan. `domain_detection` → heuristic scoring → "general" default. `coverage_inference` → heuristic scoring (threshold-based). `pipeline_augmentation` → static `DEFAULT_AUGMENTATIONS` dict (15 coverage × predefined jobs).

2. **Fallback menghasilkan output minimal tapi valid:** `pattern_inference` (K2.3) → skip (empty rules). `job_reasoning` (K2.4) → 1 deterministic fallback job. `recommendation_generation` → hardcoded recommendations per finding type.

3. **Yang tidak bisa fallback:** `architecture_detection` → hardcoded "monolithic" (sesuai R2.1). Ini tidak masalah karena arsitektur memang bukan variabel.

4. **Risk:** Tanpa LLM, generated pipeline menjadi generic (standard jobs + static augmentations). Kehilangan custom Semgrep rules (K2.3) dan custom jobs (K2.4). Hasil validasi menunjukkan ini terjadi pada AI Service (chatbot-waha) — 0 coverages applicable, 0 custom jobs.

**Jawaban Singkat (30 detik):**
Ya, masih berfungsi tapi dengan fitur minimal. Setiap node LLM punya fallback deterministik, tapi kehilangan kemampuan generative AI (custom rules, custom jobs).

**Alasan Penguji Bertanya:**
Robustness terhadap kegagalan dependensi eksternal adalah karakteristik sistem production. Terlebih setelah 1 dari 4 repositori gagal karena AI service fallback.

**Kemungkinan Follow-up:**
- Berapa persen akurasi yang hilang tanpa LLM?
- Apakah fallback deterministik cukup baik?
- Ini bukti bahwa ketergantungan LLM terlalu tinggi?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q029

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Kenapa repositori ke-4 (AI Service) gagal total? Itu kan sistem Anda sendiri?

**Jawaban Ideal:**
Ini ironis — sistem saya sendiri gagal menganalisis dirinya sendiri. Analisis kegagalan:

1. **Root cause:** "Pipeline metadata was not available when the PDF was generated. Showing synthetic defaults." AI service tidak merespons dengan benar saat pengujian — kemungkinan karena race condition atau timeout.

2. **Kenapa bisa terjadi:** Sistem chatbot-waha (Go + Python) tidak memiliki file `package.json`/`setup.py`/`requirements.txt` yang standar, sehingga teknologi detection fallback ke `general` tanpa confidence.

3. **Implikasi:** Ini justru membuktikan argumen penting — **sistem sangat bergantung pada ketersediaan AI service.** Tanpa LLM, kualitas output turun drastis (0 coverages, 0 jobs, 2 findings). Ini dicatat sebagai temuan di Bab V §5.1.4.

4. **Lesson learned:** Perlu health check + retry sebelum eksekusi pipeline. Strategi fallback yang lebih robust (saat ini terlalu aggressive ke empty).

**Jawaban Singkat (30 detik):**
Ironis. AI service saya sendiri gagal merespons saat pengujian. Membuktikan bahwa sistem sangat bergantung pada LLM — tanpa itu, output minimal/hampir kosong.

**Alasan Penguji Bertanya:**
Penguji akan sangat tertarik dengan kegagalan ini. Ini adalah bukti jujur tentang ketergantungan sistem pada AI.

**Kemungkinan Follow-up:**
- Apakah ini membuat kredibilitas sistem dipertanyakan?
- Kenapa tidak di-test ulang sampai berhasil?
- Apakah Anda tahu root cause pastinya?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q030

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Ceritakan evolusi desain sistem Anda dari awal sampai v9.5.

**Jawaban Ideal:**
Evolusi melalui 4 versi mayor:

**v5 (baseline):** 40 repositori, 5 domain termasuk microservices-specific pipeline. Problem: terlalu ambisius.

**v7:** Refokus ke 3 domain (e-commerce, blog, IoT), arsitektur diseragamkan jadi monolithic. 16 node, 8 LLM calls. Belum ada konsep security coverage.

**v8:** Perbaikan flow, 16 node, 1 prompt gabung untuk semua security inference. Problem: 1 prompt terlalu besar (lossy).

**v9 (23 Juni):** Konsep security coverage diperkenalkan. 18 node, 9 LLM calls. Coverage inference dan pipeline augmentation dipisah jadi 2 node.

**v9.3 (26 Juni, current):** 18 node, 11 LLM calls. K2.3 `pattern_inference` dan K2.4 `job_reasoning` ditambahkan. Workflow repair jadi dormant.

**v9.5 (1 Juli, testing):** CVSS-driven job generation node ditambahkan (belum di-evaluasi di Bab IV).

**Jawaban Singkat (30 detik):**
v5 (40 repo, 5 domain, microservices) → v7 (3 domain, monolithic only) → v9 (security coverage concept) → v9.3 (AI-generated rules + custom jobs) → v9.5 (CVSS-driven jobs).

**Alasan Penguji Bertanya:**
Iteratif refinement adalah tanda penelitian yang matang. Penguji ingin melihat proses berpikir.

**Kemungkinan Follow-up:**
- Kenapa microservices di-drop?
- Apakah refokus ke 3 domain adalah langkah mundur?
- Evolusi ini iterasi DSR atau development sprint?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 2. BAB I — PENDAHULUAN

---

## Q031

**Kategori:** BAB I — Latar Belakang

**Pertanyaan:**
Apa urgensi penelitian ini di era AI dan DevSecOps?

**Jawaban Ideal:**
Urgensi ada pada konvergensi dua tren:

1. **DevSecOps adoption:** Gartner memperkirakan 70% organisasi akan mengadopsi DevSecOps pada 2026. Namun, pipeline security masih dikonfigurasi manual oleh engineer — error-prone, inconsistent, dan slow.

2. **AI code generation:** Tools seperti GitHub Copilot dan ChatGPT menghasilkan kode dengan kecepatan yang tidak bisa diimbangi oleh human code reviewer. Pipeline security yang statis tidak bisa mengimbangi volume kode yang di-generate AI.

3. **Supply chain attacks meningkat:** SolarWinds (2020), Codecov (2021), 3CX (2023) — semuanya mengeksploitasi kelemahan di CI/CD pipeline. Pipeline yang tidak aman adalah attack vector.

4. **Kerentanan mengelompok per domain:** Penelitian Meneely et al. (2013) dan Matter et al. (2025) menunjukkan bahwa jenis kerentanan berkorelasi dengan domain aplikasi. Namun tidak ada tools yang mengoperasionalisasi temuan ini.

Urgensi: pipeline security harus menjadi automated, adaptive, dan domain-aware — bukan manual, statis, dan generik.

**Jawaban Singkat (30 detik):**
70% organisasi adopsi DevSecOps tapi pipeline masih manual. Kode di-generate AI makin cepat. Supply chain attacks meningkat. Pipeline security harus otomatis dan adaptif.

**Alasan Penguji Bertanya:**
Latar belakang harus membangun urgensi. Mengapa sekarang? Mengapa penting?

**Kemungkinan Follow-up:**
- Statistik 70% dari mana?
- Apakah ada insiden supply chain di Indonesia?
- Kenapa baru sekarang ada penelitian ini?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q032

**Kategori:** BAB I — Latar Belakang

**Pertanyaan:**
Anda menyebut "AI-powered." Apa sebenarnya peran AI di sistem Anda?

**Jawaban:**
AI (LLM) digunakan untuk reasoning, bukan untuk generation:

1. **Context understanding (4 node):** Mendeteksi teknologi, arsitektur, deployment, dan domain dari source code — tugas yang membutuhkan pemahaman semantik, bukan sekadar regex.

2. **Security reasoning (4 node):** Menginferensi coverage applicable, men-generate custom rules (K2.3), mendesain job (K2.4), menentukan augmentasi — butuh pemahaman hubungan antara library, framework, dan jenis kerentanan.

3. **Finding enrichment (2 node):** Memperkaya findings dengan OWASP category, CWE, recommendation, before/after code examples — LLM lebih baik dalam menghasilkan penjelasan natural language.

**Yang TIDAK pakai AI:** Workflow generation (deterministic, 5,808 baris), validasi, deployment, formatting. Saya sengaja memisahkan generation dari reasoning untuk menjamin determinisme.

**Jawaban Singkat (30 detik):**
AI untuk reasoning (analisis, klasifikasi, rekomendasi). BUKAN untuk generation (YAML, deployment). Generation deterministic biar hasilnya terpercaya.

**Alasan Penguji Bertanya:**
Istilah "AI-powered" sering overclaimed. Perlu klarifikasi di mana letak AI-nya.

**Kemungkinan Follow-up:**
- Apakah "AI reasoning" ini benar-benar AI atau sekadar LLM prompt?
- Kenapa tidak pakai AI untuk YAML generation juga?
- Dimana letak "intelligence"-nya selain prompt LLM?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q033

**Kategori:** BAB I — Rumusan Masalah

**Pertanyaan:**
Apa rumusan masalah utama yang Anda jawab?

**Jawaban:**
"Bagaimana mengembangkan sistem AI agent yang dapat secara otonom menganalisis konteks repositori, menginferensi kebutuhan keamanan (security coverages) yang sesuai, dan menghasilkan pipeline CI/CD yang aman dan adaptif?"

Dijabarkan menjadi 3 research question:
1. Seberapa akurat deteksi konteks repositori dan inferensi security coverage?
2. Seberapa lengkap pipeline yang dihasilkan?
3. Seberapa efektif pipeline dalam mendeteksi kerentanan?

**Jawaban Singkat (30 detik):**
Bagaimana membuat AI agent yang otomatis menghasilkan pipeline CI/CD aman yang disesuaikan dengan konteks repositori, bukan template statis.

**Alasan Penguji Bertanya:**
Rumusan masalah harus jelas dan menjawab gap yang diidentifikasi di latar belakang.

**Kemungkinan Follow-up:**
- Apakah rumusan masalah ini terlalu teknis?
- Apakah RQ1, RQ2, RQ3 benar-benar menjawab rumusan masalah?
- Di mana letak kontribusi di rumusan masalah?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q034

**Kategori:** BAB I — Tujuan

**Pertanyaan:**
Apakah tujuan penelitian sudah tercapai?

**Jawaban:**
Sebagian besar ya, dengan catatan:

**Tercapai:**
- Sistem AI agent 4-tahap berhasil dikembangkan dan berfungsi
- Pipeline dihasilkan dan divalidasi untuk 3 dari 4 repositori
- 272 security findings terdeteksi
- Kontribusi K2 (security coverage inference) tervalidasi

**Tercapai dengan keterbatasan:**
- Akurasi domain detection rendah (semua "general" — confidence tinggi tapi salah)
- Coverage applicable rata-rata 30% (under-detection)
- Ground truth detection rate 0% (meski ini bukan kegagalan sistem, tapi keterbatasan SAST yang terdokumentasi)

**Belum tercapai:**
- CVSS-driven job generation (diimplementasikan setelah pengujian, belum di-evaluasi)
- Multi-run replikasi (baru 1×)
- User study

**Jawaban Singkat (30 detik):**
Tujuan utama tercapai (sistem berfungsi, pipeline dihasilkan). Tapi hasil evaluasi menunjukkan keterbatasan yang dicatat sebagai future work.

**Alasan Penguji Bertanya:**
Alignment antara tujuan dan hasil. Jika tujuan tidak tercapai, perlu justifikasi.

**Kemungkinan Follow-up:**
- Kalau detection rate 0%, apakah tujuan RQ3 tercapai?
- Apakah perlu revisit tujuan penelitian?
- Kenapa tujuan tidak disesuaikan di tengah jalan?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q035

**Kategori:** BAB I — Batasan

**Pertanyaan:**
Mengapa Anda membatasi hanya 3 domain? Bukankah lebih baik mencakup semua?

**Jawaban:**
Keputusan ini diambil pada R2.2 (revisi scope):

**Alasan:**
1. **Ground truth CVE:** E-commerce, blog, dan IoT memiliki CVE ground truth yang terdokumentasi dengan baik. Healthcare dan fintech membutuhkan akses ke sistem proprietary yang sulit direproduksi di lingkungan penelitian.

2. **Complexity management:** 15 security coverages × 7 domain = 105 kemungkinan kombinasi. Dengan 3 domain + general, sisa 60 kombinasi — lebih manageable untuk penelitian S1.

3. **Feasibility:** Setiap domain butuh custom Semgrep rules dan domain knowledge base. Untuk 3 domain, total 5 file YAML rules (ecommerce.yml, blog-csp.yml, iot-mqtt.yml, owasp-api.yml, general_knowledge_base.yml). Ini sudah signifikan.

4. **Research focus:** Memperdalam 3 domain (analisis kualitatif) lebih baik daripada mendangkalkan 7 domain (analisis superfisial).

**Jawaban Singkat (30 detik):**
3 domain cukup untuk membuktikan konsep. 7 domain akan terlalu luas untuk skripsi S1. Fokus pada kedalaman, bukan lebar cakupan.

**Alasan Penguji Bertanya:**
Batasan harus dijustifikasi. "3" adalah angka yang terlihat kecil untuk sistem yang diklaim "adaptive."

**Kemungkinan Follow-up:**
- Apakah sistem bisa langsung support 7 domain tanpa perubahan arsitektur?
- Bagaimana dengan domain yang belum ada (gaming, blockchain)?
- Kenapa tidak 5 domain sebagai kompromi?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q036

**Kategori:** BAB I — Batasan

**Pertanyaan:**
Kenapa arsitektur microservices tidak dideteksi? Padahal tren industri ke microservices.

**Jawaban:**
Keputusan R2.1: arsitektur BUKAN variabel eksperimen.

**Alasan:**
1. **Research focus:** Penelitian fokus pada domain sebagai variabel, bukan arsitektur. Menambah variabel arsitektur akan melipatgandakan kompleksitas (3 domain × 2 arsitektur = 6 kombinasi) tanpa menambah kontribusi signifikan pada K2 (security coverage inference).

2. **Reality check:** Dari 4 repositori yang diuji, ThingsBoard adalah microservices tapi sistem mendeteksinya sebagai monolithic. Ini jujur dicatat sebagai batasan di §4.9.

3. **Pipeline simplification:** Untuk monolithic, pipeline lebih sederhana (1 set jobs). Microservices akan butuh matrix strategy, per-service jobs, inter-service testing — menambah kompleksitas signifikan.

4. **Generalisasi:** Meski tidak mendeteksi microservices, sistem tetap bisa men-scan repositori microservices karena Semgrep/Trivy/Gitleaks tidak peduli arsitektur. Hanya pipeline YAML yang lebih simpel.

**Jawaban Singkat (30 detik):**
Fokus di domain, bukan arsitektur. Microservices akan melipatgandakan kompleksitas tanpa menambah kontribusi ke K2. Diakui sebagai batasan.

**Alasan Penguji Bertanya:**
Microservices adalah arsitektur dominan. Membatasi ini terlihat mundur (melawan tren industri).

**Kemungkinan Follow-up:**
- Apakah ThingsBoard yang microservices gagal karena keterbatasan ini?
- Bagaimana ke depannya?
- Apakah K8s bisa di-support tanpa deteksi microservices?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q037

**Kategori:** BAB I — Kontribusi

**Pertanyaan:**
Anda mengklaim kontribusi K2 sebagai novelty. Tapi bukankah "mendeteksi library lalu memilih security tools" adalah hal yang trivial?

**Jawaban:**
Tidak trivial. Berikut kenapa:

1. **Abstraksi formal:** Konsep "security coverage" adalah abstraksi baru. Sebelumnya tidak ada terminologi standar yang menghubungkan "Stripe SDK terdeteksi" dengan "perlu secret scan fokus Stripe + SAST aturan PCI-DSS + SCA untuk stripe-node."

2. **Multi-layer reasoning:** Sistem tidak sekadar `if stripe then pci-dss`. Ada 4 layer reasoning: (a) coverage inference dari konteks, (b) pattern inference untuk generate rules spesifik, (c) augmentation mapping coverages ke jobs + configuration, (d) job reasoning untuk desain job custom. Ini bukan lookup table sederhana.

3. **Domain-specific adaptation:** E-commerce dengan Stripe vs e-commerce dengan Midtrans punya profiling risiko berbeda. Sistem menangkap ini melalui `domain_sub_type` detection dan meneruskannya ke semua downstream reasoning.

4. **Empirical evidence:** 27 finding unik di ThingsBoard dari custom job `container-compose-hardening` tidak akan terdeteksi tanpa reasoning K2.4 yang menganalisis >20 docker-compose files dan memutuskan untuk membuat job validasi security_opt.

**Jawaban Singkat (30 detik):**
Bukan sekadar if-else. Ada 4 layer LLM reasoning yang menghasilkan keputusan kompleks: coverage inference → rule generation → augmentation → job design. 27 finding di ThingsBoard dari custom job adalah bukti reasoning yang tidak trivial.

**Alasan Penguji Bertanya:**
Mempertanyakan novelty adalah tugas utama penguji. Klaim novelty harus dipertahankan dengan argumen kuat.

**Kemungkinan Follow-up:**
- Apakah 27 finding itu benar-benar "finding baru" atau sekadar "temuan yang kebetulan ter-scan"?
- Apakah coverage inference bisa diganti dengan lookup table ML?
- Di mana letak "intelligence" kalau fallback-nya deterministik?

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q038

**Kategori:** BAB I — Latar Belakang

**Pertanyaan:**
Apakah ada penelitian sebelumnya yang mirip dengan Anda? (Compare & contrast)

**Jawaban:**
Penelitian terkait:

1. **Hummer et al. (2015) — Automated Deployment Models:** Mengotomasi deployment via Infrastructure-as-Code. Bedanya: fokus pada deployment, bukan security pipeline generation. Tidak ada AI reasoning.

2. **Pashchenko et al. (2018) — Comparison of Vulnerability Detection Tools:** Membandingkan efektivitas SAST/SCA/DAST tools. Sangat relevan untuk justifikasi pemilihan tools di sistem saya. Tapi penelitian mereka tidak meng-generate pipeline — hanya mengevaluasi tools.

3. **Meneely et al. (2013) — Vulnerability Clustering per Domain:** Membuktikan bahwa kerentanan mengelompok per domain aplikasi. Ini adalah landasan teori untuk penelitian saya. Tapi mereka tidak membangun sistem.

4. **Matter et al. (2025) — Context-Aware Security:** Survey tentang context-aware security. Mendukung argumen bahwa konteks repositori relevan untuk keputusan keamanan. Tapi mereka tidak memberikan implementasi.

**Posisi saya:** Di intersection — mengoperasionalisasi temuan Meneely (vuln clustering) dan Matter (context-aware security) ke dalam sistem pipeline generation yang berfungsi.

**Jawaban Singkat (30 detik):**
Ada penelitian tentang deployment automation dan vulnerability detection secara terpisah, tapi tidak ada yang mengoperasionalisasi temuan "vulnerability clustering per domain" ke dalam pipeline generation. Itu gap saya.

**Alasan Penguji Bertanya:**
Literature review untuk Bab II. Positioning terhadap penelitian existing.

**Kemungkinan Follow-up:**
- Paper mana yang paling dekat dengan penelitian Anda?
- Apa state of the art di DevSecOps pipeline generation?
- Apakah ada penelitian dari Indonesia yang serupa?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q039

**Kategori:** BAB I — Manfaat

**Pertanyaan:**
Siapa yang akan mendapat manfaat dari penelitian ini dan bagaimana mengukurnya?

**Jawaban:**
Tiga stakeholder dengan manfaat berbeda:

1. **Developer (manfaat: efisiensi):** Tidak perlu menulis pipeline security dari nol. Metric: waktu yang dihemat (dari ~2-4 jam manual menjadi <1 menit automated).

2. **Security engineer (manfaat: akurasi):** Pipeline yang di-generate menangkap security coverage yang mungkin terlewat jika dikonfigurasi manual. Metric: coverage applicable yang terdeteksi vs yang terlewat.

3. **Engineering manager (manfaat: compliance):** Pipeline yang seragam dan terukur di semua repositori. Metric: compliance score, konsistensi pipeline antar repo.

4. **Startup founder (manfaat: biaya):** Tidak perlu hire DevSecOps engineer. Metric: biaya yang dihemat ($0.03/repo vs $X/month salary).

**Jawaban Singkat (30 detik):**
Developer hemat waktu, security engineer dapat coverage analysis, manager dapat compliance, startup hemat biaya.

**Alasan Penguji Bertanya:**
Manfaat harus terukur dan spesifik per stakeholder, bukan sekadar "bermanfaat bagi masyarakat."

**Kemungkinan Follow-up:**
- Apakah Anda sudah mengukur manfaat ini secara kuantitatif?
- Bagaimana cara memvalidasi penghematan waktu?
- Apakah developer benar-benar butuh ini?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q040

**Kategori:** BAB I — Latar Belakang

**Pertanyaan:**
Anda menyebut "adaptive pipeline" berkali-kali. Apa definisi adaptif di sini?

**Jawaban:**
Adaptif = pipeline yang menyesuaikan dengan konteks repositori pada 3 level:

1. **Level bahasa/framework:** Node.js → `npm audit`, Python → `pip-audit`, Java → Maven + Trivy. Tidak semua repo di-scan dengan tools yang sama.

2. **Level domain:** E-commerce → aturan PCI-DSS, secret scan fokus payment keys. Blog → aturan CSP headers, XSS content. IoT → aturan MQTT TLS, firmware signature. Domain menentukan ruleset Semgrep dan jenis job tambahan.

3. **Level fitur bisnis:** Fitur terdeteksi (authentication, payment, file upload, MQTT) menentukan 15 security coverages yang applicable, yang kemudian menentukan job + konfigurasi + custom rules + custom job design.

Adaptif ≠ generative (tidak pakai LLM untuk generate YAML). Adaptif = parameterisasi deterministic generator berdasarkan reasoning dari Tahap 1-2.

**Jawaban Singkat (30 detik):**
Pipeine berubah berdasarkan bahasa (tools), domain (ruleset), dan fitur bisnis (security coverages) dari repositori yang dianalisis. Bukan template statis.

**Alasan Penguji Bertanya:**
Istilah "adaptif" perlu definisi operasional yang jelas. Tanpa definisi, klaim tidak bisa diverifikasi.

**Kemungkinan Follow-up:**
- Apakah "adaptif" Anda lebih baik dari "template parameterized"?
- Di mana batas antara "adaptif" dan "overfitting"?
- Apakah adaptive pipeline bisa salah adaptasi?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---


**Ikhtisar Penelitian:**
Sistem AI agent 4-tahap (18 node LangGraph) yang secara otonom:
1. Menganalisis konteks repositori (bahasa, framework, arsitektur, deployment, domain)
2. Menginferensi 15 security coverages yang applicable berdasarkan konteks repositori
3. Men-generate GitHub Actions workflow YAML yang secure + membuat branch + PR
4. Menganalisis hasil scan keamanan dan membuat laporan PDF

**Dataset:** 4 repositori (django-oscar e-commerce, Ghost blog/CMS, ThingsBoard IoT, AI Service general) × 1 run
**Hasil:** 272 security findings, CVSS sum 1,463, ground truth detection rate 0% (14 target CVE)

**Teknologi:** Go/Gin backend, Python/FastAPI AI service, React/TypeScript frontend, PostgreSQL, Redis, Docker, GitHub Actions, Semgrep, Trivy, Gitleaks, LangGraph, OpenRouter/MiniMax-m3

---

# 1. PERTANYAAN UMUM SIDANG

---

## Q001

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Ceritakan penelitian Anda dalam 3 menit.

**Jawaban Ideal:**
Penelitian ini membangun sistem AI agent yang dapat secara otomatis menghasilkan dan men-deploy pipeline CI/CD yang aman di GitHub Actions secara otonom. Ketika pengguna menghubungkan repositori GitHub, sistem akan melalui 4 tahap. Tahap 1: menganalisis konteks repositori — mendeteksi bahasa pemrograman (Python/JS/Java/Go), framework (Django/Spring/Express), arsitektur, deployment target, dan domain aplikasi (e-commerce/healthcare/fintech/blog/IoT/education/general). Tahap 2: melakukan inferensi security coverage — dari 15 jenis security coverage (authentication, API, data, payment, container, IoT, logging, file upload, healthcare, fintech, CMS, dependency, education, CSP, microservice), sistem menentukan mana yang applicable berdasarkan library, route, dan entity yang terdeteksi. Hasil inferensi ini kemudian digunakan untuk men-generate custom Semgrep rules (K2.3) dan mendesain custom CI jobs (K2.4) yang spesifik untuk repositori. Tahap 3: secara deterministik mengkomposisi workflow YAML dari 8 standard jobs + domain jobs + AI-generated custom jobs, lalu memvalidasi (SHA pinning, permissions minimal), membuat branch baru, dan membuka Pull Request. Tahap 4: setelah workflow dieksekusi GitHub Actions, sistem mengumpulkan hasil scan (Semgrep, Trivy, Gitleaks, npm audit), menormalkan SARIF findings, mengkalkulasi risk score OWASP 3-dimensi, menghasilkan rekomendasi perbaikan, dan membuat laporan PDF 5-section.

Sistem diuji pada 4 repositori dari 4 kategori McConnell berbeda (e-commerce, blog/CMS, IoT, general) dengan 4 bahasa berbeda (Python, JS/TS, Java, Go hybrid). Hasil: 272 security findings, CVSS sum 1,463. Kontribusi K2.4 (custom AI-generated jobs) menghasilkan 27 finding unik yang tidak akan terdeteksi tools SAST standar. Ground truth detection rate untuk CVE spesifik adalah 0% — yang justru menjadi argumen kuat bahwa sistem adalah pelengkap, bukan pengganti, SAST tools existing.

**Jawaban Singkat (30 detik):**
Saya membangun AI agent 4-tahap dengan 18 node LangGraph yang secara otonom menganalisis repositori GitHub, menentukan kebutuhan keamanannya berbasis 15 security coverages, men-generate CI/CD pipeline yang aman, men-deploy ke GitHub Actions via PR, dan menganalisis hasil scan. Diuji pada 4 repositori dari 4 domain berbeda, menghasilkan 272 security findings. Novelty-nya ada di K2: inferensi security coverage berbasis konteks repositori yang kemudian digunakan untuk men-generate custom rules dan custom jobs AI.

**Alasan Penguji Bertanya:**
Pertanyaan pembuka standar untuk menguji pemahaman mahasiswa terhadap penelitiannya secara keseluruhan. Mengukur kemampuan sintesis dan komunikasi.

**Kemungkinan Follow-up:**
- Bisa sebutkan 15 security coverages? Spesifiknya apa saja?
- Apa bedanya K2.3 dan K2.4?
- Kenapa ground truth detection rate 0% tapi Anda tetap klaim sukses?

**Tingkat Kesulitan:** ⭐

**Prioritas:** High

---

## Q002

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa kontribusi utama (novelty) penelitian Anda?

**Jawaban Ideal:**
Penelitian ini memiliki 3 kontribusi utama (K1, K2, K3):

**K1 — Repository Context Analysis:** Sistem 6-node yang menganalisis repositori GitHub secara otomatis untuk mendeteksi bahasa (F1=1.00), framework, arsitektur, deployment, dan domain aplikasi. Deteksi domain menggunakan 7-layer fallback mechanism (LLM + heuristic) dengan library/entity/route-based signal scoring.

**K2 — Repository-Context-Aware Security Coverage Pipeline (novelty utama):** Konsep "security coverage" sebagai abstraksi antara konteks repositori dan pipeline jobs. Sistem memiliki 15 jenis security coverage (authentication, API, data, payment, container, IoT, logging, dll). Dari konteks repositori (library terdeteksi, route, entity, domain), sistem menginferensi coverage mana yang applicable (node `coverage_inference`), men-generate Semgrep rules spesifik-repositori (K2.3 `pattern_inference`), menentukan augmentasi per-coverage ke pipeline (node `pipeline_augmentation`), dan mendesain custom CI jobs (K2.4 `job_reasoning`). Ini berbeda dari pendekatan existing yang menggunakan pipeline statis one-size-fits-all.

**K3 — Pipeline Generation + Security Evaluation:** Sistem deterministik (5,808 baris `workflow_generator.py`) yang mengkomposisi YAML dari standard jobs + domain jobs + AI-generated jobs, memvalidasi, dan men-deploy. Security evaluation dengan OWASP 3-dimensi risk scoring + domain priority elevation.

**Jawaban Singkat (30 detik):**
Kontribusi utama adalah K2: Repository-Context-Aware Security Coverage Pipeline. Sistem tidak menggunakan template pipeline statis, tapi menginferensi 15 security coverages dari konteks repositori, lalu men-generate custom Semgrep rules dan custom CI/CD jobs yang spesifik untuk repo tersebut. Ini menghasilkan pipeline yang adaptif, bukan one-size-fits-all.

**Alasan Penguji Bertanya:**
Harus bisa membedakan antara "membuat sistem" dengan "kontribusi ilmiah." Penguji ingin tahu apa yang baru secara akademik.

**Kemungkinan Follow-up:**
- K2.3 dan K2.4 itu bedanya apa konkretnya?
- Apakah 15 security coverages ini Anda yang mendefinisikan? Berdasarkan apa?
- Kalau kontribusinya hanya "inferensi coverages", apa bedanya dengan expert system biasa?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q003

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa gap penelitian yang Anda isi?

**Jawaban Ideal:**
Ada 3 gap utama yang diidentifikasi:

1. **Pipeline CI/CD security yang statis dan one-size-fits-all.** Tools existing seperti GitHub Actions starter workflows, GitLab CI templates, atau Jenkins pipelines menggunakan template statis yang tidak adaptif terhadap konteks repositori. Semua repo Python dapat pipeline yang sama, tidak peduli apakah itu e-commerce atau blog.

2. **Security scanning yang tidak kontekstual.** Tools SAST seperti Semgrep, CodeQL, SonarQube menerapkan ruleset yang sama tanpa mempertimbangkan domain aplikasi. E-commerce dan IoT butuh aturan keamanan yang berbeda (PCI-DSS vs MQTT security), tapi tools SAST tidak punya mekanisme untuk menyesuaikan ruleset berdasarkan domain.

3. **Tidak ada abstraksi formal antara konteks repositori dan kebutuhan keamanan.** Literatur (Meneely et al. 2013, Matter et al. 2025) menunjukkan bahwa kerentanan mengelompok per domain, tapi belum ada sistem yang mengoperasionalisasi temuan ini ke dalam pipeline generation. Gap ini yang saya isi dengan konsep "security coverage."

**Jawaban Singkat (30 detik):**
Pipeline CI/CD security saat ini statis — semua repo diperlakukan sama. Padahal kerentanan mengelompok per domain (e-commerce vs IoT vs healthcare). Sistem saya mengisi gap ini dengan menginferensi security coverage dari konteks repositori, menghasilkan pipeline yang adaptif berbasis domain.

**Alasan Penguji Bertanya:**
Menguji dasar ilmiah penelitian — apakah penelitian ini menjawab masalah nyata atau sekadar "membuat sesuatu."

**Kemungkinan Follow-up:**
- Referensi yang mendukung "kerentanan mengelompok per domain"?
- Kenapa tools SAST existing tidak bisa disuruh ganti ruleset per project? Itu kan tinggal konfigurasi?
- Apakah gap ini signifikan secara praktis?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q004

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Mengapa topik ini dipilih?

**Jawaban Ideal:**
Tiga alasan:

1. **Relevansi praktis:** DevSecOps adalah tren industri yang berkembang pesat. GitHub Actions memiliki >100 juta workflow runs per bulan. Namun, mengkonfigurasi pipeline yang aman tetap menjadi tantangan — butuh expertise di security + CI/CD + domain spesifik. Sistem ini mengotomasi proses tersebut.

2. **Gap akademik:** Literatur security pipeline generation masih terbatas. Kebanyakan penelitian fokus pada deteksi kerentanan (SAST/DAST/SCA), bukan pada generasi pipeline yang adaptif. Konsep "security coverage" sebagai jembatan antara konteks repositori dan kebutuhan pipeline adalah kontribusi novel.

3. **Feasibility:** GitHub API + GitHub Actions + tools open-source (Semgrep, Trivy, Gitleaks) + LLM modern menyediakan infrastruktur yang cukup untuk mewujudkan sistem ini. Tidak perlu membangun scanner dari nol — fokusnya pada orkestrasi dan reasoning.

**Jawaban Singkat (30 detik):**
DevSecOps adalah tren industri, tapi pipeline security masih dikonfigurasi manual. Saya melihat opportunity untuk mengotomasi ini dengan AI, khususnya dengan pendekatan context-aware — pipeline yang menyesuaikan dengan repositorinya.

**Alasan Penguji Bertanya:**
Motivasi personal/akademik. Penguji ingin tahu apakah topik dipilih karena tren atau karena genuine research interest.

**Kemungkinan Follow-up:**
- Apakah Anda tertarik di security atau di AI?
- Kenapa tidak pilih topik yang lebih "aman" seperti web app biasa?
- Apa relevansi penelitian ini dengan industri Indonesia?

**Tingkat Kesulitan:** ⭐

**Prioritas:** Medium

---

## Q005

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa research question Anda?

**Jawaban Ideal:**
Tiga research question:

**RQ1 (Accuracy):** Seberapa akurat sistem dalam menganalisis konteks repositori (bahasa, framework, arsitektur, domain) dan menginferensi security coverage yang applicable? Diukur dengan precision/recall/F1 terhadap ground truth manual labeling.

**RQ2 (Completeness):** Seberapa lengkap pipeline yang dihasilkan — berapa banyak security coverage yang tercakup oleh jobs yang digenerate? Diukur dengan coverage ratio (applicable coverages yang punya corresponding job / total applicable coverages).

**RQ3 (Effectiveness):** Seberapa efektif pipeline dalam mendeteksi kerentanan — berapa banyak security findings yang dihasilkan dan bagaimana distribusi severity-nya? Diukur dengan jumlah findings, CVSS aggregate, dan detection rate terhadap ground truth CVE.

**Jawaban Singkat (30 detik):**
RQ1: seberapa akurat deteksi konteks repositori dan inferensi coverage? RQ2: seberapa lengkap pipeline yang dihasilkan? RQ3: seberapa efektif pipeline mendeteksi kerentanan?

**Alasan Penguji Bertanya:**
Research question harus jelas, terukur, dan menjawab gap. Penguji ingin melihat apakah pertanyaan penelitian selaras dengan metodologi.

**Kemungkinan Follow-up:**
- Bagaimana cara mengukur RQ2? Apa metriknya?
- Kenapa RQ3 tidak pakai precision/recall terhadap CVE?
- Apakah RQ1-RQ3 ini menjawab gap yang Anda klaim?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q006

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa batasan penelitian Anda?

**Jawaban Ideal:**
7 batasan utama:

1. **Bahasa pemrograman:** Sistem mendeteksi Python, JavaScript/TypeScript, Java, Go, Rust — tidak mencakup C/C++ (firmware/embedded), Ruby, PHP, C#, Kotlin, Swift.

2. **Platform CI/CD:** Hanya GitHub Actions. Tidak mendukung GitLab CI, Jenkins, CircleCI, Bitbucket Pipelines.

3. **Deployment target:** Hanya Docker dan Docker Compose. Kubernetes, Terraform, Helm tidak dideteksi.

4. **Domain:** Fokus pada 3 domain utama (e-commerce, blog, IoT) di v9.4. Fintech, healthcare, education di-remove dari scope.

5. **Arsitektur:** Semua repositori diklasifikasikan sebagai monolithic (R2.1). Microservices detection tidak diimplementasikan.

6. **SAST only:** Hanya static analysis. DAST (dynamic), IAST, RASP tidak termasuk.

7. **Single run per repo:** Pengujian dilakukan 1× per repositori. Tidak ada pengulangan untuk mengukur variansi.

**Jawaban Singkat (30 detik):**
Hanya GitHub Actions, hanya Docker, hanya 3 domain, hanya SAST, hanya monolithic, hanya 4 repo × 1 run. Tidak ada DAST, tidak ada microservices detection, tidak ada replikasi.

**Alasan Penguji Bertanya:**
Menguji kesadaran peneliti terhadap batasan sistemnya sendiri. Batasan yang jelas = penelitian yang jujur.

**Kemungkinan Follow-up:**
- Kenapa Kubernetes tidak dideteksi padahal banyak dipakai?
- Apakah dengan hanya 4 repo Anda bisa mengklaim generalisasi?
- Kenapa tidak sekalian support GitLab CI?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q007

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa kelemahan terbesar penelitian Anda?

**Jawaban Ideal:**
Dua kelemahan terbesar:

1. **Detection rate 0% untuk CVE spesifik:** Dari 14 CVE target, 0 terdeteksi sebagai true positive. Ini adalah kelemahan fundamental dari pendekatan SAST-only. SAST bagus untuk pola umum (SQLi, XSS, weak crypto) tapi tidak untuk CVE spesifik yang membutuhkan pemahaman business logic. Saya akui ini dan saya rekomendasikan integrasi DAST di Bab V.

2. **Dataset kecil (4 repositori, 1 run):** 4 repositori terlalu sedikit untuk generalisasi statistik. Tanpa pengulangan, tidak ada mean ± std dev. Ini adalah trade-off: menguji 4 repositori dari 4 domain berbeda (purposive sampling) memberi keberagaman kualitatif, tapi mengorbankan kekuatan statistik.

**Jawaban Singkat (30 detik):**
Detection rate 0% untuk CVE spesifik (kelemahan SAST) dan dataset terlalu kecil (4 repo, 1 run) untuk generalisasi statistik. Tapi saya akui keduanya di Bab V dan menyarankan perbaikan konkret.

**Alasan Penguji Bertanya:**
Menguji kejujuran akademik dan critical thinking. Peneliti yang tidak bisa menyebutkan kelemahan penelitiannya sendiri adalah red flag.

**Kemungkinan Follow-up:**
- Kalau detection rate 0%, apa gunanya sistem Anda?
- Kenapa tidak diulang 3×?
- Apakah Anda yakin ini layak disebut "kontribusi"?

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q008

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa metodologi penelitian yang Anda gunakan?

**Jawaban Ideal:**
Design Science Research (DSR) dengan pendekatan kuantitatif. DSR cocok untuk penelitian yang menghasilkan artifact (sistem) karena framework-nya meliputi:

1. **Problem identification:** Gap pipeline CI/CD statis + security scanning non-kontekstual
2. **Solution design:** 4-tahap AI agent dengan 15 security coverages
3. **Artifact development:** 18-node LangGraph graph + 3-layer architecture (Go/Python/React)
4. **Evaluation:** 4 repositori × 1 run dengan ground truth CVE
5. **Conclusion:** 3 kontribusi (K1, K2, K3) + saran perbaikan

Evaluasi menggunakan metrik kuantitatif: F1 untuk deteksi bahasa, coverage ratio untuk pipeline completeness, jumlah findings + CVSS untuk effectiveness.

**Jawaban Singkat (30 detik):**
Design Science Research — membangun artifact (sistem AI agent), lalu mengevaluasi dengan eksperimen pada 4 repositori dari 4 kategori McConnell berbeda menggunakan metrik kuantitatif.

**Alasan Penguji Bertanya:**
Metodologi menentukan kredibilitas penelitian. DSR harus dijustifikasi dengan baik.

**Kemungkinan Follow-up:**
- Kenapa DSR bukan action research atau case study?
- Di mana letak iterasi dalam DSR Anda?
- Apakah DSR cocok untuk penelitian AI?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q009

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apakah hasil penelitian Anda bisa digeneralisasi?

**Jawaban Ideal:**
Secara hati-hati, ya — dengan caveat:

1. **Generalisasi positif:** Sistem berhasil memproses 4 bahasa berbeda (Python, JS/TS, Java, Go hybrid), 4 domain berbeda (e-commerce, blog, IoT, general), dan berbagai framework (Django, Spring Boot, Express, Nx). Untuk repositori dengan karakteristik serupa, sistem diharapkan berfungsi.

2. **Batasan generalisasi:**
   - Hanya diuji pada repositori open-source dengan struktur standar
   - Domain detection lemah (semua terdeteksi "general" — confidence tinggi tapi salah)
   - Tidak diuji pada repositori proprietary/skala enterprise
   - 4 sampel terlalu sedikit untuk klaim generalisasi statistik

3. **External validity:** Purposive sampling (Patton 2015) memilih 4 repo dari 4 kategori McConnell berbeda untuk memaksimalkan variasi, tapi hasil tidak bisa digeneralisasi ke populasi repositori secara statistik. Diperlukan setidaknya 12-16 repo untuk itu.

**Jawaban Singkat (30 detik):**
Terbatas. Sistem berfungsi di 4 repositori yang diuji, tapi dengan 4 sampel saya tidak bisa mengklaim generalisasi statistik. Yang bisa saya klaim: sistem berfungsi untuk karakteristik repositori serupa — open-source, bahasa mainstream, CI/CD GitHub Actions.

**Alasan Penguji Bertanya:**
External validity menentukan apakah penelitian bisa diterapkan di luar sampel. Ini pertanyaan kritis untuk DSR.

**Kemungkinan Follow-up:**
- Berapa sampel minimum untuk generalisasi?
- Apakah purposive sampling cukup untuk klaim generalisasi?
- Kenapa tidak random sampling?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q010

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa implikasi praktis penelitian Anda?

**Jawaban Ideal:**
Tiga implikasi praktis:

1. **Untuk startup/UKM:** Startup sering tidak punya dedicated DevSecOps engineer. Sistem ini bisa men-generate pipeline yang secure dalam <60 detik, mengurangi time-to-security dari berhari-hari menjadi kurang dari semenit. Biaya LLM ~$0.03 per repo (MiniMax-m3) sangat terjangkau.

2. **Untuk tim engineering:** Pipeline yang di-generate bisa menjadi starting point yang secure. Tim tinggal review dan kustomisasi, bukan mulai dari nol. PR-based workflow juga sesuai dengan praktik code review yang sudah ada.

3. **Untuk security auditor:** Coverage-to-finding mapping membantu auditor melihat gap keamanan secara sistematis — coverage mana yang sudah punya job, mana yang belum.

**Jawaban Singkat (30 detik):**
Startup bisa dapat pipeline aman dalam <60 detik tanpa DevSecOps engineer. Biaya $0.03/repo. Hasilnya berupa PR yang bisa direview seperti code biasa.

**Alasan Penguji Bertanya:**
Penelitian harus punya dampak nyata, bukan sekadar akademik. Relevan dengan TIK.

**Kemungkinan Follow-up:**
- Apakah ada startup yang sudah pakai?
- Bagaimana cara mengukur dampak praktis?
- Apakah sistem siap production?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q011

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Kenapa memakai purposive sampling dan bukan random sampling?

**Jawaban Ideal:**
Purposive sampling (Patton 2015) dipilih karena tujuan penelitian bukan generalisasi statistik, melainkan memaksimalkan variasi karakteristik:

1. **4 kategori McConnell berbeda:** Business Systems (e-commerce), Internet Systems (blog, IoT), General (chatbot) — mencakup spektrum domain yang lebar
2. **4 bahasa berbeda:** Python, JavaScript, Java, Go/JS hybrid — menguji generalisasi lintas stack
3. **Variasi arsitektur:** 3 monolith sejati + 1 microservices (ThingsBoard) + 1 hybrid (AI Service)

Random sampling dari populasi GitHub justru akan menghasilkan bias ke JavaScript/TypeScript (bahasa paling populer) dan domain general — tidak akan menguji kemampuan sistem di domain niche seperti IoT.

**Jawaban Singkat (30 detik):**
Karena tujuan-nya memaksimalkan variasi — 4 domain berbeda, 4 bahasa berbeda — bukan generalisasi statistik. Random sampling dari GitHub justru akan didominasi JS dan domain general.

**Alasan Penguji Bertanya:**
Sampling strategy menentukan validitas evaluasi. Penguji ingin memastikan pilihan ini justified secara metodologis.

**Kemungkinan Follow-up:**
- Patton 2015 — itu referensi apa? Buku atau paper?
- Apakah 4 cukup untuk "variasi maksimal"?
- Kenapa tidak pakai stratified sampling?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q012

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa yang membedakan penelitian Anda dengan tools SAST existing seperti SonarQube atau Snyk?

**Jawaban Ideal:**
Perbedaan fundamental: sistem saya tidak menghasilkan findings — sistem saya **menghasilkan pipeline yang memanggil** tools SAST/SCA/secret-scan yang sudah ada.

| Aspek | Sistem Saya | SonarQube/Snyk |
|---|---|---|
| Output | GitHub Actions workflow YAML | Security findings |
| Scope | Pipeline generation + deployment | Vulnerability detection |
| Intelligence | Context-aware (domain, library, route) | Ruleset-based (one-size-fits-all) |
| Customization | Custom Semgrep rules + custom CI jobs per repo | Custom rules but manual |
| LLM | Ya (12 dari 20 node) | Tidak (atau hanya untuk code fix suggestion) |

Sistem saya adalah **meta-layer** di atas tools SAST/SCA: menganalisis repositori → memilih tools yang tepat → mengkonfigurasi → menjalankan → menganalisis hasil. SonarQube/Snyk adalah **tools yang dipanggil**, bukan pengganti.

**Jawaban Singkat (30 detik):**
Saya bukan membuat scanner keamanan baru. Saya membuat sistem yang secara cerdas memilih, mengkonfigurasi, dan mengorkestrasi scanner yang sudah ada (Semgrep, Trivy, Gitleaks) dalam bentuk pipeline CI/CD.

**Alasan Penguji Bertanya:**
Positioning penelitian terhadap existing tools. Penguji ingin tahu apakah ini genuinely novel atau sekadar re-implementasi.

**Kemungkinan Follow-up:**
- Kalau begitu apa bedanya dengan GitHub Actions starter workflow?
- Apakah Semgrep rules Anda lebih baik dari Semgrep registry?
- Kenapa tidak pakai SonarQube sebagai scanner?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q013

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Mengapa hasil Anda bisa dipercaya (validity)?

**Jawaban Ideal:**
Validitas dijaga pada beberapa level:

1. **Internal validity — deterministic pipeline generation:** Workflow YAML di-generate secara deterministik oleh `workflow_generator.py` (5,808 baris) — tidak ada LLM di sini. Validasi dengan SHA pinning + permissions check + concurrency check dipastikan sebelum deployment.

2. **Construct validity — ground truth:** Setiap repositori memiliki CVE ground truth yang terdokumentasi (total 14 CVE/injeksi target) + mapping coverage yang diharapkan (ekspektasi peneliti). Hasil sistem dibandingkan dengan ground truth ini.

3. **External validity — purposive sampling 4 kategori McConnell:** Variasi domain, bahasa, dan arsitektur diuji. Namun saya akui 4 sampel tidak cukup untuk klaim generalisasi statistik.

4. **Reliability — deterministic fallback di setiap LLM node:** Ketika LLM gagal atau menghasilkan output tidak valid, setiap node memiliki fallback deterministik. Ini memastikan sistem tidak menghasilkan output random antar run.

5. **Reproducibility — open source:** Seluruh kode, dataset, dan hasil di-publish di GitHub. Docker Compose one-command setup.

**Jawaban Singkat (30 detik):**
Validitas internal: deterministic workflow generator. Validitas konstruk: ground truth CVE. Validitas eksternal: 4 domain berbeda. Tapi saya akui 4 sampel kurang untuk generalisasi.

**Alasan Penguji Bertanya:**
Pertanyaan paling fundamental dalam penelitian. Tanpa validitas, hasil tidak bermakna.

**Kemungkinan Follow-up:**
- Internal validity terancam oleh inkonsistensi LLM — bagaimana mengatasinya?
- Kenapa tidak pakai inter-rater reliability untuk ground truth?
- Apakah deterministic fallback cukup untuk menjamin reproducibility?

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q014

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apakah Anda sudah mengukur reproducibility?

**Jawaban Ideal:**
Belum secara formal. Beberapa langkah telah diambil:
- Semua kode di-publish di GitHub
- Docker Compose untuk one-command setup (postgres + redis + backend + ai-service + frontend + nginx)
- `.env.example` disediakan
- Setiap node LLM memiliki fallback deterministik

Namun, ada beberapa faktor yang menghambat reproducibility sempurna:
1. **Temperature LLM 0.3** — masih menghasilkan variasi antar run. Saya sarankan temperature 0.0 atau seed-controlled generation di Bab V.
2. **Ground truth tidak direproduksi** — pengujian hanya 1× per repo.
3. **Missing files:** `domain_priority.py` dan `scan_directives.py` seharusnya ada tapi tidak committed (gap yang perlu di-fix).

**Jawaban Singkat (30 detik):**
Secara infrastruktur ya (Docker Compose, open source), secara hasil belum — temperature 0.3 masih menghasilkan variasi, dan pengujian baru 1× per repo. Saya rekomendasikan temperature 0.0 di Bab V.

**Alasan Penguji Bertanya:**
Reproducibility adalah syarat penelitian ilmiah. Penguji akan concern dengan LLM non-determinism.

**Kemungkinan Follow-up:**
- Kenapa tidak pakai seed?
- Apakah Anda bisa jamin hasil yang sama jika saya jalankan ulang?
- Missing files itu gimana ceritanya?

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q015

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Berapa lama waktu yang dibutuhkan untuk satu kali pipeline generation?

**Jawaban Ideal:**
Tergantung beberapa faktor:

1. **Repository scan:** 5-30 detik (tergantung ukuran repo, max 30 file × 50KB)
2. **LLM calls (11 calls):** 30-90 detik (tergantung provider, MiniMax-m3 ~3-5 detik/call)
3. **Workflow generation:** <1 detik (deterministic)
4. **GitHub API (branch + PR):** 2-5 detik
5. **Workflow execution:** 2-15 menit (tergantung workflow jobs)

**Total end-to-end dari generate sampai PR terbuka: ~30-60 detik.** Workflow execution menunggu GitHub Actions runtime.

Untuk ThingsBoard (repo terbesar, >1M LOC), scan time >30 menit. Di-mitigasi dengan Trivy `--skip-dirs`.

**Jawaban Singkat (30 detik):**
~30-60 detik dari klik generate sampai PR terbuka. Workflow execution baru 2-15 menit setelahnya, tergantung kompleksitas repo.

**Alasan Penguji Bertanya:**
Performance praktis. Apakah sistem usable secara real-time atau butuh menunggu lama?

**Kemungkinan Follow-up:**
- Apakah ada bottleneck?
- Bagaimana kalau repo sangat besar (>10K files)?
- Apakah LLM latency dominant?

**Tingkat Kesulitan:** ⭐

**Prioritas:** Low

---

## Q016

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Berapa biaya operasional per pipeline generation?

**Jawaban Ideal:**
Biaya LLM sangat rendah karena menggunakan MiniMax-m3 via OpenRouter:

- **MiniMax-m3 pricing:** input $0.30/1M tokens, output $1.20/1M tokens
- **Estimasi per call:** ~4K input tokens + ~1.5K output tokens = ~$0.0032/call
- **11 LLM calls × 4 repo:** total 44 calls (sebagian fail/skip)
- **Total cost 4 repo:** ~$0.13 (dari tabel 4.12 di Bab IV)

Sebagai perbandingan, GPT-4o akan memakan biaya ~$2.00 untuk 4 repo yang sama. Biaya infrastruktur lain (Docker container, GitHub Actions) gratis di tier free.

**Jawaban Singkat (30 detik):**
~$0.03 per repositori dengan MiniMax-m3. Sangat murah. GPT-4o sekitar 15× lebih mahal.

**Alasan Penguji Bertanya:**
Praktikalitas deployment. Untuk adopsi industri, biaya adalah faktor kunci.

**Kemungkinan Follow-up:**
- Kenapa pilih MiniMax-m3?
- Apakah MiniMax-m3 kualitasnya setara GPT-4o?
- Bagaimana perbandingan biaya dengan menyewa DevSecOps engineer?

**Tingkat Kesulitan:** ⭐

**Prioritas:** Medium

---

## Q017

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Bagaimana Anda memvalidasi bahwa pipeline yang digenerate benar-benar "aman"?

**Jawaban Ideal:**
Validasi dilakukan pada tiga level:

1. **Pre-deployment validation (`workflow_validator`):**
   - SHA pinning untuk semua actions (tidak pakai tag mutable seperti `@v3`)
   - Permissions minimal (`contents: read`, hanya job yang perlu write yang dapat)
   - Concurrency group untuk mencegah race condition
   - `persist-credentials: false` untuk actions/checkout
   - Registry compliance check (action harus ada di `action_registry.py`)

2. **Post-execution analysis:**
   - Findings dari Semgrep, Trivy, Gitleaks, npm audit dikumpulkan
   - Setiap finding di-enrich dengan OWASP Likelihood × Impact
   - Domain priority elevation untuk finding yang relevan dengan domain

3. **Risk scoring (OWASP 3-dimensi):**
   - Threat Agent Factor + Vulnerability Factor → Likelihood
   - Business Impact → Impact
   - Risk Score = Likelihood × Impact, diskalakan 0-100

**Jawaban Singkat (30 detik):**
Pre-deployment: SHA pinning + permissions minimal + concurrency validation. Post-execution: OWASP risk scoring per finding. Pipeline dianggap aman kalau lolos validasi dan tidak ada critical finding un-addressed.

**Alasan Penguji Bertanya:**
"Pipeline aman" adalah klaim besar. Penguji ingin bukti konkret.

**Kemungkinan Follow-up:**
- Apakah 0 validation error berarti pipeline benar-benar aman?
- Bagaimana memvalidasi tidak ada supply chain attack di action yang di-pin?
- Apakah risk score OWASP cukup untuk menjustifikasi "aman"?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q018

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa perbedaan sistem Anda dengan GitHub Copilot atau ChatGPT yang disuruh generate CI/CD pipeline?

**Jawaban Ideal:**
Perbedaan fundamental:

1. **Deterministic core:** Workflow generation di sistem saya 100% deterministik (5,808 baris Python), bukan LLM-generated. Ini menjamin validitas YAML, SHA pinning, dan permissions. ChatGPT generate YAML secara probabilistik — tidak ada jaminan SHA benar atau action kompatibel.

2. **Multi-step reasoning:** Sistem saya melalui 18 node reasoning steps terpisah — dari scan repositori → deteksi teknologi → deteksi domain → inferensi coverage → generate custom rules → desain job → komposisi YAML → validasi → deploy. ChatGPT melakukan semua ini dalam 1 prompt (lossy compression).

3. **Action registry:** Sistem saya memiliki database 914-baris action registry dengan SHA, input schema, dan compatibility matrix. ChatGPT tidak punya.

4. **Execution + analysis:** Sistem saya menjalankan pipeline, mengumpulkan hasil scan, menganalisis findings, dan membuat report. ChatGPT hanya generate teks.

**Jawaban Singkat (30 detik):**
ChatGPT/Copilot hanya generate teks YAML probabilistik. Sistem saya deterministik, punya action registry, validasi, deployment, execution, dan analysis loop. Lebih terstruktur dan terpercaya.

**Alasan Penguji Bertanya:**
Pertanyaan "iseng" yang serius. Di era ChatGPT, mahasiswa harus bisa membenarkan kenapa tidak cukup pakai chatbot.

**Kemungkinan Follow-up:**
- Tapi kan hasilnya sama-sama YAML? Bedanya di mana?
- Apakah deterministic generation bisa adaptif? Bukankah LLM lebih fleksibel?
- Kenapa tidak combine: LLM untuk reasoning, deterministic untuk generation?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q019

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa rencana Anda setelah lulus? Apakah sistem ini akan dilanjutkan?

**Jawaban Ideal:**
Rencana:

1. **Akademik:** Submit paper ke konferensi (saran: ESEM 2027 untuk empirical software engineering, atau ICSE NIER untuk emerging results). Topik: "repository-context-aware security coverage inference."

2. **Open source:** Publish sebagai open-source tool. Potensi untuk GitHub Actions marketplace (custom action).

3. **Perbaikan:** Implementasi saran di Bab V:
   - DAST integration
   - CVSS-driven job generation
   - Library detection dari lock files
   - Multi-run replikasi
   - Support Kubernetes/Terraform

4. **Potensi komersial:** SaaS offering untuk startup/UKM yang ingin CI/CD security out-of-the-box. $10-50/bulan/repo.

**Jawaban Singkat (30 detik):**
Submit paper, open-source tool, implementasi saran Bab V (DAST, lock file detection, K8s support). Potensi SaaS untuk startup.

**Alasan Penguji Bertanya:**
Melihat visi jangka panjang. Menunjukkan apakah mahasiswa berpikir beyond skripsi.

**Kemungkinan Follow-up:**
- Di jurnal apa rencananya?
- Apakah ada rencana startup?
- Kontribusi open source sudah ada yang interested?

**Tingkat Kesulitan:** ⭐

**Prioritas:** Low

---

## Q020

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa state of the art di bidang Anda dan di mana posisi penelitian Anda?

**Jawaban Ideal:**
State of the art bisa dikelompokkan:

1. **Automated pipeline generation:** GitHub Actions starter workflows, GitLab CI templates — statis, template-based. Tidak ada adaptasi konteks.

2. **AI-assisted CI/CD:** GitHub Copilot (code completion), AI PR review tools (CodeRabbit, What the Diff) — fokus pada code generation/review, bukan pipeline generation.

3. **Security scanning:** Semgrep, CodeQL, SonarQube, Snyk, Trivy — mendeteksi kerentanan. Posisi tetap, tidak menghasilkan pipeline.

4. **Academic:** Hummer et al. (2015) automated deployment models, Pashchenko et al. (2018) vulnerability detection comparison, Meneely et al. (2013) vulnerability clustering per domain.

**Posisi penelitian saya:** Berada di intersection antara pipeline generation + security scanning + context-aware AI. Belum ada sistem yang mengoperasionalisasi temuan "vulnerability clustering per domain" (Meneely) ke dalam pipeline generation. Konsep "security coverage" sebagai abstraksi formal adalah kontribusi novel.

**Jawaban Singkat (30 detik):**
State of the art: pipeline statis (GitHub starter workflows) atau tools deteksi (Semgrep/Snyk). Posisi saya: di tengah-tengah — AI agent yang menganalisis repositori lalu men-generate pipeline yang disesuaikan.

**Alasan Penguji Bertanya:**
Literature review harus menghasilkan positioning yang jelas. Penguji ingin tahu apakah mahasiswa paham landscape.

**Kemungkinan Follow-up:**
- Hummer et al. 2015 itu tentang apa konkretnya?
- Apakah ada paper yang mirip dengan penelitian Anda?
- Di mana letak novelty dibanding semua state of the art ini?

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q021

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Kenapa memakai 3 kontribusi (K1, K2, K3)? Apakah 1 kontribusi tidak cukup?

**Jawaban Ideal:**
Saya memilih 3 kontribusi karena merefleksikan 3 tahap utama sistem yang masing-masing punya kontribusi terpisah:

- **K1 (Context Analysis):** Kontribusi di tahap input — menganalisis repositori secara otomatis. Meski komponen individual (deteksi bahasa, deteksi framework) bukan novelty, integrasinya ke dalam pipeline multi-node LangGraph dengan 7-layer fallback adalah kontribusi engineering.

- **K2 (Security Coverage):** Kontribusi utama (novelty) — konsep abstraksi security coverage yang menjembatani konteks repositori dan pipeline jobs. Ini yang benar-benar baru.

- **K3 (Pipeline Generation + Evaluation):** Kontribusi di tahap output — deterministic YAML generation + post-execution analysis. Meski tidak senovel K2, sistem sebesar 5,808 baris workflow generator dengan action registry adalah kontribusi engineering signifikan.

Saya bisa meringkas jadi 1 kontribusi ("Repository-Context-Aware Security Coverage Pipeline"), tapi 3 kontribusi memperjelas di mana letak novelty (K2) vs engineering (K1, K3).

**Jawaban Singkat (30 detik):**
K2 adalah novelty utama. K1 dan K3 adalah kontribusi engineering yang mensupport K2. Saya pisahkan untuk memperjelas.

**Alasan Penguji Bertanya:**
Banyak kontribusi bisa menjadi red flag (kurang fokus). Penguji ingin memastikan mahasiswa tahu mana yang benar-benar baru.

**Kemungkinan Follow-up:**
- Kalau K1 dan K3 hanya engineering, kenapa diklaim sebagai kontribusi?
- Apakah K1 bisa di-skip?
- Apakah K3 bisa diganti dengan tools existing?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q022

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Bagaimana Anda menangani error dan edge cases dalam sistem?

**Jawaban Ideal:**
Error handling diimplementasikan di setiap layer:

1. **Node-level fallback:** Setiap node LLM memiliki fallback deterministik. Contoh:
   - `technology_detection`: LLM gagal → extension-based detection (confidence ≤0.6)
   - `domain_detection`: 7-layer fallback, dari LLM → heuristic scoring → "general" default
   - `coverage_inference`: LLM gagal → heuristic scoring (threshold ≥1.0)
   - `job_reasoning`: LLM gagal → 1 deterministic fallback job

2. **Pipeline-level error handling:**
   - Retry mechanism (max 3 attempts di Tahap 2)
   - Short-circuit: jika `errors` tidak kosong di awal node, skip
   - Validation gate: `workflow_validation` gagal → langsung ke `response_formatter`

3. **GitHub API errors:**
   - Blocker logic: transient errors (502/503/timeout) tidak blocking
   - Blocker: auth/token/Permission errors → blocking
   - Partial failure (legacy workflow removal gagal sebagian) → warning, lanjut

4. **Empty state / null handling:**
   - `generated_workflow` kosong → validator skip
   - `custom_semgrep_rules_yaml` kosong → regenerasi di PR creation

**Jawaban Singkat (30 detik):**
Setiap node LLM punya fallback deterministik. GitHub API errors dipisah: transient (non-blocking) vs permanent (blocking). Retry 3× di Tahap 2.

**Alasan Penguji Bertanya:**
Robustness penting untuk sistem production-grade. Edge case handling menunjukkan kematangan engineering.

**Kemungkinan Follow-up:**
- Contoh spesifik kasus domain_detection gagal?
- Apakah ada test untuk error handling?
- Apa yang terjadi kalau LLM provider down total?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q023

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Kenapa Anda memilih GitHub Actions dan bukan Jenkins atau GitLab CI?

**Jawaban Ideal:**
Tiga alasan:

1. **Market dominance:** GitHub adalah platform hosting kode terbesar (100M+ developer). GitHub Actions terintegrasi native — tidak perlu setup server terpisah seperti Jenkins. Untuk penelitian yang ingin dampak maksimal, GitHub Actions memberikan reach terbesar.

2. **API maturity:** GitHub API v3 (REST) dan v4 (GraphQL) sangat lengkap — repository scan, branch creation, PR, workflow dispatch, check runs, annotations. Semua bisa di-automate tanpa setup infrastructure tambahan.

3. **Research scope:** Ini adalah batasan yang disengaja (boundary B2). Fokus pada satu platform memungkinkan implementasi yang dalam (5,808 baris workflow generator, 914 baris action registry) daripada implementasi dangkal di 3 platform. Ekspansi ke GitLab CI atau Jenkins adalah future work.

**Jawaban Singkat (30 detik):**
GitHub Actions terbesar, API-nya paling mature, dan ini batasan penelitian yang disengaja. Ekspansi ke GitLab CI / Jenkins adalah future work.

**Alasan Penguji Bertanya:**
Batasan harus dijustifikasi dengan baik, bukan sekadar "karena saya pakai GitHub."

**Kemungkinan Follow-up:**
- Apakah arsitektur sistem Anda bisa diadaptasi ke GitLab CI?
- Berapa banyak effort untuk support platform lain?
- Kenapa tidak Jenkins yang lebih established?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q024

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apakah Anda sudah melakukan user testing?

**Jawaban Ideal:**
Belum. Ini adalah salah satu saran di Bab V §5.2.2:

> "Tambahkan user study untuk mengukur apakah AI-generated pipeline lebih mudah di-review oleh developer manusia dibanding rule-based static pipeline."

Alasan belum dilakukan:
- Fokus penelitian adalah pada technical validation (apakah sistem berfungsi?), bukan pada user acceptance (apakah developer suka?)
- User study membutuhkan metodologi berbeda (within-subjects experiment, SUS questionnaire, time-to-review measurement)
- Waktu dan sumber daya terbatas

Saya catat ini sebagai future work yang penting. User study akan memperkuat claim "adaptive pipeline lebih baik."

**Jawaban Singkat (30 detik):**
Belum. Fokus di technical validation. User study ada di saran Bab V sebagai future work.

**Alasan Penguji Bertanya:**
Sistem yang dibuat untuk developer harus divalidasi oleh developer. Ini adalah gap yang valid.

**Kemungkinan Follow-up:**
- Bagaimana desain user study yang ideal?
- Apakah Anda punya rencana untuk merekrut partisipan?
- Bukankah tanpa user study, klaim "lebih baik" tidak berdasar?

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q025

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Bagaimana Anda memastikan penelitian Anda bukan sekadar "software development project"?

**Jawaban Ideal:**
Perbedaan "software development project" dan penelitian:

1. **Research question terdefinisi:** Tiga RQ terukur (RQ1 accuracy, RQ2 completeness, RQ3 effectiveness) — bukan sekadar "membangun aplikasi."

2. **Metodologi formal:** Design Science Research — bukan agile/scrum development.

3. **Evaluasi sistematis:** Ground truth CVE, metrik kuantitatif (F1, coverage ratio, CVSS sum), perbandingan 4 repositori — bukan sekadar "demo jalan."

4. **Kontribusi konseptual (K2):** Konsep "security coverage" sebagai abstraksi formal adalah kontribusi yang bisa digeneralisasi di luar implementasi spesifik. Software project tidak menghasilkan konsep baru.

5. **Analisis hasil:** Bab IV tidak hanya melaporkan "sistem jalan," tapi menganalisis kenapa detection rate 0%, kenapa domain detection lemah, kenapa coverage under-detect — dengan justifikasi ke literatur (Baca et al. 2008, Pashchenko et al. 2018).

**Jawaban Singkat (30 detik):**
Penelitian menghasilkan konsep baru (security coverage inference), dievaluasi dengan metrik formal terhadap ground truth, dan hasil dianalisis dengan justifikasi ke literatur. Software project tidak melakukan ini.

**Alasan Penguji Bertanya:**
Kritik paling umum untuk skripsi berbasis pembangunan sistem. Harus bisa membedakan engineering dari research.

**Kemungkinan Follow-up:**
- Apakah developer biasa tidak bisa membuat sistem seperti ini?
- Apa elemen "research" yang tidak ada di software project biasa?
- Kalau kontribusinya hanya "security coverage concept", kenapa harus bikin sistem?

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q026

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Apa yang Anda pelajari selama mengerjakan skripsi ini?

**Jawaban Ideal:**
Beberapa pembelajaran utama:

1. **Technical:** Mendalami LangGraph state machine, prompt engineering, multi-provider LLM abstraction, GitHub Actions internals, SARIF format, Semgrep rule authoring, Go concurrent patterns, Docker multi-stage builds.

2. **Research:** Pentingnya ground truth dalam evaluasi AI systems, trade-off antara determinism dan flexibility, perbedaan antara "system works" dan "system is validated."

3. **Critical thinking:** Hasil 0% detection rate untuk CVE spesifik awalnya mengecewakan, tapi justru menjadi temuan paling berharga — membuktikan batasan SAST yang sudah didokumentasikan di literatur. Gagal mendeteksi = bukan berarti sistem gagal, tapi membuktikan hipotesis bahwa SAST tidak cukup.

4. **Engineering discipline:** Pentingnya versioning (v8→v9→v9.3→v9.5), dokumentasi (struktur-v9.md, ARCHITECTURE.md), dan iterative refinement berdasarkan feedback.

**Jawaban Singkat (30 detik):**
Belajar bahwa "gagal mendeteksi" (0% detection rate) bisa menjadi kontribusi research yang lebih berharga daripada "berhasil mendeteksi" — karena membuktikan batasan SAST dan memperkuat argumen untuk DAST.

**Alasan Penguji Bertanya:**
Refleksi personal. Menunjukkan growth mindset dan kemampuan belajar.

**Kemungkinan Follow-up:**
- Apa kesulitan terbesar?
- Apa yang akan Anda lakukan berbeda kalau mengulang?
- Skill apa yang paling berkembang?

**Tingkat Kesulitan:** ⭐

**Prioritas:** Low

---

## Q027

**Kategori:** Pertanyaan Umum Sidang

**Pertanyaan:**
Jika Anda punya waktu 6 bulan lagi, apa yang akan Anda lakukan?

**Jawaban Ideal:**
Prioritas (urut):

1. **DAST integration (2 bulan):** Tambah OWASP ZAP atau sqlmap sebagai Tahap 5 — ini langsung address 0% detection rate untuk CVE spesifik. Running application → dynamic scan → bandingkan hasil SAST vs DAST.

2. **Multi-run replikasi (1 bulan):** Jalankan 3× per repositori, hitung mean ± std dev untuk semua metrik. Statistik yang valid.

3. **Ekspansi dataset (1 bulan):** 12-16 repositori, 2-3 per kategori McConnell. Termasuk bahasa yang belum diuji (Rust, Ruby).

4. **User study (1 bulan):** Within-subjects experiment — 10 developer, masing-masing review 2 pipeline (AI-generated vs static), ukur time-to-review dan jumlah issues found.

5. **Microservices + K8s support (1 bulan):** Deteksi microservices dari struktur module, generate per-service jobs, K8s manifests validation.

**Jawaban Singkat (30 detik):**
DAST integration untuk fix detection rate, multi-run replikasi untuk statistik valid, ekspansi dataset 12-16 repo, user study, K8s support.

**Alasan Penguji Bertanya:**
Roadmap penelitian. Menunjukkan bahwa mahasiswa paham apa yang kurang dan punya rencana konkret.

**Kemungkinan Follow-up:**
- Kenapa DAST prioritas tertinggi?
- Apakah user study layak secara metodologis?
- Berapa budget untuk ekspansi dataset?

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q041

**Kategori:** BAB I — Latar Belakang

**Pertanyaan:**
Kenapa penelitian ini penting bagi Indonesia?

**Jawaban:**
1. **Adopsi cloud/CI/CD meningkat:** Startup Indonesia (Gojek, Tokopedia, Traveloka, dll) semua pakai CI/CD. Tapi security pipeline masih manual/terabaikan.
2. **Regulasi PDP (UU Perlindungan Data Pribadi):** Organisasi wajib mengamankan data — pipeline security adalah kontrol preventif.
3. **Keterbatasan talent:** DevSecOps engineer langka dan mahal di Indonesia. Sistem ini bisa membantu organisasi yang tidak punya dedicated security engineer.

**Jawaban Singkat (30 detik):**
Indonesia pasar e-commerce terbesar SEA, banyak startup pakai CI/CD, tapi kekurangan DevSecOps engineer. Sistem ini bisa membantu.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

# 3. BAB II — TINJAUAN PUSTAKA

---

## Q042

**Kategori:** BAB II — Teori

**Pertanyaan:**
Apa itu DevSecOps dan bagaimana hubungannya dengan penelitian Anda?

**Jawaban:**
DevSecOps = Development + Security + Operations. Prinsip: mengintegrasikan security practices ke dalam seluruh SDLC, bukan sebagai afterthought di akhir.

Hubungan: (1) **Shift left** — security testing digeser ke kiri, di-generate saat repo dianalisis. (2) **Automation** — pipeline generation + deployment full otomatis. (3) **Continuous security** — pipeline berjalan setiap push/PR. (4) **Tool orchestration** — mengorkestrasi Semgrep + Trivy + Gitleaks + npm/pip audit.

**Jawaban Singkat (30 detik):**
DevSecOps = security integrated ke SDLC. Sistem mewujudkan ini dengan otomasi pipeline security generation, shift left, dan continuous monitoring.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q043

**Kategori:** BAB II — Teori

**Pertanyaan:**
Apa perbedaan SAST, DAST, SCA, dan Secret Scanning?

**Jawaban:**
| Jenis | Fokus | Tools di Sistem | Runtime |
|---|---|---|---|
| SAST | Source code (SQLi, XSS) | Semgrep | Tidak |
| DAST | Running app (injection, misconfig) | (Tidak ada) | Ya |
| SCA | Dependency CVE | npm/pip audit + Trivy fs | Tidak |
| Secret | Hardcoded credentials | Gitleaks | Tidak |
| Container | Image vuln + misconfig | Trivy image | Tidak |

Sistem cover SAST+SCA+Secret+Container. DAST adalah gap utama yang diidentifikasi di Bab V.

**Jawaban Singkat (30 detik):**
SAST = analisis kode statis. DAST = scan app running. SCA = dependency CVE. Secret = credential leak. Cover 4/5, DAST adalah gap.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q044

**Kategori:** BAB II — Teori

**Pertanyaan:**
Apa itu LangGraph dan mengapa dipilih dibanding alternatif?

**Jawaban:**
LangGraph = framework untuk stateful multi-actor applications dengan LLM. Alasan memilih: (1) **State management native** — 97-field TypedDict di-share antar 18 node. (2) **Compiled graph** — compile sekali, reuse untuk semua request. (3) **Deterministic routing** — conditional edges (pass/fail). (4) **Observability** — setiap node execution terekam.

Alternatif yang dipertimbangkan: CrewAI (terlalu agentic), manual state machine (verbose), Prefect/Airflow (bukan untuk LLM).

**Jawaban Singkat (30 detik):**
State management native, compiled graph reusable, deterministic routing. Bukan karena tren — karena match dengan 97-field state machine.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q045

**Kategori:** BAB II — Literature Review

**Pertanyaan:**
Jelaskan paper Meneely et al. (2013) dan relevansinya dengan penelitian Anda.

**Jawaban:**
Meneely et al. (2013), "Vulnerability Clustering in Software Systems," ESEM. Temuan: kerentanan tidak terdistribusi merata — mereka mengelompok berdasarkan domain aplikasi, bahasa, ukuran tim. Misal: e-commerce → input validation + payment; IoT → authentication + firmware.

Relevansi: Landasan teori untuk konsep security coverage. Jika kerentanan mengelompok per domain, pipeline security harus adaptif per domain. Sistem saya mengoperasionalisasi temuan ini via 15 security coverages yang applicable-nya bervariasi per repositori.

**Jawaban Singkat (30 detik):**
Kerentanan mengelompok per domain (e-commerce beda dengan IoT). Jadi pipeline security harus adaptif per domain — landasan konsep security coverage.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q046

**Kategori:** BAB II — Literature Review

**Pertanyaan:**
Jelaskan paper Pashchenko et al. (2018) dan bagaimana hubungannya dengan 0% detection rate.

**Jawaban:**
Pashchenko et al. (2018), MSR. Membandingkan efektivitas SAST/DAST/SCA. Temuan: SAST bagus untuk pola umum (SQLi, XSS, buffer overflow) tapi lemah untuk business logic. Tidak ada tool tunggal superior — kombinasi tools optimal.

Hubungan dengan 0% detection: SAST tidak mendeteksi CVE spesifik karena mayoritas adalah business logic flaws (SSRF via SVG, RCE via theme upload, SQLi via Django ORM HasKey). Ini konsisten dengan temuan paper, bukan kegagalan sistem.

**Jawaban Singkat (30 detik):**
SAST efektif untuk pola umum, lemah untuk business logic. 0% detection rate saya konsisten dengan temuan ini — bukan failure sistem.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q047

**Kategori:** BAB II — Theory

**Pertanyaan:**
Apa itu CI/CD pipeline dan apa saja standard stages yang ada?

**Jawaban:**
CI/CD = Continuous Integration / Continuous Delivery. Pipeline = rangkaian automated steps dari code commit ke production.

Standard stages di sistem saya (8 jobs): lint, test, build, sast, dependency-scan, secret-scan, container-build, container-scan.

Ditambah domain-specific jobs (pci-dss, hipaa, leda-check, csp-headers, mqtt-security, docker-compose-validate) dan AI-generated custom jobs (max 3 per repo, kebab-case, ≥2 actions + SARIF upload).

**Jawaban Singkat (30 detik):**
8 standard jobs (lint/test/build/sast/dep-scan/secret-scan/container-build/container-scan) + domain-specific + AI-generated custom jobs (max 3).

**Tingkat Kesulitan:** ⭐

**Prioritas:** Medium

---

## Q048

**Kategori:** BAB II — Theory

**Pertanyaan:**
Apa itu GitHub Actions dan bagaimana cara kerjanya?

**Jawaban:**
GitHub Actions = CI/CD platform terintegrasi di GitHub. Workflow didefinisikan dalam YAML di `.github/workflows/`. Setiap workflow terdiri dari jobs yang berisi steps (actions atau shell commands).

Sistem saya men-generate file YAML ini, men-commit ke branch baru, dan membuka PR. Setelah di-merge, workflow berjalan setiap push/PR secara otomatis.

Actions yang digunakan dipin SHA-nya (bukan tag) untuk mencegah supply chain attack. `action_registry.py` menyimpan SHA terverifikasi untuk setiap action.

**Jawaban Singkat (30 detik):**
CI/CD platform GitHub. Workflow YAML di `.github/workflows/`. Sistem generate YAML → commit → PR → merge → auto-run.

**Tingkat Kesulitan:** ⭐

**Prioritas:** Low

---

## Q049

**Kategori:** BAB II — Konsep

**Pertanyaan:**
Apa itu Design Science Research (DSR) dan kenapa cocok?

**Jawaban:**
DSR = metodologi penelitian yang menghasilkan artifact. Framework (Peffers et al. 2007): problem identification → solution design → artifact development → demonstration → evaluation → communication.

Cocok karena penelitian menghasilkan artifact (sistem AI agent), bukan theory-building. Evaluasi menggunakan kriteria: functionality, completeness, consistency, accuracy, performance, reliability.

**Jawaban Singkat (30 detik):**
DSR = metodologi untuk menghasilkan artifact. Cocok karena penelitian menghasilkan sistem, bukan teori. Evaluasi berbasis kriteria functionality, accuracy, dll.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q050

**Kategori:** BAB II — Konsep

**Pertanyaan:**
Apa itu OWASP Risk Rating?

**Jawaban:**
Framework untuk menilai severity kerentanan. Original 5-dimensi (Skill, Motive, Opportunity, Size, Ease → Likelihood; Loss, Reputation, Financial → Impact). Saya sederhanakan ke 3-dimensi:
- Likelihood = (TAF + VF) / 2
- Impact = BI
- Risk = L × I

Dimana TAF = Threat Agent Factor (1-9), VF = Vulnerability Factor (1-9), BI = Business Impact (1-9). Risk diskalakan 0-100.

**Jawaban Singkat (30 detik):**
Framework severity rating. Saya pakai 3-dimensi: Likelihood (TAF+VF) × Impact (BI). Output: risk score 0-100.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q051

**Kategori:** BAB II — Konsep

**Pertanyaan:**
Apa itu McConnell classification?

**Jawaban:**
McConnell (2006), "Code Complete," mengklasifikasikan software projects: Business Systems (ERP, e-commerce), Internet Systems (web apps, CMS), Embedded Systems (firmware, IoT), System Software (OS, compiler), General (utility).

Digunakan untuk purposive sampling — memilih repositori dari 4 kategori berbeda untuk variasi maksimal.

**Jawaban Singkat (30 detik):**
Klasifikasi jenis software dari McConnell. Dipakai untuk memilih 4 repositori dari 4 kategori berbeda (purposive sampling).

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

# 4. BAB III — METODOLOGI

---

## Q052

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Mengapa Anda memilih pendekatan multi-node LangGraph dibanding single LLM call?

**Jawaban:**
5 alasan: (1) **Debugging** — setiap tahap punya output intermediate yang bisa diinspeksi. (2) **Fallback per node** — kegagalan di satu node tidak menjatuhkan semua. (3) **Modular development** — node bisa dikembangkan/test independen. (4) **Cost efficiency** — hasil scan repo dipakai semua node, tidak perlu kirim ke LLM berkali-kali. (5) **Research transparency** — 18 node mendokumentasikan 18 langkah reasoning, bukan black box.

**Jawaban Singkat (30 detik):**
Debugging lebih mudah, fallback per node, modular, cost efisien, transparan untuk research.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q053

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Bagaimana Anda mendesain prompt untuk setiap node LLM?

**Jawaban:**
5 prinsip: (1) **Role specification** — "You are a DevSecOps engineer...". (2) **Structured input injection** — `Repository structure: {structure}`. (3) **Concrete JSON schema** — bukan free text, untuk structured parsing. (4) **Domain constraints** — domain enum, static rules exclusion. (5) **Fallback-friendly strictness** — "Be strict. Only mark applicable if clear signal."

**Jawaban Singkat (30 detik):**
Persona, structured input, JSON schema strict, domain-specific constraints, conservative classification.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q054

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Apakah prompt engineering bisa dianggap sebagai metodologi penelitian?

**Jawaban:**
**Tidak.** Prompt adalah **research instrument** (seperti kuesioner di penelitian survey). Metodologi adalah **bagaimana instrument dirancang, divalidasi, dan kualitas output diukur.** Di Bab III, tulis design rationale di balik prompt — bukan copy-paste prompt. Ini critical risk dari README-RISIKO-BAB3.md.

**Jawaban Singkat (30 detik):**
Prompt = instrument (seperti kuesioner). Metodologi = bagaimana dirancang + divalidasi. Jangan tulis Bab III seperti dokumentasi prompt.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q055

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Bagaimana Anda menentukan 15 security coverages? Apakah arbitrer?

**Jawaban:**
Tidak arbitrer. Bottom-up: analisis >50 repositori, mapping library → kategori kerentanan. Top-down: OWASP Top 10, API Security Top 10, PCI-DSS, HIPAA, domain-specific threat modeling. Setiap coverage punya sinyal deteksi concrete (library, route, entity, deployment). Coverage tanpa sinyal jelas di-drop.

**Jawaban Singkat (30 detik):**
Dari analisis 50+ repo (bottom-up) + mapping standar keamanan (top-down). Validasi dengan sinyal deteksi concrete per coverage.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q056

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Mengapa workflow generator deterministic, bukan LLM-based?

**Jawaban:**
(1) **Safety** — YAML tidak boleh probabilistik. Satu karakter salah → gagal. (2) **SHA pinning** — LLM bisa halusinasi SHA. (3) **Permissions** — LLM over-permission; deterministic = least privilege. (4) **Testability** — deterministic bisa unit test. (5) **Compliance** — consistent security policy.

**Jawaban Singkat (30 detik):**
YAML generation harus deterministic karena SHA pinning, permissions, compliance tidak boleh probabilistik. LLM untuk reasoning, bukan generation.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q057

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Bagaimana Anda menangani inkonsistensi output LLM?

**Jawaban:**
4 level: (1) Temperature rendah (0.3). (2) Structured JSON output + 3× retry + schema validation via Pydantic. (3) Deterministic fallback per node ke arah conservative (under-detect). (4) `analyze_structured()` method di `llm_service.py` sebagai single point of JSON parsing.

**Jawaban Singkat (30 detik):**
Temperature rendah, structured JSON, 3× retry, fallback deterministic, conservative defaults.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q058

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Mengapa menggunakan multi-provider LLM abstraction?

**Jawaban:**
(1) Vendor independence. (2) Cost optimization (MiniMax vs GPT). (3) Switch provider via env tanpa code change. (4) Reproducibility dengan provider yang peneliti lain punya. (5) Structured output abstraction di satu tempat.

**Jawaban Singkat (30 detik):**
Tidak lock-in, optimasi cost, switch via env, reproducible, single abstraction.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q059

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Kenapa tidak single-run LLM generation untuk seluruh pipeline?

**Jawaban:**
Pertanyaan "iseng" yang serius. Single call besar = (1) LLM harus "mengingat" semua intermediate reasoning tanpa tools, (2) context window risk — repo besar >100K token, (3) tidak ada fallback granular, (4) sulit debug — kalau output salah, tidak tahu reasoning mana yang salah. Multi-node = "chain of thought" yang enforced oleh system architecture.

**Jawaban Singkat (30 detik):**
Multi-node memaksa "chain of thought" yang verifiable. Single call = black box yang sulit di-debug jika salah.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q060

**Kategori:** BAB III — Metodologi

**Pertanyaan:**
Bagaimana Anda memilih temperature 0.3 untuk LLM?

**Jawaban:**
Trade-off determinism vs quality. 0.0 = deterministic tapi kadang "stuck". 0.3 = slight variation untuk membedakan input berbeda. Lesson: 0.3 masih terlalu bervariasi → Bab V rekomendasi 0.0 + seed.

**Jawaban Singkat (30 detik):**
Trade-off. 0.3 = slight variation. Tapi ternyata masih variatif → rekomendasi 0.0 di Bab V.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 5. BAB IV — IMPLEMENTASI & HASIL

---

## Q061

**Kategori:** BAB IV — Implementasi

**Pertanyaan:**
Ceritakan arsitektur 3-lapis sistem Anda secara detail.

**Jawaban:**
**Layer 1 — Frontend (React + TypeScript + Vite):** 15 halaman, 26+ komponen. State: AuthContext + usePipeline hooks. Port 5173.

**Layer 2 — Backend (Go + Gin):** 40+ REST endpoints. JWT auth + RBAC. PostgreSQL (persistent) + Redis (caching/session). Dependency injection pattern manual. Port 8080 internal, 8081 exposed.

**Layer 3 — AI Service (Python + FastAPI + LangGraph):** 18-node compiled graph. 11 LLM calls. 5 LLM providers (OpenAI, Anthropic, OpenRouter, OpenCode, Google). Port 8000.

**Infra:** Docker Compose (postgres, redis, backend, ai-service, frontend, nginx). Nginx sebagai reverse proxy.

**Jawaban Singkat (30 detik):**
React → Go REST API → Python AI service. PostgreSQL + Redis. Docker Compose. Nginx reverse proxy.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q062

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Kenapa domain detection semua repositori menghasilkan "general"?

**Jawaban:**
Domain detection bergantung pada library-specific signals di top-30 imports. Django-oscar: tidak ada payment SDK → bukan e-commerce walaupun oscar-based. Ghost: tidak ada marked/dompurify → bukan blog. ThingsBoard: Milo/Leshan/Californium tidak masuk top-30 → bukan IoT. LLM confidence 1.00 tapi salah → LLM overconfidence. Domain sub_type terdeteksi (oscar-based) tapi tidak diteruskan ke upstream coverage inference. Batasan di §4.9.

**Jawaban Singkat (30 detik):**
Top-30 imports tidak mengandung library domain-specific → LLM overconfident → semua "general."

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q063

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Apa insight paling penting dari ThingsBoard pipeline generation?

**Jawaban:**
Custom job `container-compose-hardening` (K2.4) menghasilkan 27 finding unik — validasi `security_opt` dan `no-new-privileges` di 20+ docker-compose files. Tidak akan terdeteksi Semgrep standar. Bukti empiris K2.4 efektif. Job ini dibuat oleh `job_reasoning` node yang menganalisis struktur compose files ThingsBoard.

**Jawaban Singkat (30 detik):**
27 finding dari K2.4 — tidak akan ada tanpa custom AI job. Bukti kontribusi nyata.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q064

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Mengapa detection rate CVE 0%? Apa yang salah?

**Jawaban:**
**Tidak ada yang salah.** Ini expected untuk SAST-only. CVE-2024-53908 (Django HasKey SQLi): SAST tidak paham `__has_key=` syntax = SQL. CVE-2026-26980 (Ghost SQLi 9.8): detected partially tapi bukan CVE spesifik. CVE-2025-34282 (ThingsBoard SSRF via SVG 9.1): image gallery processing di luar ruleset. 3 CVE Ghost RCE/SSRF: business logic flaws di luar SAST scope (konsisten Baca et al. 2008).

**Jawaban Singkat (30 detik):**
Expected. SAST tidak deteksi business logic, framework-specific patterns, atau runtime behavior. Contoh: Django HasKey SQLi, SSRF via SVG.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q065

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Kenapa AI Service (repo ke-4) gagal total?

**Jawaban:**
"Pipeline metadata was not available when the PDF was generated." AI service tidak merespons saat pengujian (timeout/race condition). Hasil: 0 coverages, 0 jobs, 2 synthetic findings. Ironis — sistem gagal analisis dirinya sendiri. Bukti ketergantungan tinggi pada LLM. Dicatat di §5.1.4.

**Jawaban Singkat (30 detik):**
AI service timeout. 0 coverages, 0 jobs. Ironis — sistem sendiri gagal. Bukti ketergantungan LLM.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q066

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Apakah 270 findings itu banyak? Bandingkan dengan baseline.

**Jawaban:**
270 findings = output orkestrasi 4 tools (Semgrep + Trivy + Gitleaks + npm/pip audit). Bukan "hasil AI" — hasil tools. Tidak ada baseline formal. Yang baru: 27 findings dari K2.4 custom jobs. CodeQL mungkin menghasilkan lebih banyak, SonarQube lebih mature. Tapi tidak ada yang mengorkestrasi multi-tool + generate custom jobs based on repo context.

**Jawaban Singkat (30 detik):**
270 findings = multi-tool orchestration. 27 unique dari K2.4. Bukan jumlah yang penting, tapi coverage diversity.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q067

**Kategori:** BAB IV — Implementasi

**Pertanyaan:**
Mengapa workflow validator selalu return `validation_errors = []`? Mencurigakan?

**Jawaban:**
By design — validator **non-blocking** (advisory). `validation_errors` selalu kosong karena tidak mendeteksi error critical. Semua issues masuk ke `validation_findings` (+ `validation_warnings`). `workflow_repair` dormant. Dipilih karena: (1) SHA check mungkin gagal network — tidak boleh blocking deploy. (2) Validasi best-effort — lebih baik deploy dengan warning daripada tidak deploy.

**Jawaban Singkat (30 detik):**
By design — non-blocking. Error critical → warning. Lebih baik deploy dengan warning daripada tidak deploy.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q068

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Apa yang terjadi dengan Gitleaks di ThingsBoard?

**Jawaban:**
False positive — Gitleaks mendeteksi placeholder `password` di file konfigurasi default ThingsBoard. Bukan bug sistem, keterbatasan Gitleaks regex-based. Run #2 failed karena secret-scan failure. Dicatat sebagai kendala teknis §4.9. Mitigasi: whitelist pattern di Gitleaks config.

**Jawaban Singkat (30 detik):**
False positive — placeholder password di konfigurasi default. Keterbatasan Gitleaks. Perlu whitelist.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q069

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Mengapa CVSS sum ThingsBoard lebih rendah dari Ghost?

**Jawaban:**
Ghost: 44 dependency CVE critical di yarn.lock → 101 findings, CVSS 632.4. Node.js ecosystem punya banyak dependency high-CVSS CVE. ThingsBoard: 70 findings didominasi Semgrep generic (weak random, weak SSL, CVSS medium-high) + custom jobs low severity. Java dependencies lebih sedikit dan stabil.

**Jawaban Singkat (30 detik):**
Ghost = 44 CVE critical dari yarn.lock. ThingsBoard = Semgrep generic + custom jobs low severity.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q070

**Kategori:** BAB IV — Implementasi

**Pertanyaan:**
Apa itu custom Semgrep rules merger dan kenapa dipisah dari workflow YAML?

**Jawaban:**
`_collect_merged_semgrep_rules()` menggabungkan Tier 1 static rules (ecommerce.yml, blog-csp.yml, iot-mqtt.yml) + K2.3 AI-generated rules ke `.github/ai-devsecops-rules.yml`. Dipisah karena GitHub Actions workflow punya limit 21K char per expression. Ruleset Semgrep bisa >50K char untuk domain kompleks. File di-commit sebagai file terpisah di `.github/`.

**Jawaban Singkat (30 detik):**
Gabung static + AI-generated rules → file terpisah karena limit 21K char workflow YAML.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q071

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Bagaimana coverage-to-finding mapping bekerja?

**Jawaban:**
Setiap finding di-enrich dengan `security_coverage` di Tahap 4 via `_infer_security_coverage()`. Static keyword map `_TYPE_TO_COVERAGE`: keyword `sql`, `orm`, `sequelize` → `data_security`. Keyword `jwt`, `oauth`, `session` → `authentication_security`. Muncul di PDF Section 5.3: coverage mana menghasilkan findings terbanyak.

**Jawaban Singkat (30 detik):**
Keyword-based mapping: SQL → data_security, JWT → authentication_security. Dipakai di PDF report.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q072

**Kategori:** BAB IV — Implementasi

**Pertanyaan:**
Kenapa action_registry.py 914 baris?

**Jawaban:**
SSOT untuk setiap GitHub Action. Setiap entry: owner/repo, inputs (supported + required), permissions (with scope), runner/node compatibility, deprecated status, pinned SHA, pinned version. Validator cross-check YAML dengan registry. Unknown action → `workflow_config_issue`.

**Jawaban Singkat (30 detik):**
SSOT untuk semua actions — SHA, permissions, compatibility. 914 baris = comprehensive coverage.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q073

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Kenapa coverage applicable rata-rata hanya 30%?

**Jawaban:**
Deteksi hanya top-30 imports. `logging_security`, `cms_security`, `file_upload_security` 0% karena library terkait tidak di top-30. Ini ceiling akurasi dari library-level detection. PHP, logger, CMS libs sering tidak muncul di top imports. Solusi (Bab V): scan full `package.json`/`requirements.txt`/`pom.xml` + stdlib detection.

**Jawaban Singkat (30 detik):**
Deteksi top-30 imports saja. Library spesifik sering tidak masuk top-30 → coverage under-detect.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q074

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Apakah pipeline yang dihasilkan benar-benar adaptif?

**Jawaban:**
Ya — bukti: 11 vs 9 vs 10 jobs (different), custom jobs berbeda per domain (django: auth+data+container, ghost: data+container, thingsboard: container+IoT), coverage applicable berbeda (4 vs 3 vs 5). 27 finding unik di ThingsBoard dari custom job. Variasi adalah bukti adaptivitas. Tapi 0 untuk AI service = adaptivitas gagal ketika AI down.

**Jawaban Singkat (30 detik):**
Ya. Pipeline bervariasi: 11/9/10 jobs, custom jobs berbeda per domain. Variasi = adaptivitas.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q075

**Kategori:** BAB IV — Hasil

**Pertanyaan:**
Mengapa coverage `payment_security` 0% di django-oscar padahal itu e-commerce?

**Jawaban:**
django-oscar support Stripe/PayPal tapi tidak ada dependency yang di-pin di `setup.py`. Sistem hanya mendeteksi library dari top-30 imports — tidak scan `requirements.txt` penuh. Tanpa payment SDK yang terdeteksi, `payment_security` tidak applicable. Ini **bias dataset** — django-oscar memang tidak meng-include payment SDK di dependency production (payment adalah plugin opsional).

**Jawaban Singkat (30 detik):**
Tidak ada payment SDK di dependency → sistem tidak detect → payment_security tidak applicable. Bias dataset.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 6. BAB V — KESIMPULAN

---

## Q076

**Kategori:** BAB V — Kesimpulan

**Pertanyaan:**
Apakah 3 kontribusi (K1, K2, K3) tervalidasi?

**Jawaban:**
Tervalidasi parsial. K1: F1=1.00 bahasa, framework presisi tinggi, deployment akurat — tapi domain lemah. K2: 12/40 coverages, 27 finding K2.4 — tapi 30% under-detect. K3: 272 findings, 3 pipeline valid — tapi 0% CVE detection. Semua punya kekuatan dan kelemahan yang didokumentasikan.

**Jawaban Singkat (30 detik):**
Parsial. K1 (bahasa ok, domain lemah), K2 (27 finding K2.4, under-detect), K3 (272 findings, 0% CVE).

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q077

**Kategori:** BAB V — Kesimpulan

**Pertanyaan:**
Apa temuan paling mengejutkan?

**Jawaban:**
(1) 0% detection rate = bukti empiris batasan SAST, bukan failure. (2) Sistem gagal analisis dirinya sendiri (AI Service repo ke-4). (3) 27 finding dari K2.4 — bukti konkret kontribusi yang measurable.

**Jawaban Singkat (30 detik):**
0% = bukti batasan SAST. Gagal analisis sendiri. 27 finding K2.4 = kontribusi measurable.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q078

**Kategori:** BAB V — Saran

**Pertanyaan:**
Kenapa saran utama adalah DAST?

**Jawaban:**
SAST terbukti 0% detection untuk CVE spesifik (business logic, framework-specific, runtime behavior). DAST (OWASP ZAP/sqlmap) uji aplikasi runtime → langsung address gap ini. Sebagai Tahap 5 setelah security_analysis, DAST akan meningkatkan detection rate ke angka measurable.

**Jawaban Singkat (30 detik):**
SAST 0% detection. DAST uji runtime → tutup gap business logic. Prioritas tertinggi.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q079

**Kategori:** BAB V — Kesimpulan

**Pertanyaan:**
Apakah sistem ini bisa menggantikan DevSecOps engineer?

**Jawaban:**
**Tidak.** "Sistem ini adalah **pelengkap, bukan pengganti**" (§5.4). Sistem mengotomasi pipeline generation dan security scanning, tapi: (1) Hasil tetap perlu human review (PR-based workflow by design). (2) False positives butuh human triage. (3) Business logic flaws tidak terdeteksi. (4) Custom compliance requirements butuh human expertise.

Sistem meningkatkan efisiensi DevSecOps engineer — mengerjakan bagian repetitive (YAML generation, tool orchestration) — tapi tidak menggantikan expertise.

**Jawaban Singkat (30 detik):**
Tidak. Pelengkap, bukan pengganti. Otomasi bagian repetitive, human review + expertise tetap diperlukan.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

# 7. SOURCE CODE

---

## Q080

**Kategori:** Source Code

**Pertanyaan:**
Mengapa backend Go (Gin) dan bukan Express atau FastAPI?

**Jawaban:**
(1) Performance — Go compiled, goroutines. (2) Type safety — compile-time check. (3) Single binary deployment. (4) Separation of concerns — AI service sudah Python, backend tidak perlu Python lagi.

**Jawaban Singkat (30 detik):**
Go untuk REST API (performance, type safety, single binary). Python untuk AI (ecosystem LangChain).

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q081

**Kategori:** Source Code

**Pertanyaan:**
Kenapa pakai Redis?

**Jawaban:**
Session caching (JWT blacklist), rate limiting, short-lived metadata cache (TTL 5m). PostgreSQL untuk persistent data. Redis untuk volatile high-speed access.

**Jawaban Singkat (30 detik):**
Session + rate limiting + cache. PG = persistent, Redis = volatile fast-access.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q082

**Kategori:** Source Code

**Pertanyaan:**
Mengapa workflow_generator.py 5,808 baris?

**Jawaban:**
Monolithic untuk velocity development. Mencakup: static job templates, domain-specific builders, AI job emission, Semgrep merger, YAML composer, stage selector, validators, auto-fix. Perlu refactoring ke modul: `job_builders.py`, `yaml_composer.py`, `validators.py`, `semgrep_merger.py`. Future work.

**Jawaban Singkat (30 detik):**
Monolithic velocity. Perlu refactoring. Diakui tech debt.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q083

**Kategori:** Source Code

**Pertanyaan:**
Mengapa TypedDict untuk state (bukan Pydantic)?

**Jawaban:**
LangGraph requirement — state graph pakai TypedDict. Type hinting tanpa overhead validation. Kelemahan: tidak ada runtime validation — dimitigasi dengan conditional checks di setiap node.

**Jawaban Singkat (30 detik):**
LangGraph requires TypedDict. Type hinting ringan. Runtime validation via conditional checks.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q084

**Kategori:** Source Code

**Pertanyaan:**
Kenapa dua file missing (domain_priority.py, scan_directives.py)?

**Jawaban:**
Direncanakan, diimpor, belum committed. Technical gap yang perlu di-fix untuk reproducibility. Kemungkinan untuk v9.5. Keduanya direferensi oleh kode exist + dokumentasi.

**Jawaban Singkat (30 detik):**
Planned, imported, not committed. Gap yang perlu di-fix.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q085

**Kategori:** Source Code

**Pertanyaan:**
Bagaimana dependency injection di Go backend?

**Jawaban:**
Manual DI (tanpa Wire/Fx). Pattern: `New{Handler}(service) *Handler`. Main function wiring: db → repos → services → handlers. Repository pattern dengan interface. Testing dengan mock.

**Jawaban Singkat (30 detik):**
Manual DI. Main wiring: db → repo → service → handler. Interface untuk mock.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

# 8. DEVSECOPS

---

## Q086

**Kategori:** DevSecOps

**Pertanyaan:**
Apa perbedaan CI/CD biasa vs DevSecOps pipeline?

**Jawaban:**
CI/CD biasa: lint → test → build → deploy. DevSecOps: +SAST +dependency scan +secret scan +container scan di setiap stage. Sistem saya = DevSecOps pipeline with domain-specific + AI-generated security stages.

**Jawaban Singkat (30 detik):**
+Security scanning integrated di setiap stage. Bukan afterthought di akhir.

**Tingkat Kesulitan:** ⭐

**Prioritas:** High

---

## Q087

**Kategori:** DevSecOps

**Pertanyaan:**
Kenapa Semgrep (bukan CodeQL/SonarQube)?

**Jawaban:**
Open source, custom rules YAML (mudah), SARIF native, multi-language, CI/CD native (`semgrep ci`). CodeQL lebih powerful tapi ruleset kompleks (QL language). SonarQube butuh server. Semgrep = sweet spot.

**Jawaban Singkat (30 detik):**
YAML rules sederhana, open source, CI/CD native. Tidak perlu server atau belajar QL.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q088

**Kategori:** DevSecOps

**Pertanyaan:**
Apa itu SHA pinning dan kenapa penting?

**Jawaban:**
Pakai commit hash (bukan tag) untuk GitHub Action. Tag mutable (bisa diupdate maintainer → supply chain attack). SHA immutable. `action_registry.py` menyimpan SHA terverifikasi untuk semua actions.

**Jawaban Singkat (30 detik):**
Hash instead of tag. Hash immutable, tag mutable → supply chain risk.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** High

---

## Q089

**Kategori:** DevSecOps

**Pertanyaan:**
Security coverage vs security control — bedanya?

**Jawaban:**
Coverage = area keamanan high-level (authentication, data, payment). Control = tools spesifik (SAST dengan ruleset p/sql-injection, secret scan fokus Stripe). Satu coverage → multiple controls.

**Jawaban Singkat (30 detik):**
Coverage = apa yang di-cover (context-based). Control = bagaimana meng-cover (tools-based).

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q090

**Kategori:** DevSecOps

**Pertanyaan:**
Bagaimana pipeline jobs dipilih?

**Jawaban:**
3-layer: (1) Standard 8 jobs (always). (2) Domain-specific jobs (based on domain + augmentations). (3) AI custom jobs (K2.4, max 3). Difilter oleh `_filter_stages_by_evidence()` + `_validate_pipeline_prerequisites()`.

**Jawaban Singkat (30 detik):**
Standard (always) + Domain (context-based) + AI custom (max 3). Filtered by evidence.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q091

**Kategori:** DevSecOps

**Pertanyaan:**
Apakah pipeline yang digenerate production-ready?

**Jawaban:**
**Tidak.** Starting point untuk human review. PR workflow by design — developer HARUS review sebelum merge. Perlu tuning: (1) ruleset adjustment, (2) infrastructure-specific config, (3) compliance add-ons, (4) organization-specific security policies.

**Jawaban Singkat (30 detik):**
Tidak — starting point. PR-based untuk human review. Perlu tuning per organisasi.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q092

**Kategori:** DevSecOps

**Pertanyaan:**
Apa itu SBOM dan kenapa tidak ada di sistem?

**Jawaban:**
SBOM = Software Bill of Materials — daftar semua komponen/dependency di software. Penting untuk supply chain security (tahu apa yang dipakai). Tidak ada di sistem karena scope difokuskan ke SAST + SCA + secret + container. SBOM generation (via Syft/SPDX) adalah future work — direferensi di `security-desc.md` sebagai control tapi tidak diimplementasikan.

**Jawaban Singkat (30 detik):**
Daftar dependency formal. Tidak ada karena scope fokus SAST+SCA+secret+container. Future work.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 9. AI / LLM

---

## Q093

**Kategori:** AI/LLM

**Pertanyaan:**
Model apa yang Anda gunakan dan kenapa?

**Jawaban:**
MiniMax-m3 via OpenRouter (default). Alasan: (1) Biaya rendah ($0.30/M input, $1.20/M output) — ~$0.03/repo. (2) Context window 128K token. (3) Structured JSON output reliable. (4) OpenRouter abstraction bikin mudah switch. GPT-4o 15× lebih mahal. Anthropic Claude untuk kualitas, tapi lebih mahal.

**Jawaban Singkat (30 detik):**
MiniMax-m3 — murah ($0.03/repo), 128K context, JSON reliable. 15× lebih murah dari GPT-4o.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q094

**Kategori:** AI/LLM

**Pertanyaan:**
Apakah Anda mengalami hallucination dari LLM? Contohnya?

**Jawaban:**
Ya — domain_detection overconfidence (confidence 1.0 tapi salah: django-oscar = e-commerce tapi dibilang general). JSON parsing kadang gagal (markdown fences, missing fields). Mitigasi: structured output parsing + 3 retry + deterministic fallback. Temperature 0.3 kemungkinan berkontribusi. Untuk generation (workflow YAML), hallucination dicegah dengan tidak pakai LLM untuk generation — hanya reasoning.

**Jawaban Singkat (30 detik):**
Ya — domain overconfidence, JSON errors. Mitigasi: retry + fallback deterministic. YAML generation tidak pakai LLM.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q095

**Kategori:** AI/LLM

**Pertanyaan:**
Kenapa tidak pakai RAG (Retrieval Augmented Generation)?

**Jawaban:**
RAG cocok untuk knowledge retrieval dari dokumen eksternal (policy document, compliance standard). Sistem saya fokus pada code analysis yang membutuhkan reasoning, bukan retrieval. Context already ada di prompt injection (repository files, structure, detected technologies). RAG bisa menjadi future enhancement: retrieve CVE database untuk perbandingan, atau retrieve security policy organisasi untuk compliance checking.

**Jawaban Singkat (30 detik):**
Tidak butuh — semua context ada di prompt injection via state. RAG potensial untuk CVE database retrieval.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q096

**Kategori:** AI/LLM

**Pertanyaan:**
Apakah Anda khawatir tentang LLM vendor lock-in?

**Jawaban:**
Tidak — sistem dirancang untuk multi-provider. `get_llm()` dispatch via env `LLM_PROVIDER`. Prompt tidak ada yang provider-specific (tidak ada "as OpenAI..." atau "as Claude..."). Semua output diminta dalam JSON structured. Switch provider = ganti env variable. Sudah diuji dengan 5 provider.

**Jawaban Singkat (30 detik):**
Tidak. Multi-provider by design. Ganti env = ganti provider. Prompt provider-agnostic.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q097

**Kategori:** AI/LLM

**Pertanyaan:**
Anda menyebut "11 LLM calls" — apa saja itu?

**Jawaban:**
Tahap 1 (4 calls): technology_detection, architecture_detection, deployment_detection, domain_detection.
Tahap 2 (4 calls): coverage_inference, pattern_inference (K2.3), pipeline_augmentation, job_reasoning (K2.4).
Tahap 3 (1 dormant): workflow_repair (tidak pernah dipanggil — validator selalu pass).
Tahap 4 (2 calls): security_analysis enrichment, recommendation_generation.

Total 10 aktif + 1 dormant = 11 LLM calls defined.

**Jawaban Singkat (30 detik):**
4 (Tahap 1) + 4 (Tahap 2) + 0 (Tahap 3 dormant) + 2 (Tahap 4) = 10 calls. 11 dengan dormant.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q098

**Kategori:** AI/LLM

**Pertanyaan:**
Kenapa tidak pakai agentic AI (tool-using agents)?

**Jawaban:**
Sistem saya "agent" dalam arti multi-step reasoning, bukan "agent" dalam arti LLM yang autonomously memilih tools. Alasan: (1) Agentic LLM unpredictable — LLM mungkin memilih tools yang salah atau tidak available. (2) GitHub API rate limiting — agentic LLM bisa exhaust API calls. (3) Deterministic pipeline generation — tidak ada keputusan runtime, semua pre-computed. (4) Cost — agentic LLM butuh banyak API calls (observation loop).

Untuk v9.5+ bisa dipertimbangkan: ReAct agent untuk runtime remediation (kalau workflow gagal, agent debug + fix + replan).

**Jawaban Singkat (30 detik):**
Agentic = unpredictable + expensive + api-exhausting. Multi-step deterministic lebih terkontrol.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q099

**Kategori:** AI/LLM

**Pertanyaan:**
Anda menyebut temperature 0.3 — bagaimana dengan seed?

**Jawaban:**
Seed tidak digunakan di pengujian saat ini. Diakui sebagai kelemahan untuk reproducibility. Bab V rekomendasi seed-controlled generation untuk eksperimen final. Beberapa provider tidak support seed (MiniMax?). Alternatif: temperature 0.0 memberikan near-deterministic output untuk kebanyakan provider.

**Jawaban Singkat (30 detik):**
Tidak pakai seed. Diakui kelemahan. Rekomendasi: seed + temperature 0.0 di Bab V.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 10. SECURITY

---

## Q100

**Kategori:** Security

**Pertanyaan:**
Apa itu OWASP Top 10 dan bagaimana hubungannya dengan 15 coverages Anda?

**Jawaban:**
OWASP Top 10 (2021): Broken Access Control, Cryptographic Failures, Injection, Insecure Design, Security Misconfiguration, Vulnerable Components, Auth Failures, Software & Data Integrity Failures, Logging & Monitoring Failures, SSRF.

Hubungan: 15 coverages saya adalah operasionalisasi OWASP Top 10 ke tingkat yang lebih spesifik dan actionable:
- A1 (Broken Access Control) → api_security
- A2 (Cryptographic Failures) → data_security
- A3 (Injection) → data_security
- A6 (Vulnerable Components) → dependency_security
- A7 (Auth Failures) → authentication_security
- A8 (Integrity Failures) → dependency_security
- A9 (Logging Failures) → logging_security

Plus coverages spesifik domain yang tidak ada di OWASP (payment_security → PCI-DSS, iot_security, healthcare_security → HIPAA).

**Jawaban Singkat (30 detik):**
Coverages = OWASP Top 10 dioperasionalisasi + domain-specific extensions (PCI-DSS, HIPAA, IoT).

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q101

**Kategori:** Security

**Pertanyaan:**
Apa perbedaan CVSS dan OWASP Risk Rating?

**Jawaban:**
CVSS (Common Vulnerability Scoring System): Base score untuk CVE spesifik — severity kerentanan INHERENT (tanpa mempertimbangkan konteks deployment). Composed: AV, AC, PR, UI, S, C, I, A.

OWASP Risk Rating: Risk score yang mempertimbangkan KONTEKS — threat agent (skill, motive), vulnerability (discovery, exploit), business impact. Risk = Likelihood × Impact.

Sistem saya menggunakan OWASP (3-dimensi) karena mempertimbangkan konteks repositori. CVSS score juga dikumpulkan tapi sebagai aggregate metric per repo.

**Jawaban Singkat (30 detik):**
CVSS = severity inherent (CVE-specific). OWASP = risk kontekstual (threat + vuln + impact). Pakai OWASP.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q102

**Kategori:** Security

**Pertanyaan:**
Bagaimana Anda membedakan false positive dan true positive?

**Jawaban:**
Secara manual. Tidak ada automated FP/TP classification. Untuk ground truth validation, 14 CVE target dibandingkan manual dengan findings yang terdeteksi. Hasil: 0 TP, 12 FN, 2 Partial.

Keterbatasan: tanpa automated FP/TP, tidak bisa menghitung precision/recall secara otomatis untuk semua findings. Future work: benchmark dengan tools established (CodeQL) + manual labeling dengan multiple annotators (inter-rater reliability Cohen's Kappa).

**Jawaban Singkat (30 detik):**
Manual comparison dengan ground truth CVE. Tidak automated. Perlu multi-annotator untuk FP/TP labeling.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

## Q103

**Kategori:** Security

**Pertanyaan:**
Kenapa tidak ada penetration testing (pentest) di sistem?

**Jawaban:**
Pentest = DAST manual/automated yang membutuhkan aplikasi running. Sistem saat ini hanya SAST (static). DAST adalah rekomendasi utama Bab V. Pentest automated (OWASP ZAP, sqlmap) akan menjadi Tahap 5.

**Jawaban Singkat (30 detik):**
Belum — scope SAST only. DAST/pentest = rekomendasi utama Bab V.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q104

**Kategori:** Security

**Pertanyaan:**
Bagaimana Anda menangani false positive yang tinggi di SAST?

**Jawaban:**
Saat ini tidak ada automated FP reduction. Semgrep OSS dan Gitleaks menghasilkan false positive (contoh: Gitleaks di ThingsBoard). Strategi untuk production: (1) Whitelist/Gitleaks allowlist untuk known-FP. (2) AI-based triage — LLM bisa mengevaluasi apakah finding benar atau FP berdasarkan kode konteks. (3) Severity threshold — low severity findings bisa di-suppress.

**Jawaban Singkat (30 detik):**
Belum otomatis. Whitelist + AI triage + severity threshold adalah strategi mitigasi.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 11. PENGUJI ISENG

---

## Q105

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kalau tanpa AI bagaimana? Bisakah pakai regex saja?

**Jawaban:**
Untuk beberapa node ya: technology_detection punya extension-based fallback (regex file extension → language). deployment_detection punya file-pattern scan. Tapi untuk tugas yang butuh semantic understanding (domain_detection, coverage_inference, pattern_inference, job_reasoning) — tidak bisa regex.

Regex tidak bisa memahami "Stripe SDK terdeteksi → payment_security applicable → perlu PCI-DSS ruleset + secret scan fokus Stripe." Butuh reasoning tentang hubungan antara library, framework, domain, dan jenis kerentanan. AI mengisi gap ini.

**Jawaban Singkat (30 detik):**
Regex ok untuk deteksi file extension. Tidak ok untuk semantic reasoning (coverage inference, job design).

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q106

**Kategori:** Penguji Iseng

**Pertanyaan:**
Mengapa tidak pakai Python untuk semua? Kenapa Go?

**Jawaban:**
Python untuk AI service (ekosistem LangChain/LangGraph). Go untuk backend REST API (performance, type safety, deployment). Memisahkan concerns: Python heavy-lifting di AI, Go fast-serving di API.

**Jawaban Singkat (30 detik):**
Python untuk AI (ecosystem), Go untuk REST API (performance). Poliglot by design.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q107

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kenapa tidak pakai Jenkins? GitHub Actions saja?

**Jawaban:**
Jenkins butuh server sendiri, maintenance overhead, plugin management. GitHub Actions terintegrasi native dengan repositori (branch, PR, triggers). Untuk startup tanpa DevOps team, Jenkins terlalu berat. GitHub Actions adalah batasan penelitian. Ekstensi ke Jenkins/GitLab CI = future work.

**Jawaban Singkat (30 detik):**
Jenkins butuh server + maintenance. GitHub Actions native GitHub integration. Batasan deliberate.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q108

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kenapa tidak pakai Kubernetes?

**Jawaban:**
K8s butuh cluster minimum, setup kompleks untuk penelitian scope. Docker Compose cukup untuk development/demo. Batasan B4: deployment target hanya Docker. K8s + Terraform + Helm = future work.

**Jawaban Singkat (30 detik):**
Docker Compose cukup untuk demo. K8s overkill untuk scope penelitian. Future work.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q109

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kenapa tidak pakai GPT-4o langsung?

**Jawaban:**
Biaya — GPT-4o 15× lebih mahal ($2.00 vs $0.13 untuk 4 repo). Untuk penelitian dengan limited budget, MiniMax-m3 cukup untuk reasoning. Abstraksi provider memungkinkan switch ke GPT-4o untuk production jika diperlukan kualitas lebih tinggi.

**Jawaban Singkat (30 detik):**
15× lebih mahal. MiniMax cukup untuk reasoning. Abstraksi = mudah switch.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Medium

---

## Q110

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kenapa tidak pakai Claude?

**Jawaban:**
Claude via Anthropic lebih mahal dan rate limit ketat. Tapi didukung via abstraksi provider — tinggal ganti env. Diuji kompatibel tapi tidak dipakai sebagai default. Claude bagus untuk reasoning panjang, tapi cost tidak justify untuk pengujian 4 repo.

**Jawaban Singkat (30 detik):**
Didukung via abstraksi. Tidak dipakai default karena cost. Mudah switch via env.

**Tingkat Kesulitan:** ⭐⭐

**Prioritas:** Low

---

## Q111

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kenapa hasil Anda bisa dipercaya? Bisa di-reproduce?

**Jawaban:**
Infrastruktur reproducible (Docker Compose, open source). Hasil semi-reproducible (LLM non-determinism). Validasi: deterministic generator, ground truth CVE, multi-tool orchestration. Keterbatasan diakui: temperature 0.3, 1 run, 4 repo. Butuh temperature 0.0 + seed + multiple runs untuk full reproducibility.

**Jawaban Singkat (30 detik):**
Infrastruktur reproducible. Hasil semi-reproducible. Keterbatasan diakui transparan di Bab V.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q112

**Kategori:** Penguji Iseng

**Pertanyaan:**
Kalau saya kasih repo Python, framework FastAPI, domain fintech — apa yang terjadi?

**Jawaban:**
Sistem akan: (1) Deteksi Python + FastAPI. (2) Deteksi deployment (Docker jika ada Dockerfile). (3) Domain detection — jika ada library fintech (plaid, dwolla) atau entity (ledger, wallet), terdeteksi fintech. Jika tidak → general. (4) Coverage inference — authentication, api, data, fintech_security applicable jika library terdeteksi. (5) Custom rules — fokus pada fintech-specific patterns. (6) Custom jobs — mungkin ledger validation atau KYC check. (7) Pipeline — standard 8 jobs + fintech-specific + custom jobs.

Tapi realitas: fintech di-remove di v9.4 (R2.2). Sistem akan fallback ke general + standard 8 jobs. Fintech rules tidak ada di semgrep_rules/ (di-remove). Ini batasan scope.

**Jawaban Singkat (30 detik):**
Di v9.4: fallback ke general (fintech di-remove). Pipeline standard 8 jobs tanpa fintech-specific.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q113

**Kategori:** Penguji Iseng

**Pertanyaan:**
Apakah Anda sudah benchmark dengan tools seperti Snyk, SonarQube, atau CodeQL?

**Jawaban:**
Belum. Ini adalah saran di Bab V untuk penelitian lanjutan. Benchmark akan membandingkan: detection rate, false positive rate, waktu eksekusi, cost per repo. Butuh setup tools eksternal (server SonarQube, CodeQL CLI) yang tidak trivial. Prioritas saat ini adalah validasi sistem, benchmark setelah sistem stabil.

**Jawaban Singkat (30 detik):**
Belum. Saran Bab V. Butuh setup tools eksternal. Prioritas: validasi sistem dulu.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** High

---

## Q114

**Kategori:** Penguji Iseng

**Pertanyaan:**
Apakah sistem Anda bisa di-scale ke 1000 repositori? Bottleneck-nya di mana?

**Jawaban:**
Bottleneck: (1) LLM rate limits (OpenRouter free tier ~200 req/day). (2) GitHub API rate limits (5,000 req/hour per token). (3) AI service single-instance (tidak horizontal scaling). (4) PostgreSQL query untuk 1000 repositori perlu indexing optimization.

Scale strategy: AI service pooling (multiple instances), LLM provider dengan higher rate limits (OpenAI/Anthropic enterprise), GitHub App authentication (higher limits), PostgreSQL read replicas untuk analytics queries.

**Jawaban Singkat (30 detik):**
LLM + GitHub rate limits + single AI service. Perlu pooling + higher-tier provider + read replicas.

**Tingkat Kesulitan:** ⭐⭐⭐

**Prioritas:** Medium

---

# 12. CRITICAL QUESTIONS

---

## Q115

**Kategori:** Critical Questions

**Pertanyaan:**
Apa kelemahan terbesar penelitian ini?

**Jawaban:**
Dua kelemahan fundamental:

1. **0% detection rate untuk CVE target.** Dari 14 CVE/injeksi target, 0 true positive terdeteksi. Ini adalah kelemahan SAST-only approach yang didokumentasikan di literatur (Baca et al. 2008, Pashchenko et al. 2018). Tapi tetap menjadi pertanyaan valid: jika 0% CVE terdeteksi, apa gunanya?

2. **Dataset terlalu kecil (4 repo, 1 run).** Tidak bisa menghitung statistical significance (p-value, confidence interval, mean ± std dev). Ini membatasi generalisabilitas klaim ke populasi repositori GitHub.

3. **Lingkaran setan validasi:** Sistem dievaluasi pada repositori yang dipilih peneliti, dengan ground truth yang ditentukan peneliti. Tidak ada blind evaluation atau external validation.

**Jawaban Singkat (30 detik):**
0% CVE detection + 4 repo × 1 run + researcher-selected evaluation. Kelemahan fundamental diakui di Bab V.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q116

**Kategori:** Critical Questions

**Pertanyaan:**
Kalau saya bilang novelty Anda tidak ada — ini cuma automation script yang pakai LLM?

**Jawaban:**
Saya menghargai kritik ini. Argumen saya:

1. **Konsep security coverage** adalah kontribusi konseptual — abstraksi formal yang menghubungkan konteks repositori dengan kebutuhan pipeline. Tidak ada di literatur DevSecOps. Sebelum ini, hubungan "library → security requirement → pipeline job" hanya ada di kepala engineer — tidak ada formalisasi.

2. **Multi-step reasoning yang dikurasi** — 4 tahap, 18 node, 11 LLM calls dengan fallback deterministik. Ini bukan "satu prompt besar." Setiap tahap dirancang dengan prompt engineering, structured output validation, dan deterministic safety nets. Automation script tidak melakukan ini.

3. **Bukti empiris** — 27 finding unik dari custom K2.4 job yang tidak akan ada tanpa sistem. Ini bukti konkret, bukan klaim.

4. **Kode kompleks** — 5,808 baris workflow generator, 914 baris action registry, 97-field state machine. Ini lebih dari "script."

**Jawaban Singkat (30 detik):**
Security coverage = kontribusi konseptual. Multi-step reasoning + deterministic safety nets. 27 finding = bukti empiris.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q117

**Kategori:** Critical Questions

**Pertanyaan:**
Bagaimana membuktikan kontribusi Anda? 0% detection rate itu kan gagal?

**Jawaban:**
Kontribusi dibuktikan dengan dua cara:

1. **Kontribusi K2.4 terukur:** 27 finding unik di ThingsBoard dari custom job `container-compose-hardening` — A/B test natural: tanpa sistem → 0 finding, dengan sistem → 27 finding. Ini peningkatan ∞% (dari 0 ke 27).

2. **0% detection rate bukan failure, tapi evidence:** Justru menjadi argumen kuat untuk integrasi DAST. Jika saya dapat 100% detection rate, kontribusi saya "hanya" mengotomasi yang sudah bisa dilakukan manual. Dengan 0%, saya membuktikan bahwa SAST tidak cukup → memperkuat argumen untuk adaptive multi-layer security (SAST + SCA + secret + container + DAST).

Paradigma: "Sistem berhasil membuktikan bahwa masalahnya lebih besar dari yang dikira" adalah kontribusi valid dalam research.

**Jawaban Singkat (30 detik):**
27 finding dari 0 = kontribusi terukur. 0% = bukti SAST tidak cukup → justru memperkuat argumen untuk DAST.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q118

**Kategori:** Critical Questions

**Pertanyaan:**
Kenapa bukan sekadar automation script? Apa value proposition-nya?

**Jawaban:**
Automation script = static rules (if Python → pip-audit, if Docker → trivy). Value proposition sistem saya: (1) **Context-aware reasoning** — tidak sekadar "if-else" tapi multi-layer LLM reasoning yang mempertimbangkan library × entity × route × domain. (2) **Generative capabilities** — AI generates custom Semgrep rules (K2.3) dan custom job designs (K2.4) yang spesifik untuk repositori. (3) **Continuous improvement** — system bisa di-update dengan prompt refinement tanpa code change. (4) **Comprehensive output** — bukan hanya YAML, tapi juga PR + custom rules + findings analysis + PDF report + risk scoring.

**Jawaban Singkat (30 detik):**
Bukan if-else. Multi-layer reasoning, generative custom rules + jobs, comprehensive output (YAML + PR + report).

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q119

**Kategori:** Critical Questions

**Pertanyaan:**
Bagaimana memastikan LLM tidak salah? Fallback deterministik itu cukup?

**Jawaban:**
Fallback deterministik tidak menjamin "benar" — hanya menjamin "tidak kosong." Contoh: coverage_inference fallback menggunakan heuristic scoring. Ini conservative — under-detect (30%) — tapi setidaknya sistem tetap berfungsi.

Strategi multi-layer: (1) Structured JSON output + schema validation mencegah format error. (2) Deterministic fallback mencegah empty output. (3) Validation nodes (workflow_validator) mencegah invalid YAML. (4) Domain constraints di prompt mencegah nonsensical output. (5) Human review (PR-based) sebagai ultimate safety net.

Tapi jujur: LLM bisa salah (domain overconfidence). Perlu perbaikan: (a) temperature 0.0, (b) ensemble LLM (multiple providers vote), (c) confidence threshold untuk reject LLM output di bawah threshold tertentu.

**Jawaban Singkat (30 detik):**
Fallback = prevent empty, not prevent wrong. Multi-layer: JSON validation + deterministic fallback + human review.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q120

**Kategori:** Critical Questions

**Pertanyaan:**
Bagaimana validasi pipeline? Apakah "valid" = "secure"?

**Jawaban:**
"Valid" ≠ "Secure." Valid = YAML parseable, SHA benar, permissions minimal, concurrency di-set. Secure = pipeline mendeteksi kerentanan dan tidak menambah risk (supply chain). Validasi saat ini hanya level 1 (technical correctness). Level 2 (security effectiveness) diukur dengan findings + CVSS + detection rate. Level 3 (supply chain security) diukur dengan SHA pinning + action registry.

Gap: tidak ada validasi bahwa ruleset Semgrep yang dipilih benar-benar relevan untuk repo. Tidak ada validasi bahwa pipeline tidak membocorkan secrets. Ini keterbatasan.

**Jawaban Singkat (30 detik):**
Valid = technically correct. Secure = detects vulns + doesn't add risk. Different levels — sistem hanya validasi level 1.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q121

**Kategori:** Critical Questions

**Pertanyaan:**
Mengapa hasil Anda bukan overfitting? Cuma 4 repo — bukankah itu terlalu sedikit?

**Jawaban:**
Risiko overfitting diakui. Tapi 4 repo dipilih via purposive sampling untuk VARIASI, bukan KESAMAAN. Jika sistem overfit, seharusnya performa bagus di semua repo yang dipilih (karena sistem "dikenal"). Kenyataannya: performa bervariasi (3 repo sukses, 1 gagal). Overfitting akan menghasilkan performa seragam tinggi.

Tapi benar: 4 repo terlalu sedikit untuk klaim generalisasi. Ini diakui di Bab V — perlu 12-16 repo dengan multiple runs untuk validasi statistik yang rigorous.

**Jawaban Singkat (30 detik):**
Purposive sampling = variasi, bukan kesamaan. Performa bervariasi (3/4 sukses) = bukan overfitting. Tapi 4 repo kurang.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q122

**Kategori:** Critical Questions

**Pertanyaan:**
Apakah 15 security coverages cukup? Kenapa tidak 50?

**Jawaban:**
15 adalah titik optimal antara coverage breadth dan feasibility:

- **Terlalu sedikit (5):** Tidak cukup granular — authentication dan API digabung, payment dan fintech digabung. One-size-fits-all.
- **Terlalu banyak (50):** Setiap coverage butuh ruleset, signal detection, augmentation mapping. Cost development tinggi. Banyak coverage tanpa sinyal deteksi yang jelas (noise).
- **15:** Cukup granular untuk membedakan e-commerce dan IoT, tapi tidak terlalu banyak untuk membuat sistem unmanageable. Validasi: 15 coverage × 4 repo = 60 kemungkinan, hanya 12 applicable (30%) — menunjukkan bahwa 15 memberikan cakupan yang cukup untuk membedakan repositori.

Untuk production, number bisa di-tune: beberapa coverage bisa di-split (api_security → rest_api_security + graphql_security), beberapa bisa di-merge.

**Jawaban Singkat (30 detik):**
15 = sweet spot granularity vs feasibility. Under-detect 30% menunjukkan ada signal, tapi tidak terlalu banyak noise.

**Tingkat Kesulitan:** ⭐⭐⭐⭐

**Prioritas:** High

---

## Q123

**Kategori:** Critical Questions

**Pertanyaan:**
Apakah Anda confident dengan LLM output untuk security-critical decisions?

**Jawaban:**
Tidak sepenuhnya. Itulah kenapa:
1. **LLM hanya untuk reasoning, bukan action.** Decision critical (YAML generation, deployment) = deterministic.
2. **Human review:** Output = PR yang harus di-review dan di-merge oleh manusia. LLM = suggestion, bukan decision.
3. **Conservative defaults:** Fallback selalu ke under-detect (false negative) daripada over-detect (false positive → noise mengganggu).
4. **Deterministic validation:** Workflow YAML di-validate dengan SHA check + permissions check sebelum deploy.

Tapi jujur: untuk fully autonomous security decisions, confidence harus >95%. Saat ini ~70% (reasonable). Perlu ensemble LLM + confidence threshold + human-in-the-loop untuk production.

**Jawaban Singkat (30 detik):**
Tidak 100%. LLM = reasoning (suggestion), deterministic = generation (action). Human review sebagai safety net.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q124

**Kategori:** Critical Questions

**Pertanyaan:**
Bagaimana Anda tahu "adaptif" itu lebih baik dari "statis"? Mana buktinya?

**Jawaban:**
Bukti langsung: 27 finding di ThingsBoard dari custom job K2.4. Jika pipeline statis (standard 8 jobs), finding ini tidak akan terdeteksi. Jadi "adaptif" menghasilkan **penemuan yang tidak ada di pipeline statis.**

Bukti tidak langsung: Coverage applicable bervariasi (4 vs 3 vs 5). Pipeline statis akan memberikan coverage yang sama untuk semua repo — yang mana akan over-scan untuk repo sederhana (waste) atau under-scan untuk repo kompleks (miss). Adaptif = proporsional.

Tapi diakui: tidak ada A/B experiment formal. Idealnya: bandingkan adaptive pipeline vs static pipeline di repositori yang sama, ukur findings + false positive rate + execution time. Ini future work.

**Jawaban Singkat (30 detik):**
27 finding = bukti adaptif > statis. Pipeline statis tidak akan menghasilkan finding itu. Tapi belum ada A/B experiment formal.

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---

## Q125

**Kategori:** Critical Questions

**Pertanyaan:**
Mengapa Anda yakin penelitian ini layak lulus?

**Jawaban:**
Karena memenuhi 3 syarat skripsi DTETI UGM:

1. **Kontribusi:** Konsep "security coverage inference" sebagai abstraksi formal adalah kontribusi konseptual yang novel. Bukti empiris: sistem berfungsi di 3 dari 4 repositori, menghasilkan 272 findings, 27 dari kontribusi K2.4.

2. **Metodologi rigorous:** DSR framework, purposive sampling based on teori (McConnell classification + Meneely clustering), ground truth CVE yang terdokumentasi, multi-layer evaluasi (F1 + coverage ratio + CVSS + detection rate).

3. **Kejujuran akademik:** 0% detection rate tidak disembunyikan — justru dianalisis dan dijustifikasi ke literatur. Semua kelemahan didokumentasikan di Bab V. Keterbatasan diakui transparan. Saran perbaikan konkret (DAST, temperature 0.0, ekspansi dataset, user study).

Penelitian yang jujur tentang keterbatasannya lebih bernilai daripada penelitian yang overclaim.

**Jawaban Singkat (30 detik):**
Kontribusi novel (security coverage), metodologi rigorous (DSR + ground truth), kejujuran akademik (0% diakui + justifikasi ke literatur).

**Tingkat Kesulitan:** ⭐⭐⭐⭐⭐

**Prioritas:** High

---



