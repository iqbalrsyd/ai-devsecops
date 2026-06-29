import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChevronDown,
  ChevronRight,
  FileCode,
  FileText,
  Sparkles,
  Workflow,
  Cog,
  Copy,
  Check,
} from "lucide-react"
import type { NodeSpec } from "@/hooks/usePipeline"

const TYPE_STYLES: Record<string, { label: string; classes: string }> = {
  deterministic: { label: "Deterministic", classes: "bg-slate-100 text-slate-700 border-slate-300" },
  llm: { label: "LLM", classes: "bg-violet-100 text-violet-800 border-violet-300" },
  hybrid: { label: "LLM + Heuristic", classes: "bg-amber-100 text-amber-800 border-amber-300" },
}

const TYPE_ICON: Record<string, typeof FileCode> = {
  deterministic: Cog,
  llm: Sparkles,
  hybrid: Workflow,
}

// Threshold above which a prompt is collapsed behind a "Show full
// prompt" button. Keeps the card scannable when 6+ LLM nodes are
// listed back-to-back in Tahap 1-3.
const PROMPT_COLLAPSE_THRESHOLD = 240

// Copy-to-clipboard for the LLM prompt. We surface a brief
// check-mark confirmation; resets after 2s.
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        // Fallback for non-secure contexts where the Clipboard
        // API is unavailable.
        const ta = document.createElement("textarea")
        ta.value = text
        ta.style.position = "fixed"
        ta.style.opacity = "0"
        document.body.appendChild(ta)
        ta.select()
        document.execCommand("copy")
        document.body.removeChild(ta)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Best-effort only — ignore copy errors (e.g. denied
      // permission in an iframe).
    }
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        // Don't let the click bubble up to a parent toggle.
        e.stopPropagation()
        handleCopy()
      }}
      className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-gray-500 hover:text-violet-700 transition-colors"
      aria-label="Copy LLM prompt"
      data-testid="copy-llm-prompt"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          Copy
        </>
      )}
    </button>
  )
}

interface Props {
  node: NodeSpec
  defaultOpen?: boolean
}

export default function NodeSpecCard({ node, defaultOpen = false }: Props) {
  // Auto-open cards that are LLM-driven so the prompt is visible
  // without an extra click. The pipeline graph has 6+ LLM nodes
  // and hiding the prompt behind a click made it easy to miss
  // — which is the whole point of the page (Bab 5.13 spec says
  // the prompt is "abbreviated metadata that the FE should
  // surface prominently").
  const hasPrompt = !!(node.prompt && node.prompt.trim().length > 0)
  const [open, setOpen] = useState(defaultOpen || hasPrompt)
  const [promptExpanded, setPromptExpanded] = useState(false)

  const typeStyle = TYPE_STYLES[node.type] ?? TYPE_STYLES.deterministic
  const TypeIcon = TYPE_ICON[node.type] ?? FileCode

  const promptIsLong =
    hasPrompt && (node.prompt?.length ?? 0) > PROMPT_COLLAPSE_THRESHOLD
  const promptDisplay = !hasPrompt
    ? ""
    : promptIsLong && !promptExpanded
      ? `${node.prompt!.slice(0, PROMPT_COLLAPSE_THRESHOLD).trimEnd()}…`
      : node.prompt!

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader
        className="cursor-pointer select-none py-3"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <CardTitle className="text-sm flex items-center gap-2">
            {open ? (
              <ChevronDown className="h-4 w-4 text-gray-500" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-500" />
            )}
            <span className="font-mono text-xs text-gray-500">T{node.tahap}.{node.id}</span>
            <span className="font-semibold">{node.name}</span>
          </CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${typeStyle.classes}`}
            >
              <TypeIcon className="h-3 w-3 inline mr-1" />
              {typeStyle.label}
            </span>
            {hasPrompt && (
              <span
                className="text-[10px] font-bold uppercase px-2 py-0.5 rounded border bg-violet-50 text-violet-700 border-violet-200 inline-flex items-center gap-1"
                title="This node has an LLM prompt (click card to view)"
              >
                <Sparkles className="h-3 w-3" />
                Prompt
              </span>
            )}
            <span className="text-[10px] text-gray-500 font-mono">
              ~{node.line_count} lines
            </span>
          </div>
        </div>
        <p className="text-xs text-gray-600 mt-1.5 ml-6">{node.function}</p>
      </CardHeader>
      {open && (
        <CardContent className="pt-0 space-y-3 pb-3">
          {/* Inputs */}
          <div>
            <div className="text-[10px] uppercase font-bold text-gray-500 mb-1 flex items-center gap-1">
              <span>Inputs (state reads)</span>
              <span className="text-gray-400 font-normal normal-case">
                ({node.inputs.length})
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {node.inputs.map((k) => (
                <span
                  key={k}
                  className="text-[11px] font-mono bg-purple-50 text-purple-800 border border-purple-200 px-2 py-0.5 rounded"
                >
                  {k}
                </span>
              ))}
            </div>
          </div>

          {/* Outputs */}
          <div>
            <div className="text-[10px] uppercase font-bold text-gray-500 mb-1 flex items-center gap-1">
              <span>Outputs (state writes)</span>
              <span className="text-gray-400 font-normal normal-case">
                ({node.outputs.length})
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {node.outputs.map((k) => (
                <span
                  key={k}
                  className="text-[11px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded"
                >
                  {k}
                </span>
              ))}
            </div>
          </div>

          {/* LLM Prompt */}
          {hasPrompt && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="text-[10px] uppercase font-bold text-gray-500 flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-violet-600" />
                  <span>LLM Prompt</span>
                  {promptIsLong && (
                    <span className="text-gray-400 font-normal normal-case">
                      ({node.prompt!.length} chars)
                    </span>
                  )}
                </div>
                <CopyButton text={node.prompt!} />
              </div>
              <pre className="text-[11px] font-mono bg-gray-50 border border-gray-200 rounded p-2 whitespace-pre-wrap text-gray-700">
                {promptDisplay}
              </pre>
              {promptIsLong && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setPromptExpanded((v) => !v)
                  }}
                  className="mt-1 text-[10px] uppercase font-bold text-violet-700 hover:text-violet-900 inline-flex items-center gap-1"
                >
                  {promptExpanded ? (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      Hide full prompt
                    </>
                  ) : (
                    <>
                      <ChevronRight className="h-3 w-3" />
                      Show full prompt
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Fallback */}
          {node.fallback && (
            <div>
              <div className="text-[10px] uppercase font-bold text-amber-700 mb-1 flex items-center gap-1">
                <Cog className="h-3 w-3" />
                <span>Fallback (deterministic)</span>
              </div>
              <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded p-2">
                {node.fallback}
              </p>
            </div>
          )}

          {/* File + Spec */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <div className="bg-gray-50 border border-gray-200 rounded p-2">
              <div className="text-[10px] uppercase font-bold text-gray-500 mb-0.5">File</div>
              <div className="font-mono text-gray-800 break-all">{node.file}</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded p-2">
              <div className="text-[10px] uppercase font-bold text-blue-600 mb-0.5 flex items-center gap-1">
                <FileText className="h-3 w-3" />
                <span>Spec</span>
              </div>
              <div className="font-mono text-blue-800 break-all">{node.spec_ref}</div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
