import { useMutation, useQuery } from "@tanstack/react-query"
import api from "@/lib/axios"

const AI_BASE = "/ai/pipeline"
const PIPELINE_BASE = "/ai/pipeline"

/**
 * Code Scanning alert normalized by the AI service.
 * Source: GitHub Code Scanning API via `code-scanning/alerts`.
 * See `normalize_code_scanning_alerts` in
 * `app/services/github_service.py` for the producer.
 */
export interface CodeScanningFinding {
  type: string
  title: string
  severity: "critical" | "high" | "medium" | "low" | "warning" | "error" | string
  scanner: string
  source_tool?: string
  scanner_version?: string
  rule_id: string
  file_location: string
  line: number | null
  column?: number | null
  evidence: string
  explanation: string
  code_snippet?: string
  recommendation?: string
  remediation_recommendation?: string
  cwe: string
  owasp: string
  scanner_url: string
  // npm-audit / GHSA findings carry these in addition. The
  // scanner normalizer in `app/services/github_service.py`
  // already populates them on the underlying alert; we model
  // them on the shared interface so the dashboard can look
  // them up directly (e.g. for the per-finding CVSS badge
  // and the per-band CVSS sum header) without casting to
  // `any`.
  package_name?: string | null
  vulnerability_id?: string | null
  // Pre-computed CVSS v3.1 base score and band (critical |
  // high | medium | low) the AI service resolved from the
  // raw alert. Optional because legacy runs persisted
  // before the CVSS mapper was added do not have them.
  cvss_score?: number | null
  cvss_vector?: string | null
  cvss_severity?: "critical" | "high" | "medium" | "low" | null
  _raw?: Record<string, unknown>
}


export interface InvalidWorkflowStage {
  stage: string
  expected: boolean
  reason: string
}

export interface PipelineResponse {
  workflow_yaml: string
  workflow_yaml_generic?: string
  workflow_yaml_custom?: string
  workflow_files?: Array<{
    name: string
    path: string
    kind: "generic" | "custom"
    jobs: string[]
  }>
  stages: string[]
  stages_general?: string[]
  stages_custom?: string[]
  explanation: string | null
  invalid_stages: InvalidWorkflowStage[]
  validation: ValidationResult
  pr_url: string | null
  generation_id: string | null
  errors: string[]
  analysis?: {
    technologies?: {
      primary_language?: string
      frameworks?: string[]
      package_manager?: string
    }
    architecture?: {
      architecture_type?: string
      architecture_confidence?: number
    }
    deployment?: {
      recommended_deployment_target?: string
      docker?: boolean
      kubernetes?: boolean
    }
    security_requirements?: {
      security_controls?: Array<{ control: string; status: string }>
    }
  }
}

export interface FailureAnalysis {
  failure_type: string
  root_cause: string
  confidence: number
  explanation: string
  recommended_fix: string
}

export interface RootCauseData {
  failure_type: string
  root_cause: string
  confidence: number
  evidence: string[]
  affected_components: string[]
  fix_type: string
}

export interface RemediationSuggestion {
  file_path: string
  change_type: string
  before: string | null
  after: string | null
  reasoning: string
  risk: string
  confidence: number
}

export interface ExecutionAnalysis {
  run_id: number
  failed_jobs: Array<{ job_id: number; job_name: string; step_name: string; conclusion: string }>
  failure_analysis: FailureAnalysis | null
  root_cause: RootCauseData | null
  remediation_suggestions: RemediationSuggestion[]
  remediation_workflow: string | null
  remediation_pr_url: string | null
  remediation_pr_number: number | null
  remediation_branch: string | null
  summary: string
  errors: string[]
}

export interface ValidationResult {
  valid: boolean
  syntax_ok: boolean
  actions_pinned: boolean
  permissions_minimal: boolean
  missing_security_stages: string[]
  warnings: string[]
  errors: string[]
}

interface GeneratePipelineApiResponse {
  generated_workflow?: string
  generated_workflow_generic?: string
  generated_workflow_custom?: string
  generated_workflow_files?: Array<{
    name: string
    path: string
    kind: "generic" | "custom"
    jobs: string[]
  }>
  explanation?: string
  generated_stages?: string[]
  generated_stages_general?: string[]
  generated_stages_custom?: string[]
  invalid_workflow_stages?: Array<{ stage: string; expected: boolean; reason: string }>
  validation_passed?: boolean
  validation_errors?: string[]
  validation_warnings?: string[]
  github_pr_url?: string | null
  github_pr_number?: number | null
  github_branch?: string | null
  errors?: string[]
  unified_response?: {
    repository_analysis?: {
      technologies?: {
        primary_language?: string
        frameworks?: string[]
        package_manager?: string
      }
      architecture?: {
        architecture_type?: string
        architecture_confidence?: number
      }
      deployment?: {
        recommended_deployment_target?: string
        docker?: boolean
        kubernetes?: boolean
      }
    }
    security_requirements?: {
      security_controls?: Array<{ control: string; status: string }>
    }
  }
  [key: string]: unknown
}

function normalizeValidation(result: GeneratePipelineApiResponse): ValidationResult {
  const validationErrors = result.validation_errors ?? []
  const validationWarnings = result.validation_warnings ?? []

  return {
    valid: result.validation_passed ?? false,
    syntax_ok: (result.generated_workflow ?? "").trim().length > 0,
    actions_pinned: !validationErrors.some((error) => error.toLowerCase().includes("pinned")),
    permissions_minimal: validationWarnings.length === 0,
    missing_security_stages: [],
    warnings: validationWarnings,
    errors: validationErrors,
  }
}

function normalizeGenerateResponse(result: GeneratePipelineApiResponse): PipelineResponse {
  const unified = result.unified_response

  return {
    workflow_yaml: result.generated_workflow ?? "",
    workflow_yaml_generic: result.generated_workflow_generic ?? "",
    workflow_yaml_custom: result.generated_workflow_custom ?? "",
    workflow_files: result.generated_workflow_files ?? [],
    explanation: result.explanation ?? "",
    stages: result.generated_stages ?? [],
    stages_general: result.generated_stages_general ?? [],
    stages_custom: result.generated_stages_custom ?? [],
    invalid_stages: (result.invalid_workflow_stages ?? []) as InvalidWorkflowStage[],
    validation: normalizeValidation(result),
    pr_url: result.github_pr_url ?? null,
    generation_id: null,
    errors: result.errors ?? [],
    analysis: unified ? {
      technologies: unified.repository_analysis?.technologies,
      architecture: unified.repository_analysis?.architecture,
      deployment: unified.repository_analysis?.deployment,
      security_requirements: unified.security_requirements,
    } : undefined,
  }
}

export interface GeneratePipelineInput {
  repository_id: string
  project_id?: string
  query?: string
  language?: string
  framework?: string
  deploy_target?: string
  project_type?: string
  security_requirements?: string[]
  pipeline_mode?: string
  github_token?: string
}

export function useGeneratePipeline() {
  return useMutation({
    mutationFn: async (input: GeneratePipelineInput) => {
      const res = await api.post(`${AI_BASE}/generate`, input)
      return normalizeGenerateResponse(res.data as GeneratePipelineApiResponse)
    },
  })
}

export function useValidateWorkflow() {
  return useMutation({
    mutationFn: async (workflowYaml: string) => {
      const res = await api.post(`${AI_BASE}/validate`, { workflow_yaml: workflowYaml })
      return res.data as ValidationResult
    },
  })
}

export function useDeployWorkflow() {
  return useMutation({
    mutationFn: async (input: {
      repository_id: string
      workflow_yaml: string
      workflow_yaml_generic?: string
      workflow_yaml_custom?: string
      workflow_files?: Array<{ name: string; path: string; kind: "generic" | "custom" }>
      workflow_filename?: string
      branch_prefix?: string
      pr_title?: string
      pr_body?: string
    }) => {
      const res = await api.post(`${AI_BASE}/deploy`, input)
      return res.data as {
        branch: string
        commit_sha: string
        pr_number: number
        pr_url: string
        success: boolean
        errors: string[]
        pipeline_version?: number
        workflow_file?: string
        workflow_file_custom?: string
        workflow_files?: Array<{ name: string; path: string; kind: string }>
      }
    },
  })
}

export function useExecuteWorkflow() {
  return useMutation({
    mutationFn: async (input: { repository_id: string; workflow_filename?: string }) => {
      const res = await api.post(`${AI_BASE}/execute`, input)
      return res.data as { run_id: number; status: string; errors: string[] }
    },
  })
}

export function useLatestWorkflowRun(repositoryId: string) {
  return useQuery({
    queryKey: ["latest-workflow-run", repositoryId],
    queryFn: async () => {
      const cachedToken =
        (typeof window !== "undefined" && localStorage.getItem("github_token")) || ""
      const res = await api.get(`${AI_BASE}/latest-run`, {
        params: {
          repository_id: repositoryId,
          github_token: cachedToken,
        },
      })
      return res.data as { run_id: number | null; status: string; conclusion: string | null }
    },
    enabled: !!repositoryId,
    retry: false,
  })
}

export interface NodeSpec {
  id: string
  name: string
  tahap: number
  type: "deterministic" | "llm" | "hybrid"
  function: string
  inputs: string[]
  outputs: string[]
  prompt: string | null
  fallback: string | null
  file: string
  line_count: number
  spec_ref: string
}

export function useNodeSpecs(tahap: number[] | undefined) {
  return useQuery<NodeSpec[]>({
    queryKey: ["node-specs", tahap],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (tahap && tahap.length === 1) {
        params.tahap = String(tahap[0])
      }
      const res = await api.get(`${PIPELINE_BASE}/node-specs`, { params })
      return (res.data?.nodes ?? []) as NodeSpec[]
    },
    staleTime: 60 * 60 * 1000,
  })
}

export function useExecutionStatus(repositoryId: string, runId: number | null) {
  return useQuery({
    queryKey: ["execution-status", repositoryId, runId],
    queryFn: async () => {
      // Pull the GitHub token from the client-side cache so the AI
      // service can hit /repos/.../actions/runs/{id}/jobs. Without
      // this, the GitHub call returns 401 and the panel shows
      // "No subject runs yet" even when the run exists.
      const cachedToken =
        (typeof window !== "undefined" && localStorage.getItem("github_token")) || ""
      const res = await api.get(`${AI_BASE}/status/${runId}`, {
        params: {
          repository_id: repositoryId,
          github_token: cachedToken,
        },
      })
      return res.data as {
        run_id: number
        status: string
        conclusion: string | null
        html_url: string
        jobs: Array<{
          id: number
          workflow_name?: string
          name: string
          status: string
          conclusion: string | null
          started_at: string | null
          completed_at: string | null
          steps: Array<{ name: string; status: string; conclusion: string | null; number: number; started_at?: string | null; completed_at?: string | null }>
        }>
        started_at: string | null
        completed_at: string | null
        duration_seconds: number | null
      }
    },
    enabled: !!repositoryId && !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "completed" || status === "success" || status === "failure" || status === "cancelled") {
        return false
      }
      return 5000
    },
  })
}

export function useExecutionLogs(repositoryId: string, runId: number | null) {
  return useQuery({
    queryKey: ["execution-logs", repositoryId, runId],
    queryFn: async () => {
      const res = await api.get(`${AI_BASE}/logs/${runId}`, {
        params: { repository_id: repositoryId },
      })
      return res.data as { logs: string }
    },
    enabled: !!repositoryId && !!runId,
    refetchInterval: 5000,
  })
}

export function useAnalyzeExecution() {
  return useMutation({
    mutationFn: async (input: {
      repositoryId: string
      runId: number | null
      workflowJobs?: string
      workflowConclusion?: string
    }) => {
      const res = await api.post(`${AI_BASE}/analyze-execution/${input.runId}`, {
        repository_id: input.repositoryId,
        workflow_jobs: input.workflowJobs,
        workflow_conclusion: input.workflowConclusion,
      })
      return res.data as ExecutionAnalysis
    },
  })
}

export interface RepositoryAnalysis {
  technologies: {
    primary_language: string
    primary_language_confidence: number
    primary_language_reason: string
    frameworks: string[]
    framework_confidences: number[]
    build_tools: string[]
    package_manager: string
    test_framework?: string
    database?: string
    runtime?: string
  }
  architecture: {
    architecture_type: string
    architecture_confidence: number
    architecture_reason: string
    service_count?: number
    service_names?: string[]
    is_containerized: boolean
    has_api_gateway: boolean
    has_message_queue: boolean
    has_database_config: boolean
    has_shared_libraries: boolean
  }
  deployment: {
    docker: boolean
    docker_confidence: number
    docker_reason: string
    docker_compose: boolean
    kubernetes: boolean
    kubernetes_confidence: number
    kubernetes_reason: string
    terraform: boolean
    helm: boolean
    cloud_provider?: string
    recommended_deployment_target: string
    alternative_deployment_targets: string[]
    deployment_reason: string
  }
  detected_at: string
}

export interface SecurityControl {
  control: string
  status: "recommended" | "optional" | "not_required"
  reason: string
  tool?: string
  tool_version?: string
}

export interface SecurityRequirements {
  security_controls: SecurityControl[]
  required_tools: Array<{ name: string; purpose: string; language: string }>
  pipeline_stages: Array<{ name: string; order: number; required_for: string[]; estimated_duration_minutes: number }>
  total_controls: number
  recommended_count: number
  optional_count: number
  not_required_count: number
}

export interface AnalyzeRepositoryResponse {
  repository: string
  repository_url: string | null
  default_branch: string | null
  technologies: RepositoryAnalysis["technologies"]
  architecture: string
  architecture_detail: RepositoryAnalysis["architecture"]
  architecture_confidence: number
  architecture_reason: string
  deployment: RepositoryAnalysis["deployment"]
  recommended_deployment_target: string
  security_requirements: SecurityRequirements
  existing_workflows: string[]
  errors: string[]
  unified_response?: {
    repository_analysis: RepositoryAnalysis
    security_requirements: SecurityRequirements
  }
}

export function useAnalyzeRepository() {
  return useMutation({
    mutationFn: async (repositoryFullName: string) => {
      const res = await api.post(`${AI_BASE}/repo/analyze`, {
        repository_full_name: repositoryFullName,
      })
      return res.data as AnalyzeRepositoryResponse
    },
  })
}

export interface PipelineAnalysisResult {
  summary: string
  findings: unknown[]
  risk_score: number | null
  risk_level: string
  compliance_score: number | null
  security_coverage_score: number | null
  compliance_mappings: unknown[]
  severity_breakdown: Record<string, number>
  recommendations: unknown[]
  errors: string[]
  validation_findings: unknown[]
  log_analysis: unknown[]
  // Code Scanning alerts (primary source) from GitHub API.
  // Shape is the AI agent's normalized SecurityFinding dict
  // (see normalize_code_scanning_alerts in github_service.py).
  code_scanning_alerts?: CodeScanningFinding[]
  code_scanning_source?: string
  workflow_conclusion: string | null
}

export function usePipelineAnalyze() {
  return useMutation({
    mutationFn: async (input: {
      repository_id: string
      run_id: number
      github_token?: string
      // Reviewer feedback: a "Refresh Analysis" button in the
      // RunDetail page sets `force: true` to bypass the
      // saved-analysis cache. The AI service then re-runs the
      // log evaluator on the latest workflow logs.
      force?: boolean
    }) => {
      const res = await api.post(`${AI_BASE}/analyze/${input.run_id}`, {
        repository_id: input.repository_id,
        github_token: input.github_token,
        force: input.force ?? false,
      })
      return res.data as PipelineAnalysisResult
    },
  })
}

export interface ComplianceResult {
  valid: boolean
  syntax_ok: boolean
  actions_pinned: boolean
  permissions_minimal: boolean
  missing_security_stages: string[]
  findings: Array<{ type: string; rule: string; message: string; action?: string }>
  errors: string[]
  warnings: string[]
}

export function useWorkflowCompliance() {
  return useMutation({
    mutationFn: async (input: { workflow_yaml: string; repository_full_name?: string }) => {
      const res = await api.post(`${AI_BASE}/compliance`, {
        workflow_yaml: input.workflow_yaml,
        repository_full_name: input.repository_full_name || "",
      })
      return res.data as ComplianceResult
    },
  })
}

/**
 * The shape of the response from `POST /ai/pipeline/repo/pipeline`.
 * This is the AI service's Tahap-1/Tahap-2 output: it carries
 * the detected technologies, architecture, deployment, the
 * applicable security coverages, the pipeline augmentations,
 * and the generated workflow YAML. The PDF report uses these
 * fields directly so the cover page, Section 1, Section 2, and
 * Section 5 are populated without us having to call the
 * analyzer first.
 */
export interface RepoPipelineResult {
  repository_full_name: string
  pipeline_version: number
  detected_architecture: {
    architecture_type: string
    service_count?: number
    confidence?: number
    reason?: string
  }
  detected_architecture_type: string
  detected_technologies: {
    primary_language?: string
    primary_language_confidence?: number
    frameworks?: string[]
    build_tools?: string[]
    package_manager?: string
    test_framework?: string
    database?: string
    runtime?: string
  }
  detected_deployment: {
    docker?: boolean
    docker_confidence?: number
    docker_compose?: boolean
    kubernetes?: boolean
    terraform?: boolean
    helm?: boolean
    cloud_provider?: string | null
  }
  recommended_deployment_target: string | null
  detected_domain: string
  domain_sub_type: string
  domain_confidence: number
  domain_evidence: string[]
  domain_threats: string[]
  attack_surfaces: string[]
  features: string[]
  inferred_security_needs: {
    security_controls: Array<{
      control: string
      status: string
      tool: string
      reason: string
    }>
  }
  security_coverages: Array<{
    id: string
    reason: string
    applicable?: boolean
  }>
  pipeline_augmentations: Array<{
    coverage: string
    job: string
    configuration: string
    reason?: string
  }>
  ai_generated_rules: Array<Record<string, unknown>>
  job_designs: Array<Record<string, unknown>>
  generated_workflow: string
  generated_workflow_generic?: string
  generated_workflow_custom?: string
  generated_stages: string[]
  generated_stages_general: string[]
  generated_stages_custom: string[]
  stage_explanations: Array<{
    stage: string
    tool: string
    explanation: string
  }>
  validation_passed: boolean
  validation_errors: string[]
  validation_warnings: string[]
  ai_explanation: string | null
  errors: string[]
  [key: string]: unknown
}

export function useRepoPipeline() {
  return useMutation({
    mutationFn: async (input: {
      repository_full_name: string
      github_token?: string
      auto_deploy?: boolean
    }) => {
      const res = await api.post(`${PIPELINE_BASE}/repo/pipeline`, {
        repository_full_name: input.repository_full_name,
        github_token: input.github_token || "",
        auto_deploy: input.auto_deploy ?? false,
      })
      return res.data as RepoPipelineResult
    },
  })
}

export interface PerVulnRecommendationResult {
  rule_id: string
  file_location: string | null
  line: number | null
  recommendation: string
  code_changes: Array<{
    before: string
    after: string
    file?: string
    description?: string
  }>
}

export function usePerVulnRecommendation() {
  return useMutation({
    mutationFn: async (input: {
      repository_full_name: string
      github_token?: string
      vulnerability: {
        rule_id: string
        severity: string
        file_location?: string | null
        line?: number | null
        title?: string | null
        code_snippet?: string | null
        cvss_score?: number | null
        scanner?: string | null
      }
    }) => {
      const res = await api.post(`${AI_BASE}/recommend`, {
        repository_full_name: input.repository_full_name,
        github_token: input.github_token || "",
        vulnerability: input.vulnerability,
      })
      return res.data as PerVulnRecommendationResult
    },
  })
}