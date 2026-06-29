// Shared types + helpers for the per-node I/O trace rendered on
// the PipelineDetail (Tahap 1-3) and RunDetail (Tahap 4) pages.
// The shape mirrors `state["node_io"]` produced by
// `_invoke_graph_phase` in ai-service/app/services/pipeline_service.py.
//
// Each record is also rendered with a `phase` tag so the FE can
// group Tahap 1, 2, 3 separately (the "phase" value is set by the
// AI service as `_current_phase` before each phase runs).

export type NodePhase = "tahap_1" | "tahap_2" | "tahap_3" | "tahap_4"

export type NodeIORecord = {
  node: string
  phase?: NodePhase | string
  started_at?: string
  status: "ok" | "error" | "running" | string
  duration_ms: number
  input_keys: string[]
  output_summary: Record<string, unknown>
  error?: string
}

// Human-readable phase label. Defensive against missing/unknown
// values (older payloads, manual edits) so the UI never crashes
// on a bad enum.
export function phaseLabel(phase?: string): string {
  if (!phase) return "Unknown"
  const known: Record<string, string> = {
    tahap_1: "Tahap 1 — Repository Context",
    tahap_2: "Tahap 2 — Security Coverage",
    tahap_3: "Tahap 3 — Pipeline Generation",
    tahap_4: "Tahap 4 — Security Evaluation",
  }
  return known[phase] ?? phase
}

// Pretty-print a duration in milliseconds as e.g. "1.23s" or
// "412ms". Used by both Tahap 1-3 and Tahap 4 cards.
export function formatDuration(ms: number): string {
  if (!ms || ms < 0) return "—"
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

// Compact JSON repr with a hard character cap. Lists/dicts are
// summarised upstream by the AI service ("type(len)" markers), so
// these should already be small, but we still cap defensively to
// keep the per-card render under a few KB.
export function formatJsonTruncated(value: unknown, max = 200): string {
  if (value === undefined) return "(unset)"
  if (value === null) return "null"
  let s: string
  try {
    s = JSON.stringify(value, null, 2)
  } catch {
    s = String(value)
  }
  if (s.length <= max) return s
  return s.slice(0, max) + "…"
}

export function jsonValueType(value: unknown): string {
  if (value === null) return "null"
  if (value === undefined) return "—"
  if (Array.isArray(value)) return `array(${value.length})`
  return typeof value
}

// Default order of node cards in a Tahap 1-3 group. Mirrors the
// natural flow of the v9.3 compiled graph so users see the trace
// in execution order rather than alphabetically. Unknown nodes
// fall to the end.
const DEFAULT_TAHAP_1_3_ORDER = [
  "repository_connection",
  "repository_scan",
  "technology_detection",
  "architecture_detection",
  "deployment_detection",
  "domain_detection",
  "coverage_inference",
  "pattern_inference",
  "pipeline_augmentation",
  "job_reasoning",
  "workflow_generator",
  "workflow_repair",
  "pull_request_creation",
  "response_formatter",
]

export function sortTahap123(records: NodeIORecord[]): NodeIORecord[] {
  const idx = (n: string) => {
    const i = DEFAULT_TAHAP_1_3_ORDER.indexOf(n)
    return i === -1 ? 999 : i
  }
  return [...records].sort((a, b) => {
    const ai = idx(a.node)
    const bi = idx(b.node)
    if (ai !== bi) return ai - bi
    return a.node.localeCompare(b.node)
  })
}

export function groupByPhase(
  records: NodeIORecord[],
): Array<{ phase: string; records: NodeIORecord[] }> {
  const map = new Map<string, NodeIORecord[]>()
  for (const r of records) {
    const key = r.phase || "unknown"
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(r)
  }
  // Stable, predictable order: tahap_1 → tahap_2 → tahap_3 → tahap_4 → unknown.
  const order: string[] = ["tahap_1", "tahap_2", "tahap_3", "tahap_4"]
  const groups: Array<{ phase: string; records: NodeIORecord[] }> = []
  for (const k of order) {
    if (map.has(k)) {
      groups.push({ phase: k, records: map.get(k)! })
    }
  }
  // Anything not in the explicit order (custom phases, typos) goes
  // at the end, alphabetical.
  for (const k of Array.from(map.keys()).sort()) {
    if (!order.includes(k)) {
      groups.push({ phase: k, records: map.get(k)! })
    }
  }
  return groups
}
