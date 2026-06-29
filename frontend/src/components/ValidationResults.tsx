import { CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface ValidationResult {
  valid: boolean
  syntax_ok: boolean
  actions_pinned: boolean
  permissions_minimal: boolean
  missing_security_stages: string[]
  warnings: string[]
  errors: string[]
}

interface ValidationResultsProps {
  validation: ValidationResult | null
}

export default function ValidationResults({ validation }: ValidationResultsProps) {
  if (!validation) return null

  const checks = [
    { label: "YAML Syntax", passed: validation.syntax_ok },
    { label: "Actions Pinned to SHA", passed: validation.actions_pinned },
    { label: "Minimal Permissions", passed: validation.permissions_minimal },
  ]

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          {validation.valid ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <XCircle className="h-5 w-5 text-red-500" />
          )}
          Validation {validation.valid ? "Passed" : "Failed"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {checks.map((check) => (
          <div key={check.label} className="flex items-center gap-2 text-sm">
            {check.passed ? (
              <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500 shrink-0" />
            )}
            <span className={check.passed ? "text-muted-foreground" : "text-foreground font-medium"}>
              {check.label}
            </span>
          </div>
        ))}

        {validation.missing_security_stages.length > 0 && (
          <div className="pt-2">
            <p className="text-sm font-medium text-amber-600 flex items-center gap-1 mb-1">
              <AlertTriangle className="h-4 w-4" />
              Missing Security Stages
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {validation.missing_security_stages.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {validation.warnings.length > 0 && (
          <div className="pt-2">
            <p className="text-sm font-medium text-amber-600 flex items-center gap-1 mb-1">
              <Info className="h-4 w-4" />
              Warnings
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {validation.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {validation.errors.length > 0 && (
          <div className="pt-2">
            <p className="text-sm font-medium text-red-600 flex items-center gap-1 mb-1">
              <XCircle className="h-4 w-4" />
              Errors
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {validation.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}