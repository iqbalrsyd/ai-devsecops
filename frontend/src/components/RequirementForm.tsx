import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

const LANGUAGES = ["Node.js", "Python", "Go", "Java", "TypeScript"]
const FRAMEWORKS: Record<string, string[]> = {
  "Node.js": ["Express", "Next.js"],
  Python: ["Django", "FastAPI", "Flask"],
  Go: ["Gin", "Echo"],
  Java: ["Spring Boot"],
  TypeScript: ["Next.js", "Express"],
}
const DEPLOY_TARGETS = ["Docker", "Kubernetes", "AWS ECS", "Cloud Run"]
const SECURITY_OPTIONS = [
  { id: "sast", label: "SAST", description: "Static code analysis" },
  { id: "dependency-scan", label: "Dependency Scan", description: "Vulnerable dependencies" },
  { id: "secret-scan", label: "Secret Scan", description: "Detect leaked secrets" },
  { id: "container-scan", label: "Container Scan", description: "Image vulnerability scan" },
]

const PIPELINE_MODES = [
  {
    id: "general",
    label: "General only",
    description: "Lint / SAST / dependency / secret scan (universal baseline).",
  },
  {
    id: "domain",
    label: "Domain-specific only",
    description: "Only the AI-designed jobs for the detected domain (e-commerce / blog / iot).",
  },
  {
    id: "both",
    label: "General + Domain",
    description: "Full pipeline with both general checks and domain compliance.",
  },
] as const

export type PipelineMode = "general" | "domain" | "both"

interface GenerationOptions {
  language: string
  framework: string
  deployTarget: string
  projectType: string
  securityReqs: string[]
  pipelineMode: PipelineMode
}

interface RequirementFormProps {
  onGenerate: (query: string, options: GenerationOptions) => void
  isLoading: boolean
}

export default function RequirementForm({ onGenerate, isLoading }: RequirementFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [language, setLanguage] = useState("")
  const [framework, setFramework] = useState("")
  const [deployTarget, setDeployTarget] = useState("")
  const [projectType, setProjectType] = useState("monolithic")
  const [securityReqs, setSecurityReqs] = useState<string[]>([])
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>("both")

  const toggleSecurity = (id: string) => {
    setSecurityReqs((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    )
  }

  const buildQuery = () => {
    const parts: string[] = []
    if (language) {
      parts.push(`Create a secure CI/CD pipeline for a ${language} application`)
    } else {
      parts.push("Auto-detect and create a secure CI/CD pipeline for this repository")
    }
    if (framework) parts.push(`using ${framework}`)
    if (deployTarget) parts.push(`with ${deployTarget} deployment`)
    if (securityReqs.length > 0) {
      const scanners = securityReqs
        .map((s) => ({ sast: "SAST", "dependency-scan": "dependency scanning", "secret-scan": "secret detection", "container-scan": "container scanning" })[s])
        .join(", ")
      parts.push(`including ${scanners}`)
    }
    parts.push("with OWASP-aligned security checks")
    return parts.join(", ")
  }

  const handleGenerate = () => {
    onGenerate(buildQuery(), {
      language,
      framework,
      deployTarget,
      projectType,
      securityReqs,
      pipelineMode,
    })
  }

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base font-semibold">Pipeline Requirements</CardTitle>
        <CardDescription>
          Configure how the CI/CD pipeline should be generated
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <Button
          onClick={handleGenerate}
          disabled={isLoading}
          className="w-full h-11 text-sm font-medium"
          size="default"
        >
          {isLoading ? "Generating pipeline..." : "Auto-Detect & Generate Pipeline"}
        </Button>

        <p className="text-xs text-muted-foreground text-center">
          AI will auto-detect language, framework, and architecture from the repository
        </p>

        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mx-auto transition-colors"
        >
          <span className="w-3 h-3 flex items-center justify-center">
            {showAdvanced ? "−" : "+"}
          </span>
          {showAdvanced ? "Hide advanced options" : "Advanced options"}
        </button>

        {showAdvanced && (
          <div className="space-y-5 pt-2 border-t border-border">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Language</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  value={language}
                  onChange={(e) => { setLanguage(e.target.value); setFramework("") }}
                >
                  <option value="">Auto-detect</option>
                  {LANGUAGES.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Framework</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  disabled={!language}
                >
                  <option value="">Auto-detect</option>
                  {(FRAMEWORKS[language] || []).map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Deployment Target</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  value={deployTarget}
                  onChange={(e) => setDeployTarget(e.target.value)}
                >
                  <option value="">Auto-detect</option>
                  {DEPLOY_TARGETS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Project Type</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  value={projectType}
                  onChange={(e) => setProjectType(e.target.value)}
                >
                  <option value="monolithic">Monolithic</option>
                  <option value="modular_monolith">Modular Monolith (FE/BE split)</option>
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-medium">Security Requirements</Label>
              <div className="grid grid-cols-2 gap-2">
                {SECURITY_OPTIONS.map((opt) => {
                  const selected = securityReqs.includes(opt.id)
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => toggleSecurity(opt.id)}
                      className={`text-left rounded-md border px-3 py-2.5 transition-colors ${
                        selected
                          ? "border-foreground bg-foreground text-primary-foreground"
                          : "border-border bg-card hover:border-foreground/30 hover:bg-accent"
                      }`}
                    >
                      <div className="text-xs font-medium">{opt.label}</div>
                      <div className={`text-[10px] mt-0.5 ${selected ? "text-primary-foreground/80" : "text-muted-foreground"}`}>
                        {opt.description}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-medium">Pipeline Mode</Label>
              <div className="grid grid-cols-1 gap-2">
                {PIPELINE_MODES.map((mode) => {
                  const selected = pipelineMode === mode.id
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => setPipelineMode(mode.id)}
                      className={`text-left rounded-md border px-3 py-2.5 transition-colors ${
                        selected
                          ? "border-foreground bg-foreground text-primary-foreground"
                          : "border-border bg-card hover:border-foreground/30 hover:bg-accent"
                      }`}
                    >
                      <div className="text-xs font-medium">{mode.label}</div>
                      <div className={`text-[10px] mt-0.5 ${selected ? "text-primary-foreground/80" : "text-muted-foreground"}`}>
                        {mode.description}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
