# Lampiran: Domain-Aware Pipeline Configuration — Bab 4 §4.4

> **Sumber:** Diskusi justifikasi tools + domain context-aware
> **Status:** Sudah diterapkan ke `chapter-4.tex`
> **Tanggal:** 21 Juni 2026

---

## A. Apa yang Ditambahkan

Sub-bab §4.4 (Hasil Pemilihan Kontrol Keamanan) sebelumnya hanya membahas pemilihan kontrol berdasarkan **arsitektur** (monolitik vs microservices). Sekarang diperluas dengan dimensi **domain webapp**, mencakup:

1. **Tabel konfigurasi domain-aware pipeline** — 7 domain × prioritas SAST ruleset × ruleset skip × pipeline jobs
2. **Naratif perbandingan** e-commerce (7 job, secret-scan CRITICAL, PCI-DSS) vs blog (5 job, tanpa secret-scan CRITICAL, tanpa container-scan)
3. **Penjelasan tiga mekanisme domain-aware berantai** yang menghasilkan perbedaan pipeline

---

## B. Lima Layer Domain-Aware dalam Sistem

| Layer | Node/Modul | Bab 3 | Efek |
|---|---|---|---|
| 1. Deteksi | `domain_detection` | §3.3.6 | Klasifikasi 7 domain + `domain_threats[]` |
| 2. Vuln Scan | `vulnerability_scan` prompt | §3.3.2 | PRIORITY/CAN SKIP checks per domain |
| 3. Inferensi | `security_requirement_inference` prompt | §3.5.2 | `scan_directives` → `sast_ruleset` + `sast_skip_rules` |
| 4. Generasi | `workflow_generation` + `_build_workflow_yaml()` | §3.6.1 | Job pipeline berbeda per domain |
| 5. Evaluasi | `domain_priority` module | §3.6.3 | Severity elevation via keyword matching |

---

## C. Tabel Utama: Job Pipeline per Domain

| Domain | Kategori McConnell | Prioritas SAST | Ruleset Skip | Pipeline Jobs | Compliance |
|---|---|---|---|---|---|
| e-commerce | Internet Systems (600–10K) | SQLi, CSRF, secret (Stripe/PayPal), mass-assignment | SSRF, service-mesh (monolith) | lint → test → **secret-scan (CRITICAL)** → sast → dep-check → container-scan → **pci-dss** | PCI DSS v4.0 |
| fintech | Internet Systems (600–10K) | IDOR, JWT, race-condition, ledger-integrity | XSS, path-traversal | lint → test → **secret-scan (CRITICAL)** → sast → dep-check → container-scan → **ledger-check** | PCI DSS, SOC2 |
| healthcare | Business Systems (800–18K) | encryption, auth-bypass, RBAC, HL7/FHIR-injection | SSRF, command-injection | lint → test → secret-scan → sast → dep-check → container-scan → **hipaa** | HIPAA |
| education | Business Systems (800–18K) | IDOR (grade tampering), auth-bypass, file-upload | SSRF, rate-limiting | lint → test → sast → secret-scan → dep-check → container-scan | OWASP Top 10 |
| blog | Internet/Business (500–7,5K) | XSS, path-traversal, file-upload, sanitization | IDOR, SSRF, JWT, rate-limiting | lint → test → sast → **csp-headers** → dep-check | OWASP Top 10 |
| IoT | Internet/Business (500–7,5K) | device-credential, MQTT-auth, TLS, command-injection | — | lint → test → secret-scan → sast → dep-check → container-scan → **mqtt-security** | OWASP IoT Top 10 |
| general | Business Systems (800–18K) | 12 standard checks (tanpa prioritas) | — | lint → test → sast → secret-scan → dep-check → container-scan (jika ada Docker) | OWASP Top 10 |

> **Catatan:** Job `container-scan` hanya di-generate jika repositori memiliki Dockerfile. Job tebal (bold) adalah job spesifik domain.

---

## D. Tiga Mekanisme Domain-Aware Berantai

```
domain_detection          security_requirement_inference       workflow_generation
     │                              │                                │
     ├─ domain_threats[] ──────────►│                                │
     │                              ├─ scan_directives ─────────────►│
     │                              │  ├─ sast_ruleset               │
     │                              │  └─ sast_skip_rules            │
     │                              │                                ├─ Job SAST (ruleset berbeda)
     │                              │                                ├─ Job spesifik domain
     │                              │                                └─ Jumlah job berbeda
     │                              │
     └─ (ke Tahap 4) ───────────────────────────────────────────────► domain_priority
                                                                        ├─ Severity elevation
                                                                        └─ Risk Score berbeda per domain
```

---

## E. Severity Elevation per Domain (cross-ref §3.6.3)

| Domain | Keyword → Critical | Keyword → High |
|---|---|---|
| e-commerce | `stripe`, `paypal`, `payment`, `credit_card`, `billing`, `checkout`, `transaction` | `order`, `cart`, `csrf`, `sql_injection` |
| healthcare | `patient`, `PHI`, `medical_record`, `FHIR`, `HIPAA`, `prescription` | `appointment`, `weak_auth`, `audit_log` |
| fintech | `transaction_tamper`, `ledger`, `wallet`, `KYC` | `account`, `balance`, `settlement` |
| education | `grade_tamper`, `student_data_exposure` | `student`, `course`, `enrollment`, `quiz` |
| blog | `file_upload_bypass`, `rce_upload` | `xss`, `csrf`, `sanitization` |
| IoT | `device_auth_bypass`, `firmware_tamper`, `default_credential` | `mqtt`, `amqp`, `tls_missing` |
| general | (tidak ada — severity asli dari scanner) | (tidak ada) |

---

## F. Perbandingan Konkret: E-commerce vs Blog

### E-commerce (Node.js + React, monolith)
- **7 job**: lint, test, secret-scan (CRITICAL), sast, dep-check, container-scan, pci-dss
- **Kenapa secret-scan CRITICAL**: Satu Stripe key bocor = transaksi fiktif = kerugian finansial langsung
- **Kenapa SSRF di-skip**: E-commerce monolith jarang membuat outbound HTTP request ke URL user-supplied
- **Kenapa PCI-DSS**: Wajib untuk domain yang menangani data kartu kredit
- **Risk Score**: 38,4 (HIGH risk) — 12 elevasi severity

### Blog (Go, monolith)
- **5 job**: lint, test, sast, csp-headers, dep-check
- **Kenapa tanpa secret-scan CRITICAL**: Tidak ada payment gateway
- **Kenapa tanpa container-scan**: Tidak menggunakan Docker
- **Kenapa IDOR/SSRF/JWT di-skip**: Tidak punya multi-tenant access control
- **Kenapa csp-headers**: Job spesifik domain untuk validasi Content-Security-Policy
- **Risk Score**: 72,1 (MEDIUM risk) — 3 elevasi severity

---

## G. Kenapa Ini Penting (Justifikasi)

Tanpa domain-aware pipeline:
- Blog menerima **false positive noise** dari IDOR/SSRF scan yang tidak relevan
- E-commerce **melewatkan** SQL injection di checkout karena tidak diprioritaskan
- Fintech **tenggelam** dalam false positive XSS dari dashboard internal

Dengan domain-aware pipeline:
- Setiap repositori mendapatkan **scan scope yang proporsional terhadap threat profile domainnya**
- Perbedaan Risk Score (e-commerce 38,4 vs blog 72,1) adalah **cerminan objektif** luas attack surface dan dampak kebocoran — bukan kelemahan sistem

---

## H. Cross-Reference Lengkap

| Elemen Bab 4 | Merujuk ke Bab 3 |
|---|---|
| Tabel McConnell domain classification | §3.1.2 (dataset), Tabel 3.1 |
| Domain detection mechanism | §3.3.6 (`domain_detection` node) |
| Vulnerability scan domain-aware branching | §3.3.2 (prompt `VULNERABILITY_SCAN_PROMPT`) |
| Security requirement inference | §3.5.2 (prompt `SECURITY_REQUIREMENT_INFERENCE_PROMPT`) |
| Domain-aware severity elevation | §3.6.3 (modul `domain_priority`) |
| Attack surface lookup table | §3.5.1, Tabel 3.5 |
| Risk Score per domain | §4.6.1 (Tabel `tab:risk-per-domain`) |
| McConnell classification | §3.1.2 (Tabel 3.1) |

---

## I. Label Referensi

| Label | Nama | Lokasi |
|---|---|---|
| `tab:security-selection` | Hasil pemilihan kontrol per arsitektur | §4.4 (existing) |
| `tab:domain-pipeline-jobs` | Konfigurasi domain-aware pipeline per domain | §4.4 (BARU) |
| `tab:risk-per-domain` | Risk Score per domain | §4.6.1 (existing) |
| `tab:mcconnell-domain` | Klasifikasi domain McConnell | §3.1.2 (existing) |

---

## J. Yang Tidak Dimasukkan (Keputusan Sadar)

1. **Severity elevation table tidak diduplikasi di Bab 4** — cukup cross-ref ke §3.6.3 agar tidak redundan
2. **Tabel threat-per-domain tidak ditambahkan** — `domain_threats[]` adalah output LLM yang berbeda tiap repositori, tidak bisa diringkas dalam tabel statis
3. **McConnell table tidak diduplikasi** — sudah ada di Bab 3 §3.1.2, Bab 4 cukup menyebutkan kategorinya dalam teks

---

## K. Checklist Verifikasi

- [x] Tabel `tab:domain-pipeline-jobs` sudah di `chapter-4.tex`
- [x] Paragraf naratif e-commerce vs blog sudah ditulis
- [x] Cross-reference ke Bab 3 (§3.3.6, §3.5.2, §3.6.3) sudah ada
- [x] Cross-reference ke §4.6.1 (Risk Score per domain) sudah ada
- [x] Paragraf penutup menjawab RQ1 dengan menyebut domain
- [ ] Cek apakah `mcconnell2006software` ada di `references.bib`
- [ ] Cek apakah `lombardi2023devops` ada di `references.bib`
- [ ] Kompilasi LaTeX untuk memastikan tidak ada error
