import { useQuery } from "@tanstack/react-query"
import api from "@/lib/axios"

export interface RecentPipeline {
  id: string
  project_id: string
  repository: string
  status: string
  query: string
  stages: string
  created_at: string
  running: boolean
  conclusion: string
  run_id: number | null
  pr_number: number | null
  pr_url: string
}

export interface DashboardStats {
  total_repositories: number
  total_pipelines: number
  total_executions: number
  total_findings: number
  critical_findings: number
  high_findings: number
  avg_risk_score: number
  avg_security_posture: number
  severity_breakdown: Record<string, number>
  recent_pipelines: RecentPipeline[]
}

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const res = await api.get("/dashboard/stats")
      return res.data
    },
    refetchInterval: 30000,
  })
}
