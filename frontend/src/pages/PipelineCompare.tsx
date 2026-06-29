import { useState } from "react"
import { useParams } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useRepositoryPipelines, useComparePipelines, type CompareResult } from "@/hooks/usePipelinesV2"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import Header from "@/components/Header"
import { ArrowUpDown, CheckCircle2, AlertTriangle, MinusCircle } from "lucide-react"

export default function PipelineCompare() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>()
  const { data: pipelines } = useRepositoryPipelines(repoId)
  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)
  const compareMutation = useComparePipelines()
  const [leftVersion, setLeftVersion] = useState("")
  const [rightVersion, setRightVersion] = useState("")
  const [result, setResult] = useState<CompareResult | null>(null)

  const handleCompare = () => {
    if (!leftVersion || !rightVersion || leftVersion === rightVersion) return
    const leftPipeline = pipelines?.find((p) => p.version_number === parseInt(leftVersion))
    const rightPipeline = pipelines?.find((p) => p.version_number === parseInt(rightVersion))
    if (!leftPipeline || !rightPipeline) return
    compareMutation.mutate(
      { pipeline_a_id: leftPipeline.id, pipeline_b_id: rightPipeline.id },
      { onSuccess: setResult }
    )
  }

  const getDeltaIcon = (value: number, higherIsBetter: boolean) => {
    if (value === 0) return <MinusCircle className="h-4 w-4 text-gray-400" />
    return value > 0 === higherIsBetter
      ? <CheckCircle2 className="h-4 w-4 text-green-500" />
      : <AlertTriangle className="h-4 w-4 text-red-500" />
  }

  const getDeltaClass = (value: number, higherIsBetter: boolean) => {
    if (value === 0) return "text-gray-500"
    return value > 0 === higherIsBetter ? "text-green-600" : "text-red-600"
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` },
        { label: "Compare" },
      ]} />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <Card>
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
              <div className="md:col-span-2">
                <label className="text-sm font-medium mb-1 block">Pipeline A</label>
                <select
                  value={leftVersion}
                  onChange={(e) => setLeftVersion(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm"
                >
                  <option value="">Select version...</option>
                  {pipelines?.map((p) => (
                    <option key={p.id} value={p.version_number}>
                      #{p.version_number} — {new Date(p.created_at).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-center">
                <ArrowUpDown className="h-6 w-6 text-gray-400" />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium mb-1 block">Pipeline B</label>
                <select
                  value={rightVersion}
                  onChange={(e) => setRightVersion(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm"
                >
                  <option value="">Select version...</option>
                  {pipelines?.map((p) => (
                    <option key={p.id} value={p.version_number}>
                      #{p.version_number} — {new Date(p.created_at).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <Button className="mt-4 w-full" onClick={handleCompare}
              disabled={!leftVersion || !rightVersion || leftVersion === rightVersion || compareMutation.isPending}>
              {compareMutation.isPending ? "Comparing..." : "Compare"}
            </Button>
          </CardContent>
        </Card>

        {result && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Risk Score", key: "risk_score", higherBetter: false },
                { label: "Compliance Score", key: "compliance_score", higherBetter: true },
                { label: "Security Coverage", key: "security_coverage", higherBetter: true },
                { label: "Workflow Quality", key: "workflow_quality", higherBetter: true },
              ].map((m) => {
                const deltaVal = (result.deltas as any)[m.key] ?? 0
                return (
                  <Card key={m.key}>
                    <CardHeader><CardTitle className="text-sm">{m.label}</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">#{(result.pipeline_a as any).version}</span>
                          <span className="font-medium">{(result.pipeline_a as any)[m.key]?.toFixed(1) ?? "-"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">#{(result.pipeline_b as any).version}</span>
                          <span className="font-medium">{(result.pipeline_b as any)[m.key]?.toFixed(1) ?? "-"}</span>
                        </div>
                        <div className="flex justify-between pt-1 border-t">
                          <span className="text-gray-500">Delta</span>
                          <span className={`font-medium flex items-center gap-1 ${getDeltaClass(deltaVal, m.higherBetter)}`}>
                            {getDeltaIcon(deltaVal, m.higherBetter)}
                            {deltaVal.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>

            <Card>
              <CardHeader><CardTitle className="text-sm">Detailed Comparison</CardTitle></CardHeader>
              <CardContent className="p-0">
                <div className="divide-y text-sm">
                  {[
                    { label: "Risk Score", key: "risk_score", higherBetter: false },
                    { label: "Compliance Score", key: "compliance_score", higherBetter: true },
                    { label: "Security Coverage", key: "security_coverage", higherBetter: true },
                    { label: "Workflow Quality", key: "workflow_quality", higherBetter: true },
                    { label: "Execution Success Rate (%)", key: "execution_success_rate", higherBetter: true },
                  ].map((d) => {
                    const deltaVal = (result.deltas as any)[d.key] ?? 0
                    return (
                      <div key={d.key} className="flex items-center justify-between px-4 py-3">
                        <span className="font-medium">{d.label}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-gray-500">#{(result.pipeline_a as any).version}: <strong>{(result.pipeline_a as any)[d.key]?.toFixed(1) ?? "-"}</strong></span>
                          <span className="text-gray-300">→</span>
                          <span className="text-gray-500">#{(result.pipeline_b as any).version}: <strong>{(result.pipeline_b as any)[d.key]?.toFixed(1) ?? "-"}</strong></span>
                          <Badge className={getDeltaClass(deltaVal, d.higherBetter)}>
                            {deltaVal > 0 ? "+" : ""}{deltaVal.toFixed(1)}
                          </Badge>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </main>
    </div>
  )
}
