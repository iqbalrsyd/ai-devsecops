import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

import api from "@/lib/axios"

export interface Repository {
  id: string
  project_id: string
  full_name: string
  github_id: string
  default_branch: string
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

interface ConnectRepoInput {
  project_id: string
  github_token: string
  full_name: string
}

export function useRepositoryDetail(id: string | undefined) {
  return useQuery<Repository>({
    queryKey: ["repository-detail", id],
    queryFn: async () => {
      const res = await api.get(`/repositories/${id}`)
      return res.data.repository
    },
    enabled: !!id,
  })
}

export function useRepositories(projectId: string | undefined) {
  return useQuery<Repository[]>({
    queryKey: ["repositories", projectId],
    queryFn: async () => {
      const res = await api.get(`/projects/${projectId}/repositories`)
      return res.data.repositories
    },
    enabled: !!projectId,
  })
}

export function useConnectRepository() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (input: ConnectRepoInput) => {
      const res = await api.post("/repositories/connect", input)
      return res.data.repository
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["repositories", data.project_id] })
    },
  })
}

export function useDeleteRepository() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/repositories/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] })
    },
  })
}