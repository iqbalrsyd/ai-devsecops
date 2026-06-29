import { Link } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Upload, GitPullRequest, FileText, Sparkles } from "lucide-react"

interface QuickActionsProps {
  projectId?: string
}

const actions = [
  {
    label: "Generate Pipeline",
    description: "AI-powered secure CI/CD pipeline",
    icon: Sparkles,
    to: (pid: string) => `/projects/${pid}/pipeline/generate`,
    color: "text-primary",
    bg: "bg-primary/10",
  },
  {
    label: "New Scan",
    description: "Upload a scan result file",
    icon: Upload,
    to: (pid: string) => `/projects/${pid}/upload`,
    color: "text-blue-600",
    bg: "bg-blue-50 dark:bg-blue-950/20",
  },
  {
    label: "Review PR",
    description: "Analyze a pull request",
    icon: GitPullRequest,
    to: (pid: string) => `/projects/${pid}/pr-review`,
    color: "text-purple-600",
    bg: "bg-purple-50 dark:bg-purple-950/20",
  },
  {
    label: "Create Project",
    description: "Start a new project",
    icon: FileText,
    to: () => "/dashboard",
    color: "text-green-600",
    bg: "bg-green-50 dark:bg-green-950/20",
  },
]

export default function QuickActions({ projectId }: QuickActionsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {actions.map((action) => (
        <Link key={action.label} to={action.to(projectId || "")}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className={`flex items-center gap-3 p-4 ${action.bg}`}>
              <div className={`p-2 rounded-lg ${action.bg}`}>
                <action.icon className={`h-5 w-5 ${action.color}`} />
              </div>
              <div>
                <p className="text-sm font-medium">{action.label}</p>
                <p className="text-xs text-muted-foreground">{action.description}</p>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}