export { AuthProvider, AuthContext } from "@/contexts/AuthContext"
export type { User, AuthContextType } from "@/contexts/AuthContext"

import { useContext } from "react"
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext"

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}