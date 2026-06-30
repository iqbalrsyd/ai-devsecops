# ISA Controls → v9 Coverage Pipeline Mapping

## Hubungan dengan struktur-v9

Dokumen ini menjembatani **72 kontrol ISA (Unilever Information Security Assessment)** ke **15 security coverages** dan **pipeline augmentations** yang didefinisikan di `struktur-v9.md` (§Tahap 2: Security Coverage Inference).

```
┌─────────────────┐      ┌──────────────────────┐      ┌─────────────────────────┐
│  72 ISA Controls │ ──→  │ 15 Security Coverages │ ──→  │ Pipeline Augmentations   │
│  (audit standard)│      │ (coverage_inference)  │      │ (pipeline_augmentation)  │
│                  │      │ §COVERAGE_LIBRARY     │      │ §DEFAULT_AUGMENTATIONS   │
└─────────────────┘      └──────────────────────┘      └─────────────────────────┘
   BUSINESS LAYER             TECHNICAL LAYER               CI/CD LAYER
   "what to audit"            "what to protect"             "how to enforce"
```

---

## 1. Ringkasan: ISA → v9 Coverage (15-way Mapping)

| v9 Coverage ID | v9 Deskripsi | ISA Controls yg Dicover | Jumlah ISA | 
|---|---|---|---|
| `authentication_security` | Auth flow, session, JWT, OAuth, login | ISA 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 62, 63, 64, 65, 69, 70 | **16** |
| `api_security` | REST/GraphQL, OWASP API Top 10 | ISA 72 (API), ISA 36 (App Scan), ISA 37-38 (Code Review + Remediation) | **4** |
| `data_security` | Database, ORM, SQL injection, encryption | ISA 33, 34, 35 (Backup/DR), ISA 45, 46 (Encryption), ISA 60, 61, 66 | **8** |
| `payment_security` | Payment, PCI-DSS, financial transaction | *(tidak ada ISA spesifik Unilever; indirectly: ISA 45-46, 61)* | **0** |
| `container_security` | Docker, image security, Dockerfile | ISA 13-17 (Secure Config), ISA 68 (Standard Builds), ISA 71 (AI Hardening) | **8** |
| `iot_security` | MQTT, sensor, firmware, device | ISA 23-24 (Anti-Malware), ISA 32 (Wireless) | **3** |
| `logging_security` | App logging, sensitive data in logs | ISA 19, 20, 21, 22, 67 | **5** |
| `file_upload_security` | Multipart upload, path traversal | *(tidak ada ISA spesifik)* | **0** |
| `healthcare_security` | PHI, FHIR, HIPAA | *(tidak ada ISA spesifik; indirectly: ISA 45-46 enkripsi data sensitif)* | **0** |
| `fintech_security` | Ledger, banking, KYC | *(tidak ada ISA spesifik; indirectly: ISA 45-46, 61)* | **0** |
| `cms_security` | Blog post, comment moderation | *(tidak ada ISA spesifik)* | **0** |
| `education_security` | LMS, course, student records | *(tidak ada ISA spesifik)* | **0** |
| `microservice_security` | (REMOVED per R2.1 — arsitektur bukan variabel) | (N/A) | **0** |
| `csp_security` | Content Security Policy, Helmet, secure headers | ISA 17 (Network Device Config) *(remote)* | **1** |
| `dependency_security` | SCA, CVEs, npm audit, pip-audit | ISA 03-04 (Asset Inventory), ISA 06 (Patch), ISA 09 (Vuln Remediation) | **4** |
| *(organizational)* | *Controls diluar pipeline otomatis* | ISA 01-02, ISA 05, ISA 08, ISA 10, ISA 18, ISA 40-41, ISA 42, ISA 43-44, ISA 57-58, ISA 59 | **14** |

> **Coverage gap**: Dari 72 ISA, **58 kontrol** bisa dipetakan ke 15 coverage v9 ↔ pipeline tooling. **14 kontrol** bersifat *organizational/governance/manual* (tidak bisa diotomatisasi penuh oleh pipeline — perlu bukti audit manual).

---

## 2. Pemetaan Detail: ISA → v9 Coverage → Pipeline Tool

### 2.1 `authentication_security` (16 ISA Controls)

ISA IAM controls yang terdeteksi oleh signals: `passport`, `jsonwebtoken`, `bcrypt`, `oauth`, `next-auth`, routes `/login`, `/signup`, entities `user`, `session`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 47 | Privileged Accounts → PAM (CyberArk) | entity: `account`, route: `/admin` | `sast` (hardcoded-credentials) |
| ISA 48 | Admin Account — Periodic Review | entity: `account` | `secret_scan` (JWT/OAuth focus) |
| ISA 49 | Identity & Access — Unique ID (SSO/AD) | lib: `passport`, `oauth`, `jsonwebtoken` | `sast` (p/secrets) |
| ISA 50 | Identity & Access — AD Integration | lib: `jsonwebtoken`, `bcrypt` | `secret_scan` |
| ISA 51 | Orphan/Dormant Account Mgmt | entity: `user` | `sast` (p/secrets) |
| ISA 52 | Password Policy Compliance | lib: `bcrypt`, `argon2` | `sast` (hardcoded-credentials) |
| ISA 53 | Leaver Account — Disable | entity: `user`, `account` | `secret_scan` |
| ISA 54 | Periodic Access Review | entity: `user`, `audit` | `sast` |
| ISA 55 | Auth Credential Encrypted/Hashed | lib: `bcrypt`, `argon2`, `crypto` | `sast` (p/secrets) |
| ISA 56 | MFA for High Risk Access | lib: `speakeasy`, `otplib` | `sast` (p/secrets) |
| ISA 62 | Service Accounts — Interactive Login Disabled | entity: `account`, `service` | `secret_scan` |
| ISA 63 | IGA — Saviynt/SAP GRC Onboarding | entity: `account`, `auth` | `secret_scan` |
| ISA 64 | SSO + MFA for All Apps & Tools | lib: `passport`, `oauth`, `next-auth` | `sast` (p/secrets) |
| ISA 65 | B2B Identity — ACAM Guest Access | entity: `account` | `secret_scan` |
| ISA 69 | Account Hardening — Active Directory | entity: `account`, `server` | `sast` (hardcoded-credentials) |
| ISA 70 | Account Hardening — Default Accounts | entity: `account` | `sast` (hardcoded-credentials) |

**Hubungan Internal (IAM lifecycle)**:
```
ISA 47 (Provision) → ISA 48 (Review) → ISA 49-50 (Identity/SSO) → ISA 51 (Dormant Cleanup)
                                                                  → ISA 52 (Password Policy)
                                                                  → ISA 53 (Leaver Disable)
                                                                  → ISA 54 (Periodic Review)
ISA 52 → ISA 55 (Hash Enforcement)
ISA 49-50 → ISA 56 (MFA)
ISA 62-65 (UL Account) → ISA 64 (SSO+MFA Comprehensive)
ISA 69-70 (Hardening) → ISA 47 (Privileged)
```

**Hubungan Cross-Domain**:
```
IAM ↔ Logging (ISA 19-22): semua aktivitas IAM harus ter-log ke SIEM
IAM ↔ Secure Config (ISA 13-17): konfigurasi IAM = bagian hardening
ISA 53 (Leaver) → ISA 66 (Data Deletion): hapus akun + hapus data
ISA 64 (SSO+MFA) → ISA 29 (Remote Access): remote wajib via SSO+MFA
```

---

### 2.2 `api_security` (4 ISA Controls)

Terdeteksi dari: `express`, `fastify`, `nestjs`, `graphql`, `apollo`, routes `/api`, `/graphql`, entities `controller`, `endpoint`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 72 | API Security (scan, gateway, TLS, credential) | lib: `express`, routes: `/api` | **Primary match**: `sast` (owasp-api.yml) |
| ISA 36 | Application Security Scan (web/mobile) | lib: `express`, `fastify` | `sast` (p/owasp-top-ten, p/javascript) |
| ISA 37 | Secure Code Review & Error Handling | entity: `controller`, `router` | `sast` (p/nodejs) |
| ISA 38 | Code Vuln Remediation (SLA) | — | `sast` (p/owasp-top-ten) |

**Hubungan Internal**:
```
ISA 72.a (API Scan) → ISA 36 (App Scan) [API = subset dari application]
ISA 72.b (Gateway) → ISA 28 (WAF) [SAP BTP = API gateway]
ISA 72.c (TLS) → ISA 45 (Encryption in Transit)
ISA 72.d (Credential Mgmt) → ISA 55 (Hash) + ISA 62 (Service Accounts)
```

**Hubungan Cross-Domain**:
```
ISA 72 (API) → ISA 11-12 (Pentest): pentest harus meliputi API
ISA 72 (API) → ISA 28 (WAF): API dilindungi WAF
ISA 36 (App Scan) → ISA 07 (Vuln Scan): app scan ≠ infra scan, saling melengkapi
ISA 38 (SLA) → ISA 09 (Vuln SLA): SLA pattern yang sama
```

---

### 2.3 `data_security` (8 ISA Controls)

Terdeteksi dari: `sequelize`, `prisma`, `mongoose`, `mysql`, `pg`, `mongodb`, entities `db`, `model`, `schema`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 33 | Automated Backups (SC/DR) | entity: `db`, `backup` | `sca` (misconfig) |
| ISA 34 | Periodic Backup Restoration (RTO/RPO) | entity: `db` | `sca` |
| ISA 35 | IT Service Continuity Drills | — | — (manual) |
| ISA 45 | Sensitive Data Encrypted in Transit | lib: `tls`, `https`, `helmet` | `sast` (p/sql-injection) |
| ISA 46 | Sensitive Data Encrypted at Rest | lib: `crypto`, `bcrypt` | `sast` (p/sql-injection) |
| ISA 60 | Data Managed — Risk Strategy (Backup Protection) | entity: `backup`, `db` | `sca` |
| ISA 61 | CIA — TLS Certificate Validity | lib: `https`, `tls` | `sast` (p/sql-injection) |
| ISA 66 | Information Handling — Secure Data Deletion | entity: `db`, `log` | `sca` |

**Hubungan Internal**:
```
ISA 33 (Backup) → ISA 34 (Restore Test) → ISA 35 (DR Drill)
ISA 33 → ISA 60 (Backup Protection)
ISA 45 (Transit) ↔ ISA 46 (Rest): wajib encrypted di kedua state
ISA 61 (TLS) → ISA 45 (Transit): TLS = mekanisme transit encryption
ISA 66 (Deletion) ↔ ISA 67 (Log Retention): data lifecycle
```

**Hubungan Cross-Domain**:
```
Data ↔ IAM: backup access harus privileged (ISA 47)
Data ↔ Network: data in transit harus melalui secure channel (ISA 29, ISA 45)
ISA 66 (Deletion) → ISA 53 (Leaver): hapus data saat leaver
ISA 35 (DR) → ISA 42 (Incident Response): major incident triggers DR
```

---

### 2.4 `container_security` (8 ISA Controls)

Terdeteksi dari: deployment signal `docker`, `docker_compose`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 13 | Secure Configuration Baselines (CIS) | deployment: `docker` | `container_scan` (Trivy image + Dockerfile) |
| ISA 14 | Config Monitoring — Scanning | deployment: `docker_compose` | `container_scan` |
| ISA 15 | Config Remediation (Critical/High) | — | `container_scan` |
| ISA 16 | Config Monitoring — Frequency | — | `container_scan` |
| ISA 68 | Management of Standardized Builds (Golden Image/IaC) | deployment: `docker`, `docker_compose` | `container_scan` |
| ISA 71 | AI System Hardening (Guardrails) | deployment: `docker` | `container_scan` |
| ISA 03 | Asset Inventory (OS/DB versions) | entity: `db`, deployment: `docker` | — |
| ISA 04 | Remediation of Obsolete/EoL | deployment: `docker` | `container_scan` |

**Hubungan Internal**:
```
ISA 13 (Baselines) → ISA 14 (Scan) → ISA 15 (Remediate)
ISA 16 (Frequency) → validasi ISA 14
ISA 13 → ISA 68 (Standardized Builds): baseline = golden image
ISA 13-17 → ISA 71: extended ke AI systems
```

**Hubungan Cross-Domain**:
```
Config ↔ Logging (ISA 19-22): semua config changes harus ter-log
Config ↔ Network (ISA 25-28): firewall = bagian secure config
ISA 18 (NTP) → Logging: timestamp consistency
ISA 68 (Standard Builds) → ISA 03 (Inventory): standardized build mempermudah inventory
```

---

### 2.5 `microservice_security` (REMOVED per R2.1)

**Status:** Dihapus per R2.1 (revisi 3-domain & 1-architecture). Arsitektur
bukan variabel eksperimen, sehingga coverage `microservice_security` tidak
applicable untuk dataset monolitik. Hubungan ISA di bawah ini tetap
disimpan sebagai referensi untuk coverage lain (terutama `api_security`).

Terdeteksi dari (legacy, tidak applicable): architecture signal
`microservices`, `modular_monolith`, libs `istio`, `linkerd`, `consul`,
`envoy`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 25 | Only Approved Ports, Protocols, Services | entities: `service`, `gateway` | (N/A — covered by `api_security`) |
| ISA 26 | Firewall Protection — Change Mgmt | entities: `service`, `gateway` | (N/A — covered by `api_security`) |
| ISA 27 | Firewall Rule Review | — | (N/A) |
| ISA 28 | WAF Protection | entities: `gateway`, `service` | (N/A — covered by `api_security`) |
| ISA 30 | Network-Based URL Filters (Proxy/Gateway) | entities: `gateway`, `proxy` | (N/A) |
| ISA 31 | Intrusion Detection/Prevention (IDS/IPS) | entities: `service` | (N/A) |
| ISA 39 | Prod/Non-Prod Segregation | architecture: `microservices` | (N/A) |

**Hubungan Internal** (referensi historis):
```
ISA 25 (Ports) → ISA 26-27 (Firewall) → ISA 28 (WAF) → ISA 30 (Proxy)
ISA 29 (Remote Access) → ISA 31 (IDS/IPS)
ISA 39 (Segregation) → ISA 25 (Ports): segregation = port isolation
```

**Hubungan Cross-Domain**:
```
Network ↔ Logging: network events → SIEM (ISA 21-22)
Network ↔ Secure Config (ISA 13-17): network config = bagian hardening
ISA 29 (Remote Access) → ISA 64 (SSO+MFA) + ISA 56 (MFA)
ISA 28 (WAF) → ISA 72 (API Security): API perlu WAF
```

---

### 2.6 `logging_security` (5 ISA Controls)

Terdeteksi dari: `winston`, `bunyan`, `pino`, `log4j`, `logrus`, `morgan`, entities `log`, `audit`, `logger`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 19 | Log Activation & Maintenance | lib: `winston`, entities: `log` | `sast` (sensitive-data-in-logs.yml) |
| ISA 20 | Monitoring & Analysis of Audit Logs | entities: `log`, `audit` | `sca` |
| ISA 21 | Logs Centralized → SIEM (System) | entities: `log`, lib: `winston` | `sast` (sensitive-data-in-logs.yml) |
| ISA 22 | Logs Centralized → SIEM (Application) | lib: `morgan`, `pino` | `sast` (sensitive-data-in-logs.yml) |
| ISA 67 | Log Retention Management | entities: `log`, `audit` | `sca` |

**Hubungan Internal**:
```
ISA 19 (Activation) → ISA 20 (Analysis) → ISA 21-22 (Centralized SIEM) → ISA 67 (Retention)
```

**Hubungan Cross-Domain**:
```
Logging → IAM: aktivitas IAM harus ter-log
Logging → Network: IDS/IPS logs ke SIEM (ISA 31)
Logging → Incident Response (ISA 42): log = bukti forensik
ISA 18 (NTP) → Logging: timestamp consistency
ISA 67 (Log Retention) ↔ ISA 66 (Data Deletion): lifecycle management
```

---

### 2.7 `dependency_security` (4 ISA Controls)

Terdeteksi dari: package managers `npm`, `yarn`, `pip`, `go mod`, `cargo`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 03 | Asset Inventory — Device/OS/DB Versions | package_managers | `sca` (npm audit / pip-audit / govulncheck) |
| ISA 04 | Remediation of Obsolete/EoL | package_managers | `sca` |
| ISA 06 | Patch Deployment — OS/Firmware/Software | package_managers | `sca` |
| ISA 09 | Vuln Remediation by Risk (SLA) | — | `sca` |

**Hubungan Internal**:
```
ISA 03 (Inventory) → ISA 04 (EoL Remediation) → ISA 06 (Patch) → ISA 09 (Remediation SLA)
```

**Hubungan Cross-Domain**:
```
Dependency ↔ Container: Docker image juga punya dependency (ISA 13-17)
ISA 06 (Patch) → ISA 24 (Anti-Malware Updates): keduanya update rutin
ISA 09 (SLA) → ISA 38 (Code SLA): SLA pattern seragam
```

---

### 2.8 `iot_security` (3 ISA Controls)

Terdeteksi dari: `mqtt`, `paho-mqtt`, `amqp`, `coap`, `modbus`, entities `device`, `sensor`, `telemetry`, `firmware`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 23 | Centrally Monitored Anti-Malware | entities: `device` | `sast` (iot-mqtt.yml) |
| ISA 24 | Periodic Updates — AV Signatures | entities: `device`, `firmware` | `secret_scan` (device creds) |
| ISA 32 | Secure Wireless Access (scan unauthorized AP) | entities: `device`, `sensor` | `sast` (iot-mqtt.yml) |

---

### 2.9 `csp_security` (1 ISA Control)

Terdeteksi dari: `helmet`, `csp`, `express-helmet`.

| ISA | Control | Signal Match | v9 Augmentation |
|-----|---------|-------------|-----------------|
| ISA 17 | Secure Network Device Configuration | lib: `helmet` (CSP headers = network security) | `sast` (csp-header-check.yml) |

---

### 2.10 `file_upload_security` (0 ISA Controls)

Terdeteksi dari: `multer`, `formidable`, `sharp`, routes `/upload`, `/files`.

> **Tidak ada ISA control spesifik untuk file upload.** Coverage ini purely dari v9 signal detection. Secara implisit terkait dengan:
> - ISA 13 (Secure Config): konfigurasi upload path harus secure
> - ISA 36 (App Scan): aplikasi harus di-scan untuk file upload vulnerability

---

### 2.11 `payment_security`, `healthcare_security`, `fintech_security`, `cms_security`, `education_security` (0 ISA Controls)

> Kelima coverage ini purely domain-driven dari v9 signal detection (libraries, entities, routes spesifik per domain). **Tidak ada ISA control Unilever yang eksplisit menyebutkan** payment, healthcare, fintech, CMS, atau education. ISA Unilever bersifat generik (hanya butuh: "data sensitif harus dienkripsi" — ISA 45-46 — regardless of domain).

---

## 3. ISA Controls Organisasional (Tidak Bisa Diotomatisasi Pipeline)

14 kontrol berikut membutuhkan **bukti audit manual** — tidak bisa di-generate oleh pipeline otomatis:

| ISA | Control | Kenapa Manual |
|-----|---------|---------------|
| ISA 01-02 | Secure Management of Assets (CMDB) | Bukti screenshot/tiket — bukan dari kode |
| ISA 05 | Application Whitelisting Review | Proses review tahunan — bukan dari kode |
| ISA 08 | Continuous Vulnerability Management | Bukti proses, bukan dari kode |
| ISA 10 | Vuln Scan Frequency Compliance | Bukti scan report — butuh evidence eksternal |
| ISA 11-12 | Penetration Testing (Remediation + Frequency) | Laporan pentest eksternal |
| ISA 18 | NTP Synchronization | Konfigurasi infrastruktur, bukan kode |
| ISA 29 | Secure Remote Access (VPN/ZPA/Citrix) | Konfigurasi network, bukan kode |
| ISA 40 | Security Awareness Training | Training records — bukan dari kode |
| ISA 41 | Incident Reporting Protocols | Policy documents — bukan dari kode |
| ISA 42 | Incident Response Exercises | Bukti incident tracker — bukan dari kode |
| ISA 43 | Mobile Device Encryption (Intune) | Mobile device management — bukan dari kode |
| ISA 44 | External Storage Encryption (BitLocker) | Endpoint management — bukan dari kode |
| ISA 57-58 | Secure SDLC + Test Data | Policy docs + process evidence |
| ISA 59 | Service Introduction — Change Mgmt | Ticket evidence |
| ISA 71 | AI System Approval Board | Board approval docs |

> **Dampak pada scoring**: 14 dari 72 kontrol (~19%) tidak bisa di-cover oleh pipeline. Max theoretical `security_standards_coverage_score` ≈ 81%.

---

## 4. Hubungan Antar ISA Control: Full Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ISA CONTROL DEPENDENCY MAP                        │
│                    (arah panah = "membutuhkan" / "bergantung pada")          │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌── ISA 01-02 (CMDB Foundation)
                        │
    ┌───────────────────┼──────────────────────────────────────────┐
    │                   ▼                                          │
    │           ISA 03 (Asset Inventory)                           │
    │              │          │                                     │
    │              ▼          ▼                                     │
    │      ISA 04 (EoL)   ISA 47-50 (IAM Identity)                 │
    │         │                │         │                          │
    │         ▼                │         ▼                          │
    │   ISA 06 (Patch)         │   ISA 51 (Dormant)                 │
    │         │                │   ISA 52 (Password)                │
    │         │                │   ISA 53 (Leaver)                  │
    │         │                │   ISA 54 (Review)                  │
    │         │                │   ISA 55 (Hash)                    │
    │         │                │   ISA 56 (MFA)                     │
    │         │                │   ISA 62-65 (UL Acct)              │
    │         │                │   ISA 69-70 (Hardening)            │
    │         │                │         │                          │
    │         │                │         └────────────┐             │
    │         │                │                      │             │
    │         ▼                ▼                      ▼             │
    │   ISA 07-10 (Vuln Mgmt)  │              ISA 64 (SSO+MFA)      │
    │         │                │                                    │
    │         ├────────────┬───┘                                    │
    │         ▼            ▼                                        │
    │   ISA 11-12     ISA 36-39 (App Sec)                           │
    │   (Pentest)         │                                          │
    │         │           ├── ISA 57 (SDLC)                         │
    │         │           ├── ISA 58 (Test Data)                    │
    │         │           └── ISA 72 (API)                          │
    │         │                │                                    │
    │         └────────┬───────┘                                    │
    │                  ▼                                            │
    │           ISA 13-17 (Secure Config)                           │
    │           ISA 68 (Standard Builds)                            │
    │           ISA 71 (AI Hardening)                               │
    │                  │                                            │
    │    ┌─────────────┼─────────────┐                              │
    │    ▼             ▼             ▼                              │
    │ ISA 25-32    ISA 18 (NTP)   ISA 23-24                        │
    │ (Network)        │          (Anti-Malware)                    │
    │    │             ▼             │                              │
    │    │       ISA 19-22 (Logging)│                              │
    │    │       ISA 67 (Retention) │                              │
    │    │             │             │                              │
    │    └──────┬──────┘             │                              │
    │           ▼                    │                              │
    │     ISA 45-46 (Encryption)     │                              │
    │     ISA 61 (TLS/CIA)           │                              │
    │           │                    │                              │
    │           ├── ISA 33-35 (DR)   │                              │
    │           ├── ISA 60 (Backup)  │                              │
    │           ├── ISA 66 (Delete)  │                              │
    │           └── ISA 43-44 (Mobile/Ext)                          │
    │                                                                │
    └─────────────── ISA 40-41 (Training) ◄── applies to ALL ───────┘
                    ISA 42 (Incident Response)
```

---

## 5. Alignment dengan v9 Pipeline: Coverage → Augmentation

Tabel ini eksplisit menyesuaikan dengan `§DEFAULT_AUGMENTATIONS` di `pipeline_augmentation_node.py`:

| v9 Coverage | ISA Controls | Augmentation Jobs | Semgrep Rules |
|-------------|-------------|-------------------|---------------|
| `authentication_security` | 16 ISA (47-56, 62-65, 69-70) | `sast`, `secret_scan` | `p/secrets`, `p/jwt` |
| `api_security` | 4 ISA (36-38, 72) | `sast` | `owasp-api.yml`, `p/owasp-top-ten`, `p/javascript`, `p/nodejs` |
| `data_security` | 8 ISA (33-35, 45-46, 60-61, 66) | `sast`, `sca` | `p/sql-injection` |
| `payment_security` | 0 ISA (domain-driven) | `sast`, `secret_scan` | `pci-dss.yml`, `ecommerce.yml` |
| `container_security` | 8 ISA (03-04, 13-17, 68, 71) | `container_scan` | *(Trivy image + Dockerfile)* |
| `iot_security` | 3 ISA (23-24, 32) | `sast`, `secret_scan` | `iot-mqtt.yml` |
| `logging_security` | 5 ISA (19-22, 67) | `sast`, `sca` | `sensitive-data-in-logs.yml` |
| `file_upload_security` | 0 ISA (lib-driven) | `sast` | `path-traversal.yml`, `file-upload-bypass.yml` |
| `healthcare_security` | 0 ISA (domain-driven) | `sast`, `secret_scan` | `hipaa.yml` |
| `fintech_security` | 0 ISA (domain-driven) | `sast`, `secret_scan` | `fintech-ledger.yml` |
| `cms_security` | 0 ISA (domain-driven) | `sast`, `sca` | `blog-csp.yml` |
| `education_security` | 0 ISA (domain-driven) | `sast` | `education-lms.yml` |
| `microservice_security` | 7 ISA (25-31, 39) — REMOVED per R2.1 | (N/A) | — |
| `csp_security` | 1 ISA (17) | `sast` | `csp-header-check.yml` |
| `dependency_security` | 4 ISA (03-04, 06, 09) | `sca` | *(npm audit / pip-audit / govulncheck)* |

---

## 6. Scoring: Security Standards Coverage

Formula di `compliance_mapper_node()` (v9) — \( \text{score} = \frac{\sum(\text{covered\_isa} \times w)}{\sum(\text{applicable\_isa} \times w)} \times 100\% \)

| Weight Tier | Bobot | ISA Controls |
|-------------|-------|-------------|
| **Critical** (w=3) | Log, WAF, IPS, Encryption, MFA, SSO, API | ISA 19, 28, 31, 45, 46, 56, 64, 72 |
| **High** (w=2) | Patch, Vuln Scan, Pentest, Config, SIEM, Backup, DR, App Scan, Incident, Admin, Hash, SDLC | ISA 06, 07, 11, 13, 21, 22, 33, 35, 36, 42, 47, 55, 57 |
| **Medium** (w=1) | Inventory, Obsolete, Whitelist, Continuous, SLA, Frequency, Config details, NTP, Anti-Malware, Network details, Wireless, Restore, App details, Mobile, Storage, IAM details, UL Account, Data lifecycle | ISA 01-05 (kecuali 03-04 high), 08-10, 12, 14-18, 20, 23-27, 29-30, 32, 34, 37-41, 43-44, 48-54, 58-63, 65-71 |

---

## 7. NIST CSF Mapping

| NIST Function | Jml ISA | Controls |
|--------------|---------|---------|
| **IDENTIFY** | 13 | ISA 03, 04, 05, 07, 10, 25, 47, 48, 49, 50, 59, 60, 66 |
| **PROTECT** | 37 | ISA 06, 13, 14, 15, 16, 17, 23, 24, 26, 27, 28, 29, 30, 32, 33, 34, 35, 43, 44, 45, 46, 52, 55, 56, 57, 58, 61, 62, 63, 64, 65, 68, 69, 70, 71, 72 |
| **DETECT** | 12 | ISA 08, 19, 20, 21, 22, 31, 36, 37, 38, 39, 67 |
| **RESPOND** | 7 | ISA 09, 11, 12, 15, 41, 42, 53 |
| **RECOVER** | 3 | ISA 34, 35, 60 |

> Distribusi NIST: **PROTECT > IDENTIFY > DETECT > RESPOND > RECOVER** — sesuai karakteristik ISA Unilever yang fokus pada proteksi dan identifikasi aset.

---

## 8. Alat (Tools) yang Digunakan dalam CI Pipeline

### 8.1 Ringkasan Tools

| Kategori | Tool | Lisensi | ISA Coverage | v9 Job | Output Format |
|---------|------|---------|-------------|--------|--------------|
| **SAST** | Semgrep | LGPL-2.1 | ISA 36, 37, 45, 46, 52, 55, 57, 72 | `sast` | Semgrep JSON / SARIF |
| **SAST** | CodeQL | MIT | ISA 36, 37, 38 | `sast` (opsional) | SARIF |
| **SCA** | npm audit | Built-in npm | ISA 04, 06, 09 | `dependency-scan` | JSON |
| **SCA** | pip-audit | Apache-2.0 | ISA 04, 06, 09 | `dependency-scan` | JSON / CycloneDX |
| **SCA** | govulncheck | BSD-3 | ISA 04, 06, 09 | `dependency-scan` | JSON |
| **SCA** | Trivy | Apache-2.0 | ISA 04, 06, 09, 13, 14, 68 | `container-scan` / `dependency-scan` | JSON / SARIF |
| **Secret** | Gitleaks | MIT | ISA 47, 51, 55, 62, 72 | `secret-scan` | JSON / SARIF |
| **Container** | Trivy (image) | Apache-2.0 | ISA 13, 14, 15, 68 | `container-scan` | JSON / SARIF |
| **Container** | Docker Scout | Docker TOS | ISA 13, 14 | `container-scan` (opsional) | JSON |
| **DAST** | OWASP ZAP | Apache-2.0 | ISA 36, 72, 11* | *(manual/pentest)* | JSON / HTML |
| **Lint** | ESLint / Pylint | MIT / GPL | ISA 57 (code quality) | `lint` | SARIF |
| **Build** | npm / pip / go / cargo | Various | — | `build` | — |
| **Test** | Jest / pytest / go test | MIT | ISA 37 (error handling) | `test` | JUnit XML |

### 8.2 Rationale Pemilihan Tools

#### 8.2.1 Mengapa Semgrep sebagai SAST Utama?

| Pertimbangan | Keputusan |
|--------------|-----------|
| **Custom rules** | Semgrep punya DSL (`pattern:`) yang bisa menulis aturan domain-specific — dari situ lahir `owasp-api.yml`, `pci-dss.yml`, `ecommerce.yml`, `hipaa.yml`, `iot-mqtt.yml`, `fintech-ledger.yml`, `blog-csp.yml`, `education-lms.yml` — yang langsung memetakan sinyal domain (libraries, entities, routes) ke vulnerability pattern. CodeQL pakai QL yang lebih kompleks, kurang cocok untuk prototyping cepat. |
| **Performance** | Semgrep analisis per-file paralel, mendukung diff-aware scanning (hanya scan file yang berubah). Ini critical untuk pipeline CI yang harus selesai <5 menit. |
| **Ecosystem** | 2000+ aturan community, SARIF output, integrasi native GitHub. |
| **Domain-specific rules** | Ini alasan utama — tidak ada tool SAST lain yang bisa menulis aturan seperti `pci-dss.yml` (deteksi pattern kartu kredit + checkout flow) secepat Semgrep. |

#### 8.2.2 Mengapa Trivy untuk Container + SCA?

| Pertimbangan | Keputusan |
|--------------|-----------|
| **Multi-purpose** | Satu binary untuk 4 use case: image scan, filesystem scan, git repo scan, Kubernetes cluster scan. Tidak perlu install 4 tool berbeda. |
| **Database** | Trivy memperbarui vulnerability database (NVD, GHSA, Red Hat, Debian, Alpine) setiap 12 jam — lebih cepat dari Docker Scout (24 jam). |
| **SBOM support** | Output CycloneDX / SPDX — bisa dikonsumsi oleh sistem compliance yang lebih besar. |
| **Dockerfile linting** | Trivy bisa langsung baca Dockerfile dan deteksi misconfiguration (user root, port exposed, no healthcheck) — langsung cover ISA 13, 14, 68. |

#### 8.2.3 Mengapa Gitleaks untuk Secret Scanning?

| Pertimbangan | Keputusan |
|--------------|-----------|
| **Git-aware** | Gitleaks di-design untuk scan git history — bukan hanya file saat ini. Bisa deteksi secret yang pernah di-commit lalu dihapus (masih ada di git log). |
| **Entropy + regex hybrid** | Kombinasi regex pattern matching (120+ rules bawaan: AWS key, GCP SA, GitHub PAT, Stripe key, JWT) + entropy detection untuk high-entropy strings. |
| **False positive rate rendah** | Dibandingkan TruffleHog (yang sering false positive pada base64 encoded strings non-secret), Gitleaks lebih akurat karena kombinasi pattern + allowlist. |
| **Performance** | Scan 1000 commits dalam <30 detik — cocok untuk CI. |

#### 8.2.4 Mengapa npm audit / pip-audit / govulncheck (Native SCA)?

| Pertimbangan | Keputusan |
|--------------|-----------|
| **Zero config** | Tidak perlu install binary tambahan — sudah built-in di package manager. |
| **Akurasi** | Dependency tree dari lockfile (`package-lock.json`, `Pipfile.lock`, `go.sum`) lebih akurat daripada SCA generik karena native resolver. |
| **Familiarity developer** | Developer sudah terbiasa dengan `npm audit` — tidak ada learning curve. |

#### 8.2.5 Mengapa OWASP ZAP untuk DAST (Opsional)?

| Pertimbangan | Keputusan |
|--------------|-----------|
| **Otomatisasi** | ZAP punya automation framework (Python client `zap-cli`) dan headless mode — bisa dijalankan sebagai bagian CI (walaupun lebih lambat: 10-30 menit). |
| **API scanning** | ZAP punya OpenAPI/Swagger importer — cocok untuk ISA 72 (API security). |
| **Industry standard** | Diadopsi oleh OWASP, digunakan sebagai benchmark di banyak compliance audit. |
| **Keterbatasan** | DAST tidak bisa dijalankan per-commit (terlalu lambat). Dijadwalkan post-deploy / nightly. |

---

## 9. Bagaimana Tools Dijahit Menjadi Satu Pipeline

### 9.1 Arsitektur Penjahitan

Pipeline tidak menjalankan tools secara terisolasi — semuanya "dijahit" melalui **3 lapisan integrasi**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                       LAPISAN 1: ORKESTRASI                         │
│                     LangGraph (18 node, 4 tahap)                    │
│                                                                     │
│  Repo Context → Coverage Inference → Pipeline Generation → Eval     │
│       │                │                    │               │       │
│       ▼                ▼                    ▼               ▼       │
│  Tech/Arch/      15 Coverage          GitHub Actions     Findings   │
│  Domain/Deploy   Detection           Workflow YAML      + Score     │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LAPISAN 2: EKSEKUSI CI/CD                         │
│                GitHub Actions Workflow (generated YAML)              │
│                                                                     │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ lint │→ │ test │→ │build │→ │secret-scan   │→ │container-scan │ │
│  │ESLint│  │ Jest │  │ npm  │  │  Gitleaks     │  │    Trivy      │ │
│  └──────┘  └──────┘  └──────┘  └──────────────┘  └───────────────┘ │
│                                     │                                │
│                          ┌──────────┴──────────┐                    │
│                          ▼                     ▼                    │
│                    ┌──────────┐          ┌──────────┐               │
│                    │   sast   │          │ dep-scan │               │
│                    │ Semgrep  │          │npm audit │               │
│                    │ (+CodeQL)│          │pip-audit │               │
│                    └──────────┘          └──────────┘               │
│                          │                     │                    │
│                          └──────────┬──────────┘                    │
│                                     ▼                                │
│                         ┌────────────────────┐                      │
│                         │  domain-stage      │ (opsional)            │
│                         │ pci-dss / hipaa    │                      │
│                         └────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 LAPISAN 3: ANALISIS & KORELASI                        │
│              Security Finding Normalizer + Domain Priority           │
│                                                                     │
│  SARIF ─┐                                                            │
│  Trivy ─┤                                                            │
│  npm   ─┼──→ _map_to_owasp() ──→ OWASP L×I scoring ──→ severity    │
│  GitL  ─┤       (unified format)       +                            │
│  Semg  ─┘                        domain_priority (elevasi severity) │
│                                       │                              │
│                                       ▼                              │
│                          ┌──────────────────────┐                   │
│                          │ _TYPE_TO_COVERAGE()  │                    │
│                          │ finding → coverage   │                    │
│                          │ (95+ keyword maps)   │                    │
│                          └──────────────────────┘                   │
│                                       │                              │
│                                       ▼                              │
│                          ┌──────────────────────┐                   │
│                          │ scoring + PDF report │                    │
│                          │ compliance_mapper    │                    │
│                          └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Alur Data (End-to-End)

```
1. REPO CONTEXT EXTRACTION (Tahap 1, 6 node)
   ┌──────────────────────────────────────────────────┐
   │ GitHub API → clone repo → scan file tree         │
   │   ├── package.json / requirements.txt → tech     │
   │   ├── folder structure → architecture            │
   │   ├── Dockerfile / docker-compose → deployment   │
   │   └── entities/routes/libraries → domain         │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
2. COVERAGE INFERENCE (Tahap 2, 2 node)
   ┌──────────────────────────────────────────────────┐
   │ COVERAGE_LIBRARY heuristik:                       │
   │   libraries match (w=3.0) + entities (w=2.0)     │
   │   + routes (w=1.5) → coverage score 0-1          │
   │                                                   │
   │ LLM re-scores dengan konteks penuh:              │
   │   architecture + deployment + domain + features   │
   │                                                   │
   │ Output: security_coverages[]                      │
   │   [{id: "payment_security", applicable: true}]    │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
3. PIPELINE AUGMENTATION (Tahap 2, 1 node)
   ┌──────────────────────────────────────────────────┐
   │ DEFAULT_AUGMENTATIONS lookup per coverage:        │
   │                                                   │
   │   payment_security → sast(pci-dss.yml)            │
   │                     + secret_scan(stripe/midtrans)│
   │   container_security → container_scan(Trivy)      │
   │   api_security → sast(owasp-api.yml)              │
   │   ...                                            │
   │                                                   │
   │ Output: pipeline_augmentations[]                   │
   │   [{coverage, job, configuration, reason}]        │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
4. WORKFLOW GENERATION (Tahap 3, 5 node — deterministik)
   ┌──────────────────────────────────────────────────┐
   │ _build_workflow_yaml():                           │
   │                                                   │
   │   8 STANDARD JOBS (selalu ada):                   │
   │     lint → test → build → sast → dep-scan         │
   │     → secret-scan → container-build → container-scan│
   │                                                   │
   │   + DOMAIN JOBS (dari augmentations):             │
   │     pci-dss | hipaa | ledger-check                │
   │     | csp-headers | mqtt-security                 │
   │                                                   │
   │   + PER-JOB CONFIG (dari augmentations):          │
   │     sast.run: semgrep --config=p/owasp-top-ten    │
   │     sast.run: semgrep --config=owasp-api.yml      │
   │     secret-scan.run: gitleaks detect --no-git     │
   │     container-scan.run: trivy image $IMAGE        │
   │     dep-scan.run: npm audit --json                │
   │                                                   │
   │ Output: .github/workflows/security-pipeline.yml   │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
5. EXECUTION (GitHub Actions)
   ┌──────────────────────────────────────────────────┐
   │ Parallel execution:                               │
   │   lint + test + build                             │
   │        │                                          │
   │        ▼ (after build success)                    │
   │   sast ‖ secret-scan ‖ dep-scan ‖ container-scan  │
   │        │                                          │
   │        ▼                                          │
   │   domain-stage (conditional)                      │
   │                                                   │
   │ Each job → produces artifact (SARIF/JSON)         │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
6. FINDING NORMALIZATION (Tahap 4, 1 node + LLM)
   ┌──────────────────────────────────────────────────┐
   │ security_finding_normalizer.py:                   │
   │                                                   │
   │   Input: multiple output formats                  │
   │     Semgrep → JSON (rule-id + message + location) │
   │     Trivy  → JSON (VulnerabilityID + Severity)    │
   │     npm    → JSON (advisory + severity)           │
   │     Gitleaks → JSON (rule + secret + location)    │
   │     CodeQL → SARIF                               │
   │                                                   │
   │   _normalize_semgrep_finding()                    │
   │   _normalize_trivy_finding()                      │
   │   _normalize_npm_finding()                        │
   │   _normalize_gitleaks_finding()                   │
   │                                                   │
   │   Output: unified Finding[]                       │
   │     {type, severity, file, line, description,     │
   │      OWASP_category, security_coverage}           │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
7. SCORING & REPORT (Tahap 4, 2 node)
   ┌──────────────────────────────────────────────────┐
   │ _TYPE_TO_COVERAGE(finding.type) → coverage_id     │
   │ _OWASP_LI_MAP(finding.type) → likelihood × impact │
   │ DOMAIN_PRIORITY_RULES(domain) → severity boost    │
   │                                                   │
   │ compliance_mapper:                                │
   │   covered_ISA = deduplicate(all_finding.coverage) │
   │   score = Σ(covered × weight) / Σ(total × weight) │
   │                                                   │
   │ Output: PDF report (5 sections)                   │
   └──────────────────────────────────────────────────┘
```

### 9.3 Kunci Penjahitan: Security Finding Normalizer

File: `ai-service/app/agents/security_finding_normalizer.py`

Normalizer adalah **jembatan kritis** yang mengubah output heterogen dari 5+ tools menjadi format seragam:

| Aspek | Tanpa Normalizer | Dengan Normalizer |
|-------|-----------------|-------------------|
| Semgrep output | `check_id: "python.lang.security..."` | `type: "sql_injection"` |
| Trivy output | `VulnerabilityID: "CVE-2023-..."` | `type: "cve_dependency"` |
| Gitleaks output | `rule: "aws-access-key"` | `type: "hardcoded_secret"` |
| npm output | `advisory: "GHSA-xxxx-xxxx"` | `type: "cve_dependency"` |
| Severity | Beragam skala (LOW/MEDIUM/HIGH/CRITICAL vs 1-10) | Seragam: `low/medium/high/critical` |
| OWASP mapping | Tidak ada | `OWASP_category: "A03:2021-Injection"` |
| Coverage mapping | Tidak ada | `security_coverage: "data_security"` |

### 9.4 Kunci Penjahitan: Domain Priority

File: `ai-service/app/agents/domain_priority.py`

Setelah normalisasi, setiap finding melewati `DOMAIN_PRIORITY_RULES` — rules berbasis keyword + file pattern yang meng-elevasi severity berdasarkan domain:

```
Contoh:
  Finding: "sql_injection" pada file checkout.js
  Domain: e-commerce
  Match: high_keywords["sql[_ ]?injection"] + file_patterns["checkout"]
  Hasil: severity LOW → severity HIGH (elevated)
         metadata: {severity_boost: "+2", reason: "e-commerce: sql_injection in checkout"}
```

Ini memastikan **finding yang sama** mendapat **perlakuan berbeda** di domain berbeda (e-commerce vs blog vs healthcare).

### 9.5 Contoh Konkrit: E-Commerce Pipeline

Repo: `iqbalrsyd/eccomerce-monolith-vuln`

```
INPUT:
  package.json → express, stripe, mysql2, jsonwebtoken, bcrypt
  Dockerfile  → node:18, EXPOSE 3000
  Routes      → /api/products, /checkout, /payment, /login
  Entities    → product, order, user, cart, transaction

TAHAP 2 — Coverage Inference:
  ✓ authentication_security (lib: jsonwebtoken, bcrypt; route: /login)
  ✓ api_security (lib: express; route: /api/products)
  ✓ data_security (lib: mysql2)
  ✓ payment_security (lib: stripe; route: /checkout, /payment)
  ✓ container_security (Dockerfile)
  ✗ iot_security, healthcare_security, fintech_security, ...

TAHAP 2 — Pipeline Augmentation:
  authentication → sast(p/secrets) + secret_scan(JWT/OAuth)
  api           → sast(owasp-api.yml)
  data          → sast(p/sql-injection) + sca(DB driver CVE)
  payment       → sast(pci-dss.yml) + secret_scan(stripe)
  container     → container_scan(Trivy image + Dockerfile)

TAHAP 3 — Generated YAML (.github/workflows/security-pipeline.yml):
  jobs:
    - lint       (ESLint)
    - test       (Jest)
    - build      (npm run build)
    - sast       (Semgrep: p/secrets + owasp-api.yml + p/sql-injection + pci-dss.yml)
    - dep-scan   (npm audit)
    - secret-scan (Gitleaks: detect --no-git)
    - container-scan (Trivy: image scan + Dockerfile lint)
    - pci-dss    (Semgrep: pci-dss.yml + ecommerce.yml)

TAHAP 4 — Evaluation:
  Findings: 23 (5 sast + 8 secret + 4 dep + 2 container + 4 pci-dss)
  Score: 78% (12 dari 15 ISA yg applicable di-cover oleh pipeline)
```

---

## 10. Ringkasan: ISA → Tools → Pipeline (Quick Reference)

| ISA Domain | Tools | v9 Job | Output ke Normalizer | Evidence yg Dihasilkan |
|-----------|-------|--------|---------------------|----------------------|
| IAM (16 ISA) | Semgrep + Gitleaks | `sast`, `secret-scan` | hardcoded_credentials, jwt_exposure | Daftar credential yg bocor (ISA 47, 51, 55) |
| API (4 ISA) | Semgrep + ZAP | `sast` | sql_injection, xss, insecure_auth | API scan report (ISA 36, 72) |
| Data (8 ISA) | Semgrep + Trivy + npm/pip | `sast`, `sca` | sql_injection, cve_dependency, misconfig | Dependency CVE list + encryption check (ISA 45-46) |
| Payment (0 ISA) | Semgrep (pci-dss) | `sast`, `secret-scan` | credit_card_leak, pii_exposure | PCI-DSS scan report |
| Container (8 ISA) | Trivy | `container-scan` | cve_dependency, docker_misconfig | Container scan report (ISA 13-14) |
| IoT (3 ISA) | Semgrep (iot-mqtt) | `sast`, `secret-scan` | mqtt_misconfig, device_creds | IoT security report (ISA 32) |
| Logging (5 ISA) | Semgrep (log-forging) | `sast` | sensitive_data_in_logs | Log security report (ISA 19-22) |
| File Upload (0) | Semgrep | `sast` | path_traversal, file_upload_bypass | File upload scan report |
| Healthcare (0) | Semgrep (hipaa) | `sast` | phi_exposure, fhir_misconfig | HIPAA compliance report |
| Fintech (0) | Semgrep (fintech-ledger) | `sast` | ledger_tamper, kyc_bypass | Fintech security report |
| CMS (0) | Semgrep (blog-csp) | `sast` | xss, content_injection | CMS security report |
| Education (0) | Semgrep (edu-lms) | `sast` | grade_tamper, enrollment_bypass | Education security report |
| Microservice (7) | docker-compose validate | `validate` | misconfig, network_policy_violation | Network config report (ISA 25-31) |
| CSP (1) | Semgrep (csp-header) | `sast` | missing_csp, weak_headers | CSP header report (ISA 17) |
| Dependency (4) | npm/pip/go audit | `sca` | cve_dependency | Dependency audit report (ISA 03-04, 06, 09) |

> **Catatan**: Tools yang menghasilkan output SARIF (Semgrep, Trivy) langsung bisa di-upload ke GitHub Security tab sebagai code scanning alerts — memberikan visibilitas tambahan di luar pipeline.

---

## 11. Perluasan Coverage ISA via Context-Aware IaC + Cloud Scanning

### 11.1 Gap Saat Ini

Dari 72 ISA, **14 kontrol** saat ini tidak ter-cover oleh pipeline aplikasi (hanya scan kode + secret + container):

| ISA | Kenapa Belum Ter-cover | Berpotensi Ter-cover Jika... |
|-----|------------------------|------------------------------|
| ISA 01-02 | CMDB — tidak ada di kode | Repo punya file inventori (`inventory.ini`, `hosts.yml`, `terraform.tfvars`) |
| ISA 08 | Continuous Vuln Mgmt — proses | Repo mengkonfigurasi Dependabot / Renovate / scheduled scan |
| ISA 10 | Vuln Scan Frequency — bukti eksternal | Repo punya cron schedule untuk security scan |
| ISA 18 | NTP Synchronization — konfigurasi infra | Repo punya Terraform/Ansible yg konfigurasi NTP |
| ISA 25 | Port/Protocol Approval — port scan report | Repo punya security group / firewall rule definition |
| ISA 26-27 | Firewall Change Mgmt + Review | Repo punya Terraform firewall rules |
| ISA 29 | Remote Access (VPN/ZPA) — konfigurasi network | Repo punya IaC untuk VPN/bastion |
| ISA 31 | IDS/IPS — konfigurasi enterprise | Repo punya Falco rules / Suricata config |
| ISA 33 | Automated Backup — konfigurasi SC/DR | Repo punya Terraform backup policy |
| ISA 34 | Backup Restore Test — RTO/RPO docs | Repo punya DR test script / runbook |
| ISA 43 | Mobile Device Encryption (Intune) — MDM | Repo punya MDM enrollment config |
| ISA 44 | External Storage Encryption (BitLocker) — endpoint | Repo punya GPO / device config |
| ISA 58 | Test Data Sanitization — policy docs | Repo punya data anonymization script/config |
| ISA 68 | Standardized Builds — golden image | Repo punya Packer template / Dockerfile base image |

### 11.2 Strategi: Coverage Inference Level 2 (IaC)

Ide: **Perluas `coverage_inference_node`** untuk mendeteksi file-file infrastruktur di repo dan menambah coverage types baru:

```
COVERAGE_LIBRARY.extend({
    "iac_security": {
        "description": "Terraform, CloudFormation, Pulumi, Ansible security",
        "files": ["*.tf", "*.tfvars", "*.tfstate", "*.hcl",
                  "cloudformation/*.yaml", "cloudformation/*.json",
                  "Pulumi.yaml", "*.pulumi.yaml",
                  "ansible/*.yml", "playbook*.yml"],
        "tools": ["checkov", "tfsec", "kics"],
    },
    "kubernetes_security": {
        "description": "K8s manifest, Helm chart, pod security",
        "files": ["deployment*.yaml", "service*.yaml", "ingress*.yaml",
                  "kustomization.yaml", "Chart.yaml", "values.yaml"],
        "tools": ["kubeaudit", "kube-bench", "checkov"],
    },
    "cloud_security": {
        "description": "AWS/GCP/Azure resource misconfig",
        "files": ["*.tf", "*.tfvars", "cloudformation/*.yaml",
                  "serverless.yml", "app.yaml", ".github/workflows/*.yml"],
        "tools": ["checkov", "prowler", "scoutsuite"],
    },
    "pipeline_security": {
        "description": "GitHub Actions / CI misconfig, injection",
        "files": [".github/workflows/*.yml", ".github/workflows/*.yaml",
                  ".gitlab-ci.yml", "Jenkinsfile"],
        "tools": ["zizmor", "checkov", "actionlint"],
    },
    "supply_chain_security": {
        "description": "SBOM, signed commits, provenance",
        "files": ["*.sbom.json", "*.sbom.xml", "cosign.*"],
        "tools": ["cosign", "syft", "slsa-verifier"],
    },
})
```

### 11.3 Tools Tambahan & Deteksinya dari Repo

| Tool | Lisensi | File Trigger di Repo | Apa yg Dicek | ISA yg Ter-cover | Output |
|------|---------|---------------------|-------------|-----------------|--------|
| **Checkov** | Apache-2.0 | `*.tf`, `*.yaml`, `Dockerfile`, `*.json` (CF), `.github/workflows/*.yml` | 750+ policy: S3 public, SG open, KMS rotation, CloudTrail enabled, K8s privileged pod, Dockerfile USER root, GH Actions injection | ISA 13, 14, 15, 25, 26, 28, 29, 31, 33, 44, 45, 46, 68 | JSON / SARIF / JUnit |
| **tfsec** | MIT | `*.tf` | AWS/Azure/GCP specific: security group rules, IAM overprivileged, S3 bucket ACL, GCP firewall, Azure storage network | ISA 13, 17, 25, 26, 27 | JSON / SARIF |
| **KICS** (Checkmarx) | Apache-2.0 | `*.tf`, `*.yaml`, `Dockerfile`, `ansible/` | 2000+ queries: Terraform, K8s, Docker, Ansible, CloudFormation, Pulumi, Crossplane | ISA 13-17, 25-31, 68 | JSON / SARIF |
| **kubeaudit** | MIT | `*deployment*.yaml`, `*pod*.yaml`, `Chart.yaml` | privileged=false, readOnlyRootFilesystem, runAsNonRoot, drop capabilities, automountServiceAccountToken, image tag `latest` | ISA 13, 14, 15, 47, 69, 70 | JSON |
| **OPA/Conftest** | Apache-2.0 | any `.yaml`, `.json`, `.tf`, `Dockerfile` | Custom Rego policies — bisa validasi apa saja (NTP config, backup policy, encryption, label compliance) | ISA 13-18, 33, 44, 45, 46, 68 | JSON / TAP |
| **Hadolint** | GPL-3.0 | `Dockerfile`, `*.dockerfile` | Dockerfile best practices: pin version tag, no `latest`, USER not root, COPY > ADD, no `apk upgrade`, HEALTHCHECK, pipefail | ISA 13, 14, 68 | JSON / SARIF |
| **Zizmor** | MIT | `.github/workflows/*.yml` | GitHub Actions security: script injection, template expansion, hardcoded credentials in workflow, unprotected workflows, overly permissive `GITHUB_TOKEN` | ISA 47, 55, 57, 62 | JSON / SARIF |
| **trivy config** | Apache-2.0 | `*.tf`, `*.yaml`, `Dockerfile`, `*.json` | Built-in misconfig scanning (already in stack — just use `trivy config` subcommand) | ISA 13, 14, 25, 45, 46, 68 | JSON / SARIF |
| **cosign** | Apache-2.0 | `*.sig`, `*.pem`, `cosign.pub` | Verify container image signatures, verify SLSA provenance | ISA 57, 68 | JSON / text |
| **syft / grype** | Apache-2.0 | `*.sbom.*`, image | Generate SBOM + scan for CVEs (alternative to Trivy, lebih detail di SBOM) | ISA 03, 04, 06, 09 | JSON / CycloneDX / SPDX |

### 11.4 Berapa ISA yg Bisa Diperluas?

```
SEBELUM (app-only pipeline):               58 ISA (81%)
                                     + IaC   +8 ISA
                                     + K8s   +4 ISA
                                     + Cloud +5 ISA
                                     + CI    +3 ISA
                                     ─────────────
SESUDAH (context-aware full stack):         ~68 ISA (94%)
```

Perluasan coverage:

| ISA | Awal | Tools Baru | Apa yg Dicek |
|-----|------|-----------|-------------|
| ISA 18 (NTP) | ❌ manual | Checkov + Conftest | Repo punya `ntp` resource di Terraform → validasi konfigurasi NTP server |
| ISA 25 (Ports) | ✓ (legacy: microservice) | Checkov + tfsec | Security group rules, exposed ports, ingress 0.0.0.0/0 |
| ISA 26-27 (Firewall) | ✓ (legacy: microservice) | Checkov + KICS | Terraform firewall rules validation, change tracking via git diff |
| ISA 29 (Remote Access) | ❌ manual | Checkov | VPN gateway config, bastion host, SSH open to world |
| ISA 31 (IDS/IPS) | ✓ (legacy: microservice) | Checkov | GuardDuty/CloudTrail enabled, VPC flow logs, Suricata/Falco config |
| ISA 33 (Backup) | ✓ (data basic) | Checkov + Conftest | RDS backup enabled, backup retention period, cross-region backup, backup vault locked |
| ISA 34 (RTO/RPO) | ✓ (data) | Conftest | Custom policy: backup retention >= N days, RPO config exists |
| ISA 44 (Ext Storage) | ❌ manual | Checkov | EBS volume encryption, S3 default encryption |
| ISA 47 (Admin) | ✓ (IAM auth) | Checkov + Zizmor | IAM overprivileged (admin:*), GH Actions token permission |
| ISA 57 (SDLC) | ✓ (API) | Zizmor + cosign | GH workflow injection, unsigned commits, missing branch protection |
| ISA 58 (Test Data) | ✓ (data) | *(static)* | Cek apakah ada data sanitization script + anonimisasi config |
| ISA 68 (Builds) | ✓ (container) | Hadolint + cosign | Dockerfile best practice + image signature verification |
| ISA 69-70 (Hardening) | ✓ (auth) | kubeaudit + Checkov | K8s: runAsNonRoot, default account renamed; Terraform: default ports changed |

### 11.5 Deteksi Konteks: File → Coverage → Tool

Cara kerja di `coverage_inference_node` (perluasan):

```python
# Current (v9) — hanya detection library/entity/route
COVERAGE_LIBRARY = {
    "authentication_security": {
        "libraries": ["passport", "jsonwebtoken", ...],
        "entities": ["user", "session", ...],
        "routes": ["/login", "/signup", ...],
    },
    # ... 14 lainnya
}

# PERLUASAN: detection file pattern di repo
FILE_COVERAGE_MAP = {
    "*.tf":                           ["iac_security", "cloud_security"],
    "*.tfvars":                       ["iac_security"],
    "cloudformation/*.{yaml,json}":   ["iac_security", "cloud_security"],
    "deployment*.yaml":               ["kubernetes_security"],
    "Chart.yaml":                     ["kubernetes_security"],
    ".github/workflows/*.yml":        ["pipeline_security", "cloud_security"],
    "ansible/":                       ["iac_security"],
    "Pulumi.yaml":                    ["iac_security", "cloud_security"],
    "serverless.yml":                 ["cloud_security"],
}
```

> Cara kerja: `repository_scan_node` sudah membaca file tree repo (lihat `_get_repo_tree` di `pipeline_service.py`). Tree ini tinggal di-`glob` pakai `FILE_COVERAGE_MAP` → menghasilkan `security_coverages[]` tambahan tanpa LLM call baru (deterministik, 0 biaya).

### 11.6 Contoh: Repo dg Terraform + K8s

```
INPUT (dari repository_scan):
  File tree:
    terraform/
      main.tf          ← aws_db_instance, aws_security_group
      variables.tf
      outputs.tf
    kubernetes/
      deployment.yaml  ← containers: api, db
      service.yaml
      ingress.yaml
    Dockerfile
    .github/workflows/
      ci.yml
    package.json        ← express, pg

HEURISTIC DETECTION (deterministik, dari FILE_COVERAGE_MAP):
  *.tf                          → +iac_security, +cloud_security
  deployment*.yaml              → +kubernetes_security
  Dockerfile                    → +container_security (existing)
  .github/workflows/*.yml       → +pipeline_security

LLM COVERAGE INFERENCE (existing, dari libraries/entities/routes):
  express + pg                  → api_security, data_security

TOTAL COVERAGES: 7
  1. api_security             (LLM: express)
  2. data_security            (LLM: pg)
  3. container_security        (existing: Dockerfile)
  4. iac_security             (NEW: *.tf)
  5. cloud_security           (NEW: *.tf)
  6. kubernetes_security      (NEW: deployment.yaml)
  7. pipeline_security        (NEW: .github/workflows/*.yml)

ISA SCORE SEBELUM:  ~5/15 ISA ter-cover  = 33%
ISA SCORE SESUDAH:  ~12/15 ISA ter-cover = 80%
```

### 11.7 Arsitektur Penambahan di Node

```
Tahap 1 (EXISTING, no change):
  repo_scan → file_tree (sudah ada di state)

Tahap 2 — coverage_inference (DITAMBAH):
  ┌──────────────────────────────────────────────────┐
  │ Step 1 (DETERMINISTIK — baru, no LLM):           │
  │   file_tree → glob(FILE_COVERAGE_MAP)             │
  │   → iac_coverages[]                               │
  │                                                   │
  │ Step 2 (EXISTING, LLM):                           │
  │   libraries + entities + routes                   │
  │   + architecture + deployment + domain            │
  │   → app_coverages[]                               │
  │                                                   │
  │ Step 3 (MERGE):                                   │
  │   security_coverages = iac_coverages              │
  │                       + app_coverages             │
  │                       (deduplicate by id)         │
  └──────────────────────────────────────────────────┘

Tahap 2 — pipeline_augmentation (DITAMBAH):
  ┌──────────────────────────────────────────────────┐
  │ DEFAULT_AUGMENTATIONS.extend({                    │
  │   "iac_security": {                               │
  │     "jobs": ["iac-scan"],                         │
  │     "config": {                                   │
  │       "checkov": "checkov -d . --framework terraform --output sarif",│
  │       "conftest": "conftest test --policy iac/policies/",             │
  │     }                                            │
  │   },                                              │
  │   "kubernetes_security": {                        │
  │     "jobs": ["k8s-scan"],                         │
  │     "config": {                                   │
  │       "kubeaudit": "kubeaudit all -f kubernetes/",│
  │     }                                             │
  │   },                                              │
  │   "cloud_security": {                             │
  │     "jobs": ["cloud-scan"],                       │
  │     "config": {                                   │
  │       "checkov": "checkov -d . --framework cloudformation --output sarif",│
  │     }                                             │
  │   },                                              │
  │   "pipeline_security": {                          │
  │     "jobs": ["zizmor"],                           │
  │     "config": {                                   │
  │       "zizmor": "zizmor --format sarif .",       │
  │     }                                             │
  │   },                                              │
  │ })                                                │
  └──────────────────────────────────────────────────┘
```

---

## 12. Final: Potensi ISA Coverage Score

```
                            ┌─────────────────────┐
  App Code Scanning (Sekarang) │  ████████████████  │ 58 ISA (81%)  Semgrep + Gitleaks + Trivy + npm/pip
                            │  ████████████████  │
  + IaC Scanning (Baru)       │  ███████          │ +8 ISA (92%)  Checkov + tfsec + KICS
  + K8s Scanning (Baru)       │  ███             │ +4 ISA (97%)  kubeaudit + OPA
  + CI Pipeline (Baru)        │  ██             │ +3 ISA (100%) Zizmor
                            └─────────────────────┘
                            Catatan: ~3-5 ISA tetap manual
                            (training, pentest bukti eksternal)

COST ADDITION (tools tambahan):
  Checkov     = 0  (open source, no license cost)
  tfsec       = 0  (open source)
  kubeaudit   = 0  (open source)
  zizmor      = 0  (open source)
  OPA/Conftest= 0  (open source)
  ─────────────────────────────
  Total       = $0 (semua free + open source)

EXECUTION TIME ADDITION:
  App scan (Semgrep + Gitleaks + Trivy + npm) = ~3-5 menit
  IaC scan (Checkov + tfsec)                  = ~30 detik (hanya file .tf/.yaml)
  K8s scan (kubeaudit)                        = ~10 detik
  CI scan (zizmor)                            = ~5 detik
  ─────────────────────────────────────────────
  Total add                                   = <1 menit
```

> **Kesimpulan**: Dengan biaya **$0** dan tambahan waktu **<1 menit**, pipeline bisa naik dari **81% → 94% ISA coverage** dengan mendeteksi file IaC/K8s/CI di repo secara deterministik — tanpa tambahan LLM call.
