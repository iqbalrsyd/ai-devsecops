import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ExternalLink, GitPullRequest, CheckCircle2, Clock } from "lucide-react"

interface PRLinkProps {
  prUrl: string | null
  prNumber: number | null
  branch: string | null
}

export default function PRLink({ prUrl, prNumber, branch }: PRLinkProps) {
  if (!prUrl) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <GitPullRequest className="h-5 w-5 text-primary" />
          Pull Request Created
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <a
          href={prUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-sm text-primary hover:underline"
        >
          <ExternalLink className="h-4 w-4" />
          PR #{prNumber} — Review on GitHub
        </a>
        {branch && (
          <p className="text-sm text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Branch: {branch}
          </p>
        )}
        <p className="text-sm text-muted-foreground flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3 text-green-500" />
          Review and merge the PR to trigger the workflow
        </p>
      </CardContent>
    </Card>
  )
}