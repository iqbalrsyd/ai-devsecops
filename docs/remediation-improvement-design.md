# Remediation Flow Improvement Design

## 0. Prinsip: Additive, Bukan Replacement

Semua perubahan bersifat **menambahkan** — tidak menghilangkan atau mengubah fitur existing.
Sistem sudah mendeteksi architecture + language + deployment sebelum generate pipeline, dan perubahan di bawah hanya beroperasi **dalam scope itu**.

### Arsitektur & Language yang Didukung (Existing → Tetap Jalan)

| Architecture | Language/Package Manager | Deployment | Yang di-generate |
|-------------|-------------------------|------------|-----------------|
| Monolith | Go / npm / Python / Rust / Java | none | lint, test, sast, secret-scan, dep-scan |
| Monolith | Go / npm / Python / Rust / Java | Docker | + container-build, container-scan |
| Monolith | Go / npm / Python / Rust / Java | Docker + K8s | + k8s-scan, kube-bench |
| Monolith | Go / npm / Python / Rust / Java | Docker + TF | + terraform-scan |
| Frontend-Backend | Go (backend) + npm (frontend) | any | matrix per-service |
| Microservices | Mixed | any | detect-services → matrix → per-service scan |
| Modular Monolith | Mixed | any | matrix per-service |

### Layer yang Dimodifikasi & Impact Scope

| Layer | File | Sifat Perubahan | Berdampak ke |
|-------|------|----------------|-------------|
| Backend handler | `pipeline_handler.go` | **Add keyword entries saja** — tidak hapus/mengubah existing | Semua architecture + language |
| Workflow generator | `workflow_generator.py` | **Tambah precondition check di dalam if-block** — tidak ubah logic penentuan inject/no-inject | Hanya project dengan k8s/terraform/docker terdeteksi |
| CVE injection | `workflow_generator.py` | **Tidak diubah** — sudah language-aware | Go/npm/Python/Rust/Java (sesuai existing) |
| Remediation node | `workflow_remediation_generation_node.py` | **Tambah multi-fix loop** — fallback ke single-fix jika failed_jobs kosong | Semua architecture + language |
| LLM prompt (workflow gen) | `workflow_generator.py` | **Tidak diubah** | Tidak berdampak |
| Security analyzer | `security_analyzer.py` | **Tidak diubah** | Tidak berdampak |

---

## 1. Current Flow (Existing)

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│ Workflow Gen │───▶│ Pipeline Run     │───▶│  createAnalysisFrom  │
│ (LLM + inject)│    │ (GitHub Actions) │    │  Jobs (Go backend)   │
└──────────────┘    └──────────────────┘    └──────────┬───────────┘
                                                       │
                                          ┌────────────▼───────────┐
                                          │ generateFindingsFromJobs│
                                          │  - keyword matching    │
                                          │  - generic fallback    │
                                          └──────────┬───────────┘
                                                       │
                                          ┌────────────▼───────────┐
                                          │ Remediation Generation │
                                          │  - SINGLE fix per run  │
                                          │  - no per-job log match│
                                          └────────────────────────┘
```

### 1.1 Problem: Finding-to-Job Mapping Gaps

**File:** `backend/internal/handlers/pipeline_handler.go:693-789`

`securityTools` keyword map existing (lines 706-727): `sast`, `codeql`, `secret`, `secrets`, `gitleaks`, `dep`, `trivy`, `checkov`, `lint`, `containers`, `iac`, `license`, `semgrep`, `sbom`, `detect`, `vulnerability`, `build`, `test`, `security`, `scan`

**Gap:** deployment jobs `kube-bench`, `k8s-scan`, `terraform-scan`, `kubescape` tidak ada keyword spesifik — `k8s-scan` dan `terraform-scan` tertangkap oleh keyword `scan` yang terlalu generik, `kube-bench` tidak tertangkap sama sekali.

| Job Name | Keyword Match | Result Finding | Issue |
|----------|--------------|----------------|-------|
| `k8s-scan` | `scan` (broad) | "Security Scan Failed" | Loses specific K8s context |
| `kube-bench` | NO MATCH | "Job 'kube-bench' Failed" | Not recognized as security, marked medium |
| `terraform-scan` | `scan` (broad) | "Security Scan Failed" | Loses IaC/Terraform context |
| `container-build` | `build` | "Build Failed" | Correct match, but no log details |

### 1.2 Problem: Deployment Jobs Don't Validate Preconditions

**File:** `ai-service/app/agents/nodes/workflow_generator.py:284-460`

Job di-inject hanya jika deployment terdeteksi (`deployment.get("kubernetes")` dll), tapi **setelah di-inject**, job tersebut tidak memvalidasi apakah direktori/file target benar-benar ada di repo. Akibatnya job gagal runtime.

| Job | Condition Inject | Failure Reason |
|-----|-----------------|---------------|
| `kube-bench` | `kubernetes=True` | `kubectl apply -f job.yaml` needs running K8s cluster — impossible in GHA runner |
| `k8s-scan` | `kubernetes=True` | References `k8s/` dir — fails if no manifests |
| `terraform-scan` | `terraform=True` | `terraform init` on `terraform/` dir — fails if dir missing |
| `container-build` | `docker=True` | Hardcoded `docker/Dockerfile.*` — wrong for most repos |
| `container-scan` | `docker=True` | Same Dockerfile path issue |

### 1.3 Problem: Remediation is Single-Fix, No Per-Job Correlation

**File:** `ai-service/app/agents/nodes/workflow_remediation_generation_node.py:37-77`

- Only generates **one** `WorkflowFix` per run (not one per failed job)
- `root_cause` is a flat dict — doesn't contain per-job error details
- No fallback chain: jika satu fix gagal apply, tidak ada attempt berikutnya

### 1.4 Problem: Validation Warnings Tidak Di-action

**File:** `ai-service/app/agents/nodes/workflow_validator.py:40-110`

Validator menghasilkan warning untuk **semua** generated workflow:
- Action di-pin ke tag/branch (`@v3`, `@master`) bukan commit SHA
- `persist-credentials: false` tidak di-set di `actions/checkout`
- Warning-warning ini tidak menyebabkan job gagal, tapi jadi supply chain risk

---

## 2. Improved Flow (Proposed)

```
┌──────────────┐    ┌──────────────────┐    ┌───────────────────────┐
│ Workflow Gen │───▶│ Pipeline Run     │───▶│  createAnalysisFrom   │
│ (LLM + inject)│    │ (GitHub Actions) │    │  Jobs                  │
│ + PRECONDITION│    │                  │    └───────────┬───────────┘
│   CHECKS      │    │                  │                │
│ + ACTION SHA  │    │                  │     ┌───────────▼───────────┐
│   RESOLUTION  │    │                  │     │ NEW: Per-Job Log Fetch │
└──────────────┘    └──────────────────┘     │  - fetch logs per job  │
                                              │  - extract error lines │
                                              └───────────┬───────────┘
                                                           │
                                              ┌────────────▼───────────┐
                                              │ ENHANCED:              │
                                              │ generateFindingsFrom   │
                                              │ Jobs                    │
                                              │  + granular keyword map│
                                              │  + embedded error logs  │
                                              │  (k8s/kube-bench/tf)   │
                                              └───────────┬───────────┘
                                                           │
                                              ┌────────────▼───────────┐
                                              │ ENHANCED:              │
                                              │ Remediation Generation │
                                              │  - MULTI-FIX (per job) │
                                              │  - per-job log→YAML    │
                                              │  - batch + fallback    │
                                              └────────────────────────┘
```

### 2.1 Enhanced Security Keyword Mapping (ADDITIVE)

**Target:** `backend/internal/handlers/pipeline_handler.go:706`

**Yang existing tetap.** Tambahkan 5 keyword baru **di bawah** entry existing, **sebelum** catch-all `scan`/`security`:

```go
// --- NEW: deployment-specific security tools (add BELOW existing entries) ---
"kube-bench":      {tool: "Kube-Bench", severity: "high",
    title: "Kubernetes Security Benchmark Failed",
    explain: "The kube-bench job failed. This job audits Kubernetes configuration against CIS benchmarks.",
    recommend: "Ensure kube-bench can run in CI. Use aquasecurity/kube-bench container image instead of kubectl apply."},
"k8s-scan":        {tool: "K8s Security Scan", severity: "high",
    title: "Kubernetes Security Scan Failed",
    explain: "The Kubernetes security scan failed. May indicate missing manifests or scan tool errors.",
    recommend: "Verify k8s/ directory exists with valid YAML manifests. Check Trivy/Kubescape scan configuration."},
"terraform-scan":  {tool: "Terraform Scan", severity: "medium",
    title: "IaC Security Scan Failed",
    explain: "The Terraform/IaC security scan failed. May indicate missing .tf files or misconfigured backend.",
    recommend: "Verify terraform/ directory exists with valid .tf files. Run terraform validate before scanning."},
"kubescape":       {tool: "Kubescape", severity: "high",
    title: "Kubernetes Compliance Scan Failed",
    explain: "Kubescape scan failed. May indicate installation or configuration issues.",
    recommend: "Use the official kubescape GitHub Action instead of curl-based install."},
```

**Penting:** Entry `checkov` sudah ada di existing (line 714). Tidak perlu ditambah lagi.

**Priority ordering:** Karena Go `map` iterasi tidak terjamin urutannya, di loop matching (line 740-755), cek keyword **spesifik multi-word** dulu sebelum **generik single-word**:

```go
// Pseudocode: di dalam loop jobs
specificKeywords := []string{"kube-bench", "k8s-scan", "terraform-scan", "kubescape", "semgrep", "gitleaks", "checkov", "codeql", "trivy"}
genericKeywords := []string{"scan", "security", "vulnerability", "build", "test", "lint", "dep", "detect", "iac", "containers", "license", "sbom", "secret"}

// Cek specific dulu
matched := false
for _, kw := range specificKeywords {
    if strings.Contains(nameLower, kw) {
        // match & generate finding
        matched = true
        break
    }
}
if !matched {
    for _, kw := range genericKeywords {
        if strings.Contains(nameLower, kw) {
            // match & generate finding
            matched = true
            break
        }
    }
}
```

**Kompatibilitas:**
- Project Go monolith tanpa k8s/tf → loop tidak menemukan keyword baru → tidak terpengaruh ✓
- Project Python dengan k8s → keyword `k8s-scan` / `kube-bench` akan match ✓
- Project npm monolith → tidak ada job k8s/tf di pipeline → tidak terpengaruh ✓

### 2.2 Defensive Precondition Checks in Deployment Jobs (ADDITIVE)

**Target:** `ai-service/app/agents/nodes/workflow_generator.py:284-460`

**Yang existing tetap.** Di dalam setiap `if deployment.get(...)` block, tambahkan precondition check di step pertama. Kalau direktori/file tidak ada, job skip dengan `exit 0` + notice.

#### 2.2.1 kube-bench fix

**Yang diubah:** cara eksekusi (dari `kubectl apply` ke Docker container) + precondition check

```yaml
  kube-bench:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Validate K8s manifests exist
        id: k8s-check
        run: |
          if ls k8s/*.yaml k8s/*.yml 2>/dev/null; then
            echo "found=true" >> $GITHUB_OUTPUT
          else
            echo "found=false" >> $GITHUB_OUTPUT
            echo "::notice::No Kubernetes manifests found in k8s/, skipping kube-bench"
          fi
      - name: Run kube-bench (containerized)
        if: steps.k8s-check.outputs.found == 'true'
        run: |
          docker run --rm -v "$PWD/k8s:/opt/kube-bench/cfg:ro" \
            aquasec/kube-bench:latest run \
            --targets node --config-dir /opt/kube-bench/cfg \
            --json | tee kube-bench-results.json
      - name: Run Checkov on Kubernetes
        if: steps.k8s-check.outputs.found == 'true'
        uses: bridgecrewio/checkov-action@master
        with:
          directory: k8s
          framework: kubernetes
          output_format: sarif
          output: checkov-k8s-results.sarif
      - name: Upload K8s benchmark results
        if: steps.k8s-check.outputs.found == 'true' && (success() || failure())
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: checkov-k8s-results.sarif
```

#### 2.2.2 k8s-scan fix

```yaml
  k8s-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Validate K8s manifests exist
        id: k8s-check
        run: |
          if ls k8s/*.yaml k8s/*.yml 2>/dev/null; then
            echo "found=true" >> $GITHUB_OUTPUT
          else
            echo "found=false" >> $GITHUB_OUTPUT
            echo "::notice::No Kubernetes manifests found in k8s/, skipping K8s scan"
          fi
      - name: Run Trivy Kubernetes scan
        if: steps.k8s-check.outputs.found == 'true'
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: config
          scan-ref: k8s/
          format: sarif
          output: trivy-k8s-results.sarif
      - name: Run Kubescape scan
        if: steps.k8s-check.outputs.found == 'true'
        uses: kubescape/github-action@v1
        with:
          path: k8s/
          framework: nsa
          outputFile: kubescape-results.sarif
          format: sarif
      - name: Upload K8s security results
        if: steps.k8s-check.outputs.found == 'true' && (success() || failure())
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-k8s-results.sarif
```

#### 2.2.3 terraform-scan fix

```yaml
  terraform-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Validate Terraform files exist
        id: tf-check
        run: |
          if ls terraform/*.tf 2>/dev/null; then
            echo "found=true" >> $GITHUB_OUTPUT
          else
            echo "found=false" >> $GITHUB_OUTPUT
            echo "::notice::No Terraform files found in terraform/, skipping IaC scan"
          fi
      - name: Setup Terraform
        if: steps.tf-check.outputs.found == 'true'
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.0
      - name: Terraform Init (CI-safe, no backend)
        if: steps.tf-check.outputs.found == 'true'
        run: terraform init -backend=false
        working-directory: terraform/
      - name: Terraform Validate
        if: steps.tf-check.outputs.found == 'true'
        run: terraform validate
        working-directory: terraform/
      - name: Run Trivy IaC scan
        if: steps.tf-check.outputs.found == 'true'
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: config
          scan-ref: terraform/
          format: sarif
          output: trivy-tf-results.sarif
      - name: Run Checkov on Terraform
        if: steps.tf-check.outputs.found == 'true'
        uses: bridgecrewio/checkov-action@master
        with:
          directory: terraform
          framework: terraform
          output_format: sarif
          output: checkov-tf-results.sarif
      - name: Upload IaC security results
        if: steps.tf-check.outputs.found == 'true' && (success() || failure())
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: checkov-tf-results.sarif
```

#### 2.2.4 container-build/container-scan fix

```yaml
  container-build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    needs: [detect-services]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Find Dockerfiles
        id: find-df
        run: |
          echo "dockerfiles<<EOF" >> $GITHUB_OUTPUT
          find . -name "Dockerfile*" -not -path "*/node_modules/*" -not -path "*/.venv/*" | tee -a $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
      - name: Set up Docker Buildx
        if: steps.find-df.outputs.dockerfiles != ''
        uses: docker/setup-buildx-action@v3
      - name: Build service images
        if: steps.find-df.outputs.dockerfiles != ''
        run: |
          echo "${{ steps.find-df.outputs.dockerfiles }}" | while IFS= read -r df; do
            [ -z "$df" ] && continue
            dir=$(dirname "$df")
            tag=$(basename "$dir"):ci
            echo "Building $tag from $df ..."
            docker build -f "$df" -t "$tag" "$dir"
          done
      - name: No Dockerfiles found
        if: steps.find-df.outputs.dockerfiles == ''
        run: |
          echo "::notice::No Dockerfiles found in repository, skipping container build."
```

```yaml
  container-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    needs: [container-build]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Find Dockerfiles
        id: find-df
        run: |
          echo "dockerfiles<<EOF" >> $GITHUB_OUTPUT
          find . -name "Dockerfile*" -not -path "*/node_modules/*" -not -path "*/.venv/*" | tee -a $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
      - name: Run Trivy image scan
        if: steps.find-df.outputs.dockerfiles != ''
        run: |
          echo "${{ steps.find-df.outputs.dockerfiles }}" | while IFS= read -r df; do
            [ -z "$df" ] && continue
            dir=$(dirname "$df")
            tag=$(basename "$dir"):ci
            docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
              aquasec/trivy:latest image --severity HIGH,CRITICAL \
              --format sarif --output "trivy-$(basename "$dir").sarif" "$tag"
          done
      - name: Upload Trivy container results
        if: success() || failure()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-*.sarif'
```

**Kompatibilitas:**
- Project tanpa k8s → `deployment.get("kubernetes") == False` → `_inject_deployment_jobs` skip seluruh k8s block → tidak terpengaruh ✓
- Project tanpa terraform → skip terraform block → tidak terpengaruh ✓
- Project tanpa Docker → skip Docker block → tidak terpengaruh ✓
- Monolith Python tanpa deployment tools → hanya dapat CVE scan + SAST + secret scan → tidak terpengaruh ✓

### 2.3 Multi-Fix Remediation (ENHANCED)

**Target:** `ai-service/app/agents/nodes/workflow_remediation_generation_node.py:37-77`

```python
def workflow_remediation_generation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state
    if not state.get("root_cause"):
        return state

    repo = state.get("repository_full_name", "") or ""
    run_id = state.get("workflow_run_id")
    failure_analysis = state.get("failure_analysis", {}) or {}
    root_cause = state.get("root_cause", {}) or {}
    current_workflow = state.get("generated_workflow") or ""
    technologies = state.get("detected_technologies", {}) or {}

    # --- NEW: extract per-job failures ---
    failed_jobs = failure_analysis.get("failed_jobs", [])

    # Fallback: if no per-job data, use the old single-fix path
    if not failed_jobs:
        failed_jobs = [{"job_name": "unknown", "error_log": ""}]

    all_fixes = []
    for job in failed_jobs:
        job_name = job.get("job_name", "unknown")
        error_log = job.get("error_log", "")

        try:
            prompt = REMEDIATION_PROMPT_PER_JOB.format(
                repo=repo,
                job_name=job_name,
                error_log=error_log[:3000],
                current_workflow=current_workflow[:6000],
                technologies=json.dumps(technologies, indent=2),
            )
            fix = analyze_structured(prompt, WorkflowFix)
            all_fixes.append(fix.model_dump())
        except Exception:
            continue  # skip failed fix, try next job

    # --- Apply all fixes sequentially ---
    remediated_workflow = current_workflow
    for fix in all_fixes:
        before = (fix.get("before") or "").strip()
        after = (fix.get("after") or "").strip()
        if before and after and before != after and before in remediated_workflow:
            remediated_workflow = remediated_workflow.replace(before, after)

    state["remediation_suggestions"] = state.get("remediation_suggestions", []) + all_fixes
    if all_fixes:
        state["remediation_workflow"] = remediated_workflow
        reasoning = all_fixes[0].get("reasoning") or ""
        if reasoning:
            state["summary"] = f"Remediation: {reasoning[:200]}"

    return state
```

**Kompatibilitas:**
- `failed_jobs` kosong → fallback ke path existing (single fix dengan `unknown` job) ✓
- Project dengan 1 job gagal → loop 1x → sama seperti behavior existing ✓
- Project dengan N job gagal → loop Nx → menghasilkan N fix ✓

### 2.4 Per-Job Log Analysis in Backend (ADDITIVE)

**Target:** `backend/internal/handlers/pipeline_handler.go:554`

Di dalam `createAnalysisFromJobs`, setelah iterasi pertama untuk hitung statistik, untuk setiap job dengan `conclusion == "failure"`, fetch log step individual via GitHub API dan embed 500 karakter terakhir error ke `finding.Explanation`:

```go
// NEW: after the first stats loop, for each failing job:
for _, j := range jobs {
    if j.Conclusion == "failure" || j.Conclusion == "cancelled" {
        // Fetch individual job logs (already available via run.Jobs structure)
        // Append error snippet to corresponding finding's Explanation
    }
}
```

### 2.5 Validation Warning → Auto-Resolve (ADDITIVE)

**Target:** `ai-service/app/agents/nodes/workflow_generator.py` + `workflow_validator.py`

#### 2.5.1 Action SHA Pinning

Setelah generate YAML (di `workflow_generator_node`, line 267 setelah `_auto_fix_all`), tambahkan step untuk resolve tag → commit SHA via GitHub API cache:

```python
# NEW: resolve action tags to commit SHA
fixed_yaml = _resolve_action_shas(fixed_yaml)
```

Fungsi `_resolve_action_shas`:
1. Parse semua `uses:` references
2. Filter yang bukan full SHA (40-char hex)
3. Untuk yang `@v3`, `@master`, dll → panggil GitHub API `GET /repos/{owner}/{repo}/git/ref/tags/{tag}` atau `git/ref/heads/{branch}`
4. Ganti reference dengan `@<full-sha>`
5. Cache hasil di in-memory dict supaya tidak panggil API berulang untuk action yang sama

#### 2.5.2 Persist Credentials

Sudah ada di `_fix_checkout_persist_credentials()` (line 1094), jadi tidak perlu tambahan — hanya pastikan fungsi ini selalu dipanggil.

#### 2.5.3 Concurrency Group

Tambahkan di `_auto_fix_all()`:

```python
# NEW: inject concurrency group if missing
if 'concurrency:' not in yaml_str:
    yaml_str = "concurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n  cancel-in-progress: true\n\n" + yaml_str
```

---

## 3. Migration Steps (Prioritas)

| # | Change | File | Sifat | Scope |
|---|--------|------|-------|-------|
| P0 | Add 4 keyword entries (kube-bench, k8s-scan, terraform-scan, kubescape) | `pipeline_handler.go:706` | **Additive** — tambah di bawah entry existing | Semua arch/lang |
| P0 | Fix matching order: specific multi-word → generic single-word | `pipeline_handler.go:740` | **Enhancement** — replace single loop dgn two-pass | Semua arch/lang |
| P0 | Precondition checks: kube-bench (Docker container) | `workflow_generator.py:373-397` | **Additive** — dalam if-block `kubernetes=True` | Hanya project dgn k8s |
| P0 | Precondition checks: k8s-scan (dir existence) | `workflow_generator.py:344-371` | **Additive** — dalam if-block `kubernetes=True` | Hanya project dgn k8s |
| P0 | Precondition checks: terraform-scan (dir existence + backend=false) | `workflow_generator.py:399-444` | **Additive** — dalam if-block `terraform=True` | Hanya project dgn TF |
| P0 | Precondition checks: container-build (find Dockerfiles) | `workflow_generator.py:323-341` | **Additive** — dalam if-block `docker=True` | Hanya project dgn Docker |
| P0 | Precondition checks: container-scan (find Dockerfiles) | `workflow_generator.py:288-321` | **Additive** — dalam if-block `docker=True` | Hanya project dgn Docker |
| P1 | Multi-fix remediation (per-job loop + fallback) | `workflow_remediation_generation_node.py` | **Enhancement** — extend existing function | Semua arch/lang |
| P1 | Per-job log fetching + embed in findings | `pipeline_handler.go` | **Additive** — setelah loop stats | Semua arch/lang |
| P2 | Action SHA resolution (tag → commit hash) | `workflow_generator.py` | **Additive** — fungsi baru + panggil di pipeline | Semua arch/lang |
| P2 | Auto-inject concurrency group | `_auto_fix_all()` in `workflow_generator.py` | **Additive** — tambah cek di auto_fix | Semua arch/lang |

---

## 4. Contoh: Flow Before vs After (Microservices + Docker + K8s + TF)

### Before (Current)
```
Detect: architecture=microservices, docker=True, k8s=True, tf=True (legacy, R2.1 monolitik only)
Generate: inject semua deployment jobs (k8s-scan, kube-bench, terraform-scan, container-build, container-scan)
Run: 4 jobs fail karena direktori/file tidak ada atau tool tidak bisa jalan

Run fails → 4 jobs fail → generateFindingsFromJobs()
  ├─ k8s-scan: matches "scan" → "Security Scan Failed" (high)     ← wrong context
  ├─ kube-bench: no match → "Job 'kube-bench' Failed" (medium)    ← not security
  ├─ terraform-scan: matches "scan" → "Security Scan Failed" (high) ← same generic
  └─ container-build: matches "build" → "Build Failed" (medium)   ← ok

→ 1 generic fix generated → applied or not → next run same failures
```

### After (Improved)
```
Detect: architecture=microservices, docker=True, k8s=True, tf=True (legacy, R2.1 monolitik only)
Generate: inject semua deployment jobs DENGAN precondition checks
Run: semua deployment jobs skip karena direktori tidak ada (exit 0)

All jobs pass ✓ → no failures → no remediation needed

Scenario 2: job tetap ada yang gagal (misal k8s/ direktori ada tapi YAML invalid)
Run fails → fetch per-job logs → generateFindingsFromJobs()
  ├─ k8s-scan: matches "k8s-scan" → "K8s Security Scan Failed" (high) + error log
  ├─ kube-bench: matches "kube-bench" → "K8s Benchmark Failed" (high) + error log
  └─ ...dll.

→ N specific fixes generated → applied to YAML → next run
```

### Contoh: Monolith Python tanpa Docker/K8s/TF
```
Detect: architecture=monolithic, lang=python, docker=False, k8s=False, tf=False
Generate: lint, test, sast (semgrep), secret-scan (gitleaks), cve-scan-python (pip-audit)
Run: semua job jalan normal

→ Tidak ada deployment jobs → tidak ada precondition checks yang di-inject → tidak terpengaruh ✓
→ Keyword map baru (kube-bench, dll) tidak pernah match → tidak terpengaruh ✓
```

---

## 5. File Referensi

| File | Deskripsi |
|------|-----------|
| `docs/examples/original-failed-workflow.yml` | Contoh pipeline yang gagal (4 deployment jobs) — untuk testing/verifikasi |
| `docs/examples/remediated-workflow.yml` | Hasil remediation dengan semua precondition checks |
| `docs/remediation-improvement-design.md` | Dokumen ini |
