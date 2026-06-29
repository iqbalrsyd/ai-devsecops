import { useMemo, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"

interface YamlViewerProps {
  content: string
  highlightedLines?: number[]
  scrollToLine?: number | null
  className?: string
}

export default function YamlViewer({ content, highlightedLines = [], scrollToLine, className }: YamlViewerProps) {
  const lineRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const lines = useMemo(() => content.split("\n"), [content])
  const highlightSet = useMemo(() => new Set(highlightedLines), [highlightedLines])

  useEffect(() => {
    if (scrollToLine && lineRefs.current[scrollToLine]) {
      lineRefs.current[scrollToLine]?.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [scrollToLine])

  return (
    <div className={cn("rounded-md border bg-zinc-950 text-zinc-50 overflow-auto max-h-96", className)}>
      <pre className="p-3 text-sm leading-relaxed font-mono">
        <code>
          {lines.map((line, i) => {
            const lineNum = i + 1
            const highlighted = highlightSet.has(lineNum)
            return (
              <div
                key={i}
                ref={(el) => { lineRefs.current[lineNum] = el }}
                id={`yaml-line-${lineNum}`}
                className={cn(
                  "flex hover:bg-zinc-900/50",
                  highlighted && "bg-red-900/30 border-l-2 border-red-500 -ml-3 pl-[10px]"
                )}
              >
                <span className="select-none text-zinc-600 w-8 shrink-0 text-right mr-3">
                  {lineNum}
                </span>
                <span className="whitespace-pre">{line || " "}</span>
              </div>
            )
          })}
        </code>
      </pre>
    </div>
  )
}