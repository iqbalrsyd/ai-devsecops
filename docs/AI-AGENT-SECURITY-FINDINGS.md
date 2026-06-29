# AI-Agent Accessible Security Findings

> README desain fitur untuk memungkinkan AI agent (vibe coder) mengakses hasil security findings dari pipeline yang dihasilkan sistem — tanpa perlu login ulang atau regenerate lewat frontend.

---

## 1. Masalah

Saat ini, untuk melihat hasil security finding dari pipeline yang dihasilkan, pengguna harus:

1. Login ke frontend.
2. Submit repository.
3. Menunggu pipeline di-generate.
4. Menunggu workflow di-deploy dan di-execute di GitHub Actions.
5. Baru melihat hasil di dashboard.

Proses ini lambat dan tidak ramah untuk iterasi cepat saat debugging atau refactoring kode. Terutama ketika AI agent (vibe coder) ingin:

- Memahami konteks security issue saat ini.
- Memberikan rekomendasi fix langsung di codebase.
- Membandingkan hasil scan sebelum vs sesudah perbaikan.

## 2. Tujuan

Membuat sebuah **Security Findings Bridge** yang:

1. Menyimpan hasil eksekusi pipeline dan security findings secara terstruktur.
2. Dapat diakses langsung oleh AI agent melalui file lokal, API, atau MCP server.
3. Mengurangi gesekan iterasi debug-fix-test untuk masalah keamanan.
4. Mendukung workflow vibe coding: AI agent membaca findings → merekomendasikan fix → developer menerapkan → AI agent bisa memverifikasi ulang.

## 3. Use Cases

| Use Case | Cara Akses | Kapan Digunakan |
|----------|-----------|-----------------|
| Developer ingin tahu vulnerability terbaru repo-nya | Buka file `.devsecops-findings/latest/findings.json` | Setelah pipeline selesai dieksekusi |
| AI agent ingin memberikan saran perbaikan | Baca findings via MCP tool `get_security_findings` | Saat session vibe coding berlangsung |
| AI agent ingin membandingkan before/after fix | Bandingkan `findings.v1.json` vs `findings.v2.json` | Setelah fix diterapkan dan pipeline di-re-run |
| CI/CD otomasi ingin fail build jika risk score tinggi | Panggil API `/api/v1/pipeline/findings/{execution_id}` | Saat gate deployment |

## 4. Arsitektur Solusi

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          GitHub Actions                              │
│  Workflow YAML di-run → menghasilkan:                                │
│    - SARIF (CodeQL, Trivy, Checkov)                                  │
│    - JSON reports (Gitleaks, npm audit, pip-audit)                   │
│    - Plaintext logs                                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Artifacts di-upload
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Service (Backend)                         │
│  - Endpoint: POST /api/v1/pipeline/findings/fetch                    │
│  - Mengunduh artifacts dari GitHub Actions                           │
│  - Memparsing SARIF/JSON menjadi format unified                      │
│  - Menyimpan ke local workspace                                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
      ┌─────────────────┐ ┌──────────┐ ┌─────────────────┐
      │ File-based      │ │ REST API │ │ MCP Server      │
      │ .devsecops/     │ │ Endpoint │ │ (AI Agent)      │
      │ findings/       │ │          │ │                 │
      └─────────────────┘ └──────────┘ └─────────────────┘
```

## 5. Struktur Data Findings

Semua findings disimpan dalam format JSON terstruktur. Lokasi default:

```text
.devsecops-findings/
└── {owner}/
    └── {repo}/
        ├── latest/                    # symlink ke run terbaru
        ├── 2026-06-18T10-00-00Z/      # per run
        │   ├── meta.json              # metadata eksekusi
        │   ├── findings.json          # unified findings
        │   ├── summary.json           # ringkasan score & stats
        │   ├── workflow.yaml          # workflow yang di-deploy
        │   ├── raw/
        │   │   ├── codeql.sarif
        │   │   ├── trivy.json
        │   │   ├── gitleaks.json
        │   │   └── npm-audit.json
        │   └── logs/
        │       └── github-actions.log
        └── history.json               # index semua run
```

### 5.1 `meta.json`

```json
{
  "execution_id": "exec_abc123",
  "repository": "https://github.com/owner/repo",
  "branch": "devsecops/ai-generated-pipeline",
  "run_id": 123456789,
  "run_url": "https://github.com/owner/repo/actions/runs/123456789",
  "started_at": "2026-06-18T10:00:00Z",
  "completed_at": "2026-06-18T10:05:30Z",
  "status": "completed",
  "detected_context": {
    "architecture": "monolith",
    "domain": "e-commerce",
    "technologies": ["nodejs", "express"],
    "deployment": "docker"
  }
}
```

### 5.2 `findings.json` (Unified)

```json
{
  "findings": [
    {
      "id": "GHAS-001",
      "tool": "CodeQL",
      "category": "sql-injection",
      "severity": "critical",
      "confidence": "high",
      "file": "src/routes/checkout.js",
      "line": 18,
      "column": 5,
      "message": "User input is directly concatenated into SQL query",
      "rule_id": "js/sql-injection",
      "rule_url": "https://codeql.github.com/...",
      "domain_relevance": "high",
      "domain_context": "payment-related",
      "suggested_fix": "Use parameterized queries or ORM",
      "status": "open"
    },
    {
      "id": "GLK-042",
      "tool": "Gitleaks",
      "category": "hardcoded-secret",
      "severity": "high",
      "confidence": "high",
      "file": ".env",
      "line": 5,
      "message": "Possible Stripe secret key detected",
      "domain_relevance": "high",
      "domain_context": "payment-secret",
      "suggested_fix": "Move secret to GitHub Secrets or vault",
      "status": "open"
    }
  ]
}
```

### 5.3 `summary.json`

```json
{
  "total_findings": 12,
  "by_severity": {
    "critical": 2,
    "high": 4,
    "medium": 3,
    "low": 3
  },
  "by_tool": {
    "CodeQL": 3,
    "Gitleaks": 2,
    "Trivy": 4,
    "npm-audit": 3
  },
  "scores": {
    "risk_score": 78,
    "security_standards_coverage_score": 42,
    "security_coverage_score": 55
  },
  "domain": "e-commerce",
  "architecture": "monolith"
}
```

## 6. Cara Kerja

### Alur Normal

1. Sistem menghasilkan workflow YAML dan membuat PR ke repo target.
2. GitHub Actions menjalankan workflow.
3. Workflow meng-upload artifacts (SARIF, JSON reports, logs).
4. Backend polling atau webhook mengetahui run selesai.
5. Backend memanggil GitHub API untuk mengunduh artifacts.
6. Backend memparse artifacts menjadi `findings.json` unified.
7. Backend menyimpan hasil ke `.devsecops-findings/{owner}/{repo}/{timestamp}/`.
8. Symlink `latest` diperbarui ke run terbaru.
9. AI agent dapat membaca hasil secara langsung.

### Alur Manual (untuk debugging cepat)

```bash
# Fetch findings untuk repo tertentu
python -m ai_security_bridge fetch \
  --repo owner/repo \
  --run-id 123456789 \
  --output .devsecops-findings/owner/repo/latest/

# Atau fetch run terbaru otomatis
python -m ai_security_bridge fetch-latest --repo owner/repo
```

## 7. Integrasi dengan AI Agent / Vibe Coder

### Opsi A: File-Based (MVP — paling sederhana)

AI agent membaca file lokal saja. Contoh untuk Cursor/Claude Code:

```text
User: "Apa vulnerability terparah di repo ini dan bagaimana fix-nya?"
AI:  membaca .devsecops-findings/latest/summary.json
     membaca .devsecops-findings/latest/findings.json
     memberikan rekomendasi fix file-per-file
```

Keuntungan:
- Tidak perlu setup server tambahan.
- Cepat untuk iterasi lokal.

Kekurangan:
- AI agent harus tahu path file-nya.
- Tidak ada semantik query khusus.

### Opsi B: REST API Endpoint

Tambahkan endpoint di `ai-service`:

| Method | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/api/v1/pipeline/findings/{execution_id}` | Ambil findings lengkap |
| GET | `/api/v1/pipeline/findings/{execution_id}/summary` | Ambil ringkasan score |
| GET | `/api/v1/pipeline/findings/latest?repo=owner/repo` | Ambil findings run terbaru |
| POST | `/api/v1/pipeline/findings/fetch` | Trigger fetch dari GitHub Actions |

Keuntungan:
- Dapat diakses dari mana saja.
- Cocok untuk integrasi CI/CD.

Kekurangan:
- Memerlukan autentikasi/token.

### Opsi C: MCP Server (Model Context Protocol) — Ideal

Buat MCP server bernama `devsecops-mcp-server` yang mengekspose tool:

```json
{
  "tools": [
    {
      "name": "get_security_findings",
      "description": "Get latest security findings for a repository",
      "input_schema": {
        "type": "object",
        "properties": {
          "repo": {"type": "string"},
          "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
          "limit": {"type": "integer"}
        }
      }
    },
    {
      "name": "get_risk_summary",
      "description": "Get risk score and standards coverage score",
      "input_schema": {
        "type": "object",
        "properties": {
          "repo": {"type": "string"}
        }
      }
    },
    {
      "name": "get_workflow_yaml",
      "description": "Get the generated workflow YAML",
      "input_schema": {
        "type": "object",
        "properties": {
          "repo": {"type": "string"}
        }
      }
    },
    {
      "name": "compare_findings",
      "description": "Compare findings between two runs",
      "input_schema": {
        "type": "object",
        "properties": {
          "repo": {"type": "string"},
          "run_a": {"type": "string"},
          "run_b": {"type": "string"}
        }
      }
    }
  ]
}
```

Keuntungan:
- AI agent (Cursor, Claude Desktop, Windsurf) bisa memanggil tool ini secara native.
- Semantik jelas: AI bisa bertanya "apa findings critical di repo X?" tanpa perlu parse file manual.
- Cocok untuk vibe coding.

## 8. API/CLI yang Perlu Dibuat

### Backend Endpoint

```python
# ai-service/app/api/findings.py

@router.get("/findings/{execution_id}")
async def get_findings(execution_id: str):
    ...

@router.get("/findings/latest")
async def get_latest_findings(repo: str):
    ...

@router.post("/findings/fetch")
async def trigger_fetch(repo: str, run_id: Optional[int] = None):
    ...
```

### CLI Tool

```bash
# Install
pip install -e ai-security-bridge/

# Fetch findings untuk run tertentu
ai-findings fetch --repo owner/repo --run-id 123456789

# Fetch run terbaru
ai-findings fetch-latest --repo owner/repo

# Tampilkan summary
ai-findings summary --repo owner/repo

# Bandingkan dua run
ai-findings compare --repo owner/repo --run-a run1 --run-b run2

# Export untuk AI agent
ai-findings export --repo owner/repo --format markdown --output findings-report.md
```

### MCP Server

```bash
# Jalankan MCP server
python -m devsecops_mcp_server

# Configure di Claude Desktop / Cursor
cat ~/.cursor/mcp.json
{
  "mcpServers": {
    "devsecops": {
      "command": "python",
      "args": ["-m", "devsecops_mcp_server"],
      "env": {
        "FINDINGS_BASE_DIR": ".devsecops-findings"
      }
    }
  }
}
```

## 9. Contoh Penggunaan oleh AI Agent

### Skenario 1: AI agent menemukan critical issue

```text
User: "Cek security findings terbaru untuk ecommerce-monolith-vuln."
AI:  [memanggil get_security_findings(repo="ecommerce-monolith-vuln", severity="critical")]
AI:  "Ditemukan 2 critical issues:
     1. SQL Injection di src/routes/checkout.js:18 — langsung mempengaruhi payment flow.
     2. Hardcoded Stripe secret key di .env:5.
     Saran perbaikan:
     - Gunakan parameterized queries.
     - Pindahkan Stripe key ke GitHub Secrets."
```

### Skenario 2: AI agent membandingkan before/after fix

```text
User: "Apakah fix yang kita lakukan sudah mengurangi risk?"
AI:  [memanggil compare_findings(repo="ecommerce-monolith-vuln", run_a="run1", run_b="run2")]
AI:  "Risk score turun dari 78 ke 34. Critical findings berkurang dari 2 menjadi 0."
```

## 10. Keamanan & Privasi

- File findings disimpan di workspace lokal developer, **tidak** di-commit ke repo.
- Tambahkan `.devsecops-findings/` ke `.gitignore`.
- Jika menggunakan MCP server, pastikan hanya bisa mengakses workspace yang diizinkan.
- API endpoint harus memerlukan autentikasi jika di-deploy ke shared environment.

## 11. Roadmap Implementasi

| Fase | Deliverable | Status |
|------|-------------|--------|
| 1 | File-based findings storage (`findings.json`, `summary.json`, `meta.json`) | Belum |
| 2 | CLI tool `ai-findings` untuk fetch dan summary | Belum |
| 3 | Backend API endpoint `/findings/*` | Belum |
| 4 | Integrasi artifact download dari GitHub Actions | Belum |
| 5 | MCP server `devsecops-mcp-server` | Belum |
| 6 | Dokumentasi dan contoh vibe coding workflow | Belum |

## 12. Rekomendasi Teknologi

| Komponen | Rekomendasi |
|----------|-------------|
| Parser SARIF | `sarif-om`, `json` stdlib |
| Parser Trivy | `json` stdlib |
| CLI framework | `typer` atau `click` |
| MCP server | `mcp` SDK (Python) dari Anthropic |
| Backend | FastAPI (sama dengan AI service yang sudah ada) |
| Storage lokal | File JSON di `.devsecops-findings/` |

---

## Catatan untuk Implementasi

Fitur ini sebaiknya diimplementasikan sebagai **modul terpisah** namun tetap terintegrasi dengan `ai-service` yang sudah ada. MVP paling cepat adalah:

1. Setelah `workflow_execution_node` selesai, trigger download artifacts.
2. Parse artifacts ke `findings.json`.
3. Simpan ke `.devsecops-findings/{owner}/{repo}/latest/`.
4. AI agent dapat langsung membaca file tersebut.

Setelah MVP stabil, baru tambahkan REST API dan MCP server untuk pengalaman vibe coding yang lebih baik.
