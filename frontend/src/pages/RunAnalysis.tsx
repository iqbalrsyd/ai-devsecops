import { useParams } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useRunAnalysis } from "@/hooks/usePipelinesV2"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import Header from "@/components/Header"
import { Shield, AlertTriangle, CheckCircle2, FileWarning, ArrowLeft } from "lucide-react"

function ScoreGauge({ label, value, max = 100 }: { label: string; value: number | null; max?: number }) {
  const score = value ?? 0
  const pct = (score / max) * 100
  const color = score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500"
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold">{score.toFixed(1)}</span>
          <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">{label}</p>
      </CardContent>
    </Card>
  )
}

interface Finding {
  scanner?: string
  type?: string
  severity?: string
  file?: string
  line?: number
  code_snippet?: string
  explanation?: string
  recommendation?: string
  title?: string
  cvss_score?: number
  cvss_vector?: string
  cvss_severity?: string
  security_coverage?: string
}

export default function RunAnalysis() {
  const { projectId, repoId, runId } = useParams<{ projectId: string; repoId: string; runId: string }>()
  const { data: analysis, isLoading } = useRunAnalysis(runId)
  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading analysis...</p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500 mb-4">Analysis not available yet.</p>
          <p className="text-sm text-gray-400">Execute the pipeline first, then analysis will be generated automatically.</p>
        </div>
      </div>
    )
  }

  const findings: Finding[] = analysis.findings_summary ? JSON.parse(analysis.findings_summary as string) : []
  const severity: Record<string, number> = analysis.severity_breakdown ? JSON.parse(analysis.severity_breakdown as string) : {}
  const recommendations: any[] = analysis.recommendations ? JSON.parse(analysis.recommendations as string) : []

  const severityColors: Record<string, string> = {
    critical: "bg-red-100 text-red-800 border-red-300",
    high: "bg-orange-100 text-orange-800 border-orange-300",
    medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
    low: "bg-blue-100 text-blue-800 border-blue-300",
  }

  type SeverityKey = "critical" | "high" | "medium" | "low"

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` },
        { label: "Analysis" },
      ]} />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Score Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <ScoreGauge label="Risk Score" value={analysis.risk_score} />
          <ScoreGauge label="Compliance Score" value={analysis.compliance_score} />
          <ScoreGauge label="Security Coverage" value={analysis.security_coverage_score} />
          <ScoreGauge label="Workflow Quality" value={analysis.workflow_quality_score} />
        </div>

        {/* Severity Breakdown */}
        {Object.keys(severity).length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-sm">Severity Breakdown</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-4">
                {(["critical", "high", "medium", "low"] as SeverityKey[]).map((sev) => (
                  <div key={sev} className="text-center p-3 rounded-lg border" style={{
                    backgroundColor: sev === "critical" ? "#fef2f2" : sev === "high" ? "#fff7ed" : sev === "medium" ? "#fefce8" : "#eff6ff",
                    borderColor: sev === "critical" ? "#fecaca" : sev === "high" ? "#fed7aa" : sev === "medium" ? "#fef08a" : "#bfdbfe",
                  }}>
                    <p className="text-lg font-bold capitalize">{severity[sev] ?? 0}</p>
                    <p className="text-xs text-gray-600 capitalize">{sev}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* AI Explanation */}
        {analysis.ai_explanation && (
          <Card>
            <CardHeader><CardTitle className="text-sm flex items-center gap-2">
              <Shield className="h-4 w-4" /> AI Analysis
            </CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{analysis.ai_explanation}</p>
            </CardContent>
          </Card>
        )}

        {/* Findings Table */}
        {findings.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <FileWarning className="h-4 w-4" />
                Security Findings ({findings.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y">
                {findings.map((f, i) => (
                  <div key={i} className="px-4 py-4 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <Badge className={severityColors[f.severity?.toLowerCase() || "medium"]}>
                            {f.severity || "medium"}
                          </Badge>
                          <span className="text-sm font-medium">{f.title || f.type || "Finding"}</span>
                          {f.scanner && (
                            <Badge variant="outline">{f.scanner}</Badge>
                          )}
                          {typeof f.cvss_score === "number" && (
                            <span
                              className="text-[10px] font-mono bg-orange-100 text-orange-800 border border-orange-300 px-1.5 py-0.5 rounded whitespace-nowrap"
                              title={f.cvss_vector || "CVSS 3.1 (estimated)"}
                            >
                              CVSS {f.cvss_score.toFixed(1)}
                              {f.cvss_severity ? ` · ${f.cvss_severity}` : ""}
                            </span>
                          )}
                          {f.security_coverage && (
                            <span className="text-[10px] font-mono bg-purple-100 text-purple-800 border border-purple-300 px-1.5 py-0.5 rounded">
                              {f.security_coverage}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{f.explanation || ""}</p>
                      </div>
                    </div>
                    {(f.file || f.line) && (
                      <div className="text-xs font-mono bg-gray-100 rounded px-2 py-1 text-gray-700">
                        {f.file && <span>{f.file}</span>}
                        {f.line && <span>{f.file ? ":" : ""}{f.line}</span>}
                      </div>
                    )}
                    {f.recommendation && (
                      <div className="flex items-start gap-1 text-xs text-blue-700 bg-blue-50 rounded px-2 py-1">
                        <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0" />
                        <span>{f.recommendation}</span>
                      </div>
                    )}
                    {f.code_snippet && (
                      <pre className="text-xs bg-gray-900 text-green-400 rounded p-2 overflow-x-auto">
                        {f.code_snippet}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recommendations */}
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
                {recommendations.map((rec: any, i: number) => (
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
      </main>
    </div>
  )
}
