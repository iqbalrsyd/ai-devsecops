import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Shield, ShieldAlert, ShieldCheck, ShieldX, Loader2, PlayCircle } from "lucide-react"

interface RiskScoreGaugeProps {
  score: number | null
  level: string | null
  onAnalyze?: () => void
  analyzing?: boolean
  /**
   * Per-severity finding counts, used to render the small
   * breakdown strip below the score (e.g. "8 crit · 1 high ·
   * 8 med"). Pass an empty object or omit for "not analyzed".
   */
  severity_counts?: {
    critical?: number
    high?: number
    medium?: number
    low?: number
  }
  /**
   * Optional pre-computed CVSS v3.1 sum across the per-bucket
   * `cvss_sum` fields. When the run has not been analyzed yet
   * (`score === null`) but the dashboard has already derived a
   * per-severity CVSS sum (e.g. from the Code Scanning alerts
   * list), the gauge falls back to this number so the headline
   * is never blank. Also used to color the gauge via the same
   * bucket thresholds the Python risk_assessor enforces.
   */
  cvss_sum?: number | null
}

// CVSS-based risk scoring (replaces the old 0-100 inverted OWASP scale).
//
// The score is the SUM of per-finding CVSS v3.1 base scores — higher
// is worse, no inversion. Pipeline-level buckets are system-defined
// (NOT user-configurable) and follow the same thresholds the
// Python risk_assessor enforces:
//   total >= 100 → critical
//   total >= 50  → high
//   total >= 25  → medium
//   else         → low
//
// NB: the per-finding CVSS bands are an entirely separate
// concern (used to color the per-finding badge in the list
// view). They are the FIRST.org standards:
//   score >= 9.0  → critical (red)
//   score >= 7.0  → high     (orange)
//   score >= 4.0  → medium   (amber)
//   score <  4.0  → low      (blue)
// A finding can be labelled "CRITICAL" by the scanner but
// carry a CVSS score of e.g. 5.4 (semgrep rule for
// cors-wildcard-origin). When that happens the per-finding
// badge uses the CVSS band (orange) rather than the
// scanner's severity label so the two stay visually
// consistent.
function isPending(score: number | null, level: string | null): boolean {
  // An analysis is "pending" when we have nothing meaningful to
  // show. The score alone is enough — `getColor`/`getBg`/`getBorder`
  // fall back to the score thresholds (100/50/25) when the level
  // is missing or unrecognised, so the user gets a usable colour
  // even on legacy runs whose `risk_level` is empty/Unknown.
  // Only treat the card as pending when the score itself is
  // missing, null, or literally zero (no findings analysed).
  if (score === null) return true
  if (
    score === 0 &&
    (!level || ["unknown", "not analyzed", ""].includes(level.trim().toLowerCase()))
  ) {
    return true
  }
  return false
}

function getColor(score: number | null, level: string | null): string {
  if (isPending(score, level)) return "text-gray-400"
  if (level) {
    const l = level.toLowerCase()
    if (l === "critical") return "text-red-600"
    if (l === "high") return "text-orange-500"
    if (l === "medium") return "text-yellow-500"
    if (l === "low") return "text-green-500"
  }
  if (score === null) return "text-gray-400"
  if (score >= 100) return "text-red-600"
  if (score >= 50) return "text-orange-500"
  if (score >= 25) return "text-yellow-500"
  return "text-green-500"
}

function getBg(score: number | null, level: string | null): string {
  if (isPending(score, level)) return "bg-gray-50"
  if (level) {
    const l = level.toLowerCase()
    if (l === "critical") return "bg-red-50"
    if (l === "high") return "bg-orange-50"
    if (l === "medium") return "bg-yellow-50"
    if (l === "low") return "bg-green-50"
  }
  if (score === null) return "bg-gray-100"
  if (score >= 100) return "bg-red-50"
  if (score >= 50) return "bg-orange-50"
  if (score >= 25) return "bg-yellow-50"
  return "bg-green-50"
}

function getBorder(level: string | null, score: number | null): string {
  if (isPending(score, level)) return "border-gray-200"
  if (level) {
    const l = level.toLowerCase()
    if (l === "critical") return "border-red-500 border-l-4"
    if (l === "high") return "border-orange-500 border-l-4"
    if (l === "medium") return "border-yellow-500 border-l-4"
    if (l === "low") return "border-green-500 border-l-4"
  }
  if (score === null) return "border-gray-300"
  if (score >= 100) return "border-red-500 border-l-4"
  if (score >= 50) return "border-orange-500 border-l-4"
  if (score >= 25) return "border-yellow-500 border-l-4"
  return "border-green-500 border-l-4"
}

function getIcon(level: string | null, pending: boolean) {
  if (pending) return Loader2
  if (!level) return Shield
  const l = level.toLowerCase()
  if (l === "critical") return ShieldX
  if (l === "high") return ShieldAlert
  if (l === "medium") return ShieldAlert
  if (l === "low") return ShieldCheck
  return Shield
}

function normalizeLevel(level: string | null, score: number | null): string {
  if (score === null) return "Not analyzed"
  if (level && level.trim() !== "" && level.toLowerCase() !== "unknown") {
    return level.charAt(0).toUpperCase() + level.slice(1).toLowerCase()
  }
  // No `level` from the server — derive it from the score
  // using the headline thresholds (100/50/25) so the label
  // and the colour stay in sync.
  if (score >= 100) return "Critical"
  if (score >= 50) return "High"
  if (score >= 25) return "Medium"
  return "Low"
}

export default function RiskScoreGauge({
  score,
  level,
  onAnalyze,
  analyzing,
  severity_counts,
  cvss_sum,
}: RiskScoreGaugeProps) {
  // Fall back to `cvss_sum` (per-bucket CVSS sum the dashboard
  // computes client-side from the alerts list) when the
  // server-side `score` is still pending. Without this the
  // card would show "—" for every run that hasn't been
  // re-analyzed yet, even though the per-finding CVSS values
  // are already known.
  const effectiveScore = score !== null ? score : (cvss_sum ?? null)
  // Synthesize a `level` from the score when the server didn't
  // send one (or sent an "Unknown" sentinel). The thresholds
  // here match the headline bands (100/50/25) and are also
  // enforced by the colour helpers below.
  const scoreDerivedLevel: string | null =
    effectiveScore === null
      ? null
      : effectiveScore >= 100
      ? "critical"
      : effectiveScore >= 50
      ? "high"
      : effectiveScore >= 25
      ? "medium"
      : "low"
  const rawLevel = (level || "").trim().toLowerCase()
  const isUsableLevel = ["critical", "high", "medium", "low"].includes(rawLevel)
  const effectiveLevel = isUsableLevel ? rawLevel : scoreDerivedLevel
  const pending = isPending(effectiveScore, level)
  const Icon = getIcon(effectiveLevel, pending)
  const color = getColor(effectiveScore, effectiveLevel)
  const bg = getBg(effectiveScore, effectiveLevel)
  const border = getBorder(effectiveLevel, effectiveScore)
  const displayLevel = normalizeLevel(effectiveLevel, effectiveScore)

  // Per-bucket counts (with defaults to 0). The Python side
  // produces these in the `severity_breakdown.<bucket>.count`
  // shape; we accept a flat object here so this component
  // stays decoupled from the response shape. The per-bucket
  // chip strip was removed in favour of the dedicated "CVSS
  // Sum by Severity" card on the right; we still need the
  // total count for the subtitle.
  const crit = severity_counts?.critical ?? 0
  const high = severity_counts?.high ?? 0
  const med = severity_counts?.medium ?? 0
  const low = severity_counts?.low ?? 0
  const totalFindings = crit + high + med + low

  // Band chip — a small pill rendered right next to the
  // headline score that explicitly states the band range so
  // the user can see at a glance WHY the number is coloured
  // the way it is (e.g. "≥ 100" → red). When the analysis is
  // still pending we render a neutral "not analyzed" chip
  // instead.
  type BandChip = { label: string; range: string; classes: string } | null
  const bandChip: BandChip = pending
    ? { label: "Not analyzed", range: "no data", classes: "bg-gray-100 text-gray-700 border-gray-300" }
    : effectiveScore === null
      ? null
      : effectiveScore > 100
        ? { label: "CRITICAL", range: "> 100", classes: "bg-red-100 text-red-800 border-red-300" }
        : effectiveScore > 50
          ? { label: "HIGH", range: "50 – 100", classes: "bg-orange-100 text-orange-800 border-orange-300" }
          : effectiveScore > 25
            ? { label: "MEDIUM", range: "25 – 50", classes: "bg-amber-100 text-amber-800 border-amber-300" }
            : { label: "LOW", range: "< 25", classes: "bg-green-100 text-green-800 border-green-300" }

  return (
    <Card className={`${bg} ${border}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Icon className={`h-5 w-5 ${color} ${pending ? "animate-spin" : ""}`} />
          Total CVSS Score
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-2 px-4 pb-4">
        {/* The score number is the headline — no dial, no arc, no
            0-100 inversion. Higher = more risk. The system
            decides the colour bucket from the CVSS sum. */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className={`text-5xl font-bold ${color}`}>
            {effectiveScore !== null ? effectiveScore.toFixed(1) : "—"}
          </span>
          {displayLevel && displayLevel !== "Not analyzed" && displayLevel !== "Unknown" && (
            <span className={`text-sm font-semibold uppercase tracking-wide ${color}`}>
              {displayLevel}
            </span>
          )}
          {/* Band chip — makes the threshold range explicit so
              the user can read WHY the number is red/orange/etc
              without consulting the helper text below. */}
          {bandChip && (
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${bandChip.classes}`}
              title={`Headline band threshold: ${bandChip.range}`}
            >
              <span>{bandChip.label}</span>
              <span className="font-mono opacity-80">· {bandChip.range}</span>
            </span>
          )}
        </div>
        {/* Subtitle: where the number comes from. Kept short
            on purpose — the per-finding CVSS band legend lives
            in the "CVSS Sum by Severity" card on the right, so
            we only need the headline here. */}
        <p className="text-[11px] text-muted-foreground leading-snug">
          {effectiveScore !== null
            ? `CVSS v3.1 sum across ${totalFindings || "—"} ${totalFindings === 1 ? "finding" : "findings"}.`
            : "Run analysis to compute the CVSS v3.1 sum."}
        </p>
        {/* Headline-band threshold reminder. Explains why the
            number above is coloured the way it is, so the
            user does not have to guess. The chip above shows
            the *current* band; this line shows the full
            legend so the user understands where the other
            bands live. */}
        {effectiveScore !== null && (
          <p className="text-[10px] text-muted-foreground/80 leading-snug">
            Headline band: critical &gt; 100, high 50 – 100, medium 25 – 50, low &lt; 25.
          </p>
        )}
        {pending && onAnalyze ? (
          <Button
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={onAnalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
            ) : (
              <PlayCircle className="h-3.5 w-3.5 mr-1" />
            )}
            {analyzing ? "Analyzing…" : "Run Analysis"}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}
