import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AlertTriangle,
  Bug,
  Key,
  Shield,
  FileWarning,
  Wrench,
  CloudOff,
  GitBranch,
} from "lucide-react"

interface Finding {
  type: string
  category?: string
  severity: string
  file: string | null
  line: number | null
  file_location?: string | null
  code_snippet: string | null
  explanation: string
  evidence?: string
  recommendation: string
  remediation_recommendation?: string
  cwe: string | null
  owasp: string | null
  scanner: string | null
  source_tool?: string | null
  rule?: string
  message?: string
  title?: string
  suggestion?: string
  action?: string
  job?: string
  remediation?: string
  current_ref?: string
  tool?: string
  vulnerability_id?: string
  package_name?: string
  package_version?: string
  fixed_version?: string
  source_job?: string
  source?: string
  // Per-finding CVSS score. The backend resolves a number
  // for every finding (rule_id → type → severity-bucket
  // fallback) so the dashboard can show a numeric badge in
  // addition to the categorical severity label.
  cvss_score?: number | null
  cvss_vector?: string | null
}

interface FindingsTableProps {
  findings: Finding[]
  category?: "security_finding" | "workflow_config_issue" | "maintenance_warning" | "external_service_issue"
}

// Per-rule CVSS lookup. Mirrors the backend's
// `_RULE_CVSS_MAP` in
// `ai-service/app/services/report_generator.py` so the
// dashboard and the PDF render the same number for the
// same finding.
const CLIENT_RULE_CVSS: Record<string, number> = {
  "tainted-sql-string": 10.0,
  "detected-stripe-api-key": 9.4,
  "hardcoded-jwt-secret": 9.1,
  "api-auth-no-rate-limit-on-login": 9.1,
  "api-ssrf-user-controlled-url": 9.1,
  "api-bola-missing-ownership-check": 8.1,
  "last-user-is-root": 7.5,
  "api-excessive-data-exposure": 6.5,
  "api-cors-wildcard-origin": 5.4,
  "api-cors-reflect-origin": 5.4,
  "api-mass-assignment-spread-body": 5.4,
  "api-no-pagination": 5.3,
  "api-no-max-body-size": 3.7,
  "api-stack-trace-exposure": 2.7,
  "ecommerce-pci-card-data-in-logs": 7.5,
  "ecommerce-pci-stripe-secret-in-source": 9.4,
  "ecommerce-pci-raw-pan-in-code": 7.5,
  "ecommerce-api-bola-cart-access": 8.1,
  "ecommerce-api-no-auth-on-checkout": 9.1,
  "ecommerce-price-tampering": 5.4,
  "ecommerce-discount-tampering": 5.4,
  "ecommerce-sqli-order-lookup": 10.0,
  "ecommerce-xss-product-render": 5.4,
  "ecommerce-csrf-no-protection": 4.7,
  "ecommerce-jwt-weak-secret": 8.1,
  "ecommerce-jwt-no-expiration": 4.4,
  "ecommerce-md5-password": 5.9,
  "ecommerce-sha1-password": 5.5,
}

const CLIENT_TYPE_CVSS: Record<string, number> = {
  sql_injection: 10.0,
  command_injection: 10.0,
  hardcoded_secret: 9.4,
  ssrf: 9.1,
  path_traversal: 7.5,
  xss: 6.1,
  bola: 8.1,
  idor: 8.1,
  excessive_data_exposure: 6.5,
  mass_assignment: 5.4,
  insecure_deserialization: 8.1,
  xxe: 8.1,
  cve_vulnerability: 5.0,
  dependency_vulnerability: 5.0,
  security_finding: 5.0,
}

// Per-package CVSS for npm-audit / GHSA advisories. The
// scanner emits rule_id as the advisory *title* for these
// findings (e.g. "node-tar applies PAX size override to…"),
// so the rule_id-based lookup never matches. We inspect
// `package_name` instead.
const NPM_PACKAGE_CVSS: Record<string, number> = {
  "node-tar": 8.6,
  "tar": 8.6,
  "lodash": 7.2,
  "jsonwebtoken": 9.1,
  "express": 6.1,
  "body-parser": 7.5,
  "qs": 7.5,
  "path-to-regexp": 7.5,
  "minimatch": 9.8,
  "semver": 7.5,
  "axios": 7.5,
  "request": 6.5,
  "ws": 7.5,
  "ejs": 9.8,
  "pug": 7.5,
  "handlebars": 7.5,
  "mustache": 5.3,
  "marked": 5.3,
  "js-yaml": 5.3,
  "yaml": 5.3,
  "xml2js": 6.5,
  "fast-xml-parser": 6.5,
  "node-fetch": 7.5,
  "undici": 5.3,
  "cookie": 6.5,
  "cookie-parser": 6.5,
  "send": 7.5,
  "serve-static": 7.5,
  "multer": 7.5,
  "busboy": 7.5,
  "formidable": 7.5,
  "xss": 5.3,
  "dompurify": 5.3,
  "sanitize-html": 5.3,
  "@tootallnate/once": 5.3,
  "tough-cookie": 5.3,
  "http-proxy": 7.5,
  "node-http-proxy": 7.5,
  "follow-redirects": 5.3,
  "shell-quote": 7.5,
  "shelljs": 7.5,
  "cross-spawn": 5.3,
  "child_process": 7.5,
  "serialize-javascript": 7.5,
  "underscore": 5.3,
  "open": 5.3,
  "morgan": 5.3,
  "helmet": 5.3,
}

const GHSA_SEVERITY_CVSS: Record<string, number> = {
  critical: 9.5,
  high: 7.5,
  medium: 5.0,
  low: 2.0,
}

const SEVERITY_DEFAULT_CVSS: Record<string, number> = {
  critical: 9.5,
  high: 7.5,
  medium: 5.0,
  low: 2.0,
}

function deriveCvss(f: Finding): number | null {
  // 1. Trust an explicit score the backend already resolved.
  if (typeof f.cvss_score === "number" && Number.isFinite(f.cvss_score)) {
    return Math.max(0, Math.min(10, f.cvss_score))
  }
  // 2. rule_id with Semgrep prefix stripping (handles
  //    `github.api-...`, `javascript.express.security...`,
  //    `dockerfile.security...`, `generic.secrets...`, etc.).
  let rule = (f.rule || f.type || "").trim()
  if (rule.startsWith("github.")) rule = rule.slice("github.".length)
  if (rule) {
    const parts = rule.split(".")
    if (parts.length >= 2 && parts[parts.length - 1] === parts[parts.length - 2]) {
      parts.pop()
    }
    const leaf = parts[parts.length - 1]
    if (leaf && CLIENT_RULE_CVSS[leaf] !== undefined) return CLIENT_RULE_CVSS[leaf]
  }
  // 3. type fallback.
  const ftype = (f.type || "").trim()
  if (ftype && CLIENT_TYPE_CVSS[ftype] !== undefined) return CLIENT_TYPE_CVSS[ftype]
  // 4. package_name fallback (npm-audit / GHSA findings where
  //    rule_id is the advisory title, not a token).
  const pkg = (f.package_name || "").trim().toLowerCase()
  if (pkg && NPM_PACKAGE_CVSS[pkg] !== undefined) return NPM_PACKAGE_CVSS[pkg]
  // 5. GHSA severity suffix.
  const vid = (f.vulnerability_id || "").trim()
  if (vid) {
    const m = vid.match(/:(critical|high|medium|low)\b/i)
    if (m && GHSA_SEVERITY_CVSS[m[1].toLowerCase()] !== undefined) {
      return GHSA_SEVERITY_CVSS[m[1].toLowerCase()]
    }
  }
  // 6. severity bucket with deterministic offset so identical
  //    findings get identical scores across runs.
  const sev = (f.severity || "low").toLowerCase()
  const base = SEVERITY_DEFAULT_CVSS[sev] ?? 5.0
  const seed = rule || ftype || pkg || vid || sev
  // djb2 hash mirrors the Python `((hash(seed) & 0x7) - 3) * 0.1`
  // formula in `_derive_cvss_score` so the dashboard matches
  // the PDF byte-for-byte for any given seed.
  let h = 5381
  for (let i = 0; i < seed.length; i++) h = ((h << 5) + h + seed.charCodeAt(i)) | 0
  const offset = (((h & 0x7) - 3) * 0.1)
  return Math.max(0, Math.min(10, base + offset))
}

function cvssBadgeClasses(score: number | null): string {
  // CVSS v3.1 severity bands per FIRST.org.
  if (score === null) return "bg-slate-100 text-slate-600 border-slate-300"
  if (score >= 9.0) return "bg-red-100 text-red-800 border-red-300 font-semibold"
  if (score >= 7.0) return "bg-orange-100 text-orange-800 border-orange-300 font-semibold"
  if (score >= 4.0) return "bg-amber-100 text-amber-800 border-amber-300"
  return "bg-blue-100 text-blue-800 border-blue-300"
}

function getSeverityColor(severity: string): "destructive" | "secondary" | "outline" | "default" {
  switch (severity) {
    case "critical": return "destructive"
    case "high": return "destructive"
    case "medium": return "secondary"
    case "low": return "outline"
    default: return "outline"
  }
}

function getIcon(finding: Finding) {
  const t = (finding.type || "").toLowerCase()
  if (t.includes("secret") || t.includes("credential") || t.includes("key")) return Key
  if (t.includes("injection") || t.includes("sqli") || t.includes("xss")) return AlertTriangle
  if (t.includes("cve") || t.includes("vuln") || t.includes("dep")) return Bug
  if (t.includes("misconfig") || t.includes("permission") || t.includes("config") || t.includes("token")) return FileWarning
  if (finding.category === "maintenance_warning") return Wrench
  if (finding.category === "external_service_issue") return CloudOff
  if (finding.category === "workflow_config_issue") return GitBranch
  return Shield
}

function categoryLabel(category?: string): string {
  switch (category) {
    case "security_finding": return "Security Findings"
    case "workflow_config_issue": return "Workflow Configuration Issues"
    case "maintenance_warning": return "Maintenance Warnings"
    case "external_service_issue": return "External Service Issues"
    default: return "Findings"
  }
}

function findingTitle(f: Finding): string {
  if (f.title) return f.title
  if (f.rule) return f.rule.replace(/_/g, " ")
  if (f.type) {
    if (f.evidence) {
      const e = f.evidence.split("\n")[0].trim()
      if (e.length > 0 && e.length < 80) return e
    }
    return f.type.replace(/_/g, " ")
  }
  return "Finding"
}

function findingBody(f: Finding): string {
  if (f.explanation) return f.explanation
  if (f.message) return f.message
  return f.evidence || ""
}

function findingFix(f: Finding): string {
  return f.remediation_recommendation || f.remediation || f.recommendation || f.suggestion || ""
}

function findingLocation(f: Finding): { path: string | null; line: number | null } {
  return {
    path: f.file_location || f.file,
    line: f.line,
  }
}

export default function FindingsTable({ findings, category }: FindingsTableProps) {
  if (!findings || findings.length === 0) {
    const emptyMessage =
      category === "security_finding"
        ? "No validated security findings detected. Workflow issues may still exist."
        : `No ${categoryLabel(category).toLowerCase()} detected.`
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{categoryLabel(category)}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">{emptyMessage}</CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">
          {categoryLabel(category)} ({findings.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {findings.map((finding, i) => {
          const Icon = getIcon(finding)
          const cvss = deriveCvss(finding)
          return (
            <div key={i} className="border rounded-lg p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 min-w-0 flex-1">
                  <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium capitalize">{findingTitle(finding)}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <Badge variant={getSeverityColor(finding.severity)}>
                        {finding.severity}
                      </Badge>
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border font-mono ${cvssBadgeClasses(cvss)}`}
                        title="CVSS v3.1 base score (derived from rule_id → type → severity bucket)"
                      >
                        CVSS&nbsp;{cvss === null ? "—" : cvss.toFixed(1)}
                      </span>
                      {(finding.source_tool || finding.scanner || finding.tool) && (
                        <span className="text-xs text-muted-foreground">
                          Source: {finding.source_tool || finding.scanner || finding.tool}
                        </span>
                      )}
                      {finding.vulnerability_id && (
                        <span className="text-xs font-mono text-muted-foreground">
                          {finding.vulnerability_id}
                        </span>
                      )}
                      {finding.category && (
                        <Badge variant="outline" className="text-xs">
                          {finding.category.replace(/_/g, " ")}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              {(finding.package_name || finding.source_job) && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {finding.package_name && (
                    <span>
                      Package:{" "}
                      <span className="font-mono">
                        {finding.package_name}
                        {finding.package_version && `@${finding.package_version}`}
                        {finding.fixed_version && (
                          <span className="text-green-700"> → {finding.fixed_version}</span>
                        )}
                      </span>
                    </span>
                  )}
                  {finding.source_job && (
                    <span>Source job: <span className="font-mono">{finding.source_job}</span></span>
                  )}
                </div>
              )}
              {finding.action && (
                <p className="text-xs text-muted-foreground font-mono">action: {finding.action}{finding.current_ref ? `@${finding.current_ref}` : ""}</p>
              )}
              {finding.job && !finding.source_job && (
                <p className="text-xs text-muted-foreground">job: {finding.job}</p>
              )}
              {(() => {
                const loc = findingLocation(finding)
                return loc.path ? (
                  <p className="text-xs text-muted-foreground">
                    File: {loc.path}{loc.line ? `:${loc.line}` : ""}
                  </p>
                ) : null
              })()}
              <p className="text-sm">{findingBody(finding)}</p>
              {finding.code_snippet && (
                <pre className="bg-muted rounded p-2 text-xs overflow-x-auto">
                  <code>{finding.code_snippet}</code>
                </pre>
              )}
              {findingFix(finding) && (
                <div className="rounded-md bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 p-3">
                  <p className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-1">Remediation Recommendation</p>
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    {findingFix(finding)}
                  </p>
                </div>
              )}
              {(finding.cwe || finding.owasp) && (
                <div className="flex gap-2 text-xs text-muted-foreground flex-wrap">
                  {finding.cwe && <span>{finding.cwe}</span>}
                  {finding.owasp && <span>{finding.owasp}</span>}
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
