# DEBUG — AI Agent Pipeline Generation Inconsistencies

> **Scope:** Mendokumentasikan proses _debugging_ masalah _pipeline generation_
> yang kadang **inkonsisten** dan **konflik _dependencies_** pada AI Agent
> (`ai-service`).
>
> **Status:** ✅ _Root cause_ teridentifikasi — _regression test_ sudah ada
> tetapi kode produksi belum men-_surface_ pelanggaran ke
> `invalid_workflow_stages`. 1 test gagal dari total 99 test.

---

## 1. Ringkasan Masalah

| Item | Detail |
|---|---|
| **Gejala** | Pipeline hasil generate bisa jadi terlalu _rigid_ (drop stage yang sebenarnya diminta) atau _kebablasan_ (meng-`include` job yang tidak ada evidence di repo). |
| **Dampak** | Reviewer tidak tahu stage mana yang sengaja di-drop karena _lying flag_ vs. _intentional_ — sehingga `workflow_config_issues` kosong padahal ada mismatch. |
| **Test gagal** | `tests/test_workflow_generator.py::test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies` |
| **Total test** | 99 (1 failed, 98 passed) |
| **Penyebab** | `_select_relevant_stages()` menyaring stage berdasarkan _file evidence_ **sebelum** `_flag_invalid_stages()` dipanggil, sehingga stage yang di-drop karena kontradiksi tidak pernah masuk ke `invalid_workflow_stages`. |

---

## 2. Cara Reproduksi (Local)

```bash
cd ai-service
source .venv/bin/activate
python -m pytest tests/test_workflow_generator.py::test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies -x
```

**Output gagal:**
```
E       assert False
E        +  where False = any(<generator ...>)
tests/test_workflow_generator.py:333: AssertionError
```

**Input _state_ pemicu:**
```python
state = _minimal_state(
    detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
    detected_deployment={"docker": True, "docker_confidence": 0.9},  # ← "lying" flag
    inferred_security_needs={
        "security_controls": [
            {"control": "sast",            "status": "recommended"},
            {"control": "container_scan",  "status": "recommended"},
            {"control": "container_build", "status": "recommended"},
            {"control": "iac_scan",        "status": "recommended"},
        ]
    },
)
# repository_structure = []      ← tidak ada Dockerfile
# repository_files    = {}        ← tidak ada file evidence
```

**Ekspektasi test:**
1. `container-scan`, `container-build`, `iac-scan` **tidak boleh** muncul di `generated_stages`.
2. `container-scan` dan `iac-scan` **harus** muncul di `invalid_workflow_stages`
   (sebagai sinyal ke reviewer / frontend).

**Aktual (saat ini):**
- ✅ `container-scan` dst. tidak muncul di `generated_stages`.
- ❌ `invalid_workflow_stages` kosong → reviewer tidak diberi tahu.

---

## 3. Metodologi Debug (Research-Backed)

Pendekatan ini memadukan _forebear_ (praktik lama yang terbukti) dan referensi
_github solution_ kontemporer.

### 3.1. Forebear Practices (Prinsip Klasik)

1. **Single Source of Truth (SSoT)** — _file evidence_ repo harus jadi satu-
   satunya penentu apakah sebuah stage di-`include`. Flag _inferred_ (mis.
   `detected_deployment.docker`) hanya bersifat _advisory_.
2. **Fail-Loud, Not Silent** — kalau input (_security controls_) kontradiktif
   dengan evidence, harus ada _trace_ eksplisit (`invalid_workflow_stages` +
   `workflow_config_issues`). Silent drop = _bug_ yang sulit dilacak.
3. **Test-First Triage** — _regression test_ yang sudah ada (yang gagal)
   memandu kita ke lokasi kode yang harus di-_patch_; tidak perlu _guess_.
4. **Separation of Concerns** — `select → flag → filter` adalah tiga langkah
   berbeda; jangan digabung, supaya setiap langkah punya _output_ yang bisa
   di-_assert_.

### 3.2. Referensi GitHub Solution (Modern Patterns)

| Pola | Referensi | Aplikasi |
|---|---|---|
| **Pipeline as DAG with explicit "skipped" edges** | [LangGraph: Conditional Edges](https://langchain-ai.github.io/langgraph/concepts/low_level/) | Tiap stage yang di-skip harus punya edge eksplisit agar _observability_ jelas. |
| **Structured Output Validation** | [GitHub: stop returning plain text from LLM](https://github.com/orgs/community/discussions/…) | Pakai `workflow_config_issues` sebagai _typed_ list (bukan string) supaya UI bisa render. |
| **Repository Evidence > Inferred Flags** | [Semgrep / Trivy docs: always re-scan source](https://github.com/aquasecurity/trivy-action) | Flag _deployment_ dari LLM bisa _stale_; file list dari GitHub API adalah kebenaran. |
| **Deterministic Safety Guard** | [LangChain: OutputFixingParser](https://python.langchain.com/) | Setiap node LLM punya _fallback_ deterministik (lihat `PROMPT-ENGINEERING-BAB3.md` §5). |

### 3.3. Strategi Debug Berlapis

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1 — Reproduce (RED)                                │
│   pytest tests/test_workflow_generator.py -x             │
├──────────────────────────────────────────────────────────┤
│ Layer 2 — Localize (PINK)                                │
│   - Baca test → identifikasi input & expected output     │
│   - Telusuri alur: select → flag → filter                │
├──────────────────────────────────────────────────────────┤
│ Layer 3 — Diagnose (ORANGE)                              │
│   - Cetak [DEBUG] stages setelah _select_relevant_stages │
│   - Lihat: container-scan HILANG sebelum masuk _flag     │
├──────────────────────────────────────────────────────────┤
│ Layer 4 — Patch (GREEN)                                  │
│   - Pindahkan _flag_invalid_stages agar menerima _list_  │
│     stage "requested tapi tak punya evidence"            │
│   - Tambahkan juga detection dari "lying deployment flag"│
├──────────────────────────────────────────────────────────┤
│ Layer 5 — Verify (BLUE)                                  │
│   - pytest tests/                                        │
│   - pytest tests/test_workflow_generator.py -v           │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Root Cause Analysis

### 4.1. Kode yang relevan (`ai-service/app/agents/nodes/workflow_generator.py`)

| Baris | Potongan | Masalah |
|---|---|---|
| 309–317 | `stages = _select_relevant_stages(...)` | Hanya me-return stage yang punya _evidence_. Stage yang "diminta tapi tak ada evidence" **langsung hilang** di sini. |
| 324 | `invalid_stages = _flag_invalid_stages(stages, state)` | Karena `stages` sudah bersih, loop di `_flag_invalid_stages` tidak menemukan stage _container/_iac_ → `invalid_stages = []`. |
| 325 | `stages = _filter_stages_by_evidence(stages, state)` | Sebenarnya _redundant_ kalau `_select_relevant_stages` sudah mem-filter; perlu diaudit ulang. |
| 366–378 | `state["invalid_workflow_stages"] = invalid_stages` | Karena `invalid_stages = []`, key ini tidak pernah di-set. |

### 4.2. Alur yang diharapkan (target design)

```
requested controls ─┐
                   │
file evidence ─────┼──► [DECIDE per stage] ──► keep | drop_with_reason
                   │            │
deployment flag ───┘            ▼
                          invalid_workflow_stages[]
                                │
                                ▼
                   workflow_config_issues (typed list)
                                │
                                ▼
                          Frontend (badge "⚠ 2 stages dropped")
```

### 4.3. Solusi (Ringkas)

> Lihat §5 untuk patch kode.

Tambah fungsi `_collect_unjustified_requested_stages(state)` yang **sebelum**
memanggil `_select_relevant_stages` memeriksa _semua_ kontrol yang diminta,
lalu mem-flag tiap stage yang tidak punya _file evidence_ — termasuk yang
tidak lolos `_select_relevant_stages`.

---

## 5. Patch (Ringkas)

> Patch detail ada di commit berikutnya. Inti perubahan:

```python
# workflow_generator.py — di dalam workflow_generator_node()

# 1. Kumpulkan kontrol yang diminta user (security inference).
requested = _collect_requested_controls(security)

# 2. Tentukan stage yang punya evidence di repo (file-based).
file_evidence_stages = _select_relevant_stages(...)

# 3. Tandai stage yang diminta tapi tidak punya evidence → MASUK invalid list.
unjustified = []
technologies = state.get("detected_technologies", {}) or {}
structure   = state.get("repository_structure", []) or []
files       = state.get("repository_files", {}) or {}
has_docker  = _has_dockerfile(structure, files)
has_iac     = _has_iac(structure, files)
has_test    = bool(technologies.get("test_framework"))

for ctrl in ("container-scan", "container-build", "sbom"):
    if ctrl in requested and not has_docker:
        unjustified.append({
            "stage": ctrl,
            "expected": False,
            "reason": f"'{ctrl}' was requested but no Dockerfile detected "
                      f"in repository analysis (inferred deployment flag "
                      f"may be stale).",
        })
for ctrl in ("iac-scan",):
    if ctrl in requested and not has_iac:
        unjustified.append({...})
for ctrl in ("test",):
    if ctrl in requested and not has_test:
        unjustified.append({...})

# 4. Filter stages untuk YAML final.
final_stages = [s for s in file_evidence_stages if s not in {u["stage"] for u in unjustified}]

# 5. Surface ke state.
if unjustified:
    state["invalid_workflow_stages"] = unjustified
    state["workflow_config_issues"] = (state.get("workflow_config_issues") or []) + [
        {"rule": f"unjustified_{u['stage']}",
         "message": f"Stage '{u['stage']}' requested but lacks evidence: {u['reason']}",
         "category": "workflow_config_issue"}
        for u in unjustified
    ]
```

---

## 6. Verifikasi

```bash
# Test yang tadinya gagal
pytest tests/test_workflow_generator.py::test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies -v

# Seluruh suite
pytest tests/ -v
```

**Target:** `99 passed, 0 failed`.

---

## 7. Daftar File Terkait

| File | Peran |
|---|---|
| `ai-service/app/agents/nodes/workflow_generator.py` | _Generator_ workflow (sumber bug). |
| `ai-service/app/agents/nodes/workflow_validator.py` | Validator pasca-generate. |
| `ai-service/app/agents/pipeline_graph.py` | Orchestrator LangGraph. |
| `ai-service/app/agents/pipeline_state.py` | Skema state pipeline. |
| `ai-service/app/services/pipeline_service.py` | Service yang memanggil graph. |
| `ai-service/tests/test_workflow_generator.py` | _Regression test_ (sudah mencakup kasus ini). |
| `docs/AI-AGENT-SECURITY-FINDINGS.md` | Catatan keamanan agent. |
| `PROMPT-ENGINEERING-BAB3.md` | Daftar 9 LLM persona & safety guard. |

---

## 8. Lampiran: Skenario Mirip yang Sudah Tertangani

| Skenario | Test | Status |
|---|---|---|
| Tanpa test framework, minta stage `test` | `test_workflow_generator_node_drops_test_job_when_no_framework` | ✅ PASS |
| Tanpa Dockerfile, minta `container_*` | `test_workflow_generator_node_drops_container_jobs_without_dockerfile` | ✅ PASS |
| **Deployment flag bohong, minta `container_*` + `iac_*`** | `test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies` | ❌ **FAIL** |
| Dockerfile ada, minta `container_scan` | `test_workflow_generator_node_includes_container_jobs_with_dockerfile` | ✅ PASS |

Baris ketiga adalah yang sedang diperbaiki.

---

_Dokumen ini disusun mengikuti pola: **reproduce → localize → diagnose →
patch → verify**, gabungan praktik _forebear_ (SSoT, fail-loud, test-first)
dan referensi _github solution_ (LangGraph conditional edges, OutputFixing
parser, deterministic fallback)._
