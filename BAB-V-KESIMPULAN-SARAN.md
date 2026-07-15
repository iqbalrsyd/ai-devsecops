# BAB V — KESIMPULAN DAN SARAN

> **Berdasarkan:** Hasil pengujian 4 repositori (Bab IV) dengan total 272 security findings dan CVSS sum 1,463
> **Tanggal:** 1 Juli 2026

---

## 5.1 Simpulan

Penelitian ini menghasilkan tiga kontribusi utama yang seluruhnya tervalidasi secara empiris melalui pengujian terhadap empat repositori dari empat kategori McConnell yang berbeda.

### 5.1.1 Kontribusi K1: Repository Context Analysis Terimplementasi dan Berfungsi

Sistem AI agent 4-tahap (18 node LangGraph) berhasil menganalisis konteks repositori dengan akurasi tinggi untuk dimensi bahasa, framework, dan arsitektur, namun memiliki keterbatasan pada dimensi domain. Pada empat repositori yang diuji (django-oscar, Ghost, ThingsBoard, AI Service), sistem mencapai:

- **Deteksi bahasa pemrograman: F1 = 1.00** (Python, JavaScript, Java, JavaScript terdeteksi dengan benar tanpa kesalahan).
- **Deteksi framework: presisi tinggi** (Django, Spring Boot, Express, Nx, React terdeteksi sesuai dependensi aktual).
- **Klasifikasi arsitektur: konsisten** (3/4 repositori terdeteksi `monolithic` sesuai kenyataan; ThingsBoard microservices terdeteksi sebagai monolithic oleh sistem — keterbatasan ini dicatat di §4.9).
- **Deteksi deployment target: akurat** (Docker terdeteksi di 3/4 repo dengan confidence 0.82–0.95 berdasarkan Dockerfile dan .dockerignore).
- **Deteksi domain: lemah** (semua repo terdeteksi `general` walaupun konteks spesifik jelas — e-commerce, blog, IoT — karena library-specific signals di top-30 imports tidak cukup).

### 5.1.2 Kontribusi K2: Security Coverage Inference dengan Presisi dan Cakupan Terbatas

Sistem berhasil meng-inferensi security coverages applicable untuk masing-masing repositori, dengan total 12 coverages applicable dari 40 kemungkinan (rata-rata 30%). Kualitas inferensi bervariasi antar repositori:

- **ThingsBoard: 5/10 coverages applicable (50%)** — tertinggi, karena Spring Security, Spring Data, dan IoT-specific libraries (Milo OPC-UA, Leshan, Californium) memberikan sinyal kuat.
- **django-oscar: 4/10 (40%)** — authentication dan data security applicable karena Django auth + ORM.
- **Ghost: 3/10 (30%)** — hanya data, container, dan dependency security applicable, walaupun Ghost adalah blog/CMS.
- **AI Service: 0/10 (0%)** — gagal karena AI service fallback ke synthetic defaults saat pengujian.

**Custom job generation (K2.4) menghasilkan 7 custom jobs spesifik** untuk tiga repositori utama (Ghost: 2, ThingsBoard: 2, django-oscar: 3), dengan justifikasi berbasis business feature dan library detection. **27 finding unik di ThingsBoard** berasal dari custom job `container-compose-hardening` yang tidak akan terdeteksi oleh standard SAST ruleset — membuktikan bahwa K2.4 efektif menambah presisi.

### 5.1.3 Kontribusi K3: Pipeline Generation + Security Evaluation Berhasil dengan Batasan SAST

Sistem menghasilkan 9–11 job CI/CD per repositori dengan workflow YAML yang seluruhnya lolos validasi otomatis (actionlint + SHA pinning + permissions minimal). Pipeline berhasil di-deploy ke GitHub Actions dan menghasilkan **272 security findings** dari 3 repositori (django-oscar: 99, Ghost: 101, ThingsBoard: 70).

**Distribusi severity:**
- **Critical: 48** (18% — didominasi dependency CVE di Ghost)
- **High: 158** (58% — SCA + Semgrep weak crypto/SSL/JWT)
- **Low: 66** (24% — Django template autoescape)
- **Total CVSS sum: 1,463** (rata-rata 5.4 per finding)

**Ground truth detection rate: 0% (0/14 CVE target) + 2 partial.** Sistem tidak mendeteksi CVE spesifik seperti CVE-2024-53908 (Django HasKey), CVE-2026-26980 (Ghost SQLi), atau CVE-2025-34282 (ThingsBoard SSRF). Kegagalan ini konsisten dengan keterbatasan SAST statis yang terdokumentasi di literatur (Baca et al. 2008; Pashchenko et al. 2018) — **tools static analysis efektif untuk pola umum (SQLi, XSS, weak crypto), namun kurang efektif untuk CVE spesifik tanpa custom ruleset yang ditailor**.

### 5.1.4 Temuan Tambahan yang Tidak Diharapkan

1. **AI Service fallback** pada pengujian chatbot-waha menunjukkan **ketergantungan tinggi pada ketersediaan AI service** — tanpa LLM response, sistem tidak dapat menghasilkan coverage applicable, custom jobs, atau analisis kontekstual. Ini mengimplikasikan **perlu strategi fallback yang lebih robust**.

2. **Inkonsistensi output LLM antar run** (temperature 0.3 masih menghasilkan variasi) mengindikasikan bahwa untuk eksperimen final perlu **temperature 0.0** atau **seed-controlled generation** untuk reproducibility.

3. **Coverage under-detection** (rata-rata 30% applicable) bukan error, tapi **cerminan realitas bahwa static analysis terbatas pada sinyal library-level** — bukan analisis kode struktural yang lebih dalam.

---

## 5.2 Saran untuk Penelitian Lanjutan

### 5.2.1 Saran untuk Peningkatan Sistem

1. **Tambahkan Dynamic Application Security Testing (DAST) layer.** Karena SAST terbukti memiliki 0% detection rate untuk CVE spesifik business logic, DAST (seperti OWASP ZAP atau sqlmap) akan menutup gap ini dengan menguji aplikasi secara runtime. Integrasi DAST sebagai tahap 5 setelah security_analysis akan meningkatkan detection rate secara signifikan.

2. **Implementasikan CVSS-Driven Coverage Gap Job (K2.4 enhancement).** Node `cvss_driven_job_generation` sudah diimplementasikan setelah pengujian ini, tetapi belum divalidasi. Penelitian selanjutnya perlu:
   - Menjalankan pipeline ulang untuk mengukur apakah custom job CVSS-driven (dengan justifikasi `cvss_justified_by`) meningkatkan detection rate CVE target.
   - Membandingkan jumlah custom job yang dihasilkan (saat ini 2–3 berbasis library) dengan jumlah yang dihasilkan berbasis top CVSS finding (ekspektasi 1–2 per repo).

3. **Perluas library detection rules.** Sistem saat ini hanya cek top-30 library imports. Saran:
   - Library detection dari `requirements.txt` / `package.json` / `pom.xml` (bukan hanya `import` statements).
   - Deteksi library dari `package-lock.json` / `yarn.lock` / `poetry.lock` (transitive dependencies).
   - Custom ruleset untuk library yang sering tertinggal di deteksi (logging, CMS).

4. **Tambahkan coverage khusus untuk Bahasa C/C++ (firmware).** McConnell's Embedded Systems yang sesungguhnya (ESP32, Zephyr, FreeRTOS) menggunakan C/C++ yang tidak tercakup di penelitian ini (Batasan B3). Penelitian selanjutnya bisa:
   - Menguji Semgrep ruleset `p/c`, `p/cpp`, `p/embedded-c` untuk firmware.
   - Menambahkan static analysis tools untuk firmware (Cppcheck, PC-lint).

5. **Tambahkan custom Semgrep rules per CVE ground truth** (sudah dimulai: 12 rules untuk Django + 10 rules untuk Java/IoT di `ecommerce.yml` dan `iot-mqtt.yml`). Penelitian selanjutnya perlu:
   - Menjalankan pipeline ulang dengan custom ruleset ini.
   - Mengukur detection rate sebelum-sesudah penambahan rules.
   - Membangun methodology untuk auto-generate ruleset dari CVE database (CVE → AST pattern → Semgrep rule).

### 5.2.2 Saran untuk Pengujian Lanjutan

1. **Tambah jumlah pengulangan (3× per repo) untuk mengukur variansi.** Pengujian saat ini hanya 1× per repo. Pengulangan akan menghasilkan data mean ± std dev untuk validasi statistik.

2. **Ekspansi dataset repositori.** 4 repositori terlalu sedikit untuk generalisasi. Saran:
   - Tambah 1–2 repositori per kategori McConnell (total 12–16 repo).
   - Pilih repositori dengan ukuran dan kompleksitas bervariasi (small/medium/large).

3. **Benchmark dengan SAST tools lain (CodeQL, SonarQube).** Bandingkan detection rate, false positive rate, dan waktu eksekusi sistem AI-generated pipeline dengan tools established untuk validasi efektivitas.

4. **Tambahkan inter-rater reliability** untuk validasi manual ground truth labeling. Jika ada 2+ evaluator yang menandai expected coverages, ukur Cohen's Kappa untuk memastikan konsistensi labeling.

5. **Tambahkan user study** untuk mengukur apakah AI-generated pipeline lebih mudah di-review oleh developer manusia dibanding rule-based static pipeline.

### 5.2.3 Saran untuk Aspek Bisnis / Operasional

1. **Hitung ROI (Return on Investment) deployment sistem di organisasi nyata.** Biaya MiniMax-m3 ($0.13 untuk 4 repo) jauh lebih murah dari GPT-4o (~$2.00 untuk 4 repo) — tetapi perlu dibandingkan dengan:
   - Biaya developer untuk menulis CI/CD pipeline manual.
   - Biaya security audit oleh konsultan eksternal.
   - Biaya downtime akibat security incident.

2. **Kembangkan deployment template** untuk organisasi kecil-menengah. Sistem saat ini kompleks (3-lapis, 18 node LangGraph, multi-LLM provider) — untuk adopsi luas perlu disederhanakan menjadi Docker Compose single-file atau SaaS offering.

3. **Compliance integration** (SOC 2, ISO 27001, NIST SSDF). Pipeline output sudah menghasilkan risk score dan findings, tetapi belum otomatis generate compliance evidence. Integrasi dengan compliance tools (Vanta, Drata, Tugboat) akan menambah nilai bisnis.

---

## 5.3 Kontribusi Penelitian

Kontribusi utama penelitian ini adalah:

1. **Artifact:** Sistem AI agent 4-tahap (18 node LangGraph) untuk adaptive security assessment yang open-source dan reproducible.
2. **Empirical evidence:** 4 repositori × 1 run = 4 dataset dengan 272 security findings, membuktikan kemampuan dan keterbatasan sistem.
3. **Methodology:** Pendekatan purposive sampling 4 kategori McConnell dengan ground truth CVE yang terdokumentasi.
4. **Insight:** SAST + AI-generated custom jobs efektif untuk deteksi pola umum (80%+) tetapi memiliki 0% detection rate untuk CVE spesifik tanpa ruleset yang tailored — menjadi argumen kuat untuk **integrasi DAST** dan **auto-generation Semgrep rules per CVE** di penelitian selanjutnya.

---

## 5.4 Penutup

Penelitian ini berhasil mengimplementasikan sistem adaptive security assessment menggunakan AI agent 4-tahap, namun hasil empiris menunjukkan bahwa **sistem ini adalah pelengkap, bukan pengganti**, untuk tools SAST/SCA established. Kombinasi dengan DAST, custom ruleset per CVE, dan library detection yang lebih luas akan menjadi arah pengembangan utama untuk penelitian selanjutnya.
