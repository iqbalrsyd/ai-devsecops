import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useConnectRepository } from "@/hooks/useRepositories"

interface ConnectRepoModalProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function ConnectRepoModal({ projectId, open, onOpenChange }: ConnectRepoModalProps) {
  const [githubToken, setGithubToken] = useState("")
  const [fullName, setFullName] = useState("")
  const [error, setError] = useState("")
  const connectRepo = useConnectRepository()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    try {
      const body = { project_id: projectId, github_token: githubToken, full_name: fullName }
      console.log("[ConnectRepo] projectId from props:", projectId)
      console.log("[ConnectRepo] Request body:", body)
      if (!projectId) {
        setError("Debug: projectId is undefined or empty. Check URL params.")
        return
      }
      await connectRepo.mutateAsync(body)
      // Stash the token in localStorage so the generate / analyze
      // flows can use it without asking the user to re-enter it on
      // every page. The backend also stores its own encrypted copy
      // on the repository row; this client-side copy is a convenience
      // cache and is cleared on logout.
      try {
        localStorage.setItem("github_token", githubToken)
      } catch {
        // localStorage may be unavailable (private mode); non-fatal.
      }
      setGithubToken("")
      setFullName("")
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect repository")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect Repository</DialogTitle>
          <DialogDescription>Link a GitHub repository to this project</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="bg-destructive/15 text-destructive text-sm rounded-md px-3 py-2 mb-4">{error}</div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="github_token">GitHub Token</Label>
              <Input id="github_token" type="password" placeholder="ghp_..." value={githubToken} onChange={(e) => setGithubToken(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="full_name">Repository</Label>
              <Input id="full_name" placeholder="owner/repo" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
          </div>
          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={connectRepo.isPending}>
              {connectRepo.isPending ? "Connecting..." : "Connect"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}