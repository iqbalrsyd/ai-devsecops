import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Lightbulb, ArrowRight } from "lucide-react"

interface RecommendationsListProps {
  recommendations: string[]
  fixExamples?: Array<{ finding_type: string; before: string; after: string }>
}

export default function RecommendationsList({ recommendations, fixExamples }: RecommendationsListProps) {
  if (!recommendations || recommendations.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Lightbulb className="h-5 w-5 text-yellow-500" />
          Recommendations ({recommendations.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {recommendations.map((rec, i) => (
          <p key={i} className="text-sm flex items-start gap-2">
            <ArrowRight className="h-4 w-4 mt-0.5 text-primary shrink-0" />
            <span>{rec}</span>
          </p>
        ))}
        {fixExamples && fixExamples.length > 0 && (
          <div className="pt-3 space-y-3">
            <p className="text-sm font-medium">Code Examples</p>
            {fixExamples.map((ex, i) => (
              <div key={i} className="space-y-1">
                <p className="text-xs text-muted-foreground">{ex.finding_type}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-red-50 rounded p-2">
                    <p className="text-xs font-medium text-red-600 mb-1">Before</p>
                    <pre className="text-xs whitespace-pre-wrap"><code>{ex.before}</code></pre>
                  </div>
                  <div className="bg-green-50 rounded p-2">
                    <p className="text-xs font-medium text-green-600 mb-1">After</p>
                    <pre className="text-xs whitespace-pre-wrap"><code>{ex.after}</code></pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}