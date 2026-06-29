import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react"

interface ComplianceItem {
  framework: string
  control_id: string
  control_name: string
  status: string
  finding_refs: string[]
}

interface ComplianceScorecardProps {
  mappings: ComplianceItem[]
  score: number | null
}

export default function ComplianceScorecard({ mappings, score }: ComplianceScorecardProps) {
  if (!mappings || mappings.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          Compliance Scorecard
          {score !== null && (
            <span className="text-lg font-bold ml-auto">
              {score.toFixed(0)}%
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {mappings.map((m, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            {m.status === "passed" && <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />}
            {m.status === "failed" && <XCircle className="h-4 w-4 text-red-500 shrink-0" />}
            {m.status === "not_applicable" && <MinusCircle className="h-4 w-4 text-gray-400 shrink-0" />}
            <span className={m.status === "passed" ? "text-muted-foreground" : "text-foreground font-medium"}>
              {m.control_id}: {m.control_name}
            </span>
            <span className="text-xs text-muted-foreground ml-auto capitalize">
              {m.status.replace(/_/g, " ")}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}