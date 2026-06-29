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
| Technology Detection | Deteksi bahasa pemrograman, framework, build tools, test frameworks |
| Architecture Classification | Klasifikasi arsitektur (monolithic/microservices) |
| Security Requirement Inference | Inferensi kebutuhan keamanan berdasarkan tech stack |
| Pipeline Generation | Generasi workflow YAML menggunakan LLM |
| Pipeline Validation | Validasi syntax, SHA pinning, permissions |
| Pipeline Deployment | Deployment sebagai Pull Request ke GitHub |
| Pipeline Monitoring | Monitoring eksekusi workflow real-time |
| Run Analysis | Analisis hasil eksekusi (risk score, compliance score, security coverage) |
| Pipeline Comparison | Perbandingan dua versi pipeline |
| Workflow Remediation | Generasi perbaikan otomatis untuk workflow yang gagal |

## 1.3 Workflow Pengguna

```
User Login → Dashboard → Project Selection
                          → Repository Selection
                              → Pipeline Generation (dengan parameter)
                              → Pipeline Deployment (sebagai PR)
                              → Pipeline Execution Monitoring
                              → Run Analysis (risk, compliance, recommendations)
                              → Pipeline Comparison
```

## 1.4 Komponen Arsitektur

| Komponen | Teknologi | Fungsi |
|----------|-----------|--------|
| Frontend | React + TypeScript + Vite | Antarmuka pengguna |
| Backend | Go + Gin + GORM | API server, database management |
| AI Service | Python + FastAPI + LangGraph | AI pipeline orchestration |
| Database (Backend) | PostgreSQL | Data repository, pipeline, runs |
| Database (AI) | PostgreSQL | Analysis cache, state management |
| External | GitHub API | Repository access, webhook events |

## 1.5 Komponen AI

Sistem AI Service menggunakan LangGraph untuk orchestrate 22 node AI Agent:

1. **Repository Connection** - Koneksi ke GitHub
2. **Repository Scan** - Pemindaian struktur
3. **Vulnerability Scan** - Analisis dependensi
4. **Technology Detection** - Deteksi teknologi
5. **Architecture Detection** - Klasifikasi arsitektur
6. **Security Requirement Inference** - Inferensi keamanan
7. **Workflow Generation** - Generasi YAML
8. **Workflow Validation** - Validasi workflow
9. **Workflow Repair** - Perbaikan otomatis
10. **GitHub Branch Creation** - Pembuatan branch
11. **Pull Request Creation** - Pembuatan PR
12. **Workflow Execution** - Trigger eksekusi
13. **Execution Monitor** - Monitoring status
14. **Execution Log Collection** - Kompilasi log
15. **Workflow Failure Analysis** - Analisis kegagalan
16. **Root Cause Detection** - Deteksi akar masalah
17. **Workflow Remediation Generation** - Generasi perbaikan
18. **Remediation PR Creation** - PR perbaikan
19. **Security Analyzer** - Analisis keamanan
20. **Risk Assessor** - Kalkulasi risk score
21. **Compliance Mapper** - Mapping compliance
22. **Recommendation Generator** - Rekomendasi
23. **Response Formatter** - Format response
24. **Error Handler** - Error handling

## 1.6 Entitas Database

**Backend (Go/GORM):**
- User, Project, Repository, RepositoryInsight, Pipeline, PipelineRun, PipelineAnalysis

**AI Service (Python/SQLAlchemy):**
- Cached analysis, LLM conversation history, Workflow state

## 1.7 Endpoint API

**Backend API** (`/api/v1/*`): 25 endpoint untuk CRUD, webhook, dashboard
**AI Service API** (`/api/pipeline/*`): 14 endpoint untuk pipeline lifecycle, analysis, webhook

## 1.8 Integrasi Eksternal

- GitHub API v3 (repos, actions, webhooks)
- GitHub Webhooks (push, pull_request, workflow_run)
- LLM Providers (OpenAI GPT-4, Anthropic Claude)

## 1.9 Mekanisme Keamanan

- JWT Authentication untuk API backend
- AES-256-GCM encryption untuk GitHub tokens
- Input validation dan sanitization
- Webhook signature verification

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

1. **Otomatisasi Analisis Repository** - Mengurangi kebutuhan manual inspection untuk menentukan teknologi dan arsitektur yang digunakan.

2. **Inferensi Keamanan Adaptif** - Menyesuaikan security controls berdasarkan karakteristik spesifik dari setiap repository.

3. **Generasi Pipeline Otomatis** - Menghasilkan workflow YAML yang sesuai dengan best practices dan compliance requirements.

4. **Analisis Hasil Eksekusi** - Memberikan insight tentang risk score, compliance score, dan rekomendasi perbaikan.

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
- **Technology Analysis**: Deteksi otomatis bahasa, framework, dan tools
- **Architecture Classification**: Klasifikasi sebagai monolith atau microservices
- **Security Inference**: Inferensi kebutuhan keamanan berdasarkan tech stack
- **Pipeline Generation**: Generasi workflow YAML adaptif
- **Pipeline Validation**: Validasi syntax dan security requirements
- **Pipeline Deployment**: Deployment sebagai Pull Request
- **Execution Monitoring**: Real-time monitoring pipeline execution
- **Run Analysis**: Analisis hasil dengan scoring system
- **Pipeline Comparison**: Perbandingan antar versi pipeline

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
- Webhook registration di GitHub
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

**Modul Terkait**:
- `repository_scan` node (AI Service)
- `technology_detection` node (AI Service)

---

### 2.3 Technology Detection

**Tujuan**: Mendeteksi bahasa pemrograman, framework, build tools, dan test frameworks yang digunakan dalam repository.

**Input**:
- Repository files (via GitHub API)
- Language statistics (dari GitHub languages API)

**Output**:
- `primary_language`: Bahasa utama repository
- `secondary_languages`: Bahasa tambahan (array)
- `frameworks`: Framework yang digunakan (array)
- `build_tools`: Build tools (npm, maven, gradle, dll.)
- `test_frameworks`: Test frameworks (jest, pytest, junit, dll.)
- `confidence_scores`: Confidence untuk setiap detection

**Modul Terkait**:
- `technology_detection` node (AI Service)

---

### 2.4 Architecture Classification

**Tujuan**: Mengklasifikasikan arsitektur repository sebagai monolithic atau microservices.

**Input**:
- Repository structure
- Technology metadata
- Dockerfile presence
- docker-compose.yml presence
- Service directory patterns

**Output**:
- `architecture_type`: "monolith" | "microservices" | "modular_monolith"
- `service_count`: Estimated number of services
- `deployment_model`: Deployment pattern yang sesuai
- `confidence`: Classification confidence score

**Decision Logic**:
- Microservices: Multiple docker-compose files, service directories, API gateway patterns
- Monolith: Single main application, unified deployment
- Modular Monolith: Clear module boundaries but single deployment

**Modul Terkait**:
- `architecture_detection` node (AI Service)

---

### 2.5 Security Requirement Inference

**Tujuan**: Melakukan inferensi kebutuhan keamanan berdasarkan teknologi yang digunakan.

**Input**:
- Technology metadata (language, framework, build tools)
- Architecture type
- Deployment target

**Output**:
- `security_controls`: Array of required security controls
- `compliance_standards`: Applicable compliance standards (OWASP, CIS, dll.)
- `scan_requirements`: Required security scans (SAST, DAST, dependency check, dll.)
- `secrets_management`: Secrets management approach

**Control Selection Logic**:
| Technology | Inferred Controls |
|------------|-------------------|
| Node.js | npm audit, dependency check, secret scanning |
| Python | safety check, bandit, dependency review |
| Java | OWASP dependency check, spotbugs |
| Go | govulncheck, staticcheck |
| Docker | trivy scan, hadolint |
| Kubernetes | kube-bench, trivy k8s |

**Modul Terkait**:
- `security_requirement_inference` node (AI Service)

---

### 2.6 Pipeline Generation

**Tujuan**: Menghasilkan GitHub Actions workflow YAML berdasarkan repository characteristics dan security requirements.

**Input**:
- Repository ID
- Repository metadata
- Security controls yang diperlukan
- User preferences (deploy target, additional config)

**Output**:
- `generated_workflow`: YAML workflow content
- `generated_stages`: Array of pipeline stages
- `explanation`: AI-generated explanation dari workflow
- `validation_passed`: Boolean validation status
- `validation_errors`: Array of validation errors (jika ada)
- `suggestions`: Improvement suggestions

**Generation Strategy**:
1. Analyze technology requirements
2. Map security controls ke workflow steps
3. Include appropriate triggers (push, pull_request, schedule)
4. Add appropriate caching strategies
5. Include notification and reporting steps

**Modul Terkait**:
- `workflow_generation` node (AI Service)
- `response_formatter` node (AI Service)

---

### 2.7 Pipeline Validation

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
- Jika validasi gagal, sistem mencoba auto-repair workflow
- Retry validasi setelah repair
- Maximum 2 retry attempts

**Modul Terkait**:
- `workflow_validation` node (AI Service)
- `workflow_repair` node (AI Service)

---

### 2.8 Pipeline Deployment

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
1. Create new branch dengan nama unik
2. Create workflow file di `.github/workflows/`
3. Create Pull Request ke default branch
4. Return PR details

**Modul Terkait**:
- `github_branch_creation` node (AI Service)
- `pull_request_creation` node (AI Service)

---

### 2.9 Pipeline Monitoring

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

### 2.10 Run Analysis

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
3. **Compliance Mapping**: Mapping findings ke compliance standards (CIS, OWASP)
4. **Recommendation Generation**: Actionable recommendations berdasarkan findings

**Modul Terkait**:
- `security_analyzer` node (AI Service)
- `risk_assessor` node (AI Service)
- `compliance_mapper` node (AI Service)
- `recommendation_gen` node (AI Service)

---

### 2.11 Pipeline Comparison

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
- AI Service `/api/pipeline/compliance` endpoint

---

### 2.12 Workflow Remediation

**Tujuan**: Menghasilkan perbaikan otomatis untuk pipeline yang gagal.

**Input**:
- Run ID dengan failure information
- Execution logs
- Root cause analysis

**Output**:
- `failure_analysis`: Explanation dari failure
- `root_cause`: Root cause yang teridentifikasi
- `remediation_yaml`: Fixed workflow YAML
- `remediation_pr_url`: Pull Request dengan fix (jika applicable)

**Remediation Process**:
1. Collect execution logs
2. Analyze failure pattern
3. Detect root cause
4. Generate remediation YAML
5. Create Pull Request dengan fix

**Modul Terkait**:
- `execution_log_collection` node (AI Service)
- `workflow_failure_analysis` node (AI Service)
- `root_cause_detection` node (AI Service)
- `workflow_remediation_generation` node (AI Service)
- `remediation_pr_creation` node (AI Service)

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

**Component Hierarchy**:
```
App
├── AuthProvider
│   ├── Landing
│   ├── Login
│   └── Register
└── ProtectedRoutes
    ├── Dashboard
    ├── ProjectList
    │   └── ProjectDetail
    │       └── RepoDetail
    │           ├── PipelineList
    │           │   └── PipelineVersionDetail
    │           │       ├── WorkflowView
    │           │       ├── RunsList
    │           │       │   └── RunDetail
    │           │       │       └── RunAnalysis
    │           │       └── PipelineDetails
    │           ├── PipelineGenerator
    │           └── PipelineCompare
    └── GlobalPipelines
```

**Key Features**:
- Real-time polling untuk run status (5 detik interval)
- SSE stream support untuk live updates
- Lazy loading untuk route components
- Error boundary untuk graceful error handling

### 3.2 Backend Architecture

**Technology Stack**:
- Go 1.21+
- Gin web framework
- GORM sebagai ORM
- PostgreSQL sebagai database
- JWT untuk authentication

**Module Structure**:
```
backend/
├── cmd/server/main.go
├── internal/
│   ├── config/
│   ├── middleware/
│   │   ├── auth.go
│   │   └── cors.go
│   ├── handlers/
│   │   ├── auth.go
│   │   ├── project.go
│   │   ├── repository.go
│   │   ├── pipeline.go
│   │   └── webhook.go
│   ├── models/
│   ├── repositories/
│   ├── services/
│   └── utils/
└── pkg/
    ├── github/
    └── encryption/
```

**Key Components**:

1. **HTTP Handlers**: Menerima request dari frontend, validasi input, routing ke service layer
2. **Service Layer**: Business logic, orchestrate multiple repositories
3. **Repository Layer**: Database operations via GORM
4. **External Services**: GitHub API integration, AI Service communication

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
│   ├── api/
│   │   └── routes/
│   │       ├── pipeline.py
│   │       ├── analysis.py
│   │       └── webhook.py
│   ├── core/
│   │   ├── config.py
│   │   └── llm_service.py
│   ├── graph/
│   │   ├── nodes/
│   │   │   ├── repository_nodes.py
│   │   │   ├── generation_nodes.py
│   │   │   ├── analysis_nodes.py
│   │   │   └── utility_nodes.py
│   │   ├── state.py
│   │   └── pipeline.py
│   ├── services/
│   │   ├── github_service.py
│   │   ├── security_service.py
│   │   └── compliance_service.py
│   └── models/
├── tests/
└── requirements.txt
```

**LangGraph Pipeline Structure**:
```python
# Main pipeline graph
workflow = StateGraph(PipelineEngineerState)
workflow.add_node("repository_connection", repository_connection_node)
workflow.add_node("repository_scan", repository_scan_node)
workflow.add_node("vulnerability_scan", vulnerability_scan_node)
workflow.add_node("technology_detection", technology_detection_node)
workflow.add_node("architecture_detection", architecture_detection_node)
workflow.add_node("security_requirement_inference", security_inference_node)
workflow.add_node("workflow_generation", workflow_generation_node)
workflow.add_node("workflow_validation", workflow_validation_node)
# ... conditional edges
```

### 3.4 Database Architecture

**Backend Database Schema** (PostgreSQL via GORM):

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────<│   Project   │────<│ Repository  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────┐          │
                    │RepositoryInsight│<───────┤
                    └──────────────┘          │
                                               │
                    ┌──────────────┐          │
                    │   Pipeline   │──────────┤
                    └──────┬───────┘          │
                           │                  │
                    ┌──────┴───────┐          │
                    │ PipelineRun  │──────────┤
                    └──────┬───────┘          │
                           │                  │
                    ┌──────┴───────┐          │
                    │PipelineAnalysis│────────┘
                    └──────────────┘
```

**AI Service Database Schema** (PostgreSQL via SQLAlchemy):

```
┌─────────────────────┐
│   CachedAnalysis     │
├─────────────────────┤
│ id (PK)             │
│ run_id              │
│ pipeline_id         │
│ analysis_data (JSON)│
│ created_at          │
│ updated_at          │
└─────────────────────┘

┌─────────────────────┐
│   LLMConversation    │
├─────────────────────┤
│ id (PK)             │
│ conversation_id     │
│ messages (JSON)     │
│ model_used          │
│ created_at          │
└─────────────────────┘

┌─────────────────────┐
│   WorkflowState     │
├─────────────────────┤
│ id (PK)             │
│ state_data (JSON)   │
│ status              │
│ created_at          │
│ updated_at          │
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
  │                 │                  │                │
  │                 │ UPDATE run       │                │
  │                 │────────────────>│                  │
  │                 │                  │                │
  │                 │ POST /analyze/*  │                │
  │                 │────────────────>│                  │
  │                 │                  │                  │
  │                 │                  │ fetch logs      │
  │                 │                  │────────────────>│
  │                 │                  │<────────────────│
  │                 │                  │                  │
  │                 │                  │ [LangGraph]     │
  │                 │                  │ analyze → score │
  │                 │                  │                  │
  │                 │                  │ INSERT analysis │
  │                 │                  │────────────────>│
  │                 │                  │<────────────────│
  │                 │                  │                  │
  │ 200 OK          │                  │                  │
  │<────────────────│                  │                  │
```

---

## 4. AI Agent Architecture

### 4.1 Agent Overview

AI Agent dalam sistem ini diimplementasikan sebagai node-node dalam LangGraph state machine. Setiap node merupakan Python function yang memodifikasi state bersama dan berkomunikasi melalui typed state dictionary. Berbeda dengan pendekatan prompt-based yang umum, setiap node memiliki logika spesifik yang dapat memanggil LLM atau menjalankan logic Python langsung.

### 4.2 Node Definitions

#### 4.2.1 Repository Connection Node

**Nama**: `repository_connection`
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

#### 4.2.2 Repository Scan Node

**Nama**: `repository_scan`
**Responsibility**: Memindai struktur repository untuk mengidentifikasi file-file kunci.

**Input**:
- `repository_metadata`: Dari repository_connection
- `github_token`: GitHub access token

**Output**:
- `file_structure`: Tree of important files
- `key_files`: Array of file paths (package.json, requirements.txt, dll.)
- `has_dockerfile`: Boolean
- `has_docker_compose`: Boolean
- `has_existing_workflows`: Boolean

**Logic**:
1. List repository root contents
2. Recursively scan for key configuration files
3. Check for Docker-related files
4. Check for existing GitHub Actions workflows
5. Return structured file inventory

**Key Files Detection**:
- Node.js: `package.json`, `package-lock.json`, `tsconfig.json`
- Python: `requirements.txt`, `setup.py`, `pyproject.toml`
- Java: `pom.xml`, `build.gradle`
- Go: `go.mod`, `go.sum`

**Downstream Node**: `vulnerability_scan`

---

#### 4.2.3 Vulnerability Scan Node

**Nama**: `vulnerability_scan`
**Responsibility**: Melakukan scan terhadap dependency vulnerabilities.

**Input**:
- `key_files`: Dependency manifest files
- `github_token`: GitHub access token

**Output**:
- `dependency_vulnerabilities`: Array of known vulnerabilities
- `outdated_dependencies`: Array of outdated packages
- `license_issues`: Array of license compliance issues

**Logic**:
1. Fetch dependency files content
2. Parse dependency manifests
3. Check against vulnerability databases (OSV, GitHub Advisory Database)
4. Identify outdated dependencies
5. Check license compatibility

**Downstream Node**: `technology_detection`

---

#### 4.2.4 Technology Detection Node

**Nama**: `technology_detection`
**Responsibility**: Mendeteksi bahasa pemrograman, framework, build tools, dan test frameworks.

**Input**:
- `repository_metadata`: Language statistics
- `key_files`: Parsed dependency files

**Output**:
- `primary_language`: Main programming language
- `secondary_languages`: Array of secondary languages
- `frameworks`: Detected frameworks
- `build_tools`: Build tools (npm, maven, gradle, make, dll.)
- `test_frameworks`: Test frameworks
- `deployment_target`: Deployment environment (k8s, vm, serverless, dll.)
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

#### 4.2.5 Architecture Detection Node

**Nama**: `architecture_detection`
**Responsibility**: Mengklasifikasikan arsitektur repository.

**Input**:
- `file_structure`: Repository structure
- `technology_metadata`: From technology_detection
- `has_dockerfile`: Boolean
- `has_docker_compose`: Boolean

**Output**:
- `architecture_type`: "monolith" | "microservices" | "modular_monolith"
- `service_count`: Estimated number of services
- `deployment_model`: Deployment pattern recommendation
- `confidence`: Classification confidence

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
    
    if score > 30: return "microservices"
    elif score > -20: return "modular_monolith"
    else: return "monolith"
```

**Downstream Node**: `security_requirement_inference`

---

#### 4.2.6 Security Requirement Inference Node

**Nama**: `security_requirement_inference`
**Responsibility**: Melakukan inferensi kebutuhan keamanan berdasarkan teknologi.

**Input**:
- `technology_metadata`: Language, frameworks, tools
- `architecture_type`: Monolith/Microservices
- `deployment_target`: Target deployment environment

**Output**:
- `security_controls`: Array of required security controls
- `compliance_standards`: Applicable compliance standards
- `scan_requirements`: Security scans to include
- `secrets_management`: Recommended secrets management

**Inference Logic**:
```python
def infer_security_requirements(tech, arch, target):
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
    
    if "java" in tech.languages:
        controls.extend(["owasp_dep_check", "spotbugs", "secret_scanning"])
        scans.extend(["SAST_SpotBugs", "OWASP_Dependency_Check"])
        compliance.append("CIS_Java")
    
    # Architecture-specific controls
    if arch == "microservices":
        controls.append("service_mesh_security")
        controls.append("network_policy_enforcement")
        scans.append("DAST_k8s_network")
    
    # Deployment-specific controls
    if target == "kubernetes":
        controls.extend(["trivy_scan", "kube_bench", "rbac_audit"])
    
    return SecurityRequirements(...)
```

**Downstream Node**: `workflow_generation`

---

#### 4.2.7 Workflow Generation Node

**Nama**: `workflow_generation`
**Responsibility**: Menghasilkan GitHub Actions workflow YAML.

**Input**:
- `repository_metadata`: Repository info
- `technology_metadata`: Tech stack
- `architecture_type`: Classification
- `security_requirements`: Inferred controls
- `user_preferences`: User-provided parameters

**Output**:
- `generated_workflow`: YAML content
- `generated_stages`: Array of pipeline stages
- `llm_explanation`: AI explanation of workflow

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
- Security Controls: {controls}

Requirements:
- Use SHA-pinned actions
- Minimal permissions
- Include: {required_scans}
- Trigger on: push, pull_request

Output format: YAML workflow
```

**Model Configuration**:
- Model: GPT-4 / Claude Sonnet
- Temperature: 0.3
- Max tokens: 4096

**Downstream Node**: `workflow_validation`

---

#### 4.2.8 Workflow Validation Node

**Nama**: `workflow_validation`
**Responsibility**: Memvalidasi generated workflow.

**Input**:
- `generated_workflow`: YAML content
- `security_requirements`: Required controls

**Output**:
- `validation_passed`: Boolean
- `validation_errors`: Array of errors
- `validation_warnings`: Array of warnings

**Validation Checks**:

1. **Syntax Validation**
   - Valid YAML syntax
   - Required fields present (name, on trigger)
   - Job structure valid

2. **Security Validation**
   - Actions use SHA commit hash
   - No hardcoded secrets
   - Minimal permissions (read-only by default)
   - Uses official actions

3. **Best Practices**
   - Appropriate trigger events
   - Caching configured
   - Timeout set
   - Error handling present

4. **Compliance Validation**
   - Required security scans included
   - Secret scanning enabled
   - Dependency scanning enabled

**Downstream Node**:
- `passed` → `workflow_repair` (if auto-repair enabled)
- `passed` → `response_formatter` (if validation OK)
- `failed` → `error_handler`

---

#### 4.2.9 Workflow Repair Node

**Nama**: `workflow_repair`
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

**Downstream Node**: `workflow_validation` (re-validation)

---

#### 4.2.10 GitHub Branch Creation Node

**Nama**: `github_branch_creation`
**Responsibility**: Membuat branch baru untuk workflow deployment.

**Input**:
- `repository_metadata`: Repository info
- `github_token`: Access token

**Output**:
- `branch_name`: Generated branch name
- `commit_sha`: Initial commit SHA

**Logic**:
1. Generate unique branch name: `devsecops-pipeline-{timestamp}`
2. Create branch dari default branch
3. Return branch details

**Downstream Node**: `pull_request_creation`

---

#### 4.2.11 Pull Request Creation Node

**Nama**: `pull_request_creation`
**Responsibility**: Membuat Pull Request dengan workflow file.

**Input**:
- `repository_metadata`: Repository info
- `branch_name`: Target branch
- `generated_workflow`: YAML content

**Output**:
- `pr_number`: Pull Request number
- `pr_url`: Pull Request URL
- `pr_status`: "created" | "failed"

**Logic**:
1. Create workflow file di `.github/workflows/devsecops-pipeline.yml`
2. Create PR dengan description
3. Return PR details

**Downstream Node**: `workflow_execution` (optional)

---

#### 4.2.12 Workflow Execution Node

**Nama**: `workflow_execution`
**Responsibility**: Trigger workflow dispatch di GitHub.

**Input**:
- `repository_metadata`: Repository info
- `branch_name`: Branch with workflow
- `workflow_id`: Workflow file name

**Output**:
- `run_id`: GitHub run ID
- `run_url`: Run URL

**Logic**:
1. Call GitHub API workflow_dispatch
2. Return run details

**Downstream Node**: `execution_monitor`

---

#### 4.2.13 Execution Monitor Node

**Nama**: `execution_monitor`
**Responsibility**: Monitoring pipeline execution sampai completion.

**Input**:
- `run_id`: GitHub run ID
- `repository_metadata`: Repository info

**Output**:
- `execution_status`: "queued" | "in_progress" | "completed" | "failed"
- `execution_conclusion`: "success" | "failure" | "cancelled" | "skipped"
- `duration_seconds`: Total execution time

**Monitoring Logic**:
```python
def monitor_execution(run_id, repo):
    timeout = 1800  # 30 minutes
    interval = 5    # seconds
    
    while elapsed < timeout:
        status = github.get_workflow_status(run_id, repo)
        
        if status == "completed":
            return format_completion(status)
        elif status == "failed":
            return format_failure(status)
        
        sleep(interval)
    
    return timeout_result()
```

**Downstream Node**:
- `completed` → `security_analyzer`
- `failed` → `workflow_failure_analysis`
- `timeout` → `error_handler`

---

#### 4.2.14 Execution Log Collection Node

**Nama**: `execution_log_collection`
**Responsibility**: Mengumpulkan logs dari workflow execution.

**Input**:
- `run_id`: GitHub run ID
- `repository_metadata`: Repository info

**Output**:
- `execution_logs`: Combined log content
- `job_logs`: Per-job logs
- `step_outputs`: Per-step outputs

**Logic**:
1. Fetch run details
2. Get job list
3. For each job, fetch step logs
4. Combine into unified log structure

**Downstream Node**: `workflow_failure_analysis` atau `security_analyzer`

---

#### 4.2.15 Workflow Failure Analysis Node

**Nama**: `workflow_failure_analysis`
**Responsibility**: Menganalisis kegagalan workflow.

**Input**:
- `execution_logs`: Log content
- `execution_status`: Failure status

**Output**:
- `failure_summary`: What failed
- `affected_jobs`: Jobs yang gagal
- `failure_patterns`: Patterns detected

**Analysis Logic**:
1. Parse log content
2. Identify failed steps
3. Extract error messages
4. Pattern match common failures
5. Return structured failure info

**Downstream Node**: `root_cause_detection`

---

#### 4.2.16 Root Cause Detection Node

**Nama**: `root_cause_detection`
**Responsibility**: Mendeteksi akar penyebab kegagalan.

**Input**:
- `failure_summary`: From failure_analysis
- `execution_logs`: Raw logs

**Output**:
- `root_cause`: Root cause category
- `root_cause_description`: Detailed explanation
- `confidence`: Detection confidence

**Detection Categories**:
- `configuration_error`: Wrong configuration
- `dependency_error`: Missing/broken dependencies
- `permission_error`: Insufficient permissions
- `network_error`: Network connectivity issues
- `resource_error`: Out of memory/disk
- `test_failure`: Tests failed
- `security_scan_failure`: Security scan found issues

**Downstream Node**: `workflow_remediation_generation`

---

#### 4.2.17 Workflow Remediation Generation Node

**Nama**: `workflow_remediation_generation`
**Responsibility**: Menghasilkan perbaikan untuk workflow yang gagal.

**Input**:
- `root_cause`: Detected root cause
- `original_workflow`: Original YAML
- `execution_context`: Failure context

**Output**:
- `remediation_yaml`: Fixed workflow YAML
- `remediation_explanation`: Explanation of changes

**Generation Logic**:
1. Analyze root cause
2. Build remediation prompt
3. Call LLM to generate fix
4. Validate fixed YAML
5. Return remediation

**Downstream Node**: `remediation_pr_creation`

---

#### 4.2.18 Remediation PR Creation Node

**Nama**: `remediation_pr_creation`
**Responsibility**: Membuat Pull Request dengan perbaikan.

**Input**:
- `remediation_yaml`: Fixed workflow
- `repository_metadata`: Repository info

**Output**:
- `remediation_pr_url`: PR URL
- `remediation_pr_status`: "created" | "failed"

**Downstream Node**: `response_formatter`

---

#### 4.2.19 Security Analyzer Node

**Nama**: `security_analyzer`
**Responsibility**: Melakukan analisis keamanan terhadap execution results.

**Input**:
- `execution_logs`: Workflow logs
- `execution_results`: Job results
- `security_requirements`: Original security requirements

**Output**:
- `security_findings`: Array of security findings
- `vulnerabilities_detected`: Vulnerabilities found
- `compliance_gaps`: Missing compliance controls

**Analysis Scope**:
1. Dependency vulnerabilities (from logs)
2. Secret exposure (from logs)
3. Insecure configurations (from workflow)
4. Missing security controls

**Downstream Node**: `risk_assessor`

---

#### 4.2.20 Risk Assessor Node

**Nama**: `risk_assessor`
**Responsibility**: Menghitung risk score berdasarkan findings.

**Input**:
- `security_findings`: From security_analyzer
- `execution_context`: Execution metadata

**Output**:
- `risk_score`: Overall risk score (0-100)
- `risk_factors`: Contributing risk factors
- `risk_category`: "critical" | "high" | "medium" | "low"

**Risk Calculation**:
```python
def calculate_risk_score(findings):
    base_score = 100
    
    for finding in findings:
        severity = finding.severity
        if severity == "critical": base_score -= 25
        elif severity == "high": base_score -= 15
        elif severity == "medium": base_score -= 10
        elif severity == "low": base_score -= 5
    
    # Adjust for exploitability
    if has_exploit_available(findings): base_score *= 0.7
    
    return max(0, base_score)
```

**Downstream Node**: `compliance_mapper`

---

#### 4.2.21 Compliance Mapper Node

**Nama**: `compliance_mapper`
**Responsibility**: Mapping findings ke compliance standards.

**Input**:
- `security_findings`: From security_analyzer
- `compliance_standards`: Target standards (CIS, OWASP, dll.)

**Output**:
- `compliance_score`: Score against standards
- `mapped_findings`: Findings mapped to controls
- `compliance_gaps`: Missing compliance controls

**Mapping Logic**:
```python
def map_to_compliance(findings, standards):
    mapped = []
    gaps = []
    
    for standard in standards:
        controls = get_controls(standard)
        for control in controls:
            matched = find_matching_finding(control, findings)
            if matched:
                mapped.append(MappedFinding(control, matched))
            else:
                gaps.append(ControlGap(control))
    
    score = (len(mapped) / (len(mapped) + len(gaps))) * 100
    return ComplianceResult(score, mapped, gaps)
```

**Downstream Node**: `recommendation_gen`

---

#### 4.2.22 Recommendation Generator Node

**Nama**: `recommendation_gen`
**Responsibility**: Menghasilkan actionable recommendations.

**Input**:
- `security_findings`: Security findings
- `risk_score`: Calculated risk
- `compliance_gaps`: Compliance gaps
- `execution_context`: Context information

**Output**:
- `recommendations`: Array of recommendations
- `priority_order`: Recommended priority order

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

#### 4.2.23 Response Formatter Node

**Nama**: `response_formatter`
**Responsibility**: Memformat response akhir untuk client.

**Input**: Semua output dari nodes sebelumnya

**Output**:
- `final_response`: Structured response
- `status`: "success" | "partial" | "failed"
- `summary`: Human-readable summary

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

#### 4.2.24 Error Handler Node

**Nama**: `error_handler`
**Responsibility**: Handle errors di setiap stage.

**Input**:
- `error`: Error message
- `stage`: Current stage
- `context`: Error context

**Output**:
- `error_response`: Formatted error
- `recovery_suggestion`: How to recover

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
│ creation    │                              │
└──────┬──────┘                              │
       │                                     │
       ▼                                     │
┌─────────────┐                              │
│ pull_request│                              │
│ _creation   │                              │
└──────┬──────┘                              │
       │                                     │
       ▼                                     │
┌─────────────┐                              │
│   workflow_ │                              │
│  execution  │                              │
└──────┬──────┘                              │
       │                                     │
       ▼                                     │
┌─────────────┐                              │
│  execution_ │                              │
│   monitor   │                              │
└──────┬──────┘                              │
       │                                     │
  ┌────┴────┐                                │
  │         │                                │
┌─┴───┐ ┌───┴───┐                            │
│Comp │ │Timeout│                            │
│leted│ │/Error │                            │
└─┬───┘ └───┬───┘                            │
  │         │                                │
  ▼         ▼                                │
┌─────────────┐  ┌──────────────────┐         │
│   security_ │  │   error_handler  │         │
│   analyzer  │  └────────┬─────────┘         │
└──────┬──────┘           │                   │
       │                  │                   │
       ▼                  │                   │
┌─────────────┐           │                   │
│ risk_assessor│          │                   │
└──────┬──────┘           │                   │
       │                  │                   │
       ▼                  │                   │
┌─────────────┐           │                   │
│compliance_  │           │                   │
│   mapper    │           │                   │
└──────┬──────┘           │                   │
       │                  │                   │
       ▼                  │                   │
┌─────────────┐           │                   │
│recommendation│          │                   │
│     _gen    │           │                   │
└──────┬──────┘           │                   │
       │                  │                   │
       ▼                  │                   │
┌─────────────┐           │                   │
│  response_  │◄──────────┴───────────────────┘
│  formatter  │
└─────────────┘
```

### 5.2 Graph Transitions

| From | To | Condition |
|------|-----|-----------|
| START | repository_connection | Initial request |
| repository_connection | repository_scan | Connection successful |
| repository_connection | error_handler | Connection failed |
| repository_scan | vulnerability_scan | Scan completed |
| vulnerability_scan | technology_detection | Vulnerabilities scanned |
| technology_detection | architecture_detection | Tech detected |
| architecture_detection | security_requirement_inference | Architecture classified |
| security_requirement_inference | workflow_generation | Security requirements inferred |
| workflow_generation | workflow_validation | Workflow generated |
| workflow_validation | workflow_repair | Validation failed (auto-repair) |
| workflow_validation | auto_deploy_check | Validation passed |
| workflow_repair | workflow_validation | Retry validation |
| auto_deploy_check | github_branch_creation | User chose deploy |
| auto_deploy_check | response_formatter | User skipped |
| github_branch_creation | pull_request_creation | Branch created |
| pull_request_creation | workflow_execution | PR created |
| workflow_execution | execution_monitor | Workflow triggered |
| execution_monitor | security_analyzer | Execution completed |
| execution_monitor | workflow_failure_analysis | Execution failed |
| execution_monitor | error_handler | Timeout |
| security_analyzer | risk_assessor | Analysis done |
| risk_assessor | compliance_mapper | Risk scored |
| compliance_mapper | recommendation_gen | Compliance mapped |
| recommendation_gen | response_formatter | Recommendations generated |
| response_formatter | END | Response ready |

### 5.3 Failure Analysis Sub-graph

```
POST /api/pipeline/analyze-execution/{run_id}

┌──────────────────────┐
│ execution_log_       │
│ collection           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│workflow_failure_     │
│analysis              │
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
│workflow_remediation_ │
│generation            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│remediation_pr_       │
│creation              │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  response_formatter  │
└──────────────────────┘
```

---

## 6. Database Design

### 6.1 User Entity

**Purpose**: Menyimpan data pengguna sistem.

**Schema**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'engineer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- role values: 'admin', 'engineer', 'viewer'
```

**Key Fields**:
- `id`: Primary key (UUID)
- `email`: Unique identifier untuk login
- `password_hash`: BCrypt hashed password
- `role`: Authorization level

**Relationships**:
- One-to-Many dengan Project (via user_id)

---

### 6.2 Project Entity

**Purpose**: Mengorganisir repositories dalam logical groupings.

**Schema**:
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    compliance_tier VARCHAR(50) NOT NULL DEFAULT 'permissive',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);

-- compliance_tier values: 'strict', 'moderate', 'permissive'
```

**Key Fields**:
- `id`: Primary key
- `user_id`: Foreign key ke User
- `compliance_tier`: Affects security controls selection

**Relationships**:
- Many-to-One dengan User
- One-to-Many dengan Repository

---

### 6.3 Repository Entity

**Purpose**: Menyimpan GitHub repository connection details.

**Schema**:
```sql
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    github_id BIGINT,
    full_name VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    default_branch VARCHAR(100) DEFAULT 'main',
    access_token_encrypted TEXT,
    webhook_id BIGINT,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Fields**:
- `full_name`: "{owner}/{repo}" format
- `access_token_encrypted`: AES-256-GCM encrypted GitHub token
- `webhook_id`: GitHub webhook ID untuk cleanup

**Relationships**:
- Many-to-One dengan Project
- One-to-One dengan RepositoryInsight
- One-to-Many dengan Pipeline

---

### 6.4 RepositoryInsight Entity

**Purpose**: Cache hasil analisis repository.

**Schema**:
```sql
CREATE TABLE repository_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID UNIQUE NOT NULL REFERENCES repositories(id),
    primary_language VARCHAR(100),
    secondary_languages JSONB DEFAULT '[]',
    frameworks JSONB DEFAULT '[]',
    build_tools JSONB DEFAULT '[]',
    test_frameworks JSONB DEFAULT '[]',
    architecture_type VARCHAR(50),
    has_dockerfile BOOLEAN DEFAULT FALSE,
    has_existing_ci_cd BOOLEAN DEFAULT FALSE,
    existing_workflows JSONB DEFAULT '[]',
    deployment_target VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Fields**:
- `primary_language`: Detected main language
- `secondary_languages`: Array of other languages
- `frameworks`: Detected frameworks
- `architecture_type`: "monolith" | "microservices" | "modular_monolith"

**Relationships**:
- One-to-One dengan Repository

---

### 6.5 Pipeline Entity

**Purpose**: Menyimpan generated pipeline configurations.

**Schema**:
```sql
CREATE TABLE pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id),
    version_number INTEGER NOT NULL,
    prompt TEXT,
    user_requirements JSONB,
    generated_yaml TEXT,
    stages JSONB DEFAULT '[]',
    ai_explanation TEXT,
    generation_params JSONB,
    validation_results JSONB,
    deployment_results JSONB,
    security_controls_applied JSONB DEFAULT '[]',
    compliance_metadata JSONB,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(repository_id, version_number)
);

-- status values: 'draft', 'generated', 'validated', 'deployed', 'failed'
```

**Key Fields**:
- `version_number`: Auto-increment per repository
- `generated_yaml`: GitHub Actions YAML content
- `security_controls_applied`: Array of applied security controls

**Relationships**:
- Many-to-One dengan Repository
- One-to-Many dengan PipelineRun

---

### 6.6 PipelineRun Entity

**Purpose**: Menyimpan eksekusi pipeline runs.

**Schema**:
```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID NOT NULL REFERENCES pipelines(id),
    run_number INTEGER NOT NULL,
    github_run_id BIGINT,
    status VARCHAR(50) DEFAULT 'pending',
    conclusion VARCHAR(50),
    html_url TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    jobs JSONB,
    logs_url TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- status values: 'pending', 'queued', 'running', 'completed', 'failed'
-- conclusion values: 'success', 'failure', 'cancelled', 'skipped'
```

**Key Fields**:
- `github_run_id`: GitHub Actions run ID
- `jobs`: JSONB array of job details with steps
- `duration_seconds`: Total execution time

**Relationships**:
- Many-to-One dengan Pipeline
- One-to-One dengan PipelineAnalysis

---

### 6.7 PipelineAnalysis Entity

**Purpose**: Menyimpan hasil analisis pipeline execution.

**Schema**:
```sql
CREATE TABLE pipeline_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID UNIQUE NOT NULL REFERENCES pipeline_runs(id),
    risk_score INTEGER,
    compliance_score INTEGER,
    workflow_quality_score INTEGER,
    security_coverage_score INTEGER,
    findings_summary JSONB DEFAULT '[]',
    severity_breakdown JSONB,
    recommendations JSONB DEFAULT '[]',
    ai_explanation TEXT,
    raw_scan_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Fields**:
- `risk_score`: 0-100 risk assessment
- `compliance_score`: 0-100 compliance assessment
- `severity_breakdown`: Breakdown by severity level
- `recommendations`: Actionable recommendations array

**Relationships**:
- One-to-One dengan PipelineRun

---

### 6.8 Entity Relationships Diagram

```
┌────────┐       ┌──────────┐       ┌────────────┐
│  User  │──1:N──│  Project │──1:N──│ Repository │
└────────┘       └──────────┘       └──────┬─────┘
                                           │
                            ┌──────────────┴──────────────┐
                            │                             │
                     ┌──────┴───────┐              ┌─────┴─────┐
                     │Repository   │              │  Pipeline │
                     │Insight (1:1)│              └──────┬────┘
                     └─────────────┘                     │
                                                        │
                                            ┌───────────┴───────────┐
                                            │                       │
                                     ┌──────┴──────┐        ┌───────┴───────┐
                                     │ PipelineRun │──1:1──│PipelineAnalysis│
                                     └─────────────┘       └───────────────┘
```

---

## 7. API Design

### 7.1 Backend API (Go/Gin) — `/api/v1`

#### 7.1.1 Public Endpoints

**GET /health**
- Purpose: Health check
- Response: `{ "status": "healthy", "timestamp": "..." }`

**POST /auth/register**
- Purpose: Register new user
- Request:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword",
    "name": "John Doe"
  }
  ```
- Response: `{ "id": "uuid", "email": "...", "token": "jwt" }`

**POST /auth/login**
- Purpose: User login
- Request:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword"
  }
  ```
- Response: `{ "token": "jwt", "user": {...} }`

**POST /auth/refresh**
- Purpose: Refresh JWT token
- Request: `{ "refresh_token": "..." }`
- Response: `{ "token": "new_jwt" }`

**POST /webhooks/github**
- Purpose: GitHub webhook receiver
- Headers: `X-GitHub-Event`, `X-Hub-Signature-256`
- Request: GitHub webhook payload
- Response: `{ "received": true }`

#### 7.1.2 Protected Endpoints (JWT Required)

**GET /me**
- Purpose: Get current user profile
- Response: `{ "id": "uuid", "email": "...", "name": "...", "role": "..." }`

**GET /dashboard/stats**
- Purpose: Aggregated dashboard statistics
- Response:
  ```json
  {
    "total_projects": 5,
    "total_repos": 12,
    "total_pipelines": 45,
    "total_executions": 234,
    "success_rate": 0.92,
    "avg_risk_score": 72,
    "compliance_score": 85,
    "security_coverage": 0.88,
    "recent_pipelines": [...]
  }
  ```

**GET /projects**
- Purpose: List user projects
- Response: `{ "projects": [...], "total": 5 }`

**POST /projects**
- Purpose: Create new project
- Request:
  ```json
  {
    "name": "My Project",
    "description": "Project description"
  }
  ```
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
- Request:
  ```json
  {
    "project_id": "uuid",
    "repo_url": "https://github.com/owner/repo",
    "access_token": "ghp_..."
  }
  ```
- Response:
  ```json
  {
    "id": "uuid",
    "name": "repo",
    "owner": "owner",
    "webhook_id": 12345
  }
  ```

**GET /projects/:projectId/repositories**
- Purpose: List repositories in project
- Response: `{ "repositories": [...], "total": 3 }`

**GET /repositories/:repoId**
- Purpose: Get repository details
- Response: `{ "id": "uuid", "full_name": "...", ... }`

**DELETE /repositories/:repoId**
- Purpose: Delete repository and webhook
- Response: `{ "deleted": true }`

**GET /repositories/:repoId/insights**
- Purpose: Get repository insights (cached analysis)
- Response:
  ```json
  {
    "primary_language": "typescript",
    "frameworks": ["react", "next.js"],
    "architecture_type": "monolith",
    ...
  }
  ```

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
- Response:
  ```json
  {
    "pipelineA": {...},
    "pipelineB": {...},
    "comparison": {
      "yaml_diff": "...",
      "score_delta": {...},
      "controls_delta": [...]
    }
  }
  ```

**GET /repositories/:repoId/pipelines**
- Purpose: List pipeline versions for repository
- Response: `{ "pipelines": [...], "total": 5 }`

**GET /repositories/:repoId/pipelines/:version**
- Purpose: Get specific pipeline version
- Response: Pipeline object

**POST /repositories/:repoId/pipelines/:version/sync-runs**
- Purpose: Sync runs from GitHub
- Response: `{ "synced": 3, "runs": [...] }`

**GET /pipelines/:pipelineId/runs**
- Purpose: List runs for pipeline
- Response: `{ "runs": [...], "total": 15 }`

**GET /runs/:runId**
- Purpose: Get run detail (live from GitHub)
- Response:
  ```json
  {
    "id": "uuid",
    "status": "completed",
    "conclusion": "success",
    "jobs": [...],
    "duration_seconds": 345
  }
  ```

**GET /runs/:runId/analysis**
- Purpose: Get analysis for run
- Response:
  ```json
  {
    "risk_score": 75,
    "compliance_score": 85,
    "findings_summary": [...],
    "recommendations": [...]
  }
  ```

### 7.2 AI Service API (Python/FastAPI) — `/api/pipeline`

**POST /repo/analyze**
- Purpose: Analyze repository (scan + tech + arch detection)
- Request:
  ```json
  {
    "repository_id": "uuid",
    "github_token": "ghp_...",
    "repo_url": "https://github.com/owner/repo"
  }
  ```
- Response:
  ```json
  {
    "primary_language": "typescript",
    "frameworks": ["react"],
    "architecture_type": "monolith",
    "security_requirements": {...}
  }
  ```

**POST /repo/pipeline**
- Purpose: Full end-to-end pipeline generation
- Request:
  ```json
  {
    "repository_id": "uuid",
    "github_token": "ghp_...",
    "project_id": "uuid",
    "query": "generate CI/CD pipeline",
    "extra": {
      "language": "typescript",
      "framework": "react",
      "deploy_target": "kubernetes"
    }
  }
  ```
- Response:
  ```json
  {
    "generated_workflow": "...yaml...",
    "generated_stages": [...],
    "explanation": "...",
    "validation_passed": true,
    "security_controls_applied": [...]
  }
  ```

**POST /generate**
- Purpose: Generate workflow YAML only
- Request: `{ "context": {...}, "requirements": {...} }`
- Response: `{ "workflow": "...yaml...", "stages": [...] }`

**POST /deploy**
- Purpose: Deploy workflow to GitHub as PR
- Request: `{ "workflow_yaml": "...", "repo_url": "...", "branch": "..." }`
- Response: `{ "branch": "devsecops-123", "pr_number": 45, "pr_url": "..." }`

**POST /execute**
- Purpose: Trigger workflow dispatch
- Request: `{ "repo_url": "...", "workflow_id": "...", "branch": "..." }`
- Response: `{ "run_id": 123456, "run_url": "..." }`

**POST /validate**
- Purpose: Validate workflow YAML
- Request: `{ "workflow_yaml": "...", "security_requirements": [...] }`
- Response: `{ "valid": true, "errors": [], "warnings": [...] }`

**GET /latest-run**
- Purpose: Get latest workflow run
- Query: `?repo_url=...&workflow_id=...`
- Response: `{ "run_id": 123, "status": "completed", ... }`

**GET /status/{run_id}**
- Purpose: Get run status + jobs
- Response: `{ "status": "...", "jobs": [...], "conclusion": "..." }`

**GET /status/{run_id}/stream**
- Purpose: SSE stream for live status
- Response: Server-Sent Events stream

**GET /logs/{run_id}**
- Purpose: Get raw workflow logs
- Response: `{ "logs": "...", "job_logs": {...} }`

**POST /analyze/{run_id}**
- Purpose: Security analysis of completed run
- Response:
  ```json
  {
    "risk_score": 75,
    "findings": [...],
    "recommendations": [...]
  }
  ```

**GET /analysis/{run_id}**
- Purpose: Retrieve cached analysis
- Response: Cached analysis object

**POST /analyze-execution/{run_id}**
- Purpose: Failure analysis + root cause + remediation PR
- Response:
  ```json
  {
    "failure_analysis": "...",
    "root_cause": "dependency_error",
    "remediation_yaml": "...yaml...",
    "remediation_pr_url": "..."
  }
  ```

**POST /compliance**
- Purpose: Compliance check workflow YAML
- Request: `{ "workflow_yaml": "..." }`
- Response: `{ "valid": true, "findings": [...], "compliance_score": 85 }`

**POST /webhook/github**
- Purpose: GitHub webhook receiver (AI Service directly)
- Response: `{ "triggered": true }`

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
   → {
       "TypeScript": 45000,
       "JavaScript": 12000,
       "HTML": 3000
     }

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

**Supported Languages**:
- JavaScript/TypeScript (Node.js ecosystem)
- Python (Django, Flask, FastAPI)
- Java (Spring Boot, Maven)
- Go (standard Go projects)
- Ruby (Rails)
- PHP (Laravel)
- C# (.NET Core)

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
        if "nuxt" in deps: frameworks.append("Nuxt.js")
        if "express" in deps: frameworks.append("Express")
        if "fastify" in deps: frameworks.append("Fastify")
        if "nest" in deps: frameworks.append("NestJS")
    
    # Python
    if "requirements.txt" in files or "pyproject.toml" in files:
        deps = parse_requirements(files)
        if "django" in deps: frameworks.append("Django")
        if "flask" in deps: frameworks.append("Flask")
        if "fastapi" in deps: frameworks.append("FastAPI")
        if "pytest" in deps or "django" in deps: frameworks.append("Django")
    
    # Java
    if "pom.xml" in files:
        deps = parse_pom(files["pom.xml"])
        if "spring-boot" in deps: frameworks.append("Spring Boot")
        if "junit" in deps: frameworks.append("JUnit")
    
    return frameworks
```

### 8.3 Architecture Detection

**Detection Heuristics**:

```python
def detect_architecture(structure):
    indicators = {
        "microservices": [],
        "monolith": [],
        "modular": []
    }
    
    # Docker indicators
    docker_compose_count = count_files("docker-compose*.yml")
    if docker_compose_count >= 2:
        indicators["microservices"].append("multiple_docker_compose")
    
    # Service directory patterns
    service_dirs = ["services/", "microservices/", "apps/"]
    for dir in service_dirs:
        if exists(dir) and count_items(dir) > 1:
            indicators["microservices"].append("service_directories")
    
    # API patterns
    if has_api_gateway(structure):
        indicators["microservices"].append("api_gateway")
    
    if has_service_discovery(structure):
        indicators["microservices"].append("service_discovery")
    
    # Monolith indicators
    if is_single_main_entry(structure):
        indicators["monolith"].append("single_entry_point")
    
    # Calculate score
    microservice_score = len(indicators["microservices"]) * 20
    monolith_score = len(indicators["monolith"]) * 15
    
    if microservice_score > 40:
        return "microservices"
    elif microservice_score > 20:
        return "modular_monolith"
    else:
        return "monolith"
```

### 8.4 Deployment Detection

**Detection Sources**:
1. Dockerfile presence
2. docker-compose.yml
3. Kubernetes manifests (k8s/ directory)
4. Helm charts (charts/ directory)
5. CloudFormation templates
6. Terraform configurations

**Deployment Target Mapping**:
| Detection | Target |
|-----------|--------|
| Dockerfile only | Docker Container |
| docker-compose.yml | Docker Compose |
| k8s/ manifests | Kubernetes |
| Helm charts | Kubernetes (Helm) |
| terraform/*.tf | Cloud (AWS/GCP/Azure) |
| serverless.yml | Serverless |

### 8.5 Confidence Scoring

**Confidence Calculation**:

```python
def calculate_confidence(detection_type, data):
    base_confidence = {
        "language": 0.9,
        "framework": 0.7,
        "architecture": 0.6,
        "deployment": 0.8
    }
    
    # Adjust based on evidence quality
    if detection_type == "language":
        if data["percentage"] > 80:
            return base_confidence["language"]
        elif data["percentage"] > 50:
            return base_confidence["language"] * 0.9
        else:
            return base_confidence["language"] * 0.7
    
    if detection_type == "framework":
        # Multiple evidence sources increase confidence
        evidence_count = len(data["evidence"])
        return min(0.95, 0.6 + (evidence_count * 0.1))
    
    return base_confidence.get(detection_type, 0.7)
```

---

## 9. Security Requirement Inference

### 9.1 Inference Process

**Input Processing**:
1. Receive technology metadata (language, frameworks, tools)
2. Receive architecture type (monolith/microservices)
3. Receive deployment target (k8s, vm, serverless)

**Control Selection Logic**:

```python
def infer_security_controls(tech, arch, target):
    controls = []
    
    # Language-specific controls
    language_controls = {
        "typescript": ["npm_audit", "snyk_scan", "secret_scanning"],
        "javascript": ["npm_audit", "snyk_scan", "secret_scanning"],
        "python": ["safety_check", "bandit_scan", "secret_scanning"],
        "java": ["owasp_dep_check", "spotbugs", "secret_scanning"],
        "go": ["govulncheck", "staticcheck", "secret_scanning"],
    }
    
    for lang in tech.languages:
        if lang in language_controls:
            controls.extend(language_controls[lang])
    
    # Framework-specific controls
    framework_controls = {
        "react": ["xss_protection", "csp_validation"],
        "vue": ["xss_protection", "csp_validation"],
        "django": ["sql_injection_check", "csrf_validation"],
        "spring": ["spring_security_scan", "dep_check"],
    }
    
    for fw in tech.frameworks:
        if fw in framework_controls:
            controls.extend(framework_controls[fw])
    
    # Architecture-specific controls
    if arch == "microservices":
        controls.extend([
            "service_mesh_security",
            "network_policy_enforcement",
            "api_gateway_auth"
        ])
    
    # Deployment-specific controls
    deployment_controls = {
        "kubernetes": ["trivy_scan", "kube_bench", "rbac_audit", "network_policy"],
        "docker": ["trivy_scan", "hadolint", "container_signing"],
        "serverless": ["function_scan", "runtime_check"],
    }
    
    if target in deployment_controls:
        controls.extend(deployment_controls[target])
    
    # Remove duplicates
    return list(set(controls))
```

### 9.2 Control Categories

| Category | Controls |
|----------|----------|
| Dependency Security | npm_audit, safety_check, owasp_dep_check, govulncheck |
| SAST | bandit, eslint_security, spotbugs, golangci-lint |
| Secret Scanning | detect_secrets, gitleaks, secret_scanning |
| Container Security | trivy_scan, hadolint, container_signing |
| Kubernetes Security | kube_bench, trivy_k8s, rbac_audit |
| Compliance | owasp_top10, cis_benchmark, nist_controls |

### 9.3 Compliance Standard Mapping

**OWASP Top 10 Mapping**:
| OWASP Category | Controls |
|----------------|----------|
| A01:2021 Broken Access Control | secret_scanning, permission_audit |
| A02:2021 Cryptographic Failures | secret_scanning, config_encryption |
| A03:2021 Injection | sast_scan, sql_injection_check |
| A04:2021 Insecure Design | threat_modeling, security_review |
| A05:2021 Security Misconfiguration | config_audit, hardening_scan |
| A06:2021 Vulnerable Components | dep_check, vulnerability_scan |
| A07:2021 Auth Failures | permission_audit, token_validation |
| A08:2021 Data Integrity Failures | supply_chain_check, sig_verification |
| A09:2021 Logging Failures | log_audit, monitoring_setup |
| A10:2021 SSRF | network_policy, egress_control |

### 9.4 Reasoning Examples

**Example 1: Node.js React Application**

```
Input:
- Language: TypeScript (85%)
- Framework: React (package.json)
- Deployment: Docker container

Inference Process:
1. Language controls → npm_audit, snyk_scan, secret_scanning
2. Framework controls → xss_protection, csp_validation
3. Deployment controls → trivy_scan, hadolint
4. Additional → dependency_check, sast_eslint

Output:
security_controls: [
  "npm_audit",
  "snyk_scan",
  "secret_scanning",
  "trivy_scan",
  "hadolint",
  "dependency_check",
  "sast_eslint"
]
compliance_standards: ["OWASP_Top10", "CIS_Docker"]
```

**Example 2: Python FastAPI Microservices**

```
Input:
- Language: Python (90%)
- Framework: FastAPI
- Architecture: microservices
- Deployment: Kubernetes

Inference Process:
1. Language controls → safety_check, bandit_scan, secret_scanning
2. Framework controls → sql_injection_check, api_security_scan
3. Architecture controls → service_mesh_security, network_policy_enforcement, api_gateway_auth
4. Deployment controls → trivy_scan, kube_bench, rbac_audit, network_policy

Output:
security_controls: [
  "safety_check",
  "bandit_scan",
  "secret_scanning",
  "api_security_scan",
  "service_mesh_security",
  "network_policy_enforcement",
  "trivy_scan",
  "kube_bench",
  "rbac_audit"
]
compliance_standards: ["OWASP_Top10", "CIS_Kubernetes", "NIST_SPF"]
```

---

## 10. Pipeline Generation Mechanism

### 10.1 Generation Inputs

**Required Inputs**:
- `repository_id`: Repository identifier
- `repo_url`: GitHub repository URL
- `github_token`: GitHub access token
- `technology_metadata`: Detected technology stack
- `security_requirements`: Inferred security controls

**Optional Inputs**:
- `build_tool`: Specific build tool preference
- `test_framework`: Specific test framework
- `deploy_target`: Specific deployment target
- `additional_config`: User-provided configuration

### 10.2 Generation Process

**Step 1: Context Building**

```python
def build_generation_context(repo_metadata, tech, security, user_config):
    context = {
        "repository": {
            "name": repo_metadata["name"],
            "owner": repo_metadata["owner"],
            "language": tech.primary_language,
            "frameworks": tech.frameworks,
            "has_dockerfile": tech.has_dockerfile
        },
        "security": {
            "controls": security.controls,
            "standards": security.compliance_standards
        },
        "build": {
            "tool": user_config.build_tool or detect_build_tool(tech),
            "test_framework": user_config.test_framework or detect_test_framework(tech)
        },
        "deployment": {
            "target": user_config.deploy_target or tech.deployment_target
        }
    }
    return context
```

**Step 2: LLM Prompt Construction**

```python
def construct_generation_prompt(context):
    prompt = f"""
Generate a GitHub Actions workflow for:

Repository: {context.repository.name}
Language: {context.repository.language}
Frameworks: {', '.join(context.repository.frameworks)}
Docker: {'Yes' if context.repository.has_dockerfile else 'No'}

Security Controls Required:
{chr(10).join(f'- {ctrl}' for ctrl in context.security.controls)}

Compliance Standards: {', '.join(context.security.standards)}

Build Configuration:
- Build Tool: {context.build.tool}
- Test Framework: {context.build.test_framework}

Deployment Target: {context.deployment.target}

Requirements:
1. Use SHA-pinned actions (no @version or @latest)
2. Minimal permissions (read-all by default)
3. Include all security controls as separate jobs
4. Add caching for dependencies
5. Set appropriate timeouts
6. Include notification on failure

Output only the YAML workflow content.
"""
    return prompt
```

**Step 3: LLM Call**

```python
def generate_workflow(prompt):
    response = llm_service.call(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a DevSecOps expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4096
    )
    
    yaml_content = parse_yaml_from_response(response)
    return yaml_content
```

**Step 4: YAML Parsing and Validation**

```python
def parse_and_validate(yaml_content):
    try:
        workflow = yaml.safe_load(yaml_content)
        
        # Validate structure
        required_fields = ["name", "on"]
        for field in required_fields:
            if field not in workflow:
                raise ValidationError(f"Missing required field: {field}")
        
        return {"valid": True, "workflow": workflow}
    
    except yaml.YAMLError as e:
        return {"valid": False, "error": str(e)}
```

### 10.3 Validation Process

**Validation Checks**:

```python
def validate_workflow(workflow, security_requirements):
    errors = []
    warnings = []
    
    # 1. Syntax validation (handled by yaml.safe_load)
    
    # 2. SHA pinning check
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            if "uses" in step:
                action = step["uses"]
                if "@" in action and not is_sha_pin(action):
                    errors.append(f"Action not SHA-pinned: {action}")
    
    # 3. Permission check
    permissions = workflow.get("permissions", {})
    if permissions.get("contents") == "write":
        warnings.append("Workflow has write permissions to contents")
    
    # 4. Security controls check
    required_controls = set(security_requirements.controls)
    included_controls = detect_included_controls(workflow)
    missing_controls = required_controls - included_controls
    
    if missing_controls:
        warnings.append(f"Missing security controls: {missing_controls}")
    
    # 5. Timeout check
    for job in workflow.get("jobs", {}).values():
        if "timeout-minutes" not in job:
            warnings.append(f"Job {job} missing timeout-minutes")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
```

### 10.4 Deployment Process

**Deployment Flow**:

```python
async def deploy_workflow(workflow_yaml, repo_metadata, branch_name):
    # 1. Create branch
    branch = await github.create_branch(
        repo=repo_metadata.full_name,
        branch=branch_name,
        from_branch=repo_metadata.default_branch
    )
    
    # 2. Create workflow file
    await github.create_file(
        repo=repo_metadata.full_name,
        path=".github/workflows/devsecops-pipeline.yml",
        content=workflow_yaml,
        branch=branch_name,
        message="feat: Add DevSecOps pipeline"
    )
    
    # 3. Create PR
    pr = await github.create_pull_request(
        repo=repo_metadata.full_name,
        title="DevSecOps Pipeline Generated",
        body=generate_pr_description(workflow_yaml),
        head=branch_name,
        base=repo_metadata.default_branch
    )
    
    return {
        "branch": branch_name,
        "pr_number": pr.number,
        "pr_url": pr.html_url
    }
```

### 10.5 Workflow Generation Strategy

**Stage Generation**:

```python
def generate_stages(tech, security):
    stages = []
    
    # Build stage
    stages.append({
        "name": "build",
        "jobs": ["lint", "compile", "test"],
        "triggers": ["push", "pull_request"]
    })
    
    # Security stage
    security_jobs = []
    for control in security.controls:
        if control in ["npm_audit", "safety_check", "dep_check"]:
            security_jobs.append("dependency_scan")
        if control in ["sast_eslint", "bandit", "spotbugs"]:
            security_jobs.append("static_analysis")
        if control in ["trivy_scan", "hadolint"]:
            security_jobs.append("container_scan")
    
    if security_jobs:
        stages.append({
            "name": "security",
            "jobs": list(set(security_jobs)),
            "triggers": ["push", "pull_request"]
        })
    
    # Deploy stage
    if tech.deployment_target:
        stages.append({
            "name": "deploy",
            "jobs": ["deploy"],
            "triggers": ["push"],
            "condition": "branch == 'main'"
        })
    
    return stages
```

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

**API Endpoints Used**:
- `GET /repos/{owner}/{repo}/actions/runs` - List runs
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}` - Get run details
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs` - Get jobs
- `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` - Trigger dispatch

### 11.2 Webhook Processing

**Processing Flow**:

```python
async def process_github_webhook(payload, event_type):
    if event_type == "workflow_run":
        return await handle_workflow_run(payload)
    elif event_type == "push":
        return await handle_push(payload)
    elif event_type == "pull_request":
        return await handle_pull_request(payload)

async def handle_workflow_run(payload):
    action = payload.get("action")
    run_data = payload.get("workflow_run", {})
    
    if action == "completed":
        # Extract run details
        run_info = {
            "github_run_id": run_data["id"],
            "status": run_data["status"],
            "conclusion": run_data["conclusion"],
            "html_url": run_data["html_url"],
            "run_number": run_data["run_number"]
        }
        
        # Update database
        pipeline_run = await update_or_create_run(run_info)
        
        # Trigger AI analysis
        await ai_service.analyze_run(pipeline_run.id)
        
        return {"status": "analyzed"}
    
    elif action in ["in_progress", "queued"]:
        # Update status only
        await update_run_status(run_data["id"], run_data["status"])
        return {"status": "updated"}
```

### 11.3 Run Collection

**Collection Process**:

```python
async def collect_run_details(run_id):
    run = await run_repository.find_by_id(run_id)
    repo = await repository_repository.find_by_id(run.pipeline.repository_id)
    
    # Decrypt GitHub token
    token = decrypt_token(repo.access_token_encrypted)
    
    # Fetch run status
    run_response = await github.get_workflow_run(
        repo.full_name,
        run.github_run_id,
        token
    )
    
    # Update run status
    run.status = run_response.status
    run.conclusion = run_response.conclusion
    run.started_at = run_response.run_started_at
    run.completed_at = run_response.completed_at
    run.duration_seconds = calculate_duration(run_response)
    
    # Fetch jobs if completed
    if run.status == "completed":
        jobs = await github.get_workflow_jobs(
            repo.full_name,
            run.github_run_id,
            token
        )
        run.jobs = json.dumps(jobs)
    
    await run_repository.update(run)
    return run
```

### 11.4 Job Collection

**Job Structure**:

```json
{
  "id": 123456,
  "name": "security-scan",
  "status": "completed",
  "conclusion": "success",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:05:00Z",
  "steps": [
    {
      "name": "Run Trivy scanner",
      "status": "completed",
      "conclusion": "success",
      "number": 1,
      "duration_seconds": 120
    },
    {
      "name": "Upload results",
      "status": "completed",
      "conclusion": "success",
      "number": 2,
      "duration_seconds": 5
    }
  ]
}
```

### 11.5 Log Analysis

**Analysis Process**:

```python
async def analyze_execution_logs(run_id):
    run = await get_run(run_id)
    repo = await get_repository(run.pipeline.repository_id)
    token = decrypt_token(repo.access_token_encrypted)
    
    # Fetch job logs
    logs = {}
    for job in run.jobs:
        job_logs = await github.get_job_logs(
            repo.full_name,
            job["id"],
            token
        )
        logs[job["name"]] = parse_logs(job_logs)
    
    # Analyze for findings
    findings = []
    
    # Check for vulnerabilities
    vuln_patterns = [
        r"CVE-\d{4}-\d+",
        r"Vulnerable package: (.+)",
        r"Security warning: (.+)"
    ]
    for job_name, log in logs.items():
        for pattern in vuln_patterns:
            matches = re.findall(pattern, log)
            for match in matches:
                findings.append(create_finding("vulnerability", match, job_name))
    
    # Check for errors
    error_patterns = [
        r"Error: (.+)",
        r"FAILED",
        r"security scan failed"
    ]
    for job_name, log in logs.items():
        for pattern in error_patterns:
            matches = re.findall(pattern, log)
            for match in matches:
                findings.append(create_finding("error", match, job_name))
    
    return findings
```

### 11.6 Risk Scoring

**Risk Calculation Formula**:

```python
def calculate_risk_score(findings, execution_context):
    base_score = 100
    
    # Severity deductions
    severity_weights = {
        "critical": 25,
        "high": 15,
        "medium": 10,
        "low": 5
    }
    
    for finding in findings:
        severity = finding.severity
        deduction = severity_weights.get(severity, 10)
        
        # Adjust for exploitability
        if finding.exploitable:
            deduction *= 1.5
        
        # Adjust for scope
        if finding.wide_scope:
            deduction *= 1.2
        
        base_score -= deduction
    
    # Execution context adjustments
    if execution_context.duration > 3600:  # > 1 hour
        base_score -= 5
    
    if execution_context.has_cache_miss:
        base_score -= 3
    
    return max(0, min(100, base_score))
```

### 11.7 Compliance Scoring

**Compliance Calculation**:

```python
def calculate_compliance_score(pipeline, findings, standards):
    total_controls = 0
    compliant_controls = 0
    
    for standard in standards:
        controls = get_standard_controls(standard)
        total_controls += len(controls)
        
        for control in controls:
            if is_control_implemented(control, pipeline):
                compliant_controls += 1
            elif not is_control_broken(control, findings):
                compliant_controls += 1  # Control not implemented but not broken either
    
    # Adjust for findings
    for finding in findings:
        if finding.breaks_compliance:
            compliant_controls -= 1
    
    return (compliant_controls / total_controls) * 100
```

### 11.8 Workflow Quality Scoring

**Quality Dimensions**:

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| Security Coverage | 30% | % of security controls implemented |
| Best Practices | 25% | SHA pinning, minimal permissions, timeouts |
| Maintainability | 20% | Clear structure, documented jobs |
| Performance | 15% | Caching configured, efficient steps |
| Observability | 10% | Logging, notifications, artifact retention |

**Scoring Formula**:

```python
def calculate_quality_score(workflow):
    scores = {}
    
    # Security coverage
    required_controls = get_required_controls(workflow)
    implemented = get_implemented_controls(workflow)
    scores["security"] = (len(implemented) / len(required_controls)) * 100 if required_controls else 100
    
    # Best practices
    best_practice_score = 0
    if has_sha_pinning(workflow): best_practice_score += 25
    if has_minimal_permissions(workflow): best_practice_score += 25
    if has_timeouts(workflow): best_practice_score += 25
    if has_error_handling(workflow): best_practice_score += 25
    scores["best_practices"] = best_practice_score
    
    # Calculate weighted score
    weights = {"security": 0.3, "best_practices": 0.25}
    total_score = sum(scores[k] * weights.get(k, 0) for k in scores)
    
    return total_score
```

---

## 12. Adaptive DevSecOps Model

### 12.1 Model Overview

**Model Purpose**: Provide adaptive DevSecOps workflows that automatically adjust to repository characteristics.

**Input → Processing → Output**:

```
┌─────────────────────┐
│ Repository          │
│ Characteristics     │
├─────────────────────┤
│ - Language          │
│ - Framework         │
│ - Architecture      │
│ - Deployment        │
│ - Security Context  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│          Adaptive Processing Pipeline           │
├─────────────────────────────────────────────────┤
│ Analysis → Classification → Security Selection   │
│                → Workflow Generation            │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│ Adaptive DevSecOps  │
│ Workflow            │
├─────────────────────┤
│ - Stage composition │
│ - Security controls │
│ - Deployment config │
│ - Monitoring setup  │
└─────────────────────┘
```

### 12.2 Input Processing

**Repository Analysis Pipeline**:

```python
def analyze_repository(repo_url, token):
    # Step 1: Connection
    metadata = connect_to_repository(repo_url, token)
    
    # Step 2: Scan
    file_structure = scan_repository(metadata, token)
    
    # Step 3: Technology Detection
    tech = detect_technology(file_structure, metadata)
    
    # Step 4: Architecture Classification
    arch = classify_architecture(file_structure, tech)
    
    # Step 5: Security Inference
    security = infer_security_requirements(tech, arch)
    
    return {
        "metadata": metadata,
        "technology": tech,
        "architecture": arch,
        "security": security
    }
```

### 12.3 Analysis Stage

**Technology Analysis**:

```python
def analyze_technology(repo):
    analysis = {
        "languages": [],
        "frameworks": [],
        "build_tools": [],
        "test_frameworks": [],
        "package_managers": []
    }
    
    # Language detection
    languages = github.get_languages(repo.full_name, token)
    analysis["languages"] = rank_languages(languages)
    
    # Framework detection via file analysis
    for file in get_config_files(repo):
        detected = detect_from_file(file)
        merge_detections(analysis, detected)
    
    return analysis
```

### 12.4 Classification Stage

**Architecture Classification**:

```python
def classify_architecture(repo, tech_analysis):
    indicators = collect_architecture_indicators(repo)
    
    # Microservices indicators
    microservices_score = 0
    if indicators["docker_compose_count"] >= 2:
        microservices_score += 30
    if indicators["service_directories"]:
        microservices_score += 20
    if indicators["api_gateway"]:
        microservices_score += 20
    if indicators["service_mesh"]:
        microservices_score += 15
    if indicators["independent_deployments"]:
        microservices_score += 15
    
    # Decision
    if microservices_score >= 50:
        return {
            "type": "microservices",
            "confidence": min(0.95, 0.5 + microservices_score/100),
            "services": indicators["service_count"]
        }
    elif microservices_score >= 25:
        return {
            "type": "modular_monolith",
            "confidence": 0.7,
            "modules": indicators["module_count"]
        }
    else:
        return {
            "type": "monolith",
            "confidence": min(0.9, 0.5 + (100 - microservices_score)/100)
        }
```

### 12.5 Security Selection Stage

**Adaptive Security Control Selection**:

```python
def select_security_controls(tech, arch, deployment):
    controls = []
    
    # Base controls for all
    controls.extend([
        "secret_scanning",
        "dependency_check",
        "vulnerability_scan"
    ])
    
    # Language-specific controls
    lang_controls = LANGUAGE_SECURITY_MAP.get(tech.primary_language, [])
    controls.extend(lang_controls)
    
    # Architecture-specific controls
    if arch.type == "microservices":
        controls.extend([
            "network_policy_enforcement",
            "service_mesh_security",
            "api_gateway_auth"
        ])
    elif arch.type == "monolith":
        controls.extend([
            "comprehensive_sast"
        ])
    
    # Deployment-specific controls
    deploy_controls = DEPLOYMENT_SECURITY_MAP.get(deployment.target, [])
    controls.extend(deploy_controls)
    
    # Remove duplicates and return
    return deduplicate_controls(controls)
```

### 12.6 Workflow Generation Stage

**Adaptive Workflow Generation**:

```python
def generate_adaptive_workflow(context):
    stages = []
    
    # Stage 1: Build (always present)
    stages.append(generate_build_stage(context.tech))
    
    # Stage 2: Security (adapted to context)
    security_stage = generate_security_stage(context.security)
    if security_stage:
        stages.append(security_stage)
    
    # Stage 3: Deploy (adapted to architecture)
    deploy_stage = generate_deploy_stage(context.arch, context.deployment)
    if deploy_stage:
        stages.append(deploy_stage)
    
    # Generate YAML
    yaml = construct_workflow(stages, context)
    
    return yaml
```

### 12.7 Adaptation for Monolithic Systems

**Monolith-Specific Adaptations**:

```python
MONOLITH_ADAPTATIONS = {
    "build": {
        "single_build_command": True,
        "monorepo_support": False,
        "workspace_awareness": False
    },
    "security": {
        "focus_areas": ["dependency", "code_quality", "secrets"],
        "scan_scope": "entire_application",
        "fail_fast": True
    },
    "deployment": {
        "single_deployment": True,
        "rollback_strategy": "version_revert",
        "canary_support": True
    },
    "monitoring": {
        "aggregated_metrics": True,
        "distributed_tracing": False,
        "service_map": False
    }
}
```

**Example Monolith Workflow**:

```yaml
name: Monolith CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: npm ci
      - name: Lint
        run: npm run lint
      - name: Test
        run: npm test
      - name: Build
        run: npm run build

  security:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Dependency check
        run: npm audit --audit-level=high
      - name: SAST
        run: npm run scan
      - name: Secret scan
        uses: trufflesecurity/trufflehog@main

  deploy:
    runs-on: ubuntu-latest
    needs: security
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy
        run: ./scripts/deploy.sh
```

### 12.8 Adaptation for Microservices Systems

**Microservices-Specific Adaptations**:

```python
MICROSERVICES_ADAPTATIONS = {
    "build": {
        "matrix_strategy": True,
        "service_isolation": True,
        "shared_dependencies": True
    },
    "security": {
        "focus_areas": ["network", "service_auth", "container", "secrets"],
        "scan_scope": "per_service",
        "fail_fast": False
    },
    "deployment": {
        "multi_deployment": True,
        "rollback_strategy": "service_rollback",
        "canary_support": True,
        "blue_green": True
    },
    "monitoring": {
        "aggregated_metrics": False,
        "distributed_tracing": True,
        "service_map": True
    }
}
```

**Example Microservices Workflow**:

```yaml
name: Microservices CI/CD Pipeline

on:
  push:
    paths:
      - 'services/**'
      - 'libs/**'
  pull_request:

jobs:
  detect-changed-services:
    runs-on: ubuntu-latest
    outputs:
      services: ${{ steps.detect.outputs.services }}
    steps:
      - uses: actions/checkout@v4
      - id: detect
        run: |
          services=$(find services -name "package.json" -exec dirname {} \;)
          echo "services=$services" >> $GITHUB_OUTPUT

  build-services:
    runs-on: ubuntu-latest
    needs: detect-changed-services
    strategy:
      matrix:
        service: ${{ fromJSON(needs.detect-changed-services.outputs.services) }}
    steps:
      - uses: actions/checkout@v4
      - name: Build ${{ matrix.service }}
        run: |
          cd services/${{ matrix.service }}
          npm ci
          npm run build
          npm test

  security:
    runs-on: ubuntu-latest
    needs: build-services
    steps:
      - name: Network policy scan
        run: kubectl network-policy-validate
      - name: Service mesh security check
        run: istio-analyze
      - name: Container scan
        run: trivy fs --severity HIGH services/**
      - name: Secret scan
        uses: trufflesecurity/trufflehog@main

  deploy-services:
    runs-on: ubuntu-latest
    needs: security
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to Kubernetes
        run: |
          for service in ${{ needs.detect-changed-services.outputs.services }}; do
            kubectl apply -f services/$service/k8s/
          done
```

### 12.9 Model Adaptation Summary

| Aspect | Monolith | Microservices |
|--------|----------|---------------|
| Build Strategy | Single build | Matrix per service |
| Security Scope | Application-wide | Per-service + network |
| Deployment | Single unit | Multiple services |
| Rollback | Full revert | Per-service |
| Monitoring | Aggregated | Distributed tracing |
| Secrets | Centralized | Per-service + vault |
| Network | Simple | Service mesh |

---

## 13. Research Contribution Mapping

### 13.1 Contribution 1: Repository Analysis Automation

**Research Question**: How can repository characteristics be automatically extracted to inform DevSecOps pipeline generation?

**Implemented Components**:
1. `repository_scan` node
   - File structure scanning
   - Key file detection
   - Configuration file parsing

2. `technology_detection` node
   - Language detection via GitHub API
   - Framework detection via package analysis
   - Build tool identification
   - Test framework detection

3. `architecture_detection` node
   - Monolith/Microservices classification
   - Deployment pattern detection
   - Service boundary identification

**Contribution**: Automated repository analysis reduces manual inspection overhead and enables adaptive pipeline generation based on accurate technology detection.

### 13.2 Contribution 2: AI-Driven Security Requirement Inference

**Research Question**: How can security requirements be inferred from technology stack without explicit user input?

**Implemented Components**:
1. `security_requirement_inference` node
   - Language-specific control mapping
   - Framework security requirements
   - Architecture-aware security needs
   - Deployment target security controls

2. Control selection logic (in `security_requirement_inference`)
   - Mapping tables for technology → controls
   - Compliance standard integration
   - Priority ordering

**Contribution**: AI-driven inference eliminates the need for users to have deep security knowledge, making DevSecOps accessible to teams without dedicated security expertise.

### 13.3 Contribution 3: Adaptive Pipeline Generation

**Research Question**: How can pipeline generation adapt to different architecture types while maintaining security compliance?

**Implemented Components**:
1. `workflow_generation` node
   - Context-aware prompt construction
   - LLM-based YAML generation
   - Stage composition based on architecture

2. `workflow_validation` node
   - Syntax validation
   - Security control verification
   - Best practice enforcement

3. `workflow_repair` node
   - Auto-correction of validation failures
   - Retry mechanism

**Contribution**: Adaptive generation ensures pipelines are tailored to specific architecture requirements (monolith vs microservices) while maintaining consistent security posture.

### 13.4 Contribution 4: Intelligent Pipeline Analysis

**Research Question**: How can pipeline execution results be analyzed to provide actionable security insights?

**Implemented Components**:
1. `security_analyzer` node
   - Log parsing and pattern matching
   - Vulnerability detection
   - Compliance gap identification

2. `risk_assessor` node
   - Risk score calculation
   - Severity categorization
   - Exploitability assessment

3. `compliance_mapper` node
   - Finding to standard mapping
   - Coverage calculation
   - Gap identification

4. `recommendation_gen` node
   - Actionable recommendation generation
   - Priority ordering
   - Reference linking

**Contribution**: Intelligent analysis transforms raw execution data into meaningful security insights with specific, actionable recommendations.

### 13.5 Contribution 5: Automated Remediation

**Research Question**: How can pipeline failures be automatically diagnosed and remediated?

**Implemented Components**:
1. `execution_log_collection` node
   - Log aggregation from multiple jobs
   - Structured log parsing

2. `workflow_failure_analysis` node
   - Failure pattern detection
   - Affected component identification

3. `root_cause_detection` node
   - Root cause categorization
   - Confidence scoring

4. `workflow_remediation_generation` node
   - LLM-based fix generation
   - Validation of remediation

5. `remediation_pr_creation` node
   - Automated PR creation with fixes

**Contribution**: Automated remediation reduces mean time to recovery (MTTR) by automatically diagnosing issues and proposing fixes.

### 13.6 Contribution 6: Adaptive DevSecOps Model

**Research Question**: How can DevSecOps practices adapt to different system architectures while maintaining consistent security posture?

**Implemented Components**:
1. Complete AI workflow graph
   - Orchestrated node execution
   - Conditional branching based on context

2. Architecture-specific pipeline templates
   - Monolith pipeline structure
   - Microservices pipeline structure

3. Security control adaptation
   - Network security for microservices
   - Application security for monoliths

**Contribution**: The adaptive model demonstrates that security controls can be appropriately scaled and configured based on architectural context, enabling consistent security outcomes across different system types.

---

## 14. Thesis Mapping

### Chapter 1: Introduction

**Relevant Sections**:
- System Overview (Section 1): Problem statement, objectives
- Functional Requirements (Section 2): System capabilities
- System Architecture (Section 3): Scope and boundaries

**Supporting Material**:
- System purpose and problem being solved
- Target users and use cases
- System limitations

### Chapter 2: Literature Review

**Relevant Sections**:
- AI Agent Architecture (Section 4): State of AI agents
- AI Workflow Graph (Section 5): Workflow orchestration
- Adaptive DevSecOps Model (Section 12): DevSecOps adaptation

**Supporting Material**:
- AI agent taxonomy and classification
- Workflow orchestration approaches
- DevSecOps best practices

### Chapter 3: Methodology

**Relevant Sections**:
- System Architecture (Section 3): Architecture design decisions
- AI Workflow Graph (Section 5): Graph-based orchestration methodology
- Repository Analysis Mechanism (Section 8): Analysis methodology
- Security Requirement Inference (Section 9): Inference methodology
- Pipeline Generation Mechanism (Section 10): Generation methodology

**Supporting Material**:
- Architecture design rationale
- AI workflow design decisions
- Analysis and inference algorithms

### Chapter 4: Implementation

**Relevant Sections**:
- Database Design (Section 6): Database schema
- API Design (Section 7): API specifications
- AI Agent Architecture (Section 4): Node implementations
- AI Workflow Graph (Section 5): Graph implementation

**Supporting Material**:
- Entity relationship diagrams
- API endpoint documentation
- Node function specifications
- Graph routing logic

### Chapter 5: Evaluation

**Relevant Sections**:
- Pipeline Execution Analysis (Section 11): Analysis methodology
- Adaptive DevSecOps Model (Section 12): Model evaluation
- Research Contribution Mapping (Section 13): Contribution validation

**Supporting Material**:
- Risk scoring methodology
- Compliance scoring methodology
- Workflow quality assessment
- Adaptation effectiveness

### Chapter 6: Conclusion

**Relevant Sections**:
- Research Contribution Mapping (Section 13): Summary of contributions
- System Overview (Section 1): System capabilities summary

**Supporting Material**:
- List of implemented contributions
- System capabilities overview
- Future work directions

---

## Lampiran: Terminologi dan Definisi

### A.1 Definisi Teknis

| Term | Definition |
|------|------------|
| **DevSecOps** | Pendekatan DevOps yang mengintegrasikan praktik keamanan sejak awal lifecycle pengembangan |
| **AI Agent** | Komponen AI yang dapat menjalankan tugas spesifik berdasarkan input dan state |
| **LangGraph** | Framework Python untuk membangun workflow berbasis graph dengan state management |
| **Pipeline** | workflow CI/CD yang mengotomatisasi build, test, dan deployment |
| **Security Controls** | Mekanisme keamanan yang diterapkan dalam pipeline |
| **Compliance Standards** | Standar keamanan yang harus dipatuhi (OWASP, CIS, NIST) |
| **Risk Score** | Nilai 0-100 yang merepresentasikan tingkat risiko keamanan |
| **Compliance Score** | Nilai 0-100 yang merepresentasikan kepatuhan terhadap standar |

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

*Document Version: 1.0*
*Generated for: Bachelor's Thesis - "Perancangan Model DevSecOps Adaptif Berbasis AI untuk Sistem Monolitik dan Microservices"*