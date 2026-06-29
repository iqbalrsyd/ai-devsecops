import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ChevronDown, ChevronRight } from "lucide-react"
import {
  type NodeIORecord,
  formatDuration,
  formatJsonTruncated,
  jsonValueType,
} from "@/lib/node-io"

interface Props {
  record: NodeIORecord
  defaultOpen?: boolean
  // Optional LLM prompt to surface under "LLM prompt" inside the
  // expanded card. Used by the Tahap 1-3 view in PipelineVersionDetail
  // to show what was sent to the LLM for nodes that have one.
  prompt?: string | null
}

/**
 * NodeIOCard — collapsible per-node I/O trace card.
 *
 * Used by:
 *   • PipelineVersionDetail → Tahap 1-3 (input keys / output diff /
 *     duration / status). Sourced from `pipeline.node_io` (persisted
 *     to the `pipelines` table at generate-time by the backend).
 *   • RunDetail → Tahap 4 (same shape, sourced from
 *     `runs/{runId}/analysis.node_io`).
 *
 * The card is collapsed by default to keep the page scannable;
 * the user clicks the header to expand the input + output tables.
 */
export default function NodeIOCard({ record, defaultOpen, prompt }: Props) {
  const [open, setOpen] = useState(!!defaultOpen)
  const isError = record.status === "error"
  const statusClasses = isError
    ? "bg-red-100 text-red-800 border-red-300"
    : record.status === "running"
      ? "bg-blue-100 text-blue-800 border-blue-300"
      : "bg-green-100 text-green-800 border-green-300"
  const statusLabel = isError ? "error" : record.status || "ok"
  return (
    <Card className={`border ${isError ? "border-red-300" : "border-slate-200"}`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/40 text-left transition-colors rounded-t-lg"
        data-testid={`node-io-card-${record.node}`}
      >
        {open ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
        <span className="text-sm font-medium flex-1 font-mono">
          {record.node.replace(/_/g, " ")}
        </span>
        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300 font-mono text-[11px]">
          {formatDuration(record.duration_ms)}
        </span>
        <span className={`px-2 py-0.5 rounded border font-mono text-[11px] ${statusClasses}`}>
          {statusLabel}
        </span>
      </button>
      {open && (
        <CardContent className="pt-0 space-y-3">
          {isError && record.error && (
            <div className="text-xs bg-red-50 border border-red-300 text-red-800 rounded p-2 font-mono whitespace-pre-wrap">
              {record.error}
            </div>
          )}
          {prompt && (
            <div>
              <p className="text-[11px] font-semibold text-slate-600 mb-1">LLM prompt</p>
              <pre className="text-[11px] font-mono bg-violet-50 border border-violet-200 rounded p-2 whitespace-pre-wrap text-slate-700">
                {formatJsonTruncated(prompt, 600)}
              </pre>
            </div>
          )}
          <div>
            <p className="text-[11px] font-semibold text-slate-600 mb-1">Input (state keys fed into this node)</p>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium w-1/2">key</th>
                    <th className="text-left px-2 py-1 font-medium">value (truncated)</th>
                  </tr>
                </thead>
                <tbody>
                  {record.input_keys.length === 0 && (
                    <tr>
                      <td colSpan={2} className="px-2 py-2 text-slate-400 italic">no input keys</td>
                    </tr>
                  )}
                  {record.input_keys.map((k) => {
                    const has = Object.prototype.hasOwnProperty.call(record.output_summary, k)
                    const v = has ? record.output_summary[k] : "(unchanged)"
                    const json = formatJsonTruncated(v)
                    return (
                      <tr key={k} className="border-t">
                        <td className="px-2 py-1 font-mono align-top">{k}</td>
                        <td className="px-2 py-1 font-mono align-top whitespace-pre-wrap break-words">{json}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-600 mb-1">Output (state keys this node wrote)</p>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-1 font-medium w-1/3">key</th>
                    <th className="text-left px-2 py-1 font-medium w-1/4">type</th>
                    <th className="text-left px-2 py-1 font-medium">value (truncated)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(record.output_summary).length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-2 py-2 text-slate-400 italic">no output keys</td>
                    </tr>
                  )}
                  {Object.entries(record.output_summary).map(([k, v]) => (
                    <tr key={k} className="border-t">
                      <td className="px-2 py-1 font-mono align-top">{k}</td>
                      <td className="px-2 py-1 font-mono align-top text-slate-500">{jsonValueType(v)}</td>
                      <td className="px-2 py-1 font-mono align-top whitespace-pre-wrap break-words">{formatJsonTruncated(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
