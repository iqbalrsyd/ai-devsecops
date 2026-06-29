import { cn } from "@/lib/utils"

interface DiffLine {
  type: "add" | "del" | "context"
  content: string
  oldLine: number | null
  newLine: number | null
}

function parseDiff(diff: string): DiffLine[] {
  const lines = diff.split("\n")
  const result: DiffLine[] = []
  let oldLine = 0
  let newLine = 0

  for (const line of lines) {
    if (line.startsWith("@@")) {
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/)
      if (match) {
        oldLine = parseInt(match[1]) - 1
        newLine = parseInt(match[2]) - 1
      }
      result.push({ type: "context", content: line, oldLine: null, newLine: null })
      continue
    }

    if (line.startsWith("---") || line.startsWith("+++")) {
      result.push({ type: "context", content: line, oldLine: null, newLine: null })
      continue
    }

    if (line.startsWith("-")) {
      oldLine++
      result.push({ type: "del", content: line, oldLine, newLine: null })
    } else if (line.startsWith("+")) {
      newLine++
      result.push({ type: "add", content: line, oldLine: null, newLine })
    } else {
      oldLine++
      newLine++
      result.push({ type: "context", content: line, oldLine, newLine })
    }
  }

  return result
}

interface CodeDiffProps {
  diff: string
  filename?: string
  className?: string
}

export default function CodeDiff({ diff, filename, className }: CodeDiffProps) {
  const lines = parseDiff(diff)

  return (
    <div className={cn("rounded-md border border-zinc-800 overflow-hidden", className)}>
      {filename && (
        <div className="px-3 py-1.5 text-xs font-mono text-zinc-400 bg-zinc-900 border-b border-zinc-800">
          {filename}
        </div>
      )}
      <pre className="bg-zinc-950 text-xs leading-relaxed overflow-x-auto">
        <code>
          {lines.map((line, i) => {
            const bg =
              line.type === "add"
                ? "bg-green-950/40"
                : line.type === "del"
                  ? "bg-red-950/40"
                  : ""
            const textColor =
              line.type === "add"
                ? "text-green-300"
                : line.type === "del"
                  ? "text-red-300"
                  : "text-zinc-300"
            return (
              <div key={i} className={cn("flex", bg)}>
                <span className="select-none text-zinc-600 w-10 shrink-0 text-right mr-2">
                  {line.type === "add" ? "+" : line.type === "del" ? "-" : " "}
                </span>
                <span className={cn("whitespace-pre", textColor)}>{line.content}</span>
              </div>
            )
          })}
        </code>
      </pre>
    </div>
  )
}