import { useState, useEffect } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import PRLink from "@/components/PRLink"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Loader2, Sparkles, AlertCircle, GitBranch, ExternalLink, CheckCircle2, FileCode2, ShieldCheck } from "lucide-react"
import { useGeneratePipeline, useDeployWorkflow, useLatestWorkflowRun, useExecutionStatus, type ValidationResult, type PipelineResponse } from "@/hooks/usePipeline"
import { useProjects } from "@/hooks/useProjects"
import { useRepositories } from "@/hooks/useRepositories"
import RequirementForm from "@/components/RequirementForm"
import ValidationResults from "@/components/ValidationResults"
import Header from "@/components/Header"
import StageIndicator from "@/components/StageIndicator"

type WorkflowKind = "generic" | "custom"

function WorkflowFileViewer({
  files,
  genericYaml,
  customYaml,
}: {
  files: PipelineResponse["workflow_files"]
  genericYaml: string
  customYaml: string
}) {
  const initialKind: WorkflowKind =
    files && files.length > 0 && files[0]?.kind === "custom" ? "custom" : "generic"
  const [active, setActive] = useState<WorkflowKind>(initialKind)
  const [copied, setCopied] = useState(false)

  if (!files || files.length === 0) {
    return (
      <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto max-h-96 leading-relaxed border border-border">
        <code className="text-foreground">{genericYaml || customYaml}</code>
      </pre>
    )
  }

  const activeFile = files.find((f) => f.kind === active) ?? files[0]
  const activeYaml = active === "custom" ? customYaml : genericYaml

  const handleCopy = async () => {
    if (!activeYaml) return
    try {
      await navigator.clipboard.writeText(activeYaml)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {files.map((f) => (
          <button
            key={f.path}
            type="button"
            onClick={() => setActive(f.kind as WorkflowKind)}
            className={
              "text-xs font-medium px-3 py-1.5 rounded-full border transition-colors " +
              (active === f.kind
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-secondary text-secondary-foreground border-border hover:bg-secondary/70")
            }
          >
            <span className="inline-flex items-center gap-1.5">
              {f.kind === "custom" ? <ShieldCheck className="h-3.5 w-3.5" /> : <FileCode2 className="h-3.5 w-3.5" />}
              <span>{f.name}</span>
              <span className="text-[10px] opacity-80">({f.jobs.length} jobs)</span>
            </span>
          </button>
        ))}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="ml-auto h-7 text-xs"
          onClick={handleCopy}
          disabled={!activeYaml}
        >
          {copied ? "Copied!" : "Copy YAML"}
        </Button>
      </div>
      <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs flex flex-wrap items-center gap-3">
        <span className="font-mono text-muted-foreground">{activeFile.path}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-foreground">
          Jobs: <span className="font-medium">{activeFile.jobs.join(", ") || "—"}</span>
        </span>
      </div>
      {activeYaml ? (
        <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto max-h-96 leading-relaxed border border-border">
          <code className="text-foreground">{activeYaml}</code>
        </pre>
      ) : (
        <p className="text-xs text-muted-foreground">No custom rules file for this domain (e.g. general).</p>
      )}
    </div>
  )
}

const GENERATION_STEPS = [
  "Connecting to repository",
  "Scanning repository structure",
  "Detecting technology stack",
  "Analyzing architecture",
  "Inferring security requirements",
  "Generating workflow YAML",
  "Validating generated pipeline",
]

interface SubjectRun {
  job_id: number
  job_name: string
  status: "queued" | "in_progress" | "completed" | "success" | "failure" | "cancelled" | "skipped" | string
  conclusion: string | null
  started_at: string | null
  completed_at: string | null
  html_url?: string
}

function LatestRunSubjectRuns({ repositoryId }: { repositoryId: string }) {
  const { data: latest, isLoading } = useLatestWorkflowRun(repositoryId)
  const runId = latest?.run_id ?? null
  const { data: status } = useExecutionStatus(repositoryId, runId)
  const jobs = (status?.jobs ?? []) as unknown as SubjectRun[]

  if (isLoading) {
    return <p className="text-xs text-muted-foreground">Loading latest run…</p>
  }
  if (!runId) {
    return <p className="text-xs text-muted-foreground">No runs yet for this repository.</p>
  }
  return (
    <div className="space-y-2">
      <div className="text-xs text-muted-foreground">
        Run #{runId} · status: <span className="font-medium text-foreground">{latest?.status || "—"}</span>
        {latest?.conclusion ? (
          <>
            {" "}· conclusion: <span className="font-medium text-foreground">{latest.conclusion}</span>
          </>
        ) : null}
      </div>
      <SubjectRunsPanel runs={jobs} />
    </div>
  )
}

function SubjectRunsPanel({ runs }: { runs: SubjectRun[] }) {
  if (!runs || runs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No subject runs yet. Trigger the pipeline from RunDetail to populate this list.
      </p>
    )
  }

  const total = runs.length
  const successful = runs.filter((r) => r.conclusion === "success" || r.status === "success").length
  const failed = runs.filter((r) => r.conclusion === "failure" || r.status === "failure").length
  const skipped = runs.filter(
    (r) => r.conclusion === "skipped" || r.status === "skipped" || r.conclusion === "cancelled",
  ).length
  const inProgress = total - successful - failed - skipped

  const statusColor = (s: SubjectRun["status"], c: SubjectRun["conclusion"]) => {
    if (c === "success" || s === "success") return "text-green-700 bg-green-50 border-green-200"
    if (c === "failure" || s === "failure") return "text-red-700 bg-red-50 border-red-200"
    if (c === "skipped" || c === "cancelled" || s === "skipped")
      return "text-gray-700 bg-gray-50 border-gray-200"
    if (s === "in_progress" || s === "queued") return "text-blue-700 bg-blue-50 border-blue-200"
    return "text-amber-700 bg-amber-50 border-amber-200"
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
          <div className="text-muted-foreground">Total IDs</div>
          <div className="text-lg font-semibold">{total}</div>
        </div>
        <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2">
          <div className="text-green-700">Successful</div>
          <div className="text-lg font-semibold text-green-700">{successful}</div>
        </div>
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2">
          <div className="text-red-700">Failed</div>
          <div className="text-lg font-semibold text-red-700">{failed}</div>
        </div>
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
          <div className="text-gray-700">Skipped / Other</div>
          <div className="text-lg font-semibold text-gray-700">
            {skipped + inProgress}
            {inProgress > 0 ? <span className="text-[10px] ml-1 text-blue-700">({inProgress} active)</span> : null}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-1.5">
        {runs.map((r) => {
          const status = (r.conclusion || r.status || "unknown").toString()
          return (
            <div
              key={r.job_id}
              className={
                "flex items-center justify-between gap-2 p-2 rounded-md border text-xs " + statusColor(r.status, r.conclusion)
              }
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[10px] opacity-70">#{r.job_id}</span>
                <span className="font-medium truncate">{r.job_name}</span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wide">{status}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function PipelineGenerator() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>()
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { data: repos } = useRepositories(projectId)
  const generatePipeline = useGeneratePipeline()
  const deployWorkflow = useDeployWorkflow()

  const [pipelineResult, setPipelineResult] = useState<PipelineResponse | null>(null)
  const [generatedYaml, setGeneratedYaml] = useState("")
  const [generatedYamlGeneric, setGeneratedYamlGeneric] = useState("")
  const [generatedYamlCustom, setGeneratedYamlCustom] = useState("")
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [generationStep, setGenerationStep] = useState(0)
  const [deployResult, setDeployResult] = useState<{
    branch: string
    pr_number: number
    pr_url: string
    errors: string[]
    success?: boolean
    pipeline_version?: number
    workflow_file?: string
    workflow_file_custom?: string
    workflow_files?: Array<{ name: string; path: string; kind: string }>
  } | null>(null)

  const [deployTarget, setDeployTarget] = useState("docker")

  const project = projects?.find((p) => p.id === projectId)
  const selectedRepo = repos?.find((r) => r.id === repoId) || repos?.[0]

  const handleGenerate = async (query: string, options: { language: string; framework: string; deployTarget: string; projectType: string; securityReqs: string[]; pipelineMode: "general" | "domain" | "both" }) => {
    const repoFullName = selectedRepo?.full_name || ""
    if (!repoFullName) {
      setGenerationError("No repository is connected to this project yet.")
      return
    }
    setGenerationError(null)
    setDeployResult(null)
    setPipelineResult(null)
    setGeneratedYaml("")
    setGenerationStep(0)
    try {
      // Pull the GitHub token from the client-side cache that
      // ConnectRepoModal writes. The backend also stores its own
      // encrypted copy on the repository row, so this is just a
      // convenience to avoid a second prompt. Without it, the AI
      // service cannot hit api.github.com and the analysis
      // collapses to "Language: Unknown, 0 stages".
      const cachedToken =
        (typeof window !== "undefined" && localStorage.getItem("github_token")) || ""
      const result = await generatePipeline.mutateAsync({
        query,
        repository_id: repoFullName,
        project_id: projectId || "",
        project_type: options.projectType,
        language: options.language,
        framework: options.framework,
        deploy_target: options.deployTarget || deployTarget,
        security_requirements: options.securityReqs,
        pipeline_mode: options.pipelineMode,
        github_token: cachedToken,
      })
      setPipelineResult(result)
      setGeneratedYaml(result.workflow_yaml)
      setGeneratedYamlGeneric(result.workflow_yaml_generic || result.workflow_yaml)
      setGeneratedYamlCustom(result.workflow_yaml_custom || "")

      if (result.errors && result.errors.length > 0) {
        setGenerationError(result.errors.join(". "))
      }
    } catch (error) {
      setPipelineResult(null)
      setGeneratedYaml("")
      setGeneratedYamlGeneric("")
      setGeneratedYamlCustom("")
      setGenerationError(error instanceof Error ? error.message : "Pipeline generation failed")
    }
  }

  const handleDeploy = async () => {
    if (!generatedYaml || !selectedRepo?.full_name) return
    try {
      const result = await deployWorkflow.mutateAsync({
        repository_id: selectedRepo.full_name,
        workflow_yaml: generatedYaml,
        workflow_yaml_generic: generatedYamlGeneric || generatedYaml,
        workflow_yaml_custom: generatedYamlCustom,
        workflow_files:
          pipelineResult?.workflow_files?.map((f) => ({ name: f.name, path: f.path, kind: f.kind })) ?? [],
      })
      setDeployResult(result)
    } catch (error) {
      setDeployResult({
        branch: "",
        pr_number: 0,
        pr_url: "",
        errors: [error instanceof Error ? error.message : "Deployment failed"],
        success: false,
      })
    }
  }

  // Drive the stage indicator with a React state that ticks every
  // 1.2s while generation is in flight, starting at 0 and capped at
  // the last step. The old implementation used `Date.now() % 7000`,
  // which made the indicator jump to a random step on every click.
  useEffect(() => {
    if (!generatePipeline.isPending) {
      return
    }
    // Reset to 0 on every fresh generation.
    setGenerationStep(0)
    const id = setInterval(() => {
      setGenerationStep((prev) =>
        prev < GENERATION_STEPS.length - 1 ? prev + 1 : prev
      )
    }, 1200)
    return () => clearInterval(id)
  }, [generatePipeline.isPending])

  const currentStageIndex = pipelineResult
    ? GENERATION_STEPS.length - 1
    : generatePipeline.isPending
    ? generationStep
    : -1

  return (
    <div className="min-h-screen bg-background">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project", href: `/projects/${projectId}` },
        ...(repoId ? [{ label: selectedRepo?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` }] : []),
        { label: "Pipeline Generator" },
      ]} />

      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* Header Info */}
        <div className="mb-6 p-4 bg-card rounded-lg border border-border">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Generate DevSecOps Pipeline</h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                {selectedRepo ? (
                  <>Repository: <span className="font-medium text-foreground">{selectedRepo.full_name}</span></>
                ) : (
                  "Configure your pipeline requirements below"
                )}
              </p>
            </div>
            {selectedRepo && (
              <div className="text-xs text-muted-foreground bg-secondary px-3 py-1.5 rounded-full w-fit">
                Branch: <span className="font-medium text-foreground">{selectedRepo.default_branch || "main"}</span>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: Form */}
          <div className="lg:col-span-2">
            <RequirementForm
              onGenerate={handleGenerate}
              isLoading={generatePipeline.isPending}
            />
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-3 space-y-4">
            {/* Loading State */}
            {generatePipeline.isPending && (
              <Card className="border-border">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">AI is generating your pipeline</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {GENERATION_STEPS.map((step, i) => {
                    const status =
                      i < currentStageIndex
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
                  <p className="text-xs text-muted-foreground pt-3 border-t border-border mt-2">
                    This usually takes 1–5 minutes depending on repository size.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Ready State */}
            {!pipelineResult && !generatePipeline.isPending && !generationError && (
              <Card className="border-border">
                <CardContent className="py-12">
                  <div className="text-center">
                    <h3 className="font-medium text-foreground mb-1">Ready to Generate</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                      Set your requirements on the left, then click Generate. AI will analyze your repository and create a secure CI/CD pipeline.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Error State */}
            {generationError && (
              <Card className="border-destructive">
                <CardContent className="py-3 text-sm text-destructive bg-destructive/5 rounded-lg">
                  {generationError}
                </CardContent>
              </Card>
            )}

            {/* Generated Result */}
            {pipelineResult && (
              <>
                {/* Compact Repository Context */}
                <Card className="border-border">
                  <CardContent className="py-3 text-sm flex flex-wrap gap-x-4 gap-y-1">
                    <span>
                      <span className="text-muted-foreground">Language: </span>
                      <span className="font-medium">{pipelineResult.analysis?.technologies?.primary_language || "—"}</span>
                    </span>
                    <span>
                      <span className="text-muted-foreground">Framework: </span>
                      <span className="font-medium">
                        {pipelineResult.analysis?.technologies?.frameworks?.join(", ") || "—"}
                      </span>
                    </span>
                    <span>
                      <span className="text-muted-foreground">Architecture: </span>
                      <span className="font-medium capitalize">
                        {pipelineResult.analysis?.architecture?.architecture_type?.replace("_", " ") || "monolithic"}
                      </span>
                    </span>
                  </CardContent>
                </Card>

                {/* Security Coverages (struktur-v9) */}
                {pipelineResult.analysis?.security_requirements?.applicable_coverages?.length > 0 && (
                  <Card className="border-border">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">Security Coverages</CardTitle>
                        <span className="text-xs text-muted-foreground">
                          {pipelineResult.analysis.security_requirements.applicable_coverages.length} applicable
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-1.5">
                      {pipelineResult.analysis.security_requirements.applicable_coverages.map((c: any, i: number) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 p-2 rounded-md border text-sm bg-blue-50 text-blue-800 border-blue-200"
                        >
                          <span className="font-bold text-base leading-none mt-0.5">●</span>
                          <div className="flex-1 min-w-0">
                            <span className="font-medium">{c.id}</span>
                            {c.reason && (
                              <p className="text-xs mt-0.5 text-muted-foreground">{c.reason}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Security Controls - emitted only (excluding merged/optional) */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">Security Controls</CardTitle>
                      <span className="text-xs text-muted-foreground">
                        {(() => {
                          const controls = (pipelineResult.analysis?.security_requirements?.security_controls || [])
                            .filter((c: any) => c.status === "recommended")
                          return `${controls.length} applied`
                        })()}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {(() => {
                      const controls = (pipelineResult.analysis?.security_requirements?.security_controls || [])
                        .filter((c: any) => c.status === "recommended")
                      if (controls.length === 0) {
                        return <p className="text-sm text-muted-foreground">No security controls applied</p>
                      }
                      return (
                        <div className="grid grid-cols-1 gap-2">
                          {controls.map((c: any, i: number) => (
                            <div
                              key={i}
                              className="flex items-center justify-between gap-2 p-2 rounded-md border text-sm bg-green-50 text-green-700 border-green-200"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="font-bold text-base leading-none">✓</span>
                                <span className="font-medium capitalize">
                                  {(c.control || "").replace(/_/g, " ")}
                                </span>
                              </div>
                              {c.tool && (
                                <span className="text-xs text-muted-foreground font-mono shrink-0">
                                  {c.tool}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )
                    })()}
                  </CardContent>
                </Card>

                {/* Generated Workflow — two-file view (generic + custom) */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">Generated Workflow Files</CardTitle>
                      <span className="text-xs text-muted-foreground">
                        {pipelineResult.workflow_files && pipelineResult.workflow_files.length > 0
                          ? `${pipelineResult.workflow_files.length} file(s)`
                          : `${pipelineResult.stages?.length || 0} stages`}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {pipelineResult.workflow_files && pipelineResult.workflow_files.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {pipelineResult.workflow_files.map((f) => (
                          <span
                            key={f.path}
                            className={
                              "text-xs font-medium px-2.5 py-1 rounded-full border " +
                              (f.kind === "custom"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-blue-50 text-blue-800 border-blue-200")
                            }
                          >
                            {f.name} <span className="opacity-70">({f.jobs.length} jobs)</span>
                          </span>
                        ))}
                      </div>
                    ) : pipelineResult.stages?.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {pipelineResult.stages.map((stage: string) => (
                          <span key={stage} className="text-xs font-medium bg-secondary text-secondary-foreground px-2.5 py-1 rounded-full border border-border">
                            {stage}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <WorkflowFileViewer
                      files={pipelineResult.workflow_files}
                      genericYaml={pipelineResult.workflow_yaml_generic || pipelineResult.workflow_yaml}
                      customYaml={pipelineResult.workflow_yaml_custom || ""}
                    />
                  </CardContent>
                </Card>

                {/* Validation Results */}
                <ValidationResults validation={pipelineResult.validation as ValidationResult} />

                {/* Deploy Button */}
                {pipelineResult.validation?.valid && !deployResult && (
                  <Button onClick={handleDeploy} disabled={deployWorkflow.isPending} className="w-full h-12 text-base" size="lg">
                    {deployWorkflow.isPending ? "Deploying..." : "Deploy to GitHub via PR"}
                  </Button>
                )}

                {/* Deploy Result */}
                {deployResult && (
                  <div className="space-y-3">
                    <PRLink
                      prUrl={deployResult.pr_url}
                      prNumber={deployResult.pr_number}
                      branch={deployResult.branch}
                    />
                    {deployResult.workflow_files && deployResult.workflow_files.length > 0 && (
                      <Card className="border-border">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-sm font-medium">Committed Workflow Files</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1.5">
                          {deployResult.workflow_files.map((f) => (
                            <div
                              key={f.path}
                              className="flex items-center justify-between text-xs p-2 rounded-md border border-border bg-muted/30"
                            >
                              <span className="font-mono">{f.path}</span>
                              <span
                                className={
                                  "text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border " +
                                  (f.kind === "custom"
                                    ? "bg-amber-50 text-amber-700 border-amber-200"
                                    : "bg-blue-50 text-blue-700 border-blue-200")
                                }
                              >
                                {f.kind}
                              </span>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    )}
                    {deployResult.errors.length > 0 && (
                      <Card className="border-destructive">
                        <CardContent className="text-sm text-destructive bg-destructive/5 py-3">
                          {deployResult.errors.join("; ")}
                        </CardContent>
                      </Card>
                    )}
                    {deployResult.success && (
                      <Button
                        onClick={() => {
                          const id = selectedRepo?.id || repos?.[0]?.id
                          const version = deployResult.pipeline_version
                          if (id && version) {
                            navigate(`/projects/${projectId}/repos/${id}/pipelines/${version}`)
                          } else if (id) {
                            navigate(`/projects/${projectId}/repos/${id}`)
                          }
                        }}
                        className="w-full h-12 text-base"
                        size="lg"
                        variant="outline"
                      >
                        View Pipeline Detail
                      </Button>
                    )}
                  </div>
                )}

                {/* Subject runs panel — pulls from the latest workflow run so the
                    user can see per-job status (id, name, conclusion) and the
                    total / successful / failed / skipped counters. */}
                {selectedRepo?.full_name && (
                  <Card className="border-border">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-medium">Subject Runs (per job ID)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <LatestRunSubjectRuns repositoryId={selectedRepo.full_name} />
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
