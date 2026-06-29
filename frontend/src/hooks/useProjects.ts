import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

import api from "@/lib/axios"

export interface Project {
  id: string
  name: string
  description: string
  user_id: string
  compliance_tier: string
  created_at: string
  updated_at: string
}

interface CreateProjectInput {
  name: string
  description: string
}

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const res = await api.get("/projects")
      return res.data.projects
    },
  })
}

export function useProject(id: string) {
  const projects = useProjects()
  return {
    ...projects,
    data: projects.data?.find((p) => p.id === id) ?? null,
  }
}

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (input: CreateProjectInput) => {
      const res = await api.post("/projects", input)
      return res.data.project
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/projects/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useProjectById(id: string | undefined) {
  return useQuery<Project | null>({
    queryKey: ["project", id],
    queryFn: async () => {
      if (!id) return null
      const res = await api.get(`/projects/${id}`)
      return res.data.project
    },
    enabled: !!id,
  })
}

export function useUpdateComplianceTier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ projectId, tier }: { projectId: string; tier: string }) => {
      const res = await api.put(`/projects/${projectId}/compliance`, { tier })
      return res.data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["project", variables.projectId] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}