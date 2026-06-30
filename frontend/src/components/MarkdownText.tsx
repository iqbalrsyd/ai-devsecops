import type { ReactNode } from "react"

// Lightweight markdown renderer for the LLM recommendation
// text. The AI service returns a single `recommendation` string
// (often markdown) so we need to render bold, inline code,
// fenced code blocks, and numbered/bulleted lists without
// pulling in a markdown dependency.
//
// Scope is intentionally narrow: the prompt asks the LLM for
// "a markdown-formatted string with the explanation +
// step-by-step fix", so we support exactly the patterns the
// LLM commonly produces and gracefully fall back to plain
// text for anything else.
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  // Inline transforms: **bold**, `code`. We process them in
  // a single pass so `**bold `code` inside**` works.
  const parts: ReactNode[] = []
  let buf = ""
  let i = 0
  const flush = () => {
    if (buf) {
      parts.push(buf)
      buf = ""
    }
  }
  while (i < text.length) {
    const ch = text[i]
    if (ch === "*" && text[i + 1] === "*") {
      const end = text.indexOf("**", i + 2)
      if (end > i + 2) {
        flush()
        parts.push(
          <strong key={`${keyPrefix}b${i}`}>
            {renderInline(text.slice(i + 2, end), `${keyPrefix}b${i}`)}
          </strong>,
        )
        i = end + 2
        continue
      }
    }
    if (ch === "`") {
      const end = text.indexOf("`", i + 1)
      if (end > i + 1) {
        flush()
        parts.push(
          <code
            key={`${keyPrefix}c${i}`}
            className="px-1 py-0.5 rounded bg-gray-100 text-pink-700 text-[11px] font-mono border border-gray-200"
          >
            {text.slice(i + 1, end)}
          </code>,
        )
        i = end + 1
        continue
      }
    }
    buf += ch
    i += 1
  }
  flush()
  return parts
}

export function renderMarkdown(input: string): ReactNode[] {
  if (!input) return []
  const lines = input.split("\n")
  const out: ReactNode[] = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // Fenced code block: ```lang ... ```
    if (trimmed.startsWith("```")) {
      const codeLines: string[] = []
      i += 1
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i])
        i += 1
      }
      i += 1 // skip closing fence
      out.push(
        <pre
          key={key++}
          className="text-[11px] bg-gray-900 text-green-200 rounded p-2 overflow-x-auto font-mono my-1"
        >
          <code>{codeLines.join("\n")}</code>
        </pre>,
      )
      continue
    }

    // Numbered list: 1. 2. 3.
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""))
        i += 1
      }
      out.push(
        <ol key={key++} className="list-decimal pl-5 space-y-1 text-gray-800">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, `${key}l${idx}`)}</li>
          ))}
        </ol>,
      )
      continue
    }

    // Bulleted list: - or * at line start
    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""))
        i += 1
      }
      out.push(
        <ul key={key++} className="list-disc pl-5 space-y-1 text-gray-800">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, `${key}l${idx}`)}</li>
          ))}
        </ul>,
      )
      continue
    }

    // Heading: # / ## / ### (max h3)
    const h = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (h) {
      const level = h[1].length
      const text = h[2]
      const cls =
        level === 1
          ? "text-base font-bold text-gray-900 mt-1"
          : level === 2
            ? "text-sm font-bold text-gray-900 mt-1"
            : "text-xs font-bold text-gray-800 mt-0.5"
      const Tag = (`h${level + 2}`) as "h4" | "h5" | "h6"
      out.push(
        <Tag key={key++} className={cls}>
          {renderInline(text, `${key}h`)}
        </Tag>,
      )
      i += 1
      continue
    }

    // Blank line: paragraph break
    if (!trimmed) {
      i += 1
      continue
    }

    // Default: inline text on its own line.
    out.push(
      <p key={key++} className="text-gray-800 leading-relaxed">
        {renderInline(trimmed, `${key}p`)}
      </p>,
    )
    i += 1
  }
  return out
}
