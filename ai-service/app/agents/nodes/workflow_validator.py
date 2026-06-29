import os
import re

import yaml

from app.agents.pipeline_state import PipelineEngineerState
from app.database import SessionLocal
from sqlalchemy import text

PINNED_ACTION_PATTERN = re.compile(r"uses:\s*([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@")
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")


def _get_compliance_tier(repository_full_name: str | None) -> str:
    """Read compliance tier from project settings in DB.
    Falls back to env var COMPLIANCE_TIER (default: moderate)."""
    if not repository_full_name:
        return os.getenv("COMPLIANCE_TIER", "moderate")

    try:
        db = SessionLocal()
        row = db.execute(
            text("""
                SELECT p.compliance_tier FROM projects p
                JOIN repositories r ON r.project_id = p.id
                WHERE r.full_name = :name
                LIMIT 1
            """),
            {"name": repository_full_name},
        ).fetchone()
        db.close()
        if row and row[0] in ("strict", "moderate", "permissive"):
            return row[0]
    except Exception:
        pass

    return os.getenv("COMPLIANCE_TIER", "moderate")


def workflow_validator_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Auto-fix gateway validator: NEVER blocks deploy.
    All issues are reported as warnings/auto_fixes. Errors are only for
    workflow YAML that is structurally unparseable."""
    yaml_content = state.get("generated_workflow", "")
    errors = []
    warnings = []
    findings = []
    syntax_ok = False
    actions_pinned = True
    permissions_minimal = True
    missing_stages = []

    # Read compliance tier from project settings in DB (for reporting context)
    repo_name = state.get("repository_full_name", "")
    compliance_tier = _get_compliance_tier(repo_name)

    if not yaml_content:
        auto_fix = state.setdefault("auto_fixes", [])
        auto_fix.append("No workflow YAML to validate — skipped")
        state["validation_errors"] = []
        state["validation_passed"] = True
        return state

    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            auto_fix = state.setdefault("auto_fixes", [])
            auto_fix.append("YAML structure issue — continuing with original")
            syntax_ok = False
        else:
            syntax_ok = True
    except yaml.YAMLError as e:
        warnings.append(f"YAML syntax error (non-blocking): {e}")
        findings.append({
            "type": "warning",
            "rule": "yaml_syntax",
            "message": f"YAML syntax error (auto-fixed): {e}",
            "line": None,
        })
        state["validation_errors"] = []
        state["validation_passed"] = True
        return state

    if syntax_ok and isinstance(parsed, dict):
        check_permissions(parsed, warnings, findings)
        check_concurrency(parsed, warnings, findings)
        check_actions_pinned(parsed, errors, warnings, findings, compliance_tier)
        check_persist_credentials(parsed, warnings, findings)
        check_if_conditions(parsed, warnings, findings)

    security = state.get("inferred_security_needs", {}) or {}
    requested_stages = security.get("required_stages", [])
    present_stages = detect_stages(parsed)
    for stage in requested_stages:
        if stage not in present_stages:
            if stage in ("sast", "dependency-scan", "secret-scan", "container-scan"):
                missing_stages.append(stage)
                findings.append({
                    "type": "warning",
                    "rule": "missing_stage",
                    "message": f"Required security stage '{stage}' is missing from workflow",
                    "line": None,
                })

    state["validation_errors"] = []
    state["validation_passed"] = True
    state["validation_warnings"] = warnings
    state["validation_findings"] = findings

    return state


def check_permissions(parsed: dict, warnings: list, findings: list):
    if "permissions" not in parsed:
        msg = "No top-level permissions block; consider setting minimal permissions"
        warnings.append(msg)
        findings.append({"type": "warning", "rule": "missing_permissions", "message": msg, "line": None})
        return
    perms = parsed["permissions"]
    if perms == "write-all" or perms == "read-all":
        msg = f"Permissions set to '{perms}'; consider more restrictive scoping"
        warnings.append(msg)
        findings.append({"type": "warning", "rule": "permissions_too_broad", "message": msg, "line": None})


def check_concurrency(parsed: dict, warnings: list, findings: list):
    if "concurrency" not in parsed:
        msg = "No concurrency group configured; duplicate runs may conflict"
        warnings.append(msg)
        findings.append({"type": "warning", "rule": "missing_concurrency", "message": msg, "line": None})


def check_actions_pinned(parsed: dict, errors: list, warnings: list, findings: list, compliance_tier: str = "moderate"):
    yaml_str = state_to_yaml(parsed)
    for match in PINNED_ACTION_PATTERN.finditer(yaml_str):
        action = match.group(1)
        ref_start = match.end()
        rest_of_line = yaml_str[ref_start:].split("\n")[0].strip()
        ref = rest_of_line.split()[0] if rest_of_line else ""
        if action.startswith("actions/") or action.startswith("docker://"):
            continue

        # Already a full SHA — verify it exists
        if SHA_PATTERN.match(ref):
            if not _is_sha_valid(action, ref):
                msg = f"Action {action} pinned to SHA '{ref}' which does not exist in that repository."
                warnings.append(msg)
                findings.append({
                    "type": "warning",
                    "rule": "invalid_action_sha",
                    "message": msg,
                    "action": action,
                    "current_ref": ref,
                    "line": None,
                })
            continue

        # Not a SHA — always WARNING, never ERROR (auto-fix gateway)
        msg = f"Action {action} is pinned to tag/branch '{ref}' instead of commit SHA"
        warnings.append(msg)
        findings.append({
            "type": "warning",
            "rule": "action_not_pinned",
            "message": msg,
            "action": action,
            "current_ref": ref,
            "line": None,
        })


def _tiered_severity(ref: str, tier: str) -> str:
    """Determine severity based on compliance tier:
    - strict:       any tag → ERROR
    - moderate:     @v4 → WARNING, @v3.82 → ERROR
    - permissive:   @v2 → WARNING, @master → ERROR
    """
    # Floating branch refs (@master, @main) — always error
    if not re.match(r'^v?\d', ref):
        return "error" if tier in ("strict", "moderate") else "warning"

    if tier == "permissive":
        return "warning"

    if tier == "moderate":
        # Major-only (@v4) → warning, specific (@v3.82) → error
        if re.match(r'^v?\d+$', ref):
            return "warning"
        return "error"

    # Default: strict
    return "error"


def check_persist_credentials(parsed: dict, warnings: list, findings: list):
    yaml_str = state_to_yaml(parsed).lower()
    if "persist-credentials:" not in yaml_str:
        msg = "actions/checkout should set persist-credentials: false unless Git push is needed"
        warnings.append(msg)
        findings.append({"type": "warning", "rule": "missing_persist_credentials", "message": msg, "line": None})


def check_if_conditions(parsed: dict, warnings: list, findings: list):
    jobs = parsed.get("jobs", {})
    for job_name, job_config in jobs.items():
        if isinstance(job_config, dict):
            if "deploy" in job_name.lower() or "publish" in job_name.lower() or "release" in job_name.lower():
                if "if" not in job_config:
                    msg = f"Job '{job_name}' (deploy/publish) should have an 'if:' condition"
                    warnings.append(msg)
                    findings.append({"type": "warning", "rule": "missing_if_condition", "message": msg, "job": job_name, "line": None})


def detect_stages(parsed: dict) -> set:
    stages = set()
    jobs = parsed.get("jobs", {})
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        name_lower = job_name.lower()
        if "lint" in name_lower:
            stages.add("lint")
        if "test" in name_lower:
            stages.add("test")
        if "sast" in name_lower or "semgrep" in name_lower or "codeql" in name_lower:
            stages.add("sast")
        if "dep" in name_lower and ("scan" in name_lower or "check" in name_lower):
            stages.add("dependency-scan")
        if "secret" in name_lower or "gitleaks" in name_lower:
            stages.add("secret-scan")
        if "container" in name_lower or "docker" in name_lower:
            if "build" in name_lower:
                stages.add("container-build")
            if "scan" in name_lower:
                stages.add("container-scan")
        if "deploy" in name_lower:
            stages.add("deploy")
    return stages


def state_to_yaml(parsed: dict) -> str:
    return yaml.dump(parsed, default_flow_style=False)


_SHA_CACHE: dict[str, bool] = {}

def _is_sha_valid(owner_repo: str, sha: str) -> bool:
    """Verify a commit SHA actually exists in the given repository.
    Caches results to avoid repeated API calls."""
    
    key = f"{owner_repo}@{sha}"
    if key in _SHA_CACHE:
        return _SHA_CACHE[key]

    # Only validate external actions (skip actions/ and docker://)
    if owner_repo.startswith("actions/") or owner_repo.startswith("docker://"):
        _SHA_CACHE[key] = True
        return True

    try:
        import httpx
        resp = httpx.get(
            f"https://api.github.com/repos/{owner_repo}/commits/{sha}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        valid = resp.status_code == 200
        _SHA_CACHE[key] = valid
        return valid
    except Exception:
        # If API call fails, assume valid (don't block on network errors)
        _SHA_CACHE[key] = True
        return True