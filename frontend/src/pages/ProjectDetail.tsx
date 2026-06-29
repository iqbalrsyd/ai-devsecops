import { useState } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"

import ConnectRepoModal from "@/components/ConnectRepoModal"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useProjects } from "@/hooks/useProjects"
import { useRepositories } from "@/hooks/useRepositories"
import { useRepositoryPipelines } from "@/hooks/usePipelinesV2"
import Header from "@/components/Header"
import DeleteProjectModal from "@/components/DeleteProjectModal"
import { Loader2, GitBranch, ArrowRight, Activity, BarChart3, Plus, Trash2 } from "lucide-react"

type Tab = "overview" | "repositories"

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { data: repos, isLoading: reposLoading } = useRepositories(projectId)
  const [tab, setTab] = useState<Tab>("overview")

  const project = projects?.find((p) => p.id === projectId)

  const [deleteOpen, setDeleteOpen] = useState(false)

  const tabs: { key: Tab; label: string; icon: typeof Activity }[] = [
    { key: "overview", label: "Overview", icon: Activity },
    { key: "repositories", label: "Repositories", icon: GitBranch },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: project?.name || "Project" },
      ]}>
        <Button variant="outline" size="sm" onClick={() => setDeleteOpen(true)}>
          <Trash2 className="h-4 w-4 mr-1" /> Delete
        </Button>
      </Header>

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
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Project Info</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">{project?.description || "No description"}</p>
                {repos && repos.length > 0 && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
                    <GitBranch className="h-4 w-4" />
                    <span>{repos.length} connected {repos.length === 1 ? "repository" : "repositories"}</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {repos && repos.length > 0 && (
              <>
                <h3 className="font-medium">Repositories</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {repos.map((repo) => (
                    <RepoCard
                      key={repo.id}
                      repoId={repo.id}
                      projectId={projectId!}
                      name={repo.full_name}
                      branch={repo.default_branch}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {tab === "repositories" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Connected Repositories</h3>
              <ConnectRepoModalButton projectId={projectId!} />
            </div>
            {reposLoading ? (
              <div className="text-center py-8 text-gray-500"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></div>
            ) : !repos || repos.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center py-12 text-gray-400">
                  <GitBranch className="h-10 w-10 mb-3" />
                  <p>No repositories connected</p>
                  <p className="text-sm mt-1">Connect a GitHub repository to get started</p>
                  <ConnectRepoModalButton projectId={projectId!} />
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {repos.map((repo) => (
                  <Card key={repo.id} className="hover:shadow-sm cursor-pointer"
                    onClick={() => navigate(`/projects/${projectId}/repos/${repo.id}`)}>
                    <CardContent className="flex items-center justify-between py-3 px-4">
                      <div className="flex items-center gap-3">
                        <GitBranch className="h-5 w-5 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium">{repo.full_name}</p>
                          <p className="text-xs text-gray-400">{repo.default_branch}</p>
                        </div>
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

      <DeleteProjectModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        projectId={projectId!}
        projectName={project?.name || "this project"}
      />
    </div>
  )
}

function RepoCard({ repoId, projectId, name, branch }: { repoId: string; projectId: string; name: string; branch: string }) {
  const { data: pipelines } = useRepositoryPipelines(repoId)
  return (
    <Link to={`/projects/${projectId}/repos/${repoId}`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-gray-400" />
            <p className="font-medium">{name}</p>
          </div>
          <div className="mt-3 flex items-center gap-4 text-sm text-gray-500">
            <span>{branch}</span>
            <span>·</span>
            <span>{pipelines?.length || 0} pipelines</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function ConnectRepoModalButton({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4 mr-1" /> Connect Repository
      </Button>
      <ConnectRepoModal projectId={projectId} open={open} onOpenChange={setOpen} />
    </>
  )
}
