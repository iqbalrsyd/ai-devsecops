# PDF Report Generation — AI DevSecOps Security Assistant

Fitur ini menghasilkan laporan PDF per repositori yang mencakup hasil empat tahap pipeline: repository context analysis, security requirement inference, pipeline generation, dan pipeline evaluation.

## Output: 1 PDF per Repositori

Setiap kali pipeline selesai dijalankan (dari analisis repositori hingga evaluasi), sistem otomatis menghasilkan satu file PDF yang disimpan di direktori `REPORTS_DIR`.

## Struktur Laporan (4 Section)

| Section | Isi |
|---------|-----|
| **Cover** | Nama repositori, arsitektur, domain, timestamp |
| **1. Repository Context** | Technology stack + **tech-stack bar chart**, architecture classification, deployment infrastructure, webapp domain + threats |
| **2. Security Requirements** | Attack surface identification, security control selection (tabel status/tool/reason/**OWASP-CWE reference**) + **donut chart**, pipeline stages |
| **3. Generated Pipeline** | Validation result, **pipeline stage diagram** + stages table, workflow YAML |
| **4. Evaluation Results** | **Risk score gauge** + Standards Coverage + Security Coverage + **coverage bars**, findings table (top 30) + **severity stacked bar**, recommendations, executive summary |

## Visualizations (v2)

Setiap section punya minimal satu elemen visual untuk memudahkan review:

| Section | Chart | Lokasi File |
|---------|-------|-------------|
| 1.1 | Horizontal bar — jumlah frameworks / build_tools / databases / runtime | `app/services/charts.py:tech_stack_bar_chart` |
| 2.2 | Donut — Recommended / Optional / Not Required + kolom OWASP/CWE reference di tabel | `app/services/charts.py:controls_donut` + `_resolve_reference` di `report_generator.py` |
| 3.2 | Pipeline stage diagram (boxes + arrows) dengan status warna hijau/merah/abu-abu | `app/services/charts.py:pipeline_stage_diagram` |
| 4.1 | Half-circle risk gauge (0-100, OWASP color band) + dua coverage progress bar | `app/services/charts.py:risk_gauge`, `coverage_bar` |
| 4.2 | Stacked horizontal bar — distribusi critical/high/medium/low | `app/services/charts.py:severity_bar` |

Semua chart di-render sebagai **vector (reportlab Drawing)** — bukan raster, sehingga ukuran PDF tidak membengkak (~13KB untuk 6 halaman dengan semua chart aktif).

## Download Manual via "Generate PDF" Button

Selain auto-generation di akhir pipeline, user bisa generate PDF kapan saja dari halaman **Run Detail** (halaman analisis per-run). Button ini memanggil endpoint:

```
GET /ai/pipeline/runs/{run_id}/report
```

Behavior:
- Rekonstruksi state dari `pipeline_analyses`, `findings`, `recommendations`, dan `pipeline_generations.generated_yaml`
- Generate PDF on-demand
- Return sebagai `application/pdf` dengan `Content-Disposition: attachment` → browser auto-download
- Filename: `{owner}_{repo}_{run_id}.pdf`
- Response header `X-Report-Path` menyimpan path file di server (untuk debugging)

Jika AI service `PDF_REPORT_ENABLED=false`, endpoint return `404`.

## File Terkait

| File | Peran |
|------|-------|
| `ai-service/app/services/report_generator.py` | Core PDF generator (pakai reportlab) |
| `ai-service/app/services/charts.py` | Helper chart (bar, donut, gauge, diagram, stacked bar) |
| `ai-service/app/api/pipeline.py` | Endpoint `GET /runs/{run_id}/report` untuk on-demand download |
| `ai-service/app/agents/nodes/response_formatter.py` | Trigger PDF generation setelah pipeline selesai (auto) |
| `ai-service/app/agents/pipeline_state.py` | State field `pdf_report_path` |
| `ai-service/app/services/pipeline_service.py` | Default state initialization |
| `frontend/src/pages/RunDetail.tsx` | Button "Generate PDF Report" di halaman detail run |

## Konfigurasi

Tambahkan di `.env`:

```env
# PDF Report
PDF_REPORT_ENABLED=true          # true/false — enable/disable auto PDF generation
REPORTS_DIR=/tmp/reports         # Directory untuk menyimpan file PDF
```

Default:
- `PDF_REPORT_ENABLED=true` (aktif)
- `REPORTS_DIR=/tmp/reports` (akan dibuat otomatis jika belum ada)

## Dependency

```txt
reportlab==5.0.*
```

`reportlab.graphics.charts` (HorizontalBarChart, Pie) + `reportlab.graphics.shapes` (Drawing, Rect, Wedge, String) digunakan untuk semua visualisasi — sudah bundled dengan `reportlab`, tidak ada dependency tambahan.

## API Response

Path PDF disertakan di response API:

```json
{
  "analysis": { ... },
  "metadata": {
    "pdf_report_path": "/tmp/reports/owner_repo_20260621-153045.pdf"
  }
}
```

## Penamaan File

`{owner}_{repo}_{timestamp}.pdf`

Contoh: `iqbalrasyad_ecommerce-api_20260621-153045.pdf`

## Catatan

- PDF generation bersifat **non-blocking** — jika gagal, pipeline tetap jalan dan error di-log sebagai warning
- YAML di section 3 ditruncate ke 200 baris pertama untuk keterbacaan
- Findings table di section 4 dibatasi 30 temuan teratas
- Laporan bisa di-download atau di-view per tahap via API terpisah (future enhancement)
