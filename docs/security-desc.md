# Security Controls Reference

> **Tujuan:** Referensi lengkap semua security control yang dikenal AI agent
> (K1 = Security Requirement Inference + K2 = Workflow Generator). Dokumen ini
> menjelaskan **apa** setiap control, **mengapa** di-include/eksklusi untuk
> konteks repositori tertentu, dan **tools** apa yang dipakai untuk
> mengeksekusinya di pipeline.

---

## 1. Definisi Istilah

| Istilah | Arti |
|---|---|
| **Security control** | Nama logis untuk kategori deteksi keamanan (mis. `sast`, `container_scan`). BUKAN tools, tapi kategori. |
| **Pipeline stage** | Job di GitHub Actions yang menjalankan satu atau beberapa tools untuk satu security control. |
| **Context-aware** | Keputusan include/exclude berdasarkan **bukti di repo** (file evidence), bukan asumsi. |
| **File evidence** | File/konten yang terdeteksi via `repository_structure` atau `repository_files` (SSoT — single source of truth). |
| **Inferred flag** | Output LLM/inference yang **advisory** saja. Bisa stale/tidak akurat, tidak override file evidence. |

Prinsip utama generator:

> **File evidence > Inferred flag.** Kalau tidak ada file pendukung, stage di-drop
> dan masuk `invalid_workflow_stages` untuk transparansi ke reviewer/UI.

---

## 2. Decision Flow Umum

```
repository context (technologies + deployment + structure + files)
  │
  ▼
attack surface identification (deterministic lookup)
  │
  ▼
mandatory controls (minimum coverage guarantee)
  │
  ▼
LLM refinement (status: recommended / optional / not_required)
  │
  ▼
workflow generator filtering (file evidence validation)
  │
  ├─► generated_workflow_stages (yang akan di-emit ke YAML)
  └─► invalid_workflow_stages (yang diminta tapi tidak punya evidence)
```

---

## 3. Daftar Lengkap Security Controls

### 3.1. `lint` — Code Quality & Style

| Properti | Nilai |
|---|---|
| **Tujuan** | Menjaga konsistensi style, mendeteksi unused vars/imports, missing returns, dsb. |
| **Tools (auto)** | ESLint (JS/TS), Ruff (Python), `go vet` (Go), golangci-lint (Go), clippy (Rust) |
| **Input** | `*.js`, `*.ts`, `*.py`, `*.go`, `*.rs` |
| **Output** | Lint report (text/JSON). Bisa fail PR jika ada error-level issues. |
| **Default status** | Selalu `recommended`. |
| **Kapan di-drop** | Tidak pernah. Wajib untuk semua codebase. |
| **Mapping domain** | Universal. Semua domain butuh code quality. |

**Konteks `eccomerce-monolith-vuln`:** ESLint untuk JavaScript. Menangkap `import unused`, `var not defined`, dsb.

---

### 3.2. `test` — Unit Testing

| Properti | Nilai |
|---|---|
| **Tujuan** | Validasi fungsionalitas, jalankan test suite, hitung code coverage. |
| **Tools (auto)** | Jest (JS/TS), pytest (Python), `go test` (Go), `npm test` |
| **Input** | `*.test.js`, `*.spec.ts`, `tests/`, `__tests__/` |
| **Output** | Test pass/fail count, coverage % (lines/branches/functions). |
| **Default status** | `recommended` jika test framework terdeteksi. |
| **Kapan di-drop** | Tidak ada test framework di `package.json` / `pyproject.toml` / `go.mod`. |
| **Mapping domain** | Universal. Coverage % jadi signal code health. |

**Konteks `eccomerce-monolith-vuln`:** Jest detected. Output: `coverage/` artifact, badge di PR.

---

### 3.3. `build` — Compilation / Bundle

| Properti | Nilai |
|---|---|
| **Tujuan** | Verifikasi kode bisa di-compile/bundle. Cegah broken commit. |
| **Tools (auto)** | `npm run build`, Webpack, Vite, esbuild, tsc, `go build` |
| **Input** | `package.json` scripts, `tsconfig.json` |
| **Output** | Build artifact (`dist/`, `build/`) atau error log. |
| **Default status** | `recommended` jika build tool terdeteksi. |
| **Kapan di-drop** | Tidak ada `build` script di `package.json` / tidak ada `tsconfig.json`. |
| **Mapping domain** | Universal untuk compiled languages; opsional untuk interpreted. |

**Konteks `eccomerce-monolith-vuln`:** `npm run build` jika ada di `package.json` scripts. Else skip.

---

### 3.4. `sast` — Static Application Security Testing

| Properti | Nilai |
|---|---|
| **Tujuan** | Cari kerentanan di source code: SQLi, XSS, hardcoded secrets, weak crypto, insecure deserialization, command injection, path traversal. |
| **Tools** | Semgrep (default). Rule sets: `p/owasp-top-ten`, `p/javascript`, `p/nodejs`, `p/expressjs`, `p/sql-injection`, `p/secrets`, `p/dockerfile`. |
| **Input** | Source code + Dockerfile + YAML. |
| **Output** | SARIF file → uploaded ke GitHub Code Scanning tab. Alert per file:line dengan rule ID + CWE link. |
| **Default status** | Selalu `recommended`. |
| **Kapan di-drop** | Tidak pernah untuk production code. |
| **Mapping domain** | **WAJIB** untuk semua domain. Prioritas untuk e-commerce (SQLi, XSS, broken auth), finance (input validation), healthcare (data leak). |

**Konteks `eccomerce-monolith-vuln`:** Semgrep dengan 7 rule sets. Ditemukan:
- `Dockerfile:12` — `USER root` di akhir
- `src/routes/auth.js:33` — `jwt.sign(..., JWT_SECRET)` hardcoded

**Catatan SAST ruleset:**

| Rule | Mendeteksi |
|---|---|
| `p/owasp-top-ten` | Top 10 OWASP (broad) |
| `p/javascript` | JS-specific (XSS via `innerHTML`, prototype pollution) |
| `p/nodejs` | Node-specific (child_process, eval, fs traversal) |
| `p/expressjs` | Express-specific (missing CORS, no rate limit, cookie httpOnly) |
| `p/sql-injection` | SQL string concat, raw query |
| `p/secrets` | API keys, tokens, private keys di source |
| `p/dockerfile` | USER root, missing USER, ADD vs COPY, latest tag, dsb. |

---

### 3.5. `dependency-scan` — Dependency Vulnerability Scan

| Properti | Nilai |
|---|---|
| **Tujuan** | Cek CVE di third-party packages. Contoh: lodash 4.17.4 (CVE-2019-10744 prototype pollution), express 4.16.0 (multiple CVEs). |
| **Tools** | `npm audit` (JS), `pip-audit` (Python), `govulncheck` (Go), Trivy filesystem scan (cross-language) |
| **Input** | `package-lock.json`, `requirements.txt`, `go.sum`, `Cargo.lock` |
| **Output** | `npm audit` JSON + SARIF (Trivy) → Code Scanning tab. |
| **Default status** | `recommended` jika package manager terdeteksi. |
| **Kapan di-drop** | Tidak ada package manager / tidak ada lockfile. |
| **Mapping domain** | **WAJIB** untuk semua domain. CVE di dependency = attack surface utama. |

**Konteks `eccomerce-monolith-vuln`:** `npm audit --audit-level=high` + Trivy fs scan. Vulnerable deps:
- `lodash@4.17.4` (prototype pollution, regex DoS)
- `express@4.16.0` (open redirect, XSS via res.redirect)

---

### 3.6. `cve_scan` — CVE Database Lookup

| Properti | Nilai |
|---|---|
| **Tujuan** | Hard check terhadap CVE database (NVD, GHSA). Lebih strict dari `dependency-scan`. |
| **Tools** | `npm audit --audit-level=critical`, `pip-audit`, `govulncheck`, Trivy dengan NVD feed |
| **Input** | Lockfiles. |
| **Output** | Critical-only CVE list. SARIF + `npm audit` JSON. |
| **Default status** | `recommended` jika package manager ada. Sering di-merge ke `dependency-scan` job. |
| **Kapan di-drop** | Sama seperti `dependency-scan`. |
| **Mapping domain** | Domain tinggi-regulasi (finance, healthcare, gov) butuh critical-only. |

**Konteks `eccomerce-monolith-vuln`:** Digabung ke `dependency-scan` job untuk efisiensi.

---

### 3.7. `secret_scan` — Hardcoded Credentials

| Properti | Nilai |
|---|---|
| **Tujuan** | Cari API key, JWT secret, password, AWS/GCP credentials, Stripe key, dsb yang tertinggal di source code atau git history. |
| **Tools** | Gitleaks (default), TruffleHog, GitGuardian |
| **Input** | Git history (full) + source code. |
| **Output** | SARIF jika ada finding. **FAIL PR** jika ada secret aktif. |
| **Default status** | Selalu `recommended`. |
| **Kapan di-drop** | Tidak pernah untuk production code. |
| **Mapping domain** | **WAJIB** untuk semua domain. Compliance (SOC2, PCI-DSS) wajib detect. |

**Konteks `eccomerce-monolith-vuln`:** Gitleaks dengan `fetch-depth: 0` (full history). Ditemukan:
- `JWT_SECRET=...` di `.env`
- Stripe API key di source code

---

### 3.8. `container_build` — Container Image Build

| Properti | Nilai |
|---|---|
| **Tujuan** | Build image untuk di-scan. Syarat untuk `container_scan`. |
| **Tools** | Docker Buildx, `docker build` |
| **Input** | `Dockerfile` + context dir. |
| **Output** | Docker image (ephemeral di runner). |
| **Default status** | `recommended` jika Dockerfile terdeteksi. |
| **Kapan di-drop** | Tidak ada `Dockerfile*` atau `docker-compose.*` di root. |
| **Mapping domain** | Microservices, e-commerce, SaaS — semua containerized. |

**Konteks `eccomerce-monolith-vuln`:** `docker build -t app:latest .` (Dockerfile ada).

---

### 3.9. `container_scan` — Container Image Vulnerability Scan

| Properti | Nilai |
|---|---|
| **Tujuan** | Scan OS packages + application libs di dalam image. Bedanya dengan `dependency-scan`: ini **runtime** libs (image layer), bukan source. |
| **Tools** | Trivy (image mode), Grype, Snyk Container |
| **Input** | Built Docker image. |
| **Output** | SARIF → Code Scanning tab. CVE per OS package + library. |
| **Default status** | `recommended` jika `container_build` ada. |
| **Kapan di-drop** | Tidak ada Dockerfile (lihat `_has_dockerfile()`). |
| **Mapping domain** | **WAJIB** untuk semua containerized deployment. |

**Konteks `eccomerce-monolith-vuln`:** Trivy image scan OS + npm packages inside image. Hasil bisa berbeda dari `dependency-scan` (image punya base OS Ubuntu/Alpine yang juga rentan).

---

### 3.10. `sbom` — Software Bill of Materials

| Properti | Nilai |
|---|---|
| **Tujuan** | Generate inventaris lengkap semua komponen software (SBOM). Untuk compliance (NTIA, EO 14028, EU Cyber Resilience Act). |
| **Tools** | Syft (SPDX format), CycloneDX, Trivy |
| **Input** | Repo atau built image. |
| **Output** | `sbom.spdx.json` atau `sbom.cdx.json` (downloadable artifact). |
| **Default status** | `recommended` untuk containerized deployment. |
| **Kapan di-drop** | Tidak ada Dockerfile (lihat `_has_dockerfile()`). |
| **Mapping domain** | **WAJIB** untuk gov, finance, healthcare. Tinggi untuk SaaS, e-commerce (PCI-DSS butuh SBOM untuk software supply chain). |

**Konteks `eccomerce-monolith-vuln`:** Syft dengan SPDX format. Output: `sbom.spdx.json` artifact download.

---

### 3.11. `iac_scan` — Infrastructure as Code Scanning

| Properti | Nilai |
|---|---|
| **Tujuan** | Audit Terraform/K8s/Helm untuk misconfiguration: S3 bucket public, IAM terlalu permisif, security group open, missing resource limits. |
| **Tools** | Trivy (config mode), Checkov, Terrascan, KICS |
| **Input** | `*.tf`, `Chart.yaml`, `values.yaml`, `k8s/`, `terraform/`, `helm/` |
| **Output** | SARIF → Code Scanning tab. |
| **Default status** | `recommended` jika ada file IaC. |
| **Kapan di-drop** | **Tidak ada** `*.tf` / `Chart.yaml` / `values.yaml` / `k8s/` / `helm/` / `terraform/`. Dockerfile saja **tidak cukup**. |
| **Mapping domain** | **WAJIB** untuk cloud-native (K8s, Terraform). High untuk e-commerce di cloud. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** karena tidak ada Terraform/K8s/Helm. Dockerfile saja tidak cukup.

**Reason drop:** `'iac-scan' was requested by security inference but no Terraform, Kubernetes, or Helm artifact was detected in the repository analysis. A Dockerfile alone is not enough to trigger iac-scan; use the 'container-config-scan' or 'container-scan' stages for Dockerfile auditing.`

---

### 3.12. `service_mesh_audit` — Service Mesh Configuration Audit

| Properti | Nilai |
|---|---|
| **Tujuan** | Audit mTLS, network policies, sidecar injection untuk Istio/Linkerd/Consul/Kuma. |
| **Tools** | Checkov (Kubernetes framework), kubeaudit |
| **Input** | Istio/Linkerd/Consul/Kuma config files, namespace YAML. |
| **Output** | SARIF. |
| **Default status** | `recommended` jika ada service mesh config. |
| **Kapan di-drop** | Tidak ada Istio/Linkerd/Consul/Kuma mention di YAML files. |
| **Mapping domain** | Microservices dengan mTLS requirement (finance, healthcare). |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — tidak ada service mesh config.

---

### 3.13. `api_gateway_test` — API Gateway Configuration Test

| Properti | Nilai |
|---|---|
| **Tujuan** | Validasi nginx.conf / Kong / AWS API Gateway: rate limit, CORS, auth header, timeout. |
| **Tools** | `nginx -t`, Trivy (config mode), Kong admin API test |
| **Input** | `nginx.conf`, Kong YAML, AWS API Gateway swagger. |
| **Output** | SARIF. |
| **Default status** | `recommended` jika ada API gateway config. |
| **Kapan di-drop** | Tidak ada `nginx.conf` / `kong.yml` / API gateway swagger. |
| **Mapping domain** | Microservices dengan API gateway, SaaS multi-tenant. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — tidak ada API gateway config (monolith Express, bukan gateway).

---

### 3.14. `per_service_sast` — Per-Service SAST

| Properti | Nilai |
|---|---|
| **Tujuan** | Untuk microservices/modular monolith: jalankan SAST per service directory (bukan satu scan global). |
| **Tools** | Semgrep, CodeQL, dengan `--scan-root` per service. |
| **Input** | Multiple service directories (matrix). |
| **Output** | SARIF per service. |
| **Default status** | `recommended` jika arsitektur `microservices` atau `modular_monolith`. |
| **Kapan di-drop** | Arsitektur `monolithic`. |
| **Mapping domain** | Microservices. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — arsitektur monolithic.

---

### 3.15. `per_service_dep_scan` — Per-Service Dependency Scan

| Properti | Nilai |
|---|---|
| **Tujuan** | Scan CVE dependencies per service di microservices. |
| **Tools** | Trivy, `npm audit`, matrix execution. |
| **Input** | Per-service lockfiles. |
| **Output** | SARIF per service. |
| **Default status** | `recommended` jika arsitektur `microservices` atau `modular_monolith`. |
| **Kapan di-drop** | Arsitektur `monolithic`. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — arsitektur monolithic.

---

### 3.16. `license_check` — License Compliance

| Properti | Nilai |
|---|---|
| **Tujuan** | Cek license compatibility third-party packages (GPL vs MIT conflict, dsb). |
| **Tools** | FOSology, ScanCode, pip-licenses, license-checker (npm) |
| **Input** | Lockfiles. |
| **Output** | License list + compatibility report. |
| **Default status** | `optional` (default dropped kecuali enterprise). |
| **Kapan di-drop** | Default dropped. Hanya di-include jika user explicit request. |
| **Mapping domain** | **WAJIB** untuk enterprise / closed-source product. High untuk SaaS B2B. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — status `optional`, default dropped.

---

### 3.17. `deploy` — Deployment

| Properti | Nilai |
|---|---|
| **Tujuan** | Deploy ke staging/production: build image, push registry, trigger K8s/CDN. |
| **Tools** | `docker push`, `kubectl apply`, Railway/Fly.io CLI, Vercel/Netlify. |
| **Input** | Built artifact. |
| **Output** | Live URL. |
| **Default status** | `optional` (default dropped). |
| **Kapan di-drop** | Default dropped. Hanya di-include jika ada explicit CD config (Pages, Heroku, Railway, Fly.toml). |
| **Mapping domain** | Semua domain butuh deploy, tapi out-of-scope untuk security generator. |

**Konteks `eccomerce-monolith-vuln`:** **DROPPED** — tidak ada CD config.

---

## 4. Mapping Security Controls → Domain Context

Mapping di bawah menunjukkan **konteks domain** (e-commerce, finance, healthcare, SaaS, dsb) dan **security controls mana yang WAJIB / tinggi / medium / opsional**.

| Control | E-commerce | Finance | Healthcare | SaaS | Gov | Microservices |
|---|---|---|---|---|---|---|
| `lint` | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB |
| `test` | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB |
| `build` | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB | WAJIB |
| `sast` | **WAJIB** (SQLi, XSS) | **WAJIB** (input validation) | **WAJIB** (data leak) | **WAJIB** | **WAJIB** | **WAJIB** |
| `dependency-scan` | **WAJIB** (CVE) | **WAJIB** (CVE) | **WAJIB** (CVE) | **WAJIB** | **WAJIB** | **WAJIB** |
| `cve_scan` | Tinggi | **WAJIB** | **WAJIB** | Tinggi | **WAJIB** | Tinggi |
| `secret_scan` | **WAJIB** (PCI-DSS) | **WAJIB** (PCI-DSS) | **WAJIB** (HIPAA) | **WAJIB** | **WAJIB** | **WAJIB** |
| `container_build` | Tinggi | Tinggi | Tinggi | **WAJIB** | Tinggi | **WAJIB** |
| `container_scan` | Tinggi | Tinggi | Tinggi | **WAJIB** | Tinggi | **WAJIB** |
| `sbom` | Tinggi (PCI-DSS) | **WAJIB** | **WAJIB** | Tinggi | **WAJIB** | Tinggi |
| `iac_scan` | Tinggi (cloud) | **WAJIB** (cloud) | **WAJIB** (cloud) | **WAJIB** | **WAJIB** | **WAJIB** |
| `service_mesh_audit` | Medium | Tinggi (mTLS) | Tinggi (mTLS) | Tinggi | Tinggi | **WAJIB** |
| `api_gateway_test` | Tinggi | **WAJIB** | **WAJIB** | **WAJIB** | **WAJIB** | **WAJIB** |
| `per_service_sast` | N/A | N/A | N/A | Tinggi | Tinggi | **WAJIB** |
| `per_service_dep_scan` | N/A | N/A | N/A | Tinggi | Tinggi | **WAJIB** |
| `license_check` | Medium | Tinggi | Tinggi | Tinggi | **WAJIB** | Medium |
| `deploy` | Opsional | Opsional | Opsional | Opsional | Opsional | Opsional |

**Konteks `eccomerce-monolith-vuln` (e-commerce, monolithic, no K8s/TF):**
- WAJIB tercakup: `lint`, `test`, `build`, `sast`, `dependency-scan`, `secret-scan`, `container_build`, `container_scan`, `sbom` ✅
- WAJIB yang di-drop karena arsitektur: tidak ada (semua WAJIB untuk e-commerce ada)
- Tinggi yang di-drop: `iac_scan` (tidak ada TF/K8s/Helm) — **acceptable** karena container-scan meng-cover Dockerfile
- `license_check` opsional, di-drop by default
- `deploy` opsional, di-drop by default

---

## 5. Attack Surface Mapping

Attack surface adalah pintu masuk potensial untuk attacker. Mapping deployment → attack surfaces → controls:

| Deployment | Attack Surfaces | Mandatory Controls |
|---|---|---|
| `docker` | Container Image, Dockerfile Config, Image Layer Secrets | container_scan, cve_scan, container_build, secret_scan |
| `kubernetes` | RBAC, Container Images, Ingress, Service Accounts, Pod Security | iac_scan, service_mesh_audit, container_scan |
| `terraform` | S3 Bucket ACL, IAM, Security Group | iac_scan |
| `code-only` | Source Code, Dependencies, Secrets | sast, dependency_scan, secret_scan |

> **Catatan penting:** Sebelum perbaikan, `Dockerfile Config` masuk mapping ke `iac_scan` (karena Trivy config bisa scan Dockerfile). Setelah perbaikan, dipindah ke `container_scan` agar `iac_scan` strictly Terraform/K8s/Helm. Ini menghindari false positive di mana repo dengan Dockerfile saja men-trigger `iac_scan` job yang tidak relevan.

---

## 6. File Evidence Reference (SSoT)

Tiap security control yang butuh file evidence punya pattern matching di `workflow_generator.py`:

| Pattern | Mendeteksi |
|---|---|
| `Dockerfile`, `Dockerfile.*`, `docker-compose.yml`, `docker-compose.yaml` | Container |
| `*.tf`, `*.tfvars`, `*.tfstate` | Terraform |
| `Chart.yaml`, `values.yaml` | Helm |
| `k8s/*`, `kubernetes/*`, `helm/*`, `terraform/*` | IaC directories |
| `package.json` | JS project |
| `requirements.txt`, `pyproject.toml` | Python project |
| `go.mod`, `go.sum` | Go project |
| `Cargo.toml` | Rust project |
| `pom.xml`, `build.gradle` | Java project |
| `nginx.conf` | API gateway |
| `istio*`, `linkerd*`, `consul*`, `kuma*` | Service mesh |

**Cara kerja `_has_file()`:** Match nama/path file dengan glob pattern (case-insensitive) di `repository_structure` (list of dicts) atau `repository_files` (dict of path → content).

---

## 7. Verifikasi Hasil Scan

Setelah workflow jalan, hasil scan bisa dilihat di:

1. **Job logs** (GitHub Actions UI): Plain text output
2. **Code Scanning tab** (GitHub repo → Security → Code scanning): SARIF alerts per file:line
3. **Workflow artifacts** (GitHub Actions UI → Artifacts): download SBOM, SARIF files
4. **GitHub API** (untuk frontend AI agent consume):

```bash
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/iqbalrsyd/eccomerce-monolith-vuln/code-scanning/alerts?state=open" \
  | jq '.[] | {
      rule: .rule.id,
      severity: .rule.security_severity_level,
      file: .most_recent_instance.location.path,
      line: .most_recent_instance.location.start_line,
      tool: .tool.name,
      state: .state,
      cwe: [.rule.tags[] | select(startswith("cwe"))] | first
    }'
```

Response:
```json
{
  "rule": "javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret",
  "severity": "error",
  "file": "src/routes/auth.js",
  "line": 33,
  "tool": "Semgrep",
  "state": "open",
  "cwe": "external/cwe/cwe-798"
}
{
  "rule": "dockerfile.security.last-user-is-root.last-user-is-root",
  "severity": "warning",
  "file": "Dockerfile",
  "line": 12,
  "tool": "Semgrep",
  "state": "open"
}
```

Frontend AI agent bisa render list ini sebagai tabel di UI Security tab → user tidak perlu buka GitHub.

---

## 8. Referensi Lintas

- [PROMPT-ENGINEERING-BAB3.md](../PROMPT-ENGINEERING-BAB3.md) §5 — Deterministic Safety Guards (kenapa file evidence > inferred flag)
- [README.md](../README.md) §AI-Generated Pipeline — Decision tree dan contoh workflow
- [AI-AGENT-SECURITY-FINDINGS.md](AI-AGENT-SECURITY-FINDINGS.md) — Format output agent untuk security findings
- [ai-service/app/agents/attack_surface_lookup.py](../ai-service/app/agents/attack_surface_lookup.py) — Source of truth mapping surface → control
- [ai-service/app/agents/nodes/workflow_generator.py](../ai-service/app/agents/nodes/workflow_generator.py) — Source of truth generator decision
- [ai-service/app/agents/action_registry.py](../ai-service/app/agents/action_registry.py) — Action SHAs dan node compatibility

---

_Dokumen ini disusun sebagai referensi single-source untuk tim DevSecOps dan
peneliti yang ingin memahami keputusan include/exclude security control di
generated workflow AI agent._
