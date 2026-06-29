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
import { useDeletePipeline } from "@/hooks/usePipelinesV2"

interface DeletePipelineModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pipelineId: string
  pipelineVersion: number
  repoId: string
  projectId: string
}

export default function DeletePipelineModal({ open, onOpenChange, pipelineId, pipelineVersion, repoId, projectId }: DeletePipelineModalProps) {
  const navigate = useNavigate()
  const deletePipeline = useDeletePipeline()

  const handleDelete = async () => {
    try {
      await deletePipeline.mutateAsync(pipelineId)
      onOpenChange(false)
      navigate(`/projects/${projectId}/repos/${repoId}`)
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
            <DialogTitle>Delete Pipeline</DialogTitle>
          </div>
          <DialogDescription className="pt-3">
            Are you sure you want to delete <strong>Pipeline #{pipelineVersion}</strong>? This includes all associated runs
            and analysis data. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deletePipeline.isPending}>
            {deletePipeline.isPending ? "Deleting..." : "Delete Pipeline"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
