    # Rencana Pengujian dan Pengambilan Dataset

    A. Kriteria Repository Uji
    - Inklusi: clone via GitHub API publik, ada package.json/Dockerfile/docker-compose.yml, bahasa JS/TS, representasi 1 dari 3 domain (e-commerce, blog, IoT), aktif di-maintain ≤ 2 tahun.
    - Eksklusi: proprietary, monorepo tanpa diferensiasi subdirektori, tanpa dependensi teranalisis, tidak aktif > 2 tahun.
    - Dataset: 15–18 repo publik, distribusi 5–6 e-commerce, 5–6 blog, 5–6 IoT.
    - Klasifikasi domain mengikuti McConnell (2006): e-commerce (Internet Systems), blog & IoT (Internet-Business hybrid).
    - Arsitektur (monolitik/modular monolith) bukan variabel eksperimen utama, hanya konteks tambahan untuk generalisasi.

    B. Identifikasi Ground-Truth untuk Studi Kasus
    - Domain & arsitektur: cek struktur direktori, docker-compose.yml, folder per-service, package.json (pustaka Stripe/Midtrans/paypal/marked/mqtt/dll), README repo.
    - Security coverage: verifikasi dependensi terhadap 10 coverages (cth: Stripe → payment_security, passport → authentication_security, Dockerfile → container_security, mqtt → iot_security).
    - Label absolut independen dari keluaran sistem, sehingga akurasi deteksi terukur tanpa bias circular reasoning.

    C. Variabel Penelitian
    - Independen: teknologi, arsitektur, deployment target, domain webapp.
    - Dependen: security coverages applicable, jumlah job pipeline, distribusi severity, pemetaan finding ke coverage, skor risiko OWASP 3-dim.
    - Pengganggu: versi scanner (Semgrep/Trivy/Gitleaks), variasi acak LLM, rate limit GitHub API.
    - Arsitektur tidak dikontrol secara statistik (batasan B7).

    D. Sumber Data
    - Tahap 1 (6 node): repository_connection, repository_scan, technology_detection, architecture_detection, deployment_detection, domain_detection → metadata repo & label domain.
    - Tahap 2 (4 node): coverage_inference, pattern_inference, pipeline_augmentation, job_reasoning → coverages, Semgrep rules generatif, augmentations, custom job designs.
    - Tahap 3 (5 node): workflow_generation, workflow_validation, github_branch_creation, pull_request_creation, workflow_execution → YAML final, status validasi, metadata deployment.
    - Tahap 4 (3 node): security_analysis, recommendation_generation, response_formatter → findings + tag coverage, rekomendasi, respons terstruktur.
    - Format: SARIF (Semgrep), JSON (Trivy, Gitleaks), state JSON di PostgreSQL.

    E. Prosedur Pengumpulan
    1. Trigger pipeline via PR pada branch terpisah.
    2. Tunggu workflow run selesai, ambil data dari GitHub Code Scanning API (`/repos/{owner}/{repo}/code-scanning/alerts`).
    3. Ekstrak findings dari workflow logs pakai regex pola SARIF/JSON.
    4. Unduh workflow artifacts untuk raw scanner output.
    5. Baca state JSON di PostgreSQL untuk verifikasi konsistensi.
    6. Rekonsiliasi & deduplikasi (hash = file + line + rule_id).

    F. Metrik Evaluasi
    - Detection coverage: applicable∩ground_truth / applicable_union, target ≥ 0,80 per domain.
    - Severity accuracy: finding sesuai ekspektasi / total terverifikasi, target ≥ 0,75.
    - Pipeline completeness: 8 standard job (lint, test, build, sast, dep-scan, secret-scan, container-build, container-scan) + 1–3 domain job (payment-check, mqtt-security), ≥ 1 Semgrep rule, custom rule relevan.
    - Pipeline validity: 100% lolos actionlint, ≥ 95% SHA pinning, ≥ 90% permissions minimal.
    - Agregasi: mean + std dev per domain via pandas.

    G. Format Penyimpanan Dataset
    - JSON terstruktur 3 tingkat: metadata repo → output Tahap 1–3 → findings Tahap 4 + ringkasan metrik.
    - Fields: URL, bahasa, arsitektur, domain, timestamp; detected_*, security_coverages, ai_generated_rules, pipeline_augmentations, job_designs, generated_workflow, validation_findings; findings (security_coverage, severity, scanner, file, line), detection_coverage, false_positive_rate, severity_accuracy, pipeline_completeness_score, risk_score.
    - Naming: `{domain}_{repo_id}_{timestamp}.json` (ISO 8601).

    H. Tahapan Analisis Data
    1. Cleaning: hapus duplikat (hash file+line+rule_id), normalisasi severity (critical/high/medium/low), hapus noise.
    2. Hitung metrik per domain: groupby domain → apply detection_coverage, FPR, severity_accuracy, agregasi mean+std.
    3. Coverage specificity: 3 coverage spesifik (payment, cms, iot) harus eksklusif di domainnya, target 0 false positive.
    4. Verifikasi pipeline: parse YAML, hitung job/SHA pinning, cek standard + domain job.
    5. Kompilasi hasil: tabel coverage-per-domain, severity-per-domain, finding-to-coverage; visualisasi bar chart perbandingan domain + heatmap korelasi domain confidence vs coverage consistency.
