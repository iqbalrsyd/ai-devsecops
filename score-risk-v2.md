# Domain-Aware Risk Scoring — Mekanisme & Perubahan Naskah

> **Sumber:** `ai-service/app/agents/domain_priority.py` + `ai-service/app/agents/nodes/risk_assessor.py`
> **Tanggal:** 20 Juni 2026

---

## A. Alur Lengkap: Domain Context → Risk Score

```
Tahap 1                  Tahap 2                   Tahap 3                Tahap 4
─────────                ─────────                 ─────────              ─────────
domain_detection  ──→   security_inference   ──→   pipeline exec   ──→   domain_priority  ──→  risk_assessor
│                       │                          │                     │                      │
│ detected_domain       │ control selection        │ scan findings       │ severity elevation   │ OWASP Risk Score
│ domain_threats[]      │ (LLM, domain-aware)      │ (SARIF, JSON)       │ (deterministic)      │ (0-100)
│                       │                          │                     │                      │
│ e-commerce            │ secret_scan CRITICAL     │ hardcoded_stripe    │ high → CRITICAL      │ 33.6 (CRITICAL)
│ blog                  │ secret_scan OPTIONAL     │ hardcoded_stripe    │ tetap high           │ 56.7 (HIGH)
│ general               │ secret_scan RECOMMENDED  │ hardcoded_stripe    │ tetap high           │ 56.7 (HIGH)
```

Dua jalur pengaruh domain ke risk score:

### Jalur 1: Control Selection (Tahap 2, LLM-based)
LLM membaca `domain_threats[]` dan memutuskan kontrol mana yang wajib/opsional:
- **e-commerce** → `secret_scan: recommended` (CRITICAL priority karena Stripe/PayPal)
- **blog** → `secret_scan: optional` (tidak prioritas, kalau resources terbatas bisa skip)
- **general** → `secret_scan: recommended` (default)

Efek: pipeline e-commerce **selalu** scan secret, pipeline blog **bisa** skip → jumlah temuan berbeda → risk score berbeda.

### Jalur 2: Severity Elevation (Tahap 4, deterministic)
Module `domain_priority.py` menaikkan severity temuan berdasarkan keyword matching:
- **e-commerce**: keyword `stripe`, `paypal`, `checkout` → severity +1 level
- **blog**: keyword `xss`, `csrf`, `sanitiz` → severity +1 level
- **general**: tidak ada elevation

Efek: severity yang dinaikkan → OWASP dimension modifier naik → risk score turun (lebih bahaya).

---

## B. Mekanisme Severity Elevation — `domain_priority.py`

### Rule per domain (tabel lengkap dari codebase)

| Domain | Critical Keywords | High Keywords | File Patterns |
|--------|------------------|---------------|---------------|
| **e-commerce** | stripe, paypal, payment, credit_card, billing, checkout, transaction, price_tamper | order, cart, discount, coupon, customer, auth_bypass, sql_injection, csrf, xss_payment | checkout, payment, billing, cart, order, invoice, stripe, paypal |
| **healthcare** | patient_data, PHI, medical_record, EHR, prescription, diagnosis, fhir, hl7, hipaa | patient, appointment, auth_bypass, weak_auth, audit_log, encryption | patient, appointment, prescription, fhir, ehr, medical, clinic |
| **fintech** | transaction_tamper, ledger, transfer, wallet, kyc_bypass, replay_attack, insider_threat | account, balance, settlement, brokerage, auth_bypass, weak_auth | account, transaction, ledger, wallet, transfer, kyc, settlement |
| **blog** | file_upload_bypass, rce_upload, path_traversal_upload | xss, cross_site_scripting, csrf, content_injection, sanitiz, markdown_inject | comment, post, article, tag, category, newsletter |
| **iot** | device_auth_bypass, firmware_tamper, default_credential | mqtt, amqp, coap, modbus, telemetry, tls_missing, plaintext_protocol | device, sensor, telemetry, actuator, gateway, firmware |
| **education** | grade_tamper, student_data_exposure | student, course, enrollment, quiz, submission, cheating_bypass | course, enrollment, quiz, student, grade, assignment, submission |
| **general** | (none) | (none) | (none) |

### Matching order (setiap finding)

1. Cek **critical keywords** — match di text finding → severity → `critical`
2. Cek **file patterns** — match di text finding + match di file path → severity → `critical`
3. Jika file pattern match di text doang (tidak di path) + severity `low/medium` → severity → `high`
4. Cek **high keywords** — match di text finding → severity → `high` (kalau belum lebih tinggi)
5. Tidak ada yang match → severity tetap

Rules only **elevate**, never downgrade (`_bump_severity`). Setiap finding ditambahi metadata `severity_boost` untuk traceability.

---

## C. Mekanisme Risk Score — `risk_assessor.py`

### Severity modifier ke OWASP dimension

| Severity | Modifier | Efek pada e, x, c, g, a |
|----------|----------|--------------------------|
| critical | **+1.0** | Setiap dimensi +1.0, dijepit ke [1, 5] |
| high | **+0.0** | Default — tidak ada perubahan |
| medium | **-0.5** | Setiap dimensi -0.5 |
| low | **-1.0** | Setiap dimensi -1.0 |

### Formula

```
Untuk setiap temuan i:
  e_i, x_i, c_i, g_i, a_i = base_dimensions(type_i) + severity_modifier(sev_i)
  L_i = (e_i + x_i) / 2                    # Likelihood (1-5)
  I_i = (c_i + g_i + a_i) / 3              # Impact (1-5)
  R_i = L_i × I_i                           # Risk (1-25)

RiskScore = max(0, 100 - (ΣR_i / (n × 25)) × 100)

Level: ≤25=critical | ≤50=high | ≤75=medium | >75=low
```

---

## D. Contoh Konkret: Temuan Sama, Domain Beda, Skor Beda

Repo JS monolith dengan 3 temuan:
1. `hardcoded_api_key` — `src/config/stripe.ts:15` — severity asli: `high`
2. `sql_injection` — `src/routes/checkout.ts:45` — severity asli: `medium`  
3. `xss` — `src/components/Comment.tsx:23` — severity asli: `low`

### Skenario E-Commerce

| Temuan | Match | Sev Asli → Final | e | x | c | g | a | L | I | R |
|--------|-------|-----------------|---|---|---|---|---|---|---|---|
| Stripe key | keyword `stripe` → critical | high → **CRITICAL** (+1.0) | 5.0 | 5.0 | 5.0 | 5.0 | 4.0 | 5.00 | 4.67 | 23.3 |
| SQLi checkout | file pattern `checkout` + keyword `sql_injection` → high | medium → **HIGH** (+0.0) | 5.0 | 4.0 | 4.0 | 5.0 | 4.0 | 4.50 | 4.33 | 19.5 |
| XSS Comment | keyword `xss` → high | low → **HIGH** (+0.0) | 4.0 | 5.0 | 3.0 | 4.0 | 2.0 | 4.50 | 3.00 | 13.5 |

```
ΣR = 56.3 | n = 3
RiskScore = max(0, 100 - (56.3 / 75) × 100) = 24.9 → CRITICAL
```

### Skenario Blog

| Temuan | Match | Sev Asli → Final | e | x | c | g | a | L | I | R |
|--------|-------|-----------------|---|---|---|---|---|---|---|---|
| Stripe key | tidak match blog keywords | high → **high** (+0.0) | 4.0 | 5.0 | 5.0 | 4.0 | 3.0 | 4.50 | 4.00 | 18.0 |
| SQLi checkout | keyword `sql_injection`? Tidak ada di blog rules | medium → **medium** (-0.5) | 4.5 | 3.5 | 3.5 | 4.5 | 3.5 | 4.00 | 3.83 | 15.3 |
| XSS Comment | keyword `xss` → high | low → **HIGH** (+0.0) | 4.0 | 5.0 | 3.0 | 4.0 | 2.0 | 4.50 | 3.00 | 13.5 |

```
ΣR = 46.8 | n = 3
RiskScore = max(0, 100 - (46.8 / 75) × 100) = 37.6 → HIGH
```

### Skenario General

| Temuan | Match | Sev Asli → Final | e | x | c | g | a | L | I | R |
|--------|-------|-----------------|---|---|---|---|---|---|---|---|
| Stripe key | tidak ada rules | high → **high** (+0.0) | 4.0 | 5.0 | 5.0 | 4.0 | 3.0 | 4.50 | 4.00 | 18.0 |
| SQLi | tidak ada rules | medium → **medium** (-0.5) | 4.5 | 3.5 | 3.5 | 4.5 | 3.5 | 4.00 | 3.83 | 15.3 |
| XSS | tidak ada rules | low → **low** (-1.0) | 3.0 | 4.0 | 2.0 | 3.0 | 1.0 | 3.50 | 2.00 | 7.0 |

```
ΣR = 40.3 | n = 3
RiskScore = max(0, 100 - (40.3 / 75) × 100) = 46.3 → HIGH
```

### Ringkasan

| Domain | Severity Elevations | ΣR | Risk Score | Level |
|--------|--------------------|------|-----------|-------|
| E-commerce | 3 elevated (critical + high + high) | 56.3 | 24.9 | **CRITICAL** |
| Blog | 1 elevated (high only) | 46.8 | 37.6 | **HIGH** |
| General | 0 elevated | 40.3 | 46.3 | **HIGH** |

---

## E. Justifikasi Teoretis — McConnell (2006)

Perbedaan skor antar domain **bukan kelemahan sistem**, tapi karakteristik alami domain:

| Domain | Kategori McConnell | Produktivitas (LOC/SM) | Kompleksitas | Ekspektasi Risk Score |
|--------|-------------------|------------------------|--------------|----------------------|
| E-commerce | Internet Systems | 600–10.000 | **Tinggi** | Rendah (bahaya) — CRITICAL |
| Healthcare | Business Systems | 800–18.000 | Sedang-Tinggi | Sedang — HIGH |
| Fintech | Internet Systems | 600–10.000 | **Tinggi** | Rendah (bahaya) — CRITICAL |
| Blog | Internet/Business | 500–7.500 | Rendah-Sedang | Tinggi (aman) — MEDIUM/HIGH |
| Education | Business Systems | 800–18.000 | Sedang | Tinggi — HIGH |
| IoT | Internet/Business | 500–7.500 | Sedang | Sedang — HIGH |
| General | Business Systems | 800–18.000 | Sedang | Tinggi — HIGH |

---

## F. Perubahan yang Diperlukan di Naskah

### F.1 Bab 2 — Tambah Sub-Bab Klasifikasi McConnell

**Lokasi:** §2.2 Dasar Teori, sebagai sub-bab baru setelah Attack Surface Identification (§2.2.6) atau sebelum Security Control Selection (§2.2.7).

**Isi:** 
- Klasifikasi *Kind of Software* (McConnell 2006) — tabel produktivitas per kategori
- Pemetaan ke 7 domain webapp penelitian
- Justifikasi: produktivitas rendah = kompleksitas tinggi = lebih banyak kontrol keamanan
- Sitasi: `\cite{mcconnell2006software}`

### F.2 Bab 3 §3.1.3 — Dataset Diperbesar

**Isi:** Tambah tabel pemetaan McConnell → domain + tabel distribusi per bahasa/domain/arsitektur. Draft sudah ada di `lampiran-refactor-bab3.md` §H.

### F.3 Bab 3 §3.6.3 — Domain-Aware Severity Priority

**Perubahan:** Tambah penjelasan di akhir sub-bab:
> *"Mekanisme ini hanya menaikkan (elevate) severity, tidak pernah menurunkan (downgrade). Pendekatannya deterministik (keyword matching) untuk menjamin konsistensi antar eksekusi. Elevation memengaruhi OWASP Risk Rating karena severity modifier memodifikasi 5 dimensi (exploitability, exposure, confidentiality, integrity, availability) sebelum likelihood dan impact dihitung."*

### F.4 Bab 3 §3.6.4 — Risk Assessment (modifier severity)

**Perubahan:** Setelah tabel mapping dimensi OWASP, tambah:
> *"Setiap dimensi dimodifikasi oleh severity temuan: critical +1.0, high +0.0, medium -0.5, low -1.0, dan dijepit dalam rentang [1.0, 5.0]."*

Kalimat ini sudah ada di `chapter-3-v6.tex` baris ~646, tapi perlu diperjelas bahwa severity yang dipakai adalah severity **setelah domain elevation**.

### F.5 Bab 4 §4.6 — Evaluasi Pipeline Multi-Dimensi

**Perubahan terpenting** — tambah sub-bab baru atau tabel baru yang menampilkan:

1. **Tabel risiko per domain** — rata-rata Risk Score untuk 7 domain
2. **Tabel severity elevation summary** — berapa temuan yang ter-elevate per domain
3. **Justifikasi McConnell** — mengapa domain e-commerce/fintech skor lebih rendah

---

## G. Ringkasan

| # | File | Perubahan | Prioritas |
|---|------|-----------|-----------|
| 1 | `chapter-2.tex` | Tambah sub-bab Klasifikasi McConnell §2.2.x | **Wajib** (arahan dosen) |
| 2 | `chapter-3.tex` §3.1.3 | Perbesar dataset: 6 kriteria + tabel McConnell + distribusi | **Wajib** (arahan dosen) |
| 3 | `chapter-3.tex` §3.6.3 | Perjelas: elevation only, deterministik, pengaruh ke risk score | Minor |
| 4 | `chapter-3.tex` §3.6.4 | Perjelas severity modifier: `critical +1.0` dsb + hubungan dgn domain elevation | Minor |
| 5 | `chapter-4.tex` §4.6 | **Breakdown risk score per domain** + tabel elevation + justifikasi McConnell | **Wajib** — inti hasil |
