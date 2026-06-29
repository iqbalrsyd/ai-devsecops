import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useProjects } from "@/hooks/useProjects"
import { useDashboardStatsV2 } from "@/hooks/usePipelinesV2"

import Header from "@/components/Header"
import NewProjectModal from "@/components/NewProjectModal"
import { Plus, FolderOpen, GitPullRequest, CheckCircle2, XCircle, Loader2, Clock, ArrowRight, BarChart3, Shield, Activity } from "lucide-react"
import type { ReactNode } from "react"

function StatCard({ icon, label, value, color }: { icon: ReactNode; label: string; value: string | number; color: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
        </div>
        <p className="text-2xl font-bold mt-3">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  )
}

function ProgressStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium">{label}</p>
          <p className="text-lg font-bold">{value.toFixed(1)}%</p>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { data: stats, isLoading } = useDashboardStatsV2()
  const [projectModalOpen, setProjectModalOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50">
      <Header>
        <Button onClick={() => setProjectModalOpen(true)} size="sm">
          <Plus className="h-4 w-4 mr-1" /> New Project
        </Button>
      </Header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Loading dashboard...</div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard
                icon={<FolderOpen className="h-5 w-5 text-blue-600" />}
                label="Total Projects"
                value={stats?.total_projects ?? 0}
                color="bg-blue-100"
              />
              <StatCard
                icon={<GitPullRequest className="h-5 w-5 text-purple-600" />}
                label="Total Repositories"
                value={stats?.total_repositories ?? 0}
                color="bg-purple-100"
              />
              <StatCard
                icon={<BarChart3 className="h-5 w-5 text-green-600" />}
                label="Total Pipelines"
                value={stats?.total_pipelines ?? 0}
                color="bg-green-100"
              />
              <StatCard
                icon={<Activity className="h-5 w-5 text-orange-600" />}
                label="Total Executions"
                value={stats?.total_executions ?? 0}
                color="bg-orange-100"
              />
            </div>

            {/* Progress Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <ProgressStat
                label="Pipeline Success Rate"
                value={stats?.pipeline_success_rate ?? 0}
                color="bg-green-500"
              />
              <ProgressStat
                label="Avg Risk Score"
                value={100 - (stats?.avg_risk_score ?? 0)}
                color={stats && stats.avg_risk_score < 30 ? "bg-green-500" : stats && stats.avg_risk_score < 60 ? "bg-yellow-500" : "bg-red-500"}
              />
              <ProgressStat
                label="Avg Compliance Score"
                value={stats?.avg_compliance_score ?? 0}
                color={stats && stats.avg_compliance_score >= 70 ? "bg-green-500" : stats && stats.avg_compliance_score >= 40 ? "bg-yellow-500" : "bg-red-500"}
              />
              <ProgressStat
                label="Avg Security Coverage"
                value={stats?.avg_security_coverage ?? 0}
                color={stats && stats.avg_security_coverage >= 70 ? "bg-green-500" : stats && stats.avg_security_coverage >= 40 ? "bg-yellow-500" : "bg-red-500"}
              />
            </div>

            {/* Projects Section */}
            <h2 className="text-lg font-semibold">Projects</h2>

            {!projects || projects.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <FolderOpen className="h-10 w-10 mb-3" />
                  <p className="mb-1">No projects yet</p>
                  <p className="text-sm">Create a project to get started</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {projects.map((project) => (
                  <Link key={project.id} to={`/projects/${project.id}`}>
                    <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                      <CardHeader>
                        <CardTitle className="text-base">{project.name}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {project.description || "No description"}
                        </p>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            )}

            {/* Recent Pipelines */}
            {stats?.recent_pipelines && stats.recent_pipelines.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Recent Pipelines</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y">
                    {stats.recent_pipelines.slice(0, 10).map((p) => (
                      <div key={p.id} className="flex items-center gap-3 px-4 py-3">
                        <Shield className="h-4 w-4 text-blue-500 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium">
                            #{p.version} — {p.repository}
                          </span>
                          <p className="text-xs text-muted-foreground">{p.status} · {new Date(p.created_at).toLocaleDateString()}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>

      <NewProjectModal open={projectModalOpen} onOpenChange={setProjectModalOpen} onSuccess={(project) => navigate(`/projects/${project.id}`)} />
    </div>
  )
}
