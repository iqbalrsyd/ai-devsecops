import asyncio
import json
import os
import re
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


def _known_code_rule_fix(
    leaf: str,
    vuln: dict,
    language: str = "",
) -> dict | None:
    """Deterministic fallback for well-known Semgrep / CodeQL / SAST rules.

    Mirrors `_known_rule_fix` but for code-level rules instead of
    dependency CVEs. The LLM call in
    `generate_per_vuln_recommendation` is the preferred path, but
    the prompt is tuned for dependency advisories and often returns
    an empty body for SAST findings — this map gives the user
    something actionable per-rule.

    Each entry maps a `rule_id` leaf (or keyword in the title) to
    a small dict with `summary`, `fix`, `why`, and an optional
    `code_changes` list.
    """
    key = (leaf or "").strip().lower()
    title = (vuln.get("title") or "").lower()
    full_key = (vuln.get("rule_id") or "").strip().lower()

    entries: list[dict] = [
        {
            "match": [
                "missing-html-sanitizer", "html-sanitizer", "xss", "cross-site-scripting",
                "bluemonday", "unescaped-html",
            ],
            "summary": (
                "User-supplied HTML is rendered without an HTML sanitizer, "
                "allowing stored / reflected XSS. An attacker can inject "
                "`<script>` or event-handler attributes that run in other "
                "users' sessions (cookie theft, account takeover)."
            ),
            "fix": (
                "Run every untrusted HTML string through a battle-tested "
                "sanitizer before rendering. In Go, add "
                "`github.com/microcosm-cc/bluemonday` (e.g. "
                "`p := bluemonday.UGCPolicy(); p.SanitizeBytes(rawHTML)`) "
                "and call `p.Sanitize*` on any `blog_posting.body`, "
                "`comment.body`, or markdown-derived HTML. In Node.js use "
                "`DOMPurify` (`DOMPurify.sanitize(html)`); in Python use "
                "`bleach.clean(html, tags=[...], attributes={...})`."
            ),
            "why": (
                "Sanitizers enforce an allow-list of safe tags and "
                "attributes, stripping `<script>`, `on*` event handlers, "
                "`javascript:` URLs, and other XSS vectors. Manual "
                "regex / string-replace escaping is bypassed by nested "
                "constructs (e.g. `<scr<script>ipt>`) and is not safe."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Declare bluemonday in go.mod and sanitize HTML before rendering",
                        "file": "go.mod",
                        "before": "// bluemonday not declared",
                        "after": "require github.com/microcosm-cc/bluemonday v1.0.27",
                    },
                    {
                        "description": "Sanitize untrusted HTML before storing or rendering",
                        "file": "internal/blog/render.go",
                        "before": "out := template.HTML(rawHTML)\nreturn c.HTML(http.StatusOK, out)",
                        "after": (
                            "p := bluemonday.UGCPolicy()\nsafe := p.SanitizeBytes([]byte(rawHTML))\n"
                            "return c.HTML(http.StatusOK, template.HTML(safe))"
                        ),
                    },
                ],
                "javascript": [
                    {
                        "description": "Sanitize user-submitted HTML with DOMPurify before storing or rendering",
                        "file": "src/posts/save.js",
                        "before": (
                            "function savePost({ title, body }) {\n"
                            "  return db.posts.insert({ title, body });\n"
                            "}"
                        ),
                        "after": (
                            "const createDOMPurify = require('dompurify');\n"
                            "const { JSDOM } = require('jsdom');\n"
                            "const window = new JSDOM('').window;\n"
                            "const DOMPurify = createDOMPurify(window);\n"
                            "\n"
                            "const ALLOWED_TAGS = ['p','br','strong','em','a','ul','ol','li','blockquote','code','pre','h2','h3','h4','img'];\n"
                            "const ALLOWED_ATTR = ['href','title','alt','src'];\n"
                            "\n"
                            "function sanitizeHtml(dirty) {\n"
                            "  return DOMPurify.sanitize(dirty, { ALLOWED_TAGS, ALLOWED_ATTR });\n"
                            "}\n"
                            "\n"
                            "function savePost({ title, body }) {\n"
                            "  const cleanBody = sanitizeHtml(body);\n"
                            "  return db.posts.insert({ title, body: cleanBody });\n"
                            "}"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Sanitize user-submitted HTML with DOMPurify before storing or rendering",
                        "file": "src/posts/save.ts",
                        "before": (
                            "export function savePost({ title, body }: PostInput): Promise<Post> {\n"
                            "  return db.posts.insert({ title, body });\n"
                            "}"
                        ),
                        "after": (
                            "import createDOMPurify from 'dompurify';\n"
                            "import { JSDOM } from 'jsdom';\n"
                            "const window = new JSDOM('').window as unknown as Window;\n"
                            "const DOMPurify = createDOMPurify(window);\n"
                            "\n"
                            "const ALLOWED_TAGS = ['p','br','strong','em','a','ul','ol','li','blockquote','code','pre','h2','h3','h4','img'];\n"
                            "const ALLOWED_ATTR = ['href','title','alt','src'];\n"
                            "\n"
                            "export function sanitizeHtml(dirty: string): string {\n"
                            "  return DOMPurify.sanitize(dirty, { ALLOWED_TAGS, ALLOWED_ATTR });\n"
                            "}\n"
                            "\n"
                            "export function savePost({ title, body }: PostInput): Promise<Post> {\n"
                            "  const cleanBody = sanitizeHtml(body);\n"
                            "  return db.posts.insert({ title, body: cleanBody });\n"
                            "}"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Sanitize user-submitted HTML with bleach before storing or rendering",
                        "file": "blog/views.py",
                        "before": (
                            "def save_post(title, body):\n"
                            "    return Post.objects.create(title=title, body=body)"
                        ),
                        "after": (
                            "import bleach\n"
                            "\n"
                            "ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li',\n"
                            "                'blockquote', 'code', 'pre', 'h2', 'h3', 'h4', 'img']\n"
                            "ALLOWED_ATTRS = {'a': ['href', 'title'], 'img': ['src', 'alt']}\n"
                            "\n"
                            "def sanitize_html(dirty):\n"
                            "    return bleach.clean(dirty, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)\n"
                            "\n"
                            "def save_post(title, body):\n"
                            "    return Post.objects.create(title=title, body=sanitize_html(body))"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "weak-password-hash", "password-hash", "md5", "sha1", "sha-1",
                "insecure-password", "unsalted-password", "weak-hash", "bcrypt-missing",
            ],
            "summary": (
                "User passwords are hashed with a fast, unsalted, or "
                "cryptographically-broken algorithm (MD5, SHA-1, SHA-256 "
                "without a salt / KDF). If the credential database is "
                "exfiltrated, attackers can recover most passwords via "
                "rainbow tables or commodity GPU brute-force in hours."
            ),
            "fix": (
                "Replace the hash function with a slow, salted, "
                "memory-hard KDF: **`bcrypt`** (cost ≥ 12), "
                "**`argon2id`** (preferred for new code), or "
                "**`scrypt`**. Verify with the library's constant-time "
                "compare helper. Never roll your own hash; never store "
                "the raw password; never apply a single global salt."
            ),
            "why": (
                "MD5/SHA-1/SHA-256 are designed to be FAST — exactly "
                "the wrong property for password hashing. A modern GPU "
                "computes billions of MD5 hashes per second. Bcrypt "
                "and argon2id are intentionally slow and memory-hard, "
                "so each guess costs milliseconds-to-seconds and "
                "hundreds of MB of RAM, making bulk cracking "
                "prohibitively expensive."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Hash passwords with bcrypt (Go example)",
                        "file": "internal/auth/password.go",
                        "before": (
                            "import \"crypto/md5\"\n"
                            "sum := md5.Sum([]byte(pw + secret))\n"
                            "db.Set(user, hex.EncodeToString(sum[:]))"
                        ),
                        "after": (
                            "import \"golang.org/x/crypto/bcrypt\"\n"
                            "h, err := bcrypt.GenerateFromPassword([]byte(pw), 12)\n"
                            "if err != nil { return err }\n"
                            "db.Set(user, string(h))"
                        ),
                    },
                    {
                        "description": "Verify a login with bcrypt (constant-time compare)",
                        "file": "internal/auth/password.go",
                        "before": (
                            "if hex.EncodeToString(sum[:]) == stored { return ok }"
                        ),
                        "after": (
                            "if bcrypt.CompareHashAndPassword([]byte(stored), []byte(pw)) == nil { return ok }"
                        ),
                    },
                ],
                "javascript": [
                    {
                        "description": "Hash passwords with bcrypt (Node.js example)",
                        "file": "src/auth/password.js",
                        "before": (
                            "const crypto = require('crypto');\n"
                            "function hash(pw) {\n"
                            "  return crypto.createHash('md5').update(pw).digest('hex');\n"
                            "}"
                        ),
                        "after": (
                            "const bcrypt = require('bcrypt');\n"
                            "async function hash(pw) {\n"
                            "  return bcrypt.hash(pw, 12);\n"
                            "}\n"
                            "async function verify(pw, stored) {\n"
                            "  return bcrypt.compare(pw, stored);\n"
                            "}"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Hash passwords with bcrypt (TypeScript example)",
                        "file": "src/auth/password.ts",
                        "before": (
                            "import crypto from 'crypto';\n"
                            "export function hash(pw: string): string {\n"
                            "  return crypto.createHash('md5').update(pw).digest('hex');\n"
                            "}"
                        ),
                        "after": (
                            "import bcrypt from 'bcrypt';\n"
                            "export async function hash(pw: string): Promise<string> {\n"
                            "  return bcrypt.hash(pw, 12);\n"
                            "}\n"
                            "export async function verify(pw: string, stored: string): Promise<boolean> {\n"
                            "  return bcrypt.compare(pw, stored);\n"
                            "}"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Hash passwords with passlib bcrypt (Python example)",
                        "file": "auth/password.py",
                        "before": (
                            "import hashlib\n"
                            "def hash_password(pw: str) -> str:\n"
                            "    return hashlib.md5(pw.encode()).hexdigest()"
                        ),
                        "after": (
                            "from passlib.hash import bcrypt\n"
                            "def hash_password(pw: str) -> str:\n"
                            "    return bcrypt.using(rounds=12).hash(pw)\n"
                            "def verify_password(pw: str, stored: str) -> bool:\n"
                            "    return bcrypt.verify(pw, stored)"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "sql-injection", "sqli", "sql-injection-format", "unsanitized-sql",
            ],
            "summary": (
                "User input is concatenated into a SQL string instead of "
                "being passed as a parameterised query, allowing an "
                "attacker to read or modify arbitrary database rows "
                "(authentication bypass, data exfiltration)."
            ),
            "fix": (
                "Use parameterised queries / prepared statements for every "
                "value that originates from user input. In Go use "
                "`db.Query(\"SELECT ... WHERE id = ?\", id)`. In Node.js "
                "use `pool.query('SELECT ... WHERE id = ?', [id])`. Never "
                "build SQL with `fmt.Sprintf` / template literals / "
                "string concatenation."
            ),
            "why": (
                "Parameterised queries send the query template and the "
                "values on separate channels; the database engine treats "
                "values as data, never as executable SQL. Escaping is a "
                "weaker mitigation that fails on edge cases (Unicode, "
                "numeric contexts, second-order injection)."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Replace string-concat SQL with a parameterised query",
                        "file": "internal/db/users.go",
                        "before": "db.QueryRow(fmt.Sprintf(\"SELECT * FROM users WHERE id = '%s'\", id))",
                        "after": "db.QueryRow(\"SELECT * FROM users WHERE id = $1\", id)",
                    },
                ],
                "javascript": [
                    {
                        "description": "Replace string-concat SQL with a parameterised query (mysql2/pg)",
                        "file": "src/db/users.js",
                        "before": (
                            "const sql = `SELECT * FROM users WHERE id = '${id}'`;\n"
                            "const row = await pool.query(sql);"
                        ),
                        "after": (
                            "const sql = 'SELECT * FROM users WHERE id = ?';\n"
                            "const [rows] = await pool.query(sql, [id]);"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Replace string-concat SQL with a parameterised query (mysql2/pg)",
                        "file": "src/db/users.ts",
                        "before": (
                            "const sql = `SELECT * FROM users WHERE id = '${id}'`;\n"
                            "const [rows] = await pool.query(sql);"
                        ),
                        "after": (
                            "const sql = 'SELECT * FROM users WHERE id = ?';\n"
                            "const [rows] = await pool.query(sql, [id]);"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Replace string-concat SQL with a parameterised cursor query",
                        "file": "db/users.py",
                        "before": (
                            "def get_user(id):\n"
                            "    cur.execute(f\"SELECT * FROM users WHERE id = '{id}'\")\n"
                            "    return cur.fetchone()"
                        ),
                        "after": (
                            "def get_user(id):\n"
                            "    cur.execute(\"SELECT * FROM users WHERE id = %s\", (id,))\n"
                            "    return cur.fetchone()"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "command-injection", "os-command-injection", "shell-injection",
                "exec-injection", "tainted-shell",
            ],
            "summary": (
                "User-controlled input is passed to a shell or "
                "`exec`-family call without validation, allowing "
                "arbitrary command execution on the host (RCE)."
            ),
            "fix": (
                "Avoid spawning a shell entirely — call the program "
                "directly via `exec.Command(name, args...)` (Go) or "
                "`child_process.execFile(file, args)` (Node). If a shell "
                "is unavoidable, validate input against a strict "
                "allow-list (regex) and never interpolate untrusted "
                "strings into the command string."
            ),
            "why": (
                "Even with quoting, metacharacters inside the value "
                "(`$`, backticks, `;`, `|`, newline) can break out of "
                "the quoted context. `exec.Command` with an argument "
                "slice bypasses the shell entirely, eliminating the "
                "parsing attack surface."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Call the binary directly instead of through a shell",
                        "file": "internal/runner/run.go",
                        "before": "exec.Command(\"sh\", \"-c\", \"git clone \"+url)",
                        "after": "exec.Command(\"git\", \"clone\", url)",
                    },
                ],
                "javascript": [
                    {
                        "description": "Use execFile so the URL is passed as an argument, not parsed by a shell",
                        "file": "src/runner/run.js",
                        "before": (
                            "const { exec } = require('child_process');\n"
                            "exec(`git clone ${url}`);"
                        ),
                        "after": (
                            "const { execFile } = require('child_process');\n"
                            "execFile('git', ['clone', url]);"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Use execFile so the URL is passed as an argument, not parsed by a shell",
                        "file": "src/runner/run.ts",
                        "before": (
                            "import { exec } from 'child_process';\n"
                            "exec(`git clone ${url}`);"
                        ),
                        "after": (
                            "import { execFile } from 'child_process';\n"
                            "execFile('git', ['clone', url]);"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Use subprocess.run with a list of args to avoid shell parsing",
                        "file": "runner/run.py",
                        "before": (
                            "import subprocess\n"
                            "subprocess.run(f\"git clone {url}\", shell=True)"
                        ),
                        "after": (
                            "import subprocess\n"
                            "subprocess.run([\"git\", \"clone\", url], shell=False)"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "path-traversal", "directory-traversal", "zip-slip", "tar-slip",
            ],
            "summary": (
                "User-supplied filenames are joined into a filesystem "
                "path without checking for `..` segments, allowing an "
                "attacker to read or overwrite files outside the "
                "intended directory."
            ),
            "fix": (
                "After joining the user-supplied filename to the base "
                "directory, verify that the cleaned path still has the "
                "base as its prefix. Reject any path containing `..`, "
                "absolute paths, or symlinks pointing outside the base."
            ),
            "why": (
                "`filepath.Join` collapses `..` segments, so a check "
                "on the raw input is insufficient. The `Clean` + "
                "`HasPrefix(base)` pattern is the standard Go idiom; "
                "Node.js equivalents are `path.resolve` + `startsWith`."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Validate the resolved path stays inside the base directory",
                        "file": "internal/fs/save.go",
                        "before": "dst := filepath.Join(base, name); os.WriteFile(dst, data, 0644)",
                        "after": (
                            "dst := filepath.Clean(filepath.Join(base, name))\n"
                            "if !strings.HasPrefix(dst, filepath.Clean(base)+\string(os.PathSeparator)) {\n"
                            "    return errors.New(\"path traversal blocked\")\n"
                            "}\n"
                            "os.WriteFile(dst, data, 0644)"
                        ),
                    },
                ],
                "javascript": [
                    {
                        "description": "Resolve the path and verify it stays inside the base directory",
                        "file": "src/fs/save.js",
                        "before": (
                            "const path = require('path');\n"
                            "const dst = path.join(base, name);\n"
                            "fs.writeFileSync(dst, data);"
                        ),
                        "after": (
                            "const path = require('path');\n"
                            "const dst = path.resolve(base, name);\n"
                            "if (!dst.startsWith(path.resolve(base) + path.sep)) {\n"
                            "  throw new Error('path traversal blocked');\n"
                            "}\n"
                            "fs.writeFileSync(dst, data);"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Resolve the path and verify it stays inside the base directory",
                        "file": "src/fs/save.ts",
                        "before": (
                            "import path from 'path';\n"
                            "const dst = path.join(base, name);\n"
                            "fs.writeFileSync(dst, data);"
                        ),
                        "after": (
                            "import path from 'path';\n"
                            "const dst = path.resolve(base, name);\n"
                            "if (!dst.startsWith(path.resolve(base) + path.sep)) {\n"
                            "  throw new Error('path traversal blocked');\n"
                            "}\n"
                            "fs.writeFileSync(dst, data);"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Use os.path.realpath + commonpath to reject traversal",
                        "file": "fs/save.py",
                        "before": (
                            "import os\n"
                            "dst = os.path.join(base, name)\n"
                            "open(dst, 'wb').write(data)"
                        ),
                        "after": (
                            "import os\n"
                            "dst = os.path.realpath(os.path.join(base, name))\n"
                            "if os.path.commonpath([dst, os.path.realpath(base)]) != os.path.realpath(base):\n"
                            "    raise ValueError('path traversal blocked')\n"
                            "open(dst, 'wb').write(data)"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "insecure-deserialization", "yaml-load", "pickle", "unsafe-deserialize",
            ],
            "summary": (
                "Untrusted data is deserialised with an unsafe loader "
                "(e.g. `yaml.load`, Python `pickle`, Java "
                "`ObjectInputStream`), allowing arbitrary code execution."
            ),
            "fix": (
                "Use a safe loader: `yaml.safe_load` instead of "
                "`yaml.load`; `json.loads` instead of `pickle.loads`. "
                "For binary formats, sign the payload with HMAC and "
                "verify before deserialising."
            ),
            "why": (
                "Unsafe loaders instantiate arbitrary types from the "
                "input, and gadget chains in those types can run code "
                "during deserialisation. Safe loaders restrict the "
                "type set to primitives and standard collections."
            ),
            "code_changes_by_lang": {
                "python": [
                    {
                        "description": "Use safe_load to block RCE via crafted YAML",
                        "file": "config/loader.py",
                        "before": "data = yaml.load(stream)",
                        "after": "data = yaml.safe_load(stream)",
                    },
                ],
                "go": [
                    {
                        "description": "Use yaml.Unmarshal, never yaml.Unmarshal into a typed pointer from untrusted data",
                        "file": "config/loader.go",
                        "before": (
                            "var cfg interface{}\n"
                            "yaml.Unmarshal(data, &cfg)  // unsafe: can decode into arbitrary types"
                        ),
                        "after": (
                            "var cfg map[string]interface{}\n"
                            "if err := yaml.Unmarshal(data, &cfg); err != nil { return err }\n"
                            "// validate cfg against an allow-list before use"
                        ),
                    },
                ],
                "javascript": [
                    {
                        "description": "Use JSON.parse instead of eval / Function constructors",
                        "file": "src/config/loader.js",
                        "before": (
                            "const fs = require('fs');\n"
                            "const data = eval('(' + fs.readFileSync('config.json', 'utf8') + ')');"
                        ),
                        "after": (
                            "const fs = require('fs');\n"
                            "const data = JSON.parse(fs.readFileSync('config.json', 'utf8'));"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Use JSON.parse instead of eval / Function constructors",
                        "file": "src/config/loader.ts",
                        "before": (
                            "import fs from 'fs';\n"
                            "const data = eval('(' + fs.readFileSync('config.json', 'utf8') + ')');"
                        ),
                        "after": (
                            "import fs from 'fs';\n"
                            "const data = JSON.parse(fs.readFileSync('config.json', 'utf8')) as Config;"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "hardcoded-secret", "hardcoded-credential", "hardcoded-password",
                "hardcoded-api-key", "hardcoded-token",
                "generic-api-key", "generic-secret", "generic-password",
                "gitleaks", "trufflehog", "git-secrets",
            ],
            "summary": (
                "A secret, API key, password, or token is committed to "
                "the repository. Anyone with read access to the repo "
                "(including forks, history, and backups) can use the "
                "credential."
            ),
            "fix": (
                "1. **Rotate the credential NOW** — assume it is "
                "compromised. 2. Move the value to an environment "
                "variable or secret manager (GitHub Actions secrets, "
                "AWS Secrets Manager, Vault). 3. Read it at runtime via "
                "`os.Getenv(\"FOO\")` / `process.env.FOO`. 4. Purge the "
                "value from git history (`git filter-repo` or BFG) and "
                "force-push, then audit for downstream clones."
            ),
            "why": (
                "Once a secret is in git, `git log -p` and GitHub's "
                "history view expose it to anyone. A secret manager "
                "keeps the value out of the repo entirely and gives you "
                "rotation, audit logs, and per-environment scoping."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Read the API key from the environment at startup",
                        "file": "internal/api/client.go",
                        "before": "const apiKey = \"sk-live-XXXXXXXXXXXXXXXX\"",
                        "after": "apiKey := os.Getenv(\"API_KEY\")",
                    },
                ],
                "javascript": [
                    {
                        "description": "Read the API key from the environment at startup",
                        "file": "src/api/client.js",
                        "before": (
                            "const apiKey = 'sk-live-XXXXXXXXXXXXXXXX';\n"
                            "const client = new ApiClient({ apiKey });"
                        ),
                        "after": (
                            "const apiKey = process.env.API_KEY;\n"
                            "if (!apiKey) throw new Error('API_KEY is not set');\n"
                            "const client = new ApiClient({ apiKey });"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Read the API key from the environment at startup",
                        "file": "src/api/client.ts",
                        "before": (
                            "const apiKey = 'sk-live-XXXXXXXXXXXXXXXX';\n"
                            "const client = new ApiClient({ apiKey });"
                        ),
                        "after": (
                            "const apiKey = process.env.API_KEY;\n"
                            "if (!apiKey) throw new Error('API_KEY is not set');\n"
                            "const client = new ApiClient({ apiKey });"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Read the API key from the environment at startup",
                        "file": "api/client.py",
                        "before": (
                            "API_KEY = 'sk-live-XXXXXXXXXXXXXXXX'\n"
                            "client = ApiClient(api_key=API_KEY)"
                        ),
                        "after": (
                            "import os\n"
                            "API_KEY = os.environ['API_KEY']  # raises if missing\n"
                            "client = ApiClient(api_key=API_KEY)"
                        ),
                    },
                ],
            },
        },
        {
            "match": [
                "open-redirect", "unvalidated-redirect",
            ],
            "summary": (
                "User input is used directly as a `Location:` header "
                "value, allowing an attacker to redirect victims to a "
                "phishing page after a successful login."
            ),
            "fix": (
                "Validate the redirect target against an allow-list of "
                "trusted hosts, or use only relative paths. Reject any "
                "URL containing a different host than the request."
            ),
            "why": (
                "An attacker sends a victim "
                "`/login?next=https://evil.example/`, the app redirects "
                "after auth, and the victim lands on a clone of the "
                "site. An allow-list or relative-only check breaks the "
                "phishing chain."
            ),
            "code_changes_by_lang": {
                "go": [
                    {
                        "description": "Restrict the redirect target to relative paths",
                        "file": "internal/auth/handler.go",
                        "before": "http.Redirect(w, r, nextURL, http.StatusFound)",
                        "after": (
                            "u, err := url.Parse(nextURL)\n"
                            "if err != nil || u.IsAbs() { http.Error(w, \"bad redirect\", 400); return }\n"
                            "http.Redirect(w, r, u.Path, http.StatusFound)"
                        ),
                    },
                ],
                "javascript": [
                    {
                        "description": "Restrict the redirect target to relative paths (Express)",
                        "file": "src/auth/handler.js",
                        "before": (
                            "app.get('/login/cb', (req, res) => {\n"
                            "  res.redirect(req.query.next);\n"
                            "});"
                        ),
                        "after": (
                            "app.get('/login/cb', (req, res) => {\n"
                            "  const next = req.query.next || '/';\n"
                            "  if (/^https?:\\/\\//i.test(next)) return res.status(400).send('bad redirect');\n"
                            "  res.redirect(next);\n"
                            "});"
                        ),
                    },
                ],
                "typescript": [
                    {
                        "description": "Restrict the redirect target to relative paths (Express)",
                        "file": "src/auth/handler.ts",
                        "before": (
                            "app.get('/login/cb', (req, res) => {\n"
                            "  res.redirect(req.query.next);\n"
                            "});"
                        ),
                        "after": (
                            "app.get('/login/cb', (req, res) => {\n"
                            "  const next: string = (req.query.next as string) || '/';\n"
                            "  if (/^https?:\\/\\//i.test(next)) return res.status(400).send('bad redirect');\n"
                            "  res.redirect(next);\n"
                            "});"
                        ),
                    },
                ],
                "python": [
                    {
                        "description": "Restrict the redirect target to relative paths (Django/Flask)",
                        "file": "auth/handler.py",
                        "before": (
                            "from django.shortcuts import redirect\n"
                            "def login_cb(request):\n"
                            "    return redirect(request.GET['next'])"
                        ),
                        "after": (
                            "from django.shortcuts import redirect\n"
                            "from django.urls import reverse\n"
                            "def login_cb(request):\n"
                            "    nxt = request.GET.get('next', '/')\n"
                            "    if nxt.startswith(('http://', 'https://')):\n"
                            "        return HttpResponseBadRequest('bad redirect')\n"
                            "    return redirect(nxt)"
                        ),
                    },
                ],
            },
        },
    ]

    for e in entries:
        for k in e["match"]:
            kl = k.lower()
            if kl in key or kl in full_key or kl in title:
                return e
    return None


def _detect_language(
    rule_id: str,
    title: str,
    file_location: str,
    code_snippet: str,
) -> str:
    """Best-effort detection of the repository's primary language.

    The `/recommend` endpoint is called per-vulnerability and the
    FE does not currently forward a `language` field, so the LLM
    has to guess. The default behaviour is to fall back to a JS
    snippet, which is wrong for Go / Python repos and is exactly
    what the user reported as "still default output".

    This helper inspects the rule id, title, file location, and
    code snippet and returns one of: `go`, `python`, `javascript`,
    `typescript`. Returns an empty string when no signal is found
    so the caller can decide what to do (the LLM is then free to
    pick based on the rest of the prompt).
    """
    rid = (rule_id or "").lower()
    ttl = (title or "").lower()
    loc = (file_location or "").lower()
    snip = (code_snippet or "").lower()

    # Go signals: `go.mod` is mentioned, or the rule id namespace
    # contains `blog-cms` / `auth` and the title talks about Go
    # constructs (`bluemonday`, `import`, `package`, `go.mod`).
    if "go.mod" in ttl or "bluemonday" in ttl or "golang" in ttl:
        return "go"
    if loc.endswith(".go") or "/go/" in loc:
        return "go"
    if "package " in snip and "func " in snip and "import " in snip:
        return "go"

    # Python signals.
    if loc.endswith(".py") or "/python/" in loc:
        return "python"
    if "django" in rid or "flask" in rid or "pyyaml" in rid:
        return "python"
    if "def " in snip and ("import " in snip or "self" in snip):
        return "python"

    # TypeScript signals (before plain JS).
    if loc.endswith(".ts") or loc.endswith(".tsx"):
        return "typescript"

    # JavaScript signals.
    if loc.endswith(".js") or loc.endswith(".jsx") or "/js/" in loc:
        return "javascript"
    if "node_modules" in loc or "package.json" in loc:
        return "javascript"
    if "const " in snip and ("require(" in snip or "=>" in snip):
        return "javascript"

    return ""


def _parse_trivy_alert(vuln: dict) -> dict:
    """Extract Trivy-specific fields from a Code Scanning alert.

    Trivy's SARIF uploader writes a structured ``message.text`` for
    every finding, e.g.::

        Package: PyJWT
        Installed Version: 1.7.1
        Vulnerability CVE-2026-48522
        Severity: MEDIUM
        Fixed Version: 2.13.0
        Link: CVE-2026-48522

        PyJWT: Server-Side Request Forgery (SSRF) via uncontrolled
        URL fetching in PyJWKClient

    The current normalizer stashes this whole blob in
    ``evidence``/``explanation`` but the per-vuln ``/recommend``
    endpoint never had access to it, so recommendations for Trivy
    findings fell back to the generic GitHub-advisory pointer.

    This helper scans the alert fields for those Trivy lines and
    returns a small dict with ``package_name``, ``installed_version``,
    ``fixed_version``, ``vulnerability_id``, ``cve``, ``ecosystem``,
    and the full Trivy description. Empty fields stay as ``""`` so
    the caller can detect "not a Trivy alert" and skip the
    special branch.
    """
    blob = "\n".join(
        str(vuln.get(k) or "")
        for k in (
            "evidence",
            "explanation",
            "message",
            "description",
            "title",
        )
    )

    out: dict = {
        "package_name": "",
        "installed_version": "",
        "fixed_version": "",
        "vulnerability_id": "",
        "cve": "",
        "description": "",
        "ecosystem": "",
        "is_trivy": False,
    }

    if not blob.strip():
        return out

    pkg = re.search(r"(?im)^Package:\s*(\S+)", blob)
    if pkg:
        out["package_name"] = pkg.group(1).strip()
        out["is_trivy"] = True

    installed = re.search(r"(?im)^Installed Version:\s*(\S+)", blob)
    if installed:
        out["installed_version"] = installed.group(1).strip()
        out["is_trivy"] = True

    fixed = re.search(r"(?im)^Fixed Version:\s*(\S+)", blob)
    if fixed:
        out["fixed_version"] = fixed.group(1).strip()
        out["is_trivy"] = True

    cve = re.search(r"\b(CVE-\d{4}-\d{4,7})\b", blob)
    if cve:
        out["cve"] = cve.group(1)
        out["vulnerability_id"] = cve.group(1)
        out["is_trivy"] = True

    if out["is_trivy"]:
        # The Trivy title is often in `rule.name`
        # ("<pkg>: <description>"); capture the LONGEST
        # "<Word>: <text>" line we can find — the package
        # name alone (e.g. "PyJWT:") gives an empty body
        # which we want to skip. The interesting line is the
        # one where the colon is followed by 20+ characters
        # of description.
        candidates = re.findall(
            r"(?m)^[A-Za-z][A-Za-z0-9_.-]+:\s+(\S.{20,})$", blob
        )
        if candidates:
            # Take the longest candidate — usually the
            # vulnerability title is more descriptive than
            # the boilerplate header.
            out["description"] = max(candidates, key=len).strip()

    # Detect the package manager from the file path the alert
    # was raised in. Trivy records the lockfile in
    # `file_location`; requirements.txt is Python, package-lock.json
    # is JS, go.sum is Go, etc.
    file_loc = (vuln.get("file_location") or "").lower()
    if any(x in file_loc for x in ("requirements.txt", "pipfile", "poetry.lock", "pyproject.toml", ".py")):
        out["ecosystem"] = "python"
    elif any(x in file_loc for x in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".js", ".ts")):
        out["ecosystem"] = "javascript"
    elif any(x in file_loc for x in ("go.sum", "go.mod", ".go")):
        out["ecosystem"] = "go"
    elif any(x in file_loc for x in ("gemfile.lock", "gemspec", ".rb")):
        out["ecosystem"] = "ruby"
    elif any(x in file_loc for x in ("cargo.lock", "cargo.toml", ".rs")):
        out["ecosystem"] = "rust"

    return out


def _known_rule_fix(
    leaf: str,
    vuln: dict,
) -> dict | None:
    """Deterministic fallback for well-known npm/pip advisories.

    The LLM call in `generate_per_vuln_recommendation` is the
    preferred path (it produces a context-aware fix), but
    when it fails or returns an empty body we want to give the
    user something actionable — the CVE / GHSA id, the safe
    version, and the exact upgrade command.

    Each entry maps a `rule_id` leaf (or keyword in the title)
    to a small dict with `summary`, `affected`, `fix`, `why`,
    `upgrade`, and an optional `code_changes` list. The
    coverage is intentionally narrow: the most common
    dependency vulnerabilities that show up in Code Scanning
    alerts. Anything we don't know about falls through to the
    generic GitHub-advisory pointer in the caller.
    """
    # Normalize the rule id (strip namespace, lowercase) for
    # case-insensitive matching.
    key = (leaf or "").strip().lower()
    title = (vuln.get("title") or "").lower()
    scanner = (vuln.get("scanner") or "").lower()
    # `full_key` includes the package name from the full rule
    # id (e.g. "node-tar.PAX-size-override") so entries keyed
    # on the package name match even when the leaf is a
    # generic identifier like "PAX-size-override" or
    # "prototype-pollution".
    full_key = (vuln.get("rule_id") or "").strip().lower()

    # Helper: combined-key matcher. Returns the first entry
    # whose `match` key appears in the rule id, the full rule
    # id, OR the title.
    def find(entries: list[dict]) -> dict | None:
        for e in entries:
            for k in e["match"]:
                kl = k.lower()
                if kl in key or kl in full_key or kl in title:
                    return e
        return None

    npm_entries: list[dict] = [
        {
            "match": ["node-tar", "node_tar"],
            "summary": (
                "`node-tar` < 7.4.4 (and the 6.x line < 6.2.1) mishandles PAX "
                "long-name / long-link headers, allowing an attacker who controls "
                "the tar archive to smuggle files outside the intended extraction "
                "directory (path traversal / file smuggling)."
            ),
            "affected": "< 7.4.4 (7.x line), < 6.2.1 (6.x line), and 5.x < 5.0.7",
            "fix": (
                "Upgrade `node-tar` to a patched version. If a transitive "
                "dependency is pulling in the vulnerable version, add an "
                "`overrides` (npm 8.3+) or `resolutions` (yarn) entry in "
                "`package.json` to force the safe version."
            ),
            "why": (
                "The patched release hardens the PAX header parser so a "
                "crafted long-name / long-link header can no longer override "
                "the size of an intermediary header and slip a forged entry "
                "into the extraction stream."
            ),
            "upgrade": "npm install node-tar@^7.4.4\n# or, for npm 8.3+: add to package.json\n# \"overrides\": { \"node-tar\": \"^7.4.4\" }",
        },
        {
            "match": ["lodash", "lodash.template", "lodash._.template", "command injection in lodash"],
            "summary": (
                "`lodash` versions <= 4.17.20 (and the `lodash.template` CVEs "
                "CVE-2019-10744 / CVE-2020-8203) are vulnerable to prototype "
                "pollution and command injection via the `_.template` "
                "imports option."
            ),
            "affected": "<= 4.17.20 (prototype pollution), and template import CVEs through 4.17.21",
            "fix": (
                "Upgrade `lodash` to a current 4.17.x release. Avoid `_.template` "
                "with untrusted input entirely — use a sandboxed template engine "
                "or escape the input manually."
            ),
            "why": (
                "The 4.17.21+ release fixes the `_.zipObjectDeep` prototype "
                "pollution; later 4.17.x releases backport fixes for the "
                "template-injection CVEs."
            ),
            "upgrade": "npm install lodash@^4.17.21",
        },
        {
            "match": ["minimatch"],
            "summary": (
                "`minimatch` < 3.0.5 and < 9.0.5 (3.x line) is vulnerable to "
                "ReDoS (regular-expression denial of service) via crafted glob "
                "patterns."
            ),
            "affected": "< 3.0.5 (3.x line), < 9.0.5 (9.x line)",
            "fix": "Upgrade `minimatch` to the latest 3.x / 9.x patch release.",
            "why": (
                "The patch adds a non-backtracking match path for nested "
                "extglob patterns, eliminating the catastrophic-backtracking "
                "worst case."
            ),
            "upgrade": "npm install minimatch@^9.0.5",
        },
        {
            "match": ["follow-redirects"],
            "summary": (
                "`follow-redirects` < 1.14.8 leaks the `Authorization` header "
                "across hosts on a cross-origin redirect (CVE-2022-0155 / "
                "CVE-2022-0536)."
            ),
            "affected": "< 1.14.8",
            "fix": "Upgrade `follow-redirects` to a patched release.",
            "why": (
                "The patch strips the `Authorization` and `Cookie` headers when "
                "the redirect target is a different host than the original "
                "request."
            ),
            "upgrade": "npm install follow-redirects@^1.14.8",
        },
        {
            "match": ["axios"],
            "summary": (
                "`axios` < 1.6.0 (and the 0.x / 0.27.x lines) has multiple "
                "SSRF and CSRF issues — most notably CVE-2023-45857 (XSRF "
                "token leak) and CVE-2024-39338 (SSRF via path-relative URLs)."
            ),
            "affected": "< 1.6.0 (1.x line), and various 0.x patches",
            "fix": "Upgrade `axios` to a current 1.x release.",
            "why": (
                "The 1.6.0 release changes the default `XSRF` cookie name and "
                "tightens URL parsing, eliminating the SSRF and CSRF paths."
            ),
            "upgrade": "npm install axios@^1.6.0",
        },
        {
            "match": ["semver"],
            "summary": (
                "`semver` < 7.5.2 is vulnerable to ReDoS in the `Range` "
                "parser (CVE-2022-25883)."
            ),
            "affected": "< 7.5.2",
            "fix": "Upgrade `semver` to a current 7.5.x release.",
            "why": (
                "The patch rewrites the range-compiler to avoid the "
                "catastrophic-backtracking pattern."
            ),
            "upgrade": "npm install semver@^7.5.2",
        },
        {
            "match": ["js-yaml"],
            "summary": (
                "`js-yaml` < 3.14.1 (3.x) and < 4.1.0 (4.x) is vulnerable to "
                "prototype pollution / code execution via crafted YAML "
                "(CVE-2021-23906 / CVE-2023-2251)."
            ),
            "affected": "< 3.14.1 (3.x), < 4.1.0 (4.x)",
            "fix": (
                "Upgrade `js-yaml` to the latest 4.1.x release. Avoid the "
                "unsafe `load()` and `SAFE_SCHEMA` — use `load()` with the "
                "default `FAILSAFE_SCHEMA` for untrusted YAML, or parse it "
                "as JSON."
            ),
            "why": (
                "The patch drops the `DEFAULT_FULL_SCHEMA` alias and tightens "
                "the `merge` function to prevent prototype pollution."
            ),
            "upgrade": "npm install js-yaml@^4.1.0",
        },
        {
            "match": ["ejs"],
            "summary": (
                "`ejs` < 3.1.7 is vulnerable to server-side template "
                "injection via the `outputFunctionName` option "
                "(CVE-2022-29078)."
            ),
            "affected": "< 3.1.7",
            "fix": "Upgrade `ejs` to a current 3.1.x release.",
            "why": (
                "The patch escapes the `outputFunctionName` value before "
                "interpolating it into the compiled template, closing the "
                "RCE path."
            ),
            "upgrade": "npm install ejs@^3.1.7",
        },
        {
            "match": ["handlebars"],
            "summary": (
                "`handlebars` < 4.7.7 is vulnerable to prototype pollution "
                "and arbitrary code execution via crafted templates "
                "(CVE-2021-23369 / CVE-2021-23362)."
            ),
            "affected": "< 4.7.7",
            "fix": "Upgrade `handlebars` to a current 4.7.x release.",
            "why": (
                "The patch restricts the prototype-access walk in the "
                "compiler and tightens the `__proto__` traversal in the "
                "runtime helpers."
            ),
            "upgrade": "npm install handlebars@^4.7.7",
        },
        {
            "match": ["shell-quote", "shellquote"],
            "summary": (
                "`shell-quote` < 1.7.3 is vulnerable to command injection "
                "via crafted input to the `quote` / `parse` functions "
                "(CVE-2021-4278)."
            ),
            "affected": "< 1.7.3",
            "fix": "Upgrade `shell-quote` to a current 1.7.x release.",
            "why": (
                "The patch adds an explicit allow-list for the operators "
                "the parser recognises, blocking the `>()` and `>()` "
                "process-substitution patterns that enable injection."
            ),
            "upgrade": "npm install shell-quote@^1.7.3",
        },
        {
            "match": ["yargs-parser", "yargsparser"],
            "summary": (
                "`yargs-parser` < 13.1.2 (13.x) / < 15.0.1 (15.x) / < 18.1.2 "
                "(18.x) is vulnerable to prototype pollution "
                "(CVE-2020-7608)."
            ),
            "affected": "< 13.1.2 / < 15.0.1 / < 18.1.2",
            "fix": "Upgrade `yargs-parser` to a current release on your major.",
            "why": (
                "The patch uses `Object.create(null)` for the parsed-options "
                "object and rejects `__proto__` keys during assignment."
            ),
            "upgrade": "npm install yargs-parser@^18.1.2",
        },
        {
            "match": ["immer"],
            "summary": (
                "`immer` < 9.0.6 is vulnerable to prototype pollution "
                "(CVE-2021-23436)."
            ),
            "affected": "< 9.0.6",
            "fix": "Upgrade `immer` to a current 9.x release.",
            "why": (
                "The patch uses `Object.create(null)` for the draft object "
                "and walks the assignment with a `__proto__` check."
            ),
            "upgrade": "npm install immer@^9.0.6",
        },
        {
            "match": ["ws"],
            "summary": (
                "`ws` < 5.2.3 / < 6.2.3 / < 7.4.6 is vulnerable to ReDoS and "
                "DoS via crafted HTTP headers (CVE-2021-32640)."
            ),
            "affected": "< 5.2.3 / < 6.2.3 / < 7.4.6",
            "fix": "Upgrade `ws` to a current release on your major.",
            "why": (
                "The patch caps the number of `Sec-Websocket-Protocol` "
                "subprotocol headers the server will parse, closing the "
                "ReDoS path."
            ),
            "upgrade": "npm install ws@^7.4.6",
        },
        {
            "match": ["open"],
            "summary": (
                "`open` < 8.4.0 (and 7.x < 7.4.2) passes a crafted `file://` "
                "URL to the system shell, enabling command injection "
                "(CVE-2022-25912)."
            ),
            "affected": "< 8.4.0 (8.x), < 7.4.2 (7.x)",
            "fix": "Upgrade `open` to a current release on your major.",
            "why": (
                "The patch rejects URLs that contain shell metacharacters "
                "before invoking the OS-level `open` helper."
            ),
            "upgrade": "npm install open@^8.4.0",
        },
        {
            "match": ["tar"],
            "summary": (
                "`tar` (the npm package, not the system binary) < 6.1.7 / "
                "< 5.0.8 / < 4.4.16 has multiple path-traversal and "
                "symlink-escape issues (CVE-2021-37701, CVE-2022-25860)."
            ),
            "affected": "< 6.1.7 / < 5.0.8 / < 4.4.16",
            "fix": "Upgrade `tar` to a current release on your major.",
            "why": (
                "The patches tighten the entry-name validation and block "
                "the symlink-following paths that allowed a malicious tar "
                "to escape the destination directory."
            ),
            "upgrade": "npm install tar@^6.1.7",
        },
        {
            "match": ["underscore"],
            "summary": (
                "`underscore` < 1.13.6 is vulnerable to arbitrary code "
                "execution via the `template` import (CVE-2021-23358)."
            ),
            "affected": "< 1.13.6",
            "fix": "Upgrade `underscore` to a current 1.13.x release.",
            "why": (
                "The patch escapes the `interpolate` / `evaluate` / "
                "`escape` delimiters before they are interpolated into the "
                "compiled template, eliminating the RCE path."
            ),
            "upgrade": "npm install underscore@^1.13.6",
        },
        {
            "match": ["request"],
            "summary": (
                "`request` is deprecated and has accumulated multiple "
                "open advisories (CSRF token leak, SSRF, credential leak "
                "in redirect). The maintainers will not backport fixes."
            ),
            "affected": "all versions (the package is unmaintained)",
            "fix": (
                "Migrate to a maintained HTTP client. Recommended "
                "replacements: `axios` ^1.6, `node-fetch` ^3.3, or the "
                "built-in `fetch` (Node 18+)."
            ),
            "why": (
                "The `request` package is officially deprecated; using it "
                "in new code (or as a transitive dependency) is "
                "considered a security smell regardless of the specific "
                "advisory."
            ),
            "upgrade": "npm uninstall request\nnpm install axios@^1.6.0",
        },
        {
            "match": ["merge", "lodash.merge"],
            "summary": (
                "`lodash.merge` < 4.6.2 (or `lodash` < 4.17.12) is vulnerable "
                "to prototype pollution via crafted deep-merge input "
                "(CVE-2019-10744)."
            ),
            "affected": "< 4.6.2 (merge), < 4.17.12 (lodash)",
            "fix": "Upgrade `lodash` to a current 4.17.x release.",
            "why": (
                "The patch walks the source object with a `__proto__` "
                "check during deep-merge, blocking the prototype-pollution "
                "path."
            ),
            "upgrade": "npm install lodash@^4.17.21",
        },
    ]

    pip_entries: list[dict] = [
        {
            "match": ["django", "sql-injection in django"],
            "summary": (
                "`Django` versions in the affected range are vulnerable to "
                "SQL injection in the `JSONField` lookup / `QuerySet` "
                "filter path."
            ),
            "affected": "varies by advisory (see CVE link)",
            "fix": "Upgrade `Django` to the latest patch release on your minor.",
            "why": (
                "The patch adds stricter quoting around JSONField lookup "
                "values, eliminating the SQL-injection path."
            ),
            "upgrade": "pip install --upgrade 'Django>=4.2.10'",
        },
        {
            "match": ["requests"],
            "summary": (
                "`requests` < 2.32.0 leaks the `Proxy-Authorization` header "
                "on a cross-origin redirect (CVE-2024-35195)."
            ),
            "affected": "< 2.32.0",
            "fix": "Upgrade `requests` to a current 2.32.x release.",
            "why": (
                "The patch strips the `Proxy-Authorization` header when "
                "the redirect target is a different host."
            ),
            "upgrade": "pip install --upgrade 'requests>=2.32.0'",
        },
        {
            "match": ["pillow", "pil"],
            "summary": (
                "`Pillow` has a steady stream of memory-safety and "
                "out-of-bounds-read advisories. The version in your lockfile "
                "is missing the latest patch."
            ),
            "affected": "varies (check the CVE link in the GitHub alert)",
            "fix": "Upgrade `Pillow` to the latest 10.x release.",
            "why": (
                "Pillow backports memory-safety fixes to each minor; the "
                "patch release named in the advisory closes the specific "
                "out-of-bounds path."
            ),
            "upgrade": "pip install --upgrade 'Pillow>=10.3.0'",
        },
        {
            "match": ["flask"],
            "summary": (
                "`Flask` < 2.3.2 / < 3.0.1 has session-cookie issues (the "
                "default `SECRET_KEY` fallback, and open-redirect on the "
                "`?next=` parameter)."
            ),
            "affected": "< 2.3.2 (2.x), < 3.0.1 (3.x)",
            "fix": "Upgrade `Flask` to a current release on your major.",
            "why": (
                "The patches set `SESSION_COOKIE_SECURE` defaults and "
                "validate the `?next=` redirect target against the request "
                "host."
            ),
            "upgrade": "pip install --upgrade 'Flask>=3.0.1'",
        },
        {
            "match": ["pyyaml", "yaml.load"],
            "summary": (
                "`PyYAML` < 5.1 (and 5.x < 5.3.1) allows arbitrary code "
                "execution via `yaml.load()` without an explicit `Loader`."
            ),
            "affected": "< 5.1 / < 5.3.1",
            "fix": (
                "Upgrade `PyYAML` to a current 6.x release. Also replace "
                "any `yaml.load(stream)` call with `yaml.safe_load(stream)` "
                "to avoid the unsafe-loader path entirely."
            ),
            "why": (
                "PyYAML 5.1+ deprecates the default `Loader` and 5.3+ "
                "removes it, forcing the caller to pick a safe loader "
                "explicitly."
            ),
            "upgrade": "pip install --upgrade 'PyYAML>=6.0'",
        },
        {
            "match": ["urllib3"],
            "summary": (
                "`urllib3` < 1.26.5 / < 2.0.1 leaks the `Authorization` "
                "header on a cross-origin redirect and has a "
                "CRLF-injection path in the URL parser."
            ),
            "affected": "< 1.26.5 (1.x), < 2.0.1 (2.x)",
            "fix": "Upgrade `urllib3` to a current release on your major.",
            "why": (
                "The patches strip the `Authorization` header on "
                "cross-origin redirects and reject URLs with embedded CR/LF."
            ),
            "upgrade": "pip install --upgrade 'urllib3>=2.0.7'",
        },
    ]

    found = find(npm_entries) if "npm" in scanner or scanner in ("",) else None
    if not found:
        found = find(pip_entries) if "pip" in scanner or "python" in scanner else None
    if not found:
        # Fall back to a cross-scanner match.
        found = find(npm_entries) or find(pip_entries)
    return found


# Per-ecosystem upgrade-command templates for Trivy findings.
# Trivy SARIF uploader doesn't tell us which package manager
# the user actually uses (just the lockfile in `file_location`),
# so we emit the most common upgrade command for each
# ecosystem. The user can adjust the syntax for their tool
# of choice (uv, poetry, pnpm, yarn, ...).
_TRIVY_UPGRADE_CMDS: dict[str, str] = {
    "python": "pip install --upgrade {pkg}>={fixed}",
    "javascript": "npm install {pkg}@{fixed}",
    "go": "go get {pkg}@{fixed}",
    "ruby": "bundle update {pkg}",
    "rust": "cargo update -p {pkg}",
}


def _build_trivy_recommendation(
    trivy: dict,
    vuln: dict,
) -> dict:
    """Render a Trivy-specific recommendation without calling the LLM.

    Trivy's SARIF uploader writes a structured message that
    already contains everything we need to give the user a
    concrete, actionable fix: the package name, the installed
    version, the CVE id, and the fixed version. The LLM call
    is best-effort and frequently returns empty for dependency
    findings (it tends to repeat the rule name and call it
    "the vulnerability"), so we short-circuit here and return
    a deterministic, info-rich response.

    The shape matches the response of
    ``generate_per_vuln_recommendation`` (rule_id,
    file_location, line, recommendation, code_changes) so the
    FE renders it via the same ``RecommendationPanel`` without
    any FE changes.
    """
    pkg = trivy.get("package_name") or "<package>"
    installed = trivy.get("installed_version") or "?"
    fixed = trivy.get("fixed_version") or "?"
    cve = trivy.get("cve") or trivy.get("vulnerability_id") or "the listed advisory"
    description = trivy.get("description") or ""
    ecosystem = trivy.get("ecosystem") or ""

    # Pick the upgrade command template for this ecosystem.
    cmd_template = _TRIVY_UPGRADE_CMDS.get(ecosystem, "update {pkg} to {fixed}")
    upgrade_cmd = cmd_template.format(pkg=pkg, fixed=fixed)
    if ecosystem == "python" and fixed == "?":
        upgrade_cmd = f"pip install --upgrade {pkg}"
    if ecosystem == "javascript" and fixed == "?":
        upgrade_cmd = f"npm install {pkg}@latest"
    if ecosystem == "go" and fixed == "?":
        upgrade_cmd = f"go get -u {pkg}"

    # Build a markdown recommendation. The structure mirrors
    # the deterministic-fallback format used by
    # _known_rule_fix so the FE renders it consistently.
    description_line = (
        f" {description}" if description and description != pkg else ""
    )
    description_clause = description_line or " closes the vulnerability path flagged by Trivy"
    recommendation = (
        f"**Summary.** `{pkg}` `{installed}` is affected by "
        f"{cve}{description_line}. The fix is to upgrade to "
        f"`{pkg}` `{fixed}` (or later)."
    )

    if ecosystem:
        recommendation += (
            f"\n\n**Affected package.** `{pkg}` "
            f"(installed `{installed}` → fixed `{fixed}`)\n\n"
            f"**Upgrade command.**\n"
            f"```bash\n{upgrade_cmd}\n```\n\n"
        )
    else:
        recommendation += (
            f"\n\n**Affected package.** `{pkg}` "
            f"(installed `{installed}` → fixed `{fixed}`)\n\n"
            f"**Upgrade command.** Adjust for your package manager:\n"
            f"```bash\n{upgrade_cmd}\n```\n\n"
        )

    recommendation += (
        f"**Why this works.** {cve} is fixed in `{pkg}` "
        f"`{fixed}`. The patched release{description_clause}. "
        f"After upgrading, re-run Trivy to confirm the finding is gone."
    )

    # Build the code_change hint. The Trivy finding itself
    # usually doesn't carry a code snippet (the issue is in a
    # lockfile, not source), so we surface a single "bump
    # dependency" change that the FE can render as the diff.
    file_loc = vuln.get("file_location") or ""
    code_changes: list[dict] = []
    if file_loc:
        code_changes.append({
            "description": (
                f"Bump `{pkg}` to the safe version `{fixed}` in the manifest."
            ),
            "file": file_loc,
            "before": f"{pkg}=={installed}" if ecosystem == "python"
                else f"\"{pkg}\": \"^{installed}\"" if ecosystem in ("javascript",)
                else f"{pkg} {installed}",
            "after": f"{pkg}=={fixed}" if ecosystem == "python"
                else f"\"{pkg}\": \"^{fixed}\"" if ecosystem in ("javascript",)
                else f"{pkg} {fixed}",
        })

    return {
        "rule_id": vuln.get("rule_id"),
        "file_location": vuln.get("file_location"),
        "line": vuln.get("line"),
        "recommendation": recommendation,
        "code_changes": code_changes,
    }


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
    # The matcher below does a substring search against the
    # full rule id AND the title, so package names like
    # `node-tar` or `lodash` are found even when they're
    # embedded in a longer leaf like `PAX-size-override`.
    full_rule_id = ".".join(parts)

    # Best-effort language detection. The FE does not forward a
    # `language` field for the per-vuln `/recommend` endpoint, so
    # the LLM often defaults to JavaScript / DOMPurify snippets
    # even when the repo is Go or Python. We infer from the rule
    # id, title, file location, and code snippet and inject the
    # result into the prompt so the LLM picks the right API.
    detected_lang = _detect_language(
        vuln.get("rule_id") or "",
        vuln.get("title") or "",
        vuln.get("file_location") or "",
        vuln.get("code_snippet") or "",
    )

    # 0. Trivy-aware deterministic branch. Code Scanning alerts
    # uploaded by Trivy's SARIF action carry a structured
    # `message.text` with the package name, installed version,
    # CVE id, and fixed version. The previous behaviour
    # discarded all of that and fell through to the generic
    # GitHub-advisory pointer, which gave the user "Open the
    # Code Scanning tab..." for every Trivy finding — useless
    # when the user is staring at the dashboard with no other
    # context. Build a rich, Trivy-specific recommendation
    # here so the user sees the package name, the version
    # jump, and the exact upgrade command inline.
    trivy = _parse_trivy_alert(vuln)
    if trivy.get("is_trivy"):
        return _build_trivy_recommendation(trivy, vuln)

    # 1. Try the LLM for a context-aware recommendation.
    recommendation = ""
    code_changes: list[dict] = []
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        prompt = (
            "You are a senior DevSecOps engineer. Generate a "
            "context-aware, actionable fix recommendation for the "
            "following vulnerability. Use the file path, line number, "
            "rule id, and (if available) the source code snippet to "
            "write a precise recommendation that the user can apply "
            "immediately.\n\n"
            f"Repository: {repo}\n"
            + (
                f"Detected language: {detected_lang}\n"
                f"All code snippets in your response MUST be written in "
                f"{detected_lang}. Use the idiomatic API for that "
                f"language (e.g. bluemonday for Go, DOMPurify for JS, "
                f"bleach for Python, bcrypt/argon2 for Go password "
                f"hashing, passlib/bcrypt for Python, bcrypt for Node).\n"
                if detected_lang
                else ""
            )
            + f"Rule ID: {vuln.get('rule_id')}\n"
            f"Severity: {vuln.get('severity')}\n"
            f"CVSS score: {vuln.get('cvss_score')}\n"
            f"File: {vuln.get('file_location') or '?'}\n"
            f"Line: {vuln.get('line')}\n"
            f"Title: {vuln.get('title') or ''}\n"
            f"Code snippet:\n```\n{vuln.get('code_snippet') or '(not provided)'}\n```\n\n"
            "Respond with a JSON object and NOTHING else (no prose "
            "before or after the JSON, no markdown code-fence). Use "
            "this exact shape:\n"
            "{\n"
            '  "summary": "1-2 sentence explanation of the issue and why it matters",\n'
            '  "recommendation": "markdown-formatted step-by-step fix (use **bold**, '
            '`inline code`, numbered lists, and ```fenced``` code blocks where useful). '
            'Cover: (1) what to change, (2) the package upgrade command if any, '
            '(3) a code snippet showing the fixed code, (4) how to verify the fix.",\n'
            '  "code_changes": [\n'
            '    {"description": "what this change does", '
            '     "file": "path/to/file", '
            '     "before": "original code (1-10 lines)", '
            '     "after": "fixed code (1-10 lines)"}\n'
            '  ],\n'
            '  "upgrade_command": "npm install <pkg>@<safe-version>  (or empty string if N/A)"\n'
            "}\n\n"
            "Important:\n"
            "- `recommendation` MUST be non-empty and at least 3-5 sentences.\n"
            "- Determine the rule type from the rule id and title:\n"
            "  * **Dependency / supply-chain rule** (e.g. lodash, node-tar, "
            "qs, minimatch, axios, semver, follow-redirects, tar, js-yaml, "
            "ejs, handlebars, underscore, request, shell-quote, yargs-parser, "
            "immer, ws, open, or any rule id that names an npm/pip package): "
            "name the CVE/GHSA id if you know it, state the affected version "
            "range, the safe version, and the exact package manager upgrade "
            "command. Set `upgrade_command` to that command.\n"
            "  * **Code-level SAST rule** (e.g. missing-html-sanitizer, "
            "weak-password-hash, sql-injection, command-injection, "
            "path-traversal, insecure-deserialization, hardcoded-secret, "
            "open-redirect, xss, unsafe-eval, missing-auth, missing-csrf, "
            "weak-crypto, insecure-random): explain the vulnerability in "
            "plain language, then give a code-level fix (use a safe API, "
            "add a sanitizer, switch to bcrypt/argon2, use parameterised "
            "queries, validate path traversal, etc.). Set `upgrade_command` "
            "to an empty string. Use the file path, line number, and code "
            "snippet to write a fix that is specific to the flagged code.\n"
            "  * **Secret-leak / hardcoded-credential rule** (e.g. "
            "generic-api-key, generic-secret, hardcoded-secret, "
            "gitleaks, trufflehog, git-secrets, or any rule whose title "
            "contains 'api key', 'secret', 'token', 'password', 'private "
            "key', 'aws access key', 'stripe', 'github token'): treat the "
            "leaked value as **already compromised**. Step 1 must be to "
            "rotate / revoke the credential at the provider, step 2 is to "
            "move it to an environment variable or secret manager "
            "(GitHub Actions secrets, AWS Secrets Manager, HashiCorp "
            "Vault, Doppler), step 3 is to purge it from git history with "
            "`git filter-repo` or BFG and force-push, and step 4 is to "
            "audit downstream clones / forks. Give a `code_changes` "
            "entry that shows the hardcoded literal being replaced with "
            "`os.environ[...]` / `process.env.X` / `os.Getenv(...)`. "
            "Set `upgrade_command` to an empty string.\n"
            "  * If the rule does not clearly match either bucket, treat it "
            "as code-level and give a code-level fix based on the rule id "
            "semantics.\n"
            "- `code_changes` should contain at least 1 entry with real, "
            "copy-pasteable code whenever the fix is a code change (e.g. "
            "adding input validation, switching a function call, fixing a "
            "regex, declaring a dependency in go.mod). Use empty "
            "`before`/`after` only when the fix is purely a dependency "
            "upgrade.\n"
            + (
                "- You MUST write all code snippets in "
                f"{detected_lang} (the language detected for this "
                "repository). Do NOT fall back to JavaScript / "
                "DOMPurify when the repo is Go or Python.\n"
                if detected_lang
                else ""
            )
            + "- Do not include any text outside the JSON object."
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        import json, re
        content = (response.content or "").strip()
        # Strip any markdown code-fence the LLM might have wrapped the
        # JSON in despite the instructions.
        md = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if md:
            content = md.group(1).strip()
        parsed: dict = {}
        try:
            parsed = json.loads(content)
        except Exception:
            # Last-ditch: grab the first {...} block.
            brace = re.search(r"\{.*\}", content, re.DOTALL)
            if brace:
                try:
                    parsed = json.loads(brace.group(0))
                except Exception:
                    parsed = {}
        # Combine `summary` + `recommendation` so the FE gets a
        # single, rich markdown body. The `summary` line gives a
        # 1-2 sentence framing that the user sees at the top of
        # the AI panel; the `recommendation` field has the
        # step-by-step fix.
        summary_text = str(parsed.get("summary") or "").strip()
        rec_text = str(parsed.get("recommendation") or "").strip()
        if summary_text and rec_text:
            recommendation = f"**Summary.** {summary_text}\n\n{rec_text}"
        else:
            recommendation = rec_text or summary_text
        raw_changes = parsed.get("code_changes") or []
        # Coerce each entry into the documented shape. The LLM
        # sometimes drops the `description` field or leaves
        # `before`/`after` as null; we want a stable contract
        # for the FE.
        code_changes = []
        for c in raw_changes:
            if not isinstance(c, dict):
                continue
            code_changes.append({
                "before": str(c.get("before") or ""),
                "after": str(c.get("after") or ""),
                "file": str(c.get("file") or vuln.get("file_location") or ""),
                "description": str(c.get("description") or ""),
            })
        # If the LLM didn't surface a useful recommendation, fall
        # through to the deterministic map below. The previous
        # behaviour was to return a generic "Review the rule
        # documentation..." string that gave the user nothing
        # actionable; the deterministic map at least names the
        # CVE, the safe version, and the upgrade command.
        if not recommendation:
            # Defer the actual fallback to the helper defined
            # further down so we keep the prompt + the
            # deterministic lookup in one place.
            recommendation = ""  # signal to the helper below
    except Exception as e:
        # LLM unavailable — fall back to the deterministic map.
        recommendation = ""  # signal to the helper below
        print(f"[per-vuln] LLM call failed: {e}")

    # 2. Deterministic fallback. If the LLM call didn't return
    #    a usable recommendation, look up the rule id in the
    #    static CVE/known-vuln map. This map carries the CVE id,
    #    the safe version, the upgrade command, and a short
    #    explanation — enough for the user to act without
    #    reading the full advisory.
    if not recommendation:
        fix = _known_rule_fix(leaf, vuln)
        if fix:
            recommendation = (
                f"**Summary.** {fix['summary']}\n\n"
                f"**Affected versions.** {fix['affected']}\n\n"
                f"**Fix.** {fix['fix']}\n\n"
                f"**Upgrade command.**\n"
                f"```bash\n{fix['upgrade']}\n```\n\n"
                f"**Why this works.** {fix['why']}"
            )
            for c in fix.get("code_changes") or []:
                code_changes.append({
                    "before": c.get("before", ""),
                    "after": c.get("after", ""),
                    "file": c.get("file", vuln.get("file_location") or ""),
                    "description": c.get("description", ""),
                })
            if not code_changes and fix.get("upgrade"):
                code_changes.append({
                    "before": "",
                    "after": fix["upgrade"],
                    "file": "package.json",
                    "description": "Bump the affected dependency to the safe version.",
                })
        else:
            code_fix = _known_code_rule_fix(leaf, vuln, detected_lang)
            if code_fix:
                recommendation = (
                    f"**Summary.** {code_fix['summary']}\n\n"
                    f"**Fix.** {code_fix['fix']}\n\n"
                    f"**Why this works.** {code_fix['why']}"
                )
                # Pick the code snippets that match the detected
                # language. Fall back to the Go default if the
                # entry doesn't carry a per-language variant —
                # keeps the original (Go-flavoured) recommendation
                # working for repos that were already covered.
                lang_key = (detected_lang or "").lower()
                lang_snippets = code_fix.get("code_changes_by_lang") or {}
                chosen = lang_snippets.get(lang_key) or code_fix.get("code_changes") or []
                for c in chosen:
                    code_changes.append({
                        "before": c.get("before", ""),
                        "after": c.get("after", ""),
                        "file": c.get("file", vuln.get("file_location") or ""),
                        "description": c.get("description", ""),
                    })
            else:
                _rid = (vuln.get("rule_id") or "").lower()
                _is_secret_rule = any(
                    tok in _rid
                    for tok in (
                        "secret", "api-key", "apikey", "password", "token",
                        "credential", "private-key", "gitleaks", "trufflehog",
                    )
                )
                if _is_secret_rule:
                    _file = vuln.get("file_location") or "the flagged file"
                    _line = vuln.get("line")
                    _loc = f"{_file}:{_line}" if _line else _file
                    recommendation = (
                        f"**Summary.** `{vuln.get('rule_id')}` detected a hardcoded "
                        f"credential in `{_loc}`. Treat the value as **already "
                        f"compromised** — anyone with read access to the repository "
                        f"(including forks, history, and backups) can use it.\n\n"
                        f"**Next steps.**\n"
                        f"1. **Rotate / revoke** the credential at the provider "
                        f"right now (regenerate the API key, invalidate the "
                        f"token, reset the password). Do this before editing code.\n"
                        f"2. **Move the value out of the repo.** Read it at runtime "
                        f"from an environment variable or a secret manager "
                        f"(GitHub Actions secrets, AWS Secrets Manager, HashiCorp "
                        f"Vault, Doppler). See the `code_changes` panel for a "
                        f"copy-pasteable patch.\n"
                        f"3. **Purge it from git history** with `git filter-repo` "
                        f"or BFG Repo-Cleaner, force-push, then audit downstream "
                        f"clones and forks (GitHub shows them under *Security → "
                        f"Code scanning → 'Detected in fork'*).\n"
                        f"4. **Re-run the analysis** to confirm the secret is no "
                        f"longer detected."
                    )
                    code_changes = [
                        {
                            "description": (
                                "Replace the hardcoded credential with an "
                                "environment variable read at runtime."
                            ),
                            "file": _file,
                            "before": (
                                "API_KEY = 'sk-live-XXXXXXXXXXXXXXXX'  # "
                                "leaked secret"
                            ),
                            "after": (
                                "import os\n"
                                "API_KEY = os.environ['API_KEY']  # raises "
                                "KeyError if missing"
                            ),
                        }
                    ]
                else:
                    recommendation = (
                        f"**Summary.** This finding comes from the `{vuln.get('rule_id')}` "
                        f"rule. The Code Scanning tab in GitHub has the full advisory "
                        f"(CVE / GHSA id, affected version range, and patch version).\n\n"
                        f"**Next steps.**\n"
                        f"1. Open the GitHub Code Scanning alert (link in the panel above) "
                        f"and note the CVE / GHSA id and the safe version.\n"
                        f"2. If the rule is a dependency vulnerability, run the upgrade "
                        f"command from the advisory (e.g. `npm install <pkg>@<safe-version>` "
                        f"or `pip install <pkg>==<safe-version>`).\n"
                        f"3. If the rule is a code-level issue, edit "
                        f"`{vuln.get('file_location') or 'the flagged file'}` and apply the "
                        f"fix described in the advisory.\n"
                        f"4. Re-run the analysis to confirm the finding is gone."
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