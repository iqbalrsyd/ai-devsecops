import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Terminal } from "lucide-react"

interface LiveLogViewerProps {
  logs: string
  isLoading: boolean
}

export default function LiveLogViewer({ logs, isLoading }: LiveLogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Terminal className="h-5 w-5" />
          Workflow Logs
          {isLoading && <span className="text-xs text-muted-foreground animate-pulse">(streaming...)</span>}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={scrollRef}
          className="bg-black text-green-400 rounded-lg p-4 font-mono text-xs h-64 overflow-y-auto whitespace-pre-wrap"
        >
          {logs || "Waiting for logs..."}
        </div>
      </CardContent>
    </Card>
  )
}