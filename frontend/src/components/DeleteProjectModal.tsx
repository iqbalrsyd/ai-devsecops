import { useNavigate } from "react-router-dom"
import { TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useDeleteProject } from "@/hooks/useProjects"

interface DeleteProjectModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  projectName: string
}

export default function DeleteProjectModal({ open, onOpenChange, projectId, projectName }: DeleteProjectModalProps) {
  const navigate = useNavigate()
  const deleteProject = useDeleteProject()

  const handleDelete = async () => {
    try {
      await deleteProject.mutateAsync(projectId)
      onOpenChange(false)
      navigate("/dashboard")
    } catch {
      // error handled by the hook
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-full bg-destructive/15">
              <TriangleAlert className="h-5 w-5 text-destructive" />
            </div>
            <DialogTitle>Delete Project</DialogTitle>
          </div>
          <DialogDescription className="pt-3">
            Are you sure you want to delete <strong>{projectName}</strong>? This will also delete all associated
            repositories and pipelines. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleteProject.isPending}>
            {deleteProject.isPending ? "Deleting..." : "Delete Project"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
