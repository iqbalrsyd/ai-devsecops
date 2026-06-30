import json
from datetime import datetime
from app.agents.pipeline_state import PipelineEngineerState


def response_formatter_node(state: PipelineEngineerState) -> PipelineEngineerState:
    findings = state.get("findings", [])
    risk_score = state.get("risk_score")
    security_posture = state.get("security_posture")
    recommendations = state.get("recommendations", [])
    compliance_score = state.get("compliance_score")
    severity_breakdown = state.get("severity_breakdown", {})

    issues_count = len(findings)
    if risk_score is not None:
        if risk_score >= 70:
            risk_level = "critical"
        elif risk_score >= 40:
            risk_level = "high"
        elif risk_score >= 20:
            risk_level = "medium"
        else:
            risk_level = "low"
    else:
        risk_level = "unknown"

    summary_parts = []
    if issues_count > 0:
        summary_parts.append(f"Found {issues_count} security issue(s).")
    if risk_score is not None:
        summary_parts.append(f"Risk score: {risk_score}/100 ({risk_level}).")
    if security_posture is not None:
        summary_parts.append(f"Security posture: {security_posture}/100.")
    if compliance_score is not None:
        summary_parts.append(f"Compliance: {compliance_score}%.")
    if recommendations:
        summary_parts.append(f"Generated {len(recommendations)} recommendation(s).")
    summary = " ".join(summary_parts) if summary_parts else "Analysis complete. No findings detected."

    validated_findings = []
    for f in findings:
        if isinstance(f, dict):
            validated_findings.append(f)
        else:
            validated_findings.append(f)

    state["summary"] = summary
    state["severity_breakdown"] = severity_breakdown

    repository_analysis = _build_repository_analysis(state)
    state["repository_analysis"] = repository_analysis

    security_explanation = _build_security_explanation(state)
    state["security_explanation"] = security_explanation

    deployment_explanation = _build_deployment_explanation(state)
    state["deployment_explanation"] = deployment_explanation

    unified_response = _build_unified_response(state)
    state["unified_response"] = unified_response

    return state


def _build_repository_analysis(state: PipelineEngineerState) -> dict:
    technologies = state.get("detected_technologies", {}) or {}
    architecture = state.get("detected_architecture", {}) or {}
    deployment = state.get("detected_deployment", {}) or {}

    return {
        "technologies": {
            "primary_language": technologies.get("primary_language", "Unknown"),
            "primary_language_confidence": technologies.get("primary_language_confidence", 0.0),
            "primary_language_reason": technologies.get("primary_language_reason", ""),
            "frameworks": technologies.get("frameworks", []),
            "framework_confidences": technologies.get("framework_confidences", []),
            "build_tools": technologies.get("build_tools", []),
            "package_manager": technologies.get("package_manager", ""),
            "package_manager_confidence": technologies.get("package_manager_confidence", 0.0),
            "test_framework": technologies.get("test_framework"),
            "database": technologies.get("database"),
            "runtime": technologies.get("runtime"),
        },
        "architecture": {
            "architecture_type": architecture.get("architecture_type", "monolithic"),
            "architecture_confidence": state.get("detected_architecture_confidence", 0.0),
            "architecture_reason": state.get("detected_architecture_reason", ""),
            "service_count": architecture.get("service_count"),
            "service_names": architecture.get("service_names", []),
            "has_api_gateway": architecture.get("has_api_gateway", False),
            "has_message_queue": architecture.get("has_message_queue", False),
            "has_database_config": architecture.get("has_database_config", False),
            "is_containerized": architecture.get("is_containerized", False),
            "has_shared_libraries": architecture.get("has_shared_libraries", False),
        },
        "deployment": {
            "docker": deployment.get("docker", False),
            "docker_confidence": deployment.get("docker_confidence", 0.0),
            "docker_reason": deployment.get("docker_reason", ""),
            "docker_compose": deployment.get("docker_compose", False),
            "kubernetes": deployment.get("kubernetes", False),
            "kubernetes_confidence": deployment.get("kubernetes_confidence", 0.0),
            "kubernetes_reason": deployment.get("kubernetes_reason", ""),
            "terraform": deployment.get("terraform", False),
            "helm": deployment.get("helm", False),
            "cloud_provider": deployment.get("cloud_provider"),
            "recommended_deployment_target": state.get("recommended_deployment_target", "docker"),
            "alternative_deployment_targets": deployment.get("alternative_deployment_targets", []),
            "deployment_reason": deployment.get("deployment_reason", ""),
        },
        "detected_at": datetime.utcnow().isoformat() + "Z",
    }


def _build_security_explanation(state: PipelineEngineerState) -> dict:
    security_needs = state.get("inferred_security_needs", {}) or {}
    security_controls = security_needs.get("security_controls", [])

    explained_controls = []
    for control in security_controls:
        explained_controls.append({
            "control": control.get("control", ""),
            "status": control.get("status", "recommended"),
            "reason": control.get("reason", ""),
            "tool": control.get("tool", ""),
            "tool_version": control.get("tool_version", "latest"),
        })

    # v9.3: surface the 15 security coverages marked applicable by
    # `coverage_inference` so the FE can render a "Security Coverages"
    # card. Each entry mirrors the schema set by
    # `coverage_inference_node` (id, applicable, reason, confidence).
    coverages = state.get("security_coverages") or []
    applicable_coverages = [
        {
            "id": c.get("id"),
            "applicable": bool(c.get("applicable")),
            "reason": c.get("reason", ""),
            "confidence": c.get("confidence", 0.0),
        }
        for c in coverages
        if c.get("applicable")
    ]

    return {
        "security_controls": explained_controls,
        "required_tools": security_needs.get("required_tools", []),
        "pipeline_stages": security_needs.get("pipeline_stages", []),
        "total_controls": len(explained_controls),
        "recommended_count": len([c for c in explained_controls if c["status"] == "recommended"]),
        "optional_count": len([c for c in explained_controls if c["status"] == "optional"]),
        "not_required_count": len([c for c in explained_controls if c["status"] == "not_required"]),
        "applicable_coverages": applicable_coverages,
    }


def _build_deployment_explanation(state: PipelineEngineerState) -> dict:
    deployment = state.get("detected_deployment", {}) or {}
    architecture = state.get("detected_architecture", {}) or {}
    technologies = state.get("detected_technologies", {}) or {}

    reasons = []

    if deployment.get("docker"):
        reasons.append(f"Docker detected (confidence: {deployment.get('docker_confidence', 0):.0%})")
    if deployment.get("kubernetes"):
        reasons.append(f"Kubernetes detected (confidence: {deployment.get('kubernetes_confidence', 0):.0%})")
    if deployment.get("terraform"):
        reasons.append("Terraform IaC detected")

    arch_type = architecture.get("architecture_type", "monolithic")
    if arch_type == "modular_monolith":
        # Per R2.1, arsitektur bukan variabel eksperimen. Branch ini TIDAK
        # akan pernah dieksekusi (arch_type selalu "monolithic"). Disimpan
        # untuk backward compatibility.
        reasons.append("Modular monolith (legacy, disabled per R2.1) - containerized deployment recommended")
    elif arch_type == "monolithic":
        reasons.append("Monolithic architecture - single Docker host deployment sufficient")

    return {
        "recommended_target": state.get("recommended_deployment_target", "docker"),
        "alternative_targets": deployment.get("alternative_deployment_targets", []),
        "reasons": reasons,
        "cloud_provider": deployment.get("cloud_provider"),
    }


def _build_unified_response(state: PipelineEngineerState) -> dict:
    return {
        "repository_analysis": _build_repository_analysis(state),
        "security_requirements": _build_security_explanation(state),
        "deployment_analysis": _build_deployment_explanation(state),
        "workflow": {
            "generated_workflow": state.get("generated_workflow"),
            "generated_stages": state.get("generated_stages", []),
            "generation_explanation": state.get("generation_explanation"),
            "validation_passed": state.get("validation_passed", False),
            "validation_errors": state.get("validation_errors", []),
            "validation_warnings": state.get("validation_warnings", []),
        },
        "deployment": {
            "github_branch": state.get("github_branch"),
            "github_pr_number": state.get("github_pr_number"),
            "github_pr_url": state.get("github_pr_url"),
            "workflow_run_id": state.get("workflow_run_id"),
            "workflow_status": state.get("workflow_status"),
            "workflow_conclusion": state.get("workflow_conclusion"),
        },
        "analysis": {
            "risk_score": state.get("risk_score"),
            "security_posture": state.get("security_posture"),
            "compliance_score": state.get("compliance_score"),
            "findings": state.get("findings", []),
            "recommendations": state.get("recommendations", []),
            "summary": state.get("summary"),
        },
        "metadata": {
            "repository_full_name": state.get("repository_full_name"),
            "request_type": state.get("request_type"),
            "auto_deploy": state.get("auto_deploy", False),
            "errors": state.get("errors", []),
            "error_stage": state.get("error_stage"),
        },
    }