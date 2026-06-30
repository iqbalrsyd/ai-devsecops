from typing import TypedDict


class PipelineEngineerState(TypedDict):
    request_type: str
    github_token: str
    repository_url: str | None
    repository_full_name: str
    repository_default_branch: str | None

    repository_structure: list | None
    repository_files: dict | None
    source_files: list[dict]
    existing_workflows: list | None
    detected_technologies: dict | None
    detected_architecture: dict | None
    detected_architecture_type: str | None
    detected_architecture_confidence: float | None
    detected_architecture_reason: str | None
    detected_deployment: dict | None
    recommended_deployment_target: str | None

    # Multi-language support: list of LanguageProfile.id values that
    # the workflow generator should emit jobs for. Populated by
    # `language_profiles.resolve_active_profiles` in
    # `workflow_generator_node`. Empty list means "language-agnostic
    # repo" — caller should rely on the universal Trivy fs scan only.
    active_language_profiles: list[str]

    # Skip custom (domain-specific) jobs and emit only the standard
    # set (lint, test, sast, secret-scan, dependency-scan,
    # container-scan). Populated by `pipeline_service` from the
    # `AI_DEVSECOPS_GENERAL_ONLY` env var. Also implicitly True when
    # `domain_confidence < 0.5` (heuristic veto fell back to
    # "general" because the LLM classifier over-fit on a weak
    # signal). The `workflow_generator_node` honours this flag.
    general_only: bool

    # Tahap 1 (Tambah v9)
    detected_domain: str | None
    domain_sub_type: str | None
    domain_confidence: float | None
    domain_evidence: list
    domain_threats: list
    features: list
    domain_priority: list | None

    # Tahap 2 (Tambah v9)
    security_coverages: list
    coverage_inference_reasoning: str | None
    ai_generated_rules: list
    pattern_inference_reasoning: str | None
    pattern_inference_valid_count: int
    pipeline_augmentations: list
    inferred_security_needs: dict | None
    job_designs: list
    job_designs_reasoning: str | None
    job_designs_valid_count: int

    # Tahap 3 (Tambah v9)
    custom_semgrep_rules_yaml: str | None
    custom_semgrep_rules_path: str | None
    custom_semgrep_rules: list
    stage_explanations: list
    vignette_context: dict | None
    invalid_workflow_stages: list
    skipped_jobs: list
    workflow_config_issues: list
    auto_fixes: list
    external_service_issues: list
    warnings: list
    removed_legacy_workflows: list

    generated_workflow: str | None
    generated_workflow_generic: str | None
    generated_workflow_custom: str | None
    generated_workflow_files: list[dict]
    generated_stages: list[str]
    generated_stages_general: list[str]
    generated_stages_custom: list[str]
    generation_explanation: str | None

    validation_errors: list[str]
    validation_warnings: list[str]
    validation_passed: bool

    github_branch: str | None
    github_commit_sha: str | None
    github_pr_number: int | None
    github_pr_url: str | None

    workflow_run_id: int | None
    workflow_status: str | None
    workflow_conclusion: str | None
    workflow_logs: list[dict]
    workflow_jobs: list[dict]
    workflow_duration_seconds: int | None

    failed_jobs: list[dict]
    failed_steps: list[dict]
    failure_logs: dict
    failure_analysis: dict | None
    root_cause: dict | None
    remediation_suggestions: list[dict]
    remediation_workflow: str | None
    remediation_branch: str | None
    remediation_pr_number: int | None
    remediation_pr_url: str | None

    scan_results: dict | None
    findings: list
    risk_score: float | None
    security_posture: float | None
    compliance_score: float | None
    compliance_mappings: list[dict]
    severity_breakdown: dict | None
    recommendations: list
    summary: str | None

    # Tahap 4 (Tambah v9)
    domain_context: dict | None
    workflow_annotations: list
    validation_findings: list
    pdf_report_path: str | None
    remediation_recommendations: list

    errors: list[str]
    error_stage: str | None
    auto_deploy: bool

    pipeline_version: int
    workflow_file: str | None
