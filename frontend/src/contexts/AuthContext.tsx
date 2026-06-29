import { createContext, useState, useCallback, useEffect, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import api from "@/lib/axios"

export interface User {
  id: string
  email: string
  name: string
  role: string
}

export interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

async function fetchUser(): Promise<User> {
  const res = await api.get("/me")
  return res.data.user || res.data
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("access_token"))
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const {
    data: user,
    isLoading,
  } = useQuery<User>({
    queryKey: ["user"],
    queryFn: fetchUser,
    enabled: !!token,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (token) {
      localStorage.setItem("access_token", token)
    } else {
      localStorage.removeItem("access_token")
    }
  }, [token])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post("/auth/login", { email, password })
    const { access_token } = res.data
    setToken(access_token)
    await queryClient.invalidateQueries({ queryKey: ["user"] })
    navigate("/dashboard")
  }, [navigate, queryClient])

  const register = useCallback(async (name: string, email: string, password: string) => {
    await api.post("/auth/register", { name, email, password })
    navigate("/login")
  }, [navigate])

  const logout = useCallback(() => {
    setToken(null)
    queryClient.setQueryData(["user"], null)
    queryClient.removeQueries({ queryKey: ["user"] })
    // Clear the client-side GitHub token cache so it doesn't linger
    // past the session. The encrypted copy in the backend is
    // unaffected and survives logout.
    try {
      localStorage.removeItem("github_token")
    } catch {
      // ignore
    }
    navigate("/login")
  }, [navigate, queryClient])

  return (
    <AuthContext.Provider
      value={{
        user: user ?? null,
        token,
        isLoading: !!token && isLoading,
        isAuthenticated: !!token,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}