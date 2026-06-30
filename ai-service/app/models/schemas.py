from pydantic import BaseModel, Field
from typing import Optional, Literal


class DetectionConfidence(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reason: str = Field(description="Why this confidence level")


class TechnologyDetection(BaseModel):
    primary_language: str = Field(description="Main programming language")
    primary_language_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    primary_language_reason: str = Field(description="Reason for language detection")
    frameworks: list[str] = Field(description="Detected frameworks")
    framework_confidences: list[float] = Field(description="Confidence scores for frameworks")
    build_tools: list[str] = Field(description="Build systems")
    package_manager: str = Field(description="Package manager used")
    package_manager_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    test_framework: Optional[str] = Field(None, description="Testing framework")
    database: Optional[str] = Field(None, description="Primary database")
    runtime: Optional[str] = Field(None, description="Runtime environment")


class ArchitectureDetection(BaseModel):
    # Per R2.1, arsitektur bukan variabel eksperimen. Always "monolithic".
    architecture_type: Literal["monolithic"] = Field(description="Architecture type — always 'monolithic' per R2.1")
    architecture_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    architecture_reason: str = Field(description="Why this architecture was detected")
    service_count: Optional[int] = Field(None, description="Number of services")
    service_names: Optional[list[str]] = Field(None, description="Service names (legacy, always empty per R2.1)")
    has_api_gateway: bool = Field(default=False, description="Has API gateway")
    has_message_queue: bool = Field(default=False, description="Has message queue")
    has_database_config: bool = Field(default=False, description="Has database configuration")
    is_containerized: bool = Field(default=False, description="Is containerized")
    has_shared_libraries: bool = Field(default=False, description="Has shared libraries")


class DeploymentDetection(BaseModel):
    docker: bool = Field(default=False, description="Docker detected")
    docker_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    docker_reason: str = Field(description="Why Docker was detected")
    docker_compose: bool = Field(default=False, description="Docker Compose detected")
    docker_compose_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    kubernetes: bool = Field(default=False, description="Kubernetes detected")
    kubernetes_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    kubernetes_reason: str = Field(description="Why Kubernetes was detected")
    terraform: bool = Field(default=False, description="Terraform detected")
    terraform_confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    helm: bool = Field(default=False, description="Helm detected")
    cloud_provider: Optional[str] = Field(None, description="Detected cloud provider (AWS/Azure/GCP)")
    recommended_deployment_target: str = Field(description="Recommended deployment target")
    alternative_deployment_targets: list[str] = Field(default_factory=list, description="Alternative targets")
    deployment_reason: str = Field(description="Why this deployment target is recommended")


class RepositoryAnalysis(BaseModel):
    technologies: TechnologyDetection
    architecture: ArchitectureDetection
    deployment: DeploymentDetection
    source_files: list[str] = Field(default_factory=list, description="Key source files detected")
    existing_workflows: list[str] = Field(default_factory=list, description="Existing GitHub workflows")
    repository_size: Optional[str] = Field(None, description="Repository size category")
    detected_at: str = Field(description="Timestamp of detection")


class SecurityControl(BaseModel):
    control: str = Field(description="Control name (lint, sast, etc.)")
    status: Literal["recommended", "optional", "not_required"] = Field(description="Control status")
    reason: str = Field(description="Why this status")
    tool: Optional[str] = Field(None, description="Recommended tool")
    tool_version: str = Field(default="latest", description="Tool version")


class SecurityRequirementResponse(BaseModel):
    security_controls: list[SecurityControl]
    required_tools: list[dict]
    pipeline_stages: list[dict]
    total_controls: int
    recommended_count: int
    optional_count: int
    not_required_count: int


class DeploymentAnalysisResponse(BaseModel):
    recommended_target: str
    alternative_targets: list[str]
    reasons: list[str]
    cloud_provider: Optional[str]


class WorkflowResponse(BaseModel):
    generated_workflow: Optional[str]
    generated_stages: list[str]
    generation_explanation: Optional[str]
    validation_passed: bool
    validation_errors: list[str]
    validation_warnings: list[str]


class PipelineGenerationResponse(BaseModel):
    repository_analysis: RepositoryAnalysis
    security_requirements: SecurityRequirementResponse
    deployment_analysis: DeploymentAnalysisResponse
    workflow: WorkflowResponse
    deployment: Optional[dict] = Field(default_factory=dict)
    analysis: Optional[dict] = Field(default_factory=dict)
    metadata: dict


class PipelineGenerationRequest(BaseModel):
    repository_url: str = Field(description="GitHub repository URL or full name")
    github_token: Optional[str] = Field(None, description="GitHub personal access token")
    project_id: Optional[str] = Field(None, description="Project ID")
    query: Optional[str] = Field(None, description="Custom instructions")
    options: Optional[dict] = Field(default_factory=dict, description="Generation options")
    preferences: Optional[dict] = Field(default_factory=dict, description="User preferences")


class ExecutionLogSummary(BaseModel):
    job_name: str
    step_name: str
    exit_code: Optional[int] = None
    failed_command: Optional[str] = None
    error_message: Optional[str] = None
    log_snippet: Optional[str] = None


class RootCauseAnalysis(BaseModel):
    failure_type: str
    root_cause: str
    confidence: float
    evidence: list[str]
    affected_components: list[str]
    fix_type: str = Field(pattern="workflow|code|config|dependency")


class RemediationSuggestion(BaseModel):
    file_path: str
    change_type: str = Field(pattern="create|modify|delete")
    before: Optional[str] = None
    after: str
    reasoning: str
    risk: str = Field(pattern="low|medium|high")
    confidence: float = Field(ge=0.0, le=1.0)


class FailureAnalysis(BaseModel):
    failure_type: str = Field(description="Category of the failure")
    root_cause: str = Field(description="Root cause description")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    explanation: str = Field(description="Detailed explanation")
    recommended_fix: str = Field(description="Recommended fix")


class WorkflowFix(BaseModel):
    before: str = Field(description="Original problematic YAML/code")
    after: str = Field(description="Fixed YAML/code")
    reasoning: str = Field(description="Why the fix works")
    risk: str = Field(pattern="low|medium|high", description="Risk level")


class ExecutionFailureFix(BaseModel):
    failure_type: str = Field(description="Type of failure: dependency_error, permission_error, action_not_found, env_var_missing, step_timeout, docker_build_error, deployment_error, permission_denied, network_error, other")
    job_name: str = Field(description="Name of the failed job")
    step_name: str = Field(description="Name of the failed step")
    root_cause: str = Field(description="Root cause of the failure")
    fix_strategy: str = Field(description="Strategy to fix: update_action, add_permission, fix_env, retry_step, simplify_job, add_conditions, other")
    yaml_changes: str = Field(description="The corrected YAML section to replace in the workflow")
    reasoning: str = Field(description="Why this fix works")
    risk: str = Field(pattern="low|medium|high", description="Risk level of applying this fix")
