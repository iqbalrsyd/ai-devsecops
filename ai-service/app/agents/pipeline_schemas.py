from pydantic import BaseModel, Field


class GeneratePipelineRequest(BaseModel):
    query: str = Field(description="Natural language requirements for the pipeline")
    repository_id: str = Field(description="GitHub repo ID (full name: owner/repo)")
    project_id: str = Field(description="Project UUID in the database")
    project_type: str = Field(default="monolithic", description="monolithic only (per R2.1 — arsitektur bukan variabel eksperimen)")


class ValidationResult(BaseModel):
    valid: bool = Field(default=False)
    syntax_ok: bool = Field(default=False)
    actions_pinned: bool = Field(default=False)
    permissions_minimal: bool = Field(default=False)
    missing_security_stages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PipelineResponse(BaseModel):
    workflow_yaml: str = Field(description="Generated YAML workflow")
    explanation: str = Field(description="Human-readable explanation")
    stages: list[str] = Field(default_factory=list, description="List of stages included")
    validation: ValidationResult = Field(default_factory=ValidationResult)
    pr_url: str | None = Field(default=None)
    generation_id: str | None = Field(default=None)
    errors: list[str] = Field(default_factory=list)


class DeployRequest(BaseModel):
    repository_id: str = Field(description="GitHub repo full name (owner/repo)")
    workflow_yaml: str = Field(description="Generated workflow YAML")
    workflow_filename: str = Field(default="ci-cd.yml", description="Workflow filename")
    branch_prefix: str = Field(default="ai-devsecops", description="Branch prefix for PR")
    commit_message: str | None = Field(default=None)
    pr_title: str | None = Field(default=None)
    pr_body: str | None = Field(default=None)


class DeployResponse(BaseModel):
    branch: str
    commit_sha: str
    pr_number: int
    pr_url: str
    success: bool = Field(default=True)
    errors: list[str] = Field(default_factory=list)


class StepStatus(BaseModel):
    name: str
    status: str
    conclusion: str | None = None
    number: int


class JobStatus(BaseModel):
    id: int
    name: str
    status: str
    conclusion: str | None = None
    steps: list[StepStatus] = Field(default_factory=list)


class ExecutionStatus(BaseModel):
    run_id: int
    status: str
    conclusion: str | None = None
    html_url: str
    jobs: list[JobStatus] = Field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: int | None = None


class SecurityFinding(BaseModel):
    type: str = Field(description="Type of finding")
    severity: str = Field(description="critical/high/medium/low")
    file: str | None = None
    line: int | None = None
    code_snippet: str | None = None
    explanation: str
    recommendation: str
    cwe: str | None = None
    owasp: str | None = None
    scanner: str | None = Field(default=None, description="semgrep | trivy | gitleaks | dep-check")


class ComplianceMapping(BaseModel):
    framework: str = Field(description="OWASP_ASVS | CIS | SOC2")
    control_id: str
    control_name: str
    status: str = Field(description="passed | failed | not_applicable")
    finding_refs: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    summary: str
    findings: list[SecurityFinding] = Field(default_factory=list)
    risk_score: float | None = None
    risk_level: str | None = Field(default=None, description="critical/high/medium/low")
    compliance_score: float | None = None
    compliance_mappings: list[ComplianceMapping] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)