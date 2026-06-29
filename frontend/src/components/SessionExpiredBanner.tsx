import { AlertTriangle, LogIn } from "lucide-react"

import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"

/**
 * SessionExpiredBanner
 *
 * Surfaces a non-dismissible banner at the top of the app when
 * the access token has expired AND the refresh-token flow has
 * failed (token revoked, refresh window closed, or no refresh
 * token was ever stored). The banner carries a "Sign in again"
 * CTA that calls `goToLogin()` from the AuthContext — which
 * clears the in-memory state and routes the user to /login
 * without losing the current page.
 *
 * Why this exists: the previous behavior silently booted the
 * user to /login on the next render after a failed refresh.
 * That was jarring because the user had no idea why they were
 * suddenly staring at the login form. The banner gives them a
 * clear cause-and-effect: "Your session has expired" →
 * "Sign in again".
 */
export default function SessionExpiredBanner() {
  const { sessionExpired, goToLogin } = useAuth()

  if (!sessionExpired) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="session-expired-banner"
      className="sticky top-0 z-50 w-full border-b border-amber-300 bg-amber-50 text-amber-900 shadow-sm"
    >
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <span className="font-semibold">Your session has expired.</span>{" "}
          <span className="text-amber-800/90">
            Please sign in again to continue.
          </span>
        </div>
        <Button
          size="sm"
          variant="default"
          onClick={goToLogin}
          className="shrink-0 gap-1.5 bg-amber-900 text-amber-50 hover:bg-amber-800"
          data-testid="session-expired-signin"
        >
          <LogIn className="h-3.5 w-3.5" />
          Sign in again
        </Button>
      </div>
    </div>
  )
}
