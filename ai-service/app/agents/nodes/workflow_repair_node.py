import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import analyze_structured, analyze_text
from app.models.schemas import WorkflowFix, ExecutionFailureFix


def _classify_failure(logs: str, failed_jobs: list, failed_steps: list) -> dict:
    logs_lower = logs.lower()
    
    if "unable to resolve action" in logs_lower or "could not find" in logs_lower:
        return {"type": "action_not_found", "strategy": "update_action"}
    if "permission" in logs_lower and ("denied" in logs_lower or "not accessible" in logs_lower):
        return {"type": "permission_error", "strategy": "add_permission"}
    if "secret" in logs_lower and ("not found" in logs_lower or "missing" in logs_lower):
        return {"type": "env_var_missing", "strategy": "fix_env"}
    if "npm err" in logs_lower or "yarn" in logs_lower and "error" in logs_lower:
        return {"type": "dependency_error", "strategy": "simplify_job"}
    if "docker" in logs_lower and ("error" in logs_lower or "failed" in logs_lower):
        return {"type": "docker_build_error", "strategy": "fix_env"}
    if "timeout" in logs_lower or "timed out" in logs_lower:
        return {"type": "step_timeout", "strategy": "retry_step"}
    if "resource not accessible" in logs_lower:
        return {"type": "permission_denied", "strategy": "add_permission"}
    if "econnrefused" in logs_lower or "connection" in logs_lower:
        return {"type": "network_error", "strategy": "fix_env"}
    if "deploy" in logs_lower or "deployment" in logs_lower:
        return {"type": "deployment_error", "strategy": "fix_env"}
    
    return {"type": "other", "strategy": "simplify_job"}


def _repair_from_execution_failure(state: PipelineEngineerState) -> PipelineEngineerState:
    workflow = state.get("generated_workflow", "")
    failed_jobs = state.get("failed_jobs", [])
    failed_steps = state.get("failed_steps", [])
    failure_logs = state.get("failure_logs", {})
    workflow_conclusion = state.get("workflow_conclusion", "")
    workflow_status = state.get("workflow_status", "")
    workflow_run_id = state.get("workflow_run_id")

    if workflow_conclusion == "success":
        return state

    if not failed_jobs and not failed_steps and not failure_logs:
        return state

    logs_text = ""
    if isinstance(failure_logs, dict):
        logs_text = "\n".join(str(v) for v in failure_logs.values())
    elif isinstance(failure_logs, str):
        logs_text = failure_logs

    for job in failed_jobs:
        if isinstance(job, dict):
            job_name = job.get("name", job.get("workflow_name", "unknown"))
            logs_text += f"\n[JOB: {job_name}] " + str(job.get("logs", ""))

    classification = _classify_failure(logs_text, failed_jobs, failed_steps)

    technologies = state.get("detected_technologies", {}) or {}
    inferred_security = state.get("inferred_security_needs", {}) or {}
    security_controls = inferred_security.get("security_controls", [])

    prompt = f"""You are an expert DevSecOps Workflow Repair Agent.

Your task is to fix a GitHub Actions workflow that failed during execution.

CRITICAL RULES:
1. Preserve the original workflow structure whenever possible.
2. Fix only the failing part — do not change working jobs.
3. Do not invent frameworks, tools, package managers, or technologies not in the repository.
4. Do not generate placeholder values or fake commit SHAs.
5. If an exact SHA cannot be verified, use the official stable action tag.
6. Ensure the workflow remains valid YAML with exactly one YAML document.
7. Remove any explanations, markdown, comments, analysis, notes, or prose outside YAML.
8. Preserve security controls already present in the workflow.
9. Preserve existing jobs, stages, triggers, permissions, concurrency settings, and timeouts unless they contain the failure.

Repository Technologies:
{json.dumps(technologies, indent=2)}

Existing Security Controls in Workflow:
{json.dumps(security_controls, indent=2)}

Original Workflow YAML:
{workflow}

Execution Failure Summary:
- Conclusion: {workflow_conclusion}
- Status: {workflow_status}
- Run ID: {workflow_run_id}
- Failed Jobs: {json.dumps(failed_jobs, indent=2)}
- Failed Steps: {json.dumps(failed_steps, indent=2)}

Failure Logs (truncated):
{logs_text[:8000]}

Detected Failure Type: {classification['type']}
Recommended Strategy: {classification['strategy']}

Return a JSON object matching this schema:
{{
  "failure_type": "string (one of: dependency_error, permission_error, action_not_found, env_var_missing, step_timeout, docker_build_error, deployment_error, permission_denied, network_error, other)",
  "job_name": "string (name of the failed job)",
  "step_name": "string (name of the failed step, or 'overall' if job-level failure)",
  "root_cause": "string (1-2 sentences explaining the root cause)",
  "fix_strategy": "string (one of: update_action, add_permission, fix_env, retry_step, simplify_job, add_conditions, other)",
  "yaml_changes": "string (the corrected YAML section — MUST be valid YAML, no markdown, no explanation)",
  "reasoning": "string (why this fix resolves the failure)",
  "risk": "string (low, medium, or high)"
}}

IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, no explanation.
"""

    try:
        fix = analyze_structured(prompt, ExecutionFailureFix)
        
        state["remediation_suggestions"] = state.get("remediation_suggestions", []) + [{
            "failure_type": fix.failure_type,
            "job_name": fix.job_name,
            "step_name": fix.step_name,
            "root_cause": fix.root_cause,
            "strategy": fix.fix_strategy,
            "yaml_changes": fix.yaml_changes,
            "reasoning": fix.reasoning,
            "risk": fix.risk,
            "source": "execution_failure",
        }]

        yaml_changes = (fix.yaml_changes or "").strip()
        if yaml_changes and yaml_changes in workflow:
            state["generated_workflow"] = workflow.replace(yaml_changes, fix.yaml_changes)
            state["summary"] = f"Workflow repaired from execution failure: {fix.root_cause[:200]}"
        elif yaml_changes:
            state["generated_workflow"] = workflow
            state.setdefault("validation_warnings", []).append(
                f"Execution failure fix could not be auto-applied: YAML section not found in workflow. Fix: {fix.root_cause}"
            )
            state["summary"] = f"Analysis complete: execution failure identified as {fix.failure_type}. Manual review recommended."

    except Exception as e:
        state["errors"].append(f"Execution failure repair failed: {e}")
        state["error_stage"] = "workflow_repair"

    return state


WORKFLOW_REPAIR_PROMPT = """You are an expert DevSecOps Workflow Repair Agent.

Your task is to repair an existing GitHub Actions workflow based on validation findings.

CRITICAL RULES

1. Preserve the original workflow structure whenever possible.
2. Fix only the issues identified by the validator.
3. Do not remove existing jobs unless they are invalid.
4. Do not invent frameworks, tools, package managers, or technologies not detected in the repository.
5. Do not generate placeholder values.
6. Do not generate fake commit SHAs.
7. If an exact SHA cannot be verified, use the official stable action tag instead.
8. Ensure the workflow remains executable on GitHub Actions.
9. Ensure the workflow remains valid YAML.
10. Ensure the workflow contains exactly one YAML document.
11. Remove any explanations, markdown, comments, analysis, notes, or prose outside YAML.
12. Preserve security controls already present in the workflow.
13. Preserve existing jobs, stages, triggers, permissions, concurrency settings, and timeouts unless they contain validation issues.
14. If actions/checkout is used and Git push is not required, set: with: persist-credentials: false
15. If validator requires SHA pinning:
    * Replace action tags with verified SHAs only if provided in validator findings.
    * Never invent SHA values.
    * If no verified SHA is provided, keep the official version tag and add a warning in the repair report.

Repository Analysis:
{technologies}

Original Workflow:
{workflow}

Validation Findings:
{findings}

Return ONLY the corrected workflow YAML as a WorkflowFix model with:
- before: the problematic section
- after: the corrected section
- reasoning: what was fixed
- risk: low/medium/high
"""


def workflow_repair_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors") and not state.get("validation_errors") and not state.get("failed_jobs"):
        return state

    workflow = state.get("generated_workflow", "")
    if not workflow:
        return state

    has_execution_failure = (
        state.get("workflow_conclusion") in ("failure", "timed_out", "cancelled") or
        state.get("workflow_status") == "completed" and state.get("workflow_conclusion") != "success"
    )
    has_failed_jobs = bool(state.get("failed_jobs"))
    has_failed_steps = bool(state.get("failed_steps"))

    if has_execution_failure or has_failed_jobs or has_failed_steps:
        state = _repair_from_execution_failure(state)
        return state

    findings = state.get("validation_findings", [])
    errors = state.get("validation_errors", [])
    technologies = state.get("detected_technologies", {}) or {}

    if findings and errors:
        try:
            prompt = WORKFLOW_REPAIR_PROMPT.format(
                technologies=json.dumps(technologies, indent=2),
                workflow=workflow,
                findings=json.dumps(findings, indent=2),
            )

            fix = analyze_structured(prompt, WorkflowFix)
            state["remediation_suggestions"] = state.get("remediation_suggestions", []) + [{
                "before": fix.before,
                "after": fix.after,
                "reasoning": fix.reasoning,
                "risk": fix.risk,
                "source": "validation_error",
            }]

            before = (fix.before or "").strip()
            after = (fix.after or "").strip()
            if before and after and before != after and before in workflow:
                state["generated_workflow"] = workflow.replace(before, after)
                state["summary"] = f"Workflow repaired: {fix.reasoning[:200]}"

        except Exception as e:
            state["errors"].append(f"Workflow repair failed: {e}")
            state["error_stage"] = "workflow_repair"

    return state