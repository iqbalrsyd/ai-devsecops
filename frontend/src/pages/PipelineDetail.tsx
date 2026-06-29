import { useState, useEffect, useMemo } from "react"
import { useParams, Link, useSearchParams, useLocation, useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useExecutionStatus, useExecuteWorkflow, useLatestWorkflowRun, useNodeSpecs } from "@/hooks/usePipeline"
import { useSyncRuns } from "@/hooks/usePipelinesV2"
import ExecutionTimeline from "@/components/ExecutionTimeline"
import PrLink from "@/components/PRLink"
import NodeSpecCard from "@/components/NodeSpecCard"
import { Loader2, Play, ArrowRight, BarChart3, AlertTriangle, XCircle, Bug, GitPullRequest, CheckCircle2, Clock, RefreshCw, Layers } from "lucide-react"

function PipelineNodesSection({ tahaps }: { tahaps: number[] }) {
  const { data: nodes, isLoading } = useNodeSpecs(tahaps)
  const grouped: Record<number, NonNullable<typeof nodes>> = {}
  for (const n of nodes ?? []) {
    if (!n) continue
    if (!grouped[n.tahap]) grouped[n.tahap] = [] as NonNullable<typeof nodes>
    grouped[n.tahap]!.push(n)
  }

  const TAHAP_LABELS: Record<number, string> = {
    1: "Repository Context Analysis",
    2: "Security Coverage Inference",
    3: "Pipeline Generation & Deployment",
    4: "Security Evaluation",
  }

  return (
    <Card className="mt-6 border-t-4 border-t-indigo-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-500" />
            Pipeline Nodes (Tahap 1-3) — Input/Output per Node
          </CardTitle>
          <span className="text-[10px] text-gray-500">
            {nodes?.length ?? 0} nodes · click to expand
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Reference for the v9.3 compiled graph. Each card shows the
          function, state inputs, state outputs, LLM prompt (if any),
          fallback, source file, and the struktur-v9 spec reference.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {isLoading && (
          <p className="text-xs text-muted-foreground">Loading node specs…</p>
        )}
        {!isLoading &&
          Object.keys(grouped)
            .map(Number)
            .sort()
            .map((t) => (
              <div key={t}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-bold uppercase text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                    Tahap {t}
                  </span>
                  <span className="text-xs font-medium text-gray-700">
                    {TAHAP_LABELS[t] || `Tahap ${t}`}
                  </span>
                  <span className="text-[10px] text-gray-400">
                    ({grouped[t]?.length ?? 0} nodes)
                  </span>
                </div>
                <div className="space-y-2">
                  {(grouped[t] ?? []).map((n) => (
                    <NodeSpecCard key={n.id} node={n} />
                  ))}
                </div>
              </div>
            ))}
      </CardContent>
    </Card>
  )
}

export default function PipelineDetail() {
  const { id: projectId, runId: runIdParam } = useParams<{ id: string; runId?: string }>()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const locationState = location.state as {
    repoName?: string
    deployInfo?: { branch: string; pr_number: number; pr_url: string }
    yaml?: string
  } | null
  const executeWorkflow = useExecuteWorkflow()

  const repoNameFromUrl = searchParams.get("repo") || locationState?.repoName || ""
  const deployInfo = locationState?.deployInfo
  const deployYaml = locationState?.yaml

  const numericRunId = useMemo(() => {
    if (!runIdParam) return null
    const parsed = parseInt(runIdParam)
    return Number.isNaN(parsed) ? null : parsed
  }, [runIdParam])

  const [repoName, setRepoName] = useState(repoNameFromUrl)
  const [workflowRunId, setWorkflowRunId] = useState<number | null>(numericRunId)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)
  const syncRuns = useSyncRuns()
  const queryClient = useQueryClient()
  const [execResult, setExecResult] = useState<{ run_id: number; status: string; errors?: string[] } | null>(null)

  // Sync repoName when URL query param changes (component may not remount)
  useEffect(() => {
    setRepoName(repoNameFromUrl)
  }, [repoNameFromUrl])

  // Reset state when navigating to a different repo in monitor mode
  useEffect(() => {
    if (!numericRunId) {
      setWorkflowRunId(null)
      setExecResult(null)
    }
  }, [repoName, numericRunId])

  const { data: latestRun } = useLatestWorkflowRun(
    !workflowRunId && repoName ? repoName : "",
  )

  useEffect(() => {
    if (latestRun?.run_id && !workflowRunId) {
      setWorkflowRunId(latestRun.run_id)
    }
  }, [latestRun, workflowRunId])

  const { data: executionStatus, isLoading: statusLoading } = useExecutionStatus(
    repoName,
    workflowRunId,
  )

  const handleExecute = async () => {
    let repo = repoName
    if (!repo) {
      const input = prompt("Enter repository full name (e.g., my-org/my-app):")
      if (!input) return
      repo = input
      setRepoName(input)
    }
    const result = await executeWorkflow.mutateAsync({ repository_id: repo })
    setWorkflowRunId(result.run_id)
    setExecResult(result)
  }

  const handleSync = async () => {
    if (!repoName) return
    setIsSyncing(true)
    setSyncMsg(null)
    try {
      const result = await syncRuns.mutateAsync({
        repoId: repoName,
        version: numericRunId || 0,
      })
      const synced = (result as { synced?: string[]; message?: string }).synced || []
      setSyncMsg(
        synced.length > 0
          ? `Synced ${synced.length} run(s): ${synced.join(", ")}`
          : (result as { message?: string }).message || "No new runs found",
      )
      queryClient.invalidateQueries({ queryKey: ["runs", repoName] })
    } catch (e) {
      setSyncMsg(`Sync failed: ${e instanceof Error ? e.message : "unknown"}`)
    } finally {
      setIsSyncing(false)
    }
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto">
        <Link to="/dashboard" className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-block">
          &larr; Back to Dashboard
        </Link>

        <div className="mb-6">
          <h1 className="text-3xl font-bold">
            {repoName ? (
              <>{repoName}{numericRunId ? ` — Run #${numericRunId}` : deployInfo ? ` — PR #${deployInfo.pr_number}` : ''}</>
            ) : (
              'Pipeline Detail'
            )}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            {executionStatus && (
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                executionStatus.conclusion === 'success' ? 'bg-green-100 text-green-700' :
                executionStatus.conclusion === 'failure' ? 'bg-red-100 text-red-700' :
                executionStatus.status === 'in_progress' || executionStatus.status === 'queued' ? 'bg-blue-100 text-blue-700' :
                'bg-yellow-100 text-yellow-700'
              }`}>
                {executionStatus.conclusion === 'success' ? <CheckCircle2 className="h-3 w-3" /> :
                 executionStatus.conclusion === 'failure' ? <XCircle className="h-3 w-3" /> :
                 executionStatus.status === 'in_progress' ? <Loader2 className="h-3 w-3 animate-spin" /> :
                 <Clock className="h-3 w-3" />}
                {executionStatus.conclusion || executionStatus.status}
              </span>
            )}
            {!workflowRunId && deployInfo && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                <GitPullRequest className="h-3 w-3" />
                Deployed
              </span>
            )}
            {!workflowRunId && !deployInfo && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                <Clock className="h-3 w-3" />
                Waiting
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {!workflowRunId && (
              <>
                {deployInfo ? (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <GitPullRequest className="h-4 w-4" />
                        Pipeline Deployed
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-muted-foreground">
                        Workflow has been deployed to <strong>{repoName}</strong> via PR.
                      </p>
                      <div className="flex items-center gap-2">
                        {deployInfo.pr_url && (
                          <a href={deployInfo.pr_url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">
                            View PR #{deployInfo.pr_number} on GitHub &rarr;
                          </a>
                        )}
                      </div>
                      {deployYaml && (
                        <details className="text-sm">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            View Deployed Workflow YAML
                          </summary>
                          <pre className="mt-2 bg-muted rounded-lg p-3 text-xs overflow-x-auto max-h-64">
                            <code>{deployYaml}</code>
                          </pre>
                        </details>
                      )}
                      <div className="pt-2">
                        <p className="text-sm text-muted-foreground mb-2">
                          Merge the PR or trigger the workflow to start execution:
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button onClick={handleExecute} disabled={executeWorkflow.isPending}>
                            {executeWorkflow.isPending ? (
                              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Triggering...</>
                            ) : (
                              <><Play className="h-4 w-4 mr-2" /> Trigger Workflow</>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={handleSync}
                            disabled={isSyncing}
                          >
                            {isSyncing ? (
                              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Syncing...</>
                            ) : (
                              <><RefreshCw className="h-4 w-4 mr-2" /> Sync from GitHub</>
                            )}
                          </Button>
                        </div>
                        {syncMsg && (
                          <p className="text-xs text-blue-600 mt-2 bg-blue-50 rounded px-2 py-1 border border-blue-200">
                            {syncMsg}
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="py-8">
                      <div className="text-center space-y-3">
                        <p className="text-muted-foreground">No workflow execution in progress</p>
                        <div className="flex flex-wrap items-center justify-center gap-2">
                          <Button onClick={handleExecute} disabled={executeWorkflow.isPending}>
                            {executeWorkflow.isPending ? (
                              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Triggering...</>
                            ) : (
                              <><Play className="h-4 w-4 mr-2" /> Trigger Workflow</>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={handleSync}
                            disabled={isSyncing}
                          >
                            {isSyncing ? (
                              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Syncing...</>
                            ) : (
                              <><RefreshCw className="h-4 w-4 mr-2" /> Sync from GitHub</>
                            )}
                          </Button>
                        </div>
                        {syncMsg && (
                          <p className="text-xs text-blue-600 mt-2 bg-blue-50 rounded px-2 py-1 border border-blue-200">
                            {syncMsg}
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {execResult && execResult.run_id && !numericRunId && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Workflow Triggered</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">
                    Workflow dispatched. Run ID: {execResult.run_id}
                  </p>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/projects/${projectId}/pipeline/${execResult.run_id}`}>
                      Monitor Execution <ArrowRight className="h-3 w-3 ml-1" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}

            {executionStatus && (
              <ExecutionTimeline jobs={executionStatus.jobs || []} />
            )}

            <PipelineNodesSection tahaps={[1, 2, 3]} />
          </div>

          <div className="space-y-4">
            {executionStatus && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Run ID</span>
                      <span className="font-mono">{executionStatus.run_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status</span>
                      <span className="font-medium capitalize">{executionStatus.status}</span>
                    </div>
                    {executionStatus.conclusion && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Conclusion</span>
                        <span className="font-medium capitalize">{executionStatus.conclusion}</span>
                      </div>
                    )}
                    {executionStatus.duration_seconds && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Duration</span>
                        <span>{executionStatus.duration_seconds}s</span>
                      </div>
                    )}
                    {executionStatus.html_url && (
                      <a
                        href={executionStatus.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline text-sm block mt-2"
                      >
                        View on GitHub &rarr;
                      </a>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* ── Error Analysis ── */}
            {executionStatus && executionStatus.conclusion === "failure" && (
              <Card className="border-red-200">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base text-red-700">
                    <Bug className="h-4 w-4" />
                    Pipeline Failed
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-red-600">
                    Workflow execution failed with conclusion: <strong>{executionStatus.conclusion}</strong>
                  </p>
                </CardContent>
              </Card>
            )}

            {repoName && workflowRunId && (
            <Link to={`/projects/${projectId}/report/${workflowRunId}?repo=${encodeURIComponent(repoName)}`}>
              <Button variant="secondary" className="w-full">
                View Security Report
              </Button>
            </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}