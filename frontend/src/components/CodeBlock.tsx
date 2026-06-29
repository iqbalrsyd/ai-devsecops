import { cn } from "@/lib/utils"

interface CodeBlockProps {
  code: string
  language?: string
  highlightLines?: number[]
  className?: string
}

export default function CodeBlock({ code, language, highlightLines, className }: CodeBlockProps) {
  const lines = code.split("\n")

  return (
    <div className={cn("rounded-md border bg-zinc-950 text-zinc-50 overflow-hidden", className)}>
      {language && (
        <div className="px-3 py-1 text-xs text-zinc-400 border-b border-zinc-800 bg-zinc-900">
          {language}
        </div>
      )}
      <pre className="p-3 overflow-x-auto text-sm leading-relaxed">
        <code>
          {lines.map((line, i) => {
            const lineNum = i + 1
            const highlighted = highlightLines?.includes(lineNum)
            return (
              <div
                key={i}
                className={cn(
                  "flex",
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