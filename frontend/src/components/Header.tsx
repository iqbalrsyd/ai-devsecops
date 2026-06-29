import { useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { LogOut, User, Settings } from "lucide-react"

import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface Breadcrumb {
  label: string
  href?: string
}

interface HeaderProps {
  breadcrumbs?: Breadcrumb[]
  children?: ReactNode
}

export default function Header({ breadcrumbs, children }: HeaderProps) {
  const { user, logout } = useAuth()
  const [logoutOpen, setLogoutOpen] = useState(false)

  const handleLogout = () => {
    logout()
    setLogoutOpen(false)
  }

  return (
    <>
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {breadcrumbs ? (
              breadcrumbs.map((crumb, i) => (
                <span key={i} className="flex items-center gap-3">
                  {i > 0 && <span className="text-gray-400">/</span>}
                  {crumb.href ? (
                    <Link to={crumb.href} className="text-sm text-blue-600 hover:underline">
                      {crumb.label}
                    </Link>
                  ) : (
                    <h1 className="text-xl font-semibold">{crumb.label}</h1>
                  )}
                </span>
              ))
            ) : (
              <h1 className="text-xl font-semibold text-gray-900">
                AI DevSecOps Pipeline Engineer
              </h1>
            )}
          </div>
          <div className="flex items-center gap-3">
            {children}
            <div className="flex items-center gap-2 border-l border-gray-200 pl-3">
              <div className="h-7 w-7 rounded-full bg-gray-100 flex items-center justify-center">
                <span className="text-xs font-medium text-gray-600">
                  {user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || "U"}
                </span>
              </div>
              <span className="text-sm text-gray-600 max-w-[120px] truncate">
                {user?.name || user?.email || "User"}
              </span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setLogoutOpen(true)} title="Logout">
                <LogOut className="h-4 w-4 text-gray-500" />
              </Button>
              <Link to="/settings" title="Settings">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Settings className="h-4 w-4 text-gray-500" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      <Dialog open={logoutOpen} onOpenChange={setLogoutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Logout</DialogTitle>
            <DialogDescription>
              Are you sure you want to log out of your account?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLogoutOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleLogout}>Logout</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
