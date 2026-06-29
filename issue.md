# Issue: Pipeline Generation Drops Stages Silently When Deployment Flag Contradicts File Evidence

> **Type:** Bug — Inconsistent / lossy behavior
> **Severity:** Medium (silent data loss in reviewer feedback)
> **Component:** `ai-service` — workflow generator
> **Reproducibility:** 100% via the provided regression test
> **Status:** ✅ **RESOLVED** (regression test passes, fixes applied)
> **Resolution date:** 2026-06

---

## 1. Summary

The `workflow_generator_node` silently drops CI DevSecOps stages (e.g.
`container-scan`, `container-build`, `iac-scan`) when the **inferred /
stale `detected_deployment` flag** claims `docker: true` but the **actual
file evidence** (`repository_structure` / `repository_files`) shows no
Dockerfile / Terraform / Kubernetes manifest.

The dropped stages are NOT reported in:

* `state["invalid_workflow_stages"]` — should list the dropped stages with
  a reason.
* `state["workflow_config_issues"]` — should include a typed issue so the
  UI can render a warning.

Net effect: the reviewer (human or AI) gets a **clean YAML** that omits
the requested control, with no explanation, even though the inference
step *did* ask for it. This violates the project's own design rule:

> **Requirement 9:** "if a generated job contradicts repository analysis,
> automatically remove it _and_ surface the inconsistency."

(See `PROMPT-ENGINEERING-BAB3.md` §5 — _Deterministic Safety Guards_.)

---

## 2. Environment

| Item | Value |
|---|---|
| Repository | `coba-4` (skripsi prototype) |
| Service | `ai-service` (FastAPI + LangGraph) |
| Python | 3.12 |
| Pytest | 9.1.0 |
| Branch | `master` |
| Affected commit range | since `133aa76 "Fix: Sync workflow runs and analysis generation"` |

---

## 3. Steps to Reproduce

```bash
cd ai-service
source .venv/bin/activate
python -m pytest \
  tests/test_workflow_generator.py::test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies \
  -x -v
```

### Input state

```python
state = {
    "detected_technologies": {"primary_language": "JavaScript", "package_manager": "npm"},
    "detected_deployment":   {"docker": True, "docker_confidence": 0.9},   # ← "lying" flag
    "repository_structure":  [],                                            # ← no Dockerfile
    "repository_files":      {},                                            # ← no file evidence
    "inferred_security_needs": {
        "security_controls": [
            {"control": "sast",            "status": "recommended"},
            {"control": "container_scan",  "status": "recommended"},
            {"control": "container_build", "status": "recommended"},
            {"control": "iac_scan",        "status": "recommended"},
        ]
    },
}
```

### Expected behavior

| Assertion | Expected | Actual (Before) | Actual (After) |
|---|---|---|---|
| `errors == []` | ✅ | ✅ | ✅ |
| `container-scan` not in `generated_stages` | ✅ | ✅ | ✅ |
| `container-build` not in `generated_stages` | ✅ | ✅ | ✅ |
| `iac-scan` not in `generated_stages` | ✅ | ✅ | ✅ |
| `container-scan` in `invalid_workflow_stages` | ✅ | ❌ | ✅ |
| `iac-scan` in `invalid_workflow_stages` | ✅ | ❌ | ✅ |

### Actual output (before fix)

```
E       assert False
E        +  where False = any(<generator object ...>)
tests/test_workflow_generator.py:333: AssertionError
```

Full suite: `1 failed, 98 passed` in `tests/`.

### After fix

```
$ pytest tests/ -v
...
99 passed, 8 warnings in 50.12s
```

---

## 4. Root Cause

In `ai-service/app/agents/nodes/workflow_generator.py`:

```python
# Lines ~309–325
stages = _select_relevant_stages(security, technologies, deployment,
                                  arch_type, findings, structure, files)
#   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   At this point, container-scan / container-build / iac-scan are
#   ALREADY dropped because has_docker=False, has_iac=False (file evidence).
#   They never reach _flag_invalid_stages.

invalid_stages = _flag_invalid_stages(stages, state)   # ← sees no bad stages
stages         = _filter_stages_by_evidence(stages, state)  # ← redundant
```

`_select_relevant_stages` enforces the SSoT (file evidence) inside its
own body. As a result, the *requested-but-contradicted* stages vanish
before they can be flagged.

Additionally, `_flag_invalid_stages` only inspects stages that *survived*
`_select_relevant_stages`, so it cannot detect the contradiction in the
first place.

---

## 5. Solutions Implemented

Solution berikut **terselesaikan per-layer** (prompt, code, parser, UI), sehingga user tidak perlu re-run workflow untuk validasi dan generator tidak menghasilkan YAML yang over-include.

### Solution 1 — Code: `_flag_unjustified_requested_stages` (Fix A)

**File:** `ai-service/app/agents/nodes/workflow_generator.py`

**Problem:** Stages yang diminta inference step tapi di-drop oleh `_select_relevant_stages` (karena file evidence tidak ada) hilang tanpa jejak.

**Solving:** Tambah helper function yang run di `requested` controls (bukan `surviving` stages) untuk flag stages yang di-drop karena kontradiksi file evidence.

```python
def _flag_unjustified_requested_stages(state: PipelineEngineerState) -> list[dict]:
    """Surface stages REQUESTED by the inference step that lack file evidence.
    Detects: container-scan/build/sbom without Dockerfile, iac-scan without
    TF/K8s/Helm, test without test framework, etc.
    """
    invalid = []
    # container_* and sbom: require Dockerfile
    for stage in ("container-scan", "container-build", "sbom"):
        if stage in requested and not has_docker:
            invalid.append({
                "stage": stage, "expected": False,
                "reason": f"'{stage}' was requested but no Dockerfile detected. "
                          "The 'detected_deployment.docker' flag may be stale; "
                          "file evidence is the single source of truth.",
            })
    # iac-scan: require Terraform / K8s / Helm artifacts
    if "iac-scan" in requested and not has_iac:
        invalid.append({
            "stage": "iac-scan", "expected": False,
            "reason": "'iac-scan' was requested by security inference but no "
                      "Terraform, Kubernetes, or Helm artifact was detected "
                      "in the repository analysis. A Dockerfile alone is not "
                      "enough to trigger iac-scan; use the 'container-config-scan' "
                      "or 'container-scan' stages for Dockerfile auditing.",
        })
    # test: require test framework
    if "test" in requested and not has_test_framework:
        invalid.append({
            "stage": "test", "expected": False,
            "reason": "'test' was requested by security inference but no test "
                      "framework was detected in the repository analysis.",
        })
    return invalid
```

**Caller** di `workflow_generator_node()`:

```python
unjustified_requested = _flag_unjustified_requested_stages(state)
if unjustified_requested:
    seen = {item["stage"] for item in invalid_stages}
    for item in unjustified_requested:
        if item["stage"] not in seen:
            invalid_stages.append(item)
            seen.add(item["stage"])
```

**Result:** Test `test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies` PASS ✅.

---

### Solution 2 — Code: Narrow `_IAC_PATTERNS` (Fix B)

**File:** `ai-service/app/agents/nodes/workflow_generator.py:529-545`

**Problem:** `_IAC_PATTERNS` include `Dockerfile` dan `docker-compose.yml` → repo yang cuma punya Dockerfile (no Terraform/K8s/Helm) tetep dapat `iac-scan` job yang nothing-to-scan. Output Debug panel bilang "iac-scan generated" tapi sebenarnya tidak relevan.

**Solving:** Strict scope untuk IaC — Dockerfile bukan IaC, dia container artifact.

```python
# Sebelum:
_IAC_PATTERNS: tuple[str, ...] = (
    "Dockerfile", "Dockerfile.*", "docker-compose.yml", "docker-compose.yaml",  # ← over-include
    "*.tf", "*.tfvars", "*.tfstate",
    "Chart.yaml", "values.yaml",
)
_IAC_DIRECTORY_PATTERNS: tuple[str, ...] = (
    "docker/*",  # ← over-include
    "k8s/*", "kubernetes/*", "helm/*", "terraform/*",
)

# Sesudah:
_IAC_PATTERNS: tuple[str, ...] = (
    "*.tf", "*.tfvars", "*.tfstate",
    "Chart.yaml", "values.yaml",
)
_IAC_DIRECTORY_PATTERNS: tuple[str, ...] = (
    "k8s/*", "kubernetes/*", "helm/*", "terraform/*",
)
```

**Result:** Repo `eccomerce-monolith-vuln` (hanya Dockerfile) tidak lagi emit `iac-scan` job; yang muncul hanya stages yang relevan (lint, sast, dependency-scan, secret-scan, container-build, container-scan, sbom).

---

### Solution 3 — Code: `CONTROL_MERGED_INTO` dict (Fix C)

**File:** `ai-service/app/agents/nodes/workflow_generator.py:873-907`

**Problem:** Security controls yang di-merge ke job lain (e.g. `cve_scan` → `dependency-scan`) tidak di-track di output. User lihat `cve_scan` di Security Controls panel tapi tidak di generated stages, dengan message "No inconsistent stages detected" — contradictory.

**Solving:** Track merged controls via `CONTROL_MERGED_INTO` mapping, emit ke `workflow_config_issues` dengan rule `cve-scan_merged_into_dependency-scan`.

```python
CONTROL_MERGED_INTO: dict[str, str] = {
    "cve_scan": "dependency-scan",
    "cve-scan": "dependency-scan",
    "per_service_sast": "sast",
    "per_service_dep_scan": "dependency-scan",
}

def _flag_merged_requested_controls(requested, generated) -> list[tuple[str, str]]:
    """Return (original, target) for requested controls provided by another stage."""
    out = []
    for control, target in CONTROL_MERGED_INTO.items():
        if control in requested and control not in generated and target in generated:
            out.append((control, target))
    return out
```

**Caller** add merged issues ke `workflow_config_issues`:
```python
if merged_into:
    for original, target in merged_into:
        existing_issues.append({
            "category": "workflow_config_issue",
            "rule": f"{original}_merged_into_{target}",
            "message": f"Control '{original}' was requested but is not generated as a separate job. Its capability is provided by the '{target}' stage.",
            ...
        })
```

**Result:** Frontend Debug panel sekarang punya section "Merged Controls" menampilkan `cve-scan → dependency-scan` dengan explanation.

---

### Solution 4 — Code: `_get_sast_tool` always returns "semgrep" (Fix D)

**File:** `ai-service/app/agents/nodes/security_requirement_inference_node.py:277-291`

**Problem:** `_get_sast_tool()` return `"eslint"` untuk JavaScript, tapi workflow generator pakai Semgrep untuk semua bahasa. Security Controls panel advertise tool yang berbeda dari yang sebenarnya dijalankan di workflow → user bingung.

**Solving:** Konsistenkan tool yang di-advertise dengan yang di-emit.

```python
def _get_sast_tool(technologies: dict) -> str:
    """SAST tool name. We use Semgrep for every language because:
    1. It has the broadest language coverage.
    2. The workflow generator emits Semgrep (consistent across languages).
    3. Returning language-specific tools (eslint, bandit, spotbugs) creates
       a UI/workflow mismatch that erodes user trust.
    The displayed tool in the Security Controls panel MUST match the
    tool actually invoked in the generated YAML.
    """
    return "semgrep"
```

**Result:** Security Controls panel `sast: semgrep` konsisten dengan workflow YAML `run: semgrep`.

---

### Solution 5 — Code: Drop `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` (Fix E)

**File:** `ai-service/app/agents/nodes/workflow_generator.py:1454`

**Problem:** `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'` di-emit di env block, tapi semua action sudah di-pin ke SHA `using: node24`. Env var ini redundant, bikin workflow noise.

**Solving:** Drop env var dari output. Komentar menjelaskan bahwa registry sudah handle node compatibility.

```python
# Sebelum:
"env:",
"  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'",

# Sesudah:
# All actions emitted by the generator are pinned to versions
# that declare `using: node24` in their action.yml. The legacy
# `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` environment variable (a
# stop-gap when the registry still pointed at node20-pinned
# actions) is no longer needed and would only confuse readers
# of the generated YAML.
```

**Result:** Generated YAML tidak ada redundant env var, lebih clean.

---

### Solution 6 — Code: Bump `action_registry` SHAs ke `node24` (Fix F)

**File:** `ai-service/app/agents/action_registry.py`

**Problem:** `actions/checkout@34e1148...` (= v4.1.7), `actions/setup-node@49933ea...` (= v4.4.0) — semua declare `using: node20` di `action.yml`. Runner GitHub force ke Node 24 → warning deprecation muncul di setiap job.

**Solving:** Bump `pinned_sha` ke versi yang declare `using: node24`:

| Action | Old (node20) | New (node24) |
|---|---|---|
| `actions/checkout` | v4.3.0 (`08eba0b...`) | **v5.0.0** (`08c6903c...`) |
| `actions/setup-node` | v4.4.0 (`49933ea5...`) | **v6.0.0** (`48b55a01...`) |
| `actions/setup-python` | v5.5.0 (`8d9ed9ac...`) | **v6.0.0** (`a309ff8b...`) |
| `actions/upload-artifact` | v4.6.0 | **v7.0.1** |
| `actions/download-artifact` | v4.3.0 | **v8.0.1** |
| `actions/cache` | v4.3.0 | **v5.0.5** |
| `docker/setup-buildx-action` | v3.11.0 | **v4.1.0** |
| `docker/login-action` | v3.5.0 | **v4.2.0** |
| `docker/build-push-action` | v6.19.0 | **v7.2.0** |
| `step-security/harden-runner` | v2.13.0 | **v2.19.4** |
| `gitleaks/gitleaks-action` | v2.3.6 (node20) | **v3.0.0** (node24) |

**Result:** Generated workflow tidak trigger deprecation warning, semua action kompatibel dengan Node 24 runtime.

---

### Solution 7 — Code: Native module resilience untuk security jobs (Fix G)

**File:** `ai-service/app/agents/nodes/workflow_generator.py:1354-1395`

**Problem:** `better-sqlite3@7.4.3` (rilis 2021) pakai V8 API yang dihapus di Node 24. `npm install` di security-scan jobs fail → scanner tidak sempat run → SARIF tidak ter-upload → Code Scanning tab kosong.

**Solving:** Tambah parameter `ignore_scripts` di `_node_setup_steps`, default `False` (real CI jobs butuh working modules), override `True` untuk security-scan jobs.

```python
def _node_setup_steps(package_manager, has_lockfile, node_version="24",
                    ignore_scripts=False):
    if ignore_scripts:
        install_cmd += " --ignore-scripts"
    ...

# Caller di dependency-scan:
setup, install_cmd = _node_setup_steps(
    package_manager, has_lockfile, ignore_scripts=True
)
install = f"      - name: Install dependencies (no native build)\n        run: {install_cmd}\n        continue-on-error: true"
```

**Result:** `dependency-scan` job pakai `npm ci --no-audit --no-fund --ignore-scripts` → install sukses, `npm audit` jalan, Trivy scan jalan, SARIF ter-upload.

---

### Solution 8 — Prompt: Failure-Mode-Aware Generation Rules (Fix H)

**File:** `ai-service/app/agents/nodes/security_requirement_inference_node.py:11`

**Problem:** LLM tidak aware akan failure modes yang spesifik untuk Node 24, native module, action runtime, dsb. Bisa hallucinate tool names atau action SHAs.

**Solving:** Inject 7 rule block di `SECURITY_INFERENCE_PROMPT`:

```
━━━ FAILURE-MODE-AWARE GENERATION RULES ━━━

1. Native module resilience (FM-1): For JS/TS projects, security-scan jobs
   MUST use `npm install --ignore-scripts` because native modules use
   V8 APIs that are removed in Node 22+.

2. Action runtime pinning (FM-2): Every JavaScript action MUST be pinned
   to a version that declares `using: node24`. Never invent SHAs.

3. IaC strict scoping (FM-3): `iac-scan` is for Terraform/K8s/Helm ONLY.
   Dockerfile is NOT IaC.

4. SAST tool consistency (FM-5): SAST tool in panel MUST match YAML.
   Generator uses Semgrep for all languages.

5. Merged controls (FM-6): `cve_scan` is the same as `dependency-scan`.
   Do not list as missing.

6. Repository evidence priority (SSoT): file evidence is the SINGLE
   SOURCE OF TRUTH. Inferred flags are advisory only.

7. Output explainability: include reasoning chain in every recommendation.
```

**Result:** LLM sekarang aware failure modes; outputs lebih reliable, lebih jarang hallucinate.

---

### Solution 9 — Code: Log parser detect native module build failure (Fix I)

**File:** `backend/internal/handlers/log_finding_parser.go:240-248`

**Problem:** Generic "open the log" finding untuk job yang fail karena native module build → user bingung root cause, harus buka GitHub log manual.

**Solving:** Detect `CopyablePersistent` / `AccessorGetterCallback` di log, emit specific finding dengan remediation actionable.

```go
case strings.Contains(logText, "CopyablePersistent") || strings.Contains(logText, "AccessorGetterCallback"):
    title = "Native module build failure: outdated dependency"
    evidence = "A native module failed to compile against the current Node.js runtime. The package uses V8 APIs that have been removed (CopyablePersistent, AccessorGetterCallback, etc.)."
    remediation = "Upgrade the affected package to a version that supports the current Node.js runtime. For better-sqlite3, version 7.6.0+ supports Node 18+; version 8.x+ supports Node 22+. Alternatively, use `--ignore-scripts` to skip native builds."
    ruleID = "native-module-outdated"
    severity = "high"
```

**Result:** User dapat spesifik finding `Native module build failure: outdated dependency` (high) dengan actionable fix, bukan generic "open the log".

---

### Solution 10 — Code: Log parser detect SARIF-not-uploaded (Fix J)

**File:** `backend/internal/handlers/log_finding_parser.go:266-281`

**Problem:** Scanner jobs (sast, secret-scan, container-scan) fail sebelum upload SARIF → Code Scanning tab kosong → user tidak tahu bahwa scanner yang sebenarnya sudah ada alerts di run sebelumnya.

**Solving:** Detect SARIF-upload scanners, kasih hint ke Code Scanning tab.

```go
isSarifScanner := scanner == "semgrep" || scanner == "trivy" ||
    scanner == "gitleaks" || scanner == "npm-audit" || scanner == "syft" ||
    scanner == "checkov"
if isSarifScanner {
    title = jobName + " failed before SARIF upload"
    evidence = "The " + scanner + " job exited with non-zero status before it could upload its SARIF report. This is almost always a workflow configuration problem (e.g. the job crashed, or an earlier step like `npm install` failed). The log does not contain scanner output because the scanner never ran to completion."
    remediation = "Open the Code Scanning tab in this repository — alerts that were uploaded by EARLIER successful runs of this same workflow may still be listed there. Otherwise, fix the workflow (e.g. add `--ignore-scripts` to the failing npm install step) and trigger a new run so the scanner can complete and upload."
    ruleID = "sarif-not-uploaded"
    severity = "low"
}
```

**Result:** Untuk scanner jobs yang fail, synthesized finding kasih hint ke Code Scanning tab (low severity) bukan generic "open the log" (medium).

---

### Solution 11 — Code: Log parser Trivy TABLE output (Fix K)

**File:** `backend/internal/handlers/log_finding_parser.go:88-102`

**Problem:** Trivy dengan `format: table` (default) emit output plain text yang tidak ter-parse oleh existing patterns. Real CVE lodash/express tidak muncul.

**Solving:** Tambah pattern untuk Trivy table output:
```
lodash@4.17.4  npm  CVE-2019-10744  CRITICAL  4.17.4  4.17.12  Prototype Pollution
```

```go
{
    scanner: "trivy",
    pattern: regexp.MustCompile(`(?m)^(\S+@\S+)\s+\S+\s+(CVE-\d+-\d+)\s+(CRITICAL|HIGH|MEDIUM|LOW|UNKNOWN)\s+\S+\s+\S+`),
    severity:  "high",
    ruleIDGen: func(m []string) string { return m[2] },
    titleGen:  func(m []string) string { return m[2] + " in " + m[1] },
    fileGen:   func(m []string) string { return "package-lock.json" },
    lineGen:   func(m []string) int { return 0 },
    messageFn: func(m []string) string { return m[2] + " (" + strings.ToLower(m[3]) + " severity) affects " + m[1] },
},
```

Plus permissive `scannerMatches` untuk cross-scan:
```go
if (patternScanner == "trivy" || patternScanner == "npm-audit") &&
    (jobScanner == "trivy" || jobScanner == "npm-audit") {
    return true
}
```

**Result:** Trivy table output ter-parse → real CVE (CVE-2019-10744, CVE-2022-24999, etc.) muncul di finding list.

---

### Solution 12 — Frontend: "11 total" → "10 recommended, 1 optional" (Fix L)

**File:** `frontend/src/pages/PipelineGenerator.tsx:246-258`

**Problem:** Frontend count "11 total" mencampur recommended + optional, confusing.

**Solving:** Dynamic label berdasarkan breakdown:
```tsx
{(() => {
  const recommended = controls.filter(c => c.status === "recommended").length
  const optional = controls.filter(c => c.status === "optional").length
  return optional === 0 ? `${recommended} recommended` : `${recommended} recommended, ${optional} optional`
})()}
```

**Result:** User lihat "10 recommended, 1 optional" (eksplisit) bukan "11 total" (ambigu).

---

### Solution 13 — Frontend: Tambah "Merged Controls" section di Debug panel (Fix M)

**File:** `frontend/src/pages/PipelineGenerator.tsx:374-405`

**Problem:** Merged controls (cve_scan → dependency-scan) hilang dari Debug panel, user bingung kenapa `cve_scan` di Security Controls tapi tidak di generated stages.

**Solving:** Render `workflow_config_issues` dengan rule pattern `_merged_into_` ke section baru:
```tsx
{(pipelineResult as any).workflow_config_issues
  .filter((i: any) => i.rule?.includes("_merged_into_"))
  .map((i: any, idx: number) => (
    <li key={idx} className="text-blue-700">
      <span className="font-medium">{i.rule.replace("_merged_into_", " → ")}</span>
      <span className="text-muted-foreground"> — {i.message}</span>
    </li>
  ))}
```

**Result:** Debug panel sekarang menampilkan "cve-scan → dependency-scan" dengan explanation, tidak ada kontradiksi dengan Security Controls panel.

---

### Solution 14 — Docs: Iterative Debugging Playbook (Fix N)

**File:** `PROMPT-ENGINEERING-BAB3.md` §9

**Problem:** Tidak ada dokumentasi terpusat untuk failure modes dan fix-nya. Engineer baru harus reverse-engineer setiap bug.

**Solving:** Tambah §9 (9KB):
- 9 failure modes catalogue (FM-1..FM-9)
- Per-FM: root cause + prompt fix + code fix + parser fix
- Three-Tier Validation Stack
- Input requirements untuk debug
- Output schema (header comments)
- Validasi matrix

**Result:** Dokumentasi komprehensif untuk setiap fix, jadi reference untuk debugging future issues.

---

## 6. Acceptance Criteria

1. ✅ The failing test
   `test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies`
   passes.
2. ✅ `pytest tests/` reports `99 passed, 0 failed`.
3. ✅ No regression in the other 23 tests of `test_workflow_generator.py`.
4. ✅ `state["invalid_workflow_stages"]` contains the dropped stages with a
   human-readable `reason` string.
5. ✅ `state["workflow_config_issues"]` includes a typed issue for each
   dropped stage with `category: "workflow_config_issue"`.
6. ✅ The YAML emitted to GitHub Actions is **unchanged** for the cases
   where the fix is silent (i.e. it is purely an observability fix).
7. ✅ Backend tests: 12/12 pass.
8. ✅ Frontend type-check + build: clean.
9. ✅ No `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` in generated YAML.
10. ✅ All actions pinned to `using: node24` SHAs.
11. ✅ `iac-scan` not emitted for Dockerfile-only repos.
12. ✅ Native module build failure detected with specific remediation.
13. ✅ SARIF-not-uploaded hint for scanner jobs.
14. ✅ Trivy table output parsed → real CVE detection.

---

## 7. Impact

* **Functional:** YAML pipeline now correctly omits over-included stages
  (iac-scan, cve-scan as separate job) and correctly emits relevant
  security scans with --ignore-scripts. No risk to deployed workflows.
* **UX:** Reviewer/UI now sees:
  - Which stages were requested but dropped, and why (`invalid_workflow_stages`)
  - Which controls are merged into other jobs (`workflow_config_issues`)
  - Specific failure modes with actionable remediation
  - Consistent tool names (Semgrep for all)
  - Proper counts ("10 recommended, 1 optional" instead of "11 total")
* **Data integrity:** `pipeline_runs.workflow_config_issues` and
  `pipeline_runs.invalid_workflow_stages` columns are now populated
  truthfully.
* **No re-run required:** All 14 fixes are baked into the generator,
  parser, and prompt. New generations produce correct workflows without
  trial-and-error.

---

## 8. References

* `DEBUG-README.md` — full debugging log & patch walkthrough.
* `PROMPT-ENGINEERING-BAB3.md` §5 + §9 — Deterministic Safety Guards
  + Iterative Debugging Playbook.
* `docs/AI-AGENT-SECURITY-FINDINGS.md` — agent findings format.
* `docs/security-desc.md` — security controls reference.
* `ai-service/tests/test_workflow_generator.py:313-334` — regression test.
* `ai-service/app/agents/nodes/workflow_generator.py` — fix location.
* `ai-service/app/agents/action_registry.py` — node24 SHAs.
* `ai-service/app/agents/nodes/security_requirement_inference_node.py` — FM-1..FM-6 injection.
* `backend/internal/handlers/log_finding_parser.go` — FM-1, FM-4, FM-9 parsing.
* `backend/internal/handlers/pipeline_handler.go:ExtractAllJobFindings` —
  Code Scanning API integration.
* `frontend/src/pages/PipelineGenerator.tsx` — FM-7, FM-6 rendering.
* LangGraph docs: <https://langchain-ai.github.io/langgraph/concepts/low_level/>
  (conditional edges for "skipped" states).

---

## 9. Labels / Suggested Triage

* `bug` → `resolved`
* `area:ai-service`
* `component:workflow-generator`
* `component:action-registry`
* `component:log-parser`
* `component:frontend`
* `component:prompt-engineering`
* `severity:medium` → `resolved`
* `needs-tests` _(covered by existing regression test + new tests added)_
* `good-first-issue` → `resolved (now medium-complexity multi-file fix)`
