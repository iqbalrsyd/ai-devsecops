import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, Clock, Loader2, XCircle, ChevronDown, ChevronRight } from "lucide-react"

interface StepData {
  name: string
  status: string
  conclusion: string | null
  number: number
}

interface JobData {
  id: number
  workflow_name?: string
  name: string
  status: string
  conclusion: string | null
  steps: StepData[]
  started_at?: string | null
  completed_at?: string | null
}

interface ExecutionTimelineProps {
  jobs: JobData[]
}

function getDuration(started_at: string | null | undefined, completed_at: string | null | undefined): string {
  if (!started_at || !completed_at) return ""
  const secs = Math.round((new Date(completed_at).getTime() - new Date(started_at).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function StatusIcon({ status, conclusion, className }: { status: string; conclusion: string | null; className?: string }) {
  if (conclusion === "success") return <CheckCircle2 className={`text-green-500 ${className || "h-4 w-4"}`} />
  if (conclusion === "failure" || conclusion === "cancelled") return <XCircle className={`text-red-500 ${className || "h-4 w-4"}`} />
  if (status === "in_progress" || status === "queued" || status === "running") return <Loader2 className={`text-blue-500 animate-spin ${className || "h-4 w-4"}`} />
  return <Clock className={`text-yellow-500 ${className || "h-4 w-4"}`} />
}

function JobCard({ job }: { job: JobData }) {
  const [expanded, setExpanded] = useState(false)
  const hasSteps = job.steps && job.steps.length > 0
  const displayName = job.workflow_name ? `${job.workflow_name} / ${job.name}` : job.name
  const duration = getDuration(job.started_at, job.completed_at)

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 text-left transition-colors"
      >
        {hasSteps ? (
          expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <div className="w-4 shrink-0" />
        )}
        <StatusIcon status={job.status} conclusion={job.conclusion} />
        <span className="text-sm font-medium flex-1">{displayName}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {job.conclusion === "success" && duration && `Passing after ${duration}`}
            {job.conclusion === "failure" && duration && `Failing after ${duration}`}
            {job.status === "running" && "Running"}
            {job.status === "queued" && "Queued"}
          </span>
          <Badge variant={job.conclusion === "success" ? "default" : job.conclusion === "failure" ? "destructive" : "secondary"} className="text-xs whitespace-nowrap">
            {job.conclusion || job.status}
          </Badge>
        </div>
      </button>
      {expanded && hasSteps && (
        <div className="border-t px-4 py-2 bg-muted/30">
          {job.steps.map((step) => (
            <div key={step.number} className="flex items-center gap-3 py-1.5">
              <StatusIcon status={step.status} conclusion={step.conclusion} className="h-3.5 w-3.5" />
              <span className="text-sm text-muted-foreground">{step.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ExecutionTimeline({ jobs }: ExecutionTimelineProps) {
  if (!jobs || jobs.length === 0) return null

  const failingJobs = jobs.filter((j) => j.conclusion === "failure" || j.conclusion === "cancelled")
  const successfulJobs = jobs.filter((j) => j.conclusion === "success")
  const pendingJobs = jobs.filter((j) => !j.conclusion || j.status === "running" || j.status === "queued")

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          Checks
          <span className="text-xs font-normal text-muted-foreground">
            ({successfulJobs.length} passed, {failingJobs.length} failed, {pendingJobs.length} pending)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {failingJobs.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-red-700 mb-1.5 flex items-center gap-1">
              <XCircle className="h-3 w-3" /> Failing
            </h4>
            <div className="space-y-1.5">
              {failingJobs.map((job) => <JobCard key={job.id} job={job} />)}
            </div>
          </div>
        )}
        {pendingJobs.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-blue-700 mb-1.5 flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> In progress
            </h4>
            <div className="space-y-1.5">
              {pendingJobs.map((job) => <JobCard key={job.id} job={job} />)}
            </div>
          </div>
        )}
        {successfulJobs.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-green-700 mb-1.5 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" /> Successful
            </h4>
            <div className="space-y-1.5">
              {successfulJobs.map((job) => <JobCard key={job.id} job={job} />)}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}