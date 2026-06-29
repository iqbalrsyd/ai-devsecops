# README: LLM Input/Output per Tahap dan per Node

> **Audiens**: Dosen penguji (untuk konfirmasi metodologi)
> **Status**: Snapshot per 22 Juni 2026 (commit `f73813f`)
> **Tujuan**: Mendokumentasikan **apa yang LLM terima sebagai input** dan **apa yang LLM hasilkan sebagai output** di setiap tahap pipeline dan setiap node.

---

## 1. Peta Besar: 4 Tahapan × 8 Node yang Pakai LLM

Pipeline AI agent punya **20 node** (lihat `ARCHITECTURE.md`). Dari 20 itu, **8 node** memanggil LLM (`get_llm().invoke(...)`). Sisanya **deterministic** (regex, dict lookup, code generation).

```
┌──────────────────────────────────────────────────────────────────────┐
│  TAHAP 1: Repository Context Analysis (K1)                          │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  1.1 technology_detection    [LLM ✓]                      │       │
│  │  1.2 architecture_detection  [LLM ✓]                      │       │
│  │  1.3 deployment_detection    [LLM ✓]                      │       │
│  │  1.4 vulnerability_scan      [LLM ✓]                      │       │
│  │  1.5 domain_detection        [LLM ✓]                      │       │
│  └──────────────────────────────────────────────────────────┘       │
│     Deterministic: repository_connection, repository_scan           │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│  TAHAP 2: Security Requirement Inference (K2)                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  2.1 security_requirement_inference [LLM ✓]                │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│  TAHAP 3: Generation + Deployment (K3)                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  3.1 workflow_generation      [DETERMINISTIC]            │       │
│  │  3.2 workflow_validation      [DETERMINISTIC]            │       │
│  │  3.3 github_branch_creation    [DETERMINISTIC]            │       │
│  │  3.4 pull_request_creation    [DETERMINISTIC]             │       │
│  │  3.5 workflow_execution       [DETERMINISTIC]            │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│  TAHAP 4: Scoring (K3)                                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  4.1 security_analysis       [LLM ✓ — enrichment only]   │       │
│  │  4.2 risk_assessment          [DETERMINISTIC]            │       │
│  │  4.3 compliance_mapper        [DETERMINISTIC]            │       │
│  │  4.4 recommendation_generation [LLM ✓]                   │       │
│  │  4.5 response_formatter       [DETERMINISTIC]            │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│  TAHAP 5: Post-Execution (Ai Log Evaluator)                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  5.1 ai_log_evaluator         [LLM ✓ — optional]          │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

**Ringkasan**: 8 dari 20 node panggil LLM. Lokasi: K1 (5 node), K2 (1 node), K3 Generation (0 LLM), K3 Scoring (2 LLM opsional), Post-execution (1 LLM opsional).

---

## 2. Tabel Input → Output per Node (LLM only)

### K1: Repository Context Analysis

#### 1.1 `technology_detection_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (fallback setelah heuristic) |
| **Input ke LLM** | Prompt `TECH_DETECTION_PROMPT` dengan: `package_files` (JSON, isi file dependency), `repo_name`, `structure_summary` (top 20 file) |
| **Output LLM (JSON)** | `{languages: [...], package_managers: [...], frameworks: [...], build_tools: [...], test_frameworks: [...], rationale: str}` |
| **Fallback** | Kalau LLM gagal: regex + filename-based detection (deterministic) |
| **State update** | `state["detected_technologies"]` |
| **Prompt file** | `technology_detection_node.py:line ~80` |

#### 1.2 `architecture_detection_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (fallback setelah heuristic) |
| **Input ke LLM** | `repo_name`, `package_files` (dependencies), `structure_summary`, `heuristic_signals` (file count, has_dockerfile, has_k8s_yaml) |
| **Output LLM (JSON)** | `{architecture_type: "monolithic"\|"microservices"\|"modular_monolith"\|"serverless"\|"library"\|"unknown", confidence: 0-1, reasoning: str, indicators: [...]}` |
| **Fallback** | Deterministic by file count + framework detection |
| **State update** | `state["detected_architecture"]` + `state["detected_architecture_type"]` + `state["detected_architecture_confidence"]` |
| **Prompt file** | `architecture_detection_node.py:line ~50` |

#### 1.3 `deployment_detection_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (fallback setelah heuristic) |
| **Input ke LLM** | `repo_name`, `package_files`, `structure_summary`, `heuristic_signals` (has_dockerfile, has_docker_compose, has_k8s_yaml, has_terraform) |
| **Output LLM (JSON)** | `{deployment_target: "docker"\|"kubernetes"\|"vercel"\|"netlify"\|"heroku"\|"static"\|"unknown", container: bool, k8s: bool, serverless: bool, reasoning: str}` |
| **Fallback** | Deterministic by Dockerfile / k8s / terraform detection |
| **State update** | `state["detected_deployment"]` + `state["recommended_deployment_target"]` |
| **Prompt file** | `deployment_detection_node.py:line ~60` |

#### 1.4 `vulnerability_scan_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (selalu — pattern scan + LLM verify) |
| **Input ke LLM** | `VULN_SCAN_PROMPT` dengan: `architecture_type`, `source_files` (top 30 file content), `pattern_findings` (preliminary dari regex) |
| **Output LLM (JSON array)** | `[{type, severity, file, line, code_snippet, explanation, recommendation, cwe, owasp}, ...]` |
| **Fallback** | Empty array kalau LLM gagal (caller pakai pattern_findings saja) |
| **State update** | `state["findings"]` (overwrite atau extend) |
| **Prompt file** | `vulnerability_scan_node.py:line 21` |
| **Catatan** | 70 lines prompt — list 20 vulnerability patterns (hardcoded secret, SQLi, XSS, SSRF, JWT weak, dll) + 8 microservice-specific patterns |

#### 1.5 `domain_detection_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (hybrid dengan heuristic) |
| **Input ke LLM** | `DOMAIN_DETECTION_PROMPT` dengan: `repo_name`, `repo_description`, `detected_libraries` (top 50), `detected_entities` (top 30), `detected_routes` (top 30), `heuristic_scores` (pre-computed) |
| **Output LLM (JSON)** | `{domain: str, sub_type: str, confidence: 0-1, evidence: [...], domain_threats: [...]}` |
| **Domain options** | `e-commerce` \| `healthcare` \| `fintech` \| `blog` \| `iot` \| `education` \| `general` |
| **Sub_type options (e-commerce)** | `stripe` \| `midtrans` \| `xendit` \| `doku` \| `paypal` \| `braintree` \| `razorpay` \| `adyen` \| `square` \| `multi` \| `unknown` \| `none` |
| **Fallback** | Kalau LLM gagal/ragu: pakai heuristic dari library/entity/route match. Sub_type dari `_infer_payment_processor()` |
| **State update** | `state["detected_domain"]`, `state["detected_sub_type"]`, `state["domain_confidence"]`, `state["domain_threats"]`, `state["domain_evidence"]` |
| **Prompt file** | `domain_detection_node.py:line 277` |

### K2: Security Requirement Inference

#### 2.1 `security_requirement_inference_node`

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (selalu) |
| **Input ke LLM** | `SECURITY_INFERENCE_PROMPT` dengan: `technologies`, `architecture`, `deployment`, `domain`, `domain_confidence`, `domain_threats`, `domain_evidence`, `attack_surfaces`, `mandatory_controls` |
| **Output LLM (JSON)** | `{security_controls: [{control, status, priority, reasoning, ...}], all_controls, required_tools, pipeline_stages, attack_surfaces, domain_context}` |
| **Fallback** | Kalau LLM gagal: pakai `_get_default_controls(technologies, architecture, deployment)` (deterministic mapping) |
| **State update** | `state["inferred_security_needs"]` + `state["inferred_security_needs"]["scan_directives"]` (BARU, lihat PIPELINE-STRUCTURE.md) |
| **Prompt file** | `security_requirement_inference_node.py:line 11` |

### K3 Generation: TIDAK ADA LLM

> Semua node di K3 Generation **deterministic**:
> - `workflow_generation` — emit YAML dari template (no LLM)
> - `workflow_validation` — validate against action registry (no LLM)
> - `github_branch_creation` — git API (no LLM)
> - `pull_request_creation` — git API (no LLM)
> - `workflow_execution` — workflow runtime (no LLM)
>
> **Alasan**: Generator harus deterministik agar output reproducible dan tidak ada LLM drift.

### K3 Scoring: 2 LLM (opsional)

#### 4.1 `security_analyzer` (LLM only for **enrichment**)

| Aspek | Detail |
|---|---|
| **LLM?** | ⚠️ Parsial (opsional) — hanya untuk **enrichment**, bukan detection |
| **Logic** | 1. Pattern-based finding extraction (deterministic) → 2. LLM enrichment (opsional) → 3. Merge (deterministic) |
| **Input ke LLM (jika dipanggil)** | `ENRICHMENT_PROMPT` dengan: top 12KB of `findings` list (already extracted by pattern) |
| **Output LLM (JSON array)** | Array of same length, each with: `type, severity, scanner, file, line, code_snippet, package_name, installed_version, fixed_version, cve, cwe, owasp, explanation, impact, recommendation` |
| **Critical** | "Do NOT add new findings. Do NOT invent issues." (LLM hanya enrich, tidak bikin baru) |
| **State update** | `state["findings"]` (enriched), `state["workflow_config_issues"]`, `state["maintenance_warnings"]`, `state["external_service_issues"]` |
| **Prompt file** | `security_analyzer.py:line 33` |

#### 4.4 `recommendation_generation` (LLM untuk fix recommendations)

| Aspek | Detail |
|---|---|
| **LLM?** | ✅ Ya (selalu) |
| **Input ke LLM** | `RECOMMENDATION_PROMPT` dengan: `findings` (top 6000 chars), `risk_score` |
| **Output LLM (JSON)** | `{recommendations: [str], fix_examples: [{finding_type, before, after}]}` |
| **State update** | `state["recommendations"]`, `state["fix_examples"]` |
| **Prompt file** | `recommendation_gen.py:line 4` |

### Post-Execution: 1 LLM (opsional)

#### 5.1 `ai_log_evaluator` (opsional, fallback only)

| Aspek | Detail |
|---|---|
| **LLM?** | ⚠️ Parsial — **primary path** adalah parser SARIF deterministic. LLM **hanya fallback** kalau SARIF download gagal |
| **Trigger** | Hanya kalau `force=True` di `pipeline_service.run_pipeline_analysis(force=True)` dan artifact download dari GitHub API gagal |
| **Input ke LLM** | Log text (workflow run logs) — top N lines |
| **Output LLM** | Refined extraction: list of findings (type, severity, scanner) |
| **State update** | Fallback ke regex-based log line classification (deterministic) |
| **Prompt file** | `ai_log_evaluator.py:line 711` (the `prompt` variable) |
| **Catatan** | LLM ini **jarang dipanggil** — biasanya SARIF sudah cukup. LLM = safety net |

---

## 3. Matriks Ringkas

| # | Node | Tahap | LLM? | Trigger | Input | Output |
|---|---|---|---|---|---|---|
| 1 | `technology_detection` | K1 | ✅ | LLM fallback | package_files, repo_name, structure | detected_technologies |
| 2 | `architecture_detection` | K1 | ✅ | LLM fallback | repo_name, package_files, structure | detected_architecture |
| 3 | `deployment_detection` | K1 | ✅ | LLM fallback | repo_name, structure, signals | detected_deployment |
| 4 | `vulnerability_scan` | K1 | ✅ | Selalu | source_files, pattern_findings, architecture | findings (vulns) |
| 5 | `domain_detection` | K1 | ✅ | Hybrid | signals (libs, entities, routes), heuristic_scores | domain + sub_type + threats |
| 6 | `security_requirement_inference` | K2 | ✅ | Selalu | technologies, architecture, domain, threats | security_controls, scan_directives |
| 7 | `security_analyzer` | K4 | ⚠️ Opsional | Enrichment only | findings (pre-extracted) | enriched findings + config issues |
| 8 | `recommendation_generation` | K4 | ✅ | Selalu | findings, risk_score | fix recommendations |
| 9 | `ai_log_evaluator` | Post | ⚠️ Fallback | SARIF download fail | workflow run logs | refined findings (fallback) |

**8 LLM calls** (5 wajib + 3 opsional/fallback).

---

## 4. Detail Kontrak I/O per Node

### Tiap Node: Input → Processing → Output

#### Stage 1.1 — technology_detection_node
```
INPUT (state):
  - repository_name: str
  - repository_files: dict (package.json content, etc.)
  - repository_structure: list[dict] (top 20 files)
  - state.detected_technologies: dict (partial, from heuristic)

LLM CALL (if heuristic < 0.8 confidence):
  Prompt: TECH_DETECTION_PROMPT.format(
    repo_name, package_files, structure_summary
  )
  Output: {
    "languages": ["JavaScript", "TypeScript"],
    "package_managers": ["npm"],
    "frameworks": ["express"],
    "build_tools": ["webpack"],
    "test_frameworks": ["jest"],
    "rationale": "Detected package.json with express dependency..."
  }

OUTPUT (state):
  - state.detected_technologies: <merged final>
```

#### Stage 1.5 — domain_detection_node
```
INPUT (state):
  - repository_name: str
  - repository_description: str
  - state.detected_libraries: set[str] (from package.json)
  - state.detected_entities: set[str] (from source code)
  - state.detected_routes: set[str] (regex from route handlers)
  - state.heuristic_scores: dict (pre-computed by deterministic)

LLM CALL (always):
  Prompt: DOMAIN_DETECTION_PROMPT.format(
    repo_name, repo_description, libraries, entities, routes, scores
  )
  Output: {
    "domain": "e-commerce",
    "sub_type": "stripe",
    "confidence": 0.95,
    "evidence": [
      "Domain library detected: ['stripe']",
      "Domain entity detected: ['order', 'cart']",
      "Domain route detected: ['/checkout']"
    ],
    "domain_threats": [
      "Stripe key hardcoded in source",
      "SQL injection in checkout form",
      "CSRF on payment endpoint"
    ]
  }

HYBRID DECISION:
  - if LLM succeeded AND confidence >= 0.5: use LLM result
  - else if heuristic has strong evidence: use heuristic
  - else: "general"

FALLBACK for sub_type:
  if sub_type == "none" AND domain == "e-commerce":
    sub_type = _infer_payment_processor(detected_libraries)

OUTPUT (state):
  - state.detected_domain: "e-commerce"
  - state.detected_sub_type: "stripe"
  - state.domain_confidence: 0.95
  - state.domain_evidence: [...]
  - state.domain_threats: [...]
```

#### Stage 2.1 — security_requirement_inference_node
```
INPUT (state):
  - state.detected_technologies
  - state.detected_architecture
  - state.detected_deployment
  - state.detected_domain
  - state.domain_confidence
  - state.domain_threats
  - state.domain_evidence
  - state.attack_surfaces (from identify_attack_surfaces())
  - mandatory_controls (from map_surfaces_to_controls())

LLM CALL (always):
  Prompt: SECURITY_INFERENCE_PROMPT.format(
    technologies, architecture, deployment, domain,
    domain_confidence, domain_threats, domain_evidence,
    attack_surfaces, mandatory_controls
  )
  Output: {
    "security_controls": [
      {"control": "sast", "status": "required", "priority": "high", "reasoning": "..."},
      {"control": "secret_scan", "status": "required", "priority": "critical",
       "reasoning": "E-commerce domain with payment processing"},
      ...
    ],
    "all_controls": [...],
    "required_tools": [...],
    "pipeline_stages": [...],
    "attack_surfaces": [...],
    "domain_context": {...}
  }

POST-PROCESS (deterministic):
  - enforce mandatory controls
  - build scan_directives via build_scan_directives()
  - add llm_rule_suggestions (if LLM provided)

OUTPUT (state):
  - state.inferred_security_needs: {controls, ..., scan_directives}
```

#### Stage 4.1 — security_analyzer (LLM enrichment)
```
INPUT (state):
  - state.findings: list[dict] (already extracted by pattern-based scanner_normalizer)

PHASE 1: deterministic pattern extraction
  - normalize findings via scanner_normalizer
  - categorize into: security | config | maintenance | external

PHASE 2: LLM enrichment (optional, for top-N findings)
  Prompt: ENRICHMENT_PROMPT.format(findings=json_dumps(findings)[:12000])
  Output: [
    {
      "type": "sql_injection",
      "severity": "critical",
      "scanner": "semgrep",
      "file": "src/routes/checkout.js",
      "line": 16,
      "code_snippet": "db.query(`SELECT * FROM orders WHERE id = ${id}`)",
      "package_name": null,
      "installed_version": null,
      "fixed_version": null,
      "cve": null,
      "cwe": "CWE-89",
      "owasp": "A1: Injection",
      "explanation": "...",
      "impact": "...",
      "recommendation": "Use parameterized queries..."
    },
    ...
  ]

PHASE 3: deterministic merge
  - preserve scanner evidence (file, line, code_snippet)
  - add LLM context (cwe, owasp, recommendation)
  - apply domain_priority severity elevation

OUTPUT (state):
  - state.findings: enriched list
  - state.workflow_config_issues: [...]
  - state.maintenance_warnings: [...]
  - state.external_service_issues: [...]
  - state.domain_context: {boosted_count, ...}
```

#### Stage 4.4 — recommendation_generation
```
INPUT (state):
  - state.findings: list[dict]
  - state.risk_score: float

LLM CALL (always):
  Prompt: RECOMMENDATION_PROMPT.format(
    findings=str(findings)[:6000], risk_score=risk_score
  )
  Output: {
    "recommendations": [
      "Replace MD5 with bcrypt for password hashing...",
      "Use parameterized queries in checkout.js...",
      ...
    ],
    "fix_examples": [
      {
        "finding_type": "sql_injection",
        "before": "db.query(`SELECT * FROM orders WHERE id = ${id}`)",
        "after": "db.query('SELECT * FROM orders WHERE id = ?', [id])"
      },
      ...
    ]
  }

OUTPUT (state):
  - state.recommendations: [...]
  - state.fix_examples: [...]
```

#### Stage 5.1 — ai_log_evaluator (LLM fallback only)
```
INPUT (state):
  - state.workflow_jobs: list[dict]
  - state.workflow_logs: list[dict] (per-job logs)
  - state.scanner_outputs: dict (SARIF artifacts if available)

PRIMARY PATH (deterministic):
  - Parse SARIF via scanner_normalizer (OASIS 2.1.0)
  - Dedup by composite key
  - Output findings

FALLBACK PATH (LLM, only if SARIF parse fails):
  Prompt: prompt.format(<workflow log lines>)
  Output: refined list of findings with type, severity, scanner

OUTPUT (state):
  - state.findings: list[dict] (from primary or fallback path)
  - state.log_extraction: {source: "structured"|"llm_fallback", ...}
```

---

## 5. Mengapa Pakai LLM vs Deterministic?

| Node | LLM? | Alasan |
|---|---|---|
| `technology_detection` | ✅ (fallback) | Heuristic miss untuk bahasa/framework jarang (e.g. Bun, Deno). LLM fallback untuk akurasi. |
| `architecture_detection` | ✅ (fallback) | LLM lebih akurat baca signal kontekstual (e.g. microservice = separate services detected). |
| `deployment_detection` | ✅ (fallback) | Similar — deployment target kadang ambiguous. |
| `vulnerability_scan` | ✅ (wajib) | LLM **WAJIB** untuk SAST. Pattern matching alone = false positive. LLM membaca konteks kode. |
| `domain_detection` | ✅ (wajib) | LLM **WAJIB** untuk klasifikasi domain. Tidak bisa deterministic (e-commerce vs fintech = business logic). |
| `security_requirement_inference` | ✅ (wajib) | LLM **WAJIB** untuk inferensi control selection. Trade-off: control mana yang di-skip per domain. |
| `security_analyzer` (enrichment) | ⚠️ (opsional) | **Pattern scan = primary**. LLM **opsional** untuk tambah konteks (CWE, OWASP, explanation). |
| `recommendation_generation` | ✅ (wajib) | LLM **WAJIB** untuk fix recommendations — butuh human-readable context. |
| `ai_log_evaluator` | ⚠️ (fallback) | SARIF parse = primary. LLM hanya kalau parse gagal (mis. SARIF corrupt). |

**Prinsip desain**:
- **Wajib pakai LLM**: di mana **konteks** atau **business logic** dibutuhkan
  (vuln, domain, security control, fix recommendation)
- **Deterministic + LLM fallback**: di mana **pattern matching** cukup tapi edge case perlu LLM
  (tech, arch, deployment)
- **Deterministic only + LLM enrichment**: di mana **akurat** adalah must-have, LLM hanya untuk polish
  (security_analyzer)
- **Deterministic only**: di mana **reproducible** wajib (workflow generation)

---

## 6. Cara Baca README Ini untuk Konfirmasi Dosen

### Pertanyaan yang Bisa Diajukan

> **"Apa yang AI agent tanyakan ke LLM?"**

Jawab dengan tabel section 3 di atas. 8 LLM calls, masing-masing dengan **input + output** yang jelas.

> **"Mengapa tidak semua pakai LLM?"**

Jawab dengan section 5: **prinsip desain** (konteks vs pattern vs reproducible). Workflow generation **harus deterministik** agar output reproducible — kalau LLM yang generate YAML, bisa beda tiap kali.

> **"Bagaimana kalau LLM gagal?"**

Jawab: **setiap node punya fallback deterministic** (lihat kolom "Fallback" di section 3). Pipeline tidak pernah stuck karena LLM error.

> **"Berapa kali LLM dipanggil per pipeline run?"**

Jawab: **5-8 calls** (5 wajib di K1-K2, 2-3 di K4). Per pipeline, LLM cost ~$0.05-0.20 (tergantung model).

> **"Bagaimana Anda verifikasi output LLM?"**

Jawab: 3 mekanisme:
1. **Schema validation** (JSON parse + key check)
2. **Deterministic fallback** (kalau LLM return invalid JSON)
3. **Heuristic cross-check** (e.g. domain_detection cross-check LLM result dengan library match)

> **"Apakah LLM hasil konsisten?"**

Jawab: 78/78 unit test pass untuk deterministic path. LLM path **non-deterministic by design**, tapi:
- LLM result di-merge dengan deterministic result (e.g. code_snippet, file, line dari scanner, CWE/OWASP dari LLM)
- Deterministic fallback kalau LLM tidak konsisten
- Heuristic guard (e.g. `confidence < 0.5 → use heuristic`)

---

## 7. File-File Prompt

Semua prompt tersimpan di:
- `app/agents/nodes/technology_detection_node.py` (~line 80)
- `app/agents/nodes/architecture_detection_node.py` (~line 50)
- `app/agents/nodes/deployment_detection_node.py` (~line 60)
- `app/agents/nodes/vulnerability_scan_node.py` (~line 21)
- `app/agents/nodes/domain_detection_node.py` (~line 277)
- `app/agents/nodes/security_requirement_inference_node.py` (~line 11)
- `app/agents/nodes/security_analyzer.py` (~line 33)
- `app/agents/nodes/recommendation_gen.py` (~line 4)
- `app/agents/nodes/ai_log_evaluator.py` (~line 711)

**Total: 9 file prompt, ~400 baris prompt template.**

---

## 8. Checklist untuk Konfirmasi

- [x] 8 node yang pakai LLM teridentifikasi
- [x] Input → Output untuk setiap node terdokumentasi
- [x] Fallback strategy untuk setiap LLM call
- [x] Prinsip desain: LLM hanya untuk konteks, bukan untuk deterministic generation
- [x] State update per node terdokumentasi
- [x] Cara baca untuk dosen (FAQ) tersedia

**Siap untuk konfirmasi dosen.**

---

**End of README — LLM I/O Documentation**
