import { Card, CardContent } from "@/components/ui/card"
import { Clock, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"

interface ActivityItem {
  id: string
  type: string
  status: string
  description: string
  created_at: string
}

interface RecentActivityProps {
  items: ActivityItem[]
}

export function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "success":
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    case "failed":
    case "failure":
      return <AlertCircle className="h-4 w-4 text-red-500" />
    case "running":
    case "processing":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
    default:
      return <Clock className="h-4 w-4 text-yellow-500" />
  }
}

export default function RecentActivity({ items }: RecentActivityProps) {
  return (
    <Card>
      <CardContent className="p-0">
        {!items || items.length === 0 ? (
          <p className="text-center py-8 text-sm text-muted-foreground">No recent activity</p>
        ) : (
          <div className="divide-y">
            {items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <StatusIcon status={item.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.type}</p>
                  <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
