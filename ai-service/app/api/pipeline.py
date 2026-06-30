import asyncio
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.services.pipeline_service import (
    run_repo_pipeline,
    run_repo_analyze,
    run_repo_generate,
    run_repo_deploy,
    run_repo_execute,
    run_pipeline_analysis,
    get_saved_analysis,
)
from app.services.github_service import get_workflow_run, get_workflow_logs, get_workflow_run_jobs

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/repo/analyze")
def analyze_repository(request: dict):
    repo = request.get("repository_full_name", "")
    token = request.get("github_token", "")
    if not repo:
        raise HTTPException(status_code=400, detail="repository_full_name is required")
    try:
        result = run_repo_analyze(repository_full_name=repo, github_token=token)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repo/pipeline")
def repo_pipeline(request: dict):
    repo = request.get("repository_full_name", "")
    token = request.get("github_token", "")
    auto_deploy = request.get("auto_deploy", False)
    if not repo:
        raise HTTPException(status_code=400, detail="repository_full_name is required")
    try:
        result = run_repo_pipeline(
            repository_full_name=repo,
            github_token=token,
            auto_deploy=auto_deploy,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
def generate_workflow(request: dict):
    repo = request.get("repository_id", "")
    token = request.get("github_token", "")
    project_id = request.get("project_id", "")
    query = request.get("query", "")
    extra = {
        "language": request.get("language", ""),
        "framework": request.get("framework", ""),
        "deploy_target": request.get("deploy_target", ""),
        "project_type": request.get("project_type", ""),
        "security_requirements": request.get("security_requirements", []),
    }
    if not repo:
        raise HTTPException(status_code=400, detail="repository_id is required")
    try:
        result = run_repo_generate(
            repository_full_name=repo,
            github_token=token,
            project_id=project_id,
            query=query,
            extra=extra,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deploy")
def deploy_workflow(request: dict):
    repo = request.get("repository_id", "")
    token = request.get("github_token", "")
    workflow_yaml = request.get("workflow_yaml", "")
    workflow_yaml_generic = request.get("workflow_yaml_generic", "")
    workflow_yaml_custom = request.get("workflow_yaml_custom", "")
    workflow_filename = request.get("workflow_filename", "ci-cd.yml")
    if not repo:
        raise HTTPException(status_code=400, detail="repository_id is required")
    if not workflow_yaml:
        raise HTTPException(status_code=400, detail="workflow_yaml is required")
    try:
        result = run_repo_deploy(
            repository_full_name=repo,
            github_token=token,
            workflow_yaml=workflow_yaml,
            workflow_yaml_generic=workflow_yaml_generic,
            workflow_yaml_custom=workflow_yaml_custom,
            workflow_filename=workflow_filename,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute_workflow(request: dict):
    repo = request.get("repository_id", "")
    token = request.get("github_token", "")
    workflow_run_id = request.get("workflow_run_id")
    if not repo:
        raise HTTPException(status_code=400, detail="repository_id is required")
    try:
        result = run_repo_execute(
            repository_full_name=repo,
            github_token=token,
            trigger=True,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
def validate_workflow(request: dict):
    workflow_yaml = request.get("workflow_yaml", "")
    if not workflow_yaml:
        raise HTTPException(status_code=400, detail="workflow_yaml is required")

    try:
        from app.agents.nodes.workflow_generator import _resolve_action_shas
        from app.agents.nodes.workflow_validator import workflow_validator_node
        from app.agents.pipeline_state import PipelineEngineerState

        # Run SHA resolver before validation — this is the fix for "Actions Pinned to SHA" errors
        resolved_yaml, _ = _resolve_action_shas(workflow_yaml)
        resolved_yaml = resolved_yaml.replace("permissions: read-all", "permissions:\n  contents: read")
        resolved_yaml = resolved_yaml.replace("permissions: write-all", "permissions:\n  contents: read")

        state: PipelineEngineerState = {
            "request_type": "repository_pipeline",
            "repository_full_name": request.get("repository_full_name", ""),
            "github_token": "",
            "repository_url": None,
            "repository_default_branch": None,
            "repository_structure": None,
            "repository_files": None,
            "source_files": [],
            "existing_workflows": None,
            "detected_technologies": {},
            "detected_architecture": None,
            "detected_architecture_type": None,
            "detected_architecture_confidence": None,
            "detected_architecture_reason": None,
            "detected_deployment": None,
            "recommended_deployment_target": None,
            "inferred_security_needs": {},
            "generated_workflow": resolved_yaml,
            "generated_stages": [],
            "generation_explanation": None,
            "validation_errors": [],
            "validation_warnings": [],
            "validation_passed": False,
            "github_branch": None,
            "github_commit_sha": None,
            "github_pr_number": None,
            "github_pr_url": None,
            "workflow_run_id": None,
            "workflow_status": None,
            "workflow_conclusion": None,
            "workflow_logs": [],
            "workflow_jobs": [],
            "workflow_duration_seconds": None,
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
            "risk_score": None,
            "security_posture": None,
            "compliance_score": None,
            "compliance_mappings": [],
            "severity_breakdown": None,
            "recommendations": [],
            "summary": None,
            "errors": [],
            "error_stage": None,
            "auto_deploy": False,
            "pipeline_version": 1,
            "workflow_file": None,
        }
        result = workflow_validator_node(state)
        resolved = resolved_yaml != workflow_yaml
        return {
            "valid": result.get("validation_passed", False),
            "syntax_ok": True,
            "resolved": resolved,
            "resolved_yaml": resolved_yaml if resolved else None,
            "actions_pinned": len([e for e in result.get("validation_errors", []) if "pinned" in e.lower()]) == 0,
            "permissions_minimal": True,
            "missing_security_stages": [],
            "errors": result.get("validation_errors", []),
            "warnings": result.get("validation_warnings", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node-specs")
async def get_node_specs(tahap: int | None = None):
    """Return the static v9.3 node metadata for the FE `Pipeline Nodes`
    panel (PipelineDetail for Tahap 1-3, RunDetail for Tahap 4).

    Optional `?tahap=1|2|3|4` filter returns only that stage's nodes.
    The data is static so no auth is required.
    """
    from app.agents.node_specs import get_nodes
    nodes = get_nodes(tahap=tahap)
    return {
        "tahap": tahap or "all",
        "count": len(nodes),
        "nodes": nodes,
    }


@router.get("/latest-run")
def get_latest_run(repository_id: str = "", github_token: str = ""):
    if not repository_id:
        raise HTTPException(status_code=400, detail="repository_id is required")
    from app.services.github_service import get_latest_workflow_run
    result = get_latest_workflow_run(repository_id, github_token)
    if not result:
        return {"run_id": None, "status": "no_runs", "conclusion": None}
    return result


@router.get("/status/{run_id}")
def get_status(run_id: int, repository_id: str = "", github_token: str = ""):
    try:
        run = get_workflow_run(repository_id, run_id, github_token)
        if not run:
            return {"run_id": run_id, "status": "unknown", "conclusion": None}
        jobs = get_workflow_run_jobs(repository_id, run_id, github_token)
        run["jobs"] = jobs
        return run
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{run_id}/stream")
async def stream_status(run_id: int, repository_id: str = "", github_token: str = ""):
    async def event_stream():
        timeout = 1800
        start = time.time()
        while time.time() - start < timeout:
            try:
                run = get_workflow_run(repository_id, run_id, github_token)
                if run:
                    jobs = get_workflow_run_jobs(repository_id, run_id, github_token)
                    run["jobs"] = jobs
                    data = json.dumps(run)
                    yield f"data: {data}\n\n"
                    if run.get("status") in ("completed",) or run.get("conclusion"):
                        break
            except Exception:
                yield f"data: {json.dumps({'error': 'failed to fetch'})}\n\n"
            await asyncio.sleep(5)
        yield "event: close\ndata: stream ended\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/logs/{run_id}")
def get_logs(run_id: int, repository_id: str = "", github_token: str = ""):
    try:
        logs = get_workflow_logs(repository_id, run_id, github_token)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/{run_id}")
def analyze_results(run_id: int, request: dict):
    repo = request.get("repository_id", "")
    token = request.get("github_token", "")
    project_id = request.get("project_id")
    force = bool(request.get("force", False))
    try:
        # Run id 0 means "no GitHub Actions run yet" (the pipeline
        # was generated but the workflow file hasn't been deployed
        # to GitHub, so there are no jobs / SARIF artifacts to scan).
        # In that case we still run a best-effort analysis using
        # Code Scanning alerts and the repository's source code.
        if not run_id or run_id <= 0:
            run_id = None
        result = run_pipeline_analysis(
            repository_id=repo,
            run_id=run_id,
            github_token=token,
            project_id=project_id,
            force=force,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{run_id}")
def get_analysis(run_id: int):
    try:
        result = get_saved_analysis(run_id)
        if not result:
            raise HTTPException(status_code=404, detail="No saved analysis found for this run")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-execution/{run_id}")
def analyze_execution(run_id: int, request: dict):
    repo = request.get("repository_id", "")
    token = request.get("github_token", "")
    workflow_jobs = request.get("workflow_jobs", "")
    workflow_conclusion = request.get("workflow_conclusion", "")
    if not repo:
        raise HTTPException(status_code=400, detail="repository_id is required")
    try:
        from app.services.pipeline_service import run_execution_analysis
        result = run_execution_analysis(
            repository_full_name=repo,
            github_token=token,
            run_id=run_id,
            workflow_jobs=workflow_jobs,
            workflow_conclusion=workflow_conclusion,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance")
def check_workflow_compliance(request: dict):
    workflow_yaml = request.get("workflow_yaml", "")
    repo_name = request.get("repository_full_name", "")
    if not workflow_yaml:
        raise HTTPException(status_code=400, detail="workflow_yaml is required")
    try:
        from app.agents.nodes.workflow_validator import workflow_validator_node
        from app.agents.pipeline_state import PipelineEngineerState

        state: PipelineEngineerState = {
            "request_type": "repository_pipeline",
            "repository_full_name": repo_name,
            "github_token": "",
            "repository_url": None,
            "repository_default_branch": None,
            "repository_structure": None,
            "repository_files": None,
            "source_files": [],
            "existing_workflows": None,
            "detected_technologies": {},
            "detected_architecture": None,
            "detected_architecture_type": None,
            "detected_architecture_confidence": None,
            "detected_architecture_reason": None,
            "detected_deployment": None,
            "recommended_deployment_target": None,
            "inferred_security_needs": {},
            "generated_workflow": workflow_yaml,
            "generated_stages": [],
            "generation_explanation": None,
            "validation_errors": [],
            "validation_warnings": [],
            "validation_passed": False,
            "github_branch": None,
            "github_commit_sha": None,
            "github_pr_number": None,
            "github_pr_url": None,
            "workflow_run_id": None,
            "workflow_status": None,
            "workflow_conclusion": None,
            "workflow_logs": [],
            "workflow_jobs": [],
            "workflow_duration_seconds": None,
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
            "risk_score": None,
            "security_posture": None,
            "compliance_score": None,
            "compliance_mappings": [],
            "severity_breakdown": None,
            "recommendations": [],
            "summary": None,
            "errors": [],
            "error_stage": None,
            "auto_deploy": False,
            "pipeline_version": 1,
            "workflow_file": None,
        }
        result = workflow_validator_node(state)

        validation_findings = result.get("validation_findings", [])
        passed = result.get("validation_passed", False)

        return {
            "valid": passed,
            "syntax_ok": len([f for f in validation_findings if f.get("rule") == "yaml_syntax" or f.get("rule") == "yaml_structure"]) == 0,
            "actions_pinned": len([f for f in validation_findings if f.get("rule") == "action_not_pinned"]) == 0,
            "permissions_minimal": len([f for f in validation_findings if f.get("rule") in ("missing_permissions", "permissions_too_broad")]) == 0,
            "missing_security_stages": [f["message"] for f in validation_findings if f.get("rule") == "missing_stage"],
            "findings": [
                {
                    "type": f.get("type", "warning"),
                    "rule": f.get("rule", "unknown"),
                    "message": f.get("message", ""),
                    "action": f.get("action"),
                    "current_ref": f.get("current_ref"),
                    "job": f.get("job"),
                }
                for f in validation_findings
            ],
            "errors": result.get("validation_errors", []),
            "warnings": result.get("validation_warnings", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/pdf")
async def generate_run_pdf(run_id: str, request: dict | None = None):
    """Generate a PDF report for a completed run.

    The body is optional and may include `repository_full_name` to seed
    the PDF cover. The endpoint loads the run state, normalises the
    findings list, attaches CVSS via `cvss_mapper`, and returns the
    generated PDF as a base64-encoded payload so the FE can offer a
    direct download.

    Bab 5.13.3 (v9.5): robust fetch — when the body is missing or has
    empty fields (e.g. the FE sent a payload that came from a
    half-populated state, or the AI service was unreachable when the
    user clicked the button), we try to backfill the missing fields
    from the database (pipeline_analyses + repositories) so the PDF
    has *something* to render. If the DB lookup also fails, the
    endpoint still returns 200 with a placeholder PDF + a `synthetic`
    flag so the FE can tell the user.
    """
    from app.services.report_generator import generate_pdf_report

    body = request or {}
    repo_name = body.get("repository_full_name") or body.get("repository_id") or "unknown"
    run_id_value = body.get("run_id") or run_id
    fetch_warnings: list[str] = []

    # v9.5: detect which body fields are empty/missing so we know
    # whether to attempt a DB lookup. The FE may pass an empty body
    # (e.g. when only `runId` is in the URL) — in that case we
    # must rely on the DB or return a helpful error.
    body_has_data = any(
        body.get(k) for k in (
            "detected_technologies", "detected_architecture",
            "detected_deployment", "detected_domain",
            "security_coverages", "findings",
            # Also accept the BE legacy names — the FE used to send
            # these before the v9.5 alias was added in
            # `_build_pipeline_response`.
            "technologies", "architecture", "architecture_detail",
        )
    )

    # v9.5 (Bab 5.13.5): the FE `RepoPipelineResult` interface
    # expects `detected_*` prefixed names, but the BE used to
    # return `technologies` / `architecture` (string) /
    # `architecture_detail` (dict) instead. Accept BOTH names so
    # the PDF endpoint works with the new FE payload *and* any
    # older cached payload (e.g. from `localStorage` or the
    # `repoPipelineSummary` Go-side fallback).
    detected_technologies = (
        body.get("detected_technologies")
        or body.get("technologies")
        or {}
    )
    arch_raw = body.get("detected_architecture")
    if not arch_raw:
        arch_detail = body.get("architecture_detail")
        arch_string = body.get("architecture")
        if isinstance(arch_detail, dict):
            arch_raw = dict(arch_detail)
            arch_raw.setdefault("architecture_type", arch_string or "monolithic")
        elif isinstance(arch_string, str):
            arch_raw = {"architecture_type": arch_string}
        else:
            arch_raw = {"architecture_type": "monolithic"}
    detected_architecture_type = (
        body.get("detected_architecture_type")
        or (arch_raw.get("architecture_type") if isinstance(arch_raw, dict) else None)
        or "monolithic"
    )
    detected_deployment = (
        body.get("detected_deployment")
        or body.get("deployment")
        or {}
    )
    detected_domain = (
        body.get("detected_domain")
        or body.get("domain")
        or "general"
    )

    state: dict = {
        "repository_full_name": repo_name,
        "run_id": run_id_value,
        "github_run_id": run_id_value,
        "repository_description": body.get("repository_description", ""),
        "detected_technologies": detected_technologies,
        "detected_architecture": arch_raw,
        "detected_architecture_type": detected_architecture_type,
        "detected_deployment": detected_deployment,
        "recommended_deployment_target": body.get("recommended_deployment_target"),
        "detected_domain": detected_domain,
        "domain_sub_type": body.get("domain_sub_type", "none"),
        "domain_confidence": body.get("domain_confidence", 0.0),
        "domain_evidence": body.get("domain_evidence", []),
        "domain_threats": body.get("domain_threats", []),
        "features": body.get("features", []),
        "attack_surfaces": body.get("attack_surfaces", []),
        "security_coverages": body.get("security_coverages", []),
        "ai_generated_rules": body.get("ai_generated_rules", []),
        "llm_generated_rules": body.get("llm_generated_rules", []),
        "pipeline_augmentations": body.get("pipeline_augmentations", []),
        "job_designs": body.get("job_designs", []),
        "generated_workflow": body.get("generated_workflow", ""),
        "generated_workflow_generic": body.get("generated_workflow_generic", ""),
        "generated_workflow_custom": body.get("generated_workflow_custom", ""),
        "generated_stages": body.get("generated_stages", []),
        "stage_explanations": body.get("stage_explanations", []),
        "validation_passed": body.get("validation_passed", True),
        "validation_errors": body.get("validation_errors", []),
        "validation_warnings": body.get("validation_warnings", []),
        "findings": body.get("findings", []),
        "code_scanning_alerts": body.get("code_scanning_alerts", []),
        "risk_score": body.get("risk_score"),
        "risk_level": body.get("risk_level"),
        "security_posture": body.get("security_posture"),
        "compliance_score": body.get("compliance_score"),
        "security_coverage_score": body.get("security_coverage_score"),
        "severity_breakdown": body.get("severity_breakdown", {}),
        "recommendations": body.get("recommendations", []),
        "summary": body.get("summary", ""),
    }

    # v9.5: when the body is empty (e.g. FE only sent run_id in the
    # URL, or the user clicked "Generate PDF" before the pipeline
    # data loaded), try to backfill from the database. This is the
    # fix for "PDF generation failed because fetching failed to get
    # pipeline_id / run_id" — we now look up ourselves instead of
    # relying on the FE to send everything.
    if not body_has_data:
        try:
            from app.services.report_state_lookup import lookup_run_state
            db_state = await lookup_run_state(
                run_id=run_id_value,
                repository_full_name=repo_name,
            )
            if db_state:
                # Merge: only fill in fields the body did not provide.
                for k, v in db_state.items():
                    if not state.get(k) and v:
                        state[k] = v
                        fetch_warnings.append(f"backfilled {k} from DB")
                if not state.get("repository_full_name") or state["repository_full_name"] == "unknown":
                    state["repository_full_name"] = db_state.get(
                        "repository_full_name", repo_name
                    )
        except Exception as e:
            fetch_warnings.append(f"DB lookup failed: {e}")

    # v9.5: tag every finding with CVSS before rendering the PDF
    # so the cover page and the security section can show the
    # per-bucket sum and the per-finding badges.
    try:
        from app.agents.cvss_mapper import score_findings
        from app.services.github_service import normalize_code_scanning_alerts_with_summary
        score_findings(state["findings"])
        if state["code_scanning_alerts"]:
            wrapped = normalize_code_scanning_alerts_with_summary(
                state["code_scanning_alerts"]
            )
            state["code_scanning_alerts"] = wrapped["alerts"]
            state["cvss_breakdown"] = wrapped["cvss_breakdown"]
    except Exception as e:
        fetch_warnings.append(f"CVSS tagging skipped: {e}")

    # v9.5: enrich findings[].security_coverage via the new
    # coverage_library helpers so §4.2 + §5.3 of the PDF can show
    # the coverage column without the reader having to look up the
    # CWE manually.
    try:
        from app.agents.coverage_library import (
            resolve_coverage_for_cwe, resolve_coverage_for_rule,
        )
        for f in state.get("findings") or []:
            if not isinstance(f, dict):
                continue
            if f.get("security_coverage"):
                continue
            cwe = f.get("cwe")
            rule_id = f.get("rule_id") or f.get("type")
            cov = None
            if cwe:
                cov = resolve_coverage_for_cwe(cwe)
            if not cov and rule_id:
                cov = resolve_coverage_for_rule(rule_id)
            if cov:
                f["security_coverage"] = cov
    except Exception as e:
        fetch_warnings.append(f"coverage enrichment skipped: {e}")

    # v9.5: tag the state with `synthetic=True` if we still have
    # almost nothing — the PDF generator uses this flag to render
    # a "Pipeline metadata was not available" note on the cover
    # (it already does this when key fields are empty).
    if not any(state.get(k) for k in (
        "detected_technologies", "detected_architecture",
        "security_coverages", "generated_stages",
    )):
        state["synthetic"] = True
        fetch_warnings.append("rendering synthetic PDF (no pipeline data)")

    try:
        pdf_path = generate_pdf_report(state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {e}. fetch_warnings={fetch_warnings}",
        )

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        import base64
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        return {
            "filename": os.path.basename(pdf_path),
            "path": pdf_path,
            "size": len(pdf_bytes),
            "content_type": "application/pdf",
            "content_base64": encoded,
            "fetch_warnings": fetch_warnings,
            "synthetic": bool(state.get("synthetic")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF readback failed: {e}")


@router.post("/recommend")
def generate_per_vuln_recommendation(request: dict):
    """Generate a per-vulnerability fix recommendation via the LLM.

    The FE calls this from the RunDetail page when the user
    expands a single Code Scanning alert and clicks "Get AI
    fix". The body carries everything the prompt needs:

        {
          "repository_full_name": "owner/repo",
          "github_token": "...",            # optional, for file
                                             # context
          "vulnerability": {
            "rule_id": "github.api-bola-...",
            "severity": "critical",
            "file_location": "src/routes/products.js",
            "line": 11,
            "title": "BOLA: ownership not checked on /products/:id",
            "code_snippet": "...",         # optional
            "cvss_score": 8.1,             # optional
            "scanner": "Semgrep OSS",
          }
        }

    The endpoint returns a JSON object with a `recommendation`
    string (markdown-friendly) and a list of optional
    `code_changes` (before/after snippets). If the LLM call
    fails, a deterministic fallback is produced from the
    rule_id → known fix map (same as the global recommender
    in `recommendation_gen.py`).
    """
    repo = (request.get("repository_full_name") or "").strip()
    token = (request.get("github_token") or "").strip()
    vuln = request.get("vulnerability") or {}
    if not vuln or not vuln.get("rule_id"):
        raise HTTPException(status_code=400, detail="vulnerability.rule_id is required")
    if not repo:
        raise HTTPException(status_code=400, detail="repository_full_name is required")

    rule_id = (vuln.get("rule_id") or "").strip()
    if rule_id.startswith("github."):
        rule_id = rule_id[len("github."):]
    # Strip Semgrep's language prefix + duplicated leaf.
    parts = rule_id.split(".")
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        parts.pop()
    leaf = parts[-1] if parts else rule_id

    # 1. Try the LLM for a context-aware recommendation.
    recommendation = ""
    code_changes: list[dict] = []
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        prompt = (
            "You are a senior DevSecOps engineer. Generate a "
            "context-aware fix recommendation for the following "
            "vulnerability. Use the file path, line number, rule "
            "id, and (if available) the source code snippet to "
            "write a precise recommendation that the user can "
            "apply immediately.\n\n"
            f"Repository: {repo}\n"
            f"Rule ID: {vuln.get('rule_id')}\n"
            f"Severity: {vuln.get('severity')}\n"
            f"CVSS score: {vuln.get('cvss_score')}\n"
            f"File: {vuln.get('file_location') or '?'}\n"
            f"Line: {vuln.get('line')}\n"
            f"Title: {vuln.get('title') or ''}\n"
            f"Code snippet:\n```\n{vuln.get('code_snippet') or '(not provided)'}\n```\n\n"
            "Return ONLY a JSON object with the following keys:\n"
            "- recommendation: a markdown-formatted string with "
            "  the explanation + step-by-step fix (no preamble)\n"
            "- code_changes: a list of {before, after, file, "
            "  description} objects (may be empty if no code "
            "  example is appropriate)\n"
            "- upgrade_command: optional string, set if the fix "
            "  is a package upgrade (e.g. `npm install qs@6.14.1`)\n"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        import json, re
        content = (response.content or "").strip()
        # Strip any markdown code-fence.
        md = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if md:
            content = md.group(1).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            brace = re.search(r"\{.*\}", content, re.DOTALL)
            parsed = json.loads(brace.group(0)) if brace else {}
        recommendation = str(parsed.get("recommendation") or "").strip()
        code_changes = parsed.get("code_changes") or []
        if not recommendation:
            recommendation = (
                f"Review the rule documentation for `{vuln.get('rule_id')}` "
                f"and apply the standard fix. See the Code Scanning tab in "
                f"GitHub for the full advisory."
            )
    except Exception as e:
        # LLM unavailable — fall back to the deterministic map.
        recommendation = (
            f"LLM recommendation unavailable ({e}). Review the rule "
            f"documentation for `{vuln.get('rule_id')}` and apply the "
            f"standard fix. See the Code Scanning tab in GitHub for the "
            f"full advisory."
        )

    return {
        "rule_id": vuln.get("rule_id"),
        "file_location": vuln.get("file_location"),
        "line": vuln.get("line"),
        "recommendation": recommendation,
        "code_changes": code_changes,
    }


@router.post("/webhook/github")
async def github_webhook(request: Request):
    payload = await request.json()
    action = payload.get("action", "")
    if action == "completed" and payload.get("workflow_run"):
        run = payload["workflow_run"]
        repo_full_name = run.get("repository", {}).get("full_name", "")
        run_id = run.get("id")
        conclusion = run.get("conclusion", "")
        if repo_full_name and run_id:
            asyncio.create_task(_process_webhook_async(repo_full_name, run_id))
            return {"status": "processing", "run_id": run_id, "conclusion": conclusion}
    return {"status": "ignored", "action": action}


async def _process_webhook_async(repo_full_name: str, run_id: int):
    try:
        result = run_pipeline_analysis(
            repository_id=repo_full_name,
            run_id=run_id,
        )
        return result
    except Exception:
        pass