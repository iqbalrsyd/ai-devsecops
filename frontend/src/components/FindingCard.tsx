import { useState } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import CodeBlock from "@/components/CodeBlock"
import { CheckCircle2, Flag } from "lucide-react"

interface Finding {
  id: string
  file: string
  line: number
  severity: string
  rule: string
  description: string
  recommendation: string
  code_snippet: string
  status?: string
}

interface FindingCardProps {
  finding: Finding
  onMarkFixed?: (id: string) => void
  onAcknowledge?: (id: string) => void
}

export default function FindingCard({ finding, onMarkFixed, onAcknowledge }: FindingCardProps) {
  const [status, setStatus] = useState(finding.status || "open")

  const handleMarkFixed = () => {
    setStatus("fixed")
    onMarkFixed?.(finding.id)
  }

  const handleAcknowledge = () => {
    setStatus("acknowledged")
    onAcknowledge?.(finding.id)
  }

  const colorMap: Record<string, string> = {
    critical: "border-red-500/50",
    high: "border-orange-500/50",
    medium: "border-yellow-500/50",
    low: "border-slate-500/50",
  }

  return (
    <Card className={`border-l-4 ${colorMap[finding.severity] || "border-l-zinc-300"}`}>
      <CardHeader className="pb-2 flex-row items-start justify-between space-y-0">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono text-muted-foreground">{finding.rule}</span>
          </div>
          <p className="text-sm">
            <span className="font-medium">{finding.file}</span>
            {finding.line > 0 && (
              <span className="text-muted-foreground">:{finding.line}</span>
            )}
          </p>
        </div>
        {status === "fixed" && (
          <span className="inline-flex items-center gap-1 text-xs text-green-600">
            <CheckCircle2 className="h-3 w-3" /> Fixed
          </span>
        )}
        {status === "acknowledged" && (
          <span className="inline-flex items-center gap-1 text-xs text-blue-600">
            <Flag className="h-3 w-3" /> Acknowledged
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{finding.description}</p>

        {finding.code_snippet && (
          <CodeBlock code={finding.code_snippet} highlightLines={finding.line > 0 ? [finding.line] : undefined} />
        )}

        {finding.recommendation && (
          <div className="rounded-md bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 p-3">
            <p className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-1">Recommendation</p>
            <p className="text-sm text-blue-700 dark:text-blue-300">{finding.recommendation}</p>
          </div>
        )}

        {status === "open" && (
          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="outline" onClick={handleMarkFixed}>
              <CheckCircle2 className="h-3 w-3 mr-1" /> Mark as Fixed
            </Button>
            <Button size="sm" variant="ghost" onClick={handleAcknowledge}>
              <Flag className="h-3 w-3 mr-1" /> Acknowledge
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}