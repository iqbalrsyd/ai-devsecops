import { useEffect, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useRunDetail, useRunAnalysis, useJobLogFindings, useRunRawLog, useGeneratePdf } from "@/hooks/usePipelinesV2"
import { usePipelineAnalyze, useNodeSpecs, useRepoPipeline, usePerVulnRecommendation, type RepoPipelineResult } from "@/hooks/usePipeline"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import Header from "@/components/Header"
import NodeSpecCard from "@/components/NodeSpecCard"
import type { PipelineJob, JobStep, Finding } from "@/hooks/usePipelinesV2"
import { Clock, ExternalLink, Loader2, CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronRight, FileWarning, Shield, RefreshCw, FileText, Layers, Sparkles } from "lucide-react"

function safeJsonParse<T>(val: unknown, fallback: T): T {
  if (val == null || val === "" || val === "null") return fallback
  try {
    const parsed = typeof val === "string" ? JSON.parse(val) : val
    return parsed != null ? parsed : fallback
  } catch {
    return fallback
  }
}

function getDuration(seconds: number | null): string {
  if (!seconds) return ""
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function formatTime(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return "just now"
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString()
}

function StatusIcon({ status, conclusion, className }: { status: string; conclusion: string | null; className?: string }) {
  if (conclusion === "success") return <CheckCircle2 className={`text-green-500 ${className || "h-5 w-5"}`} />
  if (conclusion === "failure" || conclusion === "cancelled" || conclusion === "skipped")
    return <XCircle className={`text-red-500 ${className || "h-5 w-5"}`} />
  if (status === "in_progress" || status === "queued" || status === "running" || status === "pending")
    return <Loader2 className={`text-blue-500 animate-spin ${className || "h-5 w-5"}`} />
  return <Clock className={`text-yellow-500 ${className || "h-5 w-5"}`} />
}

function StepRow({ step }: { step: JobStep }) {
  return (
    <div className="flex items-center gap-3 py-1.5 px-2">
      <StatusIcon status={step.status} conclusion={step.conclusion} className="h-4 w-4" />
      <span className="text-sm text-muted-foreground">{step.name}</span>
      <span className="text-xs text-muted-foreground ml-auto">
        {step.conclusion === "success" && step.completed_at && formatTime(step.completed_at)}
        {step.status === "running" && "in progress"}
      </span>
    </div>
  )
}

function JobCard({ job, repoId, version, runId }: { job: PipelineJob; repoId: string; version: number; runId: string }) {
  const [expanded, setExpanded] = useState(false)
  const [showFindings, setShowFindings] = useState(false)
  const hasSteps = job.steps && job.steps.length > 0
  const displayName = job.workflow_name ? `${job.workflow_name} / ${job.name}` : job.name
  const duration = job.started_at && job.completed_at
    ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
    : null

  const isFailed = job.conclusion === "failure" || job.conclusion === "cancelled" || job.conclusion === "timed_out"
  const isCompleted = job.conclusion === "success" || isFailed
  const findingsQuery = useJobLogFindings({
    enabled: showFindings && isCompleted,
    repoId,
    version,
    runId,
    jobId: job.id,
  })

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 text-left transition-colors"
      >
        {hasSteps || isCompleted ? (
          expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <div className="w-4 shrink-0" />
        )}
        <StatusIcon status={job.status} conclusion={job.conclusion} />
        <span className="text-sm font-medium flex-1">{displayName}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {job.conclusion === "success" && duration != null && `Passing after ${getDuration(duration)}`}
            {job.conclusion === "failure" && duration != null && `Failing after ${getDuration(duration)}`}
            {job.status === "running" && "Running"}
            {job.status === "queued" && "Queued"}
            {job.status === "pending" && "Pending"}
            {job.status === "completed" && !job.conclusion && "Completed"}
          </span>
          <Badge variant={
            job.conclusion === "success" ? "default" as const :
            job.conclusion === "failure" ? "destructive" as const :
            "secondary" as const
          } className="text-xs whitespace-nowrap">
            {job.conclusion || job.status}
          </Badge>
        </div>
      </button>
      {expanded && (
        <div className="border-t bg-muted/30">
          {hasSteps && (
            <div className="px-4 py-2">
              {job.steps.map((step) => (
                <StepRow key={step.number} step={step} />
              ))}
            </div>
          )}
          {isCompleted && (
            <div className="px-4 py-3 border-t">
              <div className="flex items-center gap-2 mb-2">
                <Shield className={`h-4 w-4 ${isFailed ? "text-amber-600" : "text-blue-600"}`} />
                <span className="text-sm font-medium">Security findings from job log</span>
                <span className="text-xs text-muted-foreground">
                  ({isFailed ? "failure may indicate workflow config error" : "scan output"})
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto h-7 text-xs"
                  onClick={() => setShowFindings((v) => !v)}
                >
                  {showFindings ? "Hide" : "Extract"}
                </Button>
              </div>
              {showFindings && (
                <JobLogFindingsPanel
                  loading={findingsQuery.isLoading}
                  error={findingsQuery.error}
                  data={findingsQuery.data}
                  jobConclusion={job.conclusion || ""}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function JobLogFindingsPanel({
  loading,
  error,
  data,
  jobConclusion,
}: {
  loading: boolean
  error: unknown
  data?: { scanner: string; findings: Array<{ title: string; severity: string; file_location?: string; line?: number; evidence: string; remediation_recommendation?: string; rule_id?: string }>; truncated: boolean; unparsed_lines: number }
  jobConclusion: string
}) {
  if (loading) {
    return (
      <div className="text-xs text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-3 w-3 animate-spin" />
        Fetching log from GitHub and parsing…
      </div>
    )
  }
  if (error) {
    return (
      <div className="text-xs text-red-600">
        Failed to fetch log findings: {String((error as Error)?.message || error)}
      </div>
    )
  }
  if (!data) return null

  const severityColors: Record<string, string> = {
    critical: "bg-red-100 text-red-800 border-red-300",
    high: "bg-orange-100 text-orange-800 border-orange-300",
    medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
    low: "bg-blue-100 text-blue-800 border-blue-300",
  }

  const isFailed = jobConclusion === "failure" || jobConclusion === "cancelled" || jobConclusion === "timed_out"
  const isSynthesizedConfigError = data.findings.length === 1 && data.findings[0].rule_id === "job-failure"

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Scanner: <span className="font-mono">{data.scanner}</span></span>
        {data.truncated && <span className="text-amber-700">(log truncated to last 2MB)</span>}
        <span>• {data.findings.length} finding{data.findings.length === 1 ? "" : "s"} extracted</span>
      </div>

      {isFailed && isSynthesizedConfigError && (
        <div className="border border-amber-300 bg-amber-50 rounded-md px-3 py-2 text-xs">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700" />
            <span className="font-semibold text-amber-800">Workflow configuration error</span>
          </div>
          <p className="text-amber-900">
            This job exited with a non-zero status but its log did not contain parseable scanner output.
            The failure is likely a workflow configuration problem (missing dependency, wrong command,
            version mismatch, or step ran before the scanner was installed) rather than a code-level
            security issue. Open the raw log on GitHub for the actual error.
          </p>
        </div>
      )}

      {isFailed && !isSynthesizedConfigError && (
        <div className="border border-amber-300 bg-amber-50 rounded-md px-3 py-2 text-xs flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-700 mt-0.5 shrink-0" />
          <span className="text-amber-900">
            Job failed, but the log also contained parseable security findings. These are reported below
            because the scanner did manage to emit output before the job exited.
          </span>
        </div>
      )}

      {!isFailed && data.findings.length === 1 && data.findings[0].rule_id === "job-failure" && (
        <div className="border border-gray-200 bg-gray-50 rounded-md px-3 py-2 text-xs text-gray-600 flex items-center gap-2">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
          No security findings detected in the log. The job completed successfully.
        </div>
      )}

      {data.findings.map((f, i) => {
        const isSynthesized = f.rule_id === "job-failure"
        if (isSynthesized && isFailed) {
          return (
            <div key={i} className="border border-amber-300 bg-amber-50 rounded-md px-3 py-2 text-xs">
              <div className="font-semibold text-amber-800 mb-1">{f.title}</div>
              <p className="text-amber-900">{f.evidence}</p>
              {f.remediation_recommendation && (
                <div className="mt-1 text-[11px] italic text-amber-800">
                  Fix: {f.remediation_recommendation}
                </div>
              )}
            </div>
          )
        }
        return (
          <div key={i} className={`border rounded-md px-3 py-2 text-xs ${severityColors[f.severity] || severityColors.low}`}>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="font-semibold uppercase">{f.severity}</span>
              <span className="font-medium flex-1">{f.title}</span>
              {typeof f.cvss_score === "number" && (
                <span
                  className="text-[10px] font-mono bg-orange-100 text-orange-800 border border-orange-300 px-1.5 py-0.5 rounded whitespace-nowrap"
                  title={f.cvss_vector || "CVSS 3.1"}
                >
                  CVSS {f.cvss_score.toFixed(1)}
                  {f.cvss_severity ? ` · ${f.cvss_severity}` : ""}
                </span>
              )}
            </div>
            {f.file_location && (
              <div className="font-mono text-[11px] opacity-80">
                {f.file_location}{f.line ? `:${f.line}` : ""}
              </div>
            )}
            {f.evidence && (
              <div className="mt-1 text-[11px] opacity-90 whitespace-pre-wrap break-words">
                {f.evidence}
              </div>
            )}
            {f.remediation_recommendation && (
              <div className="mt-1 text-[11px] italic">
                Fix: {f.remediation_recommendation}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// RawLogCard renders the actual workflow log text. Reviewer
// feedback: users want to see the raw log so they can verify the
// AI agent's findings. The log is fetched on demand and rendered
// in a terminal-style block; users can search, copy, or expand
// the view to read in full.
function RawLogCard({ repoId, version, runId }: { projectId: string; repoId: string; version: string; runId: string }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState("")
  const [copied, setCopied] = useState(false)
  const numericVersion = Number(version)
  const { data, isLoading, error, refetch, isFetching } = useRunRawLog({
    enabled: open,
    repoId,
    version: numericVersion,
    runId,
  })

  const logText = data?.log_text ?? ""
  const filtered = filter
    ? logText
        .split("\n")
        .filter((line) => line.toLowerCase().includes(filter.toLowerCase()))
        .join("\n")
    : logText

  const handleCopy = async () => {
    if (!logText) return
    try {
      await navigator.clipboard.writeText(logText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard may be unavailable in some browsers; ignore.
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="text-sm flex items-center gap-2">
            <FileWarning className="h-4 w-4 text-gray-600" />
            Raw workflow log
            {data && (
              <span className="text-xs font-normal text-muted-foreground">
                {data.size.toLocaleString()} chars
                {data.truncated && " (truncated to 5MB)"}
                {data.source === "per_job_logs" && " · per-job fallback"}
              </span>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? "Hide log" : "Show log"}
            </Button>
            {open && data && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => refetch()}
                  disabled={isFetching}
                >
                  {isFetching ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3 mr-1" />
                  )}
                  Refresh
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <CheckCircle2 className="h-3 w-3 mr-1 text-green-600" />
                  ) : null}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </>
            )}
          </div>
        </div>
        {open && (
          <p className="text-xs text-muted-foreground mt-1">
            Same log text the AI agent scans. Use the filter to find
            lines containing specific keywords (CVE ids, scanner
            names, error messages, etc.).
          </p>
        )}
      </CardHeader>
      {open && (
        <CardContent className="space-y-2">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Fetching log from GitHub…
            </div>
          )}
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
              Failed to fetch log:{" "}
              {String((error as { message?: string })?.message ?? error)}
            </div>
          )}
          {data && (
            <>
              <input
                type="text"
                placeholder="Filter lines (case-insensitive)…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full text-sm px-2 py-1 border rounded bg-white"
              />
              {filter && (
                <p className="text-xs text-muted-foreground">
                  Showing {filtered.split("\n").filter(Boolean).length} of{" "}
                  {logText.split("\n").filter(Boolean).length} lines
                </p>
              )}
              <pre
                data-testid="raw-log-pre"
                className="text-xs bg-gray-900 text-green-200 rounded p-3 overflow-x-auto overflow-y-auto font-mono"
                style={{ maxHeight: "600px" }}
              >
                {filtered || (
                  <span className="text-gray-500">
                    (log is empty)
                  </span>
                )}
              </pre>
            </>
          )}
        </CardContent>
      )}
    </Card>
  )
}

type NodeIORecord = {
  node: "security_analysis" | "recommendation_generation" | "response_formatter"
  phase: string
  started_at: string
  status: "ok" | "error"
  duration_ms: number
  input_keys: string[]
  output_summary: Record<string, unknown>
  error?: string
}

function formatJsonTruncated(value: unknown, max = 200): string {
  const s = JSON.stringify(value, null, 2)
  if (s.length <= max) return s
  return s.slice(0, max) + "…"
}

function jsonValueType(value: unknown): string {
  if (value === null) return "null"
  if (Array.isArray(value)) return `array(${value.length})`
  return typeof value
}

function NodeIOCard({ record, defaultOpen }: { record: NodeIORecord; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen)
  const isError = record.status === "error"
  const seconds = (record.duration_ms / 1000).toFixed(2)
  const statusClasses = isError
    ? "bg-red-100 text-red-800 border-red-300"
    : "bg-green-100 text-green-800 border-green-300"
  const statusLabel = isError ? "error" : "ok"
  return (
    <Card className={`border ${isError ? "border-red-300" : "border-slate-200"}`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/40 text-left transition-colors rounded-t-lg"
      >
        {open ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
        <span className="text-sm font-medium flex-1 capitalize">
          {record.node.replace(/_/g, " ")}
        </span>
        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300 font-mono text-[11px]">
          {seconds}s
        </span>
        <span className={`px-2 py-0.5 rounded border font-mono text-[11px] ${statusClasses}`}>
          {statusLabel}
        </span>
      </button>
      {open && (
        <CardContent className="pt-0 space-y-3">
          {isError && record.error && (
            <div className="text-xs bg-red-50 border border-red-300 text-red-800 rounded p-2 font-mono whitespace-pre-wrap">
              {record.error}
            </div>
          )}
          <div>
            <p className="text-[11px] font-semibold text-slate-600 mb-1">Input (state keys fed into this node)</p>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium w-1/2">key</th>
                    <th className="text-left px-2 py-1 font-medium">value (truncated)</th>
                  </tr>
                </thead>
                <tbody>
                  {record.input_keys.length === 0 && (
                    <tr>
                      <td colSpan={2} className="px-2 py-2 text-slate-400 italic">no input keys</td>
                    </tr>
                  )}
                  {record.input_keys.map((k) => {
                    const has = Object.prototype.hasOwnProperty.call(record.output_summary, k)
                    const v = has ? record.output_summary[k] : "(unchanged)"
                    const json = formatJsonTruncated(v)
                    return (
                      <tr key={k} className="border-t">
                        <td className="px-2 py-1 font-mono align-top">{k}</td>
                        <td className="px-2 py-1 font-mono align-top whitespace-pre-wrap break-words">{json}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-600 mb-1">Output (state keys this node wrote)</p>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium w-1/3">key</th>
                    <th className="text-left px-2 py-1 font-medium w-1/4">type</th>
                    <th className="text-left px-2 py-1 font-medium">value (truncated)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(record.output_summary).length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-2 py-2 text-slate-400 italic">no output keys</td>
                    </tr>
                  )}
                  {Object.entries(record.output_summary).map(([k, v]) => (
                    <tr key={k} className="border-t">
                      <td className="px-2 py-1 font-mono align-top">{k}</td>
                      <td className="px-2 py-1 font-mono align-top text-slate-500">{jsonValueType(v)}</td>
                      <td className="px-2 py-1 font-mono align-top whitespace-pre-wrap break-words">{formatJsonTruncated(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

function Tahap4NodeIOCards({ records }: { records: NodeIORecord[] }) {
  if (!records || records.length === 0) return null
  const order: NodeIORecord["node"][] = ["security_analysis", "recommendation_generation", "response_formatter"]
  const byNode = new Map(records.map((r) => [r.node, r]))
  const sorted = order.map((n) => byNode.get(n)).filter((r): r is NodeIORecord => !!r)
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {sorted.map((r) => (
        <NodeIOCard key={r.node} record={r} />
      ))}
    </div>
  )
}

function RunDetailTahap4Section({ nodeIoRecords }: { nodeIoRecords?: NodeIORecord[] }) {
  const { data: nodes, isLoading } = useNodeSpecs([4])
  const hasNodeIO = (nodeIoRecords?.length ?? 0) > 0
  return (
    <Card className="mt-4 border-t-4 border-t-indigo-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-500" />
            Pipeline Nodes (Tahap 4) — Security Evaluation
          </CardTitle>
          <span className="text-[10px] text-gray-500">
            {nodes?.length ?? 0} nodes · click to expand
          </span>
        </div>
        {hasNodeIO ? (
          <p className="text-xs text-muted-foreground mt-1">
            Live I/O trace for Tahap 4 of the v9.3 graph. Each card shows
            the input keys fed to the node and the state keys it wrote.
            Security Analysis normalises SARIF findings + attaches CVSS,
            Recommendation Generation produces actionable fixes,
            Response Formatter builds the unified response + PDF.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground mt-1">
            Reference for Tahap 4 of the v9.3 graph. Security Analysis
            normalises SARIF findings + attaches CVSS, Recommendation
            Generation produces actionable fixes, Response Formatter
            builds the unified response + PDF.
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {hasNodeIO && <Tahap4NodeIOCards records={nodeIoRecords ?? []} />}
        {isLoading && (
          <p className="text-xs text-muted-foreground">Loading node specs…</p>
        )}
        {(nodes ?? []).map((n) => (
          <NodeSpecCard key={n.id} node={n} />
        ))}
      </CardContent>
    </Card>
  )
}

export default function RunDetail() {
  const { projectId, repoId, runId, version } = useParams<{ projectId: string; repoId: string; runId: string; version: string }>()
  return <RunDetailContent key={runId} projectId={projectId!} repoId={repoId!} runId={runId!} version={version!} />
}


// =========================================================================
// Code Scanning alerts card
// =========================================================================
//
// Renders the alerts that the AI service fetched from GitHub's Code
// Scanning API (the primary source of structured security findings).
// Each alert includes file:line, severity, scanner, rule id, CWE,
// OWASP, and a link to the alert on GitHub.

function cvssBand(score: number | null | undefined): "critical" | "high" | "medium" | "low" | null {
  if (typeof score !== "number" || !Number.isFinite(score)) return null
  if (score >= 9.0) return "critical"
  if (score >= 7.0) return "high"
  if (score >= 4.0) return "medium"
  return "low"
}

function cvssBandToBadge(band: "critical" | "high" | "medium" | "low"): {
  label: string
  classes: string
} {
  switch (band) {
    case "critical":
      return { label: "CRITICAL", classes: "bg-red-200 text-red-900 border-red-400" }
    case "high":
      return { label: "HIGH", classes: "bg-red-100 text-red-800 border-red-300" }
    case "medium":
      return { label: "MEDIUM", classes: "bg-amber-100 text-amber-800 border-amber-300" }
    case "low":
      return { label: "LOW", classes: "bg-blue-100 text-blue-800 border-blue-300" }
  }
}

function severityToLabel(severity: string | undefined | null): {
  label: string
  classes: string
} {
  // Legacy path: derive the badge from the scanner's
  // severity label. The CVSS-based path (see `cvssBandToBadge`)
  // is preferred and is what the per-row rendering actually
  // uses; this helper is kept for the summary header chips
  // that don't have a CVSS score yet.
  const s = (severity || "medium").toLowerCase()
  if (s === "critical") {
    return { label: "CRITICAL", classes: "bg-red-200 text-red-900 border-red-400" }
  }
  if (s === "error" || s === "high") {
    return { label: "ERROR", classes: "bg-red-100 text-red-800 border-red-300" }
  }
  if (s === "warning" || s === "medium") {
    return { label: "WARNING", classes: "bg-amber-100 text-amber-800 border-amber-300" }
  }
  return { label: "NOTE", classes: "bg-blue-100 text-blue-800 border-blue-300" }
}

function CodeScanningAlertsCard({
  alerts,
  repositoryFullName,
}: {
  alerts: import("@/hooks/usePipeline").CodeScanningFinding[]
  repositoryFullName?: string
}) {
  // Per-vulnerability AI recommendation. The mutation is
  // cached by react-query on the rule_id + file + line key,
  // so expanding the same alert twice does not re-hit the LLM.
  const recommendMutation = usePerVulnRecommendation()
  // Per-row recommendation state, keyed by
  // `${rule_id}::${file}::${line}` so each alert has its own
  // recommendation card.
  const [recByKey, setRecByKey] = useState<
    Record<
      string,
      {
        loading: boolean
        error?: string
        recommendation?: import("@/hooks/usePipeline").PerVulnRecommendationResult
      }
    >
  >({})
  const fetchRecommendation = async (
    alert: import("@/hooks/usePipeline").CodeScanningFinding,
  ) => {
    const key = `${alert.rule_id ?? ""}::${alert.file_location ?? ""}::${alert.line ?? ""}`
    if (!repositoryFullName || !alert.rule_id) return
    if (recByKey[key]?.recommendation) return // already fetched
    setRecByKey((prev) => ({ ...prev, [key]: { loading: true } }))
    try {
      const result = await recommendMutation.mutateAsync({
        repository_full_name: repositoryFullName,
        vulnerability: {
          rule_id: alert.rule_id,
          severity: alert.severity,
          file_location: alert.file_location,
          line: alert.line,
          title: alert.title,
          code_snippet: alert.code_snippet,
          cvss_score: alert.cvss_score ?? null,
          scanner: alert.scanner,
        },
      })
      setRecByKey((prev) => ({ ...prev, [key]: { loading: false, recommendation: result } }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setRecByKey((prev) => ({ ...prev, [key]: { loading: false, error: msg } }))
    }
  }

  // Group alerts by severity (error first, then warning) so the most
  // important issues appear at the top of the list.
  const sorted = [...alerts].sort((a, b) => {
    const order: Record<string, number> = {
      critical: 0,
      error: 1,
      high: 2,
      warning: 3,
      medium: 4,
      note: 5,
      low: 6,
    }
    const aRank = order[(a.severity || "").toLowerCase()] ?? 99
    const bRank = order[(b.severity || "").toLowerCase()] ?? 99
    return aRank - bRank
  })

  const errorCount = sorted.filter(
    (a) => ["critical", "error", "high"].includes((a.severity || "").toLowerCase()),
  ).length
  const warningCount = sorted.filter((a) =>
    ["warning", "medium"].includes((a.severity || "").toLowerCase()),
  ).length

  // Bab 5.13.3: compute the CVSS sum per severity band so the header
  // can show "35 critical · CVSS 324.0" pills (matches the GitHub
  // Code Scanning UI layout).
  const cvssByBand: Record<string, { count: number; sum: number }> = {
    critical: { count: 0, sum: 0 },
    high: { count: 0, sum: 0 },
    medium: { count: 0, sum: 0 },
    low: { count: 0, sum: 0 },
  }
  let totalCvss = 0
  for (const a of sorted) {
    const band = (a.cvss_severity || "").toLowerCase()
    const score = typeof a.cvss_score === "number" ? a.cvss_score : 0
    if (cvssByBand[band]) {
      cvssByBand[band].count += 1
      cvssByBand[band].sum += score
    }
    totalCvss += score
  }
  const fmtSum = (n: number) => Math.round(n * 10) / 10

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader>
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="text-sm flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-500" />
            Code Scanning Alerts ({sorted.length})
          </CardTitle>
          <div className="flex items-center gap-2 text-xs">
            {cvssByBand.critical.count > 0 && (
              <span className="px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-300 font-mono">
                {cvssByBand.critical.count} critical · CVSS {fmtSum(cvssByBand.critical.sum)}
              </span>
            )}
            {cvssByBand.high.count > 0 && (
              <span className="px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-300 font-mono">
                {cvssByBand.high.count} high · CVSS {fmtSum(cvssByBand.high.sum)}
              </span>
            )}
            {cvssByBand.medium.count > 0 && (
              <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300 font-mono">
                {cvssByBand.medium.count} medium · CVSS {fmtSum(cvssByBand.medium.sum)}
              </span>
            )}
            {cvssByBand.low.count > 0 && (
              <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300 font-mono">
                {cvssByBand.low.count} low · CVSS {fmtSum(cvssByBand.low.sum)}
              </span>
            )}
            {sorted.length > 0 && (
              <span className="px-2 py-0.5 rounded bg-gray-900 text-white border border-gray-700 font-mono">
                Total CVSS {fmtSum(totalCvss)}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Risk levels from CVSS v3.1 (error → critical, warning → high, note → low).
          CVSS sum is the per-bucket total of the per-finding base scores (higher = more risk).
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y">
          {sorted.map((a, i) => {
            // Prefer the CVSS-band badge over the scanner
            // severity label. The CVSS band is the
            // authoritative number — when the scanner says
            // "critical" but the CVSS is 5.4 (medium band)
            // we render the medium band so the colour is
            // consistent with the per-finding CVSS chip in
            // the totals header.
            const band = cvssBand(a.cvss_score)
            const sev = band
              ? cvssBandToBadge(band)
              : severityToLabel(a.severity)
            // Extract a short package label from the file_location
            // (e.g. "package.json:1" or "node_modules/qs/lib/parse.js:42")
            // to mirror the GitHub Code Scanning table layout.
            const packageLabel = a.file_location
              ? a.file_location.split("/")[0] + (
                  a.file_location.includes("package.json") || a.file_location.includes("lock")
                    ? ""
                    : ""
                )
              : ""
            // Build the recommendation text the FE will display
            // when the row is expanded. The backend populates one
            // of `recommendation` / `remediation_recommendation`
            // / `explanation`; we render whichever is present so
            // the user can see the actionable fix inline (matches
            // the GitHub Code Scanning detail panel layout).
            const fixText =
              a.remediation_recommendation ||
              a.recommendation ||
              a.explanation ||
              ""
            const detailKey = `${a.rule_id}-${a.file_location}-${a.line}-${i}`
            const recKey = `${a.rule_id ?? ""}::${a.file_location ?? ""}::${a.line ?? ""}`
            const rec = recByKey[recKey]
            return (
              <details
                key={detailKey}
                className="group hover:bg-gray-50 [&[open]]:bg-blue-50/30"
              >
                <summary className="list-none cursor-pointer px-4 py-2 grid grid-cols-12 gap-3 items-center">
                  <div className="col-span-1 flex items-center gap-1">
                    <ChevronRight className="h-3 w-3 text-gray-400 transition-transform group-open:rotate-90" />
                    <span
                      className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border whitespace-nowrap ${sev.classes}`}
                      title={
                        band
                          ? `CVSS ${a.cvss_score?.toFixed(1)} — ${band} band`
                          : undefined
                      }
                    >
                      {sev.label}
                    </span>
                    <span className="text-[10px] font-mono text-gray-400 ml-0.5">
                      #{i + 1}
                    </span>
                  </div>
                  <div className="col-span-5 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {a.title || a.rule_id}
                    </div>
                    {a.evidence && (
                      <div className="text-[11px] text-gray-500 truncate">
                        {a.evidence}
                      </div>
                    )}
                  </div>
                  <div className="col-span-2 min-w-0 text-right">
                    {a.file_location && (
                      <div
                        className="text-[10px] font-mono text-gray-600 truncate"
                        title={a.file_location}
                      >
                        {a.file_location}
                      </div>
                    )}
                    {packageLabel && packageLabel !== a.file_location && (
                      <div className="text-[10px] font-mono text-gray-400 truncate">
                        {packageLabel}
                      </div>
                    )}
                  </div>
                  <div className="col-span-2 min-w-0 text-right">
                    {a.scanner && (
                      <div className="text-[10px] font-mono text-gray-500 truncate">
                        {a.scanner}
                        {a.scanner_version ? ` v${a.scanner_version}` : ""}
                      </div>
                    )}
                  </div>
                  <div className="col-span-2 min-w-0 text-right">
                    {typeof a.cvss_score === "number" && (
                      <div
                        className="text-[10px] font-mono text-orange-700 truncate"
                        title={a.cvss_vector || "CVSS 3.1 (derived from github-severity)"}
                      >
                        CVSS {a.cvss_score.toFixed(1)}
                        {band ? ` · ${band}` : ""}
                      </div>
                    )}
                  </div>
                </summary>
                <div className="px-4 pb-3 pt-1 border-t border-gray-200 bg-white">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div>
                      <div className="font-semibold text-gray-700 mb-1">
                        {a.rule_id}
                      </div>
                      {a.scanner && (
                        <div className="text-gray-600 mb-1">
                          Detected by <b>{a.scanner}</b>
                          {a.scanner_version ? ` v${a.scanner_version}` : ""}
                          {a.file_location ? ` in ${a.file_location}` : ""}
                          {typeof a.line === "number" ? ` :${a.line}` : ""}
                        </div>
                      )}
                      {a.cwe && (Array.isArray(a.cwe) ? a.cwe.length > 0 : true) && (
                        <div className="text-gray-600 mb-1">
                          <span className="font-mono">
                            {Array.isArray(a.cwe) ? a.cwe.join(", ") : a.cwe}
                          </span>
                        </div>
                      )}
                      {a.owasp && (Array.isArray(a.owasp) ? a.owasp.length > 0 : true) && (
                        <div className="text-gray-600 mb-1">
                          OWASP: <span className="font-mono">
                            {Array.isArray(a.owasp) ? a.owasp.join(", ") : a.owasp}
                          </span>
                        </div>
                      )}
                      {typeof a.cvss_score === "number" && (
                        <div className="text-gray-600 mb-1">
                          CVSS: <b>{a.cvss_score.toFixed(1)}</b>
                          {band ? ` (${band})` : ""}
                          {a.cvss_vector ? ` · ${a.cvss_vector}` : ""}
                        </div>
                      )}
                      {a.scanner_url && (
                        <a
                          href={a.scanner_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-blue-600 hover:underline"
                        >
                          View on GitHub →
                        </a>
                      )}
                    </div>
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="font-semibold text-gray-700">
                          Recommendation
                        </div>
                        {repositoryFullName && a.rule_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 px-2 text-[10px]"
                            disabled={rec?.loading}
                            onClick={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              void fetchRecommendation(a)
                            }}
                          >
                            {rec?.loading ? (
                              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            ) : rec?.recommendation ? (
                              <CheckCircle2 className="h-3 w-3 mr-1 text-green-600" />
                            ) : (
                              <Sparkles className="h-3 w-3 mr-1 text-purple-600" />
                            )}
                            {rec?.loading
                              ? "Generating…"
                              : rec?.recommendation
                              ? "Regenerate"
                              : "Get AI fix"}
                          </Button>
                        )}
                      </div>
                      {rec?.error ? (
                        <p className="text-red-600 italic">
                          Failed to generate: {rec.error}
                        </p>
                      ) : rec?.recommendation ? (
                        <div className="space-y-2">
                          <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                            {rec.recommendation.recommendation}
                          </p>
                          {rec.recommendation.code_changes &&
                            rec.recommendation.code_changes.length > 0 && (
                              <div className="space-y-2">
                                {rec.recommendation.code_changes.map(
                                  (cc, idx) => (
                                    <div
                                      key={idx}
                                      className="border border-gray-200 rounded p-2 bg-gray-50"
                                    >
                                      {cc.description && (
                                        <div className="text-[11px] text-gray-600 mb-1">
                                          {cc.description}
                                        </div>
                                      )}
                                      {cc.before && (
                                        <pre className="text-[10px] bg-red-50 border border-red-200 rounded p-1 overflow-x-auto mb-1">
                                          <code>- {cc.before}</code>
                                        </pre>
                                      )}
                                      {cc.after && (
                                        <pre className="text-[10px] bg-green-50 border border-green-200 rounded p-1 overflow-x-auto">
                                          <code>+ {cc.after}</code>
                                        </pre>
                                      )}
                                    </div>
                                  ),
                                )}
                              </div>
                            )}
                        </div>
                      ) : fixText ? (
                        <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                          {fixText}
                        </p>
                      ) : (
                        <p className="text-gray-400 italic">
                          No recommendation available yet. Click{" "}
                          <b>Get AI fix</b> to generate a context-aware fix for
                          this vulnerability.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </details>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function RunDetailContent({ projectId, repoId, runId, version }: { projectId: string; repoId: string; runId: string; version: string }) {
  const { data: run, isLoading } = useRunDetail(runId)
  const { data: savedAnalysis } = useRunAnalysis(runId)
  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)
  // Reviewer feedback: a "Refresh Analysis" button forces the AI
  // agent to re-evaluate the workflow logs. Useful when the saved
  // analysis is empty (e.g. logs were not yet uploaded when the
  // run was first synced) or when the user wants the latest
  // findings. The `force=true` flag bypasses the saved-analysis
  // cache in the AI service.
  //
  // IMPORTANT: The AI service and the Go backend use separate
  // databases, so the "saved" analysis fetched via the Go
  // `GetAnalysis` endpoint does NOT see the log-derived findings
  // saved by the AI service. To work around this, the refresh
  // path calls the AI service directly, captures its response,
  // and renders that response in the dashboard until the next
  // page load. The saved analysis (`savedAnalysis`) is still used
  // for the initial render and for risk/compliance scores.
  const analyzeMutation = usePipelineAnalyze()
  const queryClient = useQueryClient()
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null)
  const [pdfMsg, setPdfMsg] = useState<string | null>(null)
  const [showRawLog, setShowRawLog] = useState(false)
  const pdfMutation = useGeneratePdf()
  // Tahap-1 / Tahap-2 pipeline data (detected technologies,
  // architecture, deployment, domain, security coverages,
  // pipeline augmentations, generated workflow). The AI
  // service returns this from `POST /ai/pipeline/repo/pipeline`.
  // We cache the result in state so the PDF generator can
  // pull detected_technologies / security_coverages /
  // pipeline_augmentations / generated_stages without the
  // user having to click anything.
  const repoPipelineMutation = useRepoPipeline()
  const [pipelineResult, setPipelineResult] = useState<RepoPipelineResult | null>(null)
  const [pipelineLoading, setPipelineLoading] = useState(false)
  // The most recent AI response (with log-derived findings) is
  // held in this state so the Security Findings table can render
  // it immediately without waiting for a Go-side re-sync.
  const [liveAnalysis, setLiveAnalysis] = useState<{
    findings: Finding[]
    code_scanning_alerts?: import("@/hooks/usePipeline").CodeScanningFinding[]
    severity_breakdown: Record<string, number>
    log_extraction: { source: string; lines_scanned: number; security_findings_count: number }
    node_io?: NodeIORecord[]
  } | null>(null)
  // Fetch Tahap-1 / Tahap-2 pipeline data once per repository
  // so the PDF report has the detected technologies,
  // architecture, deployment, domain, security coverages,
  // pipeline augmentations, generated stages, and generated
  // workflow YAML. The AI service is the source of truth for
  // all of these — the Go backend's `PipelineRun` schema
  // does not carry them.
  useEffect(() => {
    let cancelled = false
    const fetchPipeline = async () => {
      if (!repo?.full_name || pipelineResult || pipelineLoading) return
      setPipelineLoading(true)
      try {
        const result = await repoPipelineMutation.mutateAsync({
          repository_full_name: repo.full_name,
        })
        if (!cancelled) {
          setPipelineResult(result)
        }
      } catch (e) {
        // Silently fall back: the PDF will simply show
        // placeholders for the missing fields. The user can
        // still see all 52 findings, the CVSS breakdown,
        // and the per-finding table — those come from the
        // analyzer, not the pipeline.
        console.warn("[RunDetail] failed to fetch pipeline data:", e)
      } finally {
        if (!cancelled) setPipelineLoading(false)
      }
    }
    void fetchPipeline()
    return () => {
      cancelled = true
    }
    // We intentionally only refetch when the repository
    // changes. Re-fetching on every render would be wasteful
    // (the AI service runs an LLM call on each invocation).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo?.full_name])
  const handleRefreshAnalysis = async () => {
    if (!repo?.full_name) {
      setRefreshMsg("Repository not loaded yet")
      return
    }
    setRefreshMsg(null)
    // github_run_id is 0 when the workflow file has not been
    // deployed to GitHub yet (no real GitHub Actions run). In
    // that case the AI service still runs a best-effort analysis
    // on Code Scanning alerts and the repository's source code.
    const targetRunId = run?.github_run_id ?? Number(runId)
    try {
      const result = await analyzeMutation.mutateAsync({
        repository_id: repo.full_name,
        run_id: targetRunId,
        force: true,
      })
      // The AI service response includes the log-derived findings.
      // Capture it for immediate display; the Go-side saved
      // analysis is a different database row and will not be
      // updated until the next sync.
      // Reviewer feedback: log heuristic may extract many
      // findings, but the graph nodes (security_analyzer,
      // risk_assessor) can filter them out. We therefore fall back
      // to `log_security_findings` (raw log findings) when the
      // graph-level findings array is empty but the log extractor
      // found something.
      const graphFindings = ((result as { findings?: Finding[] }).findings ?? []) as Finding[]
      const rawLogFindings = ((result as { log_security_findings?: Finding[] }).log_security_findings ?? []) as Finding[]
      // Code Scanning alerts (primary source) — fetched by the AI
      // service from the GitHub Code Scanning API. These are the
      // authoritative SARIF-based findings.
      const codeScanningAlerts = ((result as { code_scanning_alerts?: import("@/hooks/usePipeline").CodeScanningFinding[] }).code_scanning_alerts ?? []) as import("@/hooks/usePipeline").CodeScanningFinding[]
      // Merge strategy: prefer Code Scanning alerts (the
      // authoritative SARIF-based findings from GitHub's Code
      // Scanning API) as the primary source, then graph findings
      // (which are usually a filtered subset), then log-derived
      // findings. The user explicitly asked for Code Scanning to
      // be the primary source so the dashboard is consistent with
      // what GitHub shows under the Security tab.
      const codeScanningAsFindings = (codeScanningAlerts ?? []).map(
        (a): Finding => ({
          type: a.rule_id,
          title: a.title,
          severity: a.severity,
          file_location: a.file_location,
          line: a.line,
          file: a.file_location,
          code_snippet: a.code_snippet,
          evidence: a.evidence,
          explanation: a.explanation,
          recommendation: a.recommendation,
          remediation_recommendation: a.remediation_recommendation,
          source_tool: a.source_tool ?? a.scanner,
          scanner: a.scanner,
          scanner_version: a.scanner_version,
          rule_id: a.rule_id,
          cwe: a.cwe,
          owasp: a.owasp,
          cvss_score: a.cvss_score,
          cvss_vector: a.cvss_vector,
          cvss_severity: a.cvss_severity,
          security_coverage: a.security_coverage,
          scanner_url: a.scanner_url,
          _raw: a._raw,
        }),
      )
      const seen = new Set<string>()
      const findings: Finding[] = []
      for (const f of [
        ...codeScanningAsFindings,
        ...graphFindings,
        ...rawLogFindings,
      ]) {
        if (!f) continue
        const key = `${f.rule_id ?? f.type ?? f.title ?? ""}::${f.file_location ?? f.file ?? ""}::${f.line ?? ""}`
        if (seen.has(key)) continue
        seen.add(key)
        findings.push(f)
      }
      const sev = (result as { severity_breakdown?: Record<string, number> }).severity_breakdown ?? {}
      const le = (result as { log_extraction?: { source: string; lines_scanned: number; security_findings_count: number } }).log_extraction ?? {
        source: "unknown", lines_scanned: 0, security_findings_count: findings.length,
      }
      const nodeIO = ((result as { node_io?: NodeIORecord[] }).node_io ?? []) as NodeIORecord[]
      console.log("[RunDetail] analyze response:", {
        graph_findings_count: graphFindings.length,
        log_findings_count: rawLogFindings.length,
        code_scanning_alerts_count: codeScanningAlerts.length,
        using: "code_scanning_alerts (primary) + graph + log (deduped)",
        final_findings: findings.length,
        severity_breakdown: sev,
        log_extraction: le,
      })
      setLiveAnalysis({
        findings,
        code_scanning_alerts: codeScanningAlerts,
        severity_breakdown: sev,
        log_extraction: le,
        node_io: nodeIO,
      })
      queryClient.invalidateQueries({ queryKey: ["run-analysis", runId] })
      // Compose a user-facing summary message that highlights the
      // primary source (Code Scanning alerts) so reviewers know
      // what is being rendered. The new deduped union is now
      // primary, with code_scanning + graph + log as the source
      // breakdown shown in the message.
      if (findings.length > 0) {
        const parts: string[] = []
        if (codeScanningAlerts.length > 0) {
          parts.push(`${codeScanningAlerts.length} Code Scanning`)
        }
        if (graphFindings.length > 0 && graphFindings !== codeScanningAsFindings) {
          parts.push(`${graphFindings.length} graph`)
        }
        if (rawLogFindings.length > 0) {
          parts.push(`${rawLogFindings.length} log-derived`)
        }
        const source = parts.length > 0 ? ` (${parts.join(" + ")})` : ""
        setRefreshMsg(
          `Refresh done: ${findings.length} finding(s) extracted${source}.`
        )
      } else if (le.source === "conclusions_only") {
        setRefreshMsg(
          `Refresh done but logs were not fetched (source=${le.source}). ` +
          `Check the GitHub token has 'actions: read' scope and that the run logs are still available.`
        )
      } else if (le.security_findings_count === 0) {
        setRefreshMsg(
          `Refresh done: ${le.lines_scanned} log lines scanned, 0 security patterns matched.`
        )
      } else {
        setRefreshMsg(
          `Refresh done: ${le.security_findings_count} log-derived finding(s) extracted from ${le.lines_scanned} lines.`
        )
      }
    } catch (e: unknown) {
      const err = e as {
        response?: { data?: { error?: string }; status?: number }
        code?: string
        message?: string
      }
      // Surface the most actionable cause. Axios uses different
      // `code` values for the various failure modes (the generic
      // "Network Error" string the browser emits when CORS or
      // preflight misbehaves is the most common).
      let detail = err?.response?.data?.error
      if (!detail) {
        if (err?.code === "ERR_NETWORK") {
          detail =
            "Network error — the AI service may be down or unreachable. " +
            "Check that ai-service:8000 is up and nginx is proxying /ai/."
        } else if (err?.code === "ECONNABORTED") {
          detail = "Timeout — analysis took longer than the client allowed."
        } else if (err?.response?.status) {
          detail = `HTTP ${err.response.status} — ${
            err?.response?.data?.error || err?.message || "unknown"
          }`
        } else {
          detail = err?.message || "unknown error"
        }
      }
      console.error("[Refresh Analysis] failed:", err)
      setRefreshMsg(`Refresh failed: ${detail}`)
    }
  }

  // Generate PDF Report: bundle the analysis state into a payload,
  // post to the AI service, receive base64-encoded PDF, and trigger
  // a browser download. The AI service composes the cover page,
  // security section, and the per-finding CVSS table.
  //
  // IMPORTANT: the `run` object (loaded from the Go backend) only
  // carries metadata — it does NOT have the findings list, code
  // scanning alerts, security coverages, or generated pipeline
  // stages. Those live in the AI service's analysis (either the
  // saved one or the live one captured after a Refresh click).
  // The previous version read everything from `run`, which made
  // the PDF a blank template.
  const handleGeneratePdf = async () => {
    if (!repo?.full_name) {
      setPdfMsg("Repository is not loaded yet")
      return
    }
    if (!run?.id) {
      setPdfMsg("Run id is not yet available — try again after sync")
      return
    }
    const repoFullName = repo.full_name
    setPdfMsg(null)
    try {
      // Prefer the live analysis (the one captured when the
      // user clicked Refresh Analysis) over the saved one, so
      // the PDF reflects whatever the user most recently
      // saw on the dashboard. Fall back to the saved
      // analysis when no refresh has been performed.
      const analysis = (liveAnalysis ?? savedAnalysis) as
        | (typeof savedAnalysis & {
            code_scanning_alerts?: unknown[]
            findings?: unknown[]
            severity_breakdown?: Record<string, number>
            risk_score?: number | null
            risk_level?: string
            compliance_score?: number | null
          })
        | null
      const codeScanningAlerts = (analysis?.code_scanning_alerts ??
        (run as any).code_scanning_alerts ??
        []) as unknown[]
      const findings = (analysis?.findings ??
        (run as any).findings ??
        []) as unknown[]
      const severityBreakdown = (analysis?.severity_breakdown ??
        (run as any).severity_breakdown ??
        {}) as Record<string, number>
      const riskScore = analysis?.risk_score ?? (run as any).risk_score ?? null
      const riskLevel = analysis?.risk_level ?? (run as any).risk_level ?? null
      const complianceScore = analysis?.compliance_score ??
        (run as any).compliance_score ?? null
      const recommendations = (analysis?.recommendations ??
        (run as any).recommendations ??
        []) as unknown[]
      const summary = analysis?.summary ?? ""
      // Pipeline-side fields. The Go `PipelineRun` schema does
      // NOT carry these (it only has the GitHub Actions
      // metadata: id, status, jobs, etc.). The authoritative
      // source is the AI service's Tahap-1/Tahap-2 output
      // from `POST /ai/pipeline/repo/pipeline`, which we
      // fetched on mount into `pipelineResult`. We try the
      // analysis first, then the pipeline result, then the
      // run, then fall back to a sensible default so the
      // PDF never reads "—".
      const detectedTechnologies =
        (analysis as any)?.analysis?.technologies ??
        (analysis as any)?.detected_technologies ??
        pipelineResult?.detected_technologies ??
        (run as any).detected_technologies ?? {}
      const detectedArchitecture =
        (analysis as any)?.analysis?.architecture ??
        (analysis as any)?.detected_architecture ??
        pipelineResult?.detected_architecture ??
        (run as any).detected_architecture ?? {}
      const detectedDeployment =
        (analysis as any)?.analysis?.deployment ??
        (analysis as any)?.detected_deployment ??
        pipelineResult?.detected_deployment ??
        (run as any).detected_deployment ?? {}
      const detectedDomain =
        (analysis as any)?.analysis?.domain ??
        (analysis as any)?.detected_domain ??
        pipelineResult?.detected_domain ??
        (run as any).detected_domain ??
        "general"
      const pipelineAnalysis = (analysis as any)?.analysis ??
        pipelineResult ?? (run as any)
      const detectedArchitectureType =
        pipelineAnalysis?.detected_architecture_type ??
        pipelineAnalysis?.architecture?.architecture_type ??
        "monolithic"
      const recommendedDeploymentTarget =
        pipelineAnalysis?.recommended_deployment_target ??
        pipelineAnalysis?.deployment?.recommended_target ??
        null
      const domainSubType =
        pipelineAnalysis?.domain_sub_type ??
        pipelineAnalysis?.domain?.sub_type ??
        "none"
      const domainConfidence =
        pipelineAnalysis?.domain_confidence ??
        pipelineAnalysis?.domain?.confidence ??
        0.0
      const domainThreats =
        pipelineAnalysis?.domain_threats ??
        pipelineAnalysis?.domain?.threats ??
        []
      const features = pipelineAnalysis?.features ?? []
      const securityCoverages =
        (analysis as any)?.security_coverages ??
        pipelineResult?.security_coverages ?? []
      const pipelineAugmentations =
        (analysis as any)?.pipeline_augmentations ??
        pipelineResult?.pipeline_augmentations ?? []
      const generatedStages =
        (analysis as any)?.generated_stages ??
        pipelineResult?.generated_stages ?? []
      const generatedWorkflow =
        (analysis as any)?.generated_workflow ??
        pipelineResult?.generated_workflow ?? ""
      const aiGeneratedRules =
        (analysis as any)?.ai_generated_rules ??
        pipelineResult?.ai_generated_rules ?? []
      const jobDesigns =
        (analysis as any)?.job_designs ??
        pipelineResult?.job_designs ?? []
      const payload = {
        repository_full_name: repoFullName,
        run_id: run.id,
        repository_description: repo?.description || "",
        detected_technologies: detectedTechnologies,
        detected_architecture: detectedArchitecture,
        detected_architecture_type: detectedArchitectureType,
        detected_deployment: detectedDeployment,
        recommended_deployment_target: recommendedDeploymentTarget,
        detected_domain: detectedDomain,
        domain_sub_type: domainSubType,
        domain_confidence: domainConfidence,
        domain_threats: domainThreats,
        features: features,
        security_coverages: securityCoverages,
        ai_generated_rules: aiGeneratedRules,
        pipeline_augmentations: pipelineAugmentations,
        job_designs: jobDesigns,
        generated_workflow: generatedWorkflow,
        generated_stages: generatedStages,
        validation_passed: (run as any).validation_passed ?? true,
        validation_errors: (run as any).validation_errors ?? [],
        validation_warnings: (run as any).validation_warnings ?? [],
        findings: findings,
        code_scanning_alerts: codeScanningAlerts,
        risk_score: riskScore,
        risk_level: riskLevel,
        security_posture: (run as any).security_posture ?? null,
        compliance_score: complianceScore,
        security_coverage_score:
          (analysis as any)?.security_coverage_score ?? null,
        severity_breakdown: severityBreakdown,
        recommendations: recommendations,
        summary: summary,
      }
      const result = await pdfMutation.mutateAsync({
        repoId: repoFullName,
        runId: run.id,
        payload,
      })
      const bytes = atob(result.content_base64 || "")
      const len = bytes.length
      const arr = new Uint8Array(len)
      for (let i = 0; i < len; i++) arr[i] = bytes.charCodeAt(i)
      const blob = new Blob([arr], { type: result.content_type || "application/pdf" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = result.filename || "ai-devsecops-report.pdf"
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setPdfMsg(`PDF generated (${(result.size / 1024).toFixed(1)} KB) — download started`)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setPdfMsg(
        `PDF failed: ${err?.response?.data?.detail ?? err?.message ?? "unknown error"}`,
      )
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Run not found</p>
      </div>
    )
  }

  const jobs: PipelineJob[] = safeJsonParse<PipelineJob[]>(run.jobs, [])

  const failingJobs = jobs.filter((j) => j.conclusion === "failure" || j.conclusion === "cancelled" || j.conclusion === "skipped")
  const successfulJobs = jobs.filter((j) => j.conclusion === "success")
  const pendingJobs = jobs.filter((j) => !j.conclusion || j.status === "running" || j.status === "queued" || j.status === "pending")
  const otherJobs = jobs.filter((j) => !failingJobs.includes(j) && !successfulJobs.includes(j) && !pendingJobs.includes(j))

  const totalChecks = jobs.length
  const passedCount = successfulJobs.length
  const failedCount = failingJobs.length
  const pendingCount = pendingJobs.length
  const allPassed = failedCount === 0 && pendingCount === 0 && totalChecks > 0
  const someFailing = failedCount > 0

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` },
        { label: `Run #${run.run_number}` },
      ]}>
        {run.status === "running" || run.status === "queued" ? (
          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
        ) : run.conclusion === "success" ? (
          <CheckCircle2 className="h-4 w-4 text-green-500" />
        ) : run.conclusion === "failure" ? (
          <XCircle className="h-4 w-4 text-red-500" />
        ) : null}
      </Header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {jobs.length > 0 && (
          <Card className={allPassed ? "border-green-300" : someFailing ? "border-red-300" : "border-blue-300"}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                {allPassed ? (
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                ) : someFailing ? (
                  <XCircle className="h-8 w-8 text-red-500" />
                ) : (
                  <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
                )}
                <div>
                  <h2 className="text-lg font-semibold">
                    {allPassed && "All checks passed"}
                    {someFailing && "Some checks were not successful"}
                    {!allPassed && !someFailing && pendingCount > 0 && "Some checks are still running"}
                    {!allPassed && !someFailing && pendingCount === 0 && totalChecks === 0 && "No checks completed yet"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {failedCount} failing, {passedCount} successful{totalChecks > 0 ? `, ${totalChecks} total checks` : ""}
                    {pendingCount > 0 && ` — ${pendingCount} still running`}
                  </p>
                </div>
                <div className="ml-auto flex items-center gap-2">
                  {run.duration_seconds && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-4 w-4" />
                      <span>{getDuration(run.duration_seconds)}</span>
                    </div>
                  )}
                  {run.html_url && (
                    <a href={run.html_url} target="_blank" rel="noopener noreferrer">
                      <Button size="sm" variant="outline">
                        <ExternalLink className="h-4 w-4 mr-1" /> View on GitHub
                      </Button>
                    </a>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {run.status === "running" || run.status === "queued" || run.status === "pending" ? (
          <Card>
            <CardContent className="py-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
              <h3 className="text-lg font-medium">Pipeline is {run.status}</h3>
              <p className="text-sm text-muted-foreground mt-1">Waiting for jobs to complete...</p>
            </CardContent>
          </Card>
        ) : null}

        <div className="space-y-2">
          {failingJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-2">
                <XCircle className="h-4 w-4" /> Failing checks
              </h3>
              <div className="space-y-2">
                {failingJobs.map((job) => (
                  <JobCard key={job.id} job={job} repoId={repoId} version={version} runId={runId} />
                ))}
              </div>
            </div>
          )}

          {pendingJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-blue-700 mb-2 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Running checks
              </h3>
              <div className="space-y-2">
                {pendingJobs.map((job) => (
                  <JobCard key={job.id} job={job} repoId={repoId} version={version} runId={runId} />
                ))}
              </div>
            </div>
          )}

          {successfulJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" /> Successful checks
              </h3>
              <div className="space-y-2">
                {successfulJobs.map((job) => (
                  <JobCard key={job.id} job={job} repoId={repoId} version={version} runId={runId} />
                ))}
              </div>
            </div>
          )}

          {otherJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> Other checks
              </h3>
              <div className="space-y-2">
                {otherJobs.map((job) => (
                  <JobCard key={job.id} job={job} repoId={repoId} version={version} runId={runId} />
                ))}
              </div>
            </div>
          )}

          {jobs.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                {run.status === "running" ? "Waiting for job data..." : "No job data available"}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Reviewer feedback: a "Refresh Analysis" card gives the user
            a way to force the AI agent to re-evaluate the workflow
            logs. The card is shown whenever an analysis row exists
            (even if it has zero findings) so the user can recover
            from a transient log-fetch failure during the initial
            sync. */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">Security analysis</p>
                <p className="text-xs text-muted-foreground">
                  Findings below are extracted from the workflow log
                  (npm audit, Trivy, Gitleaks, Semgrep). If the table
                  is empty, the analysis ran before the logs were
                  available — click Refresh to re-evaluate.
                </p>
                {refreshMsg && (
                  <p
                    className={`text-xs mt-1 ${
                      refreshMsg.startsWith("Refresh failed")
                        ? "text-red-600"
                        : "text-green-700"
                    }`}
                  >
                    {refreshMsg}
                  </p>
                )}
                {pdfMsg && (
                  <p className="text-xs mt-1 text-blue-700">{pdfMsg}</p>
                )}
              </div>
              <Button
                size="sm"
                variant="default"
                className="bg-blue-600 hover:bg-blue-700"
                onClick={handleRefreshAnalysis}
                disabled={analyzeMutation.isPending}
              >
                {analyzeMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-1" />
                )}
                {analyzeMutation.isPending ? "Refreshing…" : "Refresh Analysis"}
              </Button>
              <Button
                size="sm"
                variant="default"
                className="bg-purple-600 hover:bg-purple-700"
                onClick={handleGeneratePdf}
                disabled={pdfMutation.isPending}
              >
                {pdfMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <FileText className="h-4 w-4 mr-1" />
                )}
                {pdfMutation.isPending ? "Generating…" : "Generate PDF Report"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowRawLog((v) => !v)}
              >
                <FileText className="h-4 w-4 mr-1" />
                {showRawLog ? "Hide Raw Output" : "View Raw Output"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Reviewer feedback: a "Show raw log" card lets the user
            verify the AI agent's findings against the actual
            workflow log text. The log is fetched from GitHub on
            demand and displayed in a scrollable terminal-style
            block. The text is the same log the AI agent scans. */}
        {showRawLog && (
          <RawLogCard
            projectId={projectId}
            repoId={repoId}
            version={version}
            runId={runId}
          />
        )}

        {savedAnalysis && (() => {
          // Reviewer feedback: prefer the live (refreshed) findings
          // over the Go-side saved findings when the user has just
          // clicked Refresh Analysis. The two databases are
          // separate, so the AI service's findings only reach the
          // UI through `liveAnalysis`.
          const findings: Array<{ source_tool?: string; scanner?: string; type?: string; severity?: string; file?: string; file_location?: string; line?: number; code_snippet?: string; explanation?: string; evidence?: string; recommendation?: string; remediation_recommendation?: string; title?: string }> =
            liveAnalysis?.findings ?? savedAnalysis.findings ?? []
          const severity: Record<string, number> =
            liveAnalysis?.severity_breakdown ?? savedAnalysis.severity_breakdown ?? {}
          const recommendations: Finding[] = savedAnalysis.recommendations ?? []
          const nodeIoRecords: NodeIORecord[] =
            (liveAnalysis?.node_io && liveAnalysis.node_io.length > 0
              ? liveAnalysis.node_io
              : ((savedAnalysis as { node_io?: NodeIORecord[] } | undefined)?.node_io ?? [])) as NodeIORecord[]

          const severityColors: Record<string, string> = {
            critical: "bg-red-100 text-red-800 border-red-300",
            high: "bg-orange-100 text-orange-800 border-orange-300",
            medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
            low: "bg-blue-100 text-blue-800 border-blue-300",
          }

          type SeverityKey = "critical" | "high" | "medium" | "low"

          // Bab 5.13.3: severity is bucketed by the CVSS base score,
          // not by the raw GitHub "warning|error|note" string. This
          // makes the breakdown match the industry-standard CVSS v3.1
          // bands (critical >= 9.0, high >= 7.0, medium >= 4.0, low < 4.0)
          // regardless of which scanner produced the finding.
          const cvssBands: Record<SeverityKey, { count: number; sum: number }> = {
            critical: { count: 0, sum: 0 },
            high: { count: 0, sum: 0 },
            medium: { count: 0, sum: 0 },
            low: { count: 0, sum: 0 },
          }
          let totalCvss = 0
          // Bucket anchors: representative CVSS score used when a
          // finding carries a severity band but no numeric score
          // (e.g. log-derived npm audit output). Keeps the
          // Severity Breakdown card in sync with the Security
          // Findings list even when the deterministic CVSS lookup
          // has not run yet for a particular rule.
          const bandAnchor: Record<SeverityKey, number> = {
            critical: 9.5,
            high: 7.5,
            medium: 5.0,
            low: 2.0,
          }
          for (const f of findings as Array<{ cvss_score?: number; cvss_severity?: string; severity?: string }>) {
            const rawScore = typeof f.cvss_score === "number" ? f.cvss_score : null
            const sevStr = (f.cvss_severity || f.severity || "").toLowerCase()
            // Prefer cvss_severity (already banded by the 3-tier
            // CVSS lookup); fall back to deriving the band from
            // the raw CVSS score for findings that only carry a
            // score; fall back to the severity string for log
            // findings that have neither.
            const band = (f.cvss_severity || "").toLowerCase() as SeverityKey
            const derivedBand: SeverityKey =
              band in cvssBands
                ? band
                : rawScore != null
                  ? rawScore >= 9.0
                    ? "critical"
                    : rawScore >= 7.0
                      ? "high"
                      : rawScore >= 4.0
                        ? "medium"
                        : "low"
                  : sevStr.includes("critical") || sevStr === "error"
                    ? "critical"
                    : sevStr.includes("high") || sevStr === "warning"
                      ? "high"
                      : sevStr.includes("medium") || sevStr === "note"
                        ? "medium"
                        : sevStr.includes("low") || sevStr === "info"
                          ? "low"
                          : "medium"
            const effectiveScore = rawScore ?? bandAnchor[derivedBand]
            cvssBands[derivedBand].count += 1
            cvssBands[derivedBand].sum += effectiveScore
            totalCvss += effectiveScore
          }
          const cvssBandLabel: Record<SeverityKey, string> = {
            critical: "Critical",
            high: "High",
            medium: "Medium",
            low: "Low",
          }
          const cvssBandColors: Record<SeverityKey, { bg: string; text: string; border: string }> = {
            critical: { bg: "bg-red-100", text: "text-red-800", border: "border-red-300" },
            high: { bg: "bg-orange-100", text: "text-orange-800", border: "border-orange-300" },
            medium: { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300" },
            low: { bg: "bg-blue-100", text: "text-blue-800", border: "border-blue-300" },
          }

          return (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Total CVSS", value: totalCvss > 0 ? totalCvss : null, invertBar: false, suffix: "", useBand: false },
                  { label: "Risk Score", value: savedAnalysis.risk_score, invertBar: true, suffix: "", useBand: false },
                  { label: "Compliance", value: savedAnalysis.compliance_score, invertBar: false, suffix: "", useBand: false },
                  { label: "Security Coverage", value: savedAnalysis.security_coverage_score, invertBar: false, suffix: "", useBand: false },
                ].map((m) => (
                  <Card key={m.label}>
                    <CardContent className="pt-4 pb-4">
                      <div className="flex items-center gap-3">
                        <span className={`text-2xl font-bold ${
                          m.value == null ? "" :
                          m.invertBar
                            ? m.value >= 75 ? "text-red-600" : m.value >= 40 ? "text-yellow-600" : "text-green-600"
                            : m.value >= 75 ? "text-green-600" : m.value >= 40 ? "text-yellow-600" : "text-red-600"
                        }`}>
                          {m.value != null
                            ? (m.label === "Total CVSS"
                                ? m.value.toFixed(1)
                                : m.value.toFixed(1))
                            : "-"}
                        </span>
                        <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${
                            m.value == null ? "bg-gray-300" :
                            m.invertBar
                              ? m.value < 40 ? "bg-green-500" : m.value < 75 ? "bg-yellow-500" : "bg-red-500"
                              : m.value < 40 ? "bg-red-500" : m.value < 75 ? "bg-yellow-500" : "bg-green-500"
                          }`} style={{ width: `${Math.min(m.value ?? 0, 100)}%` }} />
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{m.label}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Severity Breakdown by CVSS band (Bab 5.13.3).
                  The bucket counts are derived from cvss_severity
                  (preferred) or the raw CVSS score (fallback), so
                  the same alert can be counted differently from its
                  GitHub Code Scanning severity string. */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">
                    Severity Breakdown
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Buckets derived from the CVSS v3.1 base score (critical
                    &ge; 9.0, high &ge; 7.0, medium &ge; 4.0, low &lt; 4.0).
                    Not the GitHub Code Scanning severity string.
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {(["critical", "high", "medium", "low"] as SeverityKey[]).map((b) => (
                      <div
                        key={b}
                        className={`rounded-md border ${cvssBandColors[b].border} ${cvssBandColors[b].bg} px-3 py-3`}
                      >
                        <div className={`text-[10px] font-bold uppercase ${cvssBandColors[b].text}`}>
                          {cvssBandLabel[b]}
                        </div>
                        <div className={`text-2xl font-bold ${cvssBandColors[b].text}`}>
                          {cvssBands[b].count}
                        </div>
                        <div className={`text-[10px] ${cvssBandColors[b].text} font-mono opacity-75`}>
                          CVSS Σ {cvssBands[b].sum.toFixed(1)}
                        </div>
                      </div>
                     ))}
                  </div>
                </CardContent>
              </Card>

              {savedAnalysis.ai_explanation && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Shield className="h-4 w-4" /> AI Analysis
                      </CardTitle>
                      <Link
                        to={`/projects/${projectId}/repos/${repoId}/pipelines/${version}/runs/${runId}/analysis`}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View Full Analysis →
                      </Link>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{savedAnalysis.ai_explanation}</p>
                  </CardContent>
                </Card>
              )}

              {liveAnalysis?.code_scanning_alerts && liveAnalysis.code_scanning_alerts.length > 0 ? (
                <CodeScanningAlertsCard
                  alerts={liveAnalysis.code_scanning_alerts}
                  repositoryFullName={repo?.full_name}
                />
              ) : savedAnalysis && (savedAnalysis.code_scanning_alerts?.length ?? 0) > 0 ? (
                <CodeScanningAlertsCard
                  alerts={savedAnalysis.code_scanning_alerts!}
                  repositoryFullName={repo?.full_name}
                />
              ) : null}

              {(() => {
                // Only show the "Other Security Findings" card
                // when there are findings that did NOT make it
                // into the Code Scanning Alerts list. The Code
                // Scanning card is the primary source of
                // truth; this fallback surfaces the AI log /
                // graph-derived findings that are unique to
                // the analyzer (e.g. SARIF parse errors,
                // configuration findings, log heuristics that
                // GitHub did not surface). When the two are
                // perfectly aligned, this card is hidden.
                const alertKeys = new Set(
                  (
                    liveAnalysis?.code_scanning_alerts ??
                    savedAnalysis?.code_scanning_alerts ??
                    []
                  ).map(
                    (a) =>
                      `${a.rule_id ?? ""}::${a.file_location ?? ""}::${a.line ?? ""}`,
                  ),
                )
                const otherFindings = findings.filter((f) => {
                  const key = `${(f as { rule_id?: string }).rule_id ?? (f as { type?: string }).type ?? ""}::${(f as { file_location?: string }).file_location ?? (f as { file?: string }).file ?? ""}::${(f as { line?: number }).line ?? ""}`
                  return !alertKeys.has(key)
                })
                if (otherFindings.length === 0) return null
                return (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <FileWarning className="h-4 w-4 text-red-500" />
                        Other Security Findings ({otherFindings.length})
                      </CardTitle>
                      <p className="text-[11px] text-muted-foreground mt-1">
                        Findings produced by the AI log/graph analyser that
                        did not appear in the Code Scanning list. Most often
                        these are configuration issues, log heuristics, or
                        SARIF parse warnings.
                      </p>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="divide-y">
                        {otherFindings.map((f, i) => {
                          const rawFile = (f.file_location || f.file || "") as string
                          const segs = rawFile.split("/")
                          let packageLabel = ""
                          if (rawFile.includes("node_modules/")) {
                            const idx = segs.findIndex((s) => s === "node_modules")
                            if (idx >= 0 && idx + 1 < segs.length) {
                              packageLabel = segs[idx + 1] ?? ""
                            }
                          } else if (segs[0] && /\.(json|lock|yaml|yml|toml|mod)$/i.test(segs[0])) {
                            packageLabel = segs[0]
                          }
                          const fScore = (f as { cvss_score?: number }).cvss_score
                          const fBand = cvssBand(fScore)
                          const fSev = fBand
                            ? cvssBandToBadge(fBand)
                            : severityToLabel(f.severity as string)
                          return (
                            <div
                              key={`${(f as { rule_id?: string }).rule_id ?? (f as { type?: string }).type ?? ""}-${rawFile}-${(f as { line?: number }).line ?? ""}-${i}`}
                              className="px-4 py-2 grid grid-cols-12 gap-3 items-center hover:bg-gray-50"
                            >
                              <div className="col-span-1">
                                <span
                                  className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border whitespace-nowrap ${fSev.classes}`}
                                >
                                  {fSev.label}
                                </span>
                              </div>
                              <div className="col-span-5 min-w-0">
                                <div className="text-sm font-medium truncate">
                                  {f.title ||
                                    (f as { rule_id?: string }).rule_id ||
                                    (f as { type?: string }).type?.replace(/_/g, " ") ||
                                    "Finding"}
                                </div>
                                {(f.evidence || f.explanation) && (
                                  <div className="text-[11px] text-gray-500 truncate">
                                    {f.evidence || f.explanation}
                                  </div>
                                )}
                              </div>
                              <div className="col-span-3 min-w-0 text-right">
                                {rawFile && (
                                  <div
                                    className="text-[10px] font-mono text-gray-600 truncate"
                                    title={rawFile}
                                  >
                                    {rawFile}
                                  </div>
                                )}
                                {packageLabel && packageLabel !== rawFile && (
                                  <div className="text-[10px] font-mono text-gray-400 truncate">
                                    {packageLabel}
                                  </div>
                                )}
                              </div>
                              <div className="col-span-2 min-w-0 text-right">
                                {typeof fScore === "number" && (
                                  <div className="text-[10px] font-mono text-orange-700 truncate">
                                    CVSS {fScore.toFixed(1)}
                                  </div>
                                )}
                                {((f as { source_tool?: string }).source_tool || (f as { scanner?: string }).scanner) && (
                                  <div className="text-[10px] font-mono text-gray-400 truncate">
                                    {(f as { source_tool?: string }).source_tool || (f as { scanner?: string }).scanner}
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )
              })()}

              <RunDetailTahap4Section nodeIoRecords={nodeIoRecords} />

              {recommendations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      Recommendations ({recommendations.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="divide-y">
                      {recommendations.map((rec: Finding, i: number) => (
                        <div key={i} className="px-4 py-3">
                          <div className="flex items-start gap-2">
                            <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                            <div>
                              <p className="text-sm font-medium">{rec.title || `Recommendation ${i + 1}`}</p>
                              {rec.description && <p className="text-xs text-gray-500 mt-1">{rec.description}</p>}
                              {rec.remediation && <p className="text-xs text-blue-600 mt-1">{rec.remediation}</p>}
                              {rec.priority && <Badge className="mt-1">{rec.priority}</Badge>}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )
        })()}
      </main>
    </div>
  )
}