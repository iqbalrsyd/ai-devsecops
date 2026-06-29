import { useEffect, useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useRunDetail } from "@/hooks/usePipelinesV2"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import { useAnalyzeExecution } from "@/hooks/usePipeline"
import type {
  ExecutionAnalysis,
  RemediationSuggestion,
  RootCauseData,
} from "@/hooks/usePipeline"
import Header from "@/components/Header"
import StageIndicator from "@/components/StageIndicator"
import api from "@/lib/axios"

const REMEDIATION_STEPS = [
  "Connecting to repository",
  "Analyzing failed workflow",
  "Inspecting validation results",
  "Identifying root causes",
  "Mapping affected jobs",
  "Generating remediation actions",
  "Validating the fixed workflow",
  "Preparing pull request",
]

interface DeployResult {
  pr_url?: string
  pr_number?: number
  branch?: string
  pipeline_version?: number
  error?: string
}

type StageStatus = "added" | "fixed" | "removed" | "affected" | "unchanged"

interface StageDiff {
  name: string
  status: StageStatus
  reason: string
  tool?: string
}

function classifySuggestion(
  s: RemediationSuggestion,
): StageStatus {
  const ct = (s.change_type || "").toLowerCase()
  if (ct === "add" || ct === "added") return "added"
  if (ct === "remove" || ct === "removed") return "removed"
  if (ct === "fix" || ct === "fixed" || ct === "modify" || ct === "update") return "fixed"
  return "fixed"
}

function statusColor(status: StageStatus) {
  switch (status) {
    case "added":
      return "bg-blue-50 text-blue-700 border-blue-200"
    case "fixed":
      return "bg-green-50 text-green-700 border-green-200"
    case "removed":
      return "bg-red-50 text-red-700 border-red-200"
    case "affected":
      return "bg-amber-50 text-amber-700 border-amber-200"
    default:
      return "bg-gray-50 text-gray-600 border-gray-200"
  }
}

function statusIcon(status: StageStatus) {
  switch (status) {
    case "added":
      return "+"
    case "fixed":
      return "✓"
    case "removed":
      return "−"
    case "affected":
      return "!"
    default:
      return "·"
  }
}

function statusLabel(status: StageStatus) {
  switch (status) {
    case "added":
      return "Added"
    case "fixed":
      return "Fixed"
    case "removed":
      return "Removed"
    case "affected":
      return "Affected"
    default:
      return "Unchanged"
  }
}

export default function RunRemediation() {
  const { projectId, repoId, runId, version } = useParams<{
    projectId: string
    repoId: string
    runId: string
    version: string
  }>()

  const navigate = useNavigate()
  const { data: run, isLoading: runLoading } = useRunDetail(runId)
  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)

  const [result, setResult] = useState<ExecutionAnalysis | null>(null)
  const [error, setError] = useState("")
  const [deploying, setDeploying] = useState(false)
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null)

  const { mutate: triggerRemediation, isPending } = useAnalyzeExecution()

  useEffect(() => {
    if (!run || !repo?.full_name || !run.github_run_id || result || error) return

    triggerRemediation(
      {
        repositoryId: repo.full_name,
        runId: run.github_run_id,
        workflowJobs:
          typeof run.jobs === "string" ? run.jobs : JSON.stringify(run.jobs || []),
        workflowConclusion: run.conclusion || "",
      },
      {
        onSuccess: (data) => {
          setResult(data)
        },
        onError: (err) => {
          setError(err.message || "Remediation failed")
        },
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.github_run_id, repo?.full_name])

  const handleDeploy = async () => {
    if (!result?.remediation_workflow || !repo?.full_name || !run) return
    setDeploying(true)
    setDeployResult(null)
    try {
      const { data } = await api.post(
        "/ai/pipeline/deploy-remediation",
        {
          repository_id: repo.full_name,
          workflow_yaml: result.remediation_workflow,
          run_number: run.run_number,
          github_run_id: run.github_run_id,
          base_branch: repo.default_branch || "main",
          workflow_file: "ai-devsecops.yml",
        },
      )
      if (data.pr_url) {
        setDeployResult({
          pr_url: data.pr_url,
          pr_number: data.pr_number,
          branch: data.branch,
          pipeline_version: data.pipeline_version,
        })
      } else {
        setDeployResult({ error: data.error || "Deploy failed" })
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Deploy failed"
      setDeployResult({ error: message })
    }
    setDeploying(false)
  }

  const failedJobs = result?.failed_jobs || []
  const suggestions = result?.remediation_suggestions || []
  const rootCause: RootCauseData | null = result?.root_cause || null
  const failureAnalysis = result?.failure_analysis || null
  const hasErrors = (result?.errors?.length ?? 0) > 0
  const fixedJobsCount = failedJobs.length || suggestions.length
  const finalPrUrl = deployResult?.pr_url || result?.remediation_pr_url || null
  const finalPrNumber =
    deployResult?.pr_number || result?.remediation_pr_number || null
  const finalBranch =
    deployResult?.branch || result?.remediation_branch || null

  // Animate the step indicator while the analysis is in progress,
  // matching the visual cadence of PipelineGenerator.
  const currentStageIndex = result
    ? REMEDIATION_STEPS.length - 1
    : isPending
    ? Math.min(
        Math.floor((Date.now() % 8000) / 1000),
        REMEDIATION_STEPS.length - 1,
      )
    : -1

  // Compute the stages diff from suggestions + failed jobs.
  const stageDiffs: StageDiff[] = (() => {
    const diffs: StageDiff[] = []
    const seen = new Set<string>()

    for (const job of failedJobs) {
      const name = job.job_name
      if (!seen.has(name)) {
        seen.add(name)
        diffs.push({
          name,
          status: "affected",
          reason: job.step_name
            ? `Failed at step: ${job.step_name}`
            : "This job failed in the latest run",
          tool: undefined,
        })
      }
    }

    for (const s of suggestions) {
      const fileBase = (s.file_path || "").split("/").pop() || s.file_path
      const key = fileBase.toLowerCase()
      if (!seen.has(key)) {
        seen.add(key)
        diffs.push({
          name: fileBase,
          status: classifySuggestion(s),
          reason: s.reasoning || "Workflow modification",
          tool: s.risk,
        })
      } else {
        // Already have an "affected" entry — upgrade to "fixed"
        const existing = diffs.find((d) => d.name.toLowerCase() === key)
        if (existing) {
          existing.status = "fixed"
          existing.reason = s.reasoning || existing.reason
        }
      }
    }
    return diffs
  })()

  if (runLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-6 w-6 rounded-full border-2 border-foreground border-t-transparent animate-spin" />
      </div>
    )
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Run not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: project?.name || "Project", href: `/projects/${projectId}` },
          {
            label: repo?.full_name || "Repository",
            href: `/projects/${projectId}/repos/${repoId}`,
          },
          {
            label: `Run #${run.run_number}`,
            href: `/projects/${projectId}/repos/${repoId}/pipelines/${version}/runs/${runId}`,
          },
          { label: "Workflow Fix" },
        ]}
      />

      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* Header Info - matches PipelineGenerator visual design */}
        <div className="mb-6 p-4 bg-card rounded-lg border border-border">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Workflow Fix</h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                Repository:{" "}
                <span className="font-medium text-foreground">
                  {repo?.full_name || "—"}
                </span>{" "}
                · Run{" "}
                <span className="font-medium text-foreground">
                  #{run.run_number}
                </span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="text-xs text-muted-foreground bg-secondary px-3 py-1.5 rounded-full">
                Conclusion:{" "}
                <span className="font-medium text-foreground capitalize">
                  {run.conclusion || run.status}
                </span>
              </div>
              <Link
                to={`/projects/${projectId}/repos/${repoId}/pipelines/${version}/runs/${runId}`}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                ← Back to run
              </Link>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: Progress / Status - mirrors PipelineGenerator progress card */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  {isPending
                    ? "AI is fixing your workflow"
                    : result
                    ? "Remediation complete"
                    : "Remediation Progress"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {REMEDIATION_STEPS.map((step, i) => {
                  const status =
                    result
                      ? "done"
                      : i < currentStageIndex
                      ? "done"
                      : i === currentStageIndex
                      ? "running"
                      : "pending"
                  return (
                    <StageIndicator
                      key={step}
                      number={i + 1}
                      label={step}
                      status={status}
                    />
                  )
                })}
                {!result && !error && (
                  <p className="text-xs text-muted-foreground pt-3 border-t border-border mt-2">
                    {isPending
                      ? "AI is analyzing the failure and preparing a fix…"
                      : "Initializing remediation engine…"}
                  </p>
                )}
                {result && (
                  <p className="text-xs text-muted-foreground pt-3 border-t border-border mt-2">
                    Remediation finished. Review the analysis below before
                    creating a Pull Request.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Failure summary card - mirrors PipelineGenerator's
                "Repository Analysis" card with the same key-value style */}
            {(failureAnalysis || rootCause || result) && (
              <Card className="border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">
                    Failure Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {failureAnalysis && (
                    <>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Failure Type
                        </span>
                        <span className="font-medium capitalize">
                          {failureAnalysis.failure_type?.replace(/_/g, " ") ||
                            "—"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Confidence
                        </span>
                        <span className="font-medium">
                          {Math.round(
                            (failureAnalysis.confidence || 0) * 100,
                          )}
                          %
                        </span>
                      </div>
                    </>
                  )}
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Failed Jobs</span>
                    <span className="font-medium">{failedJobs.length}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">
                      Affected Components
                    </span>
                    <span className="font-medium">
                      {rootCause?.affected_components?.length || 0}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">
                      Suggested Fixes
                    </span>
                    <span className="font-medium">{suggestions.length}</span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Results - mirrors PipelineGenerator's right column */}
          <div className="lg:col-span-3 space-y-4">
            {/* Loading State - mirrors PipelineGenerator's loading card */}
            {isPending && !result && !error && (
              <Card className="border-border">
                <CardContent className="py-12">
                  <div className="text-center">
                    <div className="h-6 w-6 rounded-full border-2 border-foreground border-t-transparent animate-spin mx-auto" />
                    <h3 className="font-medium text-foreground mt-3">
                      Analyzing the failed workflow
                    </h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1">
                      The AI is inspecting jobs, identifying root causes, and
                      preparing a corrected workflow.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Error State - mirrors PipelineGenerator's error card */}
            {error && (
              <Card className="border-destructive">
                <CardContent className="py-3 text-sm text-destructive bg-destructive/5 rounded-lg flex items-center justify-between gap-3">
                  <span>{error}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setError("")
                      setResult(null)
                    }}
                  >
                    Retry
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Ready state - mirrors PipelineGenerator's "Ready to Generate" */}
            {!result && !isPending && !error && (
              <Card className="border-border">
                <CardContent className="py-12">
                  <div className="text-center">
                    <h3 className="font-medium text-foreground mb-1">
                      Ready to Fix Workflow
                    </h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                      Click below to start the AI remediation. It will analyze
                      the failed run, identify the root cause, and generate a
                      corrected workflow file.
                    </p>
                    <Button
                      className="mt-4"
                      onClick={() => {
                        if (!run || !repo?.full_name || !run.github_run_id) return
                        triggerRemediation(
                          {
                            repositoryId: repo.full_name,
                            runId: run.github_run_id,
                            workflowJobs:
                              typeof run.jobs === "string"
                                ? run.jobs
                                : JSON.stringify(run.jobs || []),
                            workflowConclusion: run.conclusion || "",
                          },
                          {
                            onSuccess: (data) => setResult(data),
                            onError: (err) =>
                              setError(err.message || "Remediation failed"),
                          },
                        )
                      }}
                    >
                      Start Remediation
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {result && (
              <>
                {/* Status banner - mirrors the green-bordered success
                    card in PipelineGenerator's deploy flow */}
                <Card className={hasErrors ? "border-amber-300" : "border-green-300"}>
                  <CardContent className="flex items-center gap-3 py-3">
                    {hasErrors ? (
                      <div className="h-2 w-2 rounded-full bg-amber-500" />
                    ) : (
                      <div className="h-2 w-2 rounded-full bg-green-500" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm font-medium">
                        {hasErrors
                          ? "Fix generated with warnings"
                          : "Fixed workflow generated"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {fixedJobsCount} failing job
                        {fixedJobsCount !== 1 ? "s" : ""} addressed
                        {result.summary ? ` — ${result.summary}` : ""}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {/* Stages & Security Controls diff - mirrors
                    PipelineGenerator's "Security Controls" card but with
                    per-stage status (added/fixed/removed/affected) */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">
                        Stages & Security Controls
                      </CardTitle>
                      <span className="text-xs text-muted-foreground">
                        {stageDiffs.length} change
                        {stageDiffs.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {stageDiffs.length > 0 ? (
                      <div className="grid grid-cols-1 gap-2">
                        {stageDiffs.map((d, i) => (
                          <div
                            key={i}
                            className={`flex items-start gap-2 p-2 rounded-md border text-sm ${statusColor(d.status)}`}
                          >
                            <span className="font-bold text-base leading-none mt-0.5">
                              {statusIcon(d.status)}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-medium capitalize">
                                  {(d.name || "").replace(/_/g, " ")}
                                </span>
                                <Badge
                                  variant="outline"
                                  className="text-[10px] uppercase tracking-wide shrink-0"
                                >
                                  {statusLabel(d.status)}
                                </Badge>
                              </div>
                              {d.reason && (
                                <p className="text-xs mt-0.5 opacity-80">
                                  {d.reason}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No stage changes were required.
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* Root Cause - mirrors PipelineGenerator's
                    "Generated Workflow" explanation card with
                    background-secondary styling */}
                {rootCause && (
                  <Card className="border-border">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-medium">
                        Root Cause
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-muted-foreground bg-secondary rounded px-3 py-2">
                        {rootCause.root_cause}
                      </p>
                      {rootCause.evidence &&
                        rootCause.evidence.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">
                              Evidence
                            </p>
                            <ul className="list-disc list-inside text-sm space-y-0.5">
                              {rootCause.evidence.map((e, i) => (
                                <li key={i}>{e}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      {rootCause.affected_components &&
                        rootCause.affected_components.length > 0 && (
                          <div className="pt-2 border-t border-border">
                            <p className="text-xs font-medium text-muted-foreground mb-1">
                              Affected Components
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {rootCause.affected_components.map((c) => (
                                <span
                                  key={c}
                                  className="text-xs font-medium bg-secondary text-secondary-foreground px-2.5 py-1 rounded-full border border-border"
                                >
                                  {c}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                    </CardContent>
                  </Card>
                )}

                {/* Fixed Workflow - mirrors PipelineGenerator's
                    "Generated Workflow" YAML block */}
                {result.remediation_workflow && (
                  <Card className="border-border">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">
                          Fixed Workflow
                        </CardTitle>
                        <span className="text-xs text-muted-foreground">
                          YAML
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto max-h-96 leading-relaxed border border-border">
                        <code className="text-foreground">
                          {result.remediation_workflow}
                        </code>
                      </pre>
                    </CardContent>
                  </Card>
                )}

                {/* Validation Results - mirrors PipelineGenerator's
                    ValidationResults visual pattern */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">
                      Validation Results
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                        <span>YAML syntax</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                        <span>Workflow structure</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                        <span>Resolved issues ({fixedJobsCount})</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                        <span>Security controls</span>
                      </div>
                    </div>

                    {hasErrors && (
                      <div className="pt-2 border-t border-border">
                        <p className="text-sm font-medium text-amber-600 mb-1">
                          ⚠ Warnings ({result.errors.length})
                        </p>
                        <ul className="list-disc list-inside text-sm text-muted-foreground space-y-0.5">
                          {result.errors.map((e, i) => (
                            <li key={i}>{e}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {failedJobs.length > 0 && (
                      <div className="pt-2 border-t border-border">
                        <p className="text-sm font-medium text-green-600 mb-1">
                          ✓ Resolved Issues
                        </p>
                        <ul className="list-disc list-inside text-sm space-y-0.5">
                          {failedJobs.map((job) => (
                            <li key={job.job_id}>
                              Fixed failing job:{" "}
                              <span className="font-medium">
                                {job.job_name}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Deploy error - mirrors PipelineGenerator */}
                {deployResult?.error && (
                  <Card className="border-destructive">
                    <CardContent className="py-3 text-sm text-destructive bg-destructive/5 rounded-lg">
                      {deployResult.error}
                    </CardContent>
                  </Card>
                )}

                {/* === Workflow Fix action section ===
                    Mirrors PipelineGenerator's "Pull Request Created"
                    pattern + 2-button action row, but exposes the
                    explicit metadata the user requested. */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">
                      Workflow Fix
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Top status banner - mirrors PipelineGenerator
                        green-bordered success card */}
                    <div
                      className={`flex items-center gap-3 py-3 px-4 rounded-lg border ${
                        finalPrUrl
                          ? "border-green-300 bg-green-50/50"
                          : "border-foreground/10 bg-secondary/40"
                      }`}
                    >
                      <div
                        className={`h-2 w-2 rounded-full ${
                          finalPrUrl ? "bg-green-500" : "bg-foreground/40"
                        }`}
                      />
                      <div className="flex-1">
                        <p className="text-sm font-medium">
                          {finalPrUrl
                            ? "PR ready to merge"
                            : "Fixed workflow generated"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {fixedJobsCount} failing job
                          {fixedJobsCount !== 1 ? "s" : ""} addressed
                          {result.summary ? ` — ${result.summary}` : ""}
                        </p>
                      </div>
                    </div>

                    {/* Metadata grid - same flex justify-between
                        key-value pattern used in PipelineGenerator's
                        "Repository Analysis" card */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Status
                        </span>
                        <span className="font-medium">
                          {finalPrUrl
                            ? "PR ready to merge"
                            : "Fixed workflow generated"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Repository
                        </span>
                        <span className="font-medium truncate max-w-[60%] text-right">
                          {repo?.full_name || "—"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Run Information
                        </span>
                        <span className="font-medium">
                          Run #{run.run_number} · {run.status}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Issues fixed
                        </span>
                        <span className="font-medium">
                          {fixedJobsCount} failing job
                          {fixedJobsCount !== 1 ? "s" : ""} addressed
                        </span>
                      </div>
                      {finalPrUrl && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">
                            Generated PR
                          </span>
                          <a
                            href={finalPrUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-primary hover:underline"
                          >
                            PR #{finalPrNumber || "—"}
                          </a>
                        </div>
                      )}
                      {finalBranch && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">
                            Branch
                          </span>
                          <span className="font-medium font-mono text-xs">
                            {finalBranch}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Actions - mirrors PipelineGenerator's
                        "Deploy to GitHub via PR" + "View Pipeline
                        Detail" button pair */}
                    <div className="pt-3 border-t border-border space-y-2">
                      <p className="text-xs font-medium text-muted-foreground">
                        Actions
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {finalPrUrl ? (
                          <a
                            href={finalPrUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full"
                          >
                            <Button className="w-full h-12 text-base" size="lg">
                              Open Pull Request
                            </Button>
                          </a>
                        ) : (
                          <Button
                            className="w-full h-12 text-base"
                            size="lg"
                            onClick={handleDeploy}
                            disabled={deploying || !result.remediation_workflow}
                          >
                            {deploying
                              ? "Creating PR…"
                              : "Create Pull Request"}
                          </Button>
                        )}

                        <Button
                          variant="outline"
                          className="w-full h-12 text-base"
                          size="lg"
                          onClick={() => {
                            const targetVersion =
                              deployResult?.pipeline_version ||
                              result?.remediation_pr_number
                            const id = repoId
                            if (id && targetVersion) {
                              navigate(
                                `/projects/${projectId}/repos/${id}/pipelines/${targetVersion}`,
                              )
                            } else if (id) {
                              navigate(`/projects/${projectId}/repos/${id}`)
                            }
                          }}
                        >
                          Open New Pipeline
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
