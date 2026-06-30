import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import api from "@/lib/axios"

export interface Pipeline {
  id: string
  repository_id: string
  version_number: number
  prompt: string
  user_requirements: string | null
  generated_yaml: string
  stages: string
  ai_explanation: string | null
  generation_params: string
  validation_results: string | null
  deployment_results: string | null
  security_controls_applied: string
  compliance_metadata: string
  // node_io is the per-node I/O trace for Tahap 1-3 (input keys,
  // output diff, duration_ms, status, error). Stored as a JSON
  // string in the `pipelines.node_io` jsonb column; the FE parses
  // it lazily so a missing/empty trace does not break the page.
  node_io?: string | null
  status: string
  created_at: string
  repository?: { full_name: string }
  runs?: PipelineRun[]
}

export interface JobStep {
  name: string
  status: string
  conclusion: string | null
  number: number
  started_at?: string | null
  completed_at?: string | null
}

export interface PipelineJob {
  id: number
  run_id?: number
  workflow_name?: string
  name: string
  status: string
  conclusion: string | null
  started_at: string | null
  completed_at: string | null
  steps: JobStep[]
  html_url?: string | null
}

export interface PipelineRun {
  id: string
  pipeline_id: string
  run_number: number
  github_run_id: number | null
  status: string
  conclusion: string | null
  html_url: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  jobs: string | null
  created_at: string
  error_message?: string | null
}

export interface PipelineAnalysis {
  id: string
  pipeline_run_id: string
  risk_score: number | null
  compliance_score: number | null
  workflow_quality_score: number | null
  security_coverage_score: number | null
  findings_summary: string | null
  severity_breakdown: string
  recommendations: string
  ai_explanation: string | null
  created_at: string
}

// === Dashboard ===
export interface DashboardStats {
  total_projects: number
  total_repositories: number
  total_pipelines: number
  total_executions: number
  pipeline_success_rate: number
  avg_risk_score: number
  avg_compliance_score: number
  avg_security_coverage: number
  avg_workflow_quality: number
  recent_pipelines: Array<{
    id: string
    version: number
    repository: string
    status: string
    created_at: string
  }>
}

export function useDashboardStatsV2() {
  return useQuery<DashboardStats>({
    queryKey: ["dashboard-stats-v2"],
    queryFn: async () => {
      const res = await api.get("/dashboard/stats")
      return res.data
    },
    refetchInterval: 30000,
  })
}

// === Pipelines (Global History) ===
export function usePipelinesList(params: {
  page?: number
  limit?: number
  sort_by?: string
  sort_order?: string
  repository_id?: string
  status?: string
}) {
  return useQuery({
    queryKey: ["pipelines-list", params],
    queryFn: async () => {
      const res = await api.get("/pipelines", { params })
      return res.data as { pipelines: Pipeline[]; total: number; page: number; limit: number }
    },
  })
}

// === Pipelines (By Repository) ===
export function useRepositoryPipelines(repoId: string | undefined) {
  return useQuery({
    queryKey: ["repository-pipelines", repoId],
    queryFn: async () => {
      const res = await api.get(`/repositories/${repoId}/pipelines`)
      return res.data.pipelines as Pipeline[]
    },
    enabled: !!repoId,
  })
}

// === Pipeline By Version ===
export function usePipelineByVersion(repoId: string | undefined, version: number | undefined) {
  return useQuery({
    queryKey: ["pipeline-version", repoId, version],
    queryFn: async () => {
      const res = await api.get(`/repositories/${repoId}/pipelines/${version}`)
      return res.data as Pipeline
    },
    enabled: !!repoId && !!version,
  })
}

// === Pipeline Detail ===
export function usePipelineDetail(pipelineId: string | undefined) {
  return useQuery({
    queryKey: ["pipeline-detail", pipelineId],
    queryFn: async () => {
      const res = await api.get(`/pipelines/${pipelineId}`)
      return res.data as Pipeline
    },
    enabled: !!pipelineId,
  })
}

// === Compare Pipelines ===
interface CompareInput {
  pipeline_a_id: string
  pipeline_b_id: string
}

export interface CompareResult {
  pipeline_a: Record<string, unknown>
  pipeline_b: Record<string, unknown>
  deltas: Record<string, number>
}

export function useComparePipelines() {
  return useMutation({
    mutationFn: async (input: CompareInput) => {
      const res = await api.post("/pipelines/compare", input)
      return res.data as CompareResult
    },
  })
}

// === Pipeline Runs ===
export function usePipelineRuns(pipelineId: string | undefined) {
  return useQuery({
    queryKey: ["pipeline-runs", pipelineId],
    queryFn: async () => {
      const res = await api.get(`/pipelines/${pipelineId}/runs`)
      return res.data.runs as PipelineRun[]
    },
    enabled: !!pipelineId,
  })
}

export function useRunDetail(runId: string | undefined) {
  return useQuery({
    queryKey: ["run-detail", runId],
    queryFn: async () => {
      const res = await api.get(`/runs/${runId}`)
      return res.data as PipelineRun
    },
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "completed" || status === "failed") return false
      return 5000
    },
  })
}

// === Pipeline Analysis ===
export function useRunAnalysis(runId: string | undefined) {
  return useQuery({
    queryKey: ["run-analysis", runId],
    queryFn: async () => {
      const res = await api.get(`/runs/${runId}/analysis`)
      return res.data as PipelineAnalysis
    },
    enabled: !!runId,
  })
}

// === Sync Runs from GitHub ===
export function useDeletePipeline() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/pipelines/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines-list"] })
      queryClient.invalidateQueries({ queryKey: ["repository-pipelines"] })
    },
  })
}

export function useSyncRuns() {
  return useMutation({
    mutationFn: async ({ repoId, version }: { repoId: string; version: number }) => {
      const res = await api.post(`/repositories/${repoId}/pipelines/${version}/sync-runs`)
      return res.data as { message: string; synced: string[] }
    },
  })
}

// === Per-job log findings + raw log (added to fix missing exports) ===
//
// These hooks back the "Findings" panel and "Raw log" view on the
// RunDetail page. The panel currently used by the page is a thin
// "scanner/findings" object that the backend can populate from the
// workflow logs; if the backend endpoint is not yet wired the hook
// returns a safe empty result so the UI doesn't crash.
export interface LogFinding {
  title: string
  severity: string
  file_location?: string
  line?: number
  evidence: string
  remediation_recommendation?: string
  rule_id?: string
}

export interface LogFindingsResponse {
  scanner: string
  findings: LogFinding[]
  truncated: boolean
  unparsed_lines: number
}

export interface RawLogResponse {
  log_text: string
  truncated: boolean
}

export function useJobLogFindings(input: {
  enabled: boolean
  repoId: string | undefined
  version: string | undefined
  runId: string | undefined
  jobId: number
}) {
  return useQuery<LogFindingsResponse>({
    queryKey: ["job-log-findings", input.repoId, input.version, input.runId, input.jobId],
    queryFn: async () => {
      const res = await api.get(
        `/repositories/${input.repoId}/pipelines/${input.version}/runs/${input.runId}/jobs/${input.jobId}/log-findings`,
      )
      return res.data as LogFindingsResponse
    },
    enabled:
      input.enabled && !!input.repoId && !!input.version && !!input.runId && !!input.jobId,
    retry: false,
  })
}

export function useRunRawLog(input: {
  enabled: boolean
  repoId: string | undefined
  version: number
  runId: string | undefined
}) {
  return useQuery<RawLogResponse>({
    queryKey: ["run-raw-log", input.repoId, input.version, input.runId],
    queryFn: async () => {
      const res = await api.get(
        `/repositories/${input.repoId}/pipelines/${input.version}/runs/${input.runId}/raw-log`,
      )
      return res.data as RawLogResponse
    },
    enabled: input.enabled && !!input.repoId && !!input.runId,
    retry: false,
  })
}


// === PDF report generation (RunDetail "Generate PDF Report" button) ===

export interface PdfReportResponse {
  filename: string
  path: string
  size: number
  content_type: string
  content_base64: string
}

export interface PdfReportRequest {
  repository_full_name: string
  run_id: string
  repository_description?: string
  detected_technologies?: Record<string, unknown>
  detected_architecture?: Record<string, unknown>
  detected_architecture_type?: string
  detected_deployment?: Record<string, unknown>
  recommended_deployment_target?: string | null
  detected_domain?: string
  domain_sub_type?: string
  domain_confidence?: number
  domain_threats?: string[]
  features?: string[]
  security_coverages?: Array<Record<string, unknown>>
  ai_generated_rules?: Array<Record<string, unknown>>
  llm_generated_rules?: Array<Record<string, unknown>>
  pipeline_augmentations?: Array<Record<string, unknown>>
  job_designs?: Array<Record<string, unknown>>
  generated_workflow?: string
  generated_stages?: string[]
  validation_passed?: boolean
  validation_errors?: string[]
  validation_warnings?: string[]
  findings?: Array<Record<string, unknown>>
  code_scanning_alerts?: Array<Record<string, unknown>>
  risk_score?: number | null
  security_posture?: number | null
  compliance_score?: number | null
  severity_breakdown?: Record<string, number>
  recommendations?: string[]
}

export function useGeneratePdf() {
  return useMutation({
    mutationFn: async ({
      runId,
      payload,
    }: {
      repoId?: string
      runId: string
      payload: PdfReportRequest
    }) => {
      // The PDF endpoint lives on the AI service
      // (`POST /pipeline/runs/{run_id}/pdf` in
      // `ai-service/app/api/pipeline.py` — note the
      // router prefix `/pipeline`). It is NOT on the Go
      // backend, so we must hit it through the
      // `/ai/...` Vite proxy (which rewrites to
      // `http://ai-service:8000/api/...`) instead of
      // the default `/api/v1/` proxy that goes to Go.
      //
      // v9.5: include run_id AND repository_full_name in both
      // the URL (path param) and the body. The body is the
      // primary source of pipeline metadata; the URL is the
      // fallback that lets the BE look up the run in the DB
      // if the body is empty (e.g. when the FE's state
      // hasn't been hydrated yet).
      const res = await api.post(
        `/ai/pipeline/runs/${runId}/pdf`,
        { run_id: runId, ...payload },
        {
          // LLM-backed PDF generation can take >30s when
          // the AI service is rebuilding the run state. Set
          // the axios timeout to 90s (default is 10s in many
          // axios configs) so the user doesn't get a
          // premature "timeout" error.
          timeout: 90_000,
        },
      )
      const data = res.data as PdfReportResponse & {
        fetch_warnings?: string[]
        synthetic?: boolean
      }
      // Defensive: if the response is missing content_base64
      // (e.g. the AI service returned an empty body), throw
      // an error with a helpful message instead of letting
      // the caller crash on `atob(undefined)`.
      if (!data || !data.content_base64) {
        throw new Error(
          "AI service returned an empty PDF payload. " +
            "This usually means the AI service was unreachable " +
            "or the run has not been persisted yet. " +
            "Try clicking 'Refresh' and then 'Generate PDF' again.",
        )
      }
      return data
    },
  })
}
