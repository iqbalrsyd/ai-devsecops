import axios from "axios"

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1"

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  // No client-side timeout. The /pipeline/analyze endpoint can
  // take several minutes when the AI agent re-runs on a fresh
  // log (LLM call + scanner artifact download + CVSS lookup).
  // A 90s ceiling caused the spinner to fail with "timeout
  // exceeded" even though the request was still in flight on
  // the server, which was misleading. The server still has
  // its own internal timeouts; if the AI service itself is
  // hung the request will fail there, not here.
  timeout: 0,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Single-flight refresh: if multiple 401s arrive at once we
// only call /auth/refresh once and share the result.
let refreshInflight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token")
  if (!refreshToken) return null
  if (refreshInflight) return refreshInflight
  refreshInflight = (async () => {
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      const newAccess = res.data?.access_token
      const newRefresh = res.data?.refresh_token
      if (newAccess) localStorage.setItem("access_token", newAccess)
      if (newRefresh) localStorage.setItem("refresh_token", newRefresh)
      return newAccess || null
    } catch {
      // Refresh failed (expired or revoked). Clear tokens so the
      // AuthContext redirects the user to /login on the next render.
      try {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
      } catch {
        // ignore
      }
      return null
    } finally {
      refreshInflight = null
    }
  })()
  return refreshInflight
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    // Only attempt refresh on 401 and only once per request to avoid
    // infinite loops on permanently-revoked tokens.
    if (status === 401 && original && !original.__isRetry) {
      original.__isRetry = true
      const newToken = await refreshAccessToken()
      if (newToken) {
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newToken}`
        return api.request(original)
      }
    }
    const message = error.response?.data?.error || error.response?.data?.message || error.message || "An error occurred"
    return Promise.reject(new Error(message))
  }
)

export default api
