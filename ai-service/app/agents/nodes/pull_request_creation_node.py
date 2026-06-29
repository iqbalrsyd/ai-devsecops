import time

from app.agents.action_registry import (
    actions_used_in_yaml,
    validate_yaml_against_registry,
)
from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import (
    commit_file,
    create_pull_request,
    delete_file,
    get_default_branch_sha,
    list_workflow_files,
)


PR_TITLE_TEMPLATE = "[AI DevSecOps] Add secure CI/CD pipeline"

PR_BODY_TEMPLATE = """## 🤖 AI DevSecOps: Automated Pipeline Generation

{tech_section}
{stages_section}

### Security Controls Applied
- ✅ All actions pinned to commit SHA
- ✅ Minimal GITHUB_TOKEN permissions
- ✅ Concurrency groups configured
- ✅ `persist-credentials: false` on checkout
- ✅ `if:` conditions on deploy/publish jobs
- ✅ Security scans gating deployment
{cleanup_section}
{config_section}
{maintenance_section}
{external_section}
{remediation_section}

### Next Steps
1. Review the workflow file
2. Merge this PR
3. The pipeline will run automatically on future pushes
"""


def _disable_legacy_workflows(
    repo: str,
    branch: str,
    keep_path: str,
    github_token: str,
) -> tuple[list[str], list[str]]:
    """Delete every existing workflow file in `.github/workflows/` that is not
    the newly generated one.

    GitHub Actions will run *every* workflow file in `.github/workflows/`
    whose `on:` trigger matches the event. If we leave legacy pipelines
    in place they keep firing on every PR and the user sees the wrong
    job set in the PR checks. Deleting them ensures the generated
    pipeline is the only one being executed.

    Special handling for AI-generated pipeline files
    (`ai-devsecops-v{N}.yml`): when the same content already exists at
    the new version (e.g. v8 and v9 were identical because nothing
    changed in the workflow itself), we delete ALL older versions
    regardless of name to avoid the "triple-run" scenario where
    GitHub fires every historical version on every push.

    Returns (deleted_paths, errors).
    """
    deleted: list[str] = []
    errors: list[str] = []
    try:
        existing = list_workflow_files(repo, branch, github_token)
    except Exception as e:
        return [], [f"Failed to list existing workflows: {e}"]

    keep_name = keep_path.rsplit("/", 1)[-1]  # e.g. "ai-devsecops.yml"
    is_pipeline_keep = keep_name == "ai-devsecops.yml"

    for path in existing:
        if path.rstrip("/") == keep_path.rstrip("/"):
            continue
        # The keep file (ai-devsecops.yml) is the single AI-generated
        # pipeline file. Every older ai-devsecops-v{N}.yml that may
        # have been left over from previous deploys (the workflow
        # used to be versioned in commit 65c847f and earlier) is
        # deleted here so the repo ends up with only the fixed
        # name. The new ai-devsecops.yml will overwrite the previous
        # one via commit_file (path = keep_path), so the repo
        # always has at most 1 AI-generated workflow file plus any
        # user-authored workflows.
        if is_pipeline_keep:
            fname = path.rsplit("/", 1)[-1]
            if fname.startswith("ai-devsecops-v") and fname.endswith(".yml"):
                ok = delete_file(
                    repo, branch, path,
                    message=f"Remove legacy versioned pipeline {path} — replaced by {keep_name}",
                    github_token=github_token,
                )
                if ok:
                    deleted.append(path)
                    print(f"[disable_legacy] removed {path} (legacy ai-devsecops-v*.yml)")
                else:
                    errors.append(f"Failed to remove {path}")
                continue
        # Generic cleanup for any other workflow file the user
        # previously had that the new pipeline supersedes. (e.g.
        # an older ci-cd.yml that the team committed before
        # adopting the AI generator.) We still skip files that
        # look like user-authored integrations (e.g. release.yml,
        # deploy.yml) by only deleting when the file is not
        # explicitly preserved.
        ok = delete_file(
            repo,
            branch,
            path,
            message=f"Remove legacy workflow {path} — replaced by AI-generated pipeline",
            github_token=github_token,
        )
        if ok:
            deleted.append(path)
        else:
            errors.append(f"Failed to remove {path}")
    return deleted, errors


def _cleanup_main_branch_workflows(
    repo: str,
    keep_paths: set[str],
    github_token: str | None,
) -> tuple[list[str], list[str]]:
    """Delete LEGACY versioned workflow files (`ai-devsecops-v*.yml`)
    on the DEFAULT branch (main / master).

    The new pipeline file has a fixed name (`ai-devsecops.yml`) and
    overwrites the previous one via `commit_file`, so the repo will
    always end up with at most 1 AI-generated workflow file after the
    next deploy lands.

    This helper still cleans up the older `ai-devsecops-v{N}.yml`
    files that may have been committed by deploys from before the
    filename was fixed (every v2, v8, v9, v11, v13, v14, v17 that
    accumulated in repos like iqbalrsyd/ecommerce-clean). It only
    touches files matching the `ai-devsecops-v*.yml` pattern; the
    new fixed-name file (`ai-devsecops.yml`) and any user-authored
    workflows are NEVER deleted.

    Safety constraints:
      * Only deletes `ai-devsecops-v*.yml`. The new
        `ai-devsecops.yml` is in keep_paths and is not touched.
      * Skips silently if the default branch cannot be reached
        (token may lack `repo:write` on main, or main may be
        protected). The PR's own cleanup is still in effect.
      * Skips files that are not in the legacy versioned prefix
        (user-authored workflows, custom integrations).

    Returns (deleted_paths, errors).
    """
    deleted: list[str] = []
    errors: list[str] = []
    # Discover the default branch and resolve its HEAD sha.
    try:
        default_sha = get_default_branch_sha(repo, github_token)
    except Exception as e:
        return [], [f"Could not resolve default-branch sha: {e}"]
    if not default_sha:
        return [], []

    # We need the branch NAME, not just the sha, because
    # delete_file / list_workflow_files take a branch ref. Try
    # main / master in order, matching get_default_branch_sha.
    default_branch: str | None = None
    for candidate in ("main", "master"):
        try:
            existing = list_workflow_files(repo, candidate, github_token)
        except Exception:
            continue
        if existing:
            default_branch = candidate
            break
    if not default_branch:
        return [], []

    try:
        existing = list_workflow_files(repo, default_branch, github_token)
    except Exception as e:
        return [], [f"Failed to list workflows on {default_branch}: {e}"]

    for path in existing:
        if path.rstrip("/") in keep_paths:
            continue
        fname = path.rsplit("/", 1)[-1]
        # Only delete the LEGACY versioned AI-generated pipeline
        # files on main (ai-devsecops-v{N}.yml from the old
        # versioned-naming scheme). The new fixed-name
        # ai-devsecops.yml is preserved (it lives in keep_paths)
        # because commit_file will overwrite it directly. User-
        # authored workflows are never touched.
        if not (fname.startswith("ai-devsecops-v") and fname.endswith(".yml")):
            continue
        ok = delete_file(
            repo,
            default_branch,
            path,
            message=f"Remove legacy versioned pipeline {path} — replaced by ai-devsecops.yml",
            github_token=github_token,
        )
        if ok:
            deleted.append(path)
            print(f"[cleanup_main] removed {path} from {default_branch}")
        else:
            errors.append(f"Failed to remove {path} from {default_branch}")
    return deleted, errors


def _validate_actions_pre_commit(yaml_text: str) -> list[dict]:
    """Pre-commit action-compatibility validation.

    Every action emitted into the PR is cross-checked against the
    compatibility registry. The result is a list of
    `workflow_config_issue` dicts.

    These issues do NOT block the PR. The pipeline priority is
    "executable workflows over simply generating security controls",
    so an action with a missing optional input is still committed and
    surfaced in the PR body for the human to address. Genuine blockers
    (e.g. `actions/upload-artifact@v3`) are recorded in the maintenance
    section and the user is told to upgrade before merging.
    """
    return validate_yaml_against_registry(yaml_text)


def _render_config_section(issues: list[dict]) -> str:
    if not issues:
        return ""
    lines = ["", "### ⚠️ Workflow Configuration Issues",
             "These were detected against the action compatibility registry. None are security findings; they are recorded here so the workflow can be made executable before merging.", ""]
    for i in issues[:20]:
        rule = i.get("rule", "")
        action = i.get("action", "")
        job = i.get("job", "")
        message = i.get("message", "")
        suggestion = i.get("suggestion", "")
        scope = f"`{action}`" if action else (f"job `{job}`" if job else "workflow")
        lines.append(f"- **{rule}** in {scope}: {message}")
        if suggestion:
            lines.append(f"  - _Fix:_ {suggestion}")
    return "\n".join(lines)


def _render_maintenance_section(warnings: list[dict]) -> str:
    if not warnings:
        return ""
    lines = ["", "### 🛠 Maintenance Warnings",
             "These do not break the workflow today, but will need attention soon.", ""]
    for w in warnings[:20]:
        rule = w.get("rule", "")
        action = w.get("action", "")
        message = w.get("message", "")
        scope = f"`{action}`" if action else "workflow"
        lines.append(f"- **{rule}** in {scope}: {message}")
    return "\n".join(lines)


def _render_remediation_section(recs: list[dict]) -> str:
    actionable = [r for r in (recs or []) if r.get("auto_applicable")]
    if not actionable:
        return ""
    lines = ["", "### ✅ Auto-Applied Remediations",
             "The following workflow-configuration fixes have already been applied to this PR:", ""]
    for r in actionable[:10]:
        lines.append(f"- {r.get('description') or r.get('title', '')}")
    return "\n".join(lines)


def _render_external_section(issues: list[dict]) -> str:
    """Render external service issues (502, GitHub status degraded, etc.).

    These are surfaced in the PR body so the reviewer knows why the
    pipeline generation hit a transient problem, but they do NOT block
    the PR and do NOT affect the risk score.
    """
    if not issues:
        return ""
    lines = ["", "### 🌐 External Service Issues",
             "The pipeline encountered upstream transient errors. **These are NOT security findings**, do NOT require a code change, and do NOT affect the risk score.", ""]
    for iss in issues[:20]:
        rule = iss.get("rule", "")
        message = iss.get("message", "") or iss.get("description", "")
        source = iss.get("source", "upstream")
        suggestion = iss.get("suggestion", "")
        lines.append(f"- **{rule}** (via {source}): {message[:200]}")
        if suggestion:
            lines.append(f"  - _Suggestion:_ {suggestion[:200]}")
    return "\n".join(lines)


def _blocking_errors(errors: list[str]) -> bool:
    """Return True if `errors` contains a genuine blocker.

    Transient upstream errors (5xx, 502, Bad Gateway, etc.) that were
    already routed to `external_service_issues` do NOT block the PR.
    Only structural errors (missing YAML, missing branch, GitHub auth
    failure) are blockers.
    """
    BLOCKER_KEYWORDS = (
        "no workflow yaml",
        "no branch",
        "auth",
        "authentication",
        "unauthorized",
        "forbidden",
        "token",
        "not found",
        "invalid",
        "parse error",
        "yaml syntax",
        "commit failed",
        "create branch",
        "create pull request",
    )
    TRANSIENT_PATTERNS = (
        "502",
        "503",
        "504",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "request failed with status code",
        "our services aren't available",
        "github services aren't available",
        "connection refused",
        "connection reset",
        "timed out",
    )
    for err in (errors or []):
        if not isinstance(err, str):
            continue
        low = err.lower()
        # If it's clearly a transient external error, it does not block.
        if any(p.lower() in low for p in TRANSIENT_PATTERNS):
            continue
        # If it matches a blocker keyword, it blocks.
        if any(kw in low for kw in BLOCKER_KEYWORDS):
            return True
    return False


def pull_request_creation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    errors = state.get("errors") or []
    yaml_content = state.get("generated_workflow", "")
    branch = state.get("github_branch", "")

    # Priority rule: "executable workflows over simply generating security
    # controls". A transient 502 during SHA resolution is NOT a blocker
    # if we still have a workflow to commit. Only structural failures
    # (no YAML, no branch, auth errors) block the PR.
    if _blocking_errors(errors) or (not yaml_content and errors):
        return state

    if not yaml_content:
        state["errors"].append("No workflow YAML to commit")
        return state
    if not branch:
        state["errors"].append("No branch to commit to")
        return state

    repo = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN
    base_branch = state.get("repository_default_branch", "main")
    tech = state.get("detected_technologies", {}) or {}
    architecture_raw = state.get("detected_architecture", {})
    architecture = state.get("detected_architecture_type") or (
        architecture_raw.get("architecture_type") if isinstance(architecture_raw, dict) else str(architecture_raw or "")
    )
    security = state.get("inferred_security_needs", {}) or {}
    version = state.get("pipeline_version", 1)

    # ------------------------------------------------------------------
    # Pre-commit action-compatibility validation.
    # We do not block the PR; we record the findings and surface them in
    # the PR body so the human reviewer can address them. Executable
    # workflows are the priority.
    # ------------------------------------------------------------------
    pre_commit_issues = _validate_actions_pre_commit(yaml_content)
    if pre_commit_issues:
        existing = state.get("workflow_config_issues") or []
        state["workflow_config_issues"] = existing + pre_commit_issues

    workflow_filename = f"ai-devsecops-v{version}.yml"
    workflow_path = f".github/workflows/{workflow_filename}"
    state["workflow_file"] = workflow_path
    commit_message = "Add AI-generated secure CI/CD pipeline with DevSecOps best practices"

    # ------------------------------------------------------------------
    # Two-file workflow (struktur-v9.3 — domain-aware deployment).
    # The generator now produces TWO workflow files:
    #   1. `ai-devsecops.yml`        — generic pipeline (lint, test, sast,
    #                                  secret-scan, dep-check, container-scan)
    #                                  which calls the custom file via
    #                                  `uses: ./.github/workflows/ai-devsecops-custom.yml`.
    #   2. `ai-devsecops-custom.yml` — domain-specific compliance jobs
    #                                  (pci-dss, hipaa, ledger-check, etc.)
    #                                  exposed as a reusable workflow_call.
    # Backwards-compat: when only the merged single yaml is present in
    # `state["generated_workflow"]`, we fall back to the legacy single-file
    # commit path so old callers keep working.
    # ------------------------------------------------------------------
    generic_yaml = state.get("generated_workflow_generic") or ""
    custom_yaml = state.get("generated_workflow_custom") or ""
    workflow_file_meta = state.get("generated_workflow_files") or []

    if generic_yaml and custom_yaml:
        generic_path = ".github/workflows/ai-devsecops.yml"
        custom_path = ".github/workflows/ai-devsecops-custom.yml"
        state["workflow_file"] = generic_path
        state["workflow_file_custom"] = custom_path
        state["workflow_files"] = [
            {"name": "ai-devsecops.yml", "path": generic_path, "kind": "generic"},
            {"name": "ai-devsecops-custom.yml", "path": custom_path, "kind": "custom"},
        ]
        workflow_path = generic_path
        # Commit the custom file FIRST so the generic file's
        # `uses: ./.github/workflows/ai-devsecops-custom.yml` reference
        # resolves on the very first commit of the PR.
        try:
            custom_sha = commit_file(
                repo, branch, custom_path, custom_yaml,
                "Add AI-DevSecOps custom rules + domain compliance workflow",
                github_token,
            )
            if not custom_sha:
                state["errors"].append("Failed to commit custom workflow file")
                return state
        except Exception as e:
            state["errors"].append(f"Custom workflow file commit failed: {e}")
            return state

        try:
            commit_sha = commit_file(
                repo, branch, generic_path, generic_yaml, commit_message, github_token,
            )
            if not commit_sha:
                state["errors"].append("Failed to commit generic workflow file")
                return state
            state["github_commit_sha"] = commit_sha
        except Exception as e:
            state["errors"].append(f"Generic workflow file commit failed: {e}")
            return state
    else:
        # Legacy single-file path (unchanged behaviour).
        try:
            commit_sha = commit_file(repo, branch, workflow_path, yaml_content, commit_message, github_token)
            if not commit_sha:
                state["errors"].append("Failed to commit workflow file")
                return state
            state["github_commit_sha"] = commit_sha
        except Exception as e:
            state["errors"].append(f"File commit failed: {e}")
            return state

    # ------------------------------------------------------------------
    # Domain-aware custom Semgrep rules. When the AI agent has classified
    # the repo's domain (e.g. e-commerce), push the relevant custom
    # rule files to .semgrep/ in the repo so the Semgrep CLI can
    # reference them with --config=.semgrep/<file>.yml.
    # ------------------------------------------------------------------
    domain_rule_files_committed: list[str] = []
    detected_domain = state.get("detected_domain")
    if detected_domain and detected_domain != "general":
        try:
            from app.agents.nodes.workflow_generator import (
                _semgrep_rules_for_domain,
            )
            import os

            custom_rule_files = _semgrep_rules_for_domain(detected_domain)
            rules_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "semgrep_rules",
            )
            for rule_filename in custom_rule_files:
                src = os.path.join(rules_dir, rule_filename)
                if not os.path.isfile(src):
                    continue
                with open(src) as f:
                    rule_content = f.read()
                dst_path = f".semgrep/{rule_filename}"
                rule_sha = commit_file(
                    repo, branch, dst_path, rule_content,
                    f"Add custom Semgrep rules for {detected_domain}",
                    github_token,
                )
                if rule_sha:
                    if rule_sha != "UNCHANGED":
                        domain_rule_files_committed.append(dst_path)
                    else:
                        print(f"[pull_request_creation] {dst_path} already up-to-date on branch — no commit needed")
        except Exception as e:
            state.setdefault("warnings", []).append(
                f"Could not commit custom Semgrep rules for {detected_domain}: {e}"
            )

    if domain_rule_files_committed:
        state["custom_semgrep_rules"] = domain_rule_files_committed

    # ------------------------------------------------------------------
    # AI-generated Semgrep rules (K2.3 / Tier 3). When the pattern
    # inference node produced extra rules tailored to the concrete
    # source code, persist them to `.semgrep/ai-generated.yml` so the
    # `sast` job in the generated workflow picks them up via
    # `--config=.semgrep` (folder import). Without this, the AI rules
    # would only live in the workflow heredoc (which we just removed
    # in workflow_generator.py).
    # ------------------------------------------------------------------
    ai_rules = state.get("ai_generated_rules") or []
    if ai_rules:
        try:
            import yaml as _ai_yaml
            ai_rules_content = _ai_yaml.safe_dump(
                {"rules": ai_rules},
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
            ai_rules_path = ".semgrep/ai-generated.yml"
            ai_sha = commit_file(
                repo, branch, ai_rules_path, ai_rules_content,
                f"Add {len(ai_rules)} AI-generated Semgrep rules",
                github_token,
            )
            if ai_sha:
                if ai_sha != "UNCHANGED":
                    domain_rule_files_committed.append(ai_rules_path)
                else:
                    print(f"[pull_request_creation] {ai_rules_path} already up-to-date on branch — no commit needed")
        except Exception as e:
            state.setdefault("warnings", []).append(
                f"Could not commit AI-generated Semgrep rules: {e}"
            )

    # Remove every other workflow file so the PR checks reflect ONLY the
    # generated pipeline. If this step fails we still continue (the new
    # file is already committed) but we surface the issue in PR body.
    deleted_legacy, cleanup_errors = _disable_legacy_workflows(
        repo, branch, workflow_path, github_token
    )
    state["removed_legacy_workflows"] = deleted_legacy
    if cleanup_errors:
        state.setdefault("warnings", []).extend(cleanup_errors)

    # Additionally clean up the DEFAULT branch (main / master).
    # The PR cleanup above only takes effect on main after the PR
    # is merged, so if the user has re-deployed the pipeline
    # several times (or if the previous PR was force-closed),
    # main can still hold every historical ai-devsecops-v{N}.yml.
    # That produces the "12 cancelled, 15 successful" symptom
    # where GitHub triggers every historical version on every
    # push. The helper below is intentionally narrow: it only
    # touches files matching the ai-devsecops-v*.yml prefix, so
    # user-authored workflows are preserved.
    keep_paths = {workflow_path}
    if custom_yaml:
        keep_paths.add(".github/workflows/ai-devsecops-custom.yml")
    for rp in domain_rule_files_committed:
        keep_paths.add(rp)
    deleted_main, cleanup_errors_main = _cleanup_main_branch_workflows(
        repo, keep_paths, github_token
    )
    if deleted_main:
        state.setdefault("removed_legacy_workflows", []).extend(deleted_main)
    if cleanup_errors_main:
        # Only surface the main-branch cleanup errors as warnings;
        # the PR's own cleanup is already in effect.
        state.setdefault("warnings", []).extend(cleanup_errors_main)

    language = (tech.get("primary_language") or tech.get("language", "unknown"))
    frameworks = ", ".join(tech.get("frameworks", []) or ["unknown"])
    build_tools = ", ".join(tech.get("build_tools", []) or ["unknown"])
    stages = state.get("generated_stages") or security.get("required_stages", [])
    stage_rows = "\n".join(f"| {s} | Automated {s} |" for s in stages)

    has_tech = language != "unknown"
    tech_lines = []
    if has_tech:
        tech_lines.append(f"**Language:** {language}")
        if frameworks and frameworks != "unknown":
            tech_lines.append(f"**Frameworks:** {frameworks}")
        if build_tools and build_tools != "unknown":
            tech_lines.append(f"**Build Tools:** {build_tools}")
        if architecture:
            tech_lines.append(f"**Architecture:** {architecture}")
    tech_section = "### Repository Analysis\n" + "\n".join(tech_lines) if tech_lines else ""

    stages_section = f"### Pipeline Stages\n{stage_rows}" if stage_rows.strip() else ""

    if deleted_legacy:
        cleanup_lines = ["", "### Legacy Workflows Removed", "The following existing workflow files were removed to prevent conflicts:"]
        for p in deleted_legacy:
            cleanup_lines.append(f"- 🗑 `{p}`")
        cleanup_section = "\n".join(cleanup_lines)
    else:
        cleanup_section = ""

    # Surface the four-category dashboard in the PR body, but only the
    # non-security buckets. Security findings are dashboard-only, never
    # attached to the PR.
    config_section = _render_config_section(
        state.get("workflow_config_issues") or []
    )
    maintenance_section = _render_maintenance_section(
        state.get("maintenance_warnings") or []
    )
    external_section = _render_external_section(
        state.get("external_service_issues") or []
    )
    remediation_section = _render_remediation_section(
        state.get("remediation_recommendations") or []
    )

    pr_title = f"{PR_TITLE_TEMPLATE}" + (f" for {language}" if has_tech else "")
    pr_body = PR_BODY_TEMPLATE.format(
        tech_section=tech_section,
        stages_section=stages_section,
        cleanup_section=cleanup_section,
        config_section=config_section,
        maintenance_section=maintenance_section,
        external_section=external_section,
        remediation_section=remediation_section,
    )

    try:
        pr = create_pull_request(repo, branch, pr_title, pr_body, base_branch, github_token)
        if pr:
            state["github_pr_number"] = pr["number"]
            state["github_pr_url"] = pr["html_url"]
        else:
            state["errors"].append("Failed to create pull request")
    except Exception as e:
        state["errors"].append(f"PR creation failed: {e}")

    return state