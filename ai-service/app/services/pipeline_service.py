import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.pipeline_state import PipelineEngineerState
from app.agents.pipeline_graph import pipeline_graph
from app.services.github_service import get_workflow_run, get_workflow_logs, create_branch, commit_file, create_pull_request
from app.database import SessionLocal

from sqlalchemy import text

# Global wall-clock budget for a single end-to-end pipeline run.
# Pipeline generator invokes 8-11 LLM calls sequentially (one per
# detection/inference/generation node). With a slow upstream gateway
# (e.g. opencode.ai/zen/v1) each call can take 30-60s, and one
# hung call would otherwise stall the whole request indefinitely.
# After this many seconds, _invoke_graph_phase stops dispatching
# new nodes and returns the partial result with an error so the
# client gets a deterministic 502-with-error response instead of
# a silent nginx timeout. Tunable via env so we can adjust per
# environment without redeploying.
PIPELINE_DEADLINE_SECONDS = int(os.getenv("PIPELINE_DEADLINE_SECONDS", "600"))


def _get_default_state(
    repository_full_name: str,
    github_token: str | None = None,
) -> PipelineEngineerState:
    return {
        "request_type": "repository_pipeline",
        "repository_full_name": repository_full_name,
        "github_token": github_token or "",
        "repository_url": None,
        "repository_default_branch": None,
        "repository_name": None,
        "repository_description": None,
        "repository_structure": None,
        "repository_files": None,
        "source_files": [],
        "existing_workflows": None,
        "detected_technologies": None,
        "detected_architecture": None,
        "detected_architecture_type": None,
        "detected_architecture_confidence": None,
        "detected_architecture_reason": None,
        "detected_deployment": None,
        "recommended_deployment_target": None,
        "detected_domain": None,
        "domain_confidence": None,
        "domain_evidence": [],
        "domain_threats": [],
        "attack_surfaces": [],
        "inferred_security_needs": None,
        "generated_workflow": None,
        "generated_workflow_generic": None,
        "generated_workflow_custom": None,
        "generated_workflow_files": [],
        "generated_stages": [],
        "generated_stages_general": [],
        "generated_stages_custom": [],
        "stage_explanations": [],
        "generation_explanation": None,
        "vignette_context": None,
        "validation_errors": [],
        "validation_warnings": [],
        "validation_passed": False,
        "warnings": [],
        "removed_legacy_workflows": [],

        "workflow_config_issues": [],
        "maintenance_warnings": [],
        "external_service_issues": [],
        "workflow_annotations": [],
        "remediation_recommendations": [],
        "remediation_yaml_patches": [],
        "skipped_jobs": [],
        "execution_results": {},
        "github_branch": None,
        "github_commit_sha": None,
        "github_pr_number": None,
        "github_pr_url": None,
        "workflow_file_custom": None,
        "workflow_files": [],
        "workflow_run_id": None,
        "workflow_status": None,
        "workflow_conclusion": None,
        "workflow_logs": [],
        "workflow_jobs": [],
        "workflow_duration_seconds": None,
        "raw_logs": None,
        "failed_jobs": [],
        "failed_steps": [],
        "failure_logs": {},
        "failure_analysis": None,
        "root_cause": None,
        "remediation_suggestions": [],
        "remediation_workflow": None,
        "remediation_branch": None,
        "remediation_pr_number": None,
        "remediation_pr_url": None,
        "scan_results": None,
        "findings": [],
        "domain_context": None,
        "risk_score": None,
        "risk_score_metadata": None,
        "security_standards_coverage_score": None,
        "security_standards_coverage_score_metadata": None,
        "security_standards_coverage_mappings": [],
        "compliance_score": None,
        "compliance_score_metadata": None,
        "compliance_mappings": [],
        "severity_breakdown": None,
        "security_coverage_score": None,
        "security_coverage_metadata": None,
        "recommendations": [],
        "summary": None,
        "errors": [],
        "error_stage": None,
        "auto_deploy": False,
        "pipeline_version": 1,
        "workflow_file": None,
        "pdf_report_path": None,
        "node_io": [],
        "scanner_normalizer": None,
        "_current_phase": None,
    }


def _extract_security_controls_for_storage(result: dict) -> list[dict]:
    """Build the structured `security_controls_applied` list for DB storage.

    Prefers the structured `unified_response.security_requirements.security_controls`
    (with `control`, `status`, `reason`, `tool`, `tool_version`). Falls back to
    the bare list of stage names for older payloads.
    """
    unified = result.get("unified_response") or {}
    sec = (unified.get("security_requirements") or {}).get("security_controls") or []
    if sec:
        return [
            {
                "control": c.get("control", ""),
                "status": c.get("status", "recommended"),
                "reason": c.get("reason", ""),
                "tool": c.get("tool", ""),
                "tool_version": c.get("tool_version", "latest"),
            }
            for c in sec
        ]
    return [{"control": s, "status": "recommended", "reason": "", "tool": "", "tool_version": "latest"}
            for s in (result.get("security_needs") or [])]


def _build_pipeline_response(result: dict, repository_full_name: str) -> dict:
    tech = result.get("detected_technologies", {}) or {}
    arch_raw = result.get("detected_architecture", {})
    arch_type = result.get("detected_architecture_type")
    if not arch_type and isinstance(arch_raw, dict):
        arch_type = arch_raw.get("architecture_type", "monolithic")
    elif not arch_type:
        arch_type = arch_raw if isinstance(arch_raw, str) else "monolithic"
    security = result.get("inferred_security_needs", {}) or {}

    dashboard = result.get("dashboard_findings") or _build_dashboard_from_state(result)

    # v9.5 (Bab 5.13.5 — PDF "all fields empty" bug fix): the FE
    # `RepoPipelineResult` interface expects fields prefixed with
    # `detected_` (e.g. `detected_technologies`, `detected_architecture`,
    # `detected_domain`, `security_coverages`, `pipeline_augmentations`,
    # `ai_generated_rules`, `job_designs`, etc.) but `_build_pipeline_response`
    # historically used a different naming convention
    # (`technologies`, `architecture` + `architecture_detail`, etc.).
    # When the FE reads the response, every `detected_*` lookup returns
    # `undefined`, the fallback chain hits the Go-side summary (which
    # also lacks these fields), and the PDF renders with all "N/A" —
    # exactly the symptom the user reported.
    #
    # Fix: include BOTH the legacy key (kept for any callers that
    # already work) AND the canonical `detected_*` alias so the FE
    # interface resolves cleanly. The state field is the source of
    # truth; the alias is a thin pass-through.
    domain_raw = result.get("domain") if isinstance(result.get("domain"), dict) else None
    detected_domain = (
        result.get("detected_domain")
        or (domain_raw.get("domain") if domain_raw else None)
        or "general"
    )
    detected_domain_sub_type = (
        result.get("domain_sub_type")
        or (domain_raw.get("sub_type") if domain_raw else None)
        or "none"
    )
    detected_domain_confidence = float(
        result.get("domain_confidence")
        or (domain_raw.get("confidence") if domain_raw else 0.0)
        or 0.0
    )
    detected_domain_evidence = (
        result.get("domain_evidence")
        or (domain_raw.get("evidence") if domain_raw else [])
        or []
    )
    detected_domain_threats = (
        result.get("domain_threats")
        or (domain_raw.get("threats") if domain_raw else [])
        or []
    )
    # `detected_architecture` on the FE is a dict with shape
    # `{ architecture_type, service_count, confidence, reason }`. Map
    # the BE's split representation (string `architecture` + dict
    # `architecture_detail`) into that single object.
    arch_dict: dict = {}
    if isinstance(arch_raw, dict):
        arch_dict = dict(arch_raw)
    else:
        arch_dict = {"architecture_type": arch_type}
    arch_dict.setdefault("architecture_type", arch_type)
    arch_dict.setdefault(
        "confidence", result.get("detected_architecture_confidence", 0.0)
    )
    arch_dict.setdefault(
        "reason", result.get("detected_architecture_reason", "")
    )

    response = {
        "status": "analyzed" if not result.get("errors") else "failed",
        "repository": repository_full_name,
        # === Canonical (legacy BE) keys — keep for backward compat ===
        "technologies": tech,
        "architecture": arch_type,
        "architecture_detail": arch_raw if isinstance(arch_raw, dict) else {},
        "security_needs": security.get("required_stages", []),
        # === v9.5 aliases for FE RepoPipelineResult contract ===
        "detected_technologies": tech,
        "detected_architecture": arch_dict,
        "detected_architecture_type": arch_type,
        "detected_architecture_confidence": arch_dict.get("confidence", 0.0),
        "detected_architecture_reason": arch_dict.get("reason", ""),
        "detected_deployment": result.get("detected_deployment", {}) or {},
        "recommended_deployment_target": result.get("recommended_deployment_target"),
        "detected_domain": detected_domain,
        "domain_sub_type": detected_domain_sub_type,
        "domain_confidence": detected_domain_confidence,
        "domain_evidence": detected_domain_evidence,
        "domain_threats": detected_domain_threats,
        "features": result.get("features", []),
        "attack_surfaces": result.get("attack_surfaces", []),
        "security_coverages": result.get("security_coverages", []) or [],
        "pipeline_augmentations": result.get("pipeline_augmentations", []) or [],
        "ai_generated_rules": result.get("ai_generated_rules", []) or [],
        "llm_generated_rules": result.get("llm_generated_rules", []) or [],
        "job_designs": result.get("job_designs", []) or [],
        # === Pipeline output (already canonical names) ===
        "generated_workflow": result.get("generated_workflow", ""),
        "generated_workflow_generic": result.get("generated_workflow_generic", ""),
        "generated_workflow_custom": result.get("generated_workflow_custom", ""),
        "generated_workflow_files": result.get("generated_workflow_files", []),
        "generated_stages": result.get("generated_stages", []),
        "generated_stages_general": result.get("generated_stages_general", []),
        "generated_stages_custom": result.get("generated_stages_custom", []),
        "invalid_workflow_stages": result.get("invalid_workflow_stages", []),
        "stage_explanations": result.get("stage_explanations", []),
        "explanation": result.get("generation_explanation", ""),
        "vignette_context": result.get("vignette_context"),
        "validation_passed": result.get("validation_passed", False),
        "validation_errors": result.get("validation_errors", []),
        "validation_warnings": result.get("validation_warnings", []),
        "warnings": result.get("warnings", []),
        "removed_legacy_workflows": result.get("removed_legacy_workflows", []),
        "github_branch": result.get("github_branch"),
        "github_pr_number": result.get("github_pr_number"),
        "github_pr_url": result.get("github_pr_url"),
        "workflow_run_id": result.get("workflow_run_id"),
        "workflow_status": result.get("workflow_status"),
        "workflow_conclusion": result.get("workflow_conclusion"),
        "summary": result.get("summary", ""),
        "findings": result.get("findings", []),
        "code_scanning_alerts": result.get("code_scanning_alerts", []) or [],
        "dashboard_findings": dashboard,
        "risk_score": result.get("risk_score"),
        "risk_score_metadata": result.get("risk_score_metadata"),
        "security_standards_coverage_score": result.get("security_standards_coverage_score"),
        "security_standards_coverage_score_metadata": result.get("security_standards_coverage_score_metadata"),
        "security_standards_coverage_mappings": result.get("security_standards_coverage_mappings", []),
        "compliance_score": result.get("compliance_score"),
        "compliance_score_metadata": result.get("compliance_score_metadata"),
        "compliance_mappings": result.get("compliance_mappings", []),
        "severity_breakdown": result.get("severity_breakdown"),
        "security_coverage_score": result.get("security_coverage_score"),
        "security_coverage_metadata": result.get("security_coverage_metadata"),
        "recommendations": result.get("recommendations", []),
        "errors": result.get("errors", []),
        # Four-category dashboard buckets
        "workflow_config_issues": result.get("workflow_config_issues", []),
        "maintenance_warnings": result.get("maintenance_warnings", []),
        "external_service_issues": result.get("external_service_issues", []),
        "remediation_recommendations": result.get("remediation_recommendations", []),
        "workflow_annotations": result.get("workflow_annotations", []),
        # Requirement 3: three-category execution results.
        "execution_results": result.get("execution_results", {}),
        "skipped_jobs": result.get("skipped_jobs", []),
        "dashboard_messages": (result.get("execution_results") or {}).get("dashboard_messages", []),
    }
    return response


def _build_dashboard_from_state(state: dict) -> dict:
    """Build the four-category dashboard from any state object."""
    from app.agents.finding_categories import build_dashboard
    # Raw workflow_annotations are intentionally excluded — they are already
    # categorized into the dedicated buckets by earlier nodes.
    return build_dashboard(
        state.get("findings") or [],
        state.get("validation_findings") or [],
        state.get("workflow_config_issues") or [],
        state.get("maintenance_warnings") or [],
        state.get("external_service_issues") or [],
        state.get("log_analysis") or [],
    )


def _invoke_graph_phase(
    state: PipelineEngineerState,
    node_names: list[str],
    deadline_monotonic: float | None = None,
) -> PipelineEngineerState:
    # struktur-v9.2: 18-node graph. We import only the nodes that
    # are still in the active graph. Older nodes
    # (vulnerability_scan, security_requirement_inference,
    # risk_assessment, compliance_mapper, error_handler) were
    # removed in the v9 refactor and live in deprecated stubs in
    # `app/agents/nodes/_deprecated/` if needed for legacy
    # callers, but the active pipeline does not invoke them.
    from app.agents.nodes.repository_connection_node import repository_connection_node
    from app.agents.nodes.repository_scan_node import repository_scan_node
    from app.agents.nodes.technology_detection_node import technology_detection_node
    from app.agents.nodes.architecture_detection_node import architecture_detection_node
    from app.agents.nodes.deployment_detection_node import deployment_detection_node
    from app.agents.nodes.domain_detection_node import domain_detection_node
    from app.agents.nodes.coverage_inference_node import coverage_inference_node
    from app.agents.nodes.pattern_inference_node import pattern_inference_node
    from app.agents.nodes.pipeline_augmentation_node import pipeline_augmentation_node
    from app.agents.nodes.job_reasoning_node import job_reasoning_node
    from app.agents.nodes.workflow_generator import workflow_generator_node
    from app.agents.nodes.workflow_validator import workflow_validator_node
    from app.agents.nodes.workflow_repair_node import workflow_repair_node
    from app.agents.nodes.github_branch_creation_node import github_branch_creation_node
    from app.agents.nodes.pull_request_creation_node import pull_request_creation_node
    from app.agents.nodes.workflow_execution import workflow_execution_node
    from app.agents.nodes.security_analyzer import security_analyzer_node
    from app.agents.nodes.recommendation_gen import recommendation_gen_node
    from app.agents.nodes.response_formatter import response_formatter_node

    node_map = {
        # Tahap 1: Repository Context Analysis (6)
        "repository_connection": repository_connection_node,
        "repository_scan": repository_scan_node,
        "technology_detection": technology_detection_node,
        "architecture_detection": architecture_detection_node,
        "deployment_detection": deployment_detection_node,
        "domain_detection": domain_detection_node,
        # Tahap 2: Security Coverage Inference (4) — K2.3 + K2.4
        "coverage_inference": coverage_inference_node,
        "pattern_inference": pattern_inference_node,
        "pipeline_augmentation": pipeline_augmentation_node,
        "job_reasoning": job_reasoning_node,
        # Tahap 3: Pipeline Generation & Deployment (5)
        "workflow_generation": workflow_generator_node,
        "workflow_validation": workflow_validator_node,
        "workflow_repair": workflow_repair_node,
        "github_branch_creation": github_branch_creation_node,
        "pull_request_creation": pull_request_creation_node,
        "workflow_execution": workflow_execution_node,
        # Tahap 4: Security Evaluation (3)
        "security_analysis": security_analyzer_node,
        "recommendation_generation": recommendation_gen_node,
        "response_formatter": response_formatter_node,
    }

    # Snapshot the full state BEFORE the phase starts so we can
    # produce an accurate per-node diff (only the keys the node
    # actually wrote). The previous implementation only snapshotted
    # 9 hard-coded keys, which caused the diff to record every
    # other state key as "added" on the first node and made the
    # output_summary useless for debugging.
    #
    # We snapshot the value's id() + a fingerprint so the diff
    # doesn't have to deep-copy 100KB of code scanning alerts per
    # iteration. The fingerprint is `(type, len-or-repr-short)`
    # for collections, `repr()[:60]` for scalars.
    def _fingerprint(v: Any) -> tuple:
        if isinstance(v, list):
            return ("list", len(v))
        if isinstance(v, dict):
            return ("dict", len(v))
        if isinstance(v, str):
            return ("str", len(v))
        if isinstance(v, (int, float, bool)) or v is None:
            return (type(v).__name__, v)
        return (type(v).__name__, repr(v)[:60])

    def _state_diff(before: dict, after_state: dict) -> dict:
        """Return only the keys whose fingerprint changed between
        `before` and the live `after_state`. Keys present in
        `after_state` but not in `before` are also included."""
        changed: dict[str, Any] = {}
        for k, v in after_state.items():
            if k.startswith("_"):
                continue
            before_fp = before.get(k, _MISSING)
            if before_fp is _MISSING:
                # New key written by some node
                changed[k] = _summarise_value(v)
                continue
            if before_fp != _fingerprint(v):
                changed[k] = _summarise_value(v)
        return changed

    # _MISSING sentinel distinguishes "not snapshotted" from
    # "snapshotted as None".
    _MISSING = object()

    node_io_records: list[dict] = list(state.get("node_io") or [])
    # Full pre-phase snapshot. Skip private keys; the diff treats
    # them as unchanged anyway.
    before_snapshot: dict[str, tuple] = {
        k: _fingerprint(v)
        for k, v in state.items()
        if not k.startswith("_")
    }

    for name in node_names:
        if state.get("errors"):
            # In v9.2, error handling is done by the compiled
            # graph in pipeline_graph.py. When the manual
            # dispatch path is used (e.g. legacy callers), the
            # flow is aborted and the error is returned to the
            # caller. There is no dedicated error_handler node
            # in v9.2.
            break
        # Wall-clock deadline guard. A single hung LLM call (e.g.
        # opencode.ai gateway never responding for a long prompt)
        # would otherwise stall the entire request until the
        # upstream proxy (nginx 900s) closes the socket. By
        # breaking out of the dispatch loop here, we let the
        # caller see a partial result with a clear error message
        # and the FE can retry instead of hanging forever.
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            elapsed = PIPELINE_DEADLINE_SECONDS
            timeout_msg = (
                f"Pipeline exceeded wall-clock deadline of "
                f"{elapsed}s; halted before node '{name}'"
            )
            print(f"[pipeline] TIMEOUT {timeout_msg} (completed so far: "
                  f"{[r['node'] for r in node_io_records if r.get('status') == 'ok']})")
            state.setdefault("errors", []).append(timeout_msg)
            state["error_stage"] = name
            state["node_io"] = node_io_records
            break
        node_fn = node_map.get(name)
        if not node_fn:
            continue
        node_start = time.monotonic()
        node_record: dict[str, Any] = {
            "node": name,
            "phase": state.get("_current_phase", "tahap_4"),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "input_keys": sorted([k for k in state.keys() if not k.startswith("_")])[:20],
        }
        try:
            state = node_fn(state)
            node_record["status"] = "ok"
        except Exception as e:
            state.setdefault("errors", []).append(f"Node '{name}' failed: {e}")
            state["error_stage"] = name
            node_record["status"] = "error"
            node_record["error"] = str(e)
        finally:
            # Always record duration, even on success. The previous
            # implementation only recorded it on the success path,
            # which made `response_formatter` show as 0.00s when
            # it ran in <1ms (the int() floor of 0.0005s).
            elapsed_ms = (time.monotonic() - node_start) * 1000
            node_record["duration_ms"] = max(1, int(elapsed_ms))
        node_record["output_summary"] = _state_diff(before_snapshot, state)
        node_io_records.append(node_record)
        # Per-node progress log (visible in `docker logs ai-service`).
        # Helps the user see WHICH node is taking long when the
        # pipeline appears to hang — the previous implementation
        # only printed a single line at the end, which is useless
        # for live debugging.
        elapsed_ms = (time.monotonic() - node_start) * 1000
        print(
            f"[pipeline] {state.get('_current_phase', '?')}.{name} "
            f"-> status={node_record['status']} "
            f"duration_ms={int(elapsed_ms)} "
            f"input_keys={len(node_record['input_keys'])} "
            f"output_keys={len(node_record['output_summary'])}"
        )
        # Refresh the snapshot with the post-node fingerprints
        # so the next node's diff is against the latest state.
        before_snapshot = {
            k: _fingerprint(v)
            for k, v in state.items()
            if not k.startswith("_")
        }
        if node_record["status"] == "error":
            state["node_io"] = node_io_records
            break

    state["node_io"] = node_io_records
    return state


def _summarise_value(v: Any) -> Any:
    """Compact repr of a state value for the node I/O log.

    Lists/dicts are summarised to ``type(len)`` so the per-node
    record stays small even when the state carries thousands of
    findings. Scalar values pass through.
    """
    if isinstance(v, list):
        if len(v) == 0:
            return "[]"
        sample = v[0] if isinstance(v[0], (dict, str, int, float)) else None
        return f"list({len(v)}) sample={sample!r:.120}" if sample is not None else f"list({len(v)})"
    if isinstance(v, dict):
        return f"dict(keys={list(v.keys())[:6]})"
    if isinstance(v, str) and len(v) > 120:
        return v[:117] + "..."
    return v


def _persist_pipeline_result(
    repository_full_name: str,
    result: dict,
    project_id: str | None = None,
    query: str | None = None,
) -> str | None:
    """Persist pipeline to DB. Returns error string or None on success."""
    try:
        db = SessionLocal()
        pipeline_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        repo_uuid = None
        resolved_project_id = project_id
        user_id = None
        try:
            row = db.execute(
                text("SELECT id, project_id FROM repositories WHERE full_name = :name LIMIT 1"),
                {"name": repository_full_name},
            ).fetchone()
            if row:
                repo_uuid = str(row[0])
                resolved_project_id = resolved_project_id or str(row[1])
                pu = db.execute(
                    text("SELECT user_id FROM projects WHERE id = :pid LIMIT 1"),
                    {"pid": resolved_project_id},
                ).fetchone()
                if pu:
                    user_id = str(pu[0])
        except Exception as e:
            err = f"[persist] lookup error: {e}"
            print(err)
            import traceback
            traceback.print_exc()
            db.close()
            return err

        if not repo_uuid or not resolved_project_id or not user_id:
            err = f"[persist] SKIPPED: repo_uuid={repo_uuid}, project={resolved_project_id}, user={user_id}"
            print(err)
            print(f"[persist]   repository_full_name={repository_full_name}")
            print(f"[persist]   project_id param={project_id}")
            db.close()
            return err

        # Get next version number
        version_row = db.execute(
            text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM pipelines WHERE repository_id = :repo"),
            {"repo": repo_uuid},
        ).fetchone()
        version_number = version_row[0] if version_row else 1

        print(f"[persist] INSERTING pipelines v{version_number}: repo={repository_full_name}, project={resolved_project_id}, user={user_id}")

        query_text = query or result.get("summary") or "Pipeline generation"

        deployment_info = {}
        if result.get("github_pr_url") or result.get("workflow_file"):
            deployment_info = {
                "branch": result.get("github_branch", ""),
                "commit_sha": result.get("github_commit_sha", ""),
                "pr_number": result.get("github_pr_number", 0),
                "pr_url": result.get("github_pr_url", ""),
                "workflow_file": result.get("workflow_file", ""),
            }

        extra = result.get("extra_params", {})
        technologies = result.get("technologies", {}) or {}
        tech_language = extra.get("language") or technologies.get("primary_language") or ""
        tech_framework = ""
        frameworks_list = technologies.get("frameworks", [])
        if isinstance(frameworks_list, list) and frameworks_list:
            tech_framework = frameworks_list[0]
        elif isinstance(frameworks_list, str):
            tech_framework = frameworks_list
        tech_framework = extra.get("framework") or tech_framework

        generation_params = {
            "project_id": resolved_project_id,
            "user_id": user_id,
            "language": tech_language,
            "framework": tech_framework,
            "architecture_type": extra.get("project_type") or technologies.get("architecture"),
            "deployment_target": extra.get("deploy_target"),
            "security_requirements": extra.get("security_requirements", []),
        }

        db.execute(
            text("""
                INSERT INTO pipelines (id, repository_id, version_number, prompt, user_requirements, generated_yaml, stages, ai_explanation, generation_params, validation_results, deployment_results, security_controls_applied, compliance_metadata, status, created_at)
                VALUES (:id, :repo, :version, :query, :reqs, :yaml, :stages, :explanation, :params, :validation, :deployment, :controls, :compliance, :status, :now)
            """),
            {
                "id": pipeline_id,
                "repo": repo_uuid,
                "version": version_number,
                "query": query_text,
                "reqs": "",
                "yaml": result.get("generated_workflow", "") or "",
                "stages": json.dumps(result.get("generated_stages", [])),
                "explanation": result.get("explanation") or result.get("generation_explanation"),
                "params": json.dumps(generation_params),
                "validation": json.dumps({
                    "valid": result.get("validation_passed", False),
                    "errors": result.get("validation_errors", []),
                    "warnings": result.get("validation_warnings", []),
                }),
                "deployment": json.dumps(deployment_info) if deployment_info else None,
                "controls": json.dumps(_extract_security_controls_for_storage(result)),
                "compliance": json.dumps({}),
                "status": "validated" if result.get("validation_passed") else ("failed" if result.get("errors") else "generated"),
                "now": now,
            },
        )

        # Always create a pipeline_run entry
        exec_id = str(uuid.uuid4())
        run_number_row = db.execute(
            text("SELECT COALESCE(MAX(run_number), 0) + 1 FROM pipeline_runs WHERE pipeline_id = :pid"),
            {"pid": pipeline_id},
        ).fetchone()
        run_number = run_number_row[0] if run_number_row else 1

        actual_run_id = result.get("workflow_run_id")
        run_status = "completed"
        run_conclusion = "success"
        if result.get("errors"):
            run_status = "completed"
            run_conclusion = "failure"

        db.execute(
            text("""
                INSERT INTO pipeline_runs (id, pipeline_id, run_number, git_hub_run_id, status, conclusion, started_at, completed_at, duration_seconds, created_at)
                VALUES (:id, :pid, :run_num, :run_id, :status, :conclusion, :started, :completed, :duration, :now)
            """),
            {
                "id": exec_id,
                "pid": pipeline_id,
                "run_num": run_number,
                "run_id": actual_run_id,
                "status": run_status,
                "conclusion": run_conclusion,
                "started": result.get("workflow_started_at") or now,
                "completed": result.get("workflow_completed_at") or now,
                "duration": result.get("workflow_duration_seconds"),
                "now": now,
            },
        )

        # Create analysis entry
        findings = result.get("findings", [])
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            if isinstance(f, dict):
                sev = (f.get("severity") or "medium").lower()
                if sev in severity_counts:
                    severity_counts[sev] += 1

        db.execute(
            text("""
                INSERT INTO pipeline_analyses (id, pipeline_run_id, risk_score, compliance_score, workflow_quality_score, security_coverage_score, findings_summary, severity_breakdown, recommendations, ai_explanation, raw_scan_data, created_at)
                VALUES (:id, :run_id, :risk, :compliance, NULL, :coverage, :findings, :severity, :recs, :explanation, :raw, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "run_id": exec_id,
                "risk": result.get("risk_score"),
                "compliance": result.get("compliance_score"),
                "coverage": result.get("security_coverage_score"),
                "findings": json.dumps(findings),
                "severity": json.dumps(severity_counts),
                "recs": json.dumps(result.get("recommendations", [])),
                "explanation": result.get("summary", ""),
                "raw": json.dumps({
                    "scan_results": result.get("scan_results", {}),
                    "dashboard_findings": result.get("dashboard_findings") or _build_dashboard_from_state({
                        **result,
                        "findings": findings,
                        "validation_findings": result.get("validation_findings", []),
                        "log_analysis": result.get("log_analysis", []),
                    }),
                    "workflow_config_issues": result.get("workflow_config_issues", []),
                    "maintenance_warnings": result.get("maintenance_warnings", []),
                    "external_service_issues": result.get("external_service_issues", []),
                    "remediation_recommendations": result.get("remediation_recommendations", []),
                }),
                "now": now,
            },
        )

        db.commit()
        db.close()
        return None
    except Exception as e:
        err = f"[persist] error: {e}"
        print(err)
        import traceback
        traceback.print_exc()
        return err


def _persist_analysis_result(
    repository_full_name: str,
    result: dict,
    project_id: str | None = None,
    run_id: int | None = None,
):
    """Persist full analysis results including risk, recommendations, and compliance mappings."""
    try:
        db = SessionLocal()
        now = datetime.now(timezone.utc).isoformat()

        repo_uuid = None
        resolved_project_id = project_id
        user_id = None
        try:
            row = db.execute(
                text("SELECT id, project_id FROM repositories WHERE full_name = :name LIMIT 1"),
                {"name": repository_full_name},
            ).fetchone()
            if row:
                repo_uuid = str(row[0])
                resolved_project_id = resolved_project_id or str(row[1])
                pu = db.execute(
                    text("SELECT user_id FROM projects WHERE id = :pid LIMIT 1"),
                    {"pid": resolved_project_id},
                ).fetchone()
                if pu:
                    user_id = str(pu[0])
        except Exception as e:
            print(f"[persist-analysis] lookup error: {e}")
            db.close()
            return

        if not repo_uuid or not resolved_project_id or not user_id:
            print(f"[persist-analysis] SKIPPED: repo={repository_full_name}, project={resolved_project_id}")
            db.close()
            return

        query_text = result.get("summary") or "Security analysis"

        # Ensure a pipeline_generations row exists for this repo. The
        # workflow_executions.generation_id FK points at
        # pipeline_generations(id), NOT pipelines(id). The pipeline
        # generator writes to `pipelines`, so we upsert a matching
        # generation row here if one is missing.
        gen_row = db.execute(
            text("""
                SELECT id FROM pipeline_generations
                WHERE repository_id = :repo
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"repo": repo_uuid},
        ).fetchone()
        if gen_row:
            generation_id = str(gen_row[0])
        else:
            generation_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO pipeline_generations
                        (id, project_id, repository_id, user_id, query, status, created_at, updated_at)
                    VALUES (:id, :pid, :repo, :uid, :query, :status, :now, :now)
                """),
                {
                    "id": generation_id,
                    "pid": resolved_project_id,
                    "repo": repo_uuid,
                    "uid": user_id,
                    "query": query_text,
                    "status": "analyzed",
                    "now": now,
                },
            )

        # Find matching pipeline for this repo
        pipeline_row = db.execute(
            text("SELECT id FROM pipelines WHERE repository_id = :repo ORDER BY version_number DESC LIMIT 1"),
            {"repo": repo_uuid},
        ).fetchone()
        pipeline_id = str(pipeline_row[0]) if pipeline_row else str(uuid.uuid4())

        run_number_row = db.execute(
            text("SELECT COALESCE(MAX(run_number), 0) + 1 FROM pipeline_runs WHERE pipeline_id = :pid"),
            {"pid": pipeline_id},
        ).fetchone()
        run_number = run_number_row[0] if run_number_row else 1
        exec_id = str(uuid.uuid4())

        db.execute(
            text("""
                INSERT INTO pipeline_runs (id, pipeline_id, run_number, git_hub_run_id, status, conclusion, started_at, completed_at, duration_seconds, created_at)
                VALUES (:id, :pid, :run_num, :run_id, :status, :conclusion, :started, :completed, :duration, :now)
            """),
            {
                "id": exec_id,
                "pid": pipeline_id,
                "run_num": run_number,
                "run_id": result.get("workflow_run_id"),
                "status": result.get("workflow_status", "completed"),
                "conclusion": result.get("workflow_conclusion", ""),
                "started": result.get("workflow_started_at"),
                "completed": result.get("workflow_completed_at"),
                "duration": result.get("workflow_duration_seconds"),
                "now": now,
            },
        )

        exec_id = str(uuid.uuid4())
        github_run_id = run_id or result.get("workflow_run_id")
        db.execute(
            text("""
                INSERT INTO workflow_executions (id, generation_id, git_hub_run_id, status, conclusion, created_at, updated_at)
                VALUES (:id, :gen_id, :run_id, :status, :conclusion, :now, :now)
            """),
            {
                "id": exec_id,
                "gen_id": generation_id,
                "run_id": github_run_id,
                "status": result.get("workflow_status", "completed"),
                "conclusion": result.get("workflow_conclusion", ""),
                "now": now,
            },
        )

        for idx, f in enumerate(result.get("findings", [])):
            if isinstance(f, dict):
                # Several columns have hard VARCHAR caps (scanner 50,
                # finding_type 100, severity 20, cwe 50, owasp 100).
                # Truncate defensively to avoid StringDataRightTruncation.
                def _cap(s: str | None, n: int) -> str:
                    s = s or ""
                    return s[:n]

                db.execute(
                    text("""
                        INSERT INTO findings (id, execution_id, scanner, finding_type, severity, file, line, code_snippet, explanation, recommendation, cwe, owasp, created_at)
                        VALUES (:id, :exec_id, :scanner, :type, :severity, :file, :line, :snippet, :explanation, :remediation, :cwe, :owasp, :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "exec_id": exec_id,
                        "scanner": _cap(f.get("scanner") or f.get("source_tool") or "ai", 50),
                        "type": _cap(f.get("type") or f.get("title") or "finding", 100),
                        "severity": _cap(f.get("severity", "medium"), 20),
                        "file": _cap(f.get("file_location") or f.get("file", ""), 500),
                        "line": f.get("line"),
                        "snippet": f.get("code_snippet", ""),
                        "explanation": f.get("evidence") or f.get("explanation", ""),
                        "remediation": f.get("remediation_recommendation") or f.get("recommendation", ""),
                        "cwe": _cap(f.get("cwe", ""), 50),
                        "owasp": _cap(f.get("owasp", ""), 100),
                        "now": now,
                    },
                )

        if result.get("risk_score") is not None:
            db.execute(
                text("""
                    INSERT INTO risk_assessments (id, execution_id, risk_score, security_posture, compliance_score, severity_breakdown, total_findings, risk_level, created_at)
                    VALUES (:id, :exec_id, :risk_score, NULL, :compliance_score, :severity_breakdown, :total_findings, :risk_level, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "exec_id": exec_id,
                    "risk_score": result.get("risk_score"),
                    "compliance_score": result.get("compliance_score"),
                    "severity_breakdown": json.dumps(result.get("severity_breakdown", {})),
                    "total_findings": len(result.get("findings", [])),
                    "risk_level": result.get("risk_level", ""),
                    "now": now,
                },
            )

        for rec in result.get("recommendations", []):
            if isinstance(rec, str):
                db.execute(
                    text("""
                        INSERT INTO recommendations (id, execution_id, title, description, priority, created_at)
                        VALUES (:id, :exec_id, :title, :desc, :priority, :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "exec_id": exec_id,
                        "title": rec,
                        "desc": rec,
                        "priority": "medium",
                        "now": now,
                    },
                )
            elif isinstance(rec, dict):
                db.execute(
                    text("""
                        INSERT INTO recommendations (id, execution_id, title, description, impact, remediation, example_before, example_after, priority, created_at)
                        VALUES (:id, :exec_id, :title, :desc, :impact, :remediation, :before, :after, :priority, :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "exec_id": exec_id,
                        "title": rec.get("title", "Recommendation"),
                        "desc": rec.get("description", ""),
                        "impact": rec.get("impact", ""),
                        "remediation": rec.get("remediation", ""),
                        "before": rec.get("example_before", ""),
                        "after": rec.get("example_after", ""),
                        "priority": rec.get("priority", "medium"),
                        "now": now,
                    },
                )

        for cm in result.get("compliance_mappings", []):
            if isinstance(cm, dict):
                db.execute(
                    text("""
                        INSERT INTO compliance_mappings (id, execution_id, framework, control_id, control_name, status, finding_ids, created_at)
                        VALUES (:id, :exec_id, :framework, :control_id, :control_name, :status, :finding_ids, :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "exec_id": exec_id,
                        "framework": cm.get("framework", ""),
                        "control_id": cm.get("control_id", ""),
                        "control_name": cm.get("control_name", ""),
                        "status": cm.get("status", "not_applicable"),
                        "finding_ids": "{}",
                        "now": now,
                    },
                )

        db.commit()
        db.close()
    except Exception as e:
        print(f"[persist-analysis] error: {e}")
        import traceback
        traceback.print_exc()
        pass


def _get_saved_analysis(run_id: int) -> dict | None:
    """Retrieve previously saved analysis results for a GitHub run ID."""
    try:
        db = SessionLocal()
        row = db.execute(
            text("""
                SELECT we.id, we.git_hub_run_id, we.status, we.conclusion,
                       pg.generated_yaml, pg.stages
                FROM workflow_executions we
                JOIN pipeline_generations pg ON pg.id = we.generation_id
                WHERE we.git_hub_run_id = :run_id
                ORDER BY we.created_at DESC
                LIMIT 1
            """),
            {"run_id": run_id},
        ).fetchone()
        if not row:
            return None

        exec_id = str(row[0])

        findings = []
        f_rows = db.execute(
            text("""
                SELECT scanner, finding_type, severity, file, line, code_snippet,
                       explanation, recommendation, cwe, owasp
                FROM findings WHERE execution_id = :exec_id
            """),
            {"exec_id": exec_id},
        ).fetchall()
        for f in f_rows:
            findings.append({
                "scanner": f[0],
                "type": f[1],
                "severity": f[2],
                "file": f[3],
                "line": f[4],
                "code_snippet": f[5],
                "explanation": f[6],
                "recommendation": f[7],
                "cwe": f[8],
                "owasp": f[9],
            })

        risk = db.execute(
            text("""
                SELECT risk_score, compliance_score, severity_breakdown, risk_level
                FROM risk_assessments WHERE execution_id = :exec_id LIMIT 1
            """),
            {"exec_id": exec_id},
        ).fetchone()

        # Coverage is stored in pipeline_analyses; risk_assessments no longer
        # tracks the unsupported security_posture field.
        coverage_row = db.execute(
            text("""
                SELECT security_coverage_score, raw_scan_data
                FROM pipeline_analyses WHERE pipeline_run_id = :exec_id LIMIT 1
            """),
            {"exec_id": exec_id},
        ).fetchone()
        security_coverage_score = float(coverage_row[0]) if coverage_row and coverage_row[0] is not None else None
        score_metadata = {}
        if coverage_row and coverage_row[1]:
            try:
                raw = coverage_row[1]
                if isinstance(raw, str):
                    raw = json.loads(raw)
                score_metadata = raw.get("score_metadata", {})
            except Exception:
                pass

        recommendations = []
        r_rows = db.execute(
            text("""
                SELECT title, description, impact, remediation, example_before, example_after, priority
                FROM recommendations WHERE execution_id = :exec_id
            """),
            {"exec_id": exec_id},
        ).fetchall()
        for r in r_rows:
            recommendations.append({
                "title": r[0],
                "description": r[1],
                "impact": r[2],
                "remediation": r[3],
                "example_before": r[4],
                "example_after": r[5],
                "priority": r[6],
            })

        compliance_mappings = []
        c_rows = db.execute(
            text("""
                SELECT framework, control_id, control_name, status
                FROM compliance_mappings WHERE execution_id = :exec_id
            """),
            {"exec_id": exec_id},
        ).fetchall()
        for c in c_rows:
            compliance_mappings.append({
                "framework": c[0],
                "control_id": c[1],
                "control_name": c[2],
                "status": c[3],
            })

        db.close()

        # Load the four-category dashboard + extra buckets from the
        # `pipeline_analyses.raw_scan_data` JSONB column. Older rows
        # may not have it; in that case we just return empty buckets.
        workflow_config_issues: list = []
        maintenance_warnings: list = []
        external_service_issues: list = []
        remediation_recommendations: list = []
        dashboard_findings: dict = {}
        try:
            db = SessionLocal()
            raw_row = db.execute(
                text("SELECT raw_scan_data FROM pipeline_analyses WHERE pipeline_run_id = :rid LIMIT 1"),
                {"rid": exec_id},
            ).fetchone()
            if raw_row and raw_row[0]:
                raw = raw_row[0]
                if isinstance(raw, str):
                    raw = json.loads(raw)
                workflow_config_issues = raw.get("workflow_config_issues", []) or []
                maintenance_warnings = raw.get("maintenance_warnings", []) or []
                external_service_issues = raw.get("external_service_issues", []) or []
                remediation_recommendations = raw.get("remediation_recommendations", []) or []
                dashboard_findings = raw.get("dashboard_findings", {}) or {}
            db.close()
        except Exception:
            pass

        if not dashboard_findings:
            dashboard_findings = _build_dashboard_from_state({
                "findings": findings,
                "workflow_config_issues": workflow_config_issues,
                "maintenance_warnings": maintenance_warnings,
                "external_service_issues": external_service_issues,
            })

        return {
            "summary": "Analysis complete (cached).",
            "findings": findings,
            "risk_score": float(risk[0]) if risk else None,
            "risk_level": risk[3] if risk else None,
            "security_standards_coverage_score": float(risk[1]) if risk else None,
            "compliance_score": float(risk[1]) if risk else None,
            "security_coverage_score": security_coverage_score,
            "severity_breakdown": json.loads(risk[2]) if risk and risk[2] else None,
            "security_standards_coverage_mappings": compliance_mappings,
            "compliance_mappings": compliance_mappings,
            "recommendations": recommendations,
            "generated_workflow": row[4] or "",
            "workflow_conclusion": row[3],
            "errors": [],
            "cached": True,
            "dashboard_findings": dashboard_findings,
            "workflow_config_issues": workflow_config_issues,
            "maintenance_warnings": maintenance_warnings,
            "external_service_issues": external_service_issues,
            "remediation_recommendations": remediation_recommendations,
            "score_metadata": score_metadata,
        }
    except Exception as e:
        print(f"[get-saved-analysis] error: {e}")
        return None


def get_saved_analysis(run_id: int) -> dict | None:
    return _get_saved_analysis(run_id)


def run_repo_analyze(
    repository_full_name: str,
    github_token: str | None = None,
) -> dict:
    state = _get_default_state(repository_full_name, github_token)

    try:
        state = _invoke_graph_phase(state, [
            "repository_connection",
            "repository_scan",
            "technology_detection",
            "architecture_detection",
            "deployment_detection",
            "domain_detection",
        ])
    except Exception as e:
        state["errors"].append(str(e))

    arch_raw = state.get("detected_architecture", {})
    arch_type = state.get("detected_architecture_type")
    if not arch_type and isinstance(arch_raw, dict):
        arch_type = arch_raw.get("architecture_type", "monolithic")
    elif not arch_type:
        arch_type = arch_raw if isinstance(arch_raw, str) else "monolithic"

    deployment = state.get("detected_deployment", {}) or {}
    security_needs = state.get("inferred_security_needs", {}) or {}

    return {
        "repository": repository_full_name,
        "repository_url": state.get("repository_url"),
        "default_branch": state.get("repository_default_branch"),
        "technologies": state.get("detected_technologies", {}),
        "architecture": arch_type,
        "architecture_detail": arch_raw if isinstance(arch_raw, dict) else {},
        "architecture_confidence": state.get("detected_architecture_confidence", 0.0),
        "architecture_reason": state.get("detected_architecture_reason", ""),
        "deployment": deployment,
        "recommended_deployment_target": state.get("recommended_deployment_target", "docker"),
        "domain": state.get("detected_domain"),
        "domain_confidence": state.get("domain_confidence", 0.0),
        "domain_evidence": state.get("domain_evidence", []),
        "domain_threats": state.get("domain_threats", []),
        "attack_surfaces": state.get("attack_surfaces", []),
        "security_requirements": security_needs,
        "existing_workflows": state.get("existing_workflows", []),
        "errors": state.get("errors", []),
        "unified_response": _build_unified_response(state),
    }


def _build_unified_response(state: dict) -> dict:
    technologies = state.get("detected_technologies", {}) or {}
    if not isinstance(technologies, dict):
        technologies = {}
    architecture = state.get("detected_architecture", {}) or {}
    if not isinstance(architecture, dict):
        architecture = {}
    deployment = state.get("detected_deployment", {}) or {}
    if not isinstance(deployment, dict):
        deployment = {}
    security_needs = state.get("inferred_security_needs", {}) or {}
    if not isinstance(security_needs, dict):
        security_needs = {}

    return {
        "repository_analysis": {
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
            "domain": {
                "detected_domain": state.get("detected_domain"),
                "domain_confidence": state.get("domain_confidence", 0.0),
                "domain_evidence": state.get("domain_evidence", []),
                "domain_threats": state.get("domain_threats", []),
                "attack_surfaces": state.get("attack_surfaces", []),
            },
            "detected_at": datetime.now(timezone.utc).isoformat() + "Z",
        },
        "security_requirements": {
            "security_controls": security_needs.get("security_controls", []),
            "required_tools": security_needs.get("required_tools", []),
            "pipeline_stages": security_needs.get("pipeline_stages", []),
            "total_controls": len(security_needs.get("security_controls", [])),
            "recommended_count": len([c for c in security_needs.get("security_controls", []) if c.get("status") == "recommended"]),
            "optional_count": len([c for c in security_needs.get("security_controls", []) if c.get("status") == "optional"]),
            "not_required_count": len([c for c in security_needs.get("security_controls", []) if c.get("status") == "not_required"]),
            "stage_explanations": state.get("stage_explanations", []),
        },
        "metadata": {
            "repository_full_name": state.get("repository_full_name"),
            "request_type": state.get("request_type"),
            "errors": state.get("errors", []),
            "error_stage": state.get("error_stage"),
        },
        "dashboard_findings": _build_dashboard_from_state(state),
        "workflow_config_issues": state.get("workflow_config_issues", []),
        "maintenance_warnings": state.get("maintenance_warnings", []),
        "external_service_issues": state.get("external_service_issues", []),
        "remediation_recommendations": state.get("remediation_recommendations", []),
    }


def run_repo_generate(
    repository_full_name: str,
    github_token: str | None = None,
    project_id: str | None = None,
    query: str | None = None,
    extra: dict | None = None,
    cached_insights: dict | None = None,
) -> dict:
    # Wall-clock timer for the whole pipeline. Logged at the end so
    # ops can see how long each phase took without digging through
    # uvicorn logs. The previous implementation only logged
    # individual node_io durations, which made it impossible to
    # tell whether slowness was in GitHub fetch, LLM call, or
    # workflow generation.
    import time as _wallclock
    _wc_start = _wallclock.monotonic()
    print(f"[pipeline] >>> START run_repo_generate for {repository_full_name}")

    state = _get_default_state(repository_full_name, github_token)
    state["extra_params"] = extra or {}
    state["extra_params"]["_cached_insights_used"] = bool(cached_insights)

    nodes = [
        "repository_connection",
        "repository_scan",
    ]

    if cached_insights:
        print(f"[DEBUG] run_repo_generate using cached_insights for {repository_full_name}")
        _apply_cached_insights(state, cached_insights)
        nodes.extend([
            "coverage_inference",
            "pattern_inference",
            "pipeline_augmentation",
            "job_reasoning",
            "workflow_generation",
            "workflow_validation",
        ])
    else:
        print(f"[DEBUG] run_repo_generate running full detection for {repository_full_name}")
        nodes.extend([
            "technology_detection",
            "architecture_detection",
            "deployment_detection",
            "domain_detection",
            "coverage_inference",
            "pattern_inference",
            "pipeline_augmentation",
            "job_reasoning",
            "workflow_generation",
            "workflow_validation",
        ])

    try:
        # Wall-clock deadline for the full dispatch loop. Each
        # LLM-backed node is allowed to take as long as the
        # upstream is willing to wait (we cannot interrupt a
        # single in-flight HTTP call to the LLM provider without
        # depending on a non-portable signal/threading trick), but
        # we WILL skip any remaining nodes once the budget is
        # exhausted. This guarantees the FE gets a response within
        # PIPELINE_DEADLINE_SECONDS + (one in-flight LLM call
        # duration) instead of waiting for nginx's
        # proxy_read_timeout (900s) to fire.
        _deadline = time.monotonic() + PIPELINE_DEADLINE_SECONDS
        state = _invoke_graph_phase(state, nodes, deadline_monotonic=_deadline)
    except Exception as e:
        state["errors"].append(str(e))

    # Workflow configuration analysis layer:
    #
    # struktur-v6 cleanup (P3.3): `workflow_config_issue` and
    # `workflow_config_remediation` nodes are NOT part of the 21-node
    # architecture. We retain the inline error classification logic that
    # was their fallback — it ensures transient upstream errors
    # (e.g. "Request failed with status code 502") are routed into
    # `state["external_service_issues"]` so the risk score is never
    # contaminated and the PR creation can still proceed.
    try:
        from app.agents.finding_categories import classify_httpx_exception, CATEGORY_EXTERNAL
        remaining: list[dict] = []
        transient_keywords = (
            "502", "503", "504", "bad gateway", "service unavailable",
            "gateway timeout", "request failed with status code",
            "our services aren't available", "github services aren't available",
            "connection refused", "connection reset", "timed out",
            "openai", "anthropic", "openrouter",
        )
        for err in state.get("errors") or []:
            if isinstance(err, str) and any(
                kw in err.lower() for kw in transient_keywords
            ):
                classified = classify_httpx_exception(
                    RuntimeError(err), source="llm_api_fallback"
                )
                if classified:
                    remaining.append({**classified, "category": CATEGORY_EXTERNAL})
            else:
                remaining.append({
                    "category": "unknown_error",
                    "rule": "unclassified_error",
                    "message": err[:300],
                })
        state["external_service_issues"] = state.get("external_service_issues", []) + remaining
        state["errors"] = [
            e for e in state.get("errors") or []
            if not any(kw in str(e).lower() for kw in transient_keywords)
        ]
        if not state["errors"]:
            state["error_stage"] = None
    except Exception:
        pass

    result = _build_pipeline_response(state, repository_full_name)
    result["extra_params"] = extra or {}
    result["unified_response"] = _build_unified_response(state)
    persist_err = _persist_pipeline_result(repository_full_name, result, project_id, query)
    if persist_err:
        result.setdefault("errors", []).append(persist_err)
    _wc_elapsed = _wallclock.monotonic() - _wc_start
    print(
        f"[pipeline] <<< END run_repo_generate for {repository_full_name} "
        f"in {_wc_elapsed:.1f}s "
        f"(status={result.get('status')!r}, "
        f"errors={len(result.get('errors') or [])}, "
        f"stages={len(result.get('generated_stages', []))})"
    )
    return result


def _apply_cached_insights(state: PipelineEngineerState, insights: dict):
    """Apply cached repository insights so detection LLM calls can be skipped."""
    # In v9.2, security_requirement_inference was removed and
    # the inferred_security_needs is built inline from the
    # pipeline_augmentation node downstream. For cached paths we
    # synthesise a minimal default-needs dict so the rest of the
    # pipeline (workflow_generator_node) can still run.
    def _default_needs(tech, arch, dep):
        arch_type = (arch or {}).get("architecture_type", "monolithic") if isinstance(arch, dict) else "monolithic"
        return {
            "security_controls": [
                {"control": "lint", "status": "recommended"},
                {"control": "sast", "status": "recommended"},
                {"control": "secret-scan", "status": "recommended"},
            ],
            "required_stages": ["lint", "sast", "secret-scan"],
            "required_tools": [],
            "pipeline_stages": ["lint", "sast", "secret-scan"],
            "architecture_type": arch_type,
        }

    state["detected_technologies"] = insights.get("technologies") or state.get("detected_technologies", {})
    state["detected_architecture"] = insights.get("architecture") or state.get("detected_architecture", {})
    state["detected_architecture_type"] = insights.get("architecture_type") or state.get("detected_architecture_type")
    state["detected_architecture_confidence"] = insights.get("architecture_confidence", 0.85)
    state["detected_deployment"] = insights.get("deployment") or state.get("detected_deployment", {})
    state["recommended_deployment_target"] = insights.get("recommended_deployment_target") or state.get("recommended_deployment_target")

    if insights.get("security_needs"):
        state["inferred_security_needs"] = insights.get("security_needs")
    else:
        state["inferred_security_needs"] = _default_needs(
            state.get("detected_technologies", {}),
            state.get("detected_architecture", {}),
            state.get("detected_deployment", {}),
        )

    state["findings"] = insights.get("findings") or state.get("findings", [])
    state["source_files"] = insights.get("source_files") or state.get("source_files", [])


def run_repo_deploy(
    repository_full_name: str,
    github_token: str | None = None,
    workflow_yaml: str | None = None,
    workflow_yaml_generic: str | None = None,
    workflow_yaml_custom: str | None = None,
    workflow_filename: str = "ai-devsecops.yml",
    pr_title: str | None = None,
    pr_body: str | None = None,
) -> dict:
    state = _get_default_state(repository_full_name, github_token)
    state["generated_workflow"] = workflow_yaml
    if workflow_yaml_generic:
        state["generated_workflow_generic"] = workflow_yaml_generic
    if workflow_yaml_custom:
        state["generated_workflow_custom"] = workflow_yaml_custom
        state["generated_workflow_files"] = [
            {"name": "ai-devsecops.yml", "path": ".github/workflows/ai-devsecops.yml", "kind": "generic"},
            {"name": "ai-devsecops-custom.yml", "path": ".github/workflows/ai-devsecops-custom.yml", "kind": "custom"},
        ]
    state["validation_passed"] = True

    try:
        db = SessionLocal()
        pip_row = db.execute(
            text("""
                SELECT p.id, p.version_number FROM pipelines p
                JOIN repositories r ON r.id = p.repository_id
                WHERE r.full_name = :repo
                ORDER BY p.created_at DESC LIMIT 1
            """),
            {"repo": repository_full_name},
        ).fetchone()
        if pip_row:
            pipeline_id = str(pip_row[0])
            pipeline_version = pip_row[1] if len(pip_row) > 1 else 1
            state["pipeline_version"] = pipeline_version
            # The pipeline version is recorded for DB tracking and
            # surfaced via the PR body, but the workflow FILE name
            # is fixed at 'ai-devsecops.yml' so each new deploy
            # overwrites the previous one (no historical
            # v*.yml accumulation in the repo).
        db.close()
    except Exception as e:
        print(f"[run-repo-deploy] version lookup error: {e}")

    state["workflow_file"] = f".github/workflows/{workflow_filename}"

    try:
        state = _invoke_graph_phase(state, [
            "repository_connection",
            "github_branch_creation",
            "pull_request_creation",
        ])
    except Exception as e:
        state["errors"].append(str(e))

    result = {
        "branch": state.get("github_branch", ""),
        "commit_sha": state.get("github_commit_sha", ""),
        "pr_number": state.get("github_pr_number", 0),
        "pr_url": state.get("github_pr_url", ""),
        "success": not state.get("errors"),
        "errors": state.get("errors", []),
        "workflow_file": state.get("workflow_file", ""),
        "workflow_file_custom": state.get("workflow_file_custom", ""),
        "workflow_files": state.get("workflow_files", []),
    }

    # Persist deployment info to the latest pipeline for this repo
    if result.get("success"):
        try:
            db = SessionLocal()
            pip_row = db.execute(
                text("""
                    SELECT p.id, p.version_number FROM pipelines p
                    JOIN repositories r ON r.id = p.repository_id
                    WHERE r.full_name = :repo
                    ORDER BY p.created_at DESC LIMIT 1
                """),
                {"repo": repository_full_name},
            ).fetchone()
            if pip_row:
                pipeline_id = str(pip_row[0])
                pipeline_version = pip_row[1] if len(pip_row) > 1 else None
                dep_info = {
                    "branch": result["branch"],
                    "pr_number": result["pr_number"],
                    "pr_url": result["pr_url"],
                    "workflow_file": result["workflow_file"],
                }
                db.execute(
                    text("UPDATE pipelines SET deployment_results = :dep, status = 'deployed' WHERE id = :pid"),
                    {
                        "dep": json.dumps(dep_info),
                        "pid": pipeline_id,
                    },
                )
                db.commit()
                if pipeline_version:
                    result["pipeline_version"] = pipeline_version

            db.close()
        except Exception as e:
            print(f"[run-repo-deploy] error: {e}")
            import traceback
            traceback.print_exc()

    return result


def _persist_execution_jobs(repository_full_name: str, state: dict):
    """Persist workflow job data to the pipeline_runs table after execution monitoring."""
    run_id = state.get("workflow_run_id")
    jobs = state.get("workflow_jobs", [])
    if not run_id:
        return
    try:
        db = SessionLocal()
        import json

        # Check if a run with this git_hub_run_id already exists
        existing = db.execute(
            text("SELECT id, pipeline_id FROM pipeline_runs WHERE git_hub_run_id = :run_id LIMIT 1"),
            {"run_id": run_id},
        ).fetchone()

        if existing:
            exec_id = str(existing[0])
            pipeline_id = str(existing[1])
            db.execute(
                text("""
                    UPDATE pipeline_runs
                    SET jobs = :jobs,
                        status = :status,
                        conclusion = :conclusion,
                        duration_seconds = :duration
                    WHERE id = :id
                """),
                {
                    "id": exec_id,
                    "jobs": json.dumps(jobs) if jobs else None,
                    "status": state.get("workflow_status", "completed"),
                    "conclusion": state.get("workflow_conclusion", ""),
                    "duration": state.get("workflow_duration_seconds"),
                },
            )
        else:
            # Find the latest pipeline for this repo to attach the run
            pip_row = db.execute(
                text("""
                    SELECT p.id FROM pipelines p
                    JOIN repositories r ON r.id = p.repository_id
                    WHERE r.full_name = :repo
                    ORDER BY p.created_at DESC LIMIT 1
                """),
                {"repo": repository_full_name},
            ).fetchone()
            if not pip_row:
                db.close()
                return
            pipeline_id = str(pip_row[0])
            exec_id = str(uuid.uuid4())
            run_number_row = db.execute(
                text("SELECT COALESCE(MAX(run_number), 0) + 1 FROM pipeline_runs WHERE pipeline_id = :pid"),
                {"pid": pipeline_id},
            ).fetchone()
            run_number = run_number_row[0] if run_number_row else 1
            now_ts = datetime.now(timezone.utc).isoformat()
            db.execute(
                text("""
                    INSERT INTO pipeline_runs (id, pipeline_id, run_number, git_hub_run_id, status, conclusion, jobs, started_at, completed_at, duration_seconds, created_at)
                    VALUES (:id, :pid, :num, :run_id, :status, :conclusion, :jobs, :started, :completed, :duration, :now)
                """),
                {
                    "id": exec_id,
                    "pid": pipeline_id,
                    "num": run_number,
                    "run_id": run_id,
                    "status": state.get("workflow_status", "running"),
                    "conclusion": state.get("workflow_conclusion", ""),
                    "jobs": json.dumps(jobs) if jobs else None,
                    "started": state.get("workflow_started_at") or now_ts,
                    "completed": state.get("workflow_completed_at"),
                    "duration": state.get("workflow_duration_seconds"),
                    "now": now_ts,
                },
            )

        # Update pipeline status to reflect execution
        status = "executed"
        if state.get("workflow_conclusion") == "success":
            status = "analyzed"
        elif state.get("errors"):
            status = "failed"
        db.execute(
            text("UPDATE pipelines SET status = :status, updated_at = :now WHERE id = :pid"),
            {"status": status, "now": datetime.now(timezone.utc).isoformat(), "pid": pipeline_id},
        )

        db.commit()
        db.close()
    except Exception as e:
        print(f"[persist-execution-jobs] error: {e}")
        import traceback
        traceback.print_exc()
        pass


def run_repo_pipeline(
    repository_full_name: str,
    github_token: str | None = None,
    auto_deploy: bool = False,
) -> dict:
    result = run_repo_generate(repository_full_name=repository_full_name, github_token=github_token)
    if auto_deploy and not result.get("errors"):
        deploy_result = run_repo_deploy(
            repository_full_name=repository_full_name,
            github_token=github_token,
            workflow_yaml=result.get("generated_workflow"),
        )
        result["deploy_result"] = deploy_result
    return result


def run_repo_execute(
    repository_full_name: str,
    github_token: str | None = None,
    trigger: bool = True,
) -> dict:
    state = _get_default_state(repository_full_name, github_token)
    try:
        state = _invoke_graph_phase(state, [
            "repository_connection",
            "workflow_execution",
        ])
    except Exception as e:
        state["errors"].append(str(e))
    return {
        "run_id": state.get("workflow_run_id"),
        "status": state.get("workflow_status", "triggered"),
        "errors": state.get("errors", []),
    }


def _lookup_workflow_file(repository_full_name: str) -> tuple[str | None, str | None]:
    """Look up the workflow file path from the latest pipeline's deployment_results."""
    try:
        db = SessionLocal()
        row = db.execute(
            text("""
                SELECT p.deployment_results, p.generated_yaml
                FROM pipelines p
                JOIN repositories r ON r.id = p.repository_id
                WHERE r.full_name = :repo
                ORDER BY p.created_at DESC LIMIT 1
            """),
            {"repo": repository_full_name},
        ).fetchone()
        db.close()
        if row:
            dep_results = row[0]
            generated_yaml = row[1]
            workflow_file = None
            if dep_results:
                try:
                    dep_info = json.loads(dep_results) if isinstance(dep_results, str) else dep_results
                    workflow_file = dep_info.get("workflow_file")
                except (json.JSONDecodeError, TypeError):
                    pass
            return workflow_file, generated_yaml
    except Exception as e:
        print(f"[lookup-workflow-file] error: {e}")
    return None, None


def _persist_remediation_result(
    repository_full_name: str,
    state: dict,
    project_id: str | None = None,
) -> str | None:
    """Persist remediation as a new pipeline version. Returns pipeline_id or error string."""
    if not state.get("remediation_workflow"):
        return None
    try:
        db = SessionLocal()
        now = datetime.now(timezone.utc).isoformat()

        repo_uuid = None
        resolved_project_id = project_id
        try:
            row = db.execute(
                text("SELECT id, project_id FROM repositories WHERE full_name = :name LIMIT 1"),
                {"name": repository_full_name},
            ).fetchone()
            if row:
                repo_uuid = str(row[0])
                resolved_project_id = resolved_project_id or str(row[1])
        except Exception as e:
            print(f"[persist-remediation] lookup error: {e}")
            db.close()
            return f"lookup error: {e}"

        if not repo_uuid:
            db.close()
            return "repository not found"

        github_run_id = state.get("github_run_id")
        original_stages = []
        original_controls = []
        original_compliance = {}
        original_params = {}
        if github_run_id:
            try:
                orig_row = db.execute(
                    text("""
                        SELECT p.stages, p.security_controls_applied, p.compliance_metadata, p.generation_params
                        FROM pipelines p
                        JOIN pipeline_runs pr ON pr.pipeline_id = p.id
                        WHERE pr.git_hub_run_id = :run_id
                        LIMIT 1
                    """),
                    {"run_id": github_run_id},
                ).fetchone()
                if orig_row:
                    original_stages = json.loads(orig_row[0]) if orig_row[0] else []
                    original_controls = json.loads(orig_row[1]) if orig_row[1] else []
                    original_compliance = json.loads(orig_row[2]) if orig_row[2] else {}
                    original_params = json.loads(orig_row[3]) if orig_row[3] else {}
                    print(f"[persist-remediation] Copied from original pipeline: stages={len(original_stages)}, controls={len(original_controls)}")
            except Exception as e:
                print(f"[persist-remediation] Failed to lookup original pipeline: {e}")

        version_row = db.execute(
            text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM pipelines WHERE repository_id = :repo"),
            {"repo": repo_uuid},
        ).fetchone()
        version_number = version_row[0] if version_row else 1

        pipeline_id = str(uuid.uuid4())
        remediated_yaml = state.get("remediation_workflow", "") or ""
        workflow_file = state.get("workflow_file") or ".github/workflows/ci-cd.yml"

        root_cause = state.get("root_cause", {}) or {}
        reasoning = ""
        if state.get("remediation_suggestions"):
            reasoning = state["remediation_suggestions"][0].get("reasoning", "")

        deployment_info = {
            "branch": state.get("remediation_branch", ""),
            "pr_number": state.get("remediation_pr_number", 0),
            "pr_url": state.get("remediation_pr_url", ""),
            "workflow_file": workflow_file,
        }

        db.execute(
            text("""
                INSERT INTO pipelines (id, repository_id, version_number, prompt, generated_yaml, stages, ai_explanation, generation_params, validation_results, deployment_results, security_controls_applied, compliance_metadata, status, created_at)
                VALUES (:id, :repo, :version, :prompt, :yaml, :stages, :explanation, :params, :validation, :deployment, :controls, :compliance, :status, :now)
            """),
            {
                "id": pipeline_id,
                "repo": repo_uuid,
                "version": version_number,
                "prompt": f"Remediation: {root_cause.get('root_cause', 'workflow fix')[:100]}",
                "yaml": remediated_yaml,
                "stages": json.dumps(original_stages),
                "explanation": reasoning,
                "params": json.dumps({**original_params, "source": "remediation", "remediation_run_id": state.get("workflow_run_id"), "original_github_run_id": github_run_id}),
                "validation": json.dumps({"valid": True, "errors": [], "warnings": [], "remediated": True}),
                "deployment": json.dumps(deployment_info) if deployment_info else None,
                "controls": json.dumps(original_controls),
                "compliance": json.dumps(original_compliance),
                "status": "deployed" if state.get("remediation_pr_url") else "generated",
                "now": now,
            },
        )

        findings = state.get("findings", [])
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            if isinstance(f, dict):
                sev = (f.get("severity") or "medium").lower()
                if sev in severity_counts:
                    severity_counts[sev] += 1

        root_cause_type = root_cause.get("failure_type", "unknown")
        if not findings and root_cause_type != "unknown":
            findings = [{
                "type": root_cause_type,
                "severity": "high",
                "title": f"Remediated: {root_cause_type}",
                "explanation": root_cause.get("root_cause", ""),
                "recommendation": reasoning,
            }]

        exec_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO pipeline_runs (id, pipeline_id, run_number, status, conclusion, created_at)
                VALUES (:id, :pid, :run_num, :status, :conclusion, :now)
            """),
            {
                "id": exec_id,
                "pid": pipeline_id,
                "run_num": 1,
                "status": "pending",
                "conclusion": "",
                "now": now,
            },
        )

        db.execute(
            text("""
                INSERT INTO pipeline_analyses (id, pipeline_run_id, risk_score, compliance_score, workflow_quality_score, security_coverage_score, findings_summary, severity_breakdown, recommendations, ai_explanation, created_at)
                VALUES (:id, :run_id, :risk, :compliance, NULL, :coverage, :findings, :severity, :recs, :explanation, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "run_id": exec_id,
                "risk": state.get("risk_score"),
                "compliance": state.get("compliance_score"),
                "coverage": state.get("security_coverage_score"),
                "findings": json.dumps(findings),
                "severity": json.dumps(severity_counts),
                "recs": json.dumps(state.get("recommendations", [])),
                "explanation": reasoning,
                "now": now,
            },
        )

        db.commit()

        original_run_id = state.get("workflow_run_id")
        if original_run_id:
            try:
                db.execute(
                    text("UPDATE pipeline_runs SET remediation_status = 'remediated' WHERE git_hub_run_id = :run_id"),
                    {"run_id": original_run_id},
                )
                db.commit()
            except Exception as e:
                print(f"[persist-remediation] failed to mark original run: {e}")

        db.close()
        print(f"[persist-remediation] Created pipeline v{version_number} for {repository_full_name}")
        state["_persisted_pipeline_id"] = pipeline_id
        state["_persisted_version"] = version_number
        return None
    except Exception as e:
        err = f"[persist-remediation] error: {e}"
        print(err)
        import traceback
        traceback.print_exc()
        return err


def run_execution_analysis(
    repository_full_name: str,
    github_token: str | None = None,
    run_id: int | None = None,
    workflow_jobs: str | None = None,
    workflow_conclusion: str | None = None,
) -> dict:
    """DEPRECATED — removed per struktur-v6 P3.2.

    The 5-node remediation chain (execution_log_collection →
    failure_analysis → root_cause_detection → remediation_generation →
    remediation_pr_creation) is NOT part of the 21-node architecture.
    This function is retained as a stub for backward compatibility and
    returns a 410-equivalent error payload.
    """
    return {
        "deprecated": True,
        "message": (
            "Flow F (run_execution_analysis) has been removed per struktur-v6. "
            "Workflow remediation is out of scope for this research."
        ),
        "errors": ["endpoint_removed"],
    }


def deploy_remediation_workflow(
    repository_full_name: str,
    github_token: str | None = None,
    workflow_yaml: str = "",
    run_number: int = 0,
    github_run_id: int | None = None,
    base_branch: str = "main",
    workflow_file: str = "ai-devsecops.yml",
) -> dict:
    from app.config import settings
    import time
    import re

    token = github_token or settings.GITHUB_TOKEN
    timestamp = int(time.time())
    branch_name = f"ai-devsecops/remediate-run-{run_number}-{timestamp}"

    # Ensure workflow has workflow_dispatch trigger so it can be manually triggered
    if "workflow_dispatch" not in workflow_yaml:
        workflow_yaml = re.sub(
            r"(on:\s*(?:\n\s+[^\n]+)*)",
            r"\1\n  workflow_dispatch:",
            workflow_yaml,
            count=1,
        )
        if "workflow_dispatch" not in workflow_yaml:
            workflow_yaml = "on:\n  workflow_dispatch:\n  push:\n" + workflow_yaml.partition("\n")[2].lstrip()

    try:
        success = create_branch(repository_full_name, branch_name, base_branch, token)
        if not success:
            return {"error": f"Failed to create branch '{branch_name}'"}

        workflow_path = workflow_file if workflow_file.startswith(".github/workflows/") else f".github/workflows/{workflow_file}"
        commit_msg = f"fix: auto-remediate workflow failure from Run #{run_number}"
        commit_sha = commit_file(repository_full_name, branch_name, workflow_path, workflow_yaml, commit_msg, token)
        if not commit_sha:
            return {"error": "Failed to commit remediation workflow"}

        # Remove every other workflow file so the next run executes ONLY
        # the remediated pipeline. Without this, the user would see the
        # legacy "build (pull_request)" job in addition to the new one.
        from app.services.github_service import delete_file, list_workflow_files
        try:
            existing_workflows = list_workflow_files(repository_full_name, branch_name, token)
            deleted_legacy: list[str] = []
            for wf_path in existing_workflows:
                if wf_path.rstrip("/") == workflow_path.rstrip("/"):
                    continue
                if delete_file(
                    repository_full_name,
                    branch_name,
                    wf_path,
                    message=f"Remove legacy workflow {wf_path} — replaced by remediated pipeline",
                    github_token=token,
                ):
                    deleted_legacy.append(wf_path)
        except Exception as cleanup_err:
            deleted_legacy = []
            print(f"[deploy-remediation] legacy workflow cleanup failed: {cleanup_err}")

        cleanup_section = ""
        if deleted_legacy:
            cleanup_section = (
                "\n\n### Legacy Workflows Removed\n"
                "The following existing workflow files were removed to prevent conflicts:\n"
                + "\n".join(f"- 🗑 `{p}`" for p in deleted_legacy)
            )

        pr_title = f"[AI DevSecOps] Fix workflow failure from Run #{run_number}"
        pr_body = f"""## AI DevSecOps: Automatic Workflow Remediation

This PR fixes the workflow failure from **Run #{run_number}**.

### Changes
- Updated `{workflow_path}` with AI-generated fix{cleanup_section}

### Next Steps
1. Review the changes
2. Merge this PR
3. Monitor the next workflow run
"""
        pr = create_pull_request(repository_full_name, branch_name, pr_title, pr_body, base_branch, token)

        if pr:
            state = {
                "remediation_workflow": workflow_yaml,
                "workflow_file": workflow_file,
                "remediation_branch": branch_name,
                "remediation_pr_number": pr.get("number"),
                "remediation_pr_url": pr.get("html_url"),
                "repository_full_name": repository_full_name,
                "github_run_id": github_run_id,
                "removed_legacy_workflows": deleted_legacy,
            }
            result = {
                "branch": branch_name,
                "pr_number": pr.get("number"),
                "pr_url": pr.get("html_url"),
                "commit_sha": commit_sha,
                "removed_legacy_workflows": deleted_legacy,
            }
            persist_err = _persist_remediation_result(repository_full_name, state)
            if persist_err:
                result["warning"] = f"DB persist skipped: {persist_err}"
            else:
                result["pipeline_id"] = state.get("_persisted_pipeline_id")
                result["pipeline_version"] = state.get("_persisted_version")
                _trigger_workflow_dispatch(repository_full_name, branch_name, workflow_path, token)
            return result
        else:
            return {"error": "Failed to create remediation PR"}

    except Exception as e:
        return {"error": str(e)}


def _trigger_workflow_dispatch(repo: str, ref: str, workflow_path: str, token: str):
    """Trigger a workflow_dispatch event on the remediation branch."""
    import httpx
    workflow_file = workflow_path.split("/")[-1]
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    try:
        resp = httpx.post(
            url,
            json={"ref": ref},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=15,
        )
        if resp.status_code == 204:
            print(f"[deploy-remediation] Workflow dispatch triggered on {ref}")
        else:
            print(f"[deploy-remediation] Workflow dispatch failed (status {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"[deploy-remediation] Workflow dispatch error: {e}")


def _get_generated_workflow_from_db(repository_id: str) -> str | None:
    """Fetch the latest generated workflow YAML from pipeline_generations table."""
    try:
        db = SessionLocal()
        row = db.execute(
            text("""
                SELECT generated_yaml FROM pipeline_generations
                WHERE repository_id = (
                    SELECT id FROM repositories WHERE full_name = :name LIMIT 1
                )
                ORDER BY created_at DESC LIMIT 1
            """),
            {"name": repository_id},
        ).fetchone()
        db.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return None


def _analyze_log_errors(logs: str) -> list[dict]:
    """Parse GitHub Actions logs for common error patterns."""
    import re
    findings = []

    # Unable to resolve action
    resolve_matches = re.findall(
        r"Unable to resolve action `([^`]+)`[\s\S]*?unable to find version `([^`]+)`",
        logs,
    )
    for action_ref, version in resolve_matches:
        findings.append({
            "type": "error",
            "rule": "unable_to_resolve_action",
            "message": f"GitHub cannot resolve action {action_ref} — SHA `{version}` does not exist in the repository.",
            "suggestion": "Revert to the original version tag (e.g., @v2.0.6) or verify the SHA by checking the repository's tags on GitHub.",
        })

    # Resource not accessible
    if re.search(r"Resource not accessible by integration", logs, re.IGNORECASE):
        findings.append({
            "type": "error",
            "rule": "permission_denied",
            "message": "GitHub Actions token lacks required permissions.",
            "suggestion": "Add `permissions: { security-events: write, contents: read }` if needed.",
        })

    # Missing secret
    if re.search(r"secret.*not found|missing.*secret", logs, re.IGNORECASE):
        findings.append({
            "type": "error",
            "rule": "missing_secret",
            "message": "A required GitHub Secret is not configured.",
            "suggestion": "Go to Settings → Secrets and variables → Actions, and add the missing secret.",
        })

    # npm/dependency failure
    if "npm ERR!" in logs:
        findings.append({
            "type": "error",
            "rule": "dependency_installation_failed",
            "message": "npm install/ci failed.",
            "suggestion": "Ensure package-lock.json is committed, or run `npm install` instead of `npm ci`.",
        })

    return findings


def _split_logs_by_job(logs: str, jobs: list[dict]) -> list[dict]:
    """Split a workflow log blob into per-job log text.

    The log can be either:

      1. A single concatenated string (older API) with markers like
         `##[group]<name>`, `##[error]`, `Job name: <name>`.
      2. A zip-extracted blob with `=== <step-file>.txt ===` headers
         (the new format used by `get_workflow_logs`).

    For each job in `jobs`, this function tries to find the best
    matching log slice. The strategy is:
      - Look for the job name (and any of its step numbers) in the
        `=== N_<name>.txt ===` headers emitted by the zip extractor.
      - If the job name is found, take the slice from that header
        to the next `=== ` header (or end of log).
      - As a fallback, do a substring search for the raw job name.
      - If nothing matches, the entire log is associated with the
        job so the heuristic still has content to classify.

    Returns a list of {"job_name": str, "log_text": str} dicts in
    the same order as `jobs`.
    """
    if not logs or not jobs:
        return []
    out: list[dict] = []
    used_ranges: list[tuple[int, int]] = []

    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = job.get("name") or job.get("id") or "unknown"
        # Best-effort: find a `=== N_<sanitized_name>.txt ===` header.
        sanitized = name.lower().replace(" ", "-")
        # Try the common patterns emitted by the zip extractor.
        candidates = [
            f"=== 0_{sanitized}.txt ===",
            f"=== 1_{sanitized}.txt ===",
            f"=== 2_{sanitized}.txt ===",
            f"=== {sanitized}.txt ===",
        ]
        start_idx = -1
        end_idx = len(logs)
        for cand in candidates:
            idx = logs.find(cand)
            if idx != -1:
                start_idx = idx
                # End at the next `=== ` marker.
                next_marker = logs.find("\n=== ", idx + 1)
                if next_marker != -1:
                    end_idx = next_marker
                break
        if start_idx == -1:
            # Fallback: substring search for the job name.
            idx = logs.find(name)
            if idx == -1:
                out.append({"job_name": name, "log_text": logs or ""})
                continue
            start_idx = idx
            end_idx = len(logs)
        out.append({
            "job_name": name,
            "log_text": logs[start_idx:end_idx],
        })
        used_ranges.append((start_idx, end_idx))
    return out


def run_pipeline_analysis(
    repository_id: str,
    run_id: int,
    github_token: str | None = None,
    project_id: str | None = None,
    force: bool = False,
) -> dict:
    """Re-run pipeline analysis.

    Reviewer feedback: a "Refresh Analysis" button in the RunDetail
    page should force the AI agent to re-evaluate the workflow logs
    (otherwise the saved empty analysis is returned and the user
    cannot recover from a transient log-fetch failure). When
    `force=True`, the cached analysis is bypassed and the log
    evaluator runs again.
    """
    import time as _analysis_t
    _analysis_started = _analysis_t.monotonic()
    _ANALYSIS_TOTAL_BUDGET_S = 180.0  # 3 minutes — never block the worker longer

    def _budget_exceeded(label: str = "") -> bool:
        if _analysis_t.monotonic() - _analysis_started > _ANALYSIS_TOTAL_BUDGET_S:
            print(
                f"[analysis] TOTAL budget ({_ANALYSIS_TOTAL_BUDGET_S}s) "
                f"exhausted{f' at {label}' if label else ''}, returning partial result"
            )
            return True
        return False

    # Only consult the cache when force=False. Skipping the
    # _get_saved_analysis call entirely on force=True guarantees the
    # log evaluator runs again even if a stale row is in the DB.
    if not force:
        saved = _get_saved_analysis(run_id)
        if saved:
            print(f"[analysis] Returning saved analysis for run_id={run_id}")
            saved["log_analysis"] = []
            saved["validation_findings"] = []
            saved["validation_errors"] = []
            saved["validation_warnings"] = []
        return saved

    # When `run_id` is None or 0 there is no GitHub Actions run to
    # fetch (the workflow file hasn't been deployed yet). In that
    # case we still want to surface Code Scanning alerts (which are
    # repo-scoped, not run-scoped) and an empty log so the FE can
    # render the dashboard. The AI agent then runs security_analysis
    # on the alerts and saves the analysis.
    if not run_id:
        run_data = {}
        logs = ""
    else:
        run_data = get_workflow_run(repository_id, run_id, github_token) or {}
        logs = get_workflow_logs(repository_id, run_id, github_token) or ""

    state = _get_default_state(repository_id, github_token)
    state["workflow_run_id"] = run_id
    state["workflow_status"] = run_data.get("status")
    state["workflow_conclusion"] = run_data.get("conclusion")

    # Populate `repository_files` and `source_files` from the GitHub
    # tree API so the AI agent (coverage_inference, security_analyzer)
    # can see the actual package manifests and source code even
    # when the caller did not run the full Tahap 1 graph. This is
    # what makes the "Refresh Analysis" button on a not-yet-deployed
    # pipeline produce non-zero applicable security coverages.
    #
    # Performance note (Bab 5.14 / v9.3 hotfix): the previous
    # implementation made 2 sequential HTTP calls per file (one to
    # the tree URL, one to the contents URL) for up to 200 files.
    # For `ecommerce-clean` (~50 source files) that was up to 100
    # serial round-trips to api.github.com with 10s timeout each —
    # worst case 16 minutes for a single repository scan. The new
    # version:
    #   1. caps the number of files fetched to MAX_FILES (30),
    #   2. uses the tree URL only (single call per file via blob URL),
    #   3. uses sequential fetches (no ThreadPoolExecutor — the
    #      uvicorn worker is single-threaded and concurrent sync
    #      HTTP from a sync handler deadlocks the event loop).
    try:
        import httpx as _httpx

        # Cap on files fetched. 30 manifest + source files is plenty
        # for the AI agent to see the project structure; anything more
        # just slows down the scan with diminishing returns.
        MAX_FILES = 30
        # Per-file HTTP timeout. Short so a slow file does not
        # consume the entire request budget.
        PER_FILE_TIMEOUT_S = 5.0

        _headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
        _headers["Accept"] = "application/vnd.github+json"

        # 1. Get the default branch.
        repo_resp = _httpx.get(
            f"https://api.github.com/repos/{repository_id}",
            headers=_headers,
            timeout=10,
        )
        if repo_resp.status_code != 200:
            print(
                f"[analysis] GitHub repo lookup failed: status={repo_resp.status_code} "
                f"body={repo_resp.text[:200]}"
            )
        else:
            default_branch = repo_resp.json().get("default_branch", "main")
            # 2. Get the tree.
            tree_resp = _httpx.get(
                f"https://api.github.com/repos/{repository_id}/git/trees/{default_branch}?recursive=1",
                headers=_headers,
                timeout=10,
            )
            if tree_resp.status_code != 200:
                print(
                    f"[analysis] GitHub tree fetch failed: status={tree_resp.status_code} "
                    f"body={tree_resp.text[:200]}"
                )
            else:
                tree = tree_resp.json().get("tree", [])
            # Filter for package manifests and source files.
            manifest_names = {
                "package.json", "requirements.txt", "pyproject.toml",
                "go.mod", "Cargo.toml", "Gemfile", "build.gradle",
                "pom.xml", "composer.json",
            }
            source_exts = (
                ".js", ".ts", ".jsx", ".tsx", ".py", ".go", ".rs",
                ".java", ".rb", ".php",
            )
            # Pick the most relevant files first:
            #   - all package manifests (cap at 9) — critical for
            #     technology detection
            #   - then source files sorted by path depth (top-level
            #     first), capped to fit MAX_FILES total
            manifest_entries: list[dict] = []
            source_entries: list[dict] = []
            for entry in tree:
                if entry.get("type") != "blob":
                    continue
                path = entry.get("path", "")
                name = path.rsplit("/", 1)[-1].lower()
                if name in manifest_names:
                    manifest_entries.append(entry)
                elif path.endswith(source_exts) and not any(
                    seg in path for seg in ("node_modules", "/test", "dist/", "build/", "venv/", ".venv/")
                ):
                    source_entries.append(entry)
            # Sort source files by depth then path (top-level first)
            source_entries.sort(key=lambda e: (e.get("path", "").count("/"), e.get("path", "")))
            # Truncate to fit budget
            selected = manifest_entries[:9] + source_entries[: max(0, MAX_FILES - 9)]
            print(
                f"[analysis] GitHub tree: {len(tree)} total, "
                f"selected {len(selected)} (manifests={min(9, len(manifest_entries))}, "
                f"source={len(selected) - min(9, len(manifest_entries))})"
            )

            # Sequential fetch (single HTTP call per file via blob
            # URL). No thread pool — uvicorn is single-threaded and
            # concurrent sync HTTP from a sync handler deadlocks
            # the event loop.
            import base64 as _b64
            import time as _time
            _t_start = _time.monotonic()
            repo_files: dict[str, str] = {}
            source_files: list[dict] = []
            for entry in selected:
                if _time.monotonic() - _t_start > 20.0:
                    print(
                        f"[analysis] GitHub fetch budget (20s) exhausted, "
                        f"stopping early with {len(repo_files)} manifests + "
                        f"{len(source_files)} source files"
                    )
                    break
                path = entry.get("path", "")
                url = entry.get("url", "")
                if not url:
                    continue
                try:
                    r = _httpx.get(url, headers=_headers, timeout=PER_FILE_TIMEOUT_S)
                    if r.status_code != 200:
                        continue
                    raw = r.json().get("content", "")
                    text = _b64.b64decode(
                        raw.replace("\n", "")
                    ).decode("utf-8", errors="ignore")
                    if path.rsplit("/", 1)[-1].lower() in manifest_names:
                        repo_files[path] = text
                    else:
                        source_files.append({
                            "path": path,
                            "content": text[:8192],
                        })
                except Exception:
                    continue

            state["repository_files"] = repo_files
            state["source_files"] = source_files
            state["repository_structure"] = [
                e.get("path") for e in tree if e.get("type") == "blob"
            ][:200]
            elapsed = _time.monotonic() - _t_start
            print(
                f"[analysis] populated repository_files={len(repo_files)} "
                f"source_files={len(source_files)} from GitHub tree "
                f"(fetch elapsed {elapsed:.1f}s)"
            )
    except Exception as fetch_exc:
        print(f"[analysis] GitHub tree fetch failed (non-fatal): {fetch_exc}")

    # Primary source: GitHub Code Scanning alerts (OASIS SARIF data
    # already uploaded to GitHub by the workflow's upload-sarif step).
    # This is the most reliable source because it:
    #   - has been processed by GitHub (so it's canonical)
    #   - has CWE/OWASP metadata from the rule
    #   - includes the SARIF location (file:line) precisely
    #   - works even if the artifact download from the API is throttled
    code_scanning_findings: list[dict] = []
    try:
        from app.services.github_service import (
            get_code_scanning_alerts,
            normalize_code_scanning_alerts,
        )
        raw_alerts = get_code_scanning_alerts(
            repo=repository_id,
            run_id=run_id if run_id and run_id > 0 else None,
            state="open",
            github_token=github_token,
        )
        code_scanning_findings = normalize_code_scanning_alerts(raw_alerts)
        print(
            f"[analysis] Code Scanning returned {len(raw_alerts)} raw "
            f"alerts, normalized to {len(code_scanning_findings)} findings"
        )
    except Exception as e:
        print(f"[analysis] Code Scanning fetch failed (non-fatal): {e}")

    # Parse logs for known error patterns
    log_errors = _analyze_log_errors(logs)

    # Reviewer feedback: AI agent evaluates the actual log content
    # per job (not just the job conclusion). This is the proper
    # way to extract real security findings; previous auto-extract
    # only looked at "job failed" and produced generic findings.
    try:
        from app.agents.nodes.ai_log_evaluator import (
            extract_findings_from_logs,
        )
        from app.services.github_service import get_workflow_run_jobs
        jobs = get_workflow_run_jobs(repository_id, run_id, github_token) or []
        # Build per-job log text by splitting the full log on the
        # GitHub Actions step separator. If the split fails, we
        # still get a "no logs" fallback in the extraction result.
        per_job_logs = _split_logs_by_job(logs, jobs)
        log_eval = extract_findings_from_logs(jobs, per_job_logs)
        # Pre-populate the state with log-derived findings so the
        # graph nodes (security_analyzer, response_formatter) can
        # see them.
        state["workflow_jobs"] = jobs
        state["workflow_logs"] = per_job_logs

        # DevSecOps best practice: when force=True (user clicked
        # "Refresh Analysis"), also download the SARIF / JSON
        # artifacts that the workflow uploaded. The AI log
        # evaluator's PRIMARY path (parse_sarif via
        # scanner_normalizer) is much more reliable than the
        # log-line regex fallback, because:
        #   - SARIF carries precise file:line locations
        #   - JSON carries stable package/CVE identifiers
        #   - dedup is by composite key (tool + vuln_id + package),
        #     so the same CVE reported by both dependency-scan and
        #     container-scan collapses into a single finding.
        # We only do this on force=True to avoid hitting GitHub's
        # artifact API on every analysis (rate-limit concern).
        if force:
            try:
                from app.agents.nodes.ai_log_evaluator import (
                    fetch_scanner_outputs,
                )
                scanner_outputs = fetch_scanner_outputs(
                    repository_id=repository_id,
                    run_id=run_id if run_id and run_id > 0 else None,
                    github_token=github_token,
                ) or {}
                if scanner_outputs:
                    state["scanner_outputs"] = scanner_outputs
                    # Expand roll-up advisories (e.g. npm audit's
                    # "84 vulnerabilities") into one row per
                    # package@version so the Security Findings list
                    # and the PDF "Findings by Scanner" section
                    # show every instance. Without this step, the
                    # log-derived path keeps a single row with
                    # `evidence: "84 vulnerabilities"` which is
                    # useless for triage.
                    try:
                        from app.agents.scanner_normalizer import (
                            normalize_and_dedupe,
                        )
                        normalised = normalize_and_dedupe(scanner_outputs)
                        expanded = normalised.get("findings") or []
                        if expanded:
                            print(
                                f"[analysis] scanner_normalizer "
                                f"expanded to {len(expanded)} per-package "
                                f"finding(s) "
                                f"(by_tool={normalised.get('by_tool')})"
                            )
                            # Merge into code_scanning_alerts and
                            # findings so downstream nodes (security
                            # analyzer, response formatter) and the
                            # PDF generator all see the per-package
                            # granularity.
                            code_scanning_findings = list(
                                code_scanning_findings
                            ) + expanded
                            for ef in expanded:
                                state.setdefault("findings", []).append(ef)
                            state["scanner_normalizer"] = {
                                "by_tool": normalised.get("by_tool"),
                                "by_severity": normalised.get("by_severity"),
                                "raw_count": normalised.get("raw_count"),
                                "dropped_count": normalised.get("dropped_count"),
                                "errors": normalised.get("errors"),
                            }
                    except Exception as norm_exc:
                        print(
                            f"[analysis] scanner_normalizer failed "
                            f"(non-fatal): {norm_exc}"
                        )
            except Exception as fetch_exc:
                print(
                    f"[analysis] fetch_scanner_outputs failed "
                    f"(non-fatal, falling back to log heuristic): {fetch_exc}"
                )
        # Add log-derived security findings to the state so
        # downstream nodes can include them in the dashboard.
        for f in log_eval.get("security_findings", []):
            state["findings"].append(f)
        for c in log_eval.get("config_issues", []):
            state["workflow_config_issues"].append(c)
        for s in log_eval.get("skipped_jobs", []):
            state["skipped_jobs"].append(s)
        state["log_extraction"] = {
            "source": log_eval["extraction_source"],
            "lines_scanned": log_eval["lines_scanned"],
            "security_findings_count": len(log_eval["security_findings"]),
            "config_issues_count": len(log_eval["config_issues"]),
            "skipped_jobs_count": len(log_eval["skipped_jobs"]),
            # Reviewer feedback: also include the raw findings so
            # the UI can render them when the graph node pipeline
            # filters them out. The graph-level `state["findings"]`
            # is what gets re-classified by the security_analyzer
            # and may drop log findings; this list is the
            # authoritative log-derived security findings.
            "security_findings": list(log_eval["security_findings"]),
        }
    except Exception as e:
        print(f"[analysis] AI log evaluation failed (non-fatal): {e}")

    # Fetch generated workflow for compliance validation
    generated_yaml = _get_generated_workflow_from_db(repository_id)
    if generated_yaml:
        state["generated_workflow"] = generated_yaml

    # Seed `state["findings"]` with Code Scanning alerts before
    # invoking the graph nodes. The graph nodes (security_analyzer,
    # risk_assessor) can enrich, categorize, and elevate severity
    # but the SARIF-based findings are the primary input now.
    if code_scanning_findings:
        existing = list(state.get("findings", []) or [])
        # Dedupe by (rule_id, file, line) so log-derived findings
        # don't double-count with the SARIF ones.
        seen: set[tuple[str, str, int | None]] = set()
        for f in code_scanning_findings:
            seen.add((
                f.get("rule_id", ""),
                f.get("file_location", ""),
                f.get("line"),
            ))
        merged: list[dict] = list(code_scanning_findings)
        for f in existing:
            key = (f.get("rule_id", ""), f.get("file_location", ""), f.get("line"))
            if key not in seen:
                merged.append(f)
                seen.add(key)
        state["findings"] = merged
        state["code_scanning_alerts"] = code_scanning_findings

        # Download SARIF artifact and feed to LLM to estimate CVSS for
        # findings that the deterministic 3-tier lookup cannot resolve
        # (rule_id not in RULE_CVSS_MAP, no clear type/severity). The
        # LLM only sees the SARIF `rules`/`results` summary, never the
        # full source, so it cannot leak secrets.
        try:
            from app.services.github_service import (
                get_workflow_run_artifacts,
                download_artifact,
            )
            from app.agents.cvss_mapper import score_finding
            from app.agents.llm_cvss_estimator import (
                llm_estimate_cvss_for_findings,
            )
            import time as _ct
            _sarif_start = _ct.monotonic()
            _SARIF_BUDGET_S = 20.0
            artifacts = get_workflow_run_artifacts(
                repository_id, run_id, github_token
            ) or []
            sarif_text: str | None = None
            for art in artifacts:
                if _ct.monotonic() - _sarif_start > _SARIF_BUDGET_S:
                    print(
                        f"[analysis] SARIF artifact download budget "
                        f"({_SARIF_BUDGET_S}s) exhausted, skipping "
                        f"remaining artifacts"
                    )
                    break
                name = (art.get("name") or "").lower()
                if name.endswith(".sarif") or "sarif" in name:
                    sarif_text = download_artifact(
                        repository_id, run_id, art["id"], github_token
                    )
                    if sarif_text:
                        print(
                            f"[analysis] downloaded SARIF artifact "
                            f"{art.get('name')} ({len(sarif_text)} chars)"
                        )
                        break

            # Identify findings that still lack a confident CVSS.
            needs_llm: list[dict] = []
            for f in merged:
                score = f.get("cvss_score")
                vector = f.get("cvss_vector")
                if not isinstance(score, (int, float)) or not vector:
                    needs_llm.append(f)
            if needs_llm and sarif_text:
                print(
                    f"[analysis] requesting LLM CVSS for "
                    f"{len(needs_llm)} findings without rule-level score"
                )
                enriched = llm_estimate_cvss_for_findings(
                    sarif_text=sarif_text,
                    findings=needs_llm,
                )
                if enriched:
                    for src, est in zip(needs_llm, enriched):
                        if not isinstance(est, dict):
                            continue
                        if "cvss_score" in est and est["cvss_score"] is not None:
                            src["cvss_score"] = est["cvss_score"]
                        if est.get("cvss_vector"):
                            src["cvss_vector"] = est["cvss_vector"]
                        if est.get("cvss_severity"):
                            src["cvss_severity"] = est["cvss_severity"]
                        if est.get("rationale"):
                            src["cvss_rationale"] = est["rationale"]
                        # Re-derive severity band if score updated
                        if "cvss_score" in est:
                            from app.agents.cvss_mapper import (
                                cvss_severity_band,
                            )
                            src["cvss_severity"] = cvss_severity_band(
                                float(est["cvss_score"])
                            )
        except Exception as cvss_exc:
            print(
                f"[analysis] LLM CVSS enrichment failed (non-fatal): "
                f"{cvss_exc}"
            )

    if not _budget_exceeded("graph-phase"):
        try:
            # Re-run coverage_inference if the state has no
            # `security_coverages` yet (legacy callers skip Tahap 2).
            if not state.get("security_coverages"):
                try:
                    from app.agents.nodes.coverage_inference_node import (
                        coverage_inference_node,
                    )
                    state = coverage_inference_node(state)
                    print(
                        f"[analysis] coverage_inference rerun: "
                        f"{len(state.get('security_coverages', []))} coverages, "
                        f"{sum(1 for c in (state.get('security_coverages') or []) if c.get('applicable'))} applicable"
                    )
                except Exception as ce:
                    print(f"[analysis] coverage_inference rerun failed: {ce}")
            state = _invoke_graph_phase(state, [
                "security_analysis",
                "recommendation_generation",
                "response_formatter",
            ])
            state["_current_phase"] = "tahap_4"
        except Exception as e:
            state["errors"].append(str(e))

    # Run workflow compliance validator if we have a generated workflow
    validation_findings = []
    validation_errors = []
    validation_warnings = []
    if generated_yaml:
        try:
            from app.agents.nodes.workflow_validator import workflow_validator_node
            val_state = state.copy()
            val_state["generated_workflow"] = generated_yaml
            val_result = workflow_validator_node(val_state)
            val_findings = val_result.get("validation_findings", [])
            validation_findings = [
                {
                    "type": f.get("type", "warning"),
                    "rule": f.get("rule", "unknown"),
                    "message": f.get("message", ""),
                    "action": f.get("action"),
                    "current_ref": f.get("current_ref"),
                    "job": f.get("job"),
                }
                for f in val_findings
            ]
            validation_errors = val_result.get("validation_errors", [])
            validation_warnings = val_result.get("validation_warnings", [])
        except Exception:
            pass

    dashboard = state.get("dashboard_findings") or _build_dashboard_from_state({
        **state,
        "findings": state.get("findings", []),
        "validation_findings": validation_findings,
        "log_analysis": log_errors,
    })

    # Bab 5.13.3: recompute the dashboard scores from the FINAL
    # findings list (which now includes Code Scanning alerts and
    # LLM-enriched CVSS). We combine `state["findings"]` (log-derived
    # + graph-filtered) with `state["code_scanning_alerts"]`
    # (SARIF-derived) so the risk score reflects every source.
    combined_findings = list(state.get("findings") or [])
    seen_keys: set[tuple[str, str, int | None]] = set()
    for f in combined_findings:
        seen_keys.add((
            f.get("rule_id", ""),
            f.get("file_location", ""),
            f.get("line"),
        ))
    for a in (state.get("code_scanning_alerts") or []):
        key = (a.get("rule_id", ""), a.get("file_location", ""), a.get("line"))
        if key in seen_keys:
            continue
        combined_findings.append(a)
        seen_keys.add(key)
    if combined_findings and (not state.get("risk_score") or state.get("risk_score") == 100.0):
        try:
            from app.agents.cvss_mapper import score_findings
            from app.agents.coverage_library import infer_security_coverage
            score_findings(combined_findings)
            # Tag each finding with its security coverage (Bab 5.13.4)
            # so the compliance score and the FE `security_coverage`
            # badge on each finding have data to render.
            for f in combined_findings:
                if not f.get("security_coverage"):
                    f["security_coverage"] = infer_security_coverage(f)
            cvss_scores = [
                float(f.get("cvss_score") or 0.0)
                for f in combined_findings
                if isinstance(f.get("cvss_score"), (int, float))
            ]
            if cvss_scores:
                avg_cvss = sum(cvss_scores) / len(cvss_scores)
                state["risk_score"] = round(
                    max(0.0, 100.0 - (avg_cvss / 10.0) * 100.0), 1
                )
                # Persist the combined findings so the FE has them
                state["findings"] = combined_findings
                # Severity breakdown (band counts) for the dashboard
                breakdown: dict[str, int] = {}
                for f in combined_findings:
                    band = (f.get("cvss_severity") or "").lower()
                    if band:
                        breakdown[band] = breakdown.get(band, 0) + 1
                state["severity_breakdown"] = breakdown
        except Exception:
            pass

    # Rebuild `summary` so it reflects the final risk_score /
    # compliance / coverage numbers (the response_formatter ran
    # BEFORE the recompute block above and would have produced
    # a stale "100.0/100" string). Without this rebuild the FE
    # sees the dashboard widget (27.8) and the summary text
    # (100.0) disagree.
    if state.get("findings") or state.get("code_scanning_alerts"):
        try:
            issues_count = len(state.get("findings") or [])
            rs = state.get("risk_score")
            cs = state.get("compliance_score")
            scs = state.get("security_coverage_score")
            recs = state.get("recommendations") or []
            parts = []
            if issues_count > 0:
                parts.append(f"Found {issues_count} security issue(s).")
            if rs is not None:
                rl = state.get("risk_level")
                if rl is None:
                    if rs <= 25: rl = "critical"
                    elif rs <= 50: rl = "high"
                    elif rs <= 75: rl = "medium"
                    else: rl = "low"
                parts.append(f"Risk score: {rs}/100 ({rl}).")
            if scs is not None:
                parts.append(f"Security coverage: {scs}%.")
            if cs is not None:
                parts.append(f"Compliance: {cs}%.")
            if recs:
                parts.append(f"Generated {len(recs)} recommendation(s).")
            if parts:
                state["summary"] = " ".join(parts)
        except Exception:
            pass

    # Always recompute compliance + coverage scores (idempotent) so
    # the FE dashboard is consistent even when the graph was
    # bypassed. The compliance score is the share of applicable
    # coverages that resolved to at least one finding; the coverage
    # score is the share of the 15 coverages that the AI agent
    # marked applicable.
    try:
        coverages = state.get("security_coverages") or []
        applicable = sum(1 for c in coverages if c.get("applicable"))
        state["security_coverage_score"] = round(
            (applicable / max(1, len(coverages))) * 100.0, 1
        ) if coverages else 0.0
    except Exception:
        pass
    try:
        coverages = state.get("security_coverages") or []
        applicable_ids = {c.get("id") for c in coverages if c.get("applicable")}
        covered_ids = {
            (f.get("security_coverage") or "")
            for f in (state.get("findings") or [])
        }
        if applicable_ids:
            matched = len(applicable_ids & covered_ids)
            state["compliance_score"] = round(
                (matched / len(applicable_ids)) * 100.0, 1
            )
        else:
            state["compliance_score"] = 0.0
    except Exception:
        pass

    # OWASP Risk Rating: higher score means lower risk.
    risk_score = state.get("risk_score")
    risk_level = state.get("risk_level")
    if risk_level is None and risk_score is not None:
        if risk_score <= 25:
            risk_level = "critical"
        elif risk_score <= 50:
            risk_level = "high"
        elif risk_score <= 75:
            risk_level = "medium"
        else:
            risk_level = "low"

    # `security_posture` is a legacy alias for `risk_score` — kept
    # so older dashboard widgets (and the Go DB column) keep
    # working. The Go column was nullable so any value (or None)
    # is safe to write.
    security_posture = risk_score

    result = {
        "summary": state.get("summary", "Analysis complete."),
        "findings": state.get("findings", []),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "security_posture": security_posture,
        "security_standards_coverage_score": state.get("security_standards_coverage_score"),
        "security_standards_coverage_score_metadata": state.get("security_standards_coverage_score_metadata"),
        "security_standards_coverage_mappings": state.get("security_standards_coverage_mappings", []),
        "compliance_score": state.get("compliance_score"),
        "compliance_score_metadata": state.get("compliance_score_metadata"),
        "compliance_mappings": state.get("compliance_mappings", []),
        "severity_breakdown": state.get("severity_breakdown"),
        "security_coverage_score": state.get("security_coverage_score"),
        "security_coverage_metadata": state.get("security_coverage_metadata"),
        # Reviewer feedback: surface the log-extraction metadata so the
        # user can see *why* the table is empty. If `source` is
        # "conclusions_only", the GitHub logs were not fetched (token
        # scope, expired, or network). If it is "logs" but
        # `security_findings_count` is 0, the log was parsed but
        # matched no heuristic patterns.
        "log_extraction": state.get("log_extraction") or {},
        "skipped_jobs": state.get("skipped_jobs", []),
        # Code Scanning alerts (primary source) - returned to the UI
        # so the RunDetail page can render them directly. These are
        # the SARIF findings uploaded by the GitHub Actions workflow.
        "code_scanning_alerts": state.get("code_scanning_alerts", []),
        "code_scanning_source": "github_api",
        # Tahap 4 per-node I/O log (input summary, output diff,
        # duration, errors). Consumed by RunDetail Tahap 4 cards
        # and the PDF report "Pipeline Execution Trace" section.
        "node_io": state.get("node_io", []),
        # Reviewer feedback: the graph nodes (security_analyzer,
        # risk_assessor) may filter log-derived findings out of
        # `state["findings"]` because they are tagged as
        # `source: "log_heuristic"` and the classifier can be
        # overly strict. Expose the raw log-derived security
        # findings separately so the UI can render them even when
        # the graph says "no findings". These are the findings the
        # AI agent extracted directly from the workflow log.
        "log_security_findings": state.get("log_extraction", {}).get("security_findings") or [],
        "recommendations": state.get("recommendations", []),
        "errors": state.get("errors", []),
        "generated_workflow": generated_yaml or "",
        "validation_findings": validation_findings,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "log_analysis": log_errors,
        "workflow_conclusion": state.get("workflow_conclusion"),
        "dashboard_findings": dashboard,
        "workflow_config_issues": state.get("workflow_config_issues", []),
        "maintenance_warnings": state.get("maintenance_warnings", []),
        "external_service_issues": state.get("external_service_issues", []),
        "remediation_recommendations": state.get("remediation_recommendations", []),
        "workflow_annotations": state.get("workflow_annotations", []),
        "score_metadata": {
            "risk_score": state.get("risk_score_metadata"),
            "compliance_score": state.get("compliance_score_metadata"),
            "security_coverage": state.get("security_coverage_metadata"),
        },
    }

    # Persist is best-effort. The Go backend owns the
    # pipeline_generations / pipeline_runs / pipeline_analyses
    # tables and may not have created the FK target yet for this
    # generation_id. A persist failure MUST NOT break the API
    # response — the FE needs the live findings + CVSS even if
    # the saved-analysis row could not be written.
    try:
        _persist_analysis_result(
            repository_id, result, project_id=project_id, run_id=run_id
        )
    except Exception as persist_exc:
        print(
            f"[persist-analysis] non-fatal failure: {persist_exc}"
        )
    return result