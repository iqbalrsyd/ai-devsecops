import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { usePipelinesList, useRepositoryPipelines } from "@/hooks/usePipelinesV2"
import { useProjects } from "@/hooks/useProjects"
import { useRepositoryDetail } from "@/hooks/useRepositories"
import Header from "@/components/Header"
import { ChevronLeft, ChevronRight, Search, BarChart3 } from "lucide-react"

export default function PipelineHistory() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const limit = 20

  const { data: projects } = useProjects()
  const { data: repo } = useRepositoryDetail(repoId)
  const project = projects?.find((p) => p.id === projectId)

  const { data, isLoading } = repoId
    ? useRepositoryPipelines(repoId)
    : usePipelinesList({ page, limit })

  const pipelines = Array.isArray(data) ? data : (data as any)?.pipelines || []
  const total = (data as any)?.total || pipelines.length

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={repoId ? [
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project", href: `/projects/${projectId}` },
        { label: repo?.full_name || "Repository", href: `/projects/${projectId}/repos/${repoId}` },
        { label: "Pipeline History" },
      ] : undefined}>
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/compare`)}
          disabled={!repoId}
        >
          <BarChart3 className="h-4 w-4 mr-1" /> Compare
        </Button>
      </Header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search pipelines..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <span className="text-sm text-gray-500">{total} pipelines</span>
        </div>

        {isLoading ? (
          <Card>
            <CardContent className="py-8 text-center text-gray-500">Loading...</CardContent>
          </Card>
        ) : pipelines.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-gray-500">
              No pipelines found.
              {repoId && (
                <div className="mt-3">
                  <Button onClick={() => navigate(`/projects/${projectId}/repos/${repoId}/pipelines/generate`)}>
                    Generate Pipeline
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="divide-y">
                {pipelines
                  .filter((p: any) => (p.repository?.full_name || "").includes(search) || (p.prompt || "").includes(search))
                  .map((p: any) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer"
                      onClick={() => {
                        const pid = p.repository_id || repoId
                        const pjId = projectId || "global"
                        if (pid) {
                          navigate(`/projects/${pjId}/repos/${pid}/pipelines/${p.version_number}`)
                        } else {
                          navigate(`/pipelines/${p.id}`)
                        }
                      }}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <Badge variant="outline" className="w-12">#{p.version_number || p.version}</Badge>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {p.repository?.full_name || "Unknown Repo"}
                          </p>
                          <p className="text-xs text-gray-400 truncate">
                            {p.prompt?.substring(0, 100) || "No prompt"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400">{new Date(p.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}

        {!repoId && total > limit && (
          <div className="flex items-center justify-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-gray-600">Page {page}</span>
            <Button
              size="sm"
              variant="outline"
              disabled={page * limit >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </main>
    </div>
  )
}
