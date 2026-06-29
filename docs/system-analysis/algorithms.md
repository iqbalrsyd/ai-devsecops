# Algoritma Scoring Sistem DevSecOps Adaptif

Dokumen ini mendokumentasikan formula-formula scoring yang digunakan oleh AI Service untuk menganalisis pipeline CI/CD hasil generasi. Implementasi terdapat di folder `ai-service/app/agents/nodes/`.

---

## 1. Risk Scoring (OWASP Risk Rating)

**File implementasi**: `risk_assessor.py`  
**Node**: `risk_assessor_node`

Setiap temuan keamanan dinilai pada lima dimensi dengan skala 1–5:

| Simbol | Dimensi | 1 | 5 |
|--------|---------|---|---|
| $e_i$ | Exploitability | Teoritis / sulit | Exploit publik / otomatis |
| $x_i$ | Exposure | Komponen internal | Terekspos ke publik |
| $c_i$ | Confidentiality Impact | Tidak ada data sensitif | Secret/token utama bocor |
| $g_i$ | Integrity Impact | Tidak ada dampak | Seluruh pipeline/layanan terganggu |
| $a_i$ | Availability Impact | Tidak ada dampak | Seluruh pipeline/layanan down |

### Formula

Likelihood dan impact per temuan:

$$L_i = \frac{e_i + x_i}{2}, \quad I_i = \frac{c_i + g_i + a_i}{3}$$

Risiko per temuan:

$$R_i = L_i \times I_i \quad (1 \le R_i \le 25)$$

Risk score keseluruhan (skala 0–100, **semakin tinggi semakin aman**):

$$\text{RiskScore} = \max\left(0,\; 100 - \frac{\sum_{i=1}^{n} R_i}{\max(1, n) \cdot 25} \cdot 100\right)$$

### Threshold Risk Level

| Score Range | Risk Level |
|-------------|-----------|
| 0 – 25 | `critical` |
| 26 – 50 | `high` |
| 51 – 75 | `medium` |
| 76 – 100 | `low` |

### Mapping Dimensi

Dimensi diinferensi dari `finding.type` dan `finding.severity`:

- **Secret / credential / token / key**: exposure tinggi, confidentiality maksimal.
- **SQL/command injection / RCE**: exploitability dan integrity impact tinggi.
- **XSS**: exposure publik, integrity impact tinggi.
- **Path traversal / IDOR / SSRF**: exposure dan confidentiality tinggi.
- **Insecure crypto / weak JWT**: confidentiality dan integrity tinggi.
- **Dependency vulnerability / CVE**: exploitability dan integrity tinggi.
- **Resource / timeout error**: availability impact tinggi.
- Severity menambah atau mengurangi semua dimensi: `critical +1`, `high +0`, `medium -0.5`, `low -1`.

---

## 2. Compliance Scoring

**File implementasi**: `compliance_mapper.py`  
**Node**: `compliance_mapper_node`

Compliance score mengukur kepatuhan terhadap tiga kerangka standar yang berlaku.

### Formula

$$\text{ComplianceScore} = \text{AVG}\left(
\frac{\text{compliant\_owasp\_cicd}}{\text{total\_owasp\_cicd}} \times 100,\;
\frac{\text{owasp\_top10\_covered}}{10} \times 100,\;
\frac{\text{compliant\_cis}}{\text{total\_cis}} \times 100
\right)$$

Hanya standar yang tercantum dalam `inferred_security_needs.compliance_standards` yang dievaluasi. Jika tidak ada daftar standar, sistem mengevaluasi semua secara default.

### Standar yang Dievaluasi

#### OWASP CI/CD Security Controls

8 kontrol berikut dicek terhadap workflow yang dihasilkan:

| ID | Kontrol | Cara Cek |
|----|---------|----------|
| CICD-SAST-01 | SAST scan present | `sast` ada di `required_stages` |
| CICD-DEP-01 | Dependency scan present | `dependency-scan` ada di `required_stages` |
| CICD-SEC-01 | Secret scan present | `secret-scan` ada di `required_stages` |
| CICD-CON-01 | Container scan present | Docker terdeteksi & `container-scan` di `required_stages` |
| CICD-PIN-01 | Actions pinned to SHA | Tidak ada error pemeriksaan SHA pinning |
| CICD-PRM-01 | Minimal permissions | Tidak ada warning permissions |
| CICD-CUR-01 | Concurrency configured | Tidak ada warning concurrency |
| CICD-DPL-01 | Deploy gated with condition | Tidak ada warning kondisi deploy |

#### OWASP Top 10

Menghitung jumlah kategori OWASP Top 10 yang tercakup oleh temuan. Setiap `finding.owasp` dinormalisasi ke kode kategori (misal `"A1: Injection"` → `A1`).

$$\text{score} = \frac{\text{jumlah kategori unik}}{10} \times 100$$

#### CIS Kubernetes Benchmark

Dievaluasi hanya jika deployment target mengandung Kubernetes. Menggunakan subset 5 kontrol:

| ID | Kontrol | Cara Cek |
|----|---------|----------|
| CIS-5.1.1 | Image Vulnerability Scanning | `container-scan` di `required_stages` |
| CIS-5.1.2 | Minimize Privileged Containers | Tidak ada `privileged` di job |
| CIS-5.1.3 | Minimize hostPath | Tidak ada `hostpath` di job |
| CIS-5.1.6 | Minimize Root Containers | Tidak ada indikasi `run-as-root` |
| CIS-5.3.2 | Secrets Encrypted in ETCD | `secret-scan` atau vault/sealed secrets |

---

## 3. Security Coverage

**File implementasi**: `compliance_mapper.py`  
**Node**: `compliance_mapper_node`

Security Coverage mengukur persentase kontrol **OWASP CI/CD Security Controls**
yang benar-benar diimplementasikan pada workflow yang dihasilkan. Metrik ini
bersumber dari kerangka referensi yang sama dengan komponen OWASP CI/CD pada
Compliance Score, sehingga tidak memerlukan bobot atau formula kustom.

### Formula

$$\text{SecurityCoverage} = \frac{\text{owasp\_cicd\_passed}}{\text{total\_owasp\_cicd}} \times 100$$

### Referensi

| Kontrol | Sumber Data | Kerangka |
|---------|-------------|----------|
| 8 OWASP CI/CD Security Controls | Status implementasi dari workflow hasil generasi | OWASP CI/CD Security Controls |

Workflow configuration issues, maintenance warnings, dan external service issues
tidak termasuk dalam perhitungan Security Coverage.

---

## Referensi

- `ai-service/app/agents/nodes/risk_assessor.py`
- `ai-service/app/agents/nodes/compliance_mapper.py`
- `ai-service/app/agents/nodes/workflow_validator.py`
- `struktur-v4.md` Bagian 11.6 – 11.8
