import { useMemo, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { usePipelineByVersion, usePipelineRuns, useSyncRuns } from "@/hooks/usePipelinesV2"
import { useNodeSpecs, type NodeSpec } from "@/hooks/usePipeline"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import NodeIOCard from "@/components/NodeIOCard"
import {
  type NodeIORecord,
  groupByPhase,
  sortTahap123,
  phaseLabel,
} from "@/lib/node-io"

// `security_controls_applied` and `security_requirements.security_controls`
// can be serialised in two shapes depending on which pipeline path
// generated the row:
//   (A) plain string:  "sast"
//   (B) object:        { control: "sast", status: "recommended", reason: "..." }
// Older migrations also left objects with just a `name` key. We
// normalise both into a single `string` so the renderer can call
// `.replace(...)` on it without crashing.
function controlToString(c: unknown): string {
  if (typeof c === "string") return c
  if (c && typeof c === "object") {
    const obj = c as Record<string, unknown>
    const candidate =
      (obj.control as string) ||
      (obj.name as string) ||
      (obj.id as string) ||
      (obj.tool as string) ||
      ""
    if (candidate) return String(candidate)
  }
  return ""
}
import Header from "@/components/Header"
import DeletePipelineModal from "@/components/DeletePipelineModal"
import { ArrowRight, Play, BarChart3, FileText, Activity, Info, GitBranch, GitPullRequest, Clock, Loader2, CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronRight, RefreshCw, Trash2, Layers } from "lucide-react"
import type { PipelineRun, PipelineJob } from "@/hooks/usePipelinesV2"
import PRLink from "@/components/PRLink"

type Tab = "workflow" | "runs" | "details"

export default function PipelineVersionDetail() {
  const { projectId, repoId, version } = useParams<{ projectId: string; repoId: string; version: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>("workflow")
  const versionNum = version ? parseInt(version) : undefined
  const { data: pipeline, isLoading } = usePipelineByVersion(repoId, versionNum)
  const { data: runs } = usePipelineRuns(pipeline?.id)
  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const tabs: { key: Tab; label: string; icon: typeof FileText }[] = [
    { key: "workflow", label: "Workflow", icon: FileText },
    { key: "runs", label: `Runs (${runs?.length || 0})`, icon: Activity },
    { key: "details", label: "Details", icon: Info },
  ]

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (!pipeline) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Pipeline not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || repo?.full_name?.split("/")[0] || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || pipeline.repository?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` },
        { label: `Pipeline #${version}` },
      ]}>
        <Badge className="mr-2">{pipeline.status}</Badge>
        <Button variant="outline" size="sm" onClick={() => setDeleteOpen(true)}>
          <Trash2 className="h-4 w-4 mr-1" /> Delete
        </Button>
      </Header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline"
            onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/compare?left=${version}`)}>
            <BarChart3 className="h-4 w-4 mr-1" /> Compare
          </Button>
          <Button size="sm"
            onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/generate`)}>
            <Play className="h-4 w-4 mr-1" /> Regenerate
          </Button>
        </div>

        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t.key ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <t.icon className="h-4 w-4" />
              {t.label}
            </button>
          ))}
        </div>

        {pipeline.deployment_results && (() => {
          const dep = JSON.parse(pipeline.deployment_results)
          return dep.pr_url ? (
            <PRLink prUrl={dep.pr_url} prNumber={dep.pr_number} branch={dep.branch} />
          ) : null
        })()}

        {tab === "workflow" && (
          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-sm">Generated YAML</CardTitle></CardHeader>
              <CardContent>
                <pre className="text-xs bg-gray-900 text-green-400 p-4 rounded-md overflow-x-auto max-h-96 overflow-y-auto">
                  {pipeline.generated_yaml}
                </pre>
              </CardContent>
            </Card>
            {pipeline.ai_explanation && (
              <Card>
                <CardHeader><CardTitle className="text-sm">AI Explanation</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{pipeline.ai_explanation}</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {tab === "runs" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Pipeline Runs</h3>
              <SyncButton repoId={repoId!} version={versionNum || 0} />
            </div>
            {!runs || runs.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Activity className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                  <p className="text-sm text-gray-500 mb-4">No runs synced yet for this pipeline version.</p>
                  <p className="text-xs text-gray-400 mb-4">Sync from GitHub to fetch workflow runs for this pipeline.</p>
                  <SyncButton repoId={repoId!} version={versionNum || 0} />
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {runs.map((run) => (
                  <RunCardV2 key={run.id} run={run} projectId={projectId!} repoId={repoId!} version={version!} />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "details" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle className="text-sm">Detected Technologies</CardTitle></CardHeader>
                <CardContent>
                  {(() => {
                    const params = JSON.parse(pipeline.generation_params || "{}")
                    const items = [
                      { label: "Language", value: params.language },
                      { label: "Framework", value: params.framework },
                      { label: "Architecture", value: params.architecture_type },
                      { label: "Deployment Target", value: params.deployment_target },
                    ]
                    const hasItems = items.some(i => i.value)
                    return hasItems ? (
                      <div className="space-y-3">
                        {items.map(item => (
                          <div key={item.label} className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">{item.label}</span>
                            <span className="text-sm font-medium capitalize">{item.value || <span className="text-muted-foreground italic">Not detected</span>}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No technology data available</p>
                    )
                  })()}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm">Security Controls</CardTitle></CardHeader>
                <CardContent>
                  {(() => {
                    const params = JSON.parse(pipeline.generation_params || "{}")
                    const securityReqs = params.security_requirements || []
                    const controls = Array.isArray(securityReqs) ? securityReqs : []

                    if (controls.length > 0) {
                      return (
                        <div className="flex flex-wrap gap-2">
                          {controls
                            .map((c: unknown) => controlToString(c))
                            .filter(Boolean)
                            .map((c: string) => (
                              <span key={c} className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                                {c.replace(/_/g, " ")}
                              </span>
                            ))}
                        </div>
                      )
                    }

                    const rawControls = JSON.parse(pipeline.security_controls_applied || "[]")
                    const normalised = Array.isArray(rawControls)
                      ? rawControls.map(controlToString).filter(Boolean)
                      : []
                    return normalised.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {normalised.map((c: string) => (
                          <span key={c} className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                            {c.replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No security controls configured</p>
                    )
                  })()}
                </CardContent>
              </Card>
            </div>

            {pipeline.validation_results && (() => {
              const val = JSON.parse(pipeline.validation_results)
              return (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Validation Results</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        {val.valid ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : <XCircle className="h-4 w-4 text-red-500" />}
                        <span className="text-sm font-medium">{val.valid ? "Validation passed" : "Validation failed"}</span>
                      </div>
                      {val.errors?.length > 0 && (
                        <div className="space-y-1">
                          {val.errors.map((e: string, i: number) => (
                            <p key={i} className="text-xs text-red-600 flex items-center gap-1"><XCircle className="h-3 w-3 shrink-0" />{e}</p>
                          ))}
                        </div>
                      )}
                      {val.warnings?.length > 0 && (
                        <div className="space-y-1">
                          {val.warnings.map((w: string, i: number) => (
                            <p key={i} className="text-xs text-yellow-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3 shrink-0" />{w}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )
            })()}

            {pipeline.deployment_results && (() => {
              const dep = JSON.parse(pipeline.deployment_results)
              return dep.pr_url ? (
                <Card className="border-green-200">
                  <CardHeader><CardTitle className="text-sm flex items-center gap-2">
                    <GitPullRequest className="h-4 w-4 text-green-600" />
                    GitHub PR Link
                  </CardTitle></CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-3">
                      <a 
                        href={dep.pr_url} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-sm text-blue-600 hover:underline font-medium flex items-center gap-1"
                      >
                        #{dep.pr_number} — {dep.branch}
                        <ArrowRight className="h-3 w-3" />
                      </a>
                    </div>
                    {dep.pr_url && (
                      <div className="mt-2 pt-2 border-t">
                        <a 
                          href={dep.pr_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="text-xs text-gray-500 hover:text-blue-600"
                        >
                          Open in GitHub →
                        </a>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : null
            })()}

            <Card>
              <CardHeader><CardTitle className="text-sm">Prompt</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{pipeline.prompt}</p>
              </CardContent>
            </Card>

            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer hover:text-foreground">Raw Data</summary>
              <div className="mt-2 space-y-2">
                <pre className="bg-gray-100 p-3 rounded overflow-x-auto">{JSON.stringify(JSON.parse(pipeline.generation_params || "{}"), null, 2)}</pre>
                <pre className="bg-gray-100 p-3 rounded overflow-x-auto">{JSON.stringify(JSON.parse(pipeline.security_controls_applied || "[]"), null, 2)}</pre>
               </div>
             </details>

             {/* Pipeline Nodes (Tahap 1-3) — input/output per node.
                 Filled in by `useNodeSpecs([1,2,3])` from
                 `/api/pipeline/node-specs?tahap=1|2|3`. */}
             <PipelineNodesDetails />
             {/* Tahap 1-3 execution trace — input/output/duration/status
                 per node, persisted to pipelines.node_io at generate time. */}
             <PipelineNodeIOTimeline pipeline={pipeline} />
            </div>
          )}
      </main>

      <DeletePipelineModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        pipelineId={pipeline.id}
        pipelineVersion={versionNum || 0}
        repoId={repoId!}
        projectId={projectId!}
      />
    </div>
  )
}

function RunCardV2({ run, projectId, repoId, version }: { run: PipelineRun; projectId: string; repoId: string; version: string }) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()
  const jobs: PipelineJob[] = run.jobs ? JSON.parse(run.jobs as string) : []

  return (
    <Card className="border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left transition-colors"
      >
        {expanded ? <ChevronDown className="h-4 w-4 text-gray-400 shrink-0" /> : <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />}
        {run.conclusion === "success" ? <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" /> :
         run.conclusion === "failure" ? <XCircle className="h-5 w-5 text-red-500 shrink-0" /> :
         run.status === "running" || run.status === "queued" ? <Loader2 className="h-5 w-5 text-blue-500 animate-spin shrink-0" /> :
         <Clock className="h-5 w-5 text-gray-400 shrink-0" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">Run #{run.run_number}</span>
            <Badge variant={run.conclusion === "success" ? "default" : run.conclusion === "failure" ? "destructive" : "secondary"} className="text-xs">
              {run.conclusion || run.status}
            </Badge>
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
            {run.html_url && (
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {run.html_url.split("/").slice(-3).join("/")}
              </span>
            )}
            {run.duration_seconds && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {run.duration_seconds >= 60
                  ? `${Math.floor(run.duration_seconds / 60)}m ${run.duration_seconds % 60}s`
                  : `${run.duration_seconds}s`}
              </span>
            )}
            {run.created_at && (
              <span>{new Date(run.created_at).toLocaleString()}</span>
            )}
          </div>
        </div>
        <ArrowRight className="h-4 w-4 text-gray-400"
          onClick={(e) => { e.stopPropagation(); navigate(`/projects/${projectId}/repos/${repoId}/pipelines/${version}/runs/${run.id}`) }} />
      </button>
      {expanded && (
        <div className="border-t bg-gray-50/30">
          {jobs.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500">
              {run.status === "running" || run.status === "queued" ? "Waiting for job data..." : "No job data available"}
            </div>
          ) : (
            <div className="divide-y">
              {jobs.map((job) => (
                <JobRowV2 key={job.id} job={job} />
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

function JobRowV2({ job }: { job: PipelineJob }) {
  const [expanded, setExpanded] = useState(false)
  const hasSteps = job.steps && job.steps.length > 0
  const jobDuration = job.started_at && job.completed_at
    ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
    : null

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-100/50 text-left transition-colors"
      >
        {hasSteps ? (
          expanded ? <ChevronDown className="h-3.5 w-3.5 text-gray-400 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 text-gray-400 shrink-0" />
        ) : <div className="w-3.5 shrink-0" />}
        {job.conclusion === "success" ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" /> :
         job.conclusion === "failure" ? <XCircle className="h-4 w-4 text-red-500 shrink-0" /> :
         job.status === "running" || job.status === "queued" ? <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" /> :
         <Clock className="h-4 w-4 text-gray-400 shrink-0" />}
        <span className="text-sm font-medium flex-1">{job.name}</span>
        <span className="text-xs text-gray-500">
          {job.conclusion === "success" && jobDuration != null && `Passing after ${jobDuration}s`}
          {job.conclusion === "failure" && jobDuration != null && `Failing after ${jobDuration}s`}
          {job.status === "running" && "Running"}
          {job.status === "queued" && "Queued"}
        </span>
        <Badge variant={job.conclusion === "success" ? "default" : job.conclusion === "failure" ? "destructive" : "secondary"} className="text-xs">
          {job.conclusion || job.status}
        </Badge>
      </button>
      {expanded && hasSteps && (
        <div className="border-t bg-white px-8 py-2">
          {job.steps.map((step) => (
            <div key={step.number} className="flex items-center gap-3 py-1.5">
              {step.conclusion === "success" ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" /> :
               step.conclusion === "failure" ? <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" /> :
               step.status === "running" ? <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin shrink-0" /> :
               <Clock className="h-3.5 w-3.5 text-gray-400 shrink-0" />}
              <span className="text-sm text-gray-600">{step.name}</span>
              <span className="text-xs text-gray-400 ml-auto">
                {step.conclusion === "success" && step.completed_at && new Date(step.completed_at).toLocaleTimeString()}
                {step.status === "running" && "in progress"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SyncButton({ repoId, version }: { repoId: string; version: number }) {
  const syncRuns = useSyncRuns()
  const queryClient = useQueryClient()
  const [showToast, setShowToast] = useState(false)
  const [toastMsg, setToastMsg] = useState("")

  const handleSync = async () => {
    try {
      const result = await syncRuns.mutateAsync({ repoId, version })
      const syncedList = result.synced || []
      setToastMsg(`Synced: ${syncedList.length > 0 ? syncedList.join(", ") : "No new runs"}`)
      setShowToast(true)
      queryClient.invalidateQueries({ queryKey: ["pipeline-runs"] })
      setTimeout(() => setShowToast(false), 4000)
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || "Unknown error"
      setToastMsg(`Sync failed: ${msg}`)
      setShowToast(true)
      setTimeout(() => setShowToast(false), 8000)
    }
  }

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="outline"
        onClick={handleSync}
        disabled={syncRuns.isPending}
        className="gap-2"
      >
        <RefreshCw className={`h-4 w-4 ${syncRuns.isPending ? "animate-spin" : ""}`} />
        {syncRuns.isPending ? "Syncing..." : "Sync from GitHub"}
      </Button>
      {showToast && (
        <div className="absolute top-full right-0 mt-2 bg-white border rounded-md shadow-lg px-4 py-2 text-sm text-gray-700 whitespace-nowrap z-10">
          {toastMsg}
        </div>
      )}
    </div>
  )
}

// === Pipeline Nodes (Tahap 1-3) — dev reference ===
//
// Pulls the static v9.3 node metadata from `/api/pipeline/node-specs`
// and renders one card per node grouped by Tahap. Each card shows the
// function (1 sentence), the type (deterministic / llm / hybrid), and
// the state fields read (Inputs) vs written (Outputs). No CVSS, no
// LLM prompt body — this is a dev reference for understanding the
// pipeline structure, not a security dashboard.
function PipelineNodesDetails() {
  const { data: nodes, isLoading } = useNodeSpecs([1, 2, 3])
  const TAHAP_LABELS: Record<number, string> = {
    1: "Repository Context Analysis",
    2: "Security Coverage Inference",
    3: "Pipeline Generation & Deployment",
  }
  const TAHAP_COLOR: Record<number, string> = {
    1: "bg-blue-50 border-blue-200 text-blue-800",
    2: "bg-violet-50 border-violet-200 text-violet-800",
    3: "bg-emerald-50 border-emerald-200 text-emerald-800",
  }
  const TYPE_BADGE: Record<string, string> = {
    deterministic: "bg-slate-100 text-slate-700 border-slate-300",
    llm: "bg-violet-100 text-violet-800 border-violet-300",
    hybrid: "bg-amber-100 text-amber-800 border-amber-300",
  }
  const TYPE_LABEL: Record<string, string> = {
    deterministic: "deterministic",
    llm: "LLM",
    hybrid: "LLM + heuristic",
  }
  const byTahap: Record<number, NodeSpec[]> = {}
  for (const n of nodes ?? []) {
    if (!byTahap[n.tahap]) byTahap[n.tahap] = []
    byTahap[n.tahap]!.push(n)
  }
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Pipeline Nodes (Tahap 1–3)</CardTitle>
        <p className="text-[11px] text-muted-foreground mt-1">
          Input/output per node in the v9.3 compiled graph. Reference
          for understanding the data flow through the AI agent pipeline.
          Node count: <span className="font-mono">{nodes?.length ?? 0}</span>
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {isLoading && (
          <p className="text-xs text-muted-foreground">Loading node specs…</p>
        )}
        {!isLoading &&
          [1, 2, 3].map((t) => (
            <div key={t}>
              <div
                className={`inline-block rounded border px-2 py-0.5 text-[10px] font-bold uppercase mb-2 ${TAHAP_COLOR[t] ?? ""}`}
              >
                Tahap {t} — {TAHAP_LABELS[t] ?? `Tahap ${t}`}
                <span className="ml-1 opacity-75">
                  ({byTahap[t]?.length ?? 0})
                </span>
              </div>
              <div className="border rounded-md overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-[10px]">
                    <tr>
                      <th className="text-left px-3 py-2 w-[20%]">Node</th>
                      <th className="text-left px-3 py-2 w-[14%]">Type</th>
                      <th className="text-left px-3 py-2">Inputs (state reads)</th>
                      <th className="text-left px-3 py-2">Outputs (state writes)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(byTahap[t] ?? []).map((n) => (
                      <tr key={n.id} className="align-top hover:bg-gray-50/50">
                        <td className="px-3 py-2">
                          <div className="font-mono text-[11px] font-semibold text-gray-800">
                            {n.id}
                          </div>
                          <div className="text-[11px] text-gray-600 mt-0.5">
                            {n.name}
                          </div>
                          <div className="text-[10px] text-gray-400 font-mono mt-0.5">
                            {n.spec_ref}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-block text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                              TYPE_BADGE[n.type] ?? ""
                            }`}
                          >
                            {TYPE_LABEL[n.type] ?? n.type}
                          </span>
                          <div className="text-[10px] text-gray-500 mt-1 italic">
                            {n.function}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {n.inputs.length === 0 ? (
                              <span className="text-[10px] text-gray-400 italic">none</span>
                            ) : (
                              n.inputs.map((k) => (
                                <span
                                  key={k}
                                  className="text-[10px] font-mono bg-purple-50 text-purple-800 border border-purple-200 px-1.5 py-0.5 rounded"
                                >
                                  {k}
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {n.outputs.length === 0 ? (
                              <span className="text-[10px] text-gray-400 italic">none</span>
                            ) : (
                              n.outputs.map((k) => (
                                <span
                                  key={k}
                                  className="text-[10px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-200 px-1.5 py-0.5 rounded"
                                >
                                  {k}
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
               </div>
             </div>
           ))}
      </CardContent>
    </Card>
  )
}

// === Pipeline Node I/O Trace (Tahap 1-3) ===
//
// Renders the per-node execution trace that was captured by the
// AI service (`_invoke_graph_phase` → `state["node_io"]`) and
// persisted to the `pipelines.node_io` jsonb column at
// generate-time. Each card shows: input keys fed into the node,
// output diff written by the node, duration, status, error (if
// any), and the LLM prompt (if the node is LLM-driven and we
// have the prompt metadata from `/api/pipeline/node-specs`).
//
// The structure mirrors the Tahap 4 cards on the RunDetail page
// (see `RunDetail.tsx → RunDetailTahap4Section`), so reviewers
// can compare node-level metrics across all 4 tahap of the v9.3
// compiled graph in a consistent format (Bab 5.13.4).
function PipelineNodeIOTimeline({ pipeline }: { pipeline: { node_io?: string | null } }) {
  const { data: nodes } = useNodeSpecs([1, 2, 3])

  // Parse the jsonb payload. Empty / null / malformed values
  // produce an empty array so the UI degrades to a friendly
  // "no trace" message instead of crashing.
  const records: NodeIORecord[] = useMemo(() => {
    if (!pipeline.node_io) return []
    try {
      const parsed = JSON.parse(pipeline.node_io)
      if (!Array.isArray(parsed)) return []
      return parsed.filter(
        (r): r is NodeIORecord =>
          r && typeof r === "object" && typeof r.node === "string",
      )
    } catch {
      return []
    }
  }, [pipeline.node_io])

  // Build a `node_id → prompt` lookup so we can surface the LLM
  // prompt under each card. The static spec API uses
  // `id` like "domain_detection" which matches the AI service
  // `node` field 1:1.
  const promptByNode = useMemo(() => {
    const m = new Map<string, string>()
    for (const n of nodes ?? []) {
      if (n.prompt) m.set(n.id, n.prompt)
    }
    return m
  }, [nodes])

  const groups = useMemo(() => groupByPhase(records), [records])

  return (
    <Card className="mt-4 border-t-4 border-t-emerald-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-500" />
            Pipeline Node Execution Trace (Tahap 1–3)
          </CardTitle>
          <span className="text-[10px] text-gray-500">
            {records.length} nodes · click to expand
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Per-node I/O trace from the v9.3 compiled graph. Each card
          shows the input keys, output diff, duration, and status
          recorded by the AI service during pipeline generation. LLM
          prompts are surfaced for nodes that have one.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {records.length === 0 && (
          <div className="text-xs bg-amber-50 border border-amber-200 text-amber-900 rounded p-3">
            <p className="font-semibold mb-1">No execution trace available for this version.</p>
            <p>
              Older pipeline versions (generated before the v9.3 node-I/O
              instrumentation was added) do not have a stored trace. Trigger
              a new generate to populate this section.
            </p>
          </div>
        )}
        {groups.map((g) => (
          <div key={g.phase}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold uppercase text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                {phaseLabel(g.phase)}
              </span>
              <span className="text-[10px] text-gray-400">
                ({g.records.length} nodes)
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {sortTahap123(g.records).map((r) => (
                <NodeIOCard
                  key={`${g.phase}-${r.node}`}
                  record={r}
                  prompt={promptByNode.get(r.node) ?? null}
                />
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
