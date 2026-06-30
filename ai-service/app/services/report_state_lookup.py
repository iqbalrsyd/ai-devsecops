"""DB-backed state lookup for the PDF generator (v9.5).

Fixes the "PDF failed because fetching failed to get pipeline_id /
run_id" error from the FE. When the FE posts a body that is missing
the Tahap-1 / Tahap-2 / Tahap-3 fields (e.g. it only sent `runId` in
the URL, or the AI service was unreachable when the user clicked
"Generate PDF Report"), the PDF endpoint calls
`lookup_run_state()` to backfill the missing fields from the
database.

Lookup order:
  1. pipeline_runs by id (Go-side run UUID)
  2. workflow_executions by git_hub_run_id (integer, GitHub Actions run id)
  3. pipeline_generations + repositories for the latest run
  4. pipeline_analyses for findings / risk_score / recommendations

The function never raises — any DB error is logged and the partial
result (or None) is returned so the PDF endpoint can decide whether
to render a synthetic PDF.
"""

from __future__ import annotations

import json
from typing import Any

from app.database import SessionLocal
from sqlalchemy import text


def _safe_json(value: Any) -> Any:
    """JSONB columns can be stored as a Python dict, a JSON string, or
    a JSON-encoded string of a JSON string. Walk the rabbit hole until
    we hit a real dict/list.
    """
    while isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


async def lookup_run_state(
    run_id: str | int | None = None,
    repository_full_name: str | None = None,
) -> dict | None:
    """Backfill the PDF state from the database.

    Args:
        run_id: either the Go-side run UUID (string) or the
                GitHub Actions run id (int). We try both.
        repository_full_name: optional `owner/repo` slug for the
                "latest run for this repo" lookup.

    Returns:
        A dict with the fields the PDF generator needs (technology
        stack, architecture, deployment, domain, security coverages,
        findings, recommendations, etc.), or None when nothing
        useful was found.
    """
    if not run_id and not repository_full_name:
        return None

    db = SessionLocal()
    try:
        # === 1. resolve the (pipeline_run_id, repository_id) pair ===
        run_row = None
        if run_id:
            # Try as Go-side UUID first
            run_row = db.execute(
                text("""
                    SELECT pr.id, pr.pipeline_id, pr.run_number,
                           pr.git_hub_run_id, pr.status, pr.conclusion,
                           r.full_name, r.id AS repo_id
                    FROM pipeline_runs pr
                    JOIN pipelines p ON p.id = pr.pipeline_id
                    JOIN repositories r ON r.id = p.repository_id
                    WHERE pr.id = :rid OR pr.git_hub_run_id = :rid_int
                    ORDER BY pr.created_at DESC
                    LIMIT 1
                """),
                {"rid": str(run_id), "rid_int": int(run_id) if str(run_id).isdigit() else -1},
            ).fetchone()

        if not run_row and repository_full_name:
            run_row = db.execute(
                text("""
                    SELECT pr.id, pr.pipeline_id, pr.run_number,
                           pr.git_hub_run_id, pr.status, pr.conclusion,
                           r.full_name, r.id AS repo_id
                    FROM pipeline_runs pr
                    JOIN pipelines p ON p.id = pr.pipeline_id
                    JOIN repositories r ON r.id = p.repository_id
                    WHERE r.full_name = :name
                    ORDER BY pr.created_at DESC
                    LIMIT 1
                """),
                {"name": repository_full_name},
            ).fetchone()

        if not run_row:
            return None

        run_uuid = str(run_row[0])
        pipeline_id = str(run_row[1])
        run_number = run_row[2]
        github_run_id = run_row[3]
        repo_full_name = run_row[6]
        repo_id = str(run_row[7])

        result: dict[str, Any] = {
            "repository_full_name": repo_full_name,
            "run_id": run_uuid,
            "github_run_id": github_run_id,
            "pipeline_id": pipeline_id,
            "run_number": run_number,
        }

        # === 2. pipeline_generations (Tahap 3 output) ===
        gen_row = db.execute(
            text("""
                SELECT generated_yaml, stages, ai_explanation,
                       generation_params, validation_results,
                       security_controls_applied, compliance_metadata
                FROM pipeline_generations
                WHERE pipeline_id = :pid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"pid": pipeline_id},
        ).fetchone()
        if gen_row:
            yaml_text, stages, ai_expl, gen_params, val_res, sec_ctrl, comp_meta = gen_row
            if yaml_text:
                result["generated_workflow"] = yaml_text
            if stages:
                stages_parsed = _safe_json(stages)
                if isinstance(stages_parsed, list):
                    result["generated_stages"] = stages_parsed
            if ai_expl:
                result["generation_explanation"] = ai_expl
            if val_res:
                vr = _safe_json(val_res)
                if isinstance(vr, dict):
                    result["validation_passed"] = bool(vr.get("passed", True))
                    result["validation_errors"] = vr.get("errors", []) or []
                    result["validation_warnings"] = vr.get("warnings", []) or []

        # === 3. pipeline_analyses (Tahap 4 output: risk + findings) ===
        analysis_row = db.execute(
            text("""
                SELECT risk_score, compliance_score, security_coverage_score,
                       findings_summary, severity_breakdown, recommendations,
                       raw_scan_data
                FROM pipeline_analyses
                WHERE pipeline_run_id = :rid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"rid": run_uuid},
        ).fetchone()
        if analysis_row:
            risk, comp, sec_cov, find_sum, sev_bd, recs, raw = analysis_row
            if risk is not None:
                result["risk_score"] = float(risk)
            if comp is not None:
                result["compliance_score"] = float(comp)
            if sec_cov is not None:
                result["security_coverage_score"] = float(sec_cov)
            if sev_bd:
                sb = _safe_json(sev_bd)
                if isinstance(sb, dict):
                    result["severity_breakdown"] = sb
            if recs:
                recs_parsed = _safe_json(recs)
                if isinstance(recs_parsed, list):
                    result["recommendations"] = recs_parsed
            if raw:
                raw_parsed = _safe_json(raw)
                if isinstance(raw_parsed, dict):
                    # Findings + alerts live inside raw_scan_data
                    if "findings" in raw_parsed and isinstance(raw_parsed["findings"], list):
                        result["findings"] = raw_parsed["findings"]
                    if "code_scanning_alerts" in raw_parsed and isinstance(
                        raw_parsed["code_scanning_alerts"], list
                    ):
                        result["code_scanning_alerts"] = raw_parsed["code_scanning_alerts"]
                    if "dashboard_findings" in raw_parsed and isinstance(
                        raw_parsed["dashboard_findings"], dict
                    ):
                        result["dashboard_findings"] = raw_parsed["dashboard_findings"]

        # === 4. repository_insights (Tahap 1+2 cached) ===
        insights_row = db.execute(
            text("""
                SELECT insights
                FROM repository_insights
                WHERE repository_id = :rid
                LIMIT 1
            """),
            {"rid": repo_id},
        ).fetchone()
        if insights_row and insights_row[0]:
            insights = _safe_json(insights_row[0])
            if isinstance(insights, dict):
                # The Go-side insights table stores a JSONB column with
                # the same shape as `run_repo_generate` returns.
                for key in (
                    "detected_technologies", "detected_architecture",
                    "detected_architecture_type", "detected_deployment",
                    "recommended_deployment_target", "detected_domain",
                    "domain_sub_type", "domain_confidence", "domain_threats",
                    "features", "security_coverages", "pipeline_augmentations",
                    "ai_generated_rules", "job_designs",
                ):
                    if insights.get(key) and not result.get(key):
                        result[key] = insights[key]

        return result
    except Exception as e:
        # Never raise — the PDF endpoint catches and turns this into
        # a 500 with a "fetch_warnings" array. The user still gets
        # a useful error.
        print(f"[report_state_lookup] DB lookup failed: {e}")
        return None
    finally:
        try:
            db.close()
        except Exception:
            pass
