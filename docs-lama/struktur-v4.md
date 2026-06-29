# Dokumentasi Teknis Sistem DevSecOps Adaptif Berbasis AI

## Dokumen Pendukung Tesis: "Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices"

---

# Bagian 1: Inventaris Sistem

## 1.1 Tujuan Proyek

Sistem ini dirancang untuk mengotomatisasi generation, deployment, dan analisis pipeline CI/CD dengan pendekatan DevSecOps yang adaptif. Sistem melakukan inferensi kebutuhan keamanan berdasarkan karakteristik repository, menghasilkan workflow yang sesuai, dan menganalisis hasil eksekusi untuk memberikan rekomendasi peningkatan.

## 1.2 Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Repository Connection | Koneksi ke GitHub repository dengan token encryption (AES-256-GCM) |
| Repository Analysis | Pemindaian struktur repository dan file kunci |
| Technology Detection | Deteksi bahasa pemrograman, framework, build tools, test frameworks, package managers |
| Architecture Classification | Klasifikasi arsitektur (monolithic/microservices/frontend_backend) |
| Deployment Detection | Deteksi target deployment (Docker, Kubernetes, Terraform, cloud provider) |
| Security Requirement Inference | Inferensi kebutuhan keamanan berdasarkan tech stack, arsitektur, dan deployment |
| Pipeline Generation | Generasi workflow YAML menggunakan LLM |
| Pipeline Validation | Validasi syntax, SHA pinning, permissions |
| Pipeline Repair | Perbaikan otomatis workflow berdasarkan hasil validasi |
| Pipeline Deployment | Deployment sebagai Pull Request ke GitHub |
| Pipeline Execution | Trigger eksekusi workflow via GitHub API |
| Pipeline Monitoring | Monitoring eksekusi workflow real-time |
| Run Analysis | Analisis hasil eksekusi (risk score, compliance score, security coverage) |
| Execution Analysis | Analisis kegagalan eksekusi + root cause + remediation |
| Pipeline Comparison | Perbandingan dua versi pipeline |
| Workflow Remediation | **Lengkap**: analisis kegagalan, root cause detection, generasi workflow perbaikan, deploy PR remediation |

## 1.3 Workflow Pengguna

```
User Login → Dashboard → Project Selection
                          → Repository Selection
                              → Repository Analysis (scan + tech + arch + deploy detection)
                              → Pipeline Generation (dengan parameter)
                              → Pipeline Deployment (sebagai PR)
                              → Pipeline Execution Monitoring
                              → Run Analysis (risk, compliance, recommendations)
                              → Pipeline Comparison
                              → ⦗NEW⦘ Remediation (failure analysis → root cause → fix PR)
                              → User Settings (profile update, password change)
```

## 1.4 Komponen Arsitektur

| Komponen | Teknologi | Fungsi |
|----------|-----------|--------|
| Frontend | React + TypeScript + Vite | Antarmuka pengguna |
| Backend | Go + Gin + GORM | API server, database management |
| AI Service | Python + FastAPI + LangGraph | AI pipeline orchestration |
| Database (Backend) | PostgreSQL | Data repository, pipeline, runs, refresh tokens |
| Database (AI) | PostgreSQL | Analysis cache, state management |
| External | GitHub API | Repository access, webhook events |

## 1.5 Komponen AI

Sistem AI Service menggunakan LangGraph untuk orchestrate 20 node dalam compiled graph + 6 node dipanggil manual (total 26 node):

### Node dalam Compiled Graph (20 node):

1. **Repository Connection** - Koneksi ke GitHub
2. **Repository Scan** - Pemindaian struktur
3. **Vulnerability Scan** - LLM-based SAST vulnerability detection
4. **Technology Detection** - Deteksi teknologi
5. **Architecture Detection** - Klasifikasi arsitektur
6. **Deployment Detection** - Deteksi target deployment (Docker, K8s, Terraform)
7. **Security Requirement Inference** - Inferensi keamanan
8. **Workflow Generation** - Generasi YAML via LLM
9. **Workflow Validation** - Validasi workflow
10. **Auto Deploy Check** - Decision node untuk deploy path
11. **GitHub Branch Creation** - Pembuatan branch
12. **Pull Request Creation** - Pembuatan PR
13. **Workflow Execution** - Trigger eksekusi
14. **Execution Monitor** - Monitoring status (polling)
15. **Security Analysis** - Analisis keamanan dari log
16. **Risk Assessment** - Kalkulasi risk score
17. **Compliance Mapper** - Mapping compliance
18. **Recommendation Generation** - Rekomendasi via LLM
19. **Response Formatter** - Format response
20. **Error Handler** - Error handling

### Node Dipanggil Manual (6 node):

21. **Workflow Repair** - Perbaikan otomatis workflow
22. **Execution Log Collection** - Kompilasi log dari failed jobs
23. **Failure Analysis** - Analisis kegagalan workflow
24. **Root Cause Detection** - Deteksi akar masalah
25. **Remediation Generation** - Generasi perbaikan via LLM
26. **Remediation PR Creation** - PR perbaikan

## 1.6 Entitas Database

**Backend (Go/GORM) — 9 model:**

| Model | Tabel | Deskripsi |
|-------|-------|-----------|
| User | users | Data pengguna |
| RefreshToken | refresh_tokens | Refresh token untuk JWT renewal |
| Project | projects | Logical grouping repository |
| Repository | repositories | Koneksi GitHub repository |
| RepositoryInsight | repository_insights | Cache hasil analisis repository |
| Pipeline | pipelines | Generated workflow configurations |
| PipelineRun | pipeline_runs | Riwayat eksekusi pipeline |
| PipelineAnalysis | pipeline_analyses | Hasil analisis eksekusi |
| Role | - | Enum untuk role user |

**AI Service (Python/SQLAlchemy + raw SQL):**
- Cached analysis, LLM conversation history, Workflow state
- workflow_executions, findings, risk_assessments, recommendations, compliance_mappings

## 1.7 Endpoint API

**Backend API** (`/api/v1/*`): 34 endpoint untuk CRUD, webhook, dashboard, user management
**AI Service API** (`/api/pipeline/*`): 16 endpoint untuk pipeline lifecycle, analysis, webhook, remediation

## 1.8 Integrasi Eksternal

- GitHub API v3 (repos, actions, webhooks)
- GitHub Webhooks (push, pull_request, workflow_run)
- LLM Provider (Kimi 2.7 Coder via OpenCode)

## 1.9 Mekanisme Keamanan

- JWT Authentication + Refresh Token untuk API backend
- AES-256-GCM encryption untuk GitHub tokens
- Input validation dan sanitization
- Webhook signature verification
- Rate limiting via middleware

## 1.10 Arsitektur Deployment

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Client    │ ──── │   Backend   │ ──── │   AI        │
│  (React)    │      │    (Go)     │      │  Service    │
└─────────────┘      └──────┬──────┘      │  (Python)   │
                            │             └──────┬──────┘
                     ┌──────┴──────┐            │
                     │ PostgreSQL  │      ┌─────┴─────┐
                     │  (Backend)  │      │ PostgreSQL│
                     └─────────────┘      │   (AI)    │
                                          └───────────┘
                            GitHub API (shared)
```

---

# Bagian 2: Struktur Dokumentasi Teknis

---

## 1. System Overview

### 1.1 Tujuan Sistem

Sistem DevSecOps Adaptif berbasis AI dirancang untuk mengotomatisasi proses DevSecOps pada proyek perangkat lunak dengan pendekatan adaptif yang dapat menangani berbagai arsitektur sistem, mulai dari sistem monolitik hingga microservices. Sistem ini melakukan analisis repository secara otomatis, melakukan inferensi kebutuhan keamanan berdasarkan karakteristik teknologi yang digunakan, dan menghasilkan pipeline CI/CD yang sesuai dengan prinsip DevSecOps.

### 1.2 Masalah yang Diselesaikan

Pengembangan pipeline CI/CD secara manual memerlukan pengetahuan mendalam tentang berbagai tool, security controls, dan compliance standards. Proses ini sering kali tidak konsisten, memakan waktu, dan rentan terhadap kesalahan konfigurasi yang dapat menimbulkan risiko keamanan. Sistem ini menyelesaikan masalah tersebut dengan:

1. **Otomatisasi Analisis Repository** - Mengurangi kebutuhan manual inspection untuk menentukan teknologi, arsitektur, dan deployment target yang digunakan.

2. **Inferensi Keamanan Adaptif** - Menyesuaikan security controls berdasarkan karakteristik spesifik dari setiap repository.

3. **Generasi Pipeline Otomatis** - Menghasilkan workflow YAML yang sesuai dengan best practices dan compliance requirements.

4. **Analisis Hasil Eksekusi** - Memberikan insight tentang risk score, compliance score, dan rekomendasi perbaikan.

5. **Automated Remediation** - Mendeteksi root cause kegagalan dan menghasilkan perbaikan otomatis lengkap dengan deployment PR.

### 1.3 Pengguna Target

| Pengguna | Peran dalam Sistem |
|----------|-------------------|
| Software Engineers | Menggunakan sistem untuk generate dan deploy pipeline CI/CD |
| DevOps Engineers | Monitoring dan optimizing pipeline execution |
| Security Engineers | Review security findings dan recommendations |
| Project Managers | Melihat aggregated statistics dan compliance status |

### 1.4 Cakupan Sistem

Sistem ini mencakup:

- **Repository Integration**: Koneksi ke GitHub repositories dengan webhook support
- **Technology Analysis**: Deteksi otomatis bahasa, framework, tools, dan package managers
- **Architecture Classification**: Klasifikasi sebagai monolith, microservices, atau frontend_backend
- **Deployment Detection**: Deteksi target deployment (Docker, K8s, Terraform, cloud)
- **Security Inference**: Inferensi kebutuhan keamanan berdasarkan tech stack
- **Pipeline Generation**: Generasi workflow YAML adaptif via LLM
- **Pipeline Validation**: Validasi syntax dan security requirements
- **Pipeline Repair**: Perbaikan otomatis workflow yang gagal validasi
- **Pipeline Deployment**: Deployment sebagai Pull Request
- **Execution Monitoring**: Real-time monitoring pipeline execution (polling 5 detik)
- **Run Analysis**: Analisis hasil dengan scoring system (risk, compliance, security coverage, quality)
- **Execution Analysis**: Analisis kegagalan + root cause detection + remediation generation
- **Pipeline Comparison**: Perbandingan antar versi pipeline
- **Automated Remediation**: Full remediation cycle (log collection → failure analysis → root cause → remediation YAML → PR creation) dengan UI khusus
- **User Management**: Update profil, change password, refresh token

### 1.5 Keterbatasan

Sistem ini memiliki keterbatasan sebagai berikut:

1. **GitHub-centric**: Hanya mendukung GitHub sebagai VCS provider
2. **Workflow Language**: Generated workflows hanya dalam format GitHub Actions YAML
3. **LLM Dependency**: Kualitas output bergantung pada kemampuan LLM yang digunakan
4. **Language Support**: Deteksi teknologi fokus pada bahasa pemrograman populer (Node.js, Python, Java, Go, dll.)
5. **Deployment Model**: Generated pipelines memerlukan approval untuk merge ke branch utama

---

## 2. Functional Requirements

### 2.1 Repository Connection

**Tujuan**: Menghubungkan GitHub repository ke sistem untuk enable pipeline generation dan monitoring.

**Input**:
- Repository URL (format: `github.com/{owner}/{repo}`)
- GitHub Access Token (dengan permissions: repo, workflows)

**Output**:
- Repository record dengan encrypted token
- Initial repository metadata (owner, name, default branch)

**Modul Terkait**:
- `repositories/handler.go` (Backend)
- `repository_connection` node (AI Service)

---

### 2.2 Repository Analysis

**Tujuan**: Melakukan pemindaian komprehensif terhadap struktur repository untuk menentukan teknologi yang digunakan.

**Input**:
- Repository ID
- GitHub access token

**Output**:
- File structure (key files: package.json, requirements.txt, pom.xml, dll.)
- Primary language dengan persentase penggunaan
- Framework detection
- Build tools detection
- Test framework detection
- Package manager detection
- Deployment target detection
- Dependency ecosystem analysis

**Modul Terkait**:
- `repository_scan` node (AI Service)
- `technology_detection` node (AI Service)
- `deployment_detection` node (AI Service)

---

### 2.3 Technology Detection

**Tujuan**: Mendeteksi bahasa pemrograman, framework, build tools, test frameworks, dan package managers yang digunakan dalam repository.

**Input**:
- Repository files (via GitHub API)
- Language statistics (dari GitHub languages API)
- Key files content (package.json, etc.)

**Output**:
- `primary_language`: Bahasa utama repository
- `secondary_languages`: Bahasa tambahan (array)
- `frameworks`: Framework yang digunakan (array)
- `build_tools`: Build tools (npm, maven, gradle, dll.)
- `test_frameworks`: Test frameworks (jest, pytest, junit, dll.)
- `package_managers`: Package managers (npm, pip, maven, dll.)
- `confidence_scores`: Confidence untuk setiap detection

**Modul Terkait**:
- `technology_detection` node (AI Service)

---

### 2.4 Architecture Classification

**Tujuan**: Mengklasifikasikan arsitektur repository sebagai monolithic, microservices, atau frontend_backend.

**Input**:
- Repository structure
- Technology metadata
- Dockerfile presence
- docker-compose.yml presence
- Service directory patterns

**Output**:
- `architecture_type`: "monolith" | "microservices" | "frontend_backend" | "modular_monolith"
- `service_count`: Estimated number of services
- `confidence`: Classification confidence score

**Decision Logic**:
- Microservices: Multiple docker-compose files, service directories, API gateway patterns
- Monolith: Single main application, unified deployment
- Frontend+Backend: Separate frontend/backend directories, dual package managers
- Modular Monolith: Clear module boundaries but single deployment

**Modul Terkait**:
- `architecture_detection` node (AI Service)

---

### 2.5 Deployment Detection

**Tujuan**: Mendeteksi target deployment environment repository.

**Input**:
- Repository structure
- Dockerfile presence
- docker-compose.yml presence
- Kubernetes manifests
- Terraform/HCL files
- Serverless configurations

**Output**:
- `deployment_targets`: Array of deployment targets (docker, kubernetes, terraform, serverless, cloud)
- `primary_target`: Recommended primary deployment target
- `has_dockerfile`: Boolean
- `has_docker_compose`: Boolean
- `has_kubernetes`: Boolean
- `has_terraform`: Boolean
- `cloud_provider`: Detected cloud provider (AWS, GCP, Azure)

**Detection Logic**:
| Detection Source | Target |
|------------------|--------|
| Dockerfile only | Docker Container |
| docker-compose.yml | Docker Compose |
| k8s/ manifests | Kubernetes |
| Helm charts | Kubernetes (Helm) |
| terraform/*.tf | Cloud (AWS/GCP/Azure) |
| serverless.yml | Serverless |

**Modul Terkait**:
- `deployment_detection` node (AI Service)

---

### 2.6 Security Requirement Inference

**Tujuan**: Melakukan inferensi kebutuhan keamanan berdasarkan teknologi, arsitektur, dan deployment target.

**Input**:
- Technology metadata (language, framework, build tools)
- Architecture type
- Deployment target(s)

**Output**:
- `security_controls`: Array of required security controls
- `compliance_standards`: Applicable compliance standards (OWASP, CIS, dll.)
- `scan_requirements`: Required security scans (SAST, DAST, dependency check, dll.)
- `secrets_management`: Secrets management approach

**Control Selection Logic**:
| Technology | Inferred Controls |
|------------|-------------------|
| Node.js | npm audit, dependency check, secret scanning, SAST |
| Python | safety check, bandit, dependency review |
| Java | OWASP dependency check, spotbugs |
| Go | govulncheck, staticcheck |
| Docker | trivy scan, hadolint |
| Kubernetes | kube-bench, trivy k8s, rbac audit, network policy |

**Modul Terkait**:
- `security_requirement_inference` node (AI Service)

---

### 2.7 Pipeline Generation

**Tujuan**: Menghasilkan GitHub Actions workflow YAML berdasarkan repository characteristics, deployment target, dan security requirements.

**Input**:
- Repository ID
- Repository metadata
- Technology metadata
- Architecture type
- Deployment target
- Security controls yang diperlukan
- User preferences (deploy target, additional config)

**Output**:
- `generated_workflow`: YAML workflow content
- `generated_stages`: Array of pipeline stages
- `explanation`: AI-generated explanation dari workflow
- `validation_passed`: Boolean validation status
- `validation_errors`: Array of validation errors (jika ada)
- `validation_warnings`: Array of validation warnings
- `suggestions`: Improvement suggestions

**Generation Strategy**:
1. Analyze technology requirements
2. Map security controls ke workflow steps
3. Include appropriate triggers (push, pull_request, schedule)
4. Add appropriate caching strategies
5. Tailor for deployment target (Docker build, K8s deploy, etc.)
6. Include notification and reporting steps

**Modul Terkait**:
- `workflow_generation` node (AI Service)
- `response_formatter` node (AI Service)

---

### 2.8 Pipeline Validation

**Tujuan**: Memvalidasi generated workflow sebelum deployment.

**Validation Checks**:
1. **Syntax Validation**: YAML syntax correctness
2. **SHA Pinning**: Actions menggunakan SHA commit, bukan tag/version
3. **Permissions**: Minimal permissions untuk workflow
4. **Security Controls**: Required security steps included
5. **Best Practices**: Follow GitHub Actions best practices

**Input**:
- Generated workflow YAML
- Security requirements
- Repository metadata

**Output**:
- `valid`: Boolean validation status
- `errors`: Array of critical errors
- `warnings`: Array of non-critical warnings
- `suggestions`: Improvement recommendations

**Auto-Repair Logic**:
- Jika validasi gagal, sistem auto-invoke `workflow_repair` node dalam flow `run_repo_generate()`
- Repair menghasilkan YAML perbaikan via LLM
- Re-validasi setelah repair
- Max 2 retry attempts

**Modul Terkait**:
- `workflow_validation` node (AI Service)
- `workflow_repair` node (AI Service - manual invocation dalam run_repo_generate)

---

### 2.9 Pipeline Deployment

**Tujuan**: Mendepoy generated workflow ke GitHub sebagai Pull Request.

**Input**:
- Pipeline ID
- Generated workflow YAML
- Target branch (default: default branch repository)

**Output**:
- `branch_name`: Nama branch yang dibuat
- `pr_number`: Pull Request number
- `pr_url`: Pull Request URL
- `pr_status`: Deployment status

**Process Flow**:
1. Create new branch dengan nama unik (`devsecops-pipeline-{timestamp}`)
2. Create workflow file di `.github/workflows/`
3. Create Pull Request ke default branch
4. Return PR details

**Modul Terkait**:
- `github_branch_creation` node (AI Service)
- `pull_request_creation` node (AI Service)

---

### 2.10 Pipeline Monitoring

**Tujuan**: Monitoring eksekusi pipeline secara real-time.

**Input**:
- Pipeline ID
- GitHub run ID

**Output**:
- `status`: Current run status (queued, in_progress, completed, failed)
- `conclusion`: Run conclusion (success, failure, cancelled, skipped)
- `jobs`: Array of job details dengan steps
- `duration_seconds`: Total execution time
- `html_url`: Link ke GitHub run page

**Monitoring Strategy**:
1. Initial status check via GitHub API
2. Polling interval: setiap 5 detik
3. Continue polling until completed/failed atau timeout (30 menit)
4. Fetch job details setelah completion

**Modul Terkait**:
- `execution_monitor` node (AI Service)
- Backend `PipelineHandler.GetRun` method

---

### 2.11 Run Analysis

**Tujuan**: Menganalisis hasil eksekusi pipeline untuk menentukan risk score, compliance score, dan memberikan rekomendasi.

**Input**:
- Run ID
- Execution logs
- Pipeline configuration

**Output**:
- `risk_score`: Overall risk score (0-100)
- `compliance_score`: Compliance score against standards (0-100)
- `security_coverage_score`: Percentage of security controls implemented (0-100)
- `workflow_quality_score`: Workflow quality score (0-100)
- `severity_breakdown`: Breakdown findings by severity (critical, high, medium, low)
- `findings_summary`: Summary of security findings
- `recommendations`: Array of actionable recommendations
- `ai_explanation`: AI-generated explanation dari analysis

**Analysis Components**:
1. **Security Analysis**: Dependency vulnerabilities, secret exposure, insecure configurations
2. **Risk Assessment**: Risk calculation based on findings severity dan impact
3. **Compliance Mapping**: Mapping findings ke compliance standards (CIS, OWASP CICD controls)
4. **Recommendation Generation**: Actionable recommendations berdasarkan findings via LLM

**Modul Terkait**:
- `security_analysis` node (AI Service)
- `risk_assessment` node (AI Service)
- `compliance_mapper` node (AI Service)
- `recommendation_generation` node (AI Service)

---

### 2.12 Pipeline Comparison

**Tujuan**: Membandingkan dua versi pipeline untuk mengidentifikasi perbedaan dan improvement.

**Input**:
- Pipeline ID A
- Pipeline ID B

**Output**:
- Comparison summary
- YAML differences (side-by-side atau unified diff)
- Score comparison (risk, compliance, security coverage)
- Delta analysis: Controls yang ditambahkan/dihapus

**Modul Terkait**:
- Backend `PipelineHandler.ComparePipelines`

---

### 2.13 Execution Analysis & Remediation

**Tujuan**: Menganalisis kegagalan eksekusi, mendeteksi root cause, dan menghasilkan perbaikan otomatis. Ini adalah flow **lengkap** yang mencakup UI remediation khusus.

**Input**:
- Run ID dengan failure information
- Execution logs
- Original workflow YAML

**Output**:
- `failure_analysis`: Explanation dari failure (failure_type, root_cause, confidence, explanation, recommended_fix)
- `root_cause`: Root cause yang teridentifikasi (evidence[], affected_components[], fix_type)
- `remediation_suggestions`: Array of changes dengan file_path, change_type, before, after, reasoning
- `remediation_workflow`: Fixed workflow YAML
- `remediation_pr_url`: Pull Request dengan fix (jika applicable)
- `summary`: Human-readable summary dari analisis

**Remediation Process (5 node manual)**:
1. Collect execution logs → `execution_log_collection` node
2. Analyze failure pattern → `failure_analysis` node
3. Detect root cause → `root_cause_detection` node
4. Generate remediation YAML → `remediation_generation` node
5. Create Pull Request dengan fix → `remediation_pr_creation` node

**Flow Analisis & Remediasi Lengkap**:

```
RunDetail Page
  │
  │ (jika conclusion = "failure")
  │ tombol "Fix Failed Workflow"
  │
  ▼
RunRemediation Page
  │
  ├── Stage 1: Triggering → POST /ai/pipeline/analyze-execution/{run_id}
  ├── Stage 2: Collecting Logs (execution_log_collection node)
  ├── Stage 3: Analyzing Failure (failure_analysis + root_cause_detection nodes)
  ├── Stage 4: Generating Remediation (remediation_generation + remediation_pr_creation nodes)
  │
  ├── Results Display:
  │   ├── Summary overview
  │   ├── Failed Jobs & Steps list
  │   ├── Failure Analysis (failure_type badge, root_cause, explanation, recommended_fix)
  │   ├── Root Cause Analysis (evidence snippets, affected components, fix_type)
  │   └── Remediated Workflow (YAML viewer)
  │
  └── Action: "Deploy Fix" button
        │
        ▼
      POST /ai/pipeline/deploy-remediation
        ├── Create branch untuk remediation
        ├── Commit fixed workflow YAML
        ├── Create Pull Request
        ├── Persist sebagai pipeline version baru
        ├── Trigger workflow_dispatch pada branch remediation
        └── Return PR URL + new pipeline version link
```

**Fungsi Deploy Remediation Standalone**:
Endpoint `POST /api/pipeline/deploy-remediation` menerima repository_id, workflow_yaml, run_number, base_branch, dan workflow_file untuk langsung mendepoy hasil remediasi sebagai PR baru tanpa melalui full analysis pipeline. Fungsi ini:
1. Membuat branch remediation baru
2. Commit fixed YAML ke branch tersebut
3. Membuat PR ke base branch
4. Mem-persist remediation sebagai pipeline version baru di database
5. Trigger workflow dispatch pada branch remediation

**Modul Terkait**:
- `AI Service /analyze-execution/{run_id}` endpoint — Full analysis + remediation
- `AI Service /deploy-remediation` endpoint — Standalone remediation deployment
- `PipelineService.run_execution_analysis()` method — Orchestrate 5 manual nodes
- `PipelineService.deploy_remediation_workflow()` method — Deploy fixed YAML as PR
- Frontend `RunRemediation` page — Dedicated remediation UI
- Frontend `useAnalyzeExecution` hook — Trigger AI failure analysis

---

### 2.14 User Settings

**Tujuan**: Mengelola profil pengguna dan keamanan akun.

**Fitur**:
- Update profil (nama)
- Change password
- Refresh token untuk session extension

**Modul Terkait**:
- Backend `AuthHandler.Me`, `AuthHandler.UpdateProfile`, `AuthHandler.ChangePassword`
- `refresh_tokens` table

---

## 3. System Architecture

### 3.1 Frontend Architecture

**Technology Stack**:
- React 18+ dengan TypeScript
- Vite sebagai build tool
- React Router untuk routing
- Zustand untuk state management
- React Query untuk data fetching
- TailwindCSS untuk styling

**Component Hierarchy (Updated)**:
```
App
├── AuthProvider
│   ├── Landing
│   ├── Login
│   └── Register
└── ProtectedRoutes
    ├── Header
    ├── Dashboard
    ├── ProjectList
    │   └── ProjectDetail
    │       └── RepoDetail
    │           ├── PipelineList
    │           │   └── PipelineVersionDetail
    │           │       ├── WorkflowView (YamlViewer)
    │           │       ├── PipelineDetails
    │           │       ├── RunsList
    │           │       │   └── RunDetail
    │           │       │       ├── RunAnalysis
    │           │       │       │   ├── RiskScoreGauge
    │           │       │       │   ├── SeverityChart
    │           │       │       │   ├── VulnerabilityChart
    │           │       │       │   ├── ComplianceScorecard
    │           │       │       │   ├── FindingsTable
    │           │       │       │   │   └── FindingCard
    │           │       │       │   └── RecommendationsList
    │           │       │       └── ⦗NEW⦘ RunRemediation
    │           │       │           └── YamlViewer (remediated YAML)
    │           │       └── DeletePipelineModal
    │           ├── PipelineGenerator
    │           │   └── RequirementForm
    │           └── PipelineCompare
    │               └── CodeDiff
    └── Settings
```

**Key Features**:
- Real-time polling untuk run status (5 detik interval)
- SSE stream support untuk live updates
- Live log viewer untuk log eksekusi real-time
- Execution timeline untuk visualisasi job steps
- Risk score gauge, severity charts, vulnerability metrics
- Dedicated remediation UI dengan multi-stage progress indicator
- Lazy loading untuk route components
- Error boundary untuk graceful error handling

**Frontend Pages (14):**

| # | Path | Component | Auth |
|---|------|-----------|------|
| 1 | `/` | LandingPage / redirect | No |
| 2 | `/login` | LoginPage | No |
| 3 | `/register` | RegisterPage | No |
| 4 | `/dashboard` | DashboardPage | Yes |
| 5 | `/projects/:projectId` | ProjectDetailPage | Yes |
| 6 | `/projects/:projectId/repos/:repoId` | RepoDetailPage | Yes |
| 7 | `/projects/:.../repos/:repoId/pipelines` | PipelineHistory | Yes |
| 8 | `/projects/:.../repos/:repoId/pipelines/generate` | PipelineGenerator | Yes |
| 9 | `/projects/:.../repos/:repoId/pipelines/:version` | PipelineVersionDetail | Yes |
| 10 | `/projects/:.../pipelines/:version/runs/:runId` | RunDetail | Yes |
| 11 | `/projects/:.../pipelines/:version/runs/:runId/analysis` | RunAnalysis | Yes |
| 12 | `/projects/:.../pipelines/:version/runs/:runId/remediation` | RunRemediation ⦗NEW⦘ | Yes |
| 13 | `/projects/:.../repos/:repoId/pipelines/compare` | PipelineCompare | Yes |
| 14 | `/settings` | SettingsPage | Yes |

**Frontend Components (24 application + 8 UI = 32 total):**

| Component | Deskripsi |
|-----------|-----------|
| AuthLayout | Layout untuk halaman auth (login/register) |
| Header | Navigasi utama |
| ProtectedRoute | Route guard untuk halaman yang memerlukan auth |
| NewProjectModal | Modal untuk membuat project baru |
| DeleteProjectModal | Modal konfirmasi hapus project |
| DeletePipelineModal | Modal konfirmasi hapus pipeline |
| ConnectRepoModal | Modal untuk koneksi repository |
| RequirementForm | Form untuk parameter kebutuhan pipeline |
| YamlViewer | Syntax-highlighted YAML viewer |
| LiveLogViewer | Live streaming log viewer |
| ExecutionTimeline | Timeline visual job execution |
| FindingsTable | Tabel security findings |
| FindingCard | Card untuk individual finding (dengan Mark as Fixed/Acknowledge) |
| SeverityChart | Chart distribusi severity |
| VulnerabilityChart | Chart metrik vulnerability |
| RiskScoreGauge | Gauge widget untuk risk score |
| ComplianceScorecard | Display compliance scores |
| RecommendationsList | List rekomendasi perbaikan |
| PRLink | Link Pull Request |
| ValidationResults | Display validation errors/warnings |
| QuickActions | Tombol aksi cepat |
| RecentActivity | Feed aktivitas terbaru |
| CodeDiff | Viewer perbedaan kode/diff |
| CodeBlock | Syntax highlighter untuk code |
| UI: Badge, Button, Card, Dialog, Input, Label, Toast, Toaster | shadcn/ui components |

### 3.2 Backend Architecture

**Technology Stack**:
- Go 1.21+
- Gin web framework
- GORM sebagai ORM
- PostgreSQL sebagai database
- JWT dengan refresh token untuk authentication
- Logger middleware untuk request logging

**Module Structure**:
```
backend/
├── cmd/server/main.go          # Entry point, route registration
├── internal/
│   ├── config/
│   │   ├── config.go           # Main configuration
│   │   ├── jwt.go              # JWT configuration
│   │   └── ai.go               # AI service config
│   ├── database/
│   │   ├── postgres.go         # PostgreSQL connection
│   │   └── redis.go            # Redis connection (optional)
│   ├── middleware/
│   │   ├── auth.go             # JWT authentication
│   │   ├── cors.go             # CORS configuration
│   │   └── logger.go           # Request logging
│   ├── handlers/
│   │   ├── auth.go             # Auth endpoints
│   │   ├── dashboard.go        # Dashboard stats endpoint
│   │   ├── health.go           # Health check
│   │   ├── pipeline.go         # Pipeline + Run + Analysis endpoints
│   │   ├── project.go          # Project CRUD endpoints
│   │   ├── repository.go       # Repository endpoints
│   │   └── webhook.go          # GitHub webhook endpoint
│   ├── models/
│   │   ├── user.go
│   │   ├── refresh_token.go    # Refresh token model
│   │   ├── project.go
│   │   ├── repository.go
│   │   ├── repository_insight.go
│   │   ├── pipeline.go
│   │   ├── pipeline_run.go     # [UPDATED] +RemediationStatus field
│   │   ├── pipeline_analysis.go
│   │   └── role.go
│   ├── repositories/
│   │   ├── user_repository.go
│   │   ├── refresh_token_repository.go
│   │   ├── project_repository.go
│   │   ├── repository_repository.go
│   │   ├── repository_insight_repository.go
│   │   ├── pipeline_repository.go
│   │   ├── pipeline_run_repository.go
│   │   └── pipeline_analysis_repository.go
│   ├── services/
│   │   ├── auth_service.go      # Auth + user management
│   │   ├── ai_service.go        # AI Service HTTP client
│   │   ├── github_service.go    # GitHub API integration
│   │   ├── project_service.go
│   │   └── repository_service.go
│   └── utils/
│       └── crypto.go            # AES-256-GCM encryption
└── pkg/
```

**Key Components**:

1. **HTTP Handlers**: Menerima request dari frontend, validasi input, routing ke service layer
2. **Service Layer**: Business logic, orchestrate multiple repositories
3. **Repository Layer**: Database operations via GORM (8 repositories)
4. **External Services**: GitHub API integration, AI Service komunikasi
5. **Crypto Utils**: AES-256-GCM encrypt/decrypt untuk GitHub tokens

**Backend Services (5) + Repositories (8):**

| Service | Dependencies | Key Functions |
|---------|-------------|---------------|
| AuthService | UserRepo, RefreshTokenRepo, Config | Register, Login, Refresh, GetUser, UpdateUser, ChangePassword |
| ProjectService | ProjectRepo, UserRepo | Create, List, GetByID, UpdateComplianceTier, Delete |
| RepositoryService | RepositoryRepo, ProjectRepo, GitHubService | Connect, List, GetByID, Delete, DecryptToken |
| GitHubService | http.Client | ValidateToken, CheckRepoAccess, CreateBranch, CreateFile, CreatePR, TriggerDispatch, ListWorkflowRuns, GetWorkflowRun, GetWorkflowRunJobs, GetWorkflowRunLogs, FetchWorkflowFiles, CancelWorkflowRun |
| AIService | http.Client | Generate, AnalyzeRepository, Deploy, Validate, AnalyzeExecution |

### 3.3 AI Service Architecture

**Technology Stack**:
- Python 3.11+
- FastAPI untuk HTTP layer
- LangGraph untuk workflow orchestration
- SQLAlchemy untuk database
- PostgreSQL untuk state management
- Pydantic untuk data validation

**Module Structure**:
```
ai-service/
├── app/
│   ├── main.py                       # FastAPI app + JWT middleware
│   ├── config.py                     # Settings
│   ├── database.py                   # SQLAlchemy session
│   ├── api/
│   │   └── pipeline.py              # 16 API endpoints [UPDATED]
│   ├── agents/
│   │   ├── pipeline_graph.py        # LangGraph graph definition
│   │   ├── pipeline_state.py        # PipelineEngineerState TypedDict
│   │   ├── pipeline_schemas.py      # Pydantic schemas
│   │   └── nodes/                   # 26 node functions
│   │       ├── repository_connection_node.py
│   │       ├── repository_scan_node.py
│   │       ├── vulnerability_scan_node.py
│   │       ├── technology_detection_node.py
│   │       ├── architecture_detection_node.py
│   │       ├── deployment_detection_node.py
│   │       ├── security_requirement_inference_node.py
│   │       ├── workflow_generator.py
│   │       ├── workflow_validator.py
│   │       ├── workflow_repair_node.py
│   │       ├── github_branch_creation_node.py
│   │       ├── pull_request_creation_node.py
│   │       ├── workflow_execution.py
│   │       ├── execution_monitor.py
│   │       ├── execution_log_collection_node.py
│   │       ├── workflow_failure_analysis_node.py
│   │       ├── root_cause_detection_node.py
│   │       ├── workflow_remediation_generation_node.py
│   │       ├── remediation_pr_creation_node.py
│   │       ├── security_analyzer.py
│   │       ├── risk_assessor.py
│   │       ├── compliance_mapper.py
│   │       ├── recommendation_gen.py
│   │       ├── response_formatter.py
│   │       └── error_handler.py
│   ├── services/
│   │   ├── llm_service.py           # LLM integration (Kimi 2.7 Coder via OpenCode)
│   │   ├── github_service.py        # GitHub API client
│   │   ├── pipeline_service.py      # Orchestration service [UPDATED]
│   │   ├── security_service.py
│   │   └── compliance_service.py
│   └── models/
│       └── schemas.py               # Pydantic models
├── tests/
└── requirements.txt
```

### 3.4 Database Architecture

**Backend Database Schema** (PostgreSQL via GORM):

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────<│  Project    │────<│ Repository  │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                       │
       │  ┌────────────────┐                   │
       └──│ RefreshToken   │        ┌──────────┴──────────┐
          └────────────────┘        │                     │
                             ┌──────┴───────┐      ┌──────┴──────┐
                             │Repository   │      │  Pipeline   │
                             │Insight (1:1)│      └──────┬──────┘
                             └─────────────┘             │
                                                 ┌────────┴────────┐
                                                 │                 │
                                          ┌──────┴──────┐  ┌──────┴──────┐
                                          │ PipelineRun │──│PipelineAnaly│
                                          │+remediation  │  │sis (1:1)    │
                                          │_status [NEW] │  └─────────────┘
                                          └─────────────┘
```

**AI Service Database Tables** (PostgreSQL via raw SQL):

```
┌─────────────────────┐
│  workflow_executions │
├─────────────────────┤
│ id (PK)             │
│ generation_id       │
│ github_run_id       │
│ status              │
│ conclusion          │
│ created_at          │
│ updated_at          │
└──────┬──────────────┘
       │
       ├───────────────────────────────────────┐
       │                                       │
┌──────┴──────┐  ┌─────────────────┐  ┌───────┴───────┐
│  findings   │  │ risk_assessments│  │recommendations│
├─────────────┤  ├─────────────────┤  ├───────────────┤
│ id (PK)     │  │ id (PK)         │  │ id (PK)       │
│ execution_id│  │ execution_id    │  │ execution_id  │
│ scanner     │  │ risk_score      │  │ title         │
│ title       │  │ security_posture│  │ description   │
│ finding_type│  │ compliance_score│  │ impact        │
│ severity    │  │ severity_breakdn│  │ remediation   │
│ file        │  │ total_findings  │  │ example_before│
│ line        │  │ risk_level      │  │ example_after │
│ code_snippet│  │ created_at      │  │ priority      │
│ explanation │  └─────────────────┘  │ created_at    │
│ recommend.  │                       └───────────────┘
│ cwe         │
│ owasp       │  ┌─────────────────────┐
│ created_at  │  │ compliance_mappings │
└─────────────┘  ├─────────────────────┤
                 │ id (PK)             │
                 │ execution_id        │
                 │ framework           │
                 │ control_id          │
                 │ control_name        │
                 │ status              │
                 │ finding_ids         │
                 │ created_at          │
                 └─────────────────────┘
```

### 3.5 GitHub Integration

**Integration Points**:

1. **Repository Access**
   - List repositories
   - Get repository details
   - Access file contents
   - Get language statistics

2. **Workflow Management**
   - Create workflow files
   - Trigger workflow dispatch
   - Get workflow runs
   - Get job details
   - Cancel workflow runs

3. **Webhook Events**
   - `push`: Branch updates
   - `pull_request`: PR events
   - `workflow_run`: Pipeline execution events

**Webhook Configuration**:
```json
{
  "events": ["push", "pull_request", "workflow_run"],
  "url": "https://api.devsecops-system.com/api/v1/webhooks/github",
  "content_type": "json"
}
```

### 3.6 Component Interaction

**Sequence: Pipeline Generation**

```
Frontend          Backend           AI Service        GitHub
    │                 │                  │                │
    │ POST /generate  │                  │                │
    │────────────────>│                  │                │
    │                 │ POST /repo/pipeline                  │
    │                 │────────────────>│                  │
    │                 │                  │                  │
    │                 │                  │ GET /repos/*    │
    │                 │                  │────────────────>│
    │                 │                  │<────────────────│
    │                 │                  │                  │
    │                 │                  │ [LangGraph]     │
    │                 │                  │ scan → detect   │
    │                 │                  │ → deploy_detect │
    │                 │                  │ → infer → gen    │
    │                 │                  │                  │
    │                 │                  │ POST /repos/*/.. │
    │                 │                  │────────────────>│
    │                 │                  │<────────────────│
    │                 │                  │                  │
    │                 │ {workflow, yaml} │                  │
    │                 │<────────────────│                  │
    │                 │                  │                  │
    │ 201 Created     │                  │                  │
    │<────────────────│                  │                  │
```

**Sequence: Run Monitoring via Webhook**

```
GitHub           Backend           AI Service        Database
  │                 │                  │                │
  │ workflow_run   │                  │                │
  │────────────────>│                  │                │
  │                 │ parse event      │                │
  │                 │ UPDATE run       │                │
  │                 │────────────────────────────>      │
  │                 │                  │                │
  │                 │ POST /analyze/*  │                │
  │                 │────────────────>│                  │
  │                 │                  │                  │
  │                 │                  │ fetch logs      │
  │                 │                  │────────────────>│
  │                 │                  │<────────────────│
  │                 │                  │                  │
  │                 │                  │ [LangGraph]     │
  │                 │                  │ security_analysis
  │                 │                  │ → risk_assessment
  │                 │                  │ → compliance_map
  │                 │                  │ → recommend_gen  │
  │                 │                  │                  │
  │                 │                  │ INSERT analysis │
  │                 │                  │────────────────>│
  │                 │                  │<────────────────│
  │                 │                  │                  │
  │ 200 OK          │                  │                  │
  │<────────────────│                  │                  │
```

**Sequence: Failure Remediation (NEW)**

```
Frontend              Backend          AI Service       GitHub
    │                     │                │                │
    │ Remediation page    │                │                │
    │ (RunRemediation)    │                │                │
    │ POST /ai/pipeline/  │                │                │
    │ analyze-execution/  │                │                │
    │ {run_id}            │                │                │
    │─────────────────────────────────────>│                │
    │                     │                │                │
    │                     │                │ [5 manual nodes]
    │                     │                │ log_collection │
    │                     │                │ → failure_anal │
    │                     │                │ → root_cause   │
    │                     │                │ → remediation  │
    │                     │                │ → PR creation  │
    │                     │                │                │
    │                     │                │ GET /repos/*   │
    │                     │                │───────────────>│
    │                     │                │<───────────────│
    │                     │                │                │
    │                     │                │ POST PR to repo│
    │                     │                │───────────────>│
    │                     │                │<───────────────│
    │                     │                │                │
    │ {failure_analysis,  │                │                │
    │  root_cause,        │                │                │
    │  remediation_yaml,  │                │                │
    │  remediation_pr_url}│                │                │
    │<─────────────────────────────────────│                │
    │                     │                │                │
    │ "Deploy Fix" button │                │                │
    │ POST /ai/pipeline/  │                │                │
    │ deploy-remediation  │                │                │
    │─────────────────────────────────────>│                │
    │                     │                │                │
    │                     │                │ create branch, │
    │                     │                │ commit YAML,   │
    │                     │                │ create PR,     │
    │                     │                │ trigger dispatch│
    │                     │                │                │
    │ {pr_url, pipeline_  │                │                │
    │  version}            │                │                │
    │<─────────────────────────────────────│                │
```

---

## 4. AI Agent Architecture

### 4.1 Agent Overview

AI Agent dalam sistem ini diimplementasikan sebagai node-node dalam LangGraph state machine. Setiap node merupakan Python function yang memodifikasi state bersama (`PipelineEngineerState`) dan berkomunikasi melalui typed state dictionary. Berbeda dengan pendekatan prompt-based yang umum, setiap node memiliki logika spesifik yang dapat memanggil LLM atau menjalankan logic Python langsung.

Sistem memiliki total **26 node**: 20 dalam compiled graph utama dan 6 dipanggil manual melalui `PipelineService._invoke_graph_phase()`.

### 4.2 State Definition

State yang digunakan adalah `PipelineEngineerState` TypedDict dengan field-field berikut:

| Category | Fields |
|----------|--------|
| Request | `request_type`, `github_token`, `repository_url`, `repository_full_name`, `repository_default_branch` |
| Scan | `repository_structure`, `repository_files`, `source_files`, `existing_workflows` |
| Technology | `detected_technologies`, `detected_architecture`, `detected_architecture_type`, `detected_architecture_confidence`, `detected_architecture_reason` |
| Deployment | `detected_deployment`, `recommended_deployment_target` |
| Security | `inferred_security_needs` |
| Generation | `generated_workflow`, `generated_stages`, `generation_explanation` |
| Validation | `validation_errors`, `validation_warnings`, `validation_passed` |
| Deployment | `github_branch`, `github_commit_sha`, `github_pr_number`, `github_pr_url` |
| Execution | `workflow_run_id`, `workflow_status`, `workflow_conclusion`, `workflow_logs`, `workflow_jobs`, `workflow_duration_seconds`, `raw_logs` |
| Failure | `failed_jobs`, `failed_steps`, `failure_logs`, `failure_analysis`, `root_cause`, `remediation_suggestions`, `remediation_workflow`, `remediation_branch`, `remediation_pr_number`, `remediation_pr_url` |
| Analysis | `scan_results`, `findings`, `risk_score`, `security_posture`, `compliance_score`, `compliance_mappings`, `severity_breakdown`, `recommendations`, `summary` |
| Error | `errors`, `error_stage` |
| Control | `auto_deploy`, `pipeline_version`, `workflow_file` |

### 4.3 Node Definitions

#### 4.3.1 Repository Connection Node

**Nama**: `repository_connection`
**File**: `repository_connection_node.py`
**Responsibility**: Menghubungkan ke GitHub repository dan validasi akses.

**Input**:
- `repo_url`: GitHub repository URL
- `github_token`: GitHub access token

**Output**:
- `repository_metadata`: Repository info (owner, name, default_branch, languages_url)
- `connection_status`: "connected" | "failed"

**Logic**:
1. Validate repository URL format
2. Call GitHub API to verify repository exists
3. Verify token permissions
4. Return repository metadata

**Downstream Node**: `repository_scan`

---

#### 4.3.2 Repository Scan Node

**Nama**: `repository_scan`
**File**: `repository_scan_node.py`
**Responsibility**: Memindai struktur repository untuk mengidentifikasi file-file kunci dan source code.

**Input**:
- `repository_metadata`: Dari repository_connection
- `github_token`: GitHub access token

**Output**:
- `file_structure`: Tree of important files
- `repository_files`: Dictionary of file paths → content
- `source_files`: Source code files dengan content
- `key_files`: Array of file paths (package.json, requirements.txt, dll.)
- `has_dockerfile`: Boolean
- `has_docker_compose`: Boolean
- `has_existing_workflows`: Boolean, existing workflow content

**Logic**:
1. List repository root contents
2. Recursively scan for key configuration files
3. Check for Docker-related files
4. Check for existing GitHub Actions workflows
5. Read source code files
6. Return structured file inventory

**Key Files Detection**:
- Node.js: `package.json`, `package-lock.json`, `tsconfig.json`
- Python: `requirements.txt`, `setup.py`, `pyproject.toml`
- Java: `pom.xml`, `build.gradle`
- Go: `go.mod`, `go.sum`

**Downstream Node**: `vulnerability_scan`

---

#### 4.3.3 Vulnerability Scan Node

**Nama**: `vulnerability_scan`
**File**: `vulnerability_scan_node.py`
**Responsibility**: Melakukan LLM-based SAST scan terhadap source code untuk mendeteksi kerentanan.

**Input**:
- `source_files`: Source code files
- `repository_files`: Configuration files

**Output**:
- `scan_results`: LLM-based vulnerability findings
- Detected vulnerability patterns

**Logic**:
1. Feed source code to LLM for analysis
2. Detect common vulnerability patterns (injection, XSS, etc.)
3. Score severity
4. Return findings

**Downstream Node**: `technology_detection`

---

#### 4.3.4 Technology Detection Node

**Nama**: `technology_detection`
**File**: `technology_detection_node.py`
**Responsibility**: Mendeteksi bahasa pemrograman, framework, build tools, test frameworks, dan package managers.

**Input**:
- `repository_metadata`: Language statistics
- `repository_files`: Parsed dependency files

**Output**:
- `primary_language`: Main programming language
- `secondary_languages`: Array of secondary languages
- `frameworks`: Detected frameworks
- `build_tools`: Build tools (npm, maven, gradle, make, dll.)
- `test_frameworks`: Test frameworks
- `package_managers`: Package managers (npm, pip, maven, etc.)
- `deployment_target`: Deployment environment (detected via file patterns)
- `confidence_scores`: Detection confidence per category

**Detection Logic**:
```python
def detect_technology(files, languages):
    # Language detection
    primary = max(languages, key=languages.get)
    
    # Framework detection via file patterns
    frameworks = []
    if "package.json" in files:
        deps = parse_package_json()
        if "react" in deps: frameworks.append("React")
        if "vue" in deps: frameworks.append("Vue")
        if "next" in deps: frameworks.append("Next.js")
    # Similar for other ecosystems
    
    # Build tool detection
    build_tools = []
    if exists("package.json"): build_tools.append("npm")
    if exists("pom.xml"): build_tools.append("maven")
    if exists("go.mod"): build_tools.append("go")
    
    return TechnologyMetadata(...)
```

**Downstream Node**: `architecture_detection`

---

#### 4.3.5 Architecture Detection Node

**Nama**: `architecture_detection`
**File**: `architecture_detection_node.py`
**Responsibility**: Mengklasifikasikan arsitektur repository.

**Input**:
- `file_structure`: Repository structure
- `repository_files`: Parsed files
- `detected_technologies`: From technology_detection

**Output**:
- `detected_architecture`: Full architecture info
- `detected_architecture_type`: "monolith" | "microservices" | "frontend_backend" | "modular_monolith"
- `detected_architecture_confidence`: Classification confidence
- `detected_architecture_reason`: Reasoning string

**Classification Logic**:
```python
def classify_architecture(structure, tech):
    score = 0
    
    # Microservices indicators
    if docker_compose_count >= 2: score += 30
    if has_api_gateway_pattern(structure): score += 20
    if has_service_discovery(structure): score += 20
    if multiple_api_manifests(structure): score += 15
    
    # Monolith indicators
    if single_main_entry(structure): score -= 30
    if unified_package_manager(structure): score -= 20
    
    # Frontend+Backend indicators
    if separate_frontend_backend_dirs(structure): 
        return "frontend_backend"
    
    if score > 30: return "microservices"
    elif score > -20: return "modular_monolith"
    else: return "monolith"
```

**Downstream Node**: `deployment_detection`

---

#### 4.3.6 Deployment Detection Node

**Nama**: `deployment_detection`
**File**: `deployment_detection_node.py`
**Responsibility**: Mendeteksi target deployment environment.

**Input**:
- `file_structure`: Repository structure
- `detected_technologies`: Technology metadata

**Output**:
- `detected_deployment`: Full deployment info
- `recommended_deployment_target`: Primary deployment target recommendation
- Detection flags: has_dockerfile, has_docker_compose, has_kubernetes, has_terraform, cloud_provider

**Logic**:
1. Check for Docker files
2. Check for Kubernetes manifests
3. Check for Terraform/HCL files
4. Check for Serverless configuration
5. Determine recommended target

**Downstream Node**: `security_requirement_inference`

---

#### 4.3.7 Security Requirement Inference Node

**Nama**: `security_requirement_inference`
**File**: `security_requirement_inference_node.py`
**Responsibility**: Melakukan inferensi kebutuhan keamanan berdasarkan teknologi, arsitektur, dan deployment.

**Input**:
- `detected_technologies`: Language, frameworks, tools
- `detected_architecture_type`: Monolith/Microservices
- `detected_deployment`: Target deployment environment

**Output**:
- `inferred_security_needs`: Full security requirements
- `security_controls`: Array of required security controls
- `compliance_standards`: Applicable compliance standards
- `scan_requirements`: Security scans to include
- `secrets_management`: Recommended secrets management

**Inference Logic**:
```python
def infer_security_requirements(tech, arch, deployment):
    controls = []
    compliance = []
    scans = []
    
    # Language-specific controls
    if "node" in tech.languages:
        controls.extend(["npm_audit", "snyk_scan", "secret_scanning"])
        scans.extend(["SAST_ESLint", "Dependency_Check"])
        compliance.append("OWASP_Top10")
    
    if "python" in tech.languages:
        controls.extend(["safety_check", "bandit_scan", "secret_scanning"])
        scans.extend(["SAST_Bandit", "PyUp_Safety"])
        compliance.append("OWASP_Top10")
    
    # Architecture-specific controls
    if arch == "microservices":
        controls.append("service_mesh_security")
        controls.append("network_policy_enforcement")
    
    # Deployment-specific controls (from deployment_detection)
    if deployment.target == "kubernetes":
        controls.extend(["trivy_scan", "kube_bench", "rbac_audit"])
    
    return SecurityRequirements(...)
```

**Downstream Node**: `workflow_generation`

---

#### 4.3.8 Workflow Generation Node

**Nama**: `workflow_generation`
**File**: `workflow_generator.py`
**Responsibility**: Menghasilkan GitHub Actions workflow YAML via LLM.

**Input**:
- `repository_metadata`: Repository info
- `detected_technologies`: Tech stack
- `detected_architecture_type`: Classification
- `detected_deployment`: Deployment target
- `inferred_security_needs`: Required controls
- User preferences (via `auto_deploy`, etc.)

**Output**:
- `generated_workflow`: YAML content
- `generated_stages`: Array of pipeline stages
- `generation_explanation`: AI explanation of workflow

**Generation Process**:
1. Build context prompt dengan semua metadata
2. Call LLM dengan generation prompt
3. Parse YAML output dari LLM response
4. Validate generated YAML structure
5. Return workflow content

**LLM Prompt Structure**:
```
Generate a GitHub Actions workflow for:
- Language: {language}
- Framework: {framework}
- Architecture: {architecture}
- Deployment: {deployment_target}
- Security Controls: {controls}

Requirements:
- Use SHA-pinned actions
- Minimal permissions
- Include: {required_scans}
- Trigger on: push, pull_request

Output format: YAML workflow
```

**Model Configuration**:
- Model: Kimi 2.7 Coder (via OpenCode)
- Temperature: 0.3
- Max tokens: 4096

**Downstream Node**: `workflow_validation`

---

#### 4.3.9 Workflow Validation Node

**Nama**: `workflow_validation`
**File**: `workflow_validator.py`
**Responsibility**: Memvalidasi generated workflow.

**Input**:
- `generated_workflow`: YAML content
- `inferred_security_needs`: Required controls

**Output**:
- `validation_passed`: Boolean
- `validation_errors`: Array of errors
- `validation_warnings`: Array of warnings

**Validation Checks**:

1. **Syntax Validation** - Valid YAML, required fields, job structure
2. **SHA Pinning** - Actions use commit hash
3. **Permissions** - Minimal permissions
4. **Security Controls** - Required scans included
5. **Best Practices** - Caching, timeouts, error handling

**Downstream Node**:
- `passed` → `auto_deploy_check`
- `failed` → `error_handler` (auto-repair via `workflow_repair` diinvoke manual oleh `run_repo_generate()`)

---

#### 4.3.10 Workflow Repair Node

**Nama**: `workflow_repair`
**File**: `workflow_repair_node.py`
**Type**: Manual invocation (not in compiled graph; invoked in `run_repo_generate()` flow)
**Responsibility**: Otomatis memperbaiki workflow yang gagal validasi.

**Input**:
- `generated_workflow`: Original YAML
- `validation_errors`: Errors to fix

**Output**:
- `repaired_workflow`: Fixed YAML
- `repair_attempts`: Number of repair attempts

**Repair Logic**:
1. Analyze validation errors
2. Generate repair prompt
3. Call LLM dengan repair instruction
4. Re-validate repaired workflow
5. Maximum 2 retry attempts

---

#### 4.3.11 Auto Deploy Check Node

**Nama**: `auto_deploy_check`
**File**: Inline lambda in `pipeline_graph.py`
**Responsibility**: Decision node — passes state through untuk conditional branching.

**Input**: Full state
**Output**: Unmodified state
**Conditional Edges**: Based on `auto_deploy` flag

---

#### 4.3.12 GitHub Branch Creation Node

**Nama**: `github_branch_creation`
**File**: `github_branch_creation_node.py`
**Responsibility**: Membuat branch baru untuk workflow deployment.

**Input**:
- `repository_full_name`: Repository info
- `github_token`: Access token

**Output**:
- `github_branch`: Generated branch name
- `github_commit_sha`: Initial commit SHA

**Logic**:
1. Generate unique branch name: `devsecops-pipeline-{timestamp}`
2. Create branch dari default branch
3. Return branch details

**Downstream Node**: `pull_request_creation`

---

#### 4.3.13 Pull Request Creation Node

**Nama**: `pull_request_creation`
**File**: `pull_request_creation_node.py`
**Responsibility**: Commit workflow file dan buat Pull Request.

**Input**:
- `repository_full_name`: Repository info
- `github_branch`: Target branch
- `generated_workflow`: YAML content

**Output**:
- `github_pr_number`: Pull Request number
- `github_pr_url`: Pull Request URL

**Logic**:
1. Commit workflow file di `.github/workflows/devsecops-pipeline.yml`
2. Create PR dengan description
3. Return PR details

**Downstream Node**: `workflow_execution`

---

#### 4.3.14 Workflow Execution Node

**Nama**: `workflow_execution`
**File**: `workflow_execution.py`
**Responsibility**: Trigger workflow dispatch di GitHub.

**Input**:
- `repository_full_name`: Repository info
- `github_branch`: Branch with workflow
- `workflow_file`: Workflow file name

**Output**:
- `workflow_run_id`: GitHub run ID

**Logic**:
1. Call GitHub API workflow_dispatch
2. Return run details

**Downstream Node**: `execution_monitor`

---

#### 4.3.15 Execution Monitor Node

**Nama**: `execution_monitor`
**File**: `execution_monitor.py`
**Responsibility**: Polling eksekusi workflow sampai selesai.

**Input**:
- `workflow_run_id`: GitHub run ID
- `repository_full_name`: Repository info

**Output**:
- `workflow_status`: "queued" | "in_progress" | "completed"
- `workflow_conclusion`: "success" | "failure" | "cancelled" | "skipped"
- `workflow_duration_seconds`: Total execution time
- `workflow_jobs`: Job details

**Monitoring Logic**:
```python
def monitor_execution(run_id, repo):
    timeout = 1800  # 30 minutes
    interval = 5    # seconds
    
    while elapsed < timeout:
        status = github.get_workflow_status(run_id, repo)
        
        if status == "completed":
            return format_completion(status)
        
        sleep(interval)
    
    return timeout_result()
```

**Downstream Node**:
- `completed` → `security_analysis`
- `timeout/error` → `error_handler`

> **Note**: Failure analysis (`execution_log_collection` → `failure_analysis` → `root_cause_detection` → `remediation_generation` → `remediation_pr_creation`) diinvoke terpisah via `/api/pipeline/analyze-execution/{run_id}`, bukan bagian dari compiled graph. Remediation deployment juga bisa dilakukan standalone via `/api/pipeline/deploy-remediation`.

---

#### 4.3.16 Execution Log Collection Node

**Nama**: `execution_log_collection`
**File**: `execution_log_collection_node.py`
**Type**: Manual invocation
**Responsibility**: Mengumpulkan logs dari workflow execution yang gagal.

**Input**:
- `workflow_run_id`: GitHub run ID
- `repository_full_name`: Repository info

**Output**:
- `workflow_logs`: Combined log content
- `failed_jobs`: Jobs yang gagal
- `failed_steps`: Steps yang gagal
- `failure_logs`: Per-job failure logs

---

#### 4.3.17 Failure Analysis Node

**Nama**: `failure_analysis`
**File**: `workflow_failure_analysis_node.py`
**Type**: Manual invocation
**Responsibility**: Menganalisis kegagalan workflow.

**Input**:
- `workflow_logs`: Log content
- `failed_jobs`: Failed job details

**Output**:
- `failure_analysis`: Structured failure summary dan patterns

---

#### 4.3.18 Root Cause Detection Node

**Nama**: `root_cause_detection`
**File**: `root_cause_detection_node.py`
**Type**: Manual invocation
**Responsibility**: Mendeteksi akar penyebab kegagalan.

**Detection Categories**:
- `configuration_error`: Wrong configuration
- `dependency_error`: Missing/broken dependencies
- `permission_error`: Insufficient permissions
- `network_error`: Network connectivity issues
- `resource_error`: Out of memory/disk
- `test_failure`: Tests failed
- `security_scan_failure`: Security scan found issues

**Downstream Node**: `remediation_generation`

---

#### 4.3.19 Remediation Generation Node

**Nama**: `remediation_generation`
**File**: `workflow_remediation_generation_node.py`
**Type**: Manual invocation
**Responsibility**: Menghasilkan perbaikan untuk workflow yang gagal via LLM.

**Input**:
- `root_cause`: Detected root cause
- `generated_workflow`: Original YAML
- `failure_analysis`: Failure context

**Output**:
- `remediation_workflow`: Fixed workflow YAML
- `remediation_suggestions`: Explanation of changes

**Downstream Node**: `remediation_pr_creation`

---

#### 4.3.20 Remediation PR Creation Node

**Nama**: `remediation_pr_creation`
**File**: `remediation_pr_creation_node.py`
**Type**: Manual invocation
**Responsibility**: Membuat Pull Request dengan perbaikan.

**Input**:
- `remediation_workflow`: Fixed workflow
- `repository_full_name`: Repository info

**Output**:
- `remediation_pr_url`: PR URL
- `remediation_branch`: Branch name
- `remediation_pr_number`: PR number

---

#### 4.3.21 Security Analysis Node

**Nama**: `security_analysis`
**File**: `security_analyzer.py`
**Responsibility**: Melakukan analisis keamanan terhadap execution results.

**Input**:
- `workflow_logs`: Workflow logs
- `workflow_jobs`: Job results
- `inferred_security_needs`: Original security requirements

**Output**:
- `findings`: Array of security findings
- `scan_results`: Full security scan results

**Downstream Node**: `risk_assessment`

---

#### 4.3.22 Risk Assessment Node

**Nama**: `risk_assessment`
**File**: `risk_assessor.py`
**Responsibility**: Menghitung risk score berdasarkan findings menggunakan metodologi OWASP Risk Rating.

**Input**:
- `findings`: From security_analysis
- `workflow_jobs`: Execution metadata

**Output**:
- `risk_score`: Overall risk score (0-100)
- `security_posture`: Security posture score
- `severity_breakdown`: Breakdown by severity
- `risk_level`: "critical" | "high" | "medium" | "low"

**Risk Calculation (OWASP Risk Rating)**:
```python
def calculate_risk_score(findings, workflow_jobs):
    if not findings:
        return {"risk_score": 100, "risk_level": "low"}

    total_risk = 0
    n = len(findings)

    for f in findings:
        # Likelihood: avg of exploitability and exposure
        exploit  = map_exploitability(f)   # 1-5 scale
        exposure = map_exposure(f)          # 1-5 scale
        L = (exploit + exposure) / 2

        # Impact: avg of confidentiality, integrity, availability
        conf  = map_confidentiality(f)      # 1-5 scale
        integ = map_integrity(f)            # 1-5 scale
        avail = map_availability(f)         # 1-5 scale
        I = (conf + integ + avail) / 3

        # Finding risk: L * I -> 1-25 scale
        finding_risk = L * I
        total_risk += finding_risk

    # Normalize: 100 - (avg_risk / 25 * 100)
    avg_risk = total_risk / max(1, n)
    risk_score = clamp(100 - (avg_risk / 25 * 100), 0, 100)

    if risk_score <= 25:   risk_level = "critical"
    elif risk_score <= 50: risk_level = "high"
    elif risk_score <= 75: risk_level = "medium"
    else:                  risk_level = "low"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "severity_breakdown": count_by_severity(findings)
    }
```

**Downstream Node**: `compliance_mapper`

---

#### 4.3.23 Compliance Mapper Node

**Nama**: `compliance_mapper`
**File**: `compliance_mapper.py`
**Responsibility**: Mapping findings ke compliance frameworks (OWASP CICD controls, OWASP Top 10, CIS Benchmarks) dan menghitung compliance score.

**Input**:
- `findings`: From security_analysis
- `inferred_security_needs`: Target standards

**Output**:
- `compliance_score`: Score against standards (0-100)
- `compliance_mappings`: Findings mapped to controls

**Compliance Calculation**:

```python
def calculate_compliance(findings, security_needs, workflow_jobs):
    scores = []
    mappings = []

    # OWASP CICD Controls
    if "OWASP_CICD_Controls" in security_needs.compliance_standards:
        total = len(OWASP_CICD_CONTROLS)
        compliant = 0
        for control in OWASP_CICD_CONTROLS:
            if has_control_step(control, workflow_jobs):
                compliant += 1
                mappings.append({"control": control, "status": "passed"})
            else:
                mappings.append({"control": control, "status": "not_implemented"})
        scores.append(compliant / total * 100)

    # OWASP Top 10 coverage
    if "OWASP_Top10" in security_needs.compliance_standards:
        covered = set(f.owasp for f in findings if f.owasp)
        scores.append(len(covered) / 10 * 100)

    # CIS Benchmarks
    if "CIS_Kubernetes_Benchmark" in security_needs.compliance_standards:
        cis_controls = get_cis_controls("kubernetes")
        compliant = count(c for c in cis_controls if has_passing_step(c))
        scores.append(compliant / len(cis_controls) * 100)

    compliance_score = int(average(scores)) if scores else 0
    return {"compliance_score": compliance_score, "compliance_mappings": mappings}
```

**Formula**:

$$\text{ComplianceScore} = \text{AVG}\left(
\frac{\text{compliant\_owasp\_cicd}}{\text{total\_owasp\_cicd}} \times 100,\;
\frac{\text{owasp\_top10\_covered}}{10} \times 100,\;
\frac{\text{compliant\_cis}}{\text{total\_cis}} \times 100
\right)$$

**Downstream Node**: `recommendation_generation`

---

#### 4.3.24 Recommendation Generation Node

**Nama**: `recommendation_generation`
**File**: `recommendation_gen.py`
**Responsibility**: Menghasilkan actionable recommendations via LLM.

**Input**:
- `findings`: Security findings
- `risk_score`: Calculated risk
- `compliance_mappings`: Compliance mappings
- Execution context

**Output**:
- `recommendations`: Array of recommendations dengan priority, impact, remediation

**Recommendation Structure**:
```python
{
    "category": "security",
    "title": "Update vulnerable dependencies",
    "description": "Update lodash to version >= 4.17.21",
    "impact": "Critical",
    "effort": "low",
    "action_items": ["npm update lodash", "npm audit fix"],
    "references": ["CVE-2021-23337", "OWASP A9"]
}
```

**Downstream Node**: `response_formatter`

---

#### 4.3.25 Response Formatter Node

**Nama**: `response_formatter`
**File**: `response_formatter.py`
**Responsibility**: Memformat response akhir untuk client.

**Input**: Semua output dari nodes sebelumnya

**Output**:
- `summary`: Human-readable summary
- Final formatted response

**Format**:
```json
{
  "status": "success",
  "workflow": {...},
  "analysis": {
    "risk_score": 75,
    "compliance_score": 85,
    "security_coverage": 90,
    "findings": [...],
    "recommendations": [...]
  },
  "explanation": "Generated workflow includes..."
}
```

---

#### 4.3.26 Error Handler Node

**Nama**: `error_handler`
**File**: `error_handler.py`
**Responsibility**: Handle errors di setiap stage.

**Input**:
- `errors`: Error messages
- `error_stage`: Current stage
- Full state context

**Output**:
- Formatted error response
- Recovery suggestion

**Downstream Node**: `response_formatter` (error response)

---

## 5. AI Workflow Graph

### 5.1 Complete Execution Graph

```
                    ┌─────────────────┐
                    │   START         │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  repository_connection      │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     repository_scan         │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    vulnerability_scan        │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   technology_detection       │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   architecture_detection     │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    deployment_detection      │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ security_requirement_inference│
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    workflow_generation       │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   workflow_validation        │
              └──────────────┬──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
         ┌────┴────┐                  ┌────┴────┐
         │ PASSED  │                  │ FAILED  │
         └────┬────┘                  └────┬────┘
              │                             │
              ▼                             ▼
    ┌──────────────────┐       ┌──────────────────┐
    │ auto_deploy_check│       │   error_handler  │
    └────────┬─────────┘       └────────┬─────────┘
             │                           │
      ┌──────┴──────┐                    │
      │             │                    │
  ┌───┴───┐   ┌────┴────┐               │
  │ Deploy│   │  Skip   │               │
  └───┬───┘   └────┬────┘               │
      │            │                    │
      ▼            ▼                    ▼
┌─────────────┐              ┌─────────────────────┐
│   github_   │              │  response_formatter │
│ branch_     │              └─────────────────────┘
│ creation    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ pull_request│
│ _creation   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   workflow_ │
│  execution  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  execution_ │
│   monitor   │
└──────┬──────┘
       │
  ┌────┴────┐
  │         │
┌─┴───┐ ┌───┴───┐
│Comp │ │Timeout│
│leted│ │/Error │
└─┬───┘ └───┬───┘
  │         │
  ▼         ▼
┌──────────────────┐  ┌──────────────────┐
│  security_       │  │   error_handler  │
│  analysis        │  └────────┬─────────┘
└──────┬───────────┘           │
       │                       │
       ▼                       │
┌──────────────────┐           │
│ risk_assessment  │           │
└──────┬───────────┘           │
       │                       │
       ▼                       │
┌──────────────────┐           │
│ compliance_mapper│           │
└──────┬───────────┘           │
       │                       │
       ▼                       │
┌──────────────────┐           │
│recommendation_   │           │
│    generation    │           │
└──────┬───────────┘           │
       │                       │
       ▼                       │
┌──────────────────┐           │
│  response_       │◄──────────┘
│  formatter       │
└──────────────────┘
```

### 5.2 Graph Transitions

| From | To | Condition |
|------|-----|-----------|
| START | repository_connection | Initial request |
| repository_connection | repository_scan | Connection successful |
| repository_connection | error_handler | Connection failed |
| repository_scan | vulnerability_scan | Scan completed |
| vulnerability_scan | technology_detection | SAST scan done |
| technology_detection | architecture_detection | Tech detected |
| architecture_detection | deployment_detection | Architecture classified |
| deployment_detection | security_requirement_inference | Deployment target detected |
| security_requirement_inference | workflow_generation | Security requirements inferred |
| workflow_generation | workflow_validation | Workflow generated |
| workflow_validation | auto_deploy_check | Validation passed |
| workflow_validation | error_handler | Validation failed |
| auto_deploy_check | github_branch_creation | auto_deploy = true |
| auto_deploy_check | response_formatter | auto_deploy = false (skip) |
| github_branch_creation | pull_request_creation | Branch created |
| pull_request_creation | workflow_execution | PR created |
| workflow_execution | execution_monitor | Workflow triggered |
| execution_monitor | security_analysis | Execution completed |
| execution_monitor | error_handler | Timeout / error |
| security_analysis | risk_assessment | Analysis done |
| risk_assessment | compliance_mapper | Risk scored |
| compliance_mapper | recommendation_generation | Compliance mapped |
| recommendation_generation | response_formatter | Recommendations generated |
| response_formatter | END | Response ready |

### 5.3 Failure Analysis & Remediation Sub-graph

Sub-graph ini dipanggil manual via `PipelineService.run_execution_analysis()`, bukan bagian compiled graph. Flow mencakup **2 path deployment**:

**Path A: Full Analysis + Remediation** via POST `/api/pipeline/analyze-execution/{run_id}`:

```
┌──────────────────────┐
│ execution_log_       │
│ collection           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ failure_analysis     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ root_cause_          │
│ detection            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ remediation_         │
│ generation           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ remediation_pr_      │
│ creation             │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  response_formatter  │
└──────────────────────┘
```

**Path B: Standalone Remediation Deployment** via POST `/api/pipeline/deploy-remediation`:
(bypasses all analysis nodes, directly deploys a given remediation workflow YAML)

```
Input: { workflow_yaml, repository_id, run_number, base_branch, workflow_file }
           │
           ▼
┌──────────────────────┐
│ create branch        │  (via GitHub API langsung)
│ commit fixed YAML    │
│ create PR            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ persist as new       │
│ pipeline version     │  (_persist_remediation_result)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ trigger workflow_    │
│ dispatch on new      │  (via GitHub API)
│ branch               │
└──────────────────────┘
```

### 5.4 Manual Node Invocation Patterns (PipelineService)

`PipelineService._invoke_graph_phase()` digunakan untuk menginvoke node secara manual di luar compiled graph. Berikut pola invokasi untuk setiap API endpoint:

| Method | Endpoint Target | Node Sequence |
|--------|----------------|---------------|
| `run_repo_analyze()` | POST /repo/analyze | repository_connection → scan → vuln_scan → tech → arch → deploy → security_infer (7 compiled) |
| `run_repo_generate()` | POST /generate, /repo/pipeline | (7 di atas) + workflow_generation → validation → [conditional: workflow_repair → re-validation] |
| `run_repo_deploy()` | POST /deploy | repository_connection → github_branch → PR_creation (3 compiled) |
| `run_repo_execute()` | POST /execute | repository_connection → workflow_execution (2 compiled) |
| `run_execution_analysis()` | POST /analyze-execution/{run_id} | repository_connection → execution_log_collection → failure_analysis → root_cause_detection → remediation_generation → remediation_pr_creation (6, 5 di antaranya manual) |
| `run_pipeline_analysis()` | POST /analyze/{run_id} | security_analysis → risk_assessment → compliance_mapper → recommendation_gen → response_formatter (5 compiled) |
| `deploy_remediation_workflow()` | POST /deploy-remediation | **Tidak pakai _invoke_graph_phase**. Langsung: create_branch → commit_file → create_pr → persist → trigger_dispatch via GitHub API |

---

## 6. Database Design

### 6.1 User Entity

**Purpose**: Menyimpan data pengguna sistem.

**Model** (`models/user.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | gen_random_uuid() |
| email | string (unique) | email | not null |
| password_hash | string | - | not null (bcrypt) |
| name | string | name | not null |
| role | string | role | default: "engineer" |
| created_at | timestamp | created_at | |
| updated_at | timestamp | updated_at | |

**Roles**: `admin`, `engineer`, `viewer`

**Relationships**:
- One-to-Many dengan `Project`
- One-to-Many dengan `RefreshToken`

---

### 6.2 RefreshToken Entity

**Purpose**: Menyimpan refresh token untuk JWT renewal.

**Model** (`models/refresh_token.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| user_id | uuid (FK→users) | user_id | not null, indexed |
| token | string (unique) | token | not null |
| expires_at | timestamp | expires_at | not null |
| created_at | timestamp | created_at | |

**Relationships**:
- Many-to-One dengan `User`

---

### 6.3 Project Entity

**Purpose**: Mengorganisir repositories dalam logical groupings.

**Model** (`models/project.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| user_id | uuid (FK→users) | user_id | not null, indexed |
| name | string | name | not null |
| description | text | description | |
| compliance_tier | varchar(20) | compliance_tier | default: "moderate" |
| created_at | timestamp | created_at | |
| updated_at | timestamp | updated_at | |
| deleted_at | timestamp | - | soft delete |

**Compliance Tiers**: `strict`, `moderate`, `permissive`

**Relationships**:
- Many-to-One dengan `User`
- One-to-Many dengan `Repository`

---

### 6.4 Repository Entity

**Purpose**: Menyimpan GitHub repository connection details.

**Model** (`models/repository.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| project_id | uuid (FK→projects) | project_id | not null, indexed |
| github_id | string | github_id | not null |
| full_name | string | full_name | not null (e.g. "owner/repo") |
| default_branch | string | default_branch | |
| access_token_encrypted | text | - | AES-256-GCM encrypted |
| last_synced_at | timestamp (nullable) | last_synced_at | |
| last_analyzed_at | timestamp (nullable) | last_analyzed_at | |
| created_at | timestamp | created_at | |
| updated_at | timestamp | updated_at | |

**Relationships**:
- Many-to-One dengan `Project`
- One-to-One dengan `RepositoryInsight`
- One-to-Many dengan `Pipeline`

---

### 6.5 RepositoryInsight Entity

**Purpose**: Cache hasil analisis repository.

**Model** (`models/repository_insight.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| repository_id | uuid (FK→repositories) | repository_id | unique, not null |
| primary_language | varchar(100) | primary_language | |
| secondary_languages | jsonb | secondary_languages | default '[]' |
| frameworks | jsonb | frameworks | default '[]' |
| build_tools | jsonb | build_tools | default '[]' |
| package_managers | jsonb | package_managers | default '[]' |
| test_frameworks | jsonb | test_frameworks | default '[]' |
| architecture_type | varchar(50) | architecture_type | |
| has_dockerfile | bool | has_dockerfile | default false |
| has_docker_compose | bool | has_docker_compose | default false |
| has_kubernetes | bool | has_kubernetes | default false |
| has_terraform | bool | has_terraform | default false |
| has_existing_ci_cd | bool | has_existing_ci_cd | default false |
| existing_workflows | jsonb | existing_workflows | default '[]' |
| dependency_ecosystem | jsonb | dependency_ecosystem | default '[]' |
| raw_analysis_output | jsonb | raw_analysis_output | |
| analyzed_at | timestamp (nullable) | analyzed_at | |
| created_at | timestamp | created_at | |
| updated_at | timestamp | updated_at | |

**Relationships**:
- One-to-One dengan `Repository`

---

### 6.6 Pipeline Entity

**Purpose**: Menyimpan generated pipeline configurations.

**Model** (`models/pipeline.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| repository_id | uuid (FK→repositories) | repository_id | not null, indexed |
| version_number | int | version_number | not null (auto-increment per repo) |
| prompt | text | prompt | not null |
| user_requirements | text | user_requirements | TEXT (was JSONB in v2) |
| generated_yaml | text | generated_yaml | not null |
| stages | jsonb | stages | default '[]' |
| ai_explanation | text | ai_explanation | |
| generation_params | jsonb | generation_params | default '{}' |
| validation_results | jsonb | validation_results | |
| deployment_results | jsonb | deployment_results | |
| security_controls_applied | jsonb | security_controls_applied | default '[]' |
| compliance_metadata | jsonb | compliance_metadata | default '{}' |
| status | varchar | status | default: "draft" |
| created_at | timestamp | created_at | |

**Status values**: `draft`, `generated`, `validated`, `deployed`, `failed`

**Relationships**:
- Many-to-One dengan `Repository`
- One-to-Many dengan `PipelineRun`

---

### 6.7 PipelineRun Entity

**Purpose**: Menyimpan eksekusi pipeline runs.

**Model** (`models/pipeline_run.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| pipeline_id | uuid (FK→pipelines) | pipeline_id | not null, indexed |
| run_number | int | run_number | not null |
| github_run_id | int64 | github_run_id | |
| status | varchar | status | default: "pending" |
| conclusion | varchar | conclusion | |
| html_url | text | html_url | |
| started_at | timestamp (nullable) | started_at | |
| completed_at | timestamp (nullable) | completed_at | |
| duration_seconds | int | duration_seconds | |
| jobs | jsonb | jobs | |
| logs_url | text | logs_url | |
| error_message | text | error_message | |
| remediation_status | varchar | remediation_status | ⦗NEW⦘ default: "none"; values: none/remediated/failed |
| created_at | timestamp | created_at | |

**Status values**: `pending`, `queued`, `running`, `completed`, `failed`
**Conclusion values**: `success`, `failure`, `cancelled`, `skipped`
**RemediationStatus values**: `none`, `remediated`, `failed` ⦗NEW⦘

**Relationships**:
- Many-to-One dengan `Pipeline`
- One-to-One dengan `PipelineAnalysis`

---

### 6.8 PipelineAnalysis Entity

**Purpose**: Menyimpan hasil analisis pipeline execution.

**Model** (`models/pipeline_analysis.go`):
| Field | Type | JSON Key | Notes |
|-------|------|----------|-------|
| id | uuid (PK) | id | |
| pipeline_run_id | uuid (FK→pipeline_runs) | pipeline_run_id | not null, unique |
| risk_score | decimal(5,2) | risk_score | |
| compliance_score | decimal(5,2) | compliance_score | |
| workflow_quality_score | decimal(5,2) | workflow_quality_score | |
| security_coverage_score | decimal(5,2) | security_coverage_score | |
| findings_summary | jsonb | findings_summary | |
| severity_breakdown | jsonb | severity_breakdown | default '{}' |
| recommendations | jsonb | recommendations | default '[]' |
| ai_explanation | text | ai_explanation | |
| raw_scan_data | jsonb | raw_scan_data | |
| created_at | timestamp | created_at | |

**Relationships**:
- One-to-One dengan `PipelineRun`

---

### 6.9 Entity Relationships Diagram

```
┌──────────┐       ┌──────────┐       ┌────────────┐
│   User   │──1:N──│ Project  │──1:N──│ Repository │
└────┬─────┘       └──────────┘       └──────┬─────┘
     │                                       │
     │  ┌────────────────┐                   │
     └──│ RefreshToken   │        ┌──────────┴──────────┐
        └────────────────┘        │                     │
                           ┌──────┴───────┐      ┌──────┴──────┐
                           │Repository   │      │  Pipeline   │
                           │Insight (1:1)│      └──────┬──────┘
                           └─────────────┘             │
                                                       │
                                           ┌───────────┴───────────┐
                                           │                       │
                                    ┌──────┴──────┐        ┌───────┴───────┐
                                    │ PipelineRun │──1:1──│PipelineAnalys│
                                    │+remediation_│       │is            │
                                    │status [NEW] │       └──────────────┘
                                    └────────────┘
```

---

## 7. API Design

### 7.1 Backend API (Go/Gin) — `/api/v1`

#### 7.1.1 Public Endpoints

**GET /health**
- Purpose: Health check
- Response: `{ "status": "healthy", "timestamp": "..." }`

**POST /webhooks/github**
- Purpose: GitHub webhook receiver (no auth)
- Headers: `X-GitHub-Event`, `X-Hub-Signature-256`
- Request: GitHub webhook payload
- Response: `{ "received": true }`

**POST /auth/register**
- Purpose: Register new user
- Request: `{ "email": "...", "password": "...", "name": "..." }`
- Response: `{ "id": "uuid", "email": "...", "token": "jwt" }`

**POST /auth/login**
- Purpose: User login
- Request: `{ "email": "...", "password": "..." }`
- Response: `{ "token": "jwt", "refresh_token": "...", "user": {...} }`

**POST /auth/refresh**
- Purpose: Refresh JWT token
- Request: `{ "refresh_token": "..." }`
- Response: `{ "token": "new_jwt" }`

#### 7.1.2 Protected Endpoints (JWT Required)

**GET /me**
- Purpose: Get current user profile
- Response: `{ "id": "uuid", "email": "...", "name": "...", "role": "..." }`

**PUT /me**
- Purpose: Update user profile (name)
- Request: `{ "name": "New Name" }`
- Response: `{ "id": "uuid", "email": "...", "name": "New Name" }`

**POST /auth/change-password**
- Purpose: Change password
- Request: `{ "current_password": "...", "new_password": "..." }`
- Response: `{ "status": "password_changed" }`

**GET /dashboard/stats**
- Purpose: Aggregated dashboard statistics
- Response: `{ "total_projects": 5, "total_repos": 12, "total_pipelines": 45, "total_executions": 234, "success_rate": 0.92, "avg_risk_score": 72, "compliance_score": 85, "security_coverage": 0.88, "recent_pipelines": [...] }`

**GET /projects**
- Purpose: List user projects
- Response: `{ "projects": [...], "total": 5 }`

**POST /projects**
- Purpose: Create new project
- Request: `{ "name": "My Project", "description": "..." }`
- Response: `{ "id": "uuid", "name": "...", ... }`

**GET /projects/:projectId**
- Purpose: Get project details
- Response: `{ "id": "uuid", "name": "...", "repositories": [...], ... }`

**PUT /projects/:projectId/compliance**
- Purpose: Update project compliance tier
- Request: `{ "compliance_tier": "strict" }`
- Response: `{ "updated": true }`

**DELETE /projects/:projectId**
- Purpose: Delete project (soft delete)
- Response: `{ "deleted": true }`

**POST /repositories/connect**
- Purpose: Connect GitHub repository
- Request: `{ "project_id": "uuid", "repo_url": "...", "access_token": "ghp_..." }`
- Response: `{ "id": "uuid", "full_name": "...", "default_branch": "main", "last_analyzed_at": null }`

**GET /projects/:projectId/repositories**
- Purpose: List repositories in project
- Response: `{ "repositories": [...], "total": 3 }`

**GET /repositories/:repoId**
- Purpose: Get repository details
- Response: `{ "id": "uuid", "full_name": "...", "insight": {...} }`

**DELETE /repositories/:repoId**
- Purpose: Delete repository and cleanup
- Response: `{ "deleted": true }`

**GET /repositories/:repoId/insights**
- Purpose: Get repository insights (cached analysis)
- Response: `{ "primary_language": "typescript", "frameworks": ["react"], "architecture_type": "monolith", "has_dockerfile": true, "has_docker_compose": false, "has_kubernetes": false, "has_terraform": false, "package_managers": ["npm"], "dependency_ecosystem": [...], "analyzed_at": "..." }`

**POST /repositories/:repoId/analyze**
- Purpose: Trigger repository analysis (calls AI service)
- Request: (none, uses stored token)
- Response: `{ "analyzed": true, "insight": {...} }`

**GET /pipelines**
- Purpose: List all pipelines (global, paginated)
- Query: `?page=1&limit=20&sort=created_at`
- Response: `{ "pipelines": [...], "total": 45, "page": 1 }`

**GET /pipelines/:pipelineId**
- Purpose: Get pipeline by ID
- Response: Pipeline object dengan generated_yaml

**DELETE /pipelines/:pipelineId**
- Purpose: Delete pipeline
- Response: `{ "deleted": true }`

**POST /pipelines/compare**
- Purpose: Compare two pipelines
- Request: `{ "pipelineIdA": "uuid", "pipelineIdB": "uuid" }`
- Response: `{ "pipelineA": {...}, "pipelineB": {...}, "comparison": { "yaml_diff": "...", "score_delta": {...}, "controls_delta": [...] } }`

**GET /repositories/:repoId/pipelines**
- Purpose: List pipeline versions for repository
- Response: `{ "pipelines": [...], "total": 5 }`

**GET /repositories/:repoId/pipelines/:version**
- Purpose: Get specific pipeline version
- Response: Pipeline object

**DELETE /repositories/:repoId/pipelines/:version**
- Purpose: Delete specific pipeline version
- Response: `{ "deleted": true }`

**POST /repositories/:repoId/pipelines/generate**
- Purpose: Direct trigger pipeline generation (calls AI service)
- Request: `{ "query": "generate CI/CD pipeline", "extra": { "language": "...", "deploy_target": "..." } }`
- Response: `{ "pipeline": {...}, "generated_workflow": "...", "explanation": "..." }`

**POST /repositories/:repoId/pipelines/:version/sync-runs**
- Purpose: Sync runs from GitHub
- Response: `{ "synced": 3, "runs": [...] }`

**GET /pipelines/:pipelineId/runs**
- Purpose: List runs for pipeline
- Response: `{ "runs": [...], "total": 15 }`

**GET /runs/:runId**
- Purpose: Get run detail (live from GitHub)
- Response: `{ "id": "uuid", "status": "completed", "conclusion": "success", "jobs": [...], "duration_seconds": 345, "remediation_status": "none" }` ⦗UPDATED⦘

**POST /runs/:runId/cancel**
- Purpose: Cancel workflow run
- Response: `{ "cancelled": true }`

**GET /runs/:runId/analysis**
- Purpose: Get analysis for run
- Response: `{ "risk_score": 75, "compliance_score": 85, "findings_summary": [...], "recommendations": [...] }`

### 7.2 AI Service API (Python/FastAPI) — `/api/pipeline`

**POST /pipeline/repo/analyze**
- Purpose: Analyze repository (scan + tech + arch + deploy detection)

**POST /pipeline/repo/pipeline**
- Purpose: Full end-to-end pipeline generation (analyze + generate + optional deploy)

**POST /pipeline/generate**
- Purpose: Generate workflow YAML only (with auto-repair on validation failure)

**POST /pipeline/deploy**
- Purpose: Deploy workflow to GitHub as PR

**POST /pipeline/execute**
- Purpose: Trigger workflow dispatch

**POST /pipeline/validate**
- Purpose: Validate workflow YAML

**GET /pipeline/latest-run**
- Purpose: Get latest workflow run

**GET /pipeline/status/{run_id}**
- Purpose: Get run status + jobs

**GET /pipeline/status/{run_id}/stream**
- Purpose: SSE stream for live status updates

**GET /pipeline/logs/{run_id}**
- Purpose: Get raw workflow logs

**POST /pipeline/analyze/{run_id}**
- Purpose: Security analysis of completed run (persists + returns)

**GET /pipeline/analysis/{run_id}**
- Purpose: Retrieve cached analysis for run

**POST /pipeline/analyze-execution/{run_id}**
- Purpose: Failure analysis + root cause + remediation PR generation (5 manual node chain)

**POST /pipeline/deploy-remediation** ⦗NEW⦘
- Purpose: Standalone deployment remediated workflow sebagai PR baru + trigger workflow dispatch
- Request: `{ "repository_id": "owner/repo", "workflow_yaml": "...", "run_number": 3, "base_branch": "main", "workflow_file": "ai-devsecops.yml" }`
- Response: `{ "pr_url": "...", "pipeline_version": 4 }`

**POST /pipeline/compliance**
- Purpose: Compliance check workflow YAML

**POST /pipeline/webhook/github**
- Purpose: GitHub webhook receiver (AI Service directly)

---

## 8. Repository Analysis Mechanism

### 8.1 Language Detection

**Process Flow**:

```
1. Get repository metadata dari GitHub API
   GET /repos/{owner}/{repo}
   → { "language": "TypeScript", "languages_url": "..." }

2. Fetch language statistics
   GET {languages_url}
   → { "TypeScript": 45000, "JavaScript": 12000, "HTML": 3000 }

3. Calculate language percentages
   total = sum(all languages)
   percentages = { lang: count/total for lang in languages }

4. Determine primary and secondary languages
   primary = highest percentage language
   secondary = languages with > 5% share

5. Confidence scoring
   confidence = primary_percentage / 100
   → 80% TypeScript = 0.8 confidence
```

### 8.2 Framework Detection

**Detection Strategy**:
```python
def detect_frameworks(files, package_content):
    frameworks = []
    
    # JavaScript/TypeScript
    if "package.json" in files:
        deps = parse_json(files["package.json"])["dependencies"]
        if "react" in deps: frameworks.append("React")
        if "vue" in deps: frameworks.append("Vue.js")
        if "angular" in deps: frameworks.append("Angular")
        if "next" in deps: frameworks.append("Next.js")
        if "express" in deps: frameworks.append("Express")
        if "nest" in deps: frameworks.append("NestJS")
    
    # Python
    if "requirements.txt" in files or "pyproject.toml" in files:
        deps = parse_requirements(files)
        if "django" in deps: frameworks.append("Django")
        if "flask" in deps: frameworks.append("Flask")
        if "fastapi" in deps: frameworks.append("FastAPI")
    
    # Java
    if "pom.xml" in files:
        deps = parse_pom(files["pom.xml"])
        if "spring-boot" in deps: frameworks.append("Spring Boot")
    
    return frameworks
```

### 8.3 Architecture Detection

**Detection Heuristics**: See Section 4.3.5 (Architecture Detection Node)

### 8.4 Deployment Detection

**Detection Sources**:
1. Dockerfile presence → Docker Container
2. docker-compose.yml → Docker Compose
3. Kubernetes manifests (k8s/ directory) → Kubernetes
4. Helm charts (charts/ directory) → Kubernetes (Helm)
5. Terraform/HCL files (terraform/ directory) → Cloud (AWS/GCP/Azure)
6. Serverless configuration → Serverless

### 8.5 Confidence Scoring

Multi-factor confidence scoring with base confidence adjusted by evidence quality.

---

## 9. Security Requirement Inference

### 9.1 Inference Process

**Input Processing**:
1. Receive technology metadata (language, frameworks, tools, package managers)
2. Receive architecture type (monolith / microservices / frontend_backend)
3. Receive deployment target (Docker, K8s, Terraform, cloud)

**Control Selection Logic**:
- Language-specific controls mapped per detected language
- Framework-specific controls for detected frameworks
- Architecture-specific controls (network for microservices, comprehensive SAST for monoliths)
- Deployment-specific controls based on detected target

### 9.2 Control Categories

| Category | Controls |
|----------|----------|
| Dependency Security | npm_audit, safety_check, owasp_dep_check, govulncheck |
| SAST | bandit, eslint_security, spotbugs, golangci-lint |
| Secret Scanning | detect_secrets, gitleaks, secret_scanning |
| Container Security | trivy_scan, hadolint, container_signing |
| Kubernetes Security | kube_bench, trivy_k8s, rbac_audit, network_policy |
| Compliance | owasp_top10, cis_benchmark, nist_controls, OWASP CICD |

### 9.3 Compliance Standard Mapping

Mapping findings to OWASP CICD security controls and CIS benchmarks.

---

## 10. Pipeline Generation Mechanism

### 10.1 Generation Inputs

**Required**: repository_id, repo_url, github_token, technology_metadata, security_requirements
**Optional**: build_tool, test_framework, deploy_target, additional_config

### 10.2 Generation Process

**Step 1: Context Building** — Build comprehensive context from repo metadata, tech stack, security needs, deployment target
**Step 2: LLM Prompt Construction** — Construct prompt with all requirements
**Step 3: LLM Call** — Call LLM via llm_service (Kimi 2.7 Coder via OpenCode, temperature 0.3, max tokens 4096)
**Step 4: YAML Parsing and Validation** — Parse and validate generated YAML
**Step 5: Auto-Repair (if needed)** — Invoke `workflow_repair` node jika validation gagal, max 2 retries

### 10.3 Validation Process

Syntax validation, SHA pinning check, permission check, security controls check, timeout check, best practices check.

### 10.4 Deployment Process

Branch creation → file commit → Pull Request creation

---

## 11. Pipeline Execution Analysis

### 11.1 GitHub Actions Integration

**Webhook Events**:
| Event | Trigger | Action |
|-------|---------|--------|
| workflow_run | completed | Trigger analysis |
| workflow_run | in_progress | Update status |
| push | - | Update branch reference |
| pull_request | opened/synced | Trigger validation |

**API Endpoints Used**: Run listing, run details, job details, workflow dispatch, cancel workflow

### 11.2 Webhook Processing

Processing flow: validate signature → parse event → update database → trigger AI analysis for completed runs.

### 11.3 Run Collection

Collect run details from GitHub API, update database, fetch jobs if completed.

### 11.4 Job Collection

Structured job data with steps, statuses, conclusions, and durations.

### 11.5 Log Analysis

Pattern-based log analysis for vulnerability detection and error identification.

### 11.6 Risk Scoring

Risk score mengukur tingkat risiko keamanan pipeline berdasarkan temuan dari `security_analysis`. Perhitungan diadaptasi dari metodologi **OWASP Risk Rating** yang menilai setiap temuan pada dua dimensi: **likelihood** (kemungkinan eksploitasi) dan **impact** (dampak jika tereksploitasi).

**Formula**:

Untuk setiap temuan keamanan $i$:

$$L_i = \frac{e_i + x_i}{2}, \quad I_i = \frac{c_i + g_i + a_i}{3}$$

di mana:

| Simbol | Dimensi | Skala | Deskripsi |
|--------|---------|-------|-----------|
| $e_i$ | Exploitability | 1–5 | 1 = teoritis/sulit, 3 = mungkin dengan alat, 5 = exploit publik/otomatis |
| $x_i$ | Exposure | 1–5 | 1 = komponen internal, 3 = terekspos di pipeline, 5 = terekspos ke publik |
| $c_i$ | Confidentiality Impact | 1–5 | Potensi kebocoran secret, token, atau kredensial |
| $g_i$ | Integrity Impact | 1–5 | Potensi tampering pada artifact, kode sumber, atau konfigurasi deployment |
| $a_i$ | Availability Impact | 1–5 | Potensi gangguan pada eksekusi pipeline atau layanan |

Risiko per temuan: $R_i = L_i \times I_i$ (skala 1–25).

Skor risiko keseluruhan dinormalisasi:

$$\text{RiskScore} = \max\left(0,\; 100 - \frac{\sum_{i=1}^{n} R_i}{\max(1, n) \cdot 25} \cdot 100\right)$$

**Risk Level Thresholds**:

| Score Range | Risk Level |
|-------------|-----------|
| 0–25 | `critical` |
| 26–50 | `high` |
| 51–75 | `medium` |
| 76–100 | `low` |

Skor tinggi berarti risiko rendah (pipeline lebih aman). Pembagi $\max(1, n) \times 25$ memastikan skor tetap dalam rentang 0–100 untuk jumlah temuan berapa pun.

**Likelihood & Impact Scale**:

| Nilai | Exploitability ($e_i$) | Exposure ($x_i$) |
|-------|----------------------|-------------------|
| 1 | Teoritis, belum ada exploit | Komponen internal, tidak terekspos |
| 2 | Sulit, perlu keahlian khusus | Terekspos via log internal |
| 3 | Mungkin dengan alat bantu | Terekspos di pipeline |
| 4 | Tersedia proof-of-concept | Terekspos via API internal |
| 5 | Tersedia exploit publik/otomatis | Terekspos ke publik/Internet |

| Nilai | Confidentiality ($c_i$) | Integrity ($g_i$) / Availability ($a_i$) |
|-------|------------------------|----------------------------------------|
| 1 | Tidak ada data sensitif | Tidak ada dampak |
| 2 | Data log/metadata | Dampak minor, tidak mengganggu |
| 3 | Konfigurasi/environment variable | Dampak sedang, satu job terganggu |
| 4 | Kredensial/token terbatas | Beberapa job/stage terganggu |
| 5 | Secret/token utama, akses penuh | Seluruh pipeline atau layanan terganggu |

### 11.7 Compliance Scoring

Compliance score mengukur kepatuhan terhadap standar keamanan. Dihitung sebagai rata-rata dari cakupan setiap standar yang berlaku:

$$\text{ComplianceScore} = \text{AVG}\left(
\frac{\text{compliant\_owasp\_cicd}}{\text{total\_owasp\_cicd}} \times 100,\;
\frac{\text{owasp\_top10\_covered}}{10} \times 100,\;
\frac{\text{compliant\_cis}}{\text{total\_cis}} \times 100
\right)$$

**Standar yang dievaluasi**:
- **OWASP CICD Controls**: Kepatuhan terhadap kontrol keamanan CICD OWASP
- **OWASP Top 10**: Cakupan terhadap 10 kategori OWASP
- **CIS Benchmarks**: Jika aplikatif untuk deployment target (Kubernetes, cloud)

### 11.8 Workflow Quality Scoring

Workflow quality score mengukur kualitas struktural pipeline berdasarkan praktik terbaik. Dihitung sebagai jumlah terbobot dari indikator boolean:

$$\text{QualityScore} = \sum_{i=1}^{6} (p_i \times b_i)$$

di mana $p_i$ = indikator boolean praktik terbaik ke-$i$ (0 atau 1) dan $b_i$ = bobot praktik tersebut.

| # | Best Practice | Bobot ($b_i$) |
|---|--------------|----------------|
| 1 | Action pinning (SHA commit hash) | 25 |
| 2 | Minimal permissions | 25 |
| 3 | Timeout configured (`timeout-minutes`) | 15 |
| 4 | Dependency caching | 15 |
| 5 | Error handling (`if: failure()`) | 10 |
| 6 | Concurrency control (`concurrency.group`) | 10 |

**Total maksimum**: 100 poin ketika semua 6 praktik diterapkan.

---

## 12. Adaptive DevSecOps Model

### 12.1 Model Overview

**Input → Processing → Output**:

```
Repository Characteristics
├── Language, Framework
├── Architecture Type
├── Deployment Target
└── Security Context
        │
        ▼
Adaptive Processing Pipeline
├── Analysis → Classification
├── Security Selection
└── Workflow Generation
        │
        ▼
Adaptive DevSecOps Workflow
├── Stage composition
├── Security controls
├── Deployment config
└── Monitoring setup
```

### 12.2 Input Processing

Full analysis pipeline: connection → scan → vulnerability_scan → tech_detect → arch_detect → deployment_detect → security_infer

### 12.3 Analysis Stage

Technology analysis includes language detection, framework detection, build tools, test frameworks, package managers, and dependency ecosystem.

### 12.4 Classification Stage

Architecture + deployment classification with confidence scoring.

### 12.5 Security Selection Stage

Adaptive control selection based on language, framework, architecture, and deployment target.

### 12.6 Workflow Generation Stage

Stage composition: Build → Security → Deploy, tailored per architecture type.

### 12.7 Adaptation for Monolithic Systems

Single build, unified security scope, centralized deployment.

### 12.8 Adaptation for Microservices Systems

Matrix build per service, network-centric security, per-service deployment.

### 12.9 Model Adaptation Summary

| Aspect | Monolith | Microservices |
|--------|----------|---------------|
| Build Strategy | Single build | Matrix per service |
| Security Scope | Application-wide | Per-service + network |
| Deployment | Single unit | Multiple services |
| Rollback | Full revert | Per-service |
| Monitoring | Aggregated | Distributed tracing |
| Secrets | Centralized | Per-service + vault |

---

## 13. Research Contribution Mapping

### 13.1 Contribution 1: Repository Analysis Automation

Automated extraction of repository characteristics including technology, architecture, and deployment target.

**Components**: repository_scan, technology_detection, architecture_detection, deployment_detection

### 13.2 Contribution 2: AI-Driven Security Requirement Inference

Context-aware inference of security controls from technology stack, architecture, and deployment.

**Components**: security_requirement_inference, vulnerability_scan

### 13.3 Contribution 3: Adaptive Pipeline Generation

LLM-based generation tailored to architecture with validation and auto-repair.

**Components**: workflow_generation, workflow_validation, workflow_repair

### 13.4 Contribution 4: Intelligent Pipeline Analysis

Multi-dimensional analysis producing risk scores, compliance mappings, and actionable recommendations.

**Components**: security_analysis, risk_assessment, compliance_mapper, recommendation_generation

### 13.5 Contribution 5: Automated Remediation (UPDATED)

End-to-end remediation pipeline dengan dedicated UI:

1. **Failure Detection**: RunDetail page menampilkan tombol "Fix Failed Workflow" untuk run dengan conclusion=failure
2. **Multi-stage AI Analysis**: RunRemediation page dengan progress indicator (4 stages: triggering → collecting logs → analyzing failure → generating remediation)
3. **Root Cause Analysis**: Evidence snippets, affected components, fix_type classification
4. **Remediation Generation**: LLM-generated fixed workflow YAML dengan suggestions
5. **Dual Deployment Path**:
   - Path A: Auto-PR via analyze-execution endpoint (5 manual node chain)
   - Path B: Standalone deployment via deploy-remediation endpoint (user-triggered "Deploy Fix" button)
6. **Tracking**: PipelineRun.RemediationStatus field untuk melacak status remediasi

**Components**: execution_log_collection, failure_analysis, root_cause_detection, remediation_generation, remediation_pr_creation, `deploy_remediation_workflow()`, RunRemediation page

### 13.6 Contribution 6: Adaptive DevSecOps Model

Complete AI workflow graph with conditional branching, architecture-specific adaptations, and consistent security posture across architectures.

---

## 14. Thesis Mapping

| Chapter | Relevant Sections |
|---------|------------------|
| Chapter 1: Introduction | System Overview (Sec 1), Functional Requirements (Sec 2) |
| Chapter 2: Literature Review | AI Agent Architecture (Sec 4), AI Workflow Graph (Sec 5), Adaptive Model (Sec 12) |
| Chapter 3: Methodology | System Architecture (Sec 3), Analysis Mechanism (Sec 8), Security Inference (Sec 9), Generation Mechanism (Sec 10) |
| Chapter 4: Implementation | Database Design (Sec 6), API Design (Sec 7), AI Agent Architecture (Sec 4) |
| Chapter 5: Evaluation | Execution Analysis (Sec 11), Adaptive Model (Sec 12), Contribution Mapping (Sec 13) |
| Chapter 6: Conclusion | Contribution Mapping (Sec 13), System Overview (Sec 1) |

---

## Lampiran: Terminologi dan Definisi

### A.1 Definisi Teknis

| Term | Definition |
|------|------------|
| **DevSecOps** | Pendekatan DevOps yang mengintegrasikan praktik keamanan sejak awal lifecycle pengembangan |
| **AI Agent** | Komponen AI yang dapat menjalankan tugas spesifik berdasarkan input dan state |
| **LangGraph** | Framework Python untuk membangun workflow berbasis graph dengan state management |
| **Pipeline** | Workflow CI/CD yang mengotomatisasi build, test, dan deployment |
| **Security Controls** | Mekanisme keamanan yang diterapkan dalam pipeline |
| **Compliance Standards** | Standar keamanan yang harus dipatuhi (OWASP, CIS, NIST) |
| **Risk Score** | Nilai 0-100 yang merepresentasikan tingkat risiko keamanan |
| **Compliance Score** | Nilai 0-100 yang merepresentasikan kepatuhan terhadap standar |
| **Deployment Detection** | Proses otomatis mengidentifikasi target deployment environment |
| **Refresh Token** | Token untuk memperpanjang sesi autentikasi tanpa login ulang |
| **Remediation Flow** | Proses analisis kegagalan pipeline + generasi perbaikan + deployment PR otomatis |
| **Standalone Remediation** | Deploy workflow hasil remediasi sebagai PR baru tanpa melalui full analysis pipeline |

### A.2 Akronim

| Akronim | Kepanjangan |
|---------|-------------|
| CI/CD | Continuous Integration/Continuous Deployment |
| SAST | Static Application Security Testing |
| DAST | Dynamic Application Security Testing |
| VCS | Version Control System |
| ORM | Object-Relational Mapping |
| SSE | Server-Sent Events |
| JWT | JSON Web Token |
| AES | Advanced Encryption Standard |
| GCM | Galois/Counter Mode |
| LLM | Large Language Model |
| YAML | YAML Ain't Markup Language |

### A.3 Referensi Teknis

1. GitHub Actions Documentation: https://docs.github.com/en/actions
2. LangGraph Documentation: https://langchain-ai.github.io/langgraph/
3. OWASP Top 10: https://owasp.org/Top10/
4. CIS Benchmarks: https://www.cisecurity.org/cis-benchmarks
5. NIST Security Framework: https://www.nist.gov/cyberframework

---

## Ringkasan Perubahan v3 → v4

| Area | Perubahan |
|------|-----------|
| Remediation Flow | **Major upgrade**: dedicated `RunRemediation` frontend page dengan multi-stage progress UI; new `POST /api/pipeline/deploy-remediation` standalone endpoint; dual deployment path (analyze-execution auto-PR, deploy-remediation manual) |
| Frontend Pages | 13 → **14** (+RunRemediation page dengan route `/projects/:.../runs/:runId/remediation`) |
| Frontend Components | 22 → **32** (+FindingCard, 8 UI shadcn/ui components formalized) |
| DB: pipeline_runs | +`remediation_status` field (none/remediated/failed) |
| DB: pipeline_analyses | `findings_summary` type corrected (was `varchar`, actual is `jsonb`) |
| AI: API Endpoints | 15 → **16** (+`POST /deploy-remediation` untuk standalone remediation deployment) |
| AI: pipeline_service | +`deploy_remediation_workflow()` method (bypasses _invoke_graph_phase, langsung GitHub API calls) |
| AI: run_repo_generate | Sekarang auto-invoke `workflow_repair` node dalam flow jika validation errors detected (sebelumnya tidak diinvoke dalam flow) |
| System Overview | +`Automated Remediation` di cakupan sistem (Section 1.4); workflow pengguna diperbarui dengan remediation path |
| Sequence Diagram | +"Failure Remediation" sequence diagram baru (Section 3.6) |
| Contribution 13.5 | Automated Remediation diperluas: dedicated UI, dual deployment path, remediation status tracking |
| Terminologi | +"Remediation Flow", "Standalone Remediation" di definisi |

---

*Document Version: 4.0*
*Previous Version: 3.0*
*Generated for: Bachelor's Thesis - "Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices"*
