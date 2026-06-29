import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import { useRepositoryPipelines } from "@/hooks/usePipelinesV2"
import { useProjects } from "@/hooks/useProjects"
import Header from "@/components/Header"
import { ArrowRight, GitBranch, Globe, BarChart3, Shield, Activity } from "lucide-react"

type Tab = "overview" | "pipelines"

export default function RepoDetailPage() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>("overview")
  const { data: repo } = useRepositoryDetail(repoId)
  const { data: pipelines } = useRepositoryPipelines(repoId)
  const { data: projects } = useProjects()
  const project = projects?.find((p) => p.id === projectId)

  const latestPipeline = pipelines && pipelines.length > 0 ? pipelines[0] : null

  const tabs: { key: Tab; label: string; icon: typeof Activity }[] = [
    { key: "overview", label: "Overview", icon: Activity },
    { key: "pipelines", label: "Pipelines", icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || repo?.full_name?.split("/")[0] || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || "Repository" },
      ]} />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
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

        {tab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle className="text-sm">Repository Info</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-gray-400" />
                    <span>{repo?.full_name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-gray-400" />
                    <span>{repo?.default_branch || "main"}</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm">Quick Actions</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  <Button className="w-full justify-start" variant="outline"
                    onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/generate`)}>
                    <Shield className="h-4 w-4 mr-2" /> Generate Pipeline
                  </Button>
                  <Button className="w-full justify-start" variant="outline"
                    onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines`)}>
                    <BarChart3 className="h-4 w-4 mr-2" /> View All Pipelines
                  </Button>
                </CardContent>
              </Card>
            </div>
            {latestPipeline && (
              <Card>
                <CardHeader><CardTitle className="text-sm flex items-center justify-between">
                  <span>Latest Pipeline — #{latestPipeline.version_number}</span>
                  <Badge>{latestPipeline.status}</Badge>
                </CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                    {latestPipeline.prompt?.substring(0, 200)}
                  </p>
                  <Button size="sm" variant="outline"
                    onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/${latestPipeline.version_number}`)}>
                    View Details <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {tab === "pipelines" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">All Pipeline Versions</h3>
              <Button size="sm" onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/generate`)}>
                Generate New
              </Button>
            </div>
            {!pipelines || pipelines.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-sm text-gray-500">No pipelines generated yet.</CardContent></Card>
            ) : (
              <div className="space-y-2">
                {pipelines.map((p) => (
                  <Card key={p.id} className="hover:shadow-sm cursor-pointer"
                    onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/${p.version_number}`)}>
                    <CardContent className="flex items-center justify-between py-3 px-4">
                      <div className="flex items-center gap-3">
                        <Badge variant="outline">#{p.version_number}</Badge>
                        <span className="text-sm text-gray-600">{p.status}</span>
                        <span className="text-xs text-gray-400">{new Date(p.created_at).toLocaleDateString()}</span>
                      </div>
                      <ArrowRight className="h-4 w-4 text-gray-400" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}


      </main>
    </div>
  )
}
