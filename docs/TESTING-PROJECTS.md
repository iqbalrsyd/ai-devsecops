# Testing Projects Registry

> Dokumen ini berisi daftar project dan repository uji yang sudah dibuat di lingkungan lokal (localhost). Tujuannya agar AI agent atau developer lain bisa menjalankan testing dari terminal tanpa harus buka frontend.
>
> **Catatan:** Semua URL di sini adalah lokal dev URL. Jangan commit file ini jika berisi data sensitif.

---

## Cara Menggunakan Dokumen Ini

Setiap project memiliki:
- **Project ID** — UUID project di database aplikasi.
- **Repo ID** — UUID repository di dalam project.
- **Frontend URL** — URL yang bisa dibuka di browser (localhost:5173).
- **Backend API** — endpoint terminal untuk generate pipeline / analyze repo.
- **GitHub URL** — URL repo asli di GitHub.
- **Purpose** — tujuan pengujian.

Untuk testing dari terminal, biasanya cukup panggil backend API dengan `curl` atau `httpie`.

---

## Project 1: E-Commerce Monolith Vulnerable

| Atribut | Nilai |
|---------|-------|
| Project ID | `4da7306c-ef41-40e0-ae37-4cb648983d3c` |
| Repo ID | `17f5536b-50b2-46b2-9f0b-e8c2a4414f2a` |
| Repo Name | `eccomerce-monolith-vuln` |
| GitHub URL | `https://github.com/iqbalrsyd/eccomerce-monolith-vuln` |
| Domain | E-commerce |
| Arsitektur | Monolith |
| Tech Stack | Node.js, Express, SQLite, Docker |
| Frontend URL | `http://localhost:5173/projects/4da7306c-ef41-40e0-ae37-4cb648983d3c/repos/17f5536b-50b2-46b2-9f0b-e8c2a4414f2a/pipelines/generate` |
| Tujuan | Menguji deteksi domain e-commerce, generate pipeline monolith, deteksi hardcoded secret (Stripe), SQLi, XSS, CSRF, container scan. |

### Testing dari Terminal

#### 1. Generate Pipeline via Backend API

```bash
# Pastikan backend AI service berjalan di localhost:8000
curl -X POST http://localhost:8000/api/v1/projects/4da7306c-ef41-40e0-ae37-4cb648983d3c/repos/17f5536b-50b2-46b2-9f0b-e8c2a4414f2a/pipelines/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "branch": "main"
  }'
```

> **Catatan:** Sesuaikan endpoint dan auth header sesuai backend API yang sebenarnya. Jika backend menggunakan endpoint global seperti `POST /api/v1/pipeline/analyze`, gunakan repo URL sebagai input.

#### 2. Generate Pipeline via Endpoint Global (Alternatif)

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "repo_url": "https://github.com/iqbalrsyd/eccomerce-monolith-vuln",
    "branch": "main",
    "project_id": "4da7306c-ef41-40e0-ae37-4cb648983d3c",
    "repo_id": "17f5536b-50b2-46b2-9f0b-e8c2a4414f2a"
  }'
```

#### 3. Cek Status Pipeline / Findings

```bash
# Ganti {execution_id} dengan ID dari response generate
curl http://localhost:8000/api/v1/pipeline/executions/{execution_id} \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

#### 4. Fetch GitHub Actions Run (jika sudah deploy)

```bash
# List runs untuk repo ini
gh run list -R iqbalrsyd/eccomerce-monolith-vuln --limit 5

# Download artifact hasil scan
gh run download -R iqbalrsyd/eccomerce-monolith-vuln <run-id>
```

---

## Project 2: Healthcare Microservices Vulnerable

| Atribut | Nilai |
|---------|-------|
| Project ID | *(belum dibuat di frontend)* |
| Repo ID | *(belum dibuat di frontend)* |
| Repo Name | `healthcare-micro-vuln` |
| GitHub URL | `https://github.com/iqbalrsyd/healthcare-micro-vuln` |
| Domain | Healthcare |
| Arsitektur | Microservices |
| Tech Stack | Python, FastAPI, PostgreSQL, Docker Compose, Kubernetes |
| Frontend URL | *(belum ada)* |
| Tujuan | Menguji deteksi domain healthcare, generate pipeline microservices (matrix build), deteksi PHI leak, inter-service auth weakness, container scan per-service. |

### Testing dari Terminal

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "repo_url": "https://github.com/iqbalrsyd/healthcare-micro-vuln",
    "branch": "main"
  }'
```

---

## Setup Environment untuk Terminal Testing

Sebelum menjalankan perintah di atas, pastikan:

1. **Backend AI service berjalan:**

   ```bash
   cd /mnt/ssd/college-project/skripsi-code/coba-4/ai-service
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend dev server berjalan** (jika ingin buka URL di browser):

   ```bash
   cd /mnt/ssd/college-project/skripsi-code/coba-4/frontend
   npm run dev
   ```

3. **GitHub token tersedia:**

   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

   Atau via file `.env` di project (jangan di-commit).

4. **`gh` CLI sudah terautentikasi** (untuk fetch Actions artifacts):

   ```bash
   gh auth status
   ```

---

## Catatan untuk AI Agent

- Project ID dan Repo ID di atas berasal dari database aplikasi frontend. Gunakan ID-ID ini saat memanggil backend API yang memerlukan project/repo context.
- Jika endpoint backend berbeda dari contoh di atas, sesuaikan path-nya berdasarkan dokumentasi API (`ai-service/app/api/*`).
- Untuk debugging pipeline, langkah yang paling sering dilakukan:
  1. `POST /api/v1/pipeline/analyze` atau endpoint project-specific.
  2. Cek response: `detected_context`, `security_needs`, `generated_workflow`.
  3. Jika workflow valid, lanjut deploy / trigger GitHub Actions.
  4. Fetch findings dari GitHub Actions artifacts atau backend findings endpoint.

---

## TODO

- [ ] Tambahkan Project ID dan Repo ID untuk `healthcare-micro-vuln` setelah dibuat di frontend.
- [ ] Konfirmasi endpoint backend yang benar untuk generate pipeline (project-specific vs global).
- [ ] Dokumentasikan response schema untuk memudahkan parsing oleh AI agent.
