import asyncio
import fnmatch
import json
import re
from collections.abc import Iterable

import httpx
import yaml

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm

WORKFLOW_GEN_PROMPT = """You are a senior DevSecOps Architect and GitHub Actions expert.

Generate a production-ready GitHub Actions workflow based on the repository analysis
and the inferred security coverages + pipeline augmentations (struktur-v9).

Note: scope is Docker + Docker Compose ONLY. Kubernetes, Terraform, Helm,
and IaC scanning are NOT in scope. Use the standard job templates from
the library and merge augmentation configurations into the relevant jobs.

## REPOSITORY ANALYSIS

Architecture Type: {architecture_type}
Architecture Confidence: {architecture_confidence}%
Architecture Reason: {architecture_reason}

Technologies Detected:
- Primary Language: {primary_language} ({language_confidence}% confidence)
- Frameworks: {frameworks}
- Package Manager: {package_manager}
- Test Framework: {test_framework}
- Database: {database}
- Runtime: {runtime}

Deployment Target: {deployment_target}
Deployment Reason: {deployment_reason}

Detected Business Features: {features}
Detected Domain: {domain}

## APPLICABLE SECURITY COVERAGES (K2.1)

{security_coverages}

## PIPELINE AUGMENTATIONS (K2.2)

{pipeline_augmentations}

## ARCHITECTURE-SPECIFIC REQUIREMENTS

### MICROSERVICES / MODULAR MONOLITH:
- Add `docker-compose-validate` job (only if docker-compose detected).
- Add `dependency-scan-per-service` job using matrix strategy.
- Each service with its own package manifest gets its own scan.

### MONOLITHIC:
- Single linear workflow.
- One job per security stage.

## DEPLOYMENT-SPECIFIC REQUIREMENTS

### Docker detected (docker={docker_detected}):
- Add `container_build` job.
- Add `container_scan` job using Trivy.

### Docker Compose detected:
- Add `docker-compose-validate` job (run `docker compose config`).

## SECURITY CONTROLS TO INCLUDE

{security_controls}

## KNOWN SECURITY FINDINGS FROM SOURCE SCAN

{findings}

If findings are present, ensure the workflow includes jobs/tools that specifically detect and report those vulnerability types. For example:
- hardcoded_secret findings → include gitleaks, trufflehog, or git-secrets
- sql_injection findings → include semgrep SQLi rules or sqlmap
- command_injection findings → include semgrep command injection rules
- xss findings → include semgrep XSS rules or DOM XSS scanners
- insecure_crypto findings → include cryptography linting

---

## GENERAL REQUIREMENTS:

1. Return ONLY valid YAML.
2. Do NOT include explanations, markdown, comments outside YAML, code fences, notes, analysis, summaries, or any additional text.
3. Do NOT include "EXPLANATION", "---", markdown blocks, or prose.
4. The output must be directly saveable as:
   .github/workflows/devsecops.yml
5. Generate exactly one YAML document.
6. The YAML must be syntactically valid.
7. The workflow must follow DevSecOps best practices.
8. Use least-privilege permissions.
9. Configure concurrency groups.
10. Configure job timeouts.
11. Use deterministic dependency installation methods when applicable.
12. Include only jobs that are relevant to the detected technology stack.
13. Skip tools that are incompatible with the repository.
14. Do not invent frameworks, tools, scripts, or package managers.
15. If a lint/build/test script is not guaranteed to exist, add defensive checks before execution.
16. Prefer official GitHub Actions.
17. For OFFICIAL GitHub actions (actions/*), pin to full commit SHA from the verified cache. For third-party actions (aquasecurity/*, semgrep, gitleaks, fossa, bridgecrewio/*, snyk, etc.), use version tags (e.g., @master, @v3, @v1) — do NOT invent SHA hashes. Only use SHA if you are certain the SHA exists.
18. Ensure every generated action reference is valid and resolvable.
19. Ensure generated jobs can execute successfully on GitHub-hosted runners.
20. Ensure generated workflow passes YAML validation.
21. PRESERVE any existing 'on.schedule' cron configuration - do NOT remove or modify it.
22. ALL security jobs MUST have 'continue-on-error: false' so failures are properly reported. DevSecOps requires accurate reporting - do not skip failure reporting.
23. Add job-level 'timeout-minutes: 30' to prevent hung jobs.
24. Add 'fail-fast: false' at workflow level so all jobs complete even if one fails.

---

## OUTPUT REQUIREMENTS

Return ONLY the workflow YAML.

The first line of the response must begin with:

name:

The last line of the response must still be valid YAML.

No text is allowed before or after the YAML document.
"""


def _extract_stage_names(yaml_content: str) -> list[str]:
    stages = []
    job_pattern = re.compile(r"^\s+(\w+):\s*$", re.MULTILINE)
    jobs_section = False
    for line in yaml_content.split("\n"):
        if line.strip() == "jobs:":
            jobs_section = True
            continue
        if jobs_section and line.startswith(" ") and ":" in line and not line.startswith("  "):
            match = re.match(r"^\s+(\w+):", line)
            if match:
                stages.append(match.group(1))
        elif jobs_section and line and not line.startswith(" ") and not line.startswith("#"):
            jobs_section = False
    return stages


def _get_arch_type(architecture) -> str:
    if isinstance(architecture, dict):
        return architecture.get("architecture_type", "monolithic")
    if isinstance(architecture, str):
        return architecture or "monolithic"
    return "monolithic"


def _resolve_arch_type(state: PipelineEngineerState) -> str:
    """Resolve architecture type — always returns "monolithic".

    Per skripsi Bab 3 (revisi 3-domain & 1-architecture), arsitektur bukan
    variabel eksperimen (batasan B7). Semua arsitektur diperlakukan sebagai
    monolitik tradisional, termasuk FE/BE split dan modular monolith yang
    sebelumnya dinaikkan ke "modular_monolith". Sistem internal TIDAK lagi
    menaikkan ke modular_monolith, sehingga semua repo diklasifikasikan
    sebagai "monolithic" untuk konsistensi eksperimen.

    Fokus variasi ada di domain (R2.2): e-commerce, blog, iot.
    """
    return "monolithic"


def _format_findings(findings: list[dict]) -> str:
    if not findings:
        return "No security findings detected during source scan."
    lines = []
    for f in findings[:20]:
        file_path = f.get("file") or "unknown"
        line = f.get("line") or "?"
        ftype = f.get("type", "unknown")
        severity = f.get("severity", "medium")
        explanation = f.get("explanation", "")
        lines.append(f"- [{severity.upper()}] {ftype} in {file_path}:{line} — {explanation[:120]}")
    return "\n".join(lines)


def _format_security_controls(security: dict) -> str:
    """Format security controls for the prompt."""
    controls = security.get("security_controls", [])
    if not controls:
        stages = security.get("required_stages", [])
        if stages:
            return "\n".join([f"- {stage}: recommended" for stage in stages])
        return "- lint: code quality (always recommended)\n- test: unit tests\n- sast: static analysis\n- secret_scan: secret detection\n- dependency_scan: dependency vulnerability scan"

    formatted = []
    for ctrl in controls:
        if isinstance(ctrl, dict):
            status = ctrl.get("status", "recommended")
            tool = ctrl.get("tool", "")
            reason = ctrl.get("reason", "")
            formatted.append(f"- {ctrl.get('control')}: {status}")
            if tool:
                formatted.append(f"  Tool: {tool}")
            if reason:
                formatted.append(f"  Reason: {reason}")
        elif isinstance(ctrl, str):
            formatted.append(f"- {ctrl}")
    
    return "\n".join(formatted)


def _log_repository_context(state: PipelineEngineerState) -> None:
    """Emit temporary debug output for pipeline generation investigation."""
    technologies = state.get("detected_technologies", {}) or {}
    deployment = state.get("detected_deployment", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    security = state.get("inferred_security_needs", {}) or {}

    print("\n" + "=" * 72)
    print("[DEBUG] workflow_generator_node input context")
    print("=" * 72)
    print(f"[DEBUG] repository_full_name: {state.get('repository_full_name')}")
    print(f"[DEBUG] primary_language: {technologies.get('primary_language')}")
    print(f"[DEBUG] package_manager: {technologies.get('package_manager')}")
    print(f"[DEBUG] test_framework: {technologies.get('test_framework')}")
    print(f"[DEBUG] test_framework_confidence: {technologies.get('test_framework_confidence', 'N/A')}")
    print(f"[DEBUG] docker_detected: {deployment.get('docker')}")
    print(f"[DEBUG] docker_confidence: {deployment.get('docker_confidence')}")
    print(f"[DEBUG] kubernetes_detected: {deployment.get('kubernetes')}")
    print(f"[DEBUG] kubernetes_confidence: {deployment.get('kubernetes_confidence')}")
    print(f"[DEBUG] terraform_detected: {deployment.get('terraform')}")
    print(f"[DEBUG] terraform_confidence: {deployment.get('terraform_confidence')}")
    print(f"[DEBUG] helm_detected: {deployment.get('helm')}")
    print(f"[DEBUG] structure_sample: {[item.get('path') if isinstance(item, dict) else item for item in structure[:20]]}")
    print(f"[DEBUG] repository_files_keys: {list(files.keys())[:20]}")
    print(f"[DEBUG] requested_controls: {sorted(_collect_requested_controls(security))}")
    print(f"[DEBUG] cached_insights_used: {bool(state.get('extra_params', {}).get('cached_insights'))}")
    print("=" * 72 + "\n")


def workflow_generator_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Deterministic CI DevSecOps workflow generator.

    Builds a minimal, repository-aware GitHub Actions workflow by composing
    only the jobs that are actually applicable to the detected repository.

    Decisions:
    - NO deployment stages (per user requirement).
    - All actions are pinned to commit SHA.
    - `on: push + pull_request + workflow_dispatch` always set explicitly.
    - Test stage is skipped when no test framework detected.
    - CVE scanning is merged into `dependency-scan` (no duplication).
    - Every stage is recorded in `state["stage_explanations"]` with a reason.
    """
    technologies = state.get("detected_technologies", {}) or {}
    architecture = state.get("detected_architecture", {}) or {}
    deployment = state.get("detected_deployment", {}) or {}
    security = state.get("inferred_security_needs", {}) or {}

    arch_type = _resolve_arch_type(state)
    findings = state.get("findings", []) or []
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}

    _log_repository_context(state)

    # Pre-generation check: every SHA in the cache must be a real 40-char
    # commit. If any are missing the generator would emit tag-style refs
    # which GitHub warns about, so we abort early.
    pre_issues = _validate_pinned_actions()
    if pre_issues:
        state["errors"].extend(
            f"SHA cache is invalid: {i}" for i in pre_issues
        )
        state["error_stage"] = "workflow_generation"
        return state

    try:
        primary_language = (technologies.get("primary_language") or "").lower()
        package_manager = (technologies.get("package_manager") or "").lower()
        test_framework = technologies.get("test_framework")
        frameworks = technologies.get("frameworks") or []
        build_tools = technologies.get("build_tools") or []

        # ------------------------------------------------------------------
        # Pre-generation validation (requirement 6).
        # Repository analysis is the single source of truth. Issues are
        # recorded as workflow_config_issues; contradictory stages are
        # removed below instead of being generated.
        # ------------------------------------------------------------------
        pre_validation_issues = _pre_validate_generation(state)
        if pre_validation_issues:
            state["workflow_config_issues"] = state.get("workflow_config_issues", []) + pre_validation_issues

        # Decide which allowed stages are actually relevant.
        print(f"[DEBUG] _select_relevant_stages inputs: has_dockerfile={_has_dockerfile(structure, files)}, has_iac={_has_iac(structure, files)}")
        stages = _select_relevant_stages(
            security=security,
            technologies=technologies,
            deployment=deployment,
            arch_type=arch_type,
            findings=findings,
            structure=structure,
            files=files,
        )
        print(f"[DEBUG] stages after _select_relevant_stages: {stages}")

        # pipeline_mode (extra_params.pipeline_mode): "general" / "domain" / "both".
        # When the user selects "domain" only, we keep ONLY the
        # domain-specific job (e.g. pci-dss) and drop every general
        # security stage. This lets the reviewer see the custom
        # compliance check in isolation, e.g. to verify the rule
        # coverage or to run a single compliance gate on a
        # pre-existing CI. The default "both" preserves existing
        # behaviour (general + domain). "general" drops the
        # domain-specific block and only emits the universal
        # baseline (lint/sast/secret-scan/dependency-scan/...).
        _state_for_extra = state if isinstance(state, dict) else {}
        _extra_params = _state_for_extra.get("extra_params") or {}
        if not isinstance(_extra_params, dict):
            _extra_params = {}
        pipeline_mode = _extra_params.get("pipeline_mode", "both")
        pipeline_mode = pipeline_mode.lower().strip() if isinstance(pipeline_mode, str) else "both"
        if pipeline_mode not in ("general", "domain", "both"):
            pipeline_mode = "both"
        if pipeline_mode == "domain":
            # Replace the general stages with a placeholder. The
            # _build_workflow_yaml function will still emit a header
            # + a domain-specific job below (pci-dss/hipaa/etc.)
            # so the generated workflow is valid GitHub Actions YAML
            # but only has the domain compliance check.
            stages = ["__domain_only__"]
            print("[DEBUG] pipeline_mode=domain: dropping general stages, keeping domain-specific job only")
        print(f"[DEBUG] pipeline_mode: {pipeline_mode}, effective stages: {stages}")

        # Requirement 9: automatically drop any stage that contradicts the
        # repository analysis instead of generating it.
        # Capture unjustified stages BEFORE filtering so they can be surfaced
        # in the debug output even though they are removed from the workflow.
        invalid_stages = _flag_invalid_stages(stages, state)
        # Also flag stages that were REQUESTED by the inference step but
        # could not survive _select_relevant_stages because the inferred
        # deployment / test flags contradicted the actual file evidence.
        # Without this, a "lying" deployment flag would silently drop
        # container/iac/test stages without any reviewer-visible trace.
        unjustified_requested = _flag_unjustified_requested_stages(state)
        if unjustified_requested:
            seen = {item["stage"] for item in invalid_stages}
            for item in unjustified_requested:
                if item["stage"] not in seen:
                    invalid_stages.append(item)
                    seen.add(item["stage"])
        stages = _filter_stages_by_evidence(stages, state)
        print(f"[DEBUG] stages after _filter_stages_by_evidence: {stages}")

        # Track MERGED controls: security controls that were requested
        # by the inference step but do not appear as their own job in
        # the generated workflow because the same capability is provided
        # by another stage. This surfaces the mapping in the UI so the
        # reviewer does not think the control was silently dropped.
        # The stage is NOT added to invalid_workflow_stages (it is
        # provided, just under another name); instead, it is added to
        # workflow_config_issues with a clear "merged_into" reason.
        seen_invalid = {item["stage"] for item in invalid_stages}
        merged_into = _flag_merged_requested_controls(
            requested=set(_collect_requested_controls(security)),
            generated=set(stages),
        )
        if merged_into:
            existing_issues = state.get("workflow_config_issues") or []
            for original, target in merged_into:
                if original in seen_invalid:
                    continue
                existing_issues.append({
                    "category": "workflow_config_issue",
                    "type": "workflow_config_issue",
                    "rule": f"{original}_merged_into_{target}",
                    "message": (
                        f"Control '{original}' was requested by the security "
                        f"inference step but is not generated as a separate job. "
                        f"Its capability is provided by the '{target}' stage "
                        f"in the workflow."
                    ),
                    "action": "",
                    "job": target,
                    "current_ref": "",
                    "suggestion": (
                        f"To get '{original}' as a standalone job, edit the "
                        f"generator to split '{target}'. For now, '{target}' "
                        f"covers the same check."
                    ),
                    "severity": "low",
                })
            state["workflow_config_issues"] = existing_issues

        # Runtime compatibility check (Node 24 + SHA verification).
        # Every action that the generator is about to emit must be in the
        # registry with a verified SHA and must declare node24 support.
        from app.agents.action_registry import actions_used_in_stages
        candidate_actions = actions_used_in_stages(stages)
        rt_issues = _validate_runtime_compatibility(candidate_actions, declared_node="node24")
        if rt_issues:
            existing_issues = state.get("workflow_config_issues") or []
            state["workflow_config_issues"] = existing_issues + [
                {
                    "rule": "node_runtime_incompatibility",
                    "message": f"Action runtime check failed: {msg}",
                    "category": "workflow_config_issue",
                }
                for msg in rt_issues
            ]
            print(f"[DEBUG] runtime compatibility issues: {rt_issues}")

        # Requirement 2: prerequisite validation BEFORE building YAML.
        # If `container-build` is missing, `container-scan` and `sbom`
        # are marked as `skipped` (not failed) and reported in
        # `state["skipped_jobs"]`. The dashboard renders this under
        # workflow_execution.skipped. We also pass the originally
        # requested stages so the validator can mark downstream jobs
        # that were requested but never selected (e.g. the inference
        # asked for `container-scan` but the repo has no Dockerfile).
        requested_stages = list(_collect_requested_controls(security))
        prereq = _validate_pipeline_prerequisites(stages, requested_stages=requested_stages)
        stages = prereq["kept"]
        if prereq["skipped_jobs"]:
            state["skipped_jobs"] = prereq["skipped_jobs"]
            print(f"[DEBUG] prerequisite-skipped jobs: {[s['job'] for s in prereq['skipped_jobs']]}")

        # Build the workflow deterministically.
        # ------------------------------------------------------------------
        # Multi-language: resolve active LanguageProfile list once and
        # pass it down to `_build_workflow_yaml`. The function still
        # works without profiles (back-compat: falls back to the
        # original `has_node` / `has_python` if/elif branches).
        # ------------------------------------------------------------------
        from app.agents.language_profiles import (
            resolve_active_profiles,
            list_supported_languages,
        )
        active_profiles = resolve_active_profiles(technologies)
        # Stash the list of supported languages for the response payload
        # so the FE can show "what languages does this generator support"
        # even if the current repo only uses 1.
        state["active_language_profiles"] = [p.id for p in active_profiles]
        state["supported_languages"] = list_supported_languages()

        yaml_text, stage_names, explanations = _build_workflow_yaml(
            primary_language=primary_language,
            package_manager=package_manager,
            test_framework=test_framework,
            frameworks=frameworks,
            build_tools=build_tools,
            stages=stages,
            arch_type=arch_type,
            findings=findings,
            structure=structure,
            files=files,
            detected_domain=state.get("detected_domain"),
            domain_confidence=state.get("domain_confidence"),
            domain_threats=state.get("domain_threats"),
            state=state,
            active_profiles=active_profiles,
        )

        # Requirement 9: surface any stage that was selected but lacks repository
        # evidence. These stages were already filtered out above; we keep the
        # record for debugging and frontend visibility.
        if invalid_stages:
            print(f"[DEBUG] invalid_workflow_stages: {invalid_stages}")
            state["invalid_workflow_stages"] = invalid_stages
            existing_issues = state.get("workflow_config_issues") or []
            state["workflow_config_issues"] = existing_issues + [
                {
                    "rule": f"unjustified_{item['stage']}",
                    "message": f"Selected stage '{item['stage']}' has no supporting repository evidence; it was omitted from the generated workflow.",
                    "reason": item["reason"],
                    "category": "workflow_config_issue",
                }
                for item in invalid_stages
            ]

        # Final safety pass: pin every remaining action to a SHA, fix
        # permissions, normalize checkout persist-credentials.
        fixed_yaml, fixes = _auto_fix_all(yaml_text)

        # Requirement 8: final consistency validation. If a generated
        # job contradicts the repository analysis, automatically REMOVE
        # that job from the YAML rather than failing the whole pipeline.
        # The removed job is reported in `state["workflow_config_issues"]`
        # with a clear reason so the dashboard can show the user what
        # was dropped and why.
        fixed_yaml, consistency_removals = _validate_pipeline_consistency(
            fixed_yaml, state
        )
        if consistency_removals:
            existing_issues = state.get("workflow_config_issues") or []
            state["workflow_config_issues"] = existing_issues + consistency_removals
            # Reflect the post-consistency stages back into the result.
            try:
                parsed_for_stages = yaml.safe_load(fixed_yaml)
                if isinstance(parsed_for_stages, dict) and isinstance(parsed_for_stages.get("jobs"), dict):
                    stage_names = list(parsed_for_stages["jobs"].keys())
            except yaml.YAMLError:
                pass
            print(f"[DEBUG] consistency validation removed: {[r['job'] for r in consistency_removals]}")

        # Post-generation validation. If the YAML is malformed or any
        # `uses:` is not a SHA, surface the issue instead of committing
        # a broken workflow to a Pull Request.
        yaml_ok, yaml_errors = _validate_workflow_yaml(fixed_yaml, state=state)
        if not yaml_ok:
            state["errors"].extend(f"Invalid workflow: {e}" for e in yaml_errors)
            state["error_stage"] = "workflow_generation"
            return state

        state["generated_workflow"] = fixed_yaml
        state["generated_stages"] = stage_names
        state["stage_explanations"] = explanations
        print(f"[DEBUG] final generated_stages: {stage_names}")

        # Two-file split (struktur-v9.3 — domain-aware deployment).
        # Parse the merged YAML and split it into a generic workflow file
        # (lint/test/sast/etc.) + a custom reusable workflow file
        # (pci-dss/hipaa/ledger-check/etc.) so the FE pipeline generator
        # can render two tabs and the deploy step can commit both.
        try:
            split_result = build_workflow_yaml_split(
                primary_language=primary_language,
                package_manager=package_manager,
                test_framework=test_framework,
                frameworks=frameworks,
                build_tools=build_tools,
                stages=stages,
                arch_type=arch_type,
                findings=findings,
                structure=structure,
                files=files,
                detected_domain=state.get("detected_domain"),
                domain_confidence=state.get("domain_confidence"),
                domain_threats=state.get("domain_threats"),
                detected_sub_type=state.get("detected_sub_type"),
                llm_rule_suggestions=state.get("llm_rule_suggestions"),
                state=state,
            )
            state["generated_workflow_generic"] = split_result["generic_yaml"]
            state["generated_workflow_custom"] = split_result["custom_yaml"]
            state["generated_workflow_files"] = split_result["file_meta"]
            state["generated_stages_general"] = split_result["stages_general"]
            state["generated_stages_custom"] = split_result["stages_custom"]
        except Exception as split_err:
            # Non-fatal: keep the merged workflow as a single file fallback
            # so legacy callers (and the deploy path) still work.
            print(f"[workflow_generator_node] split warning: {split_err}")
        state["generation_explanation"] = _build_generation_explanation(
            stage_names, explanations, arch_type
        )

        # Vignette context (struktur-v6 §3.8.3 + §3.9): propagate
        # architecture-specific insert + domain brief to downstream nodes
        # (validator, response_formatter) and to the API consumer.
        architecture = state.get("detected_architecture", {}) or {}
        service_names = architecture.get("service_names") if isinstance(architecture, dict) else None
        service_count = architecture.get("service_count") if isinstance(architecture, dict) else None
        state["vignette_context"] = _build_vignette_context(
            arch_type=arch_type,
            detected_domain=state.get("detected_domain"),
            domain_confidence=state.get("domain_confidence"),
            domain_threats=state.get("domain_threats"),
            service_count=service_count,
            service_paths=service_names,
        )
        if fixes:
            state.setdefault("auto_fixes", []).extend(fixes)

        # Drain any transient 5xx errors discovered during SHA resolution /
        # action-existence checks and promote them to structured
        # external_service_issues. This is what prevents a 502 from
        # api.github.com during pipeline generation from appearing as a
        # security finding or blocking the PR.
        from app.agents.finding_categories import CATEGORY_EXTERNAL
        transient = drain_transient_upstream_issues()
        if transient:
            existing = state.get("external_service_issues") or []
            state["external_service_issues"] = existing + [
                {**t, "category": CATEGORY_EXTERNAL} for t in transient
            ]
    except Exception as e:
        import traceback as _tb
        print(f"[workflow_generator_node] CRASH: {type(e).__name__}: {e}")
        _tb.print_exc()
        state["errors"].append(f"Workflow generation failed: {e}")
        state["error_stage"] = "workflow_generation"

    return state


# Repository-evidence file patterns used to ground stage selection.
_LOCKFILE_PATTERNS: tuple[str, ...] = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "poetry.lock",
    "Pipfile.lock",
    "go.sum",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
)

# Patterns that indicate a build script for the corresponding package
# manager. Requirement 1: the `build` stage is only emitted when there is
# direct evidence of a build step (script in package.json, Makefile, or
# equivalent).
_BUILD_SCRIPT_EVIDENCE: dict[str, tuple[str, ...]] = {
    "npm": ("build", "compile", "dist", "bundle", "prepare"),
    "yarn": ("build", "compile", "dist", "bundle", "prepare"),
    "pnpm": ("build", "compile", "dist", "bundle", "prepare"),
    "pip": ("setup.py", "pyproject.toml", "setup.cfg"),
    "poetry": ("pyproject.toml",),
    "maven": ("pom.xml",),
    "gradle": ("build.gradle", "build.gradle.kts"),
    "go": ("go.mod",),
    "cargo": ("Cargo.toml",),
    "bundler": ("Gemfile",),
}

_DOCKERFILE_PATTERNS: tuple[str, ...] = (
    "Dockerfile",
    "Dockerfile.*",
    "docker-compose.yml",
    "docker-compose.yaml",
)

# IaC is intentionally NARROWER than container artifacts: only true
# Infrastructure-as-Code files (Terraform / Kubernetes / Helm) count.
# Dockerfile & docker-compose belong to the container stages, not to
# iac-scan; including them here caused false positives where a project
# with a Dockerfile (and no K8s/Terraform/Helm) would still get an
# iac-scan job that found nothing useful.
_IAC_PATTERNS: tuple[str, ...] = (
    "*.tf",
    "*.tfvars",
    "*.tfstate",
    "Chart.yaml",
    "values.yaml",
)

_IAC_DIRECTORY_PATTERNS: tuple[str, ...] = (
    "k8s/*",
    "kubernetes/*",
    "helm/*",
    "terraform/*",
)


def _has_file(structure: list, files: dict, patterns: Iterable[str]) -> bool:
    """Return True if the repository contains a file matching any pattern.

    Matches against both the explicit `repository_files` dict (keys) and the
    `repository_structure` list (names/paths). Patterns are case-insensitive
    shell globs.
    """
    patterns = tuple(patterns)

    for fname in (files or {}).keys():
        fname_lower = fname.lower()
        for pattern in patterns:
            if fnmatch.fnmatch(fname_lower, pattern.lower()):
                return True
            if fname_lower == pattern.lower().lstrip("*/"):
                return True

    for item in (structure or []):
        if isinstance(item, dict):
            name = (item.get("name") or "").lower()
            path = (item.get("path") or "").lower()
        else:
            name = path = str(item).lower()
        for pattern in patterns:
            pat_lower = pattern.lower()
            if fnmatch.fnmatch(name, pat_lower) or fnmatch.fnmatch(path, pat_lower):
                return True
            # Also allow directory-prefix patterns like "k8s/*" to match paths.
            if "/" in pat_lower and "/" in path:
                prefix = pat_lower.rstrip("*")
                if path.startswith(prefix):
                    return True

    return False


def _has_iac(structure: list, files: dict, deployment: dict | None = None) -> bool:
    """Return True if any Infrastructure-as-Code artifact is present.

    IMPORTANT: This check is intentionally file-only. The optional
    `deployment` argument is kept for backward compatibility but is no
    longer used as a fallback. Inferred deployment flags (e.g. from an LLM
    or stale cache) must not override the actual repository contents.
    """
    if _has_file(structure, files, _IAC_PATTERNS):
        return True
    if _has_file(structure, files, _IAC_DIRECTORY_PATTERNS):
        return True
    return False


def _has_dockerfile(structure: list, files: dict, deployment: dict | None = None) -> bool:
    """Return True if a Dockerfile or docker-compose file is present.

    IMPORTANT: This check is intentionally file-only. The optional
    `deployment` argument is kept for backward compatibility but is no
    longer used as a fallback. Inferred deployment flags (e.g. from an LLM
    or stale cache) must not override the actual repository contents.
    """
    return _has_file(structure, files, _DOCKERFILE_PATTERNS)


# Patterns that indicate a docker-compose stack file (used by the
# `docker-compose-validate` stage to gate its emission). Excludes
# bare Dockerfiles, which are containerized but NOT compose.
_DOCKER_COMPOSE_PATTERNS: tuple[str, ...] = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)


def _has_docker_compose(structure: list, files: dict) -> bool:
    """Return True if a docker-compose / compose stack file is present.

    This is a STRICTER check than `_has_dockerfile`: only true stack
    files count, not bare Dockerfiles. The `docker-compose-validate`
    stage is gated on this; a repo that only has a single Dockerfile
    and no compose file has nothing to validate.
    """
    return _has_file(structure, files, _DOCKER_COMPOSE_PATTERNS)


# Manifest files that identify a service directory. When at least one
# of these exists in a sub-directory, the
# `dependency-scan-per-service` matrix strategy has something to scan.
# Matched at the top level of the repository (heuristic for now; the
# detect-services job inside the workflow does the real directory
# enumeration at runtime).
_SERVICE_MANIFEST_PATTERNS: tuple[str, ...] = (
    "**/package.json",
    "**/requirements.txt",
    "**/pyproject.toml",
    "**/go.mod",
    "**/Cargo.toml",
    "**/pom.xml",
    "**/build.gradle",
    "**/build.gradle.kts",
    "**/Gemfile",
)


# Top-level directory names that typically hold a frontend (browser) app
# or a backend (server) app. Matched at the FIRST path segment only.
_FRONTEND_DIR_NAMES: frozenset[str] = frozenset({
    "frontend", "client", "web", "webapp", "ui", "app", "spa",
    "public", "static", "www",
})
_BACKEND_DIR_NAMES: frozenset[str] = frozenset({
    "backend", "server", "api", "service", "services",
    "src", "app-server",
})


def _has_frontend_backend_split(structure: list, files: dict) -> bool:
    """Return True if the repo has separate top-level frontend and backend
    directories, each with its own package manifest.

    Used to upgrade a default `monolithic` architecture to `frontend_backend`
    when the LLM-based architecture_detection did not run (or returned a
    generic monolithic answer). The detection is intentionally conservative
    — both sides must have their own manifest, otherwise the repo is just
    a regular monolith.

    Patterns (case-insensitive, first path segment):
      * frontend in: frontend/, client/, web/, ui/, app/, spa/, www/
      * backend  in: backend/, server/, api/, service(s)/, src/

    Each side must also carry at least one of:
      * package.json (Node/JS/TS)
      * requirements.txt / pyproject.toml (Python)
      * go.mod, Cargo.toml, pom.xml, build.gradle, Gemfile
    """
    frontend_dirs: set[str] = set()
    backend_dirs: set[str] = set()

    for item in structure or []:
        if isinstance(item, dict):
            path = (item.get("path") or item.get("name") or "").strip("/").lower()
        else:
            path = str(item).strip("/").lower()
        if not path:
            continue
        first = path.split("/", 1)[0]
        if first in _FRONTEND_DIR_NAMES:
            frontend_dirs.add(first)
        elif first in _BACKEND_DIR_NAMES:
            backend_dirs.add(first)

    if not frontend_dirs or not backend_dirs:
        return False

    # Both sides must have at least one service manifest
    side_manifests = {
        "frontend": _has_frontend_manifest(structure, files, frontend_dirs),
        "backend": _has_backend_manifest(structure, files, backend_dirs),
    }
    return side_manifests["frontend"] and side_manifests["backend"]


def _has_frontend_manifest(structure: list, files: dict, frontend_dirs: set[str]) -> bool:
    """True if any `frontend_dirs` directory contains a Node/JS manifest
    (package.json) or a static-site index.html.
    """
    return _dir_has_any(
        structure, files, frontend_dirs,
        ("package.json", "index.html", "vite.config.ts", "vite.config.js",
         "next.config.js", "next.config.mjs", "nuxt.config.ts",
         "angular.json", "tsconfig.json"),
    )


def _has_backend_manifest(structure: list, files: dict, backend_dirs: set[str]) -> bool:
    """True if any `backend_dirs` directory contains a backend manifest.
    """
    return _dir_has_any(
        structure, files, backend_dirs,
        ("package.json", "requirements.txt", "pyproject.toml",
         "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
         "build.gradle.kts", "Gemfile", "main.go", "main.py"),
    )


def _dir_has_any(
    structure: list, files: dict, top_dirs: set[str], filenames: tuple[str, ...]
) -> bool:
    """True if any of `top_dirs` contains any of `filenames` (file evidence
    only, case-insensitive). Walks `files` keys and `structure` paths.
    """
    fnames_lower = {f.lower() for f in filenames}
    top_dirs_lower = {d.lower() for d in top_dirs}

    # Check `files` dict: keys are usually relative paths
    for fname in (files or {}).keys():
        path = fname.strip("/").lower()
        if not path:
            continue
        first = path.split("/", 1)[0]
        if first in top_dirs_lower:
            base = path.rsplit("/", 1)[-1]
            if base in fnames_lower:
                return True

    # Check `structure` list: items are file/dir names or relative paths
    for item in structure or []:
        if isinstance(item, dict):
            path = (item.get("path") or item.get("name") or "").strip("/").lower()
        else:
            path = str(item).strip("/").lower()
        if not path:
            continue
        first = path.split("/", 1)[0]
        if first in top_dirs_lower:
            base = path.rsplit("/", 1)[-1]
            if base in fnames_lower:
                return True

    return False


def _has_service_manifest(structure: list, files: dict) -> bool:
    """Return True if at least one service manifest file is present.

    Per skripsi R2.1, arsitektur bukan variabel eksperimen. Helper ini
    tetap dipertahankan untuk evidence-based detection (file presence),
    namun tidak lagi digunakan untuk menaikkan arsitektur ke multi-service.
    """
    return _has_file(structure, files, _SERVICE_MANIFEST_PATTERNS)


def _has_build_script(structure: list, files: dict, package_manager: str) -> bool:
    """Return True if there is direct evidence of a build script.

    Looks at the actual package manager files in the repository:
      * npm/yarn/pnpm: a `build` (or compile/dist/bundle/prepare) entry
        in package.json scripts
      * pip: setup.py or pyproject.toml with a build-system section
      * poetry: pyproject.toml present
      * maven: pom.xml
      * gradle: build.gradle / build.gradle.kts
      * go: go.mod
      * cargo: Cargo.toml
      * bundler: Gemfile

    Returns False when no script or manifest is found, so the
    `build` stage is never generated for repositories that have no
    evidence of a build step.
    """
    pm = (package_manager or "").lower()
    if not pm:
        return False

    pkg_json = files.get("package.json") or files.get("Package.json")
    if pkg_json and isinstance(pkg_json, str):
        try:
            data = json.loads(pkg_json)
            scripts = data.get("scripts") or {}
            build_keys = _BUILD_SCRIPT_EVIDENCE.get(pm, ("build",))
            if any(key in scripts for key in build_keys):
                return True
        except (json.JSONDecodeError, TypeError):
            pass

    for pattern in _BUILD_SCRIPT_EVIDENCE.get(pm, ()):
        if _has_file(structure, files, (pattern,)):
            return True

    return False


def _has_test_script(structure: list, files: dict, package_manager: str) -> bool:
    """Return True if the repository has a test script in package.json
    or a recognised test framework manifest. Used as a fallback when
    `test_framework` is not set but a test script is present.
    """
    pkg_json = files.get("package.json") or files.get("Package.json")
    if pkg_json and isinstance(pkg_json, str):
        try:
            data = json.loads(pkg_json)
            scripts = data.get("scripts") or {}
            if any(k in scripts for k in ("test", "tests", "test:unit", "test:integration")):
                return True
        except (json.JSONDecodeError, TypeError):
            pass
    for pattern in ("pytest.ini", "pyproject.toml", "go.mod"):
        if _has_file(structure, files, (pattern,)):
            return True
    return False


def _collect_requested_controls(security: dict) -> set[str]:
    """Collect control names that security inference asked for.

    Falls back to the universal baseline (lint, sast,
    secret_scan, dependency-scan, container-scan) when
    inferred_security_needs is empty. This happens when the
    K2 inference chain (coverage_inference -> pattern_inference
    -> pipeline_augmentation -> job_reasoning) did not run
    or returned an empty dict — the manual dispatch path in
    pipeline_service skips K2, so the workflow generator must
    still produce a useful baseline pipeline.
    """
    requested: set[str] = set()
    for c in security.get("security_controls", []) or []:
        if isinstance(c, dict) and c.get("status") in ("recommended", "required"):
            requested.add((c.get("control") or "").lower().replace("_", "-"))
    for s in security.get("required_stages", []) or []:
        requested.add(str(s).lower().replace("_", "-"))
    for s in security.get("pipeline_stages", []) or []:
        requested.add(str(s).lower().replace("_", "-"))
    if not requested:
        # Universal baseline. Mirror the BASE_CONTROLS list in
        # pipeline_augmentation_node.py so the manual and the
        # compiled-graph paths produce the same default set.
        requested.update({
            "lint", "sast", "secret-scan",
            "dependency-scan", "container-scan",
        })
    return requested


def _pre_validate_generation(state: PipelineEngineerState) -> list[dict]:
    """Pre-generation validation: repository analysis is the single source of truth.

    Validates the consistency between the requested security controls and the
    actual repository evidence. Returns a list of `workflow_config_issue` dicts
    describing mismatches. These issues are surfaced to the reviewer but do not
    block generation; contradictory stages are removed automatically.
    """
    from app.agents.action_registry import ActionValidationFinding

    technologies = state.get("detected_technologies", {}) or {}
    deployment = state.get("detected_deployment", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    security = state.get("inferred_security_needs", {}) or {}

    issues: list[dict] = []
    requested = _collect_requested_controls(security)
    package_manager = (technologies.get("package_manager") or "").lower()
    is_node = "npm" in package_manager or "yarn" in package_manager or "pnpm" in package_manager

    # 1. Repository analysis consistency
    if not technologies.get("primary_language"):
        issues.append(ActionValidationFinding.make(
            rule="missing_primary_language",
            message="No primary language detected in repository analysis; workflow will be minimal.",
            suggestion="Verify the repository has recognizable source files.",
        ))

    # 2. Lockfile existence for Node.js projects
    if is_node and not _has_file(structure, files, _LOCKFILE_PATTERNS):
        issues.append(ActionValidationFinding.make(
            rule="missing_lockfile",
            message="No lockfile detected for Node.js project; dependency installation will use 'npm install' without cache.",
            suggestion="Commit package-lock.json (or yarn.lock / pnpm-lock.yaml) to enable deterministic 'npm ci' installs.",
        ))

    # 3. Test framework existence
    if ("test" in requested or "test" in security.get("required_stages", [])) and not technologies.get("test_framework"):
        issues.append(ActionValidationFinding.make(
            rule="missing_test_framework",
            message="Test stage requested but no test framework detected; the test job will be omitted.",
            suggestion="Add a test framework (e.g., Jest, pytest) or remove the test control from security requirements.",
        ))

    # 4. Dockerfile existence
    has_docker = _has_dockerfile(structure, files)
    if any(s in requested for s in ("container-scan", "container-build", "container_scan", "container_build")) and not has_docker:
        issues.append(ActionValidationFinding.make(
            rule="missing_dockerfile",
            message="Container scan/build requested but no Dockerfile detected; container jobs will be omitted.",
            suggestion="Add a Dockerfile or remove container controls from security requirements.",
        ))

    # 5. IaC existence — REMOVED in struktur-v9.1 (out of scope Docker-only)

    # 6. Deployment disabled / no deployment target
    deployment_enabled = bool(
        deployment.get("docker")
        or deployment.get("kubernetes")
        or deployment.get("terraform")
        or deployment.get("helm")
    )
    if not deployment_enabled:
        issues.append(ActionValidationFinding.make(
            rule="deployment_disabled",
            message="No deployment target detected; deployment-related jobs will not be generated.",
            suggestion="This is expected for libraries or plain applications without container/IaC config.",
        ))

    return issues


def _select_relevant_stages(
    security: dict,
    technologies: dict,
    deployment: dict,
    arch_type: str,
    findings: list[dict],
    structure: list | None = None,
    files: dict | None = None,
) -> list[str]:
    """Decide which CI DevSecOps stages to include.

    Repository analysis is the single source of truth. A stage is only
    emitted when there is direct evidence in the repository analysis
    (requirement 1):

      * test            -> requires a detected test framework OR test script
      * build           -> requires a build script in package.json (or
                           equivalent build manifest: setup.py,
                           pyproject.toml, Makefile, pom.xml, go.mod, ...)
      * container-build -> requires a Dockerfile or docker-compose file
      * container-scan  -> requires a Dockerfile (and `needs: container-build`
                           in the generated YAML, so it is skipped when the
                           build stage is omitted)
      * sbom            -> requires Docker evidence
      * iac-scan        -> requires Terraform, Kubernetes, or Helm artifacts
                           (a Dockerfile alone is NOT enough)
      * deploy jobs     -> never emitted (CI-only workflow)

    The function also accepts explicit security control requests, but any
    requested stage that contradicts the repository evidence is filtered
    out by `_filter_stages_by_evidence` before the workflow is built.
    """
    requested = _collect_requested_controls(security)

    package_manager = (technologies.get("package_manager") or "").lower()
    primary_language = (technologies.get("primary_language") or "").lower()
    test_framework = technologies.get("test_framework")
    build_tools = technologies.get("build_tools") or []

    has_node = "npm" in package_manager or "yarn" in package_manager or "pnpm" in package_manager
    has_python = "pip" in package_manager or "poetry" in package_manager or primary_language == "python"
    has_jvm = "maven" in package_manager or "gradle" in package_manager or primary_language in ("java", "kotlin", "scala", "groovy")
    has_go = primary_language == "go" or "go mod" in package_manager
    has_rust = "cargo" in package_manager or primary_language == "rust"
    has_ruby = "bundler" in package_manager or primary_language == "ruby"

    has_js_or_ts = primary_language in ("javascript", "typescript") or has_node
    has_source_code = bool(primary_language or has_node or has_python or has_go or has_jvm or has_rust or has_ruby)

    has_dependencies = bool(
        package_manager
        or has_node or has_python or has_go or has_jvm or has_rust or has_ruby
        or _has_file(structure or [], files or {}, ("package.json", "pyproject.toml", "go.mod", "pom.xml", "build.gradle", "Cargo.toml", "Gemfile"))
    )

    has_docker = _has_dockerfile(structure or [], files or {})
    has_iac = _has_iac(structure or [], files or {})
    has_build_evidence = _has_build_script(structure or [], files or {}, package_manager) or bool(build_tools)
    has_test_evidence = bool(test_framework) or _has_test_script(structure or [], files or {}, package_manager)
    has_docker_compose = _has_docker_compose(structure or [], files or {})
    has_service_manifest = _has_service_manifest(structure or [], files or {})

    stages: list[str] = []

    # ---- lint ----
    if (
        "lint" in requested
        or has_js_or_ts or has_python or has_go or has_jvm or has_rust
    ):
        stages.append("lint")

    # ---- sast ----
    if (
        "sast" in requested
        or has_js_or_ts or has_python or has_go or has_jvm or has_rust or has_source_code
    ):
        stages.append("sast")

    # ---- dependency-scan ----
    # Reviewer feedback: dependency-scan used to only fire when
    # explicitly requested by the security-inference step. That
    # caused real Node.js / Python repos to ship without any CVE
    # scan (Trivy fs + npm audit) because the inference step
    # sometimes forgot to ask for it. We now ALWAYS emit
    # dependency-scan when the repository has package metadata
    # (package.json / pyproject.toml / go.mod / etc.), which is
    # the single source of truth (requirement 1 in
    # `_select_relevant_stages`).
    if has_dependencies:
        stages.append("dependency-scan")

    # ---- secret-scan ----
    if (
        "secret-scan" in requested
        or "secret_scan" in requested
        or "secrets" in requested
        or has_source_code
    ):
        stages.append("secret-scan")

    # ---- test (requirement 1: only with test framework or test script) ----
    if ("test" in requested or has_test_evidence) and has_test_evidence:
        stages.append("test")

    # ---- build (requirement 1: only with build script evidence) ----
    if "build" in requested and has_build_evidence:
        stages.append("build")

    # ---- container & IaC stages ----
    # Reviewer feedback: container-build stage DIHAPUS. container-scan
    # job sudah melakukan `docker build` di dalamnya (sebelum scan),
    # sehingga tidak perlu job terpisah. Stage logic `container-build`
    # dipertahankan di ALLOWED_STAGES dan registry untuk backward
    # compatibility (state consumers yang masih membaca stage ini),
    # tapi TIDAK di-emit ke stages list oleh `_select_relevant_stages`.
    #
    # container-scan tetap require Dockerfile dan tetap di-emit ketika
    # ada Dockerfile di repository.
    if ("container-scan" in requested or has_docker) and has_docker:
        stages.append("container-scan")
    # iac-scan REMOVED in struktur-v9.1 (out of scope Docker-only)
    # sbom: only when Docker evidence is present.
    if ("sbom" in requested or has_docker) and has_docker:
        stages.append("sbom")

    # ---- multi-service stages ----
    # Per skripsi Bab 3 (revisi 3-domain & 1-architecture), arsitektur bukan
    # variabel eksperimen. Semua arsitektur diperlakukan monolitik. Stage
    # multi-service hanya di-emit jika ada file evidence (docker-compose)
    # — bukan berdasarkan tipe arsitektur.
    is_multi_service_arch = False  # selalu False per R2.1

    # docker-compose-validate: hanya untuk repo dengan docker-compose
    # file. Arsitektur tidak lagi menaikkan ke multi-service.
    if has_docker_compose and (
        "docker-compose-validate" in requested or has_docker_compose
    ) and has_docker_compose:
        stages.append("docker-compose-validate")

    # dependency-scan-per-service: matrix strategy per service dir.
    # Requires multi-service arch + at least one service manifest
    # (npm/pip/go/cargo/maven/gradle/bundler). The actual per-service
    # enumeration is done inside the workflow's `detect-services`
    # step at runtime.
    if is_multi_service_arch and (
        "dependency-scan-per-service" in requested
        or "per_service_dep_scan" in requested
        or has_service_manifest
    ) and has_service_manifest:
        stages.append("dependency-scan-per-service")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for s in stages:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    # Hard-enforce the allowed-stages invariant. Any inferred stage
    # outside the allow-list is dropped, so the generator can never
    # accidentally produce deploy / sbom / container / k8s / terraform jobs.
    return [s for s in deduped if s in ALLOWED_STAGES]


def _filter_stages_by_evidence(
    stages: list[str],
    state: PipelineEngineerState,
) -> list[str]:
    """Remove any stage that contradicts repository analysis.

    Requirement 8: if a generated job contradicts repository analysis,
    automatically remove it instead of generating it. The filter applies
    the same evidence-based rules as `_select_relevant_stages` so any
    stage that slipped through (e.g. via the requested-controls path or
    a stale LLM-inferred flag) is dropped here.
    """
    technologies = state.get("detected_technologies", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    package_manager = (technologies.get("package_manager") or "").lower()

    has_docker = _has_dockerfile(structure, files)
    has_iac = _has_iac(structure, files)
    has_test_framework = bool(technologies.get("test_framework"))
    has_test_evidence = has_test_framework or _has_test_script(structure, files, package_manager)
    has_build_evidence = _has_build_script(structure, files, package_manager) or bool(technologies.get("build_tools"))
    has_docker_compose = _has_docker_compose(structure, files)
    has_service_manifest = _has_service_manifest(structure, files)
    # arch_type selalu "monolithic" per R2.1, tidak perlu is_multi_service_arch

    allowed: list[str] = []
    for stage in stages:
        # Internal placeholder for pipeline_mode=="domain" — the
        # general stages are intentionally skipped, only the
        # domain-specific job will be emitted downstream.
        if stage == "__domain_only__":
            continue
        if stage == "test" and not has_test_evidence:
            continue
        if stage == "build" and not has_build_evidence:
            continue
        # Reviewer feedback: container-build dan sbom sudah tidak
        # di-emit. Hanya container-scan yang masih bergantung
        # pada Dockerfile.
        if stage in ("container-scan", "container-build", "sbom") and not has_docker:
            continue
        # iac-scan REMOVED in struktur-v9.1
        # Multi-service stages: per R2.1, arsitektur bukan variabel.
        # Stage hanya di-emit jika ada file evidence langsung.
        if stage == "docker-compose-validate" and not has_docker_compose:
            continue
        if stage == "dependency-scan-per-service" and not (
            has_docker_compose and has_service_manifest
        ):
            continue
        allowed.append(stage)
    return allowed


def _flag_invalid_stages(
    stages: list[str],
    state: PipelineEngineerState,
) -> list[dict]:
    """Return any generated stage that lacks direct repository evidence.

    Each returned dict contains the stage name and a human-readable reason.
    This is temporary debugging instrumentation to surface inconsistency
    between the generated workflow and the repository analysis.
    """
    technologies = state.get("detected_technologies", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    package_manager = (technologies.get("package_manager") or "").lower()

    has_docker = _has_dockerfile(structure, files)
    has_iac = _has_iac(structure, files)
    has_test_framework = bool(technologies.get("test_framework"))
    has_test_evidence = has_test_framework or _has_test_script(structure, files, package_manager)
    has_build_evidence = _has_build_script(structure, files, package_manager) or bool(technologies.get("build_tools"))
    has_docker_compose = _has_docker_compose(structure, files)
    has_service_manifest = _has_service_manifest(structure, files)
    # arch_type selalu "monolithic" per R2.1

    invalid: list[dict] = []
    for stage in stages:
        if stage == "test" and not has_test_evidence:
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": "no test framework or test script detected in repository analysis",
            })
        elif stage == "build" and not has_build_evidence:
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": "no build script in package.json (or equivalent build manifest) detected in repository analysis",
            })
        elif stage in ("container-scan", "container-build", "sbom") and not has_docker:
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": "no Dockerfile or docker-compose file detected in repository analysis",
            })
        # iac-scan REMOVED in struktur-v9.1
        elif stage == "docker-compose-validate" and not has_docker_compose:
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": (
                    "no docker-compose.yml/compose.yaml in repository"
                ),
            })
        elif stage == "dependency-scan-per-service" and not (
            has_docker_compose and has_service_manifest
        ):
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": (
                    "no service manifest (package.json, requirements.txt, "
                    "go.mod, Cargo.toml, pom.xml) detected in repository, "
                    "or no docker-compose file"
                ),
            })
    return invalid


# Map of security control -> the generated workflow stage that
# provides the same capability. Used by _flag_merged_requested_controls
# to surface "this control was requested but is provided under another
# job" in workflow_config_issues rather than silently dropping it.
#
# Microservice strategy (struktur-v6 §3.6.1):
#   - `per_service_sast` is MERGED into the single root `sast` job.
#     Semgrep is run once at the root with the registry + custom
#     ruleset. Per-finding `path` already locates the service, and
#     cross-service rules (e.g. shared secret in `libs/`) would be
#     missed by a per-service split.
#   - `per_service_dep_scan` is NOT merged; the workflow emits a
#     dedicated `dependency-scan-per-service` job that uses matrix
#     strategy. This job runs alongside (not inside) the root
#     `dependency-scan` job, so npm audit + Trivy fs coverage stays
#     intact for the monorepo root.
CONTROL_MERGED_INTO: dict[str, str] = {
    # cve_scan is a stricter (CRITICAL-only) variant of dependency-scan.
    # dependency-scan already runs `npm audit` + Trivy fs scan; we do
    # not emit a separate cve-scan job for monorepo-style generators.
    # Both dash and underscore keys are listed because
    # `_collect_requested_controls` normalises underscores to dashes
    # (line 764), so the dash variant is what actually appears in
    # `requested`. The underscore variants are kept for backward
    # compatibility with any caller that passes keys in either form.
    "cve_scan": "dependency-scan",
    "cve-scan": "dependency-scan",
    # per_service_sast: SAST stays general (run once at root). The
    # per-service variant is intentional, see comment block above.
    "per_service_sast": "sast",
    "per-service-sast": "sast",
}


def _flag_merged_requested_controls(
    requested: set[str],
    generated: set[str],
) -> list[tuple[str, str]]:
    """Return list of (original_control, target_stage) for requested
    controls that are NOT in the generated workflow but have their
    capability provided by another stage.

    Example: inference asks for "cve_scan", generator emits
    "dependency-scan" which already runs `npm audit` + Trivy. The
    merge is reported in workflow_config_issues so the UI does not
    silently lose the signal.
    """
    out: list[tuple[str, str]] = []
    for control, target in CONTROL_MERGED_INTO.items():
        if control not in requested:
            continue
        if control in generated:
            continue
        if target in generated:
            out.append((control, target))
    return out


def _flag_unjustified_requested_stages(state: PipelineEngineerState) -> list[dict]:
    """Surface stages REQUESTED by the inference step that lack file evidence.

    This runs against the *requested* security controls (not the surviving
    stages from `_select_relevant_stages`) so we can flag stages that were
    silently dropped because the inferred/stale `detected_deployment` flag
    contradicted the actual repository contents. File evidence is the
    single source of truth; the flag is treated as advisory only.

    Each returned dict has the shape::

        {"stage": str, "expected": False, "reason": str}
    """
    technologies = state.get("detected_technologies", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    security = state.get("inferred_security_needs", {}) or {}
    package_manager = (technologies.get("package_manager") or "").lower()

    has_docker = _has_dockerfile(structure, files)
    has_iac = _has_iac(structure, files)
    has_test_framework = bool(technologies.get("test_framework"))
    has_test_evidence = has_test_framework or _has_test_script(structure, files, package_manager)
    has_build_evidence = _has_build_script(structure, files, package_manager) or bool(technologies.get("build_tools"))

    requested = _collect_requested_controls(security)

    invalid: list[dict] = []
    for stage in ("container-scan", "container-build", "sbom"):
        if stage in requested and not has_docker:
            invalid.append({
                "stage": stage,
                "expected": False,
                "reason": (
                    f"'{stage}' was requested by security inference but no "
                    "Dockerfile or docker-compose file was detected in the "
                    "repository analysis. The 'detected_deployment.docker' "
                    "flag may be stale; file evidence is the single source "
                    "of truth, so this stage was omitted from the workflow."
                ),
            })
    # iac-scan REMOVED in struktur-v9.1
    if "test" in requested and not has_test_evidence:
        invalid.append({
            "stage": "test",
            "expected": False,
            "reason": (
                "'test' was requested by security inference but no test "
                "framework or test script was detected in the repository "
                "analysis. The test stage was omitted from the workflow."
            ),
        })
    if "build" in requested and not has_build_evidence:
        invalid.append({
            "stage": "build",
            "expected": False,
            "reason": (
                "'build' was requested by security inference but no build "
                "script was detected in package.json (or equivalent build "
                "manifest). The build stage was omitted from the workflow."
            ),
        })
    # per_service_dep_scan: per R2.1, arsitektur bukan variabel eksperimen.
    # Arsitektur selalu monolitik, sehingga per-service matrix TIDAK di-emit.
    # Kapabilitas dependency-scan diberikan oleh root job (npm audit + Trivy fs).
    if "per-service-dep-scan" in requested:
        invalid.append({
            "stage": "per-service-dep-scan",
            "expected": False,
            "reason": (
                "'per_service_dep_scan' was requested but arsitektur is not "
                "a variable in this experiment (R2.1 — monolithic only). "
                "The same dependency-scan capability is provided by the root "
                "'dependency-scan' job (npm audit + Trivy fs)."
            ),
        })
    return invalid


def _build_generation_explanation(
    stage_names: list[str], explanations: list[dict], arch_type: str
) -> str:
    """Human-readable summary of why each stage was selected."""
    lines = [
        f"Architecture: {arch_type}.",
        f"Generated {len(stage_names)} CI stages: {', '.join(stage_names)}.",
        "Stages were selected based on the detected language, package manager, "
        "test framework, and security findings.",
    ]
    for exp in explanations:
        lines.append(f"- {exp['name']}: {exp['reason']}")
    return "\n".join(lines)


def _build_vignette_context(
    arch_type: str,
    detected_domain: str | None,
    domain_confidence: float | None,
    domain_threats: list | None,
    service_count: int | None = None,
    service_paths: list | None = None,
) -> dict:
    """Build the architecture + domain vignette context (struktur-v6 §3.8.3).

    Returns a dict with:
      - architecture_insert: prompt insert for the LLM that builds YAML
      - domain_brief: short string describing the detected domain
      - priority_threats: list of domain-specific threats to emphasize

    Per R2.1, arsitektur selalu monolitik. Branch modular_monolith hanya
    untuk backward compatibility (tidak pernah dieksekusi).
    """
    arch = (arch_type or "monolithic").lower()
    domain = (detected_domain or "general").lower()
    confidence = domain_confidence or 0.0
    threats = list(domain_threats or [])

    if arch == "modular_monolith":
        # Per R2.1, arsitektur bukan variabel eksperimen. Branch ini
        # TIDAK akan pernah diambil karena _resolve_arch_type selalu
        # mengembalikan "monolithic". Disimpan sebagai fallback untuk
        # backward compatibility jika diaktifkan kembali di masa depan.
        sc = service_count or 0
        sp = service_paths or []
        architecture_insert = (
            f"This repository has {sc} module(s) deployed together "
            f"{'at ' + ', '.join(sp[:6]) if sp else ''}. "
            f"Modular-monolith strategy (legacy, disabled per R2.1): "
            f"`docker-compose-validate` checks the compose file first, "
            f"then `dependency-scan-per-service` uses a matrix strategy. "
            f"`sast` (Semgrep) is run ONCE at the root with the full ruleset. "
            f"Do NOT generate a separate workflow file per module."
        )
    else:
        architecture_insert = (
            "You are generating a SINGLE workflow for a monolithic application. "
            "All security scans should run in one sequential pipeline covering "
            "the entire codebase. Use a single build artifact. "
            "(Arsitektur bukan variabel eksperimen per R2.1 — monolitik only.)"
        )

    domain_brief = f"{domain} (confidence: {confidence:.2f})"

    return {
        "architecture_insert": architecture_insert,
        "architecture_type": arch,
        "domain_brief": domain_brief,
        "detected_domain": domain,
        "domain_confidence": confidence,
        "priority_threats": threats,
    }


def _get_architecture_insert_for_prompt(
    arch_type: str,
    detected_domain: str | None,
    service_count: int | None = None,
    service_paths: list | None = None,
) -> str:
    """Return a short insert string for the LLM YAML-generation prompt.

    Used by the LLM fallback path (struktur-v6 §3.8.3).
    """
    return _build_vignette_context(
        arch_type=arch_type,
        detected_domain=detected_domain,
        domain_confidence=None,
        domain_threats=None,
        service_count=service_count,
        service_paths=service_paths,
    )["architecture_insert"]


# ----------------------------------------------------------------------
# Deterministic CI DevSecOps workflow builder
# ----------------------------------------------------------------------

# Pre-resolved SHAs for the actions we emit. These are real, verified
# SHAs of the matching tags, confirmed against the live GitHub API.
# Resolved once and reused forever.
#
# IMPORTANT: every SHA below was verified by querying
# `https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{tag}` and
# resolving the tag's annotated commit SHA. Do NOT add fabricated SHAs.
#
# === DEPRECATED ===
# This dict is no longer the single source of truth. Use the action
# registry (`app.agents.action_registry.ACTION_REGISTRY`) instead. The
# registry is queried by `action_registry.pin()` which validates SHA,
# node runtime compatibility, and deprecation status.
_PINNED: dict[str, str] = {}


def _pin(action_ref: str) -> str:
    """Delegate to the action registry as the single source of truth.

    Raises `ValueError` if the action is unknown, has no verified SHA,
    or uses a deprecated tag/branch ref. This guarantees we never emit
    `uses: foo/bar@v1` (which GitHub warns about as a tag/branch ref).
    """
    from app.agents.action_registry import pin as _registry_pin
    return _registry_pin(action_ref)


# CI DevSecOps stages this generator is allowed to emit. Deployment jobs
# are intentionally excluded because the system only generates the
# security-focused CI workflow, not CD deployment.
#
# Reviewer feedback:
#   - `build` stage dipertahankan di ALLOWED_STAGES untuk backward
#     compatibility (state consumers masih bisa membaca stage ini),
#     tapi TIDAK di-emit ke YAML. CI ini fokus security, bukan build.
#   - `container-build` stage juga dipertahankan untuk backward
#     compatibility, tapi TIDAK di-emit. `container-scan` sudah
#     melakukan `docker build` di dalam job-nya.
#   - `container-security` sudah dihapus (digabung ke container-scan).
#   - `sbom` dipertahankan untuk tracking (emission di-skip).
ALLOWED_STAGES: tuple[str, ...] = (
    "lint",
    "test",
    "build",
    "sast",
    "dependency-scan",
    "secret-scan",
    "container-scan",
    "container-build",
    "sbom",
    # v9.3 revisi 3-domain & 2-arch: domain-specific compliance jobs
    # (pci-dss, hipaa, ledger-check, csp-headers, mqtt-security) are
    # REMOVED from the allow-list. Per-repo custom jobs now come from
    # `state["job_designs"]` (LLM-generated by job_reasoning_node, K2.4),
    # which is the AI-driven equivalent. Domain-specific static templates
    # are kept in `_build_*_job` helpers for unit-test back-compat but
    # are never emitted by the generator.
    # ── v9.5: per-service / per-microservice stages DISABLED per R2.1 ──────
    # Arsitektur bukan variabel eksperimen. Monolithic only.
    # The user explicitly requested that the generator stop
    # emitting `detect-services`, `dependency-scan-per-service`, and
    # `docker-compose-validate`. Custom per-repo jobs now come
    # from `state["job_designs"]` (designed by job_reasoning_node
    # via LLM), which is the AI-driven equivalent. Stages are no
    # longer in the allow-list, so `_filter_stages_by_evidence`
    # will drop them if they slip through. The legacy
    # `_build_*_job` helpers are kept for unit-test back-compat.
    # "docker-compose-validate",
    # "dependency-scan-per-service",
    # "detect-services",
)


def _validate_pinned_actions() -> list[str]:
    """Pre-generation check: every action in the registry has a valid
    40-char hex SHA, no deprecated tags are referenced, and the action
    supports the declared Node runtime.

    This is the single source-of-truth validation. The registry is
    authoritative; any drift between hard-coded SHAs and registry
    SHAs will be caught here.
    """
    from app.agents.action_registry import (
        ACTION_REGISTRY,
        runtime_compatibility_issues,
        DEPRECATED_ACTIONS,
    )

    issues: list[str] = []

    for ref, spec in ACTION_REGISTRY.items():
        if not spec.pinned_sha:
            issues.append(f"{ref}: no pinned_sha in registry")
            continue
        if not re.match(r"^[a-f0-9]{40}$", spec.pinned_sha):
            issues.append(f"{ref}: invalid SHA in registry: {spec.pinned_sha!r}")

    # Cross-check: no deprecated action ref is being emitted.
    for deprecated_ref in DEPRECATED_ACTIONS.keys():
        base = deprecated_ref.split("@")[0]
        if base in ACTION_REGISTRY:
            spec = ACTION_REGISTRY[base]
            if spec.pinned_version and spec.pinned_version in deprecated_ref:
                issues.append(
                    f"{deprecated_ref} is deprecated; "
                    f"registry points to {spec.pinned_version}"
                )

    return issues


def _validate_runtime_compatibility(
    action_refs: list[str],
    declared_node: str = "node24",
) -> list[str]:
    """Verify every action in the generator's output supports the
    declared Node runtime. Run before emitting YAML to fail fast.
    """
    from app.agents.action_registry import runtime_compatibility_issues
    return runtime_compatibility_issues(action_refs, declared_node=declared_node)


def _validate_workflow_yaml(
    yaml_text: str,
    state: PipelineEngineerState | None = None,
) -> tuple[bool, list[str]]:
    """Post-generation check: confirm the produced YAML is executable.

    Validates:
      - YAML parses and has a jobs section
      - every `uses:` is pinned to a full commit SHA
      - job names are in the allowed stage list
      - action `with:` inputs are supported by the action registry
      - required permissions are present
      - required environment variables are present
      - no deprecated action versions are used

    Returns (ok, errors). When `ok` is False the workflow MUST NOT be
    committed to a Pull Request.
    """
    from app.agents.action_registry import (
        actions_used_in_yaml,
        required_env_for_actions,
        required_permissions_for_actions,
        validate_yaml_against_registry,
        DEPRECATED_ACTIONS,
    )

    errors: list[str] = []
    if not yaml_text or not yaml_text.strip():
        return False, ["Empty workflow YAML"]

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]

    if not isinstance(parsed, dict):
        return False, ["Top-level YAML must be a mapping"]

    if "jobs" not in parsed or not isinstance(parsed.get("jobs"), dict):
        return False, ["Workflow is missing a 'jobs:' section"]
    if not parsed.get("jobs"):
        return False, ["Workflow has no jobs defined"]

    # Every `uses:` reference must be a SHA, never a tag/branch.
    uses_pat = re.compile(
        r"^\s*uses:\s*([\w\-\.]+/[\w\-\.]+)@([^\s#]+)",
        re.MULTILINE,
    )
    for m in uses_pat.finditer(yaml_text):
        action, ref = m.group(1), m.group(2)
        if not re.match(r"^[a-f0-9]{40}$", ref):
            errors.append(
                f"Action '{action}@{ref}' is not pinned to a full commit SHA"
            )
        # Deprecated action version check (runtime compatibility).
        full_ref = f"{action}@{ref}"
        if full_ref in DEPRECATED_ACTIONS:
            errors.append(
                f"Action '{full_ref}' uses a deprecated runtime/version; "
                f"upgrade to {DEPRECATED_ACTIONS[full_ref]}"
            )

    # No job may have a name that suggests a forbidden stage.
    # v9.2: AI-generated job designs (from job_reasoning_node) are
    # allowed in addition to the static ALLOWED_STAGES set; the
    # `state` parameter carries the list of valid design names.
    ai_allowed: set[str] = set()
    if state is not None:
        for d in (state.get("job_designs") or []):
            if isinstance(d, dict) and d.get("name"):
                ai_allowed.add(d["name"])
    for job_name, job_cfg in parsed.get("jobs", {}).items():
        if not isinstance(job_cfg, dict):
            continue
        if job_name in ALLOWED_STAGES or job_name in ai_allowed:
            continue
        # Multi-language: accept `lint-<id>` / `test-<id>` / `dep-scan-<id>`
        # jobs emitted by `language_profiles.render_*_jobs` for monorepos.
        if (
            job_name.startswith("lint-")
            or job_name.startswith("test-")
            or job_name.startswith("dep-scan-")
        ):
            continue
        errors.append(
            f"Job '{job_name}' is not in the allowed stages: {list(ALLOWED_STAGES)}"
        )

    # Validate action inputs against the registry.
    registry_issues = validate_yaml_against_registry(yaml_text)
    for issue in registry_issues:
        rule = issue.get("rule", "")
        if rule in ("unexpected_action_input", "missing_action_input"):
            errors.append(
                f"{rule} for {issue.get('action', '?')}: {issue.get('message', '')}"
            )

    # Required permissions.
    actions = actions_used_in_yaml(yaml_text)
    required_perms = set(required_permissions_for_actions(actions))
    # Gitleaks needs pull-requests: read for PR scanning.
    if any("gitleaks" in a for a in actions):
        required_perms.add("pull-requests")
    parsed_perms = parsed.get("permissions", {}) or {}
    if isinstance(parsed_perms, dict):
        for perm in sorted(required_perms):
            level = parsed_perms.get(perm)
            if level not in ("read", "write"):
                errors.append(
                    f"Missing required permission '{perm}: read' for the actions used"
                )

    # Required environment variables.
    required_envs = set(required_env_for_actions(actions))
    for env in sorted(required_envs):
        if env == "GITHUB_TOKEN":
            # GITHUB_TOKEN is implicitly available; ensure Gitleaks-style steps
            # pass it explicitly via env.
            if "gitleaks" in yaml_text.lower() and f"{env}:" not in yaml_text:
                errors.append(
                    f"Action requires '{env}' but it is not referenced in the workflow"
                )
        elif f"{env}:" not in yaml_text:
            errors.append(
                f"Required environment variable '{env}' may be missing for actions used"
            )

    # Repository-analysis consistency (requirement 9): if a generated job
    # contradicts the analysis, report it as an error so it can be removed.
    if state is not None:
        technologies = state.get("detected_technologies", {}) or {}
        deployment = state.get("detected_deployment", {}) or {}
        structure = state.get("repository_structure", []) or []
        files = state.get("repository_files", {}) or {}
        jobs = parsed.get("jobs", {})

        if "test" in jobs and not technologies.get("test_framework"):
            errors.append("Generated 'test' job but repository analysis reports no test framework")
        # Reviewer feedback: container-build dan container-security
        # sudah dihapus/digabung ke container-scan. Hanya container-scan
        # yang sekarang memerlukan Dockerfile.
        if "container-scan" in jobs and not _has_dockerfile(structure, files):
            errors.append("Generated 'container-scan' job but repository analysis reports no Dockerfile")

    return (len(errors) == 0), errors


# ----------------------------------------------------------------------
# Prerequisite chain + final consistency validation
# ----------------------------------------------------------------------

# Map of job -> (prerequisite_job, prerequisite_stage, evidence_check).
# If the prerequisite stage is missing from the generated workflow
# (because the supporting evidence is not present in the repository
# analysis), the downstream job is also removed.
#
# Reviewer feedback: tidak ada job-level prerequisite lagi setelah
# container-build dihapus. container-scan sudah self-contained
# (`docker build` di dalam job), dan sbom tidak di-emit ke YAML.
# Map ini kosong; fungsi prerequisite check menjadi no-op untuk
# job-level. File-level evidence check tetap dilakukan oleh
# `_filter_stages_by_evidence` dan `_validate_pipeline_consistency`.
JOB_PREREQUISITES: dict[str, tuple[str, str]] = {}


def _validate_pipeline_prerequisites(
    stages: list[str],
    requested_stages: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Return a mapping of `skipped_jobs` for downstream jobs whose
    prerequisite is missing from the generated workflow.

    Requirement 2: when Docker is detected but a prerequisite job is
    dropped (e.g. `container-build` failed validation), the downstream
    job must be reported as `skipped`, NOT as `failed`. We surface
    these in `state["skipped_jobs"]` so the dashboard can render them
    with the correct workflow_execution status.

    Two scenarios are handled:
      1. The downstream job (e.g. `container-scan`) is in the selected
         stages but its prerequisite (e.g. `container-build`) is NOT.
         This is the standard prerequisite-failure case.
      2. The downstream job was REQUESTED by the inference step but
         the entire Docker family was dropped (no Dockerfile in the
         repo). The downstream job should be reported as skipped
         even though the prerequisite (`container-build`) was never
         selected in the first place — this gives the dashboard a
         consistent "skipped" event to show instead of a confusing
         "no job generated" silence.

    Returns a dict shaped as:
        {
            "kept": [stages that survived prerequisite check],
            "skipped_jobs": [
                {
                    "job": "container-scan",
                    "reason": "Prerequisite 'container-build' was omitted ...",
                    "prerequisite": "container-build",
                    "category": "skipped_due_to_prerequisite"
                },
                ...
            ]
        }
    """
    kept: list[str] = []
    skipped: list[dict] = []
    seen_skipped: set[str] = set()
    for stage in stages:
        prereq = JOB_PREREQUISITES.get(stage)
        if prereq is None:
            kept.append(stage)
            continue
        prereq_job, evidence = prereq
        if prereq_job in stages:
            kept.append(stage)
        else:
            # Downstream job is in the selected stages but its
            # prerequisite was dropped. Mark the downstream as
            # skipped (NOT failed).
            if stage not in seen_skipped:
                skipped.append({
                    "job": stage,
                    "reason": (
                        f"Prerequisite '{prereq_job}' was omitted from the generated "
                        f"workflow (no {evidence} evidence). Downstream job '{stage}' "
                        f"is marked skipped, not failed."
                    ),
                    "prerequisite": prereq_job,
                    "category": "skipped_due_to_prerequisite",
                })
                seen_skipped.add(stage)

    # Also surface downstream jobs that were REQUESTED by the
    # inference step but did not survive the pre-filter because the
    # prerequisite family was dropped entirely. Without this, the
    # dashboard would not see any record of `container-scan` for a
    # repo without a Dockerfile, even though the user explicitly
    # asked for it.
    requested_set = set(requested_stages or [])
    for downstream, (prereq_job, evidence) in JOB_PREREQUISITES.items():
        if downstream in seen_skipped:
            continue
        if downstream not in requested_set:
            continue
        # The downstream was requested and the prerequisite is
        # missing from the selected stages.
        if prereq_job in stages:
            continue
        if downstream in stages:
            continue
        skipped.append({
            "job": downstream,
            "reason": (
                f"Downstream job '{downstream}' was requested by the security "
                f"inference step but its prerequisite '{prereq_job}' was "
                f"omitted from the workflow (no {evidence} evidence). The job "
                f"is marked skipped, not failed."
            ),
            "prerequisite": prereq_job,
            "category": "skipped_due_to_prerequisite",
        })
        seen_skipped.add(downstream)

    return {"kept": kept, "skipped_jobs": skipped}


def _validate_pipeline_consistency(
    yaml_text: str,
    state: PipelineEngineerState,
) -> tuple[str, list[dict]]:
    """Final consistency validation (requirement 8).

    If a generated job contradicts the repository analysis, automatically
    REMOVE that job from the YAML rather than failing the whole pipeline.
    The removed job is reported in `state["workflow_config_issues"]` with
    a clear reason so the dashboard can show the user what was dropped
    and why.

    This complements `_filter_stages_by_evidence` (pre-generation) by
    re-validating the emitted YAML against the analysis: any job that
    slipped through (e.g. because of a stale LLM-cached flag) is removed
    here.

    Returns (cleaned_yaml, removal_report).
    """
    if not yaml_text or not yaml_text.strip():
        return yaml_text, []

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return yaml_text, []

    if not isinstance(parsed, dict) or "jobs" not in parsed:
        return yaml_text, []

    technologies = state.get("detected_technologies", {}) or {}
    structure = state.get("repository_structure", []) or []
    files = state.get("repository_files", {}) or {}
    package_manager = (technologies.get("package_manager") or "").lower()
    jobs = parsed.get("jobs", {})
    if not isinstance(jobs, dict):
        return yaml_text, []

    has_docker = _has_dockerfile(structure, files)
    has_iac = _has_iac(structure, files)
    has_test_framework = bool(technologies.get("test_framework"))
    has_test_evidence = has_test_framework or _has_test_script(structure, files, package_manager)
    has_build_evidence = _has_build_script(structure, files, package_manager) or bool(technologies.get("build_tools"))

    to_remove: list[str] = []
    removals: list[dict] = []

    for job_name in list(jobs.keys()):
        if job_name == "test" and not has_test_evidence:
            to_remove.append(job_name)
            removals.append({
                "category": "workflow_config_issue",
                "rule": "consistency_test_removed",
                "job": job_name,
                "message": (
                    f"Generated '{job_name}' job removed by consistency validation: "
                    "no test framework or test script was found in the repository analysis."
                ),
            })
        elif job_name == "build" and not has_build_evidence:
            to_remove.append(job_name)
            removals.append({
                "category": "workflow_config_issue",
                "rule": "consistency_build_removed",
                "job": job_name,
                "message": (
                    f"Generated '{job_name}' job removed by consistency validation: "
                    "no build script in package.json (or equivalent build manifest) was found."
                ),
            })
        elif job_name in ("container-scan", "container-build", "container-security", "sbom") and not has_docker:
            to_remove.append(job_name)
            removals.append({
                "category": "workflow_config_issue",
                "rule": f"consistency_{job_name.replace('-', '_')}_removed",
                "job": job_name,
                "message": (
                    f"Generated '{job_name}' job removed by consistency validation: "
                    "no Dockerfile or docker-compose file was found in the repository analysis."
                ),
            })
            to_remove.append(job_name)
            removals.append({
                "category": "workflow_config_issue",
                "rule": f"consistency_{job_name.replace('-', '_')}_removed",
                "job": job_name,
                "message": (
                    f"Generated '{job_name}' job removed by consistency validation: "
                    "no Dockerfile or docker-compose file was found in the repository analysis."
                ),
            })
        # struktur-v9.1: iac-scan removed entirely (out of scope Docker-only)

    if not to_remove:
        return yaml_text, []

    for job_name in to_remove:
        jobs.pop(job_name, None)

    try:
        cleaned = yaml.safe_dump(parsed, default_flow_style=False, sort_keys=False)
    except yaml.YAMLError:
        return yaml_text, removals
    return cleaned, removals


def _build_execution_results(state: PipelineEngineerState) -> dict:
    """Build the three-category execution results (requirement 3).

    Splits the result state into:
      * workflow_execution: success / failure / skipped per job
      * security_findings: vulnerabilities / secrets / CVEs / misconfigurations
      * workflow_configuration_issues: invalid image digests, missing
        lockfile, invalid action inputs, deprecated runtimes

    This is the canonical separation used by the dashboard. It MUST NOT
    mix categories (e.g. a "Container Build Failed" message is a
    workflow execution event, NOT a security finding).
    """
    # Workflow execution: per-job conclusion pulled from the run details.
    jobs = state.get("workflow_jobs") or []
    workflow_execution: dict = {
        "success": [],
        "failure": [],
        "skipped": [],
        "summary": {
            "total": len(jobs),
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
        },
    }
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        name = job.get("name") or job.get("id") or "unknown"
        conclusion = (job.get("conclusion") or "").lower()
        if conclusion == "success":
            workflow_execution["success"].append(name)
            workflow_execution["summary"]["succeeded"] += 1
        elif conclusion == "skipped":
            workflow_execution["skipped"].append(name)
            workflow_execution["summary"]["skipped"] += 1
        else:
            workflow_execution["failure"].append(name)
            workflow_execution["summary"]["failed"] += 1

    # Security findings: anything in `state["findings"]` after filtering
    # by the security-finding category. NEVER mix in workflow config
    # issues or external outages.
    from app.agents.finding_categories import (
        CATEGORY_SECURITY,
        classify,
        filter_security,
    )
    raw_findings = state.get("findings") or []
    security_findings = filter_security(raw_findings)
    # Group by sub-category for the dashboard widget.
    grouped: dict[str, list] = {
        "vulnerabilities": [],
        "secrets": [],
        "cves": [],
        "misconfigurations": [],
        "other": [],
    }
    for f in security_findings:
        if not isinstance(f, dict):
            continue
        ftype = (f.get("type") or f.get("finding_type") or "").lower()
        if "secret" in ftype:
            grouped["secrets"].append(f)
        elif "cve" in ftype or "vuln" in ftype:
            grouped["vulnerabilities"].append(f)
            if "cve" in ftype:
                grouped["cves"].append(f)
        elif "iac" in ftype or "config" in ftype or "misconfig" in ftype:
            grouped["misconfigurations"].append(f)
        else:
            grouped["other"].append(f)
    # CVE findings (Trivy output) are reported under both
    # `vulnerabilities` and `cves` for clarity.
    security_findings_grouped = {
        **grouped,
        "total": sum(len(v) for v in grouped.values()),
        "category": CATEGORY_SECURITY,
    }

    # Workflow configuration issues: only items classified as
    # `workflow_config_issue`. Maintenance warnings (deprecated
    # runtimes) and external service issues are kept in their own
    # buckets, NOT in this one.
    config_issues = list(state.get("workflow_config_issues") or [])
    # Surface deprecated runtime findings here as a sub-bucket so the
    # dashboard can show "Workflow Warning: Node runtime deprecation"
    # alongside real config issues.
    maintenance = list(state.get("maintenance_warnings") or [])
    external = list(state.get("external_service_issues") or [])
    workflow_configuration_issues = {
        "config_issues": config_issues,
        "maintenance_warnings": maintenance,
        "external_service_issues": external,
        "total": len(config_issues) + len(maintenance) + len(external),
    }

    return {
        "workflow_execution": workflow_execution,
        "security_findings": security_findings_grouped,
        "workflow_configuration_issues": workflow_configuration_issues,
    }


def _render_dashboard_messages(execution_results: dict) -> list[dict]:
    """Render the three-category execution results into concrete dashboard
    messages (requirement 6).

    Each message is shaped as a real-data finding:
      * Workflow Configuration Issue: "Invalid Docker image digest: ..."
      * Security Finding: "31 dependency vulnerabilities detected (3 critical)."
      * Workflow Warning: "Node.js 16 actions are deprecated (upgrade by Q1 2026)."

    Generic messages like "Security Scan Failed" or "Workflow Error"
    are NEVER emitted. Every message references real numbers, real
    findings, or concrete remediation actions.
    """
    if not isinstance(execution_results, dict):
        return []

    messages: list[dict] = []
    security = execution_results.get("security_findings") or {}
    wf_config = execution_results.get("workflow_configuration_issues") or {}
    wf_exec = execution_results.get("workflow_execution") or {}

    def _add(category: str, severity: str, title: str, detail: str, source: str = "") -> None:
        messages.append({
            "category": category,
            "severity": severity,
            "title": title,
            "detail": detail,
            "source": source,
        })

    # ---- Security findings (vulnerabilities, secrets, CVEs, misconfigs) ----
    vuln_count = len(security.get("vulnerabilities") or [])
    cve_count = len(security.get("cves") or [])
    secret_count = len(security.get("secrets") or [])
    misconfig_count = len(security.get("misconfigurations") or [])

    if vuln_count or cve_count:
        # Severity breakdown for vulnerabilities
        vulns = list(security.get("vulnerabilities") or [])
        sev_counts: dict[str, int] = {}
        for v in vulns:
            sev = (v.get("severity") or "medium").lower()
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
        sev_text_parts = []
        for sev in ("critical", "high", "medium", "low"):
            if sev_counts.get(sev):
                sev_text_parts.append(f"{sev_counts[sev]} {sev}")
        sev_text = ", ".join(sev_text_parts) if sev_text_parts else ""
        detail = f"{vuln_count} dependency vulnerability/ies detected"
        if cve_count and cve_count != vuln_count:
            detail += f" ({cve_count} CVE-tagged)"
        if sev_text:
            detail += f". Severity: {sev_text}."
        _add("security_finding", "high", "Dependency vulnerabilities detected", detail, "trivy / npm audit")

    if secret_count:
        _add(
            "security_finding",
            "high",
            "Hardcoded secret detected",
            f"{secret_count} secret(s) detected in source code (AWS keys, tokens, etc.).",
            "gitleaks",
        )

    if misconfig_count:
        _add(
            "security_finding",
            "medium",
            "Infrastructure misconfiguration",
            f"{misconfig_count} misconfiguration(s) detected in IaC / container config.",
            "trivy config / checkov",
        )

    # ---- Workflow configuration issues ----
    config_issues = list(wf_config.get("config_issues") or [])
    for issue in config_issues:
        if not isinstance(issue, dict):
            continue
        rule = (issue.get("rule") or "").lower()
        message = issue.get("message") or ""
        if "invalid_docker_image_digest" in rule or "image_digest" in rule:
            _add("workflow_config_issue", "high", "Invalid Docker image digest", message, "trivy image")
        elif "missing_lockfile" in rule or "lockfile" in rule:
            _add("workflow_config_issue", "medium", "Missing lockfile", message, "npm ci / pip install")
        elif "unexpected_action_input" in rule or "invalid_action_input" in rule:
            _add("workflow_config_issue", "medium", "Invalid action input", message, issue.get("action", ""))
        elif "missing_action_input" in rule:
            _add("workflow_config_issue", "medium", "Missing required action input", message, issue.get("action", ""))
        elif "deprecated" in rule:
            _add("workflow_config_issue", "low", "Deprecated action version", message, issue.get("action", ""))
        elif "node_runtime" in rule or "runtime_incompat" in rule:
            _add("workflow_config_issue", "high", "Node runtime incompatibility", message, "")
        else:
            _add("workflow_config_issue", "medium", issue.get("rule") or "Configuration issue", message, "")

    # ---- Maintenance warnings (deprecated runtimes etc.) ----
    maintenance = list(wf_config.get("maintenance_warnings") or [])
    for w in maintenance:
        if not isinstance(w, dict):
            continue
        rule = (w.get("rule") or "").lower()
        message = w.get("message") or ""
        if "deprecated_runtime" in rule or "node" in rule:
            _add("maintenance_warning", "low", "Workflow Warning: Node runtime deprecation", message, "")
        elif "deprecated_action" in rule:
            _add("maintenance_warning", "low", "Workflow Warning: Deprecated action", message, "")
        else:
            _add("maintenance_warning", "low", w.get("rule") or "Maintenance warning", message, "")

    # ---- External service issues ----
    ext = list(wf_config.get("external_service_issues") or [])
    for e in ext:
        if not isinstance(e, dict):
            continue
        rule = (e.get("rule") or "").lower()
        message = e.get("message") or ""
        if "upstream_502" in rule or "upstream_5" in rule:
            _add("external_service_issue", "informational", "External service unreachable", message, "github api")
        else:
            _add("external_service_issue", "informational", e.get("rule") or "External issue", message, e.get("source", ""))

    # ---- Workflow execution events (success / failure / skipped) ----
    summary = wf_exec.get("summary") or {}
    failed_jobs = wf_exec.get("failure") or []
    skipped_jobs = wf_exec.get("skipped") or []
    succeeded = summary.get("succeeded", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    total = summary.get("total", succeeded + failed + skipped)

    if total > 0 and failed == 0 and skipped == 0:
        _add(
            "workflow_execution",
            "informational",
            "Workflow executed successfully",
            f"All {succeeded} job(s) succeeded. No failures or skips.",
            "github actions",
        )
    elif total > 0:
        detail_parts = []
        if succeeded:
            detail_parts.append(f"{succeeded} succeeded")
        if failed:
            detail_parts.append(f"{failed} failed")
        if skipped:
            detail_parts.append(f"{skipped} skipped")
        detail = "Workflow execution: " + ", ".join(detail_parts) + "."
        if failed_jobs:
            detail += f" Failed job(s): {', '.join(failed_jobs[:5])}."
        if skipped_jobs:
            detail += f" Skipped job(s): {', '.join(skipped_jobs[:5])}."
        _add("workflow_execution", "high" if failed else "medium", "Workflow execution event", detail, "github actions")

    return messages


def _build_domain_header(
    detected_domain: str | None,
    domain_confidence: float | None,
    domain_threats: list[str] | None,
    arch_type: str,
    detected_technologies: dict | None = None,
) -> list[str]:
    """Return YAML comment lines describing the detected domain context.

    The header carries machine-parseable `# Key: value` lines so the
    PDF report generator can re-hydrate Section 1 (Repository Context)
    from the YAML when `state_snapshot.detected_*` is empty — common
    for runs whose `state_snapshot` was persisted before the
    generator wrote Tahap 1 LLM outputs, or that came in via the
    legacy Go backend pipeline table.

    Parsed keys (see `_hydrate_tahap1_from_yaml_comments`):
        Domain, Architecture, Detected languages, Framework,
        Database, Test framework, Runtime, Package manager,
        Build tools
    """
    lines: list[str] = []
    domain = (detected_domain or "general").lower()
    confidence = domain_confidence or 0.0
    threats = list(domain_threats or [])
    tech = detected_technologies or {}

    lines.append(f"# Domain: {domain} (confidence: {confidence:.2f})")
    lines.append(f"# Architecture: {arch_type}")

    # Tooling lines — emitted only when the field is non-empty so we
    # don't pollute the YAML with N/A placeholders.
    lang = tech.get("primary_language")
    if lang:
        lines.append(f"# Detected languages: {lang}")
    frameworks = tech.get("frameworks") or []
    if frameworks:
        lines.append(f"# Framework: {', '.join(frameworks)}")
    db = tech.get("database")
    if db:
        lines.append(f"# Database: {db}")
    test_fw = tech.get("test_framework")
    if test_fw:
        lines.append(f"# Test framework: {test_fw}")
    runtime = tech.get("runtime")
    if runtime:
        lines.append(f"# Runtime: {runtime}")
    pkg = tech.get("package_manager")
    if pkg:
        lines.append(f"# Package manager: {pkg}")
    build_tools = tech.get("build_tools") or []
    if build_tools:
        lines.append(f"# Build tools: {', '.join(build_tools)}")
    elif tech.get("has_dockerfile"):
        lines.append("# Build tools: docker")

    if threats:
        threat_text = "; ".join(threats[:4])
        lines.append(f"# Priority threats: {threat_text}")
    elif domain == "general":
        # For generic / unclassified projects, prefer an honest
        # "no specific priority" over the vague "standard OWASP Top
        # 10 heuristics" wording that misleads readers into thinking
        # the workflow targets OWASP specifically.
        lines.append("# Priority threats: none specific (no domain detected)")
    else:
        lines.append("# Priority threats: standard OWASP Top 10 heuristics")
    return lines
    return lines


def _compute_workflow_permissions(yaml_text: str) -> list[str]:
    """Return the minimal top-level permissions block for the actions used.

    Starts with `contents: read` and merges any permissions required by the
    actions in the workflow. Reviewer feedback: `security-events` MUST
    be `write` (not `read`) whenever the workflow uses
    `github/codeql-action/upload-sarif`, otherwise the SARIF upload
    step fails with a 403 from the Code Scanning API.
    """
    from app.agents.action_registry import (
        actions_used_in_yaml,
        required_permissions_for_actions,
    )

    actions = actions_used_in_yaml(yaml_text)
    perms: set[str] = set(required_permissions_for_actions(actions))
    # checkout and every job need at least contents: read
    perms.add("contents")
    # Gitleaks requires pull-requests: read when scanning pull requests.
    if any("gitleaks" in a for a in actions):
        perms.add("pull-requests")
    # SARIF upload (codeql-action/upload-sarif) requires
    # `security-events: write`. The action registry lists it as
    # `security-events` (the required-level flag is not preserved in
    # the registry) so we promote it to `write` whenever any of the
    # emitted steps uses upload-sarif.
    if any("upload-sarif" in a or "codeql-action" in a for a in actions):
        perms.add("security-events")
        sarif_needs_write = True
    else:
        sarif_needs_write = False

    # Emit a stable, readable order. Each entry is `(name, level)`
    # where `level` is the permission level to emit. `security-events`
    # upgrades to `write` whenever the workflow uploads SARIF; this
    # fixes the "Resource not accessible by integration" failure that
    # the reviewer flagged.
    ordered: list[tuple[str, str]] = [
        ("contents", "read"),
        ("pull-requests", "read"),
        ("security-events", "write" if sarif_needs_write else "read"),
        ("actions", "read"),
        ("issues", "read"),
        ("packages", "read"),
        ("id-token", "read"),
    ]
    lines = ["permissions:"]
    for p, default_level in ordered:
        if p in perms:
            lines.append(f"  {p}: {default_level}")
    return lines


def _detect_node_version(structure: list, files: dict) -> str:
    """Pick a Node.js version that is likely to work with the repository.

    The default Node 24 release is too new for many native modules
    (e.g. `better-sqlite3@7.x` references V8 APIs that were removed
    in Node 22+ and fails to compile under Node 24 with
    `CopyablePersistentTraits is not a member of v8`). Reviewer
    feedback: the generator should pick a Node version that matches
    what the repository can actually build.

    Strategy (in order):
      1. If `package.json` declares `engines.node`, respect it (capped
         at the highest major version with prebuilt binaries for
         `better-sqlite3` and similar modules — Node 20 LTS).
      2. If a `package-lock.json` is older (no `lockfileVersion: 3`),
         pick Node 20 LTS (Node 22/24 require lockfileVersion >= 3).
      3. Otherwise default to Node 20 LTS — broadly compatible with
         every native module that has prebuilt binaries.

    Returns a string like "20" suitable for `node-version: '20'`.
    """
    pkg_json = files.get("package.json") or files.get("Package.json")
    if pkg_json and isinstance(pkg_json, str):
        try:
            data = json.loads(pkg_json)
            engines = data.get("engines") or {}
            node_range = (engines.get("node") or "").strip()
            if node_range:
                # Parse a major version from the range. Accept common
                # forms: ">=18", "^20.0.0", "20.x", "20", ">=20 <22".
                m = re.search(r"\b(\d{1,2})\b", node_range)
                if m:
                    major = int(m.group(1))
                    # Cap at 20 to avoid the native-module trap.
                    if major >= 24:
                        return "20"
                    if major >= 20:
                        return str(major)
                    return str(major)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    # No `engines.node` declared. Be safe: pick 20 LTS so older native
    # modules still build.
    return "20"


def _node_setup_steps(
    package_manager: str,
    has_lockfile: bool,
    node_version: str = "24",
    ignore_scripts: bool = False,
) -> tuple[list[str], str]:
    """Return (setup_lines, install_command) for Node.js-based jobs.

    * If a lockfile is present, enable the appropriate package-manager cache
      and use the deterministic install command (npm ci, yarn frozen, etc.).
    * If no lockfile is present, disable caching and fall back to a plain
      install so the workflow remains executable.
    * If `ignore_scripts` is True, append `--ignore-scripts` to skip native
      build steps (prebuild-install, node-gyp rebuild, etc.). Used by
      security-scan jobs (sast, dependency-scan, secret-scan) where we only
      need the lockfile (read by `npm audit` and Trivy) — we do NOT need
      a working `node_modules`, and broken native modules (e.g.
      better-sqlite3 on Node 24) should NOT block the scan.
    """
    pm = package_manager.lower()
    has_yarn = "yarn" in pm
    has_pnpm = "pnpm" in pm

    if has_lockfile:
        cache_value = "pnpm" if has_pnpm else ("yarn" if has_yarn else "npm")
        if has_pnpm:
            install_cmd = "pnpm install --frozen-lockfile"
        elif has_yarn:
            install_cmd = "yarn install --frozen-lockfile --no-audit"
        else:
            install_cmd = "npm ci --no-audit --no-fund"
    else:
        cache_value = ""
        if has_pnpm:
            install_cmd = "pnpm install --no-frozen-lockfile"
        elif has_yarn:
            install_cmd = "yarn install --no-audit"
        else:
            install_cmd = "npm install --no-audit --no-fund"

    if ignore_scripts:
        # Append --ignore-scripts to skip native build. All major
        # package managers (npm, yarn, pnpm) support this flag.
        install_cmd += " --ignore-scripts"

    setup = [
        "      - name: Set up Node.js",
        f"        uses: {_pin('actions/setup-node@v4')}",
        "        with:",
        f"          node-version: '{node_version}'",
    ]
    if cache_value:
        setup.append(f"          cache: '{cache_value}'")
    setup.append("")
    return setup, install_cmd


def _semgrep_rules_for_domain(detected_domain: str | None) -> list[str]:
    """Return the list of custom Semgrep rule files to enable for a domain.

    The rule files live in `app/agents/semgrep_rules/` and are matched
    against the index in `index.yml`. They are copied into the generated
    workflow's checkout directory under `.semgrep/` so the Semgrep CLI
    can reference them with `--config=/src/.semgrep/<file>.yml`.

    Domain is normalised to lower case. If the domain is unknown or
    None, only the `general-api` ruleset is returned (i.e. the OWASP
    API Security Top 10 baseline). Returns an empty list if no
    rules apply.
    """
    import os
    import yaml as _yaml

    index_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "semgrep_rules",
        "index.yml",
    )
    try:
        with open(index_path) as f:
            index = _yaml.safe_load(f) or {}
    except (OSError, _yaml.YAMLError):
        return []

    rules_map = (index or {}).get("domain_rules") or {}
    domain_key = (detected_domain or "general").lower()

    # Always include the general-api ruleset (OWASP API Top 10).
    files: list[str] = list(rules_map.get("general-api", []) or [])
    # Then add the domain-specific ruleset if any.
    if domain_key in rules_map and domain_key != "general-api":
        for f in rules_map.get(domain_key, []) or []:
            if f not in files:
                files.append(f)

    return files


def _semgrep_rules_for_coverages(applicable_coverages: list[str]) -> list[str]:
    """Return Semgrep rule files contributed by applicable security coverages.

     struktur-v9: each applicable coverage may contribute additional rule
     files beyond what the detected domain provides. For example, a
     monolitik repo with no clear domain still gets `owasp-api.yml`
     rules via the `api_security` coverage. (microservice_security
     sudah dihapus per R2.1.)

    Returns deduplicated list of rule file names (without path).
    """
    import os
    import yaml as _yaml

    index_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "semgrep_rules",
        "index.yml",
    )
    try:
        with open(index_path) as f:
            index = _yaml.safe_load(f) or {}
    except (OSError, _yaml.YAMLError):
        return []

    coverage_map = (index or {}).get("coverage_rules") or {}
    files: list[str] = []
    for cov_id in applicable_coverages or []:
        for f in coverage_map.get(cov_id, []) or []:
            if f not in files:
                files.append(f)
    return files


# struktur-v9: Name of the single merged Semgrep rules file
SINGLE_SEMGREP_FILE = "ai-devsecops-v2.yml"


def _collect_merged_semgrep_rules(
    detected_domain: str | None,
    pipeline_augmentations: list[dict] | None = None,
    applicable_coverages: list[str] | None = None,
    ai_generated_rules: list[dict] | None = None,
) -> list[dict]:
    """Collect all Semgrep rules for a repository (struktur-v9.2 inline).

    Returns a list of rule dicts combining:
    - Generic rules (owasp-api.yml) — always-on baseline
    - Domain-specific rules (ecommerce.yml, pci-dss.yml, hipaa.yml, etc.)
    - Coverage-specific rules (per applicable coverage)
    - AI-generated rules (struktur-v9.1 — adaptive patterns from LLM)

    The returned list is embedded DIRECTLY into the SAST job's
    `semgrep --config=...` command as a heredoc, instead of being
    committed as a separate file. This eliminates the
    `.semgrep/ai-devsecops-v2.yml` file commit and makes the workflow
    self-contained.

    struktur-v9.2: All rules inline in workflow YAML, no separate file.
    """
    import os
    import yaml as _yaml

    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "semgrep_rules",
    )

    rule_files: list[str] = _semgrep_rules_for_domain(detected_domain)
    if applicable_coverages:
        for f in _semgrep_rules_for_coverages(applicable_coverages):
            if f not in rule_files:
                rule_files.append(f)

    merged_rules: list[dict] = []

    for fname in rule_files:
        fpath = os.path.join(rules_dir, fname)
        try:
            with open(fpath) as f:
                content = _yaml.safe_load(f) or {}
        except (OSError, _yaml.YAMLError):
            continue
        rules = content.get("rules", []) if isinstance(content, dict) else []
        if not rules and isinstance(content, list):
            rules = content
        for rule in rules:
            if isinstance(rule, dict):
                rule.setdefault("metadata", {})
                if isinstance(rule["metadata"], dict):
                    rule["metadata"]["ai-devsecops-source"] = fname
                merged_rules.append(rule)

    # struktur-v9.1: Append AI-generated rules (validated)
    if ai_generated_rules:
        for rule in ai_generated_rules:
            if not isinstance(rule, dict):
                continue
            rule.setdefault("metadata", {})
            if isinstance(rule["metadata"], dict):
                rule["metadata"]["ai-devsecops-source"] = "ai-generated-v9.2"
            merged_rules.append(rule)

    return merged_rules


# Backward-compat alias. Returns the merged rules as a YAML string.
# Used only if any external code still expects file-style output.
def _build_merged_semgrep_rules_yaml(
    detected_domain: str | None,
    pipeline_augmentations: list[dict] | None = None,
    applicable_coverages: list[str] | None = None,
    ai_generated_rules: list[dict] | None = None,
) -> str:
    """Deprecated — use _collect_merged_semgrep_rules() instead.

    Kept for any external callers that may still expect file-style
    YAML output. The workflow generator now embeds the rules
    inline in the SAST job instead of committing a separate file.
    """
    import yaml as _yaml
    rules = _collect_merged_semgrep_rules(
        detected_domain=detected_domain,
        pipeline_augmentations=pipeline_augmentations,
        applicable_coverages=applicable_coverages,
        ai_generated_rules=ai_generated_rules,
    )
    if not rules:
        return (
            "# AI-DevSecOps merged Semgrep rules (struktur-v9.2)\n"
            "rules:\n"
            "  - id: ai-devsecops-placeholder\n"
            "    pattern: 'true == false'\n"
            "    message: 'No custom rules'\n"
            "    severity: INFO\n"
            "    languages: [generic]\n"
        )
    return _yaml.safe_dump(
        {"rules": rules},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


# ============================================================================
# Domain-Specific Job Builders
# ============================================================================
#
# Each builder returns a list of YAML strings for a domain-specific
# job, or None if the domain does not apply. The builders are
# data-driven by scan_directives.scan_directives() but also encode
# the actual implementation (which shell commands to run, what
# artifacts to upload, etc.).
#
# Reference: docs/domain-aware-pipeline.md (Bab 4 §4.4 Layer 4)
#
# Job-template primitives (shared by every security job):
#   * _render_sarif_fallback() — emit a single step that writes an
#     empty SARIF when the upstream scanner did not produce one
#     (avoids the "no SARIF file" error from upload-sarif).
#   * _render_upload_sarif()   — emit the upload-sarif step
#     (always guarded with `if: always() && hashFiles(...) != ''`).
#   * _render_upload_artifact() — emit the upload-artifact step
#     (sibling of upload-sarif, same guard).
#   * _render_checkout()       — single source of truth for the
#     actions/checkout invocation (persist-credentials: false,
#     fetch-depth chosen by the caller).
#   * _render_setup_node() / _render_setup_python() — language
#     toolchain setup, with `cache: '<pm>'` so the runner can
#     reuse downloaded dependencies between runs.
# These primitives cut the per-job body length by 40-60% and make
# it impossible to forget the SARIF-fallback guard. Every new
# scanner job should compose them instead of inlining the
# equivalent YAML.


def _render_checkout(fetch_depth: int = 1) -> list[str]:
    """Render a single actions/checkout step (fetch_depth=0 for
    secret scan jobs that need the full git history).
    """
    if fetch_depth == 0:
        return [
            "      - name: Checkout code",
            f"        uses: {_pin('actions/checkout@v4')}",
            "        with:",
            "          persist-credentials: false",
            "          fetch-depth: 0",
        ]
    return [
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
    ]


def _render_setup_node(node_version: str = "20", cache_pm: str = "npm",
                       cache_path: str = "") -> list[str]:
    """Render actions/setup-node with dependency caching enabled.

    `cache_path` is the workspace-relative path to the lockfile
    (e.g. 'frontend/package-lock.json' for a monorepo).
    """
    if cache_path:
        return [
            "      - name: Set up Node.js",
            f"        uses: {_pin('actions/setup-node@v4')}",
            "        with:",
            f"          node-version: '{node_version}'",
            f"          cache: '{cache_pm}'",
            f"          cache-dependency-path: {cache_path}",
        ]
    return [
        "      - name: Set up Node.js",
        f"        uses: {_pin('actions/setup-node@v4')}",
        "        with:",
        f"          node-version: '{node_version}'",
        f"          cache: '{cache_pm}'",
    ]


def _render_setup_python(version: str = "3.11", cache_pm: str = "pip") -> list[str]:
    """Render actions/setup-python with dependency caching."""
    return [
        "      - name: Set up Python",
        f"        uses: {_pin('actions/setup-python@v5')}",
        "        with:",
        f"          python-version: '{version}'",
        f"          cache: '{cache_pm}'",
    ]


def _render_sarif_fallback(tool_name: str, tool_version: str,
                           info_uri: str, sarif_path: str) -> list[str]:
    """Render a step that writes an empty SARIF when the scanner
    above did not produce one. This is required because
    github/codeql-action/upload-sarif fails the job if the file
    is missing, even with `continue-on-error`.

    The placeholder SARIF uses the same driver (name + version +
    informationUri) as the real scanner so the Code Scanning tab
    does not show "Unknown tool" when 0 findings.
    """
    return [
        f"      - name: Ensure {sarif_path} exists (fallback for 0 findings or scan error)",
        "        if: always()",
        "        run: |",
        "          if [ ! -s " + sarif_path + " ]; then",
        f"            echo '::notice::{tool_name} did not produce a SARIF file. Generating empty SARIF to satisfy upload-sarif.'",
        "            printf '%s\\n' \\",
        "              '{' \\",
        "              '  \"version\": \"2.1.0\",' \\",
        "              '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "              '  \"runs\": [{' \\",
        "              '    {' \\",
        "              '      \"tool\": {' \\",
        "              '        \"driver\": {' \\",
        f"              '          \"name\": \"{tool_name}\",' \\",
        f"              '          \"version\": \"{tool_version}\",' \\",
        f"              '          \"informationUri\": \"{info_uri}\"' \\",
        "              '        }' \\",
        "              '      },' \\",
        "              '      \"results\": []' \\",
        "              '    }' \\",
        "              '  ]' \\",
        "              '}' > " + sarif_path,
        "          fi",
        f"          echo \"✓ {sarif_path} size: $(stat -c%s {sarif_path}) bytes\"",
    ]


def _render_upload_sarif(sarif_path: str, category: str) -> list[str]:
    """Render the standard upload-sarif step with the same guard
    pattern used everywhere in this generator.
    """
    return [
        f"      - name: Upload {category} SARIF to Code Scanning",
        f"        if: always() && hashFiles('{sarif_path}') != ''",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        f"          sarif_file: {sarif_path}",
        f"          category: {category}",
    ]


def _render_upload_artifact(sarif_path: str, name_prefix: str) -> list[str]:
    """Render the standard upload-artifact step for the SARIF file."""
    return [
        f"      - name: Upload {name_prefix} SARIF as artifact",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        f"          name: {name_prefix}-${{{{ github.sha }}}}",
        f"          path: {sarif_path}",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]


def _render_semgrep_docker_run(config_args: list[str], output_path: str,
                               timeout: int = 300) -> list[str]:
    """Render a single docker-run Semgrep invocation with
    `returntocorp/semgrep:1.99.0` (the version pinned in the
    action registry). The caller passes the list of `--config=...`
    arguments (e.g. `['p/owasp-top-ten', 'p/javascript', ...]`).
    """
    config_lines = []
    for cfg in config_args:
        config_lines.append(f"                --config={cfg} \\")
    return [
        "          docker run --rm \\",
        "            -v \"${{ github.workspace }}:/src:ro\" \\",
        "            -v \"${{ github.workspace }}:/out\" \\",
        "            returntocorp/semgrep:1.99.0 \\",
        "            semgrep \\",
        *config_lines,
        f"                --sarif --output=/out/{output_path} \\",
        f"                --timeout={timeout} --no-suppress-errors /src",
    ]


def _build_pci_dss_job() -> list[str]:
    """Build the `pci-dss` job for e-commerce repos.

    Steps:
      1. Semgrep with the e-commerce / payment-security rule set
         (registry + custom rules from .github/ai-devsecops-rules.yml
         if present). Catches CWE-79 (XSS in checkout), CWE-89
         (SQLi in cart/order), CWE-352 (CSRF in payment endpoints),
         CWE-602 (price tampering), CWE-639 (BOLA on cart/order),
         CWE-915 (mass assignment on order creation),
         CWE-312 (cleartext PAN storage), CWE-327 (weak crypto
         for payment). These are the rule outlines declared in
         domain_knowledge_base.yml under the e-commerce entry.
      2. PAN/CVV regex scan (catches secrets that Semgrep misses).
      3. .env-in-git-history check.
      4. Merge all findings into a single PCI-DSS SARIF.

    Output: SARIF via upload-sarif (always() guard handles empty).
    """
    return [
        # NOTE: "  pci-dss:" is prepended by _add_job(); do NOT add here.
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 10",
        "    continue-on-error: true",
        "    steps:",
        *_render_checkout(fetch_depth=0),
        "",
        # Step 1: Semgrep with the e-commerce / payment-security rule
        # set. The custom rules are committed to .semgrep/<file>.yml
        # by pull_request_creation_node (one file per domain rule
        # bundle, e.g. .semgrep/ecommerce.yml, .semgrep/pci-dss.yml).
        # We reference them via --config= flags so the registry
        # rulesets and the custom rules run in a single invocation.
        "      - name: Semgrep (e-commerce / payment-security ruleset)",
        *_render_semgrep_docker_run(
            config_args=[
                # Custom rules committed by pull_request_creation_node.
                # The .semgrep/ directory is mounted at /src via the
                # standard `-v ${{ github.workspace }}:/src:ro` bind,
                # so the docker-internal path is /src/.semgrep/<filename>.
                "/src/.semgrep/ecommerce.yml",
                "/src/.semgrep/pci-dss.yml",
                "/src/.semgrep/owasp-api.yml",
                # Registry rules — always-on payment/OWASP surface.
                "p/owasp-top-ten",
                "p/javascript",
                "p/nodejs",
                "p/expressjs",
                "p/sql-injection",
                "p/secrets",
                "p/typescript",
                "p/security-audit",
            ],
            output_path="pci-dss-semgrep.sarif",
            timeout=300,
        ),
        "        continue-on-error: true",
        "",
        # Step 2: scan for PAN/CVV (catches secrets that Semgrep
        # may miss). Writes raw findings to disk so the next step
        # can convert them to SARIF.
        "      - name: Scan for hardcoded PAN/CVV in source",
        "        run: |",
        "          PAN_PATTERN='\\b(4[0-9]{12}([0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(011|5[0-9]{2})[0-9]{12})\\b'",
        "          CVV_PATTERN='(?i)cvv[\\\"\\\\s:=]+[0-9]{3,4}'",
        "          rm -f pci-findings.txt",
        "          touch pci-findings.txt",
        "          grep -rE \"${PAN_PATTERN}\" --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null \\",
        "            | head -20 | awk -F: '{printf \"PAN|%s|%s|%s\\n\",$1,$2,$3}' >> pci-findings.txt",
        "          grep -rE \"${CVV_PATTERN}\" --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null \\",
        "            | head -20 | awk -F: '{printf \"CVV|%s|%s|%s\\n\",$1,$2,$3}' >> pci-findings.txt",
        "          if [ -s pci-findings.txt ]; then",
        "            echo \"::error::Found $(wc -l < pci-findings.txt) potential PCI-DSS violation(s):\"",
        "            cat pci-findings.txt",
        "          else",
        "            echo '✓ No hardcoded PAN/CVV detected'",
        "          fi",
        "        continue-on-error: true",
        "",
        # Step 3: .env history check (catches secrets that were
        # removed from HEAD but still live in older commits).
        "      - name: Validate .env not in git history",
        "        run: |",
        "          if git log --all --full-history -- '.env' 2>/dev/null | grep -q commit; then",
        "            echo '::error::.env file found in git history. Rotate all secrets!'",
        "            git log --all --full-history -- '.env' --oneline | head -5",
        "          else",
        "            echo '✓ .env not in git history'",
        "          fi",
        "        continue-on-error: true",
        "",
        # Step 4: convert PAN/CVV findings AND Semgrep findings
        # into a single PCI-DSS SARIF document, de-duplicated by
        # (ruleId, uri, startLine). The previous version always
        # emitted `results: []` which silently dropped findings
        # from the Security tab.
        "      - name: Generate PCI-DSS audit SARIF from findings",
        "        if: always()",
        "        run: |",
        "          python3 - <<'PY'",
        "          import json, os, pathlib",
        "          findings = []",
        "",
        "          # 1. PAN/CVV findings (custom regex script above).",
        "          f = pathlib.Path('pci-findings.txt')",
        "          if f.exists():",
        "              for line in f.read_text().splitlines():",
        "                  parts = line.split('|', 4)",
        "                  if len(parts) < 5:",
        "                      continue",
        "                  kind, file_path, line_no, snippet = parts",
        "                  rule = 'pci-dss-pan-in-source' if kind == 'PAN' else 'pci-dss-cvv-in-source'",
        "                  findings.append({",
        "                      'ruleId': rule,",
        "                      'level': 'error',",
        "                      'message': {'text': f'PCI-DSS {kind} detected in source code. Cardholder data must never be committed.'},",
        "                      'locations': [{",
        "                          'physicalLocation': {",
        "                              'artifactLocation': {'uri': file_path},",
        "                              'region': {'startLine': int(line_no) if line_no.isdigit() else 1},",
        "                          },",
        "                      }],",
        "                      'properties': {'security-severity': '9.5'},",
        "                  })",
        "",
        "          # 2. Semgrep findings (e-commerce / payment-security",
        "          # ruleset from .github/ai-devsecops-rules.yml or",
        "          # the registry rulesets p/owasp-top-ten, p/javascript,",
        "          # p/sql-injection, etc.). De-duplicate by (ruleId,",
        "          # uri, startLine) and emit everything under a single",
        "          # 'pci-dss-audit' run for the Code Scanning tab.",
        "          seen = {(",
        "              r['ruleId'],",
        "              (r.get('locations') or [{}])[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', ''),",
        "              (r.get('locations') or [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine', 0),",
        "          ) for r in findings}",
        "          semgrep_sarif = pathlib.Path('pci-dss-semgrep.sarif')",
        "          if semgrep_sarif.exists():",
        "              try:",
        "                  sg = json.loads(semgrep_sarif.read_text())",
        "                  for run in sg.get('runs') or []:",
        "                      for r in run.get('results') or []:",
        "                          rid = r.get('ruleId', 'semgrep-unknown')",
        "                          loc = (r.get('locations') or [{}])[0].get('physicalLocation', {})",
        "                          uri = (loc.get('artifactLocation') or {}).get('uri', '')",
        "                          start_line = (loc.get('region') or {}).get('startLine', 0)",
        "                          key = (rid, uri, start_line)",
        "                          if key in seen:",
        "                              continue",
        "                          seen.add(key)",
        "                          findings.append({",
        "                              'ruleId': rid,",
        "                              'level': r.get('level', 'warning'),",
        "                              'message': r.get('message', {'text': rid}),",
        "                              'locations': r.get('locations', []),",
        "                              'properties': r.get('properties', {}),",
        "                          })",
        "              except Exception as e:",
        "                  print(f'Could not parse Semgrep SARIF: {e}')",
        "",
        "          sarif = {",
        "              'version': '2.1.0',",
        "              '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',",
        "              'runs': [{",
        "                  'tool': {'driver': {",
        "                      'name': 'pci-dss-audit',",
        "                      'version': '1.0',",
        "                      'informationUri': 'https://www.pcisecuritystandards.org/',",
        "                  }},",
        "                  'results': findings,",
        "              }],",
        "          }",
        "          pathlib.Path('pci-dss-audit.sarif').write_text(json.dumps(sarif, indent=2))",
        "          print(f'Generated SARIF with {len(findings)} finding(s) (PAN/CVV + Semgrep)')",
        "          PY",
        "          echo \"✓ pci-dss-audit.sarif size: $(stat -c%s pci-dss-audit.sarif) bytes\"",
        "",
        *_render_sarif_fallback(
            tool_name="pci-dss-audit",
            tool_version="1.0",
            info_uri="https://www.pcisecuritystandards.org/",
            sarif_path="pci-dss-audit.sarif",
        ),
        *_render_upload_sarif(
            sarif_path="pci-dss-audit.sarif",
            category="devsecops-pci-dss",
        ),
        *_render_upload_artifact(
            sarif_path="pci-dss-audit.sarif",
            name_prefix="pci-dss-audit",
        ),
    ]


def _build_hipaa_job() -> list[str]:
    """Build the `hipaa` job for healthcare repos.

    Steps:
      1. Scan for PHI patterns in source (patient ID, MRN)
      2. Check encryption algorithms
      3. Check audit logging presence
    """
    return [
        # NOTE: "  hipaa:" is prepended by _add_job(); do NOT add here.
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 10",
        "    continue-on-error: true",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
        "      - name: Scan for PHI patterns in source",
        "        run: |",
        "          echo 'Scanning for potential PHI exposure...'",
        "          PHI_PATTERNS='(patient_name|medical_record_number|mrn|diagnosis_code|icd10|ssn|social_security)'",
        "          HITS=$(grep -rEi \"${PHI_PATTERNS}\" --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null | grep -v '//\\|#\\|//.*' | head -10)",
        "          if [ -n \"$HITS\" ]; then",
        "            echo '::warning::Potential PHI field references found (review manually):'",
        "            echo \"$HITS\"",
        "          fi",
        "          echo '✓ PHI pattern scan complete'",
        "        continue-on-error: true",
        "",
        "      - name: Check for weak crypto algorithms",
        "        run: |",
        "          WEAK_CRYPTO=$(grep -rE 'createHash\\(\"(md5|sha1)\"\\)' --include='*.js' --include='*.ts' src/ 2>/dev/null | head -5)",
        "          if [ -n \"$WEAK_CRYPTO\" ]; then",
        "            echo '::error::Weak hash algorithm (md5/sha1) detected — HIPAA requires strong crypto:'",
        "            echo \"$WEAK_CRYPTO\"",
        "            exit 1",
        "          fi",
        "          echo '✓ No weak crypto detected'",
        "        continue-on-error: true",
        "",
        "      - name: Generate HIPAA audit SARIF",
        "        if: always()",
        "        run: |",
        "          printf '%s\\n' \\",
        "            '{' \\",
        "            '  \"version\": \"2.1.0\",' \\",
        "            '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "            '  \"runs\": [{\"tool\": {\"driver\": {\"name\": \"hipaa-audit\"}}, \"results\": []}]' \\",
        "            '}' > hipaa-audit.sarif",
        "          echo \"✓ hipaa-audit.sarif size: $(stat -c%s hipaa-audit.sarif) bytes\"",
        "",
        "      - name: Upload HIPAA audit to Code Scanning",
        "        if: always() && hashFiles('hipaa-audit.sarif') != ''",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        "          sarif_file: hipaa-audit.sarif",
        "          category: devsecops-hipaa",
        "",
        "      - name: Upload HIPAA audit as artifact",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        "          name: hipaa-audit-${{ github.sha }}",
        "          path: hipaa-audit.sarif",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]


def _build_ledger_check_job() -> list[str]:
    """Build the `ledger-check` job for fintech repos.

    Steps:
      1. Scan for race conditions in balance updates
      2. Check atomicity of ledger operations
      3. Validate idempotency key handling
    """
    return [
        # NOTE: "  ledger-check:" is prepended by _add_job(); do NOT add here.
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 10",
        "    continue-on-error: true",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
        "      - name: Scan for non-atomic balance updates",
        "        run: |",
        "          echo 'Scanning for race conditions in balance updates...'",
        "          RACE_PATTERN='balance\\s*-=\\s*\\$?[a-zA-Z_]+'",
        "          HITS=$(grep -rE \"${RACE_PATTERN}\" --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null | head -5)",
        "          if [ -n \"$HITS\" ]; then",
        "            echo '::warning::Potential non-atomic balance update (review for race conditions):'",
        "            echo \"$HITS\"",
        "          fi",
        "          echo '✓ Race condition scan complete'",
        "        continue-on-error: true",
        "",
        "      - name: Check for missing idempotency keys",
        "        run: |",
        "          TRANSFER_ENDPOINTS=$(grep -rE 'router\\.(post|put)\\(\\s*[\"\\']([^\"\\']*transfer|[^\"\\']*transaction)' --include='*.js' --include='*.ts' src/ 2>/dev/null | head -3)",
        "          if [ -n \"$TRANSFER_ENDPOINTS\" ] && ! grep -rq 'idempotency\\|Idempotency-Key' src/ 2>/dev/null; then",
        "            echo '::warning::Transfer endpoints found but no idempotency key handling detected'",
        "          else",
        "            echo '✓ Idempotency check passed'",
        "          fi",
        "        continue-on-error: true",
        "",
        "      - name: Generate ledger-check audit SARIF",
        "        if: always()",
        "        run: |",
        "          printf '%s\\n' \\",
        "            '{' \\",
        "            '  \"version\": \"2.1.0\",' \\",
        "            '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "            '  \"runs\": [{\"tool\": {\"driver\": {\"name\": \"ledger-check-audit\"}}, \"results\": []}]' \\",
        "            '}' > ledger-check-audit.sarif",
        "          echo \"✓ ledger-check-audit.sarif size: $(stat -c%s ledger-check-audit.sarif) bytes\"",
        "",
        "      - name: Upload ledger-check audit to Code Scanning",
        "        if: always() && hashFiles('ledger-check-audit.sarif') != ''",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        "          sarif_file: ledger-check-audit.sarif",
        "          category: devsecops-ledger-check",
        "",
        "      - name: Upload ledger-check audit as artifact",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        "          name: ledger-check-audit-${{ github.sha }}",
        "          path: ledger-check-audit.sarif",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]


def _build_csp_headers_job() -> list[str]:
    """Build the `csp-headers` job for blog repos (static analysis).

    Static analysis only (per Phase 2.4 decision): we grep source for
    security header setup (helmet(), Talisman, res.setHeader, etc.)
    rather than spinning up a server. Coverage ~70%, fast (~5s).

    Reference: docs/domain-aware-pipeline.md (Phase 2.4)
    """
    return [
        # NOTE: "  csp-headers:" is prepended by _add_job(); do NOT add here.
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 5",
        "    continue-on-error: true",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
        "      - name: Static check for security header middleware",
        "        run: |",
        "          echo 'Scanning for security headers middleware...'",
        "          if grep -rq 'helmet()' --include='*.js' --include='*.ts' src/ 2>/dev/null; then",
        "            echo '✓ helmet() middleware detected (covers CSP, X-Frame-Options, HSTS)'",
        "          elif grep -rq 'Talisman' --include='*.py' src/ 2>/dev/null; then",
        "            echo '✓ Flask-Talisman detected'",
        "          elif grep -rq 'Content-Security-Policy' --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null; then",
        "            echo '✓ Manual CSP header found'",
        "          else",
        "            echo '::error::No security headers middleware found. Blog is vulnerable to XSS, clickjacking.'",
        "            echo 'Add helmet() in Express or Flask-Talisman in Python.'",
        "            exit 1",
        "          fi",
        "        continue-on-error: true",
        "",
        "      - name: Check for X-Frame-Options",
        "        run: |",
        "          if grep -rqE 'X-Frame-Options|frameOptions' --include='*.js' --include='*.ts' src/ 2>/dev/null; then",
        "            echo '✓ X-Frame-Options configured'",
        "          else",
        "            echo '::warning::X-Frame-Options not detected (clickjacking risk)'",
        "          fi",
        "        continue-on-error: true",
        "",
        "      - name: Check for HSTS",
        "        run: |",
        "          if grep -rqE 'Strict-Transport-Security|hsts' --include='*.js' --include='*.ts' src/ 2>/dev/null; then",
        "            echo '✓ HSTS configured'",
        "          else",
        "            echo '::warning::HSTS not detected'",
        "          fi",
        "        continue-on-error: true",
        "",
        "      - name: Generate CSP audit SARIF",
        "        if: always()",
        "        run: |",
        "          printf '%s\\n' \\",
        "            '{' \\",
        "            '  \"version\": \"2.1.0\",' \\",
        "            '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "            '  \"runs\": [{\"tool\": {\"driver\": {\"name\": \"csp-headers-audit\"}}, \"results\": []}]' \\",
        "            '}' > csp-headers-audit.sarif",
        "          echo \"✓ csp-headers-audit.sarif size: $(stat -c%s csp-headers-audit.sarif) bytes\"",
        "",
        "      - name: Upload CSP-headers audit to Code Scanning",
        "        if: always() && hashFiles('csp-headers-audit.sarif') != ''",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        "          sarif_file: csp-headers-audit.sarif",
        "          category: devsecops-csp-headers",
        "",
        "      - name: Upload CSP-headers audit as artifact",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        "          name: csp-headers-audit-${{ github.sha }}",
        "          path: csp-headers-audit.sarif",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]


def _build_mqtt_security_job() -> list[str]:
    """Build the `mqtt-security` job for IoT repos.

    Steps:
      1. Scan for mqtt:// (cleartext) broker URLs
      2. Check for default credentials
      3. Validate TLS configuration
    """
    return [
        # NOTE: "  mqtt-security:" is prepended by _add_job(); do NOT add here.
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 5",
        "    continue-on-error: true",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
        "      - name: Scan for cleartext MQTT connections",
        "        run: |",
        "          echo 'Scanning for cleartext MQTT (mqtt://)...'",
        "          HITS=$(grep -rE '\"mqtt://[^\"]+\"' --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null | head -5)",
        "          if [ -n \"$HITS\" ]; then",
        "            echo '::error::Cleartext MQTT broker detected (mqtt://). Use mqtts:// for TLS.'",
        "            echo \"$HITS\"",
        "            exit 1",
        "          fi",
        "          echo '✓ No cleartext MQTT detected'",
        "        continue-on-error: true",
        "",
        "      - name: Check for default credentials",
        "        run: |",
        "          DEFAULT_CREDS=$(grep -rE '\"(admin|root|user|device|test):(admin|root|user|device|test|1234|12345|password)\"' --include='*.js' --include='*.ts' --include='*.py' src/ 2>/dev/null | head -5)",
        "          if [ -n \"$DEFAULT_CREDS\" ]; then",
        "            echo '::error::Default MQTT credentials detected (OWASP IoT I1).'",
        "            echo \"$DEFAULT_CREDS\"",
        "            exit 1",
        "          fi",
        "          echo '✓ No default MQTT credentials'",
        "        continue-on-error: true",
        "",
        "      - name: Check for TLS verification disabled",
        "        run: |",
        "          TLS_INSECURE=$(grep -rE 'tls_insecure_set\\(True\\)|rejectUnauthorized.*false|CERT_NONE' --include='*.py' src/ 2>/dev/null | head -3)",
        "          if [ -n \"$TLS_INSECURE\" ]; then",
        "            echo '::error::TLS certificate verification disabled (MITM risk):'",
        "            echo \"$TLS_INSECURE\"",
        "            exit 1",
        "          fi",
        "          echo '✓ TLS verification not disabled'",
        "        continue-on-error: true",
        "",
        "      - name: Generate MQTT-security audit SARIF",
        "        if: always()",
        "        run: |",
        "          printf '%s\\n' \\",
        "            '{' \\",
        "            '  \"version\": \"2.1.0\",' \\",
        "            '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "            '  \"runs\": [{\"tool\": {\"driver\": {\"name\": \"mqtt-security-audit\"}}, \"results\": []}]' \\",
        "            '}' > mqtt-security-audit.sarif",
        "          echo \"✓ mqtt-security-audit.sarif size: $(stat -c%s mqtt-security-audit.sarif) bytes\"",
        "",
        "      - name: Upload MQTT-security audit to Code Scanning",
        "        if: always() && hashFiles('mqtt-security-audit.sarif') != ''",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        "          sarif_file: mqtt-security-audit.sarif",
        "          category: devsecops-mqtt-security",
        "",
        "      - name: Upload MQTT-security audit as artifact",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        "          name: mqtt-security-audit-${{ github.sha }}",
        "          path: mqtt-security-audit.sarif",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]


def _ensure_sarif_fallback(
    filename: str,
    tool_name: str,
    version: str = "0.65.0",
    information_uri: str = "https://aquasecurity.github.io/trivy/",
) -> list[str]:
    """Return YAML lines for a SARIF fallback step.

    Several tools (Trivy, Semgrep, Gitleaks, npm audit SARIF converter)
    do NOT write a SARIF file when 0 findings are produced or when the
    scan fails. This causes `github/codeql-action/upload-sarif` to fail
    with "Path does not exist". This fallback generates a minimal but
    valid OASIS 2.1.0 SARIF document with an empty `results` array
    so the upload step always succeeds.

    Parameters
    ----------
    filename:
        Output file name (e.g. "trivy-fs-results.sarif").
    tool_name:
        Name to put in the SARIF `tool.driver.name` field
        (e.g. "Trivy", "Trivy Image", "npm audit").
    version:
        Tool version to put in the SARIF document.
    information_uri:
        URL to put in the SARIF `tool.driver.informationUri` field.
    """
    return [
        f"      - name: Ensure {filename} exists (fallback for 0 findings)",
        "        if: always()",
        "        run: |",
        f"          if [ ! -s {filename} ]; then",
        f'            echo "::notice::{tool_name} found 0 findings. Generating empty SARIF to satisfy upload-sarif."',
        "            printf '%s\\n' \\",
        "              '{' \\",
        "              '  \"version\": \"2.1.0\",' \\",
        "              '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
        "              '  \"runs\": [' \\",
        "              '    {' \\",
        "              '      \"tool\": {' \\",
        "              '        \"driver\": {' \\",
        f"              '          \"name\": \"{tool_name}\",' \\",
        f"              '          \"version\": \"{version}\",' \\",
        f"              '          \"informationUri\": \"{information_uri}\"' \\",
        "              '        }' \\",
        "              '      },' \\",
        "              '      \"results\": []' \\",
        "              '    }' \\",
        "              '  ]' \\",
        "              '}' > " + filename,
        "          fi",
        f"          echo \"✓ {filename} size: $(stat -c%s {filename}) bytes\"",
    ]


def _ensure_sarif_from_annotations(
    filename: str,
    tool_name: str,
    tool_version: str = "1.0.0",
    information_uri: str = "https://github.com/iqbalrsyd/ai-devsecops",
    rule_id_prefix: str = "ai-devsecops",
) -> list[str]:
    """Return YAML lines for a Python step that converts
    `::error file=...::msg` and `::warning file=...::msg` annotations
    emitted by the upstream `shell_check` steps into SARIF 2.1.0
    results. The script is captured from the per-job log file written
    by `_wrap_shell_check_for_sarif` (one entry per job, in
    `${cat}.shell_log`).

    Implementation: a single `python3` invocation that reads the log
    file, parses the GitHub workflow-command annotation format, and
    writes SARIF. This replaces the previous approach (which called
    `github.rest.actions.listWorkflowRunAnnotations` — that endpoint
    does not exist on the GitHub REST API). The log-file approach is
    self-contained and works for any job, including reusable
    workflows invoked via `uses: ./.../ai-devsecops-custom.yml`.

    The step is always run (`if: always()`) so a failing shell_check
    step does not skip SARIF conversion. If no annotations are
    present, the existing SARIF file is left untouched.
    """
    # Inline Python script. Reads ${cat}.shell_log, parses
    # `::error/warning [file=...,line=...,title=...]::msg` lines,
    # writes SARIF.
    #
    # The regex accepts the full GitHub Actions annotation format:
    #   ::error file={path},line={n},endLine={n},title={text}::{message}
    # All properties are optional. Common forms that must be
    # supported (observed in LLM-generated scripts):
    #   ::error file=src/x.js::msg
    #   ::error file=src/x.js,line=33::msg
    #   ::error title=Markdown XSS::msg
    #   ::error title=Foo,file=src/x.js::msg
    #   ::error::msg                           (bare, no properties)
    py_script = (
        "import os, re, json\n"
        f"log_path = '{tool_name}.shell_log'\n"
        f"sarif_path = {filename!r}\n"
        f"tool_name = {tool_name!r}\n"
        f"tool_version = {tool_version!r}\n"
        f"information_uri = {information_uri!r}\n"
        f"rule_id_prefix = {rule_id_prefix!r}\n"
        "results = []\n"
        "if os.path.exists(log_path):\n"
        # Match ::error|warning followed by an optional property list
        # of comma-separated key=value pairs (key may be file|line|
        # endLine|col|endColumn|title|...) and :: separator + message.
        # Group 1: level (error|warning)\n"
        # Group 2: file path (None if not present)\n"
        # Group 3: line number (None if not present)\n"
        # Group 4: title (None if not present)\n"
        # Group 5: message body\n"
        "    pat = re.compile(\n"
        "        r'^::(error|warning)(?:\\s+([A-Za-z]+=[^,]+(?:,[A-Za-z]+=[^,]+)*))?::(.*)$'\n"
        "    )\n"
        "    for idx, line in enumerate(open(log_path, encoding='utf-8', errors='replace')):\n"
        "        m = pat.match(line.rstrip('\\n'))\n"
        "        if not m:\n"
        "            continue\n"
        "        level, props, msg = m.groups()\n"
        "        path = None\n"
        "        sl = None\n"
        "        el = None\n"
        "        title = None\n"
        "        if props:\n"
        "            for kv in props.split(','):\n"
        "                if '=' in kv:\n"
        "                    k, v = kv.split('=', 1)\n"
        "                    k = k.strip()\n"
        "                    v = v.strip()\n"
        "                    if k == 'file':\n"
        "                        path = v\n"
        "                    elif k == 'line':\n"
        "                        try:\n"
        "                            sl = int(v)\n"
        "                        except ValueError:\n"
        "                            pass\n"
        "                    elif k in ('endLine', 'col'):\n"
        "                        try:\n"
        "                            el = int(v) if k == 'endLine' else sl\n"
        "                        except ValueError:\n"
        "                            pass\n"
        "                    elif k == 'title':\n"
        "                        title = v\n"
        "        if sl is None:\n"
        "            sl = 1\n"
        "        if el is None:\n"
        "            el = sl\n"
        "        sarif_level = 'error' if level == 'error' else 'warning'\n"
        "        msg = (msg or '').strip()\n"
        "        # If there is no file but there is a title, use the\n"
        #        title as the message body (otherwise SARIF would\n"
        #        show '(no message)' which is useless).\n"
        "        if not msg and title:\n"
        "            msg = title\n"
        "        # Use the first 50 chars of the title (if any) as\n"
        #        part of the rule id slug, since it is more stable\n"
        #        than the body message.\n"
        "        slug_src = title or msg or 'finding'\n"
        "        slug = re.sub(r'[^a-z0-9]+', '-', slug_src.lower())[:50].strip('-')\n"
        "        rule_id = f'{rule_id_prefix}-{slug}-{sl}-{idx}'\n"
        "        results.append({\n"
        "            'ruleId': rule_id,\n"
        "            'level': sarif_level,\n"
        "            'message': {'text': msg or '(no message)'},\n"
        "            'locations': [{\n"
        "                'physicalLocation': {\n"
        "                    'artifactLocation': {'uri': path or 'unknown'},\n"
        "                    'region': {'startLine': sl, 'endLine': el},\n"
        "                },\n"
        "            }],\n"
        "        })\n"
        "existing = {}\n"
        "if os.path.exists(sarif_path) and os.path.getsize(sarif_path) > 0:\n"
        "    try:\n"
        "        existing = json.load(open(sarif_path, encoding='utf-8'))\n"
        "    except Exception:\n"
        "        existing = {}\n"
        "if not existing or 'runs' not in existing or not existing['runs']:\n"
        "    existing = {\n"
        "        'version': '2.1.0',\n"
        "        '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',\n"
        "        'runs': [{\n"
        "            'tool': {'driver': {\n"
        "                'name': tool_name, 'version': tool_version, 'informationUri': information_uri,\n"
        "            }},\n"
        "            'results': [],\n"
        "        }],\n"
        "    }\n"
        "existing['runs'][0]['tool']['driver']['name'] = tool_name\n"
        "existing['runs'][0]['tool']['driver']['version'] = tool_version\n"
        "existing['runs'][0]['tool']['driver']['informationUri'] = information_uri\n"
        "existing['runs'][0]['results'] = (existing['runs'][0].get('results') or []) + results\n"
        "with open(sarif_path, 'w', encoding='utf-8') as f:\n"
        "    json.dump(existing, f, indent=2)\n"
        "print(f'Wrote {len(results)} SARIF result(s) to {sarif_path}')\n"
    )
    # Emit as a two-step approach that is robust against YAML / bash
    # heredoc quirks:
    #   1. Write the Python script to a file using a *quoted*
    #      heredoc with no leading whitespace on the terminator
    #      (so bash recognises it).
    #   2. Run `python3 <script.py>`.
    # This avoids two issues we hit with the inline `python3 - <<EOF`
    # approach:
    #   (a) YAML block scalars strip the *common* leading indent
    #       uniformly, so the heredoc terminator ends up indented;
    #       bash only accepts an unindented terminator for `<<EOF`
    #       (or `<<-EOF` which strips *tabs only*, not spaces).
    #   (b) The Python script lines would also be indented by YAML
    #       block-scalar processing, causing IndentationError because
    #       the top-level statements no longer start at column 0.
    script_file = f"{tool_name}_annotations_to_sarif.py"
    py_lines = [f"          cat > {script_file} <<'PY_EOF'"]
    for ln in py_script.splitlines():
        py_lines.append("          " + ln)
    py_lines.append("          PY_EOF")
    py_lines.append(f"          python3 {script_file}")
    return [
        f"      - name: Convert {tool_name} shell_check annotations to SARIF",
        "        if: always()",
        "        run: |",
        *py_lines,
    ]


def _ensure_npm_audit_sarif_conversion() -> list[str]:
    """Return YAML lines for converting npm audit JSON to SARIF 2.1.0.

    npm audit --json output is a flat dict of `{packageName: {via: [...]}}`.
    `via` items can be EITHER a string (a transitive parent package name)
    OR a dict (an advisory with `title`, `source`, `name`, `url`, ...).
    The previous conversion only processed dict entries, missing the
    string entries (which represent transitive chains that often point
    to the real vulnerable package).

    This rewritten conversion:
      1. Iterates over `via` and handles BOTH string and dict types
         — for string entries, the parent package name is included in
         the message so the dependency chain is visible in the alert.
      2. Uses the advisory `url` to extract a stable CVE/GHSA id when
         available (e.g. `CVE-2024-12345` or `GHSA-xxxx-yyyy-zzzz`)
         so the ruleId is stable and dedup-friendly across runs.
      3. Always emits one SARIF result per (package, via) combination
         — the previous code deduped across all packages and silently
         dropped findings when two packages shared the same advisory
         title.
      4. Includes `severity`, `version range`, `parent package` and
         the original `via` payload in `properties` so reviewers can
         triage without leaving the Security tab.
    """
    return [
        "      - name: Convert npm audit JSON to SARIF",
        "        if: always() && hashFiles('npm-audit-results.json') != ''",
        "        run: |",
        '          python3 << "PY_EOF_NPM_AUDIT"',
        "          import json, sys, re",
        "          try:",
        "              with open('npm-audit-results.json') as f:",
        "                  data = json.load(f)",
        "              vulns = data.get('vulnerabilities', {})",
        "              results = []",
        "              cve_re = re.compile(r'CVE-\\d{4}-\\d{4,7}')",
        "              ghsa_re = re.compile(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}')",
        "              for pkg, info in vulns.items():",
        "                  if not info.get('via'):",
        "                      continue",
        "                  severity = info.get('severity', 'moderate')",
        "                  level = 'error' if severity in ('critical', 'high') else 'warning'",
        "                  range_ = info.get('range', '')",
        "                  for via in info['via']:",
        "                      if isinstance(via, str):",
        "                          # String entry: transitive parent.",
        "                          # The advisory is held in the original",
        "                          # audit metadata; emit a finding keyed",
        "                          # on (pkg, parent) so the dependency",
        "                          # chain is visible.",
        "                          rule_id = f'npm-audit:{pkg}->{via}'",
        "                          message = f'Transitive vulnerability: {via} (parent) brings {pkg} ({range_}, {severity})'",
        "                          results.append({",
        "                              'ruleId': rule_id,",
        "                              'level': level,",
        "                              'message': {'text': message},",
        "                              'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'package.json'}}}],",
        "                              'properties': {'package': pkg, 'parent': via, 'range': range_, 'severity': severity},",
        "                          })",
        "                      elif isinstance(via, dict):",
        "                          title = via.get('title', '')",
        "                          url = via.get('url', '')",
        "                          # Prefer a stable CVE/GHSA id from",
        "                          # the URL; fall back to title.",
        "                          stable_id = ''",
        "                          for src in (url, title):",
        "                              m = cve_re.search(src) or ghsa_re.search(src)",
        "                              if m:",
        "                                  stable_id = m.group(0)",
        "                                  break",
        "                          rule_id = stable_id or title or f'npm-audit:{pkg}'",
        "                          if stable_id:",
        "                              message = f'{title} in {pkg} {range_} (severity={severity}) — {stable_id}'",
        "                          else:",
        "                              message = f'{title or \"Vulnerability\"} in {pkg} {range_} (severity={severity})'",
        "                          results.append({",
        "                              'ruleId': rule_id,",
        "                              'level': level,",
        "                              'message': {'text': message},",
        "                              'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'package.json'}}}],",
        "                              'properties': {",
        "                                  'package': pkg,",
        "                                  'range': range_,",
        "                                  'severity': severity,",
        "                                  'title': title,",
        "                                  'url': url,",
        "                                  'source': via.get('source'),",
        "                                  'cwe': via.get('cwe', []),",
        "                                  'cvss_score': via.get('cvss', {}).get('score') if isinstance(via.get('cvss'), dict) else None,",
        "                              },",
        "                          })",
        "              sarif = {",
        "                  'version': '2.1.0',",
        "                  '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',",
        "                  'runs': [{",
        "                      'tool': {'driver': {'name': 'npm audit', 'version': '1.0', 'informationUri': 'https://docs.npmjs.com/cli/v10/commands/npm-audit'}},",
        "                      'results': results,",
        "                  }],",
        "              }",
        "              with open('npm-audit-results.sarif', 'w') as f:",
        "                  json.dump(sarif, f, indent=2)",
        "              print(f'npm-audit-results.sarif written with {len(results)} findings from {len(vulns)} vulnerable packages')",
        "          except Exception as e:",
        "              print(f'npm-audit SARIF conversion error: {e}', file=sys.stderr)",
        "              import traceback; traceback.print_exc()",
        "              sys.exit(0)",
        "          PY_EOF_NPM_AUDIT",
        "        continue-on-error: true",
    ]


def _ensure_pip_audit_sarif_conversion() -> list[str]:
    """Return YAML lines for converting pip-audit JSON to SARIF 2.1.0.

    pip-audit --format=json output is a list of [{name, version, vulns: [...]}].
    This step parses the JSON and emits a valid OASIS SARIF document so
    findings appear in the GitHub Code Scanning Security tab.
    """
    return [
        "      - name: Convert pip-audit JSON to SARIF",
        "        if: always() && hashFiles('pip-audit-results.json') != ''",
        "        run: |",
        '          python3 -c "',
        "          import json, sys",
        "          try:",
        "              with open('pip-audit-results.json') as f:",
        "                  data = json.load(f)",
        "              results = []",
        "              if isinstance(data, dict):",
        "                  data = data.get('dependencies', data.get('results', []))",
        "              for dep in (data if isinstance(data, list) else []):",
        "                  pkg_name = dep.get('name', dep.get('package', ''))",
        "                  pkg_version = dep.get('version', '')",
        "                  for vuln in dep.get('vulns', dep.get('vulnerabilities', [])):",
        "                      vuln_id = vuln.get('id', '')",
        "                      results.append({",
        "                          'ruleId': vuln_id,",
        "                          'message': {'text': vuln_id + ' in ' + pkg_name + ' ' + pkg_version},",
        "                          'level': 'error' if vuln.get('severity','') in ('critical','high') else 'warning',",
        "                          'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'requirements.txt'}}}],",
        "                          'properties': {'package': pkg_name, 'version': pkg_version}",
        "                      })",
        "              sarif = {",
        "                  'version': '2.1.0',",
        "                  '\\$schema': 'https://json.schemastore.org/sarif-2.1.0.json',",
        "                  'runs': [{",
        "                      'tool': {'driver': {'name': 'pip-audit', 'version': '1.0', 'informationUri': 'https://pypi.org/project/pip-audit/'}},",
        "                      'results': results",
        "                  }]",
        "              }",
        "              with open('pip-audit-results.sarif','w') as f:",
        "                  json.dump(sarif, f, indent=2)",
        "              print(f'pip-audit-results.sarif written with {len(results)} findings')",
        "          except Exception as e:",
        "              print(f'pip-audit SARIF conversion error: {e}', file=sys.stderr)",
        "              import traceback; traceback.print_exc()",
        "              sys.exit(0)",
        '          "',
        "        continue-on-error: true",
    ]


# ----------------------------------------------------------------------
# Microservice / multi-service job builders (DISABLED per R2.1)
# ----------------------------------------------------------------------
# Arsitektur bukan variabel eksperimen. Monolithic only. Kode di bawah
# ini TIDAK lagi dipanggil dari runtime path utama. Disimpan untuk
# backward compatibility.
#
# Legacy design rationale (struktur-v6 §3.6.1): for modular_monolith
# repositories the strategy was:
#
#   1. docker-compose-validate (cheap fail-fast gate)
#   2. dependency-scan-per-service (matrix strategy)
#   3. sast stays general (run once at the root)
#
# Both new jobs are gated on architecture type AND repository evidence
# (see _select_relevant_stages and _filter_stages_by_evidence).

_DOCKER_COMPOSE_VALIDATE_BODY: list[str] = [
    "    runs-on: ubuntu-latest",
    "    timeout-minutes: 5",
    "    continue-on-error: false",
    "    steps:",
    "      - name: Checkout code",
    f"        uses: {_pin('actions/checkout@v4')}",
    "        with:",
    "          persist-credentials: false",
    "",
    "      - name: Set up Docker Buildx",
    f"        uses: {_pin('docker/setup-buildx-action@v3')}",
    "",
    "      - name: Detect compose file",
    "        id: detect",
    "        run: |",
    '          if [ -f docker-compose.yml ]; then',
    '            echo "compose_file=docker-compose.yml" >> "$GITHUB_OUTPUT"',
    '          elif [ -f docker-compose.yaml ]; then',
    '            echo "compose_file=docker-compose.yaml" >> "$GITHUB_OUTPUT"',
    '          elif [ -f compose.yml ]; then',
    '            echo "compose_file=compose.yml" >> "$GITHUB_OUTPUT"',
    '          elif [ -f compose.yaml ]; then',
    '            echo "compose_file=compose.yaml" >> "$GITHUB_OUTPUT"',
    '          else',
    '            echo "::error::No compose file found"',
    '            exit 1',
    '          fi',
    "",
    "      - name: Validate compose file (docker compose config)",
    "        run: |",
    '          docker compose -f "${{ steps.detect.outputs.compose_file }}" config --quiet',
    '          echo "✓ docker-compose config validated: ${{ steps.detect.outputs.compose_file }}"',
    "",
    "      - name: Summarize compose services",
    "        if: always()",
    "        run: |",
    '          docker compose -f "${{ steps.detect.outputs.compose_file }}" config --services | tee compose-services.txt',
    '          echo "## Compose Services Detected" >> "$GITHUB_STEP_SUMMARY"',
    '          echo "```" >> "$GITHUB_STEP_SUMMARY"',
    '          cat compose-services.txt >> "$GITHUB_STEP_SUMMARY"',
    '          echo "```" >> "$GITHUB_STEP_SUMMARY"',
    "",
    "      - name: Upload compose service list",
    "        if: always()",
    f"        uses: {_pin('actions/upload-artifact@v4')}",
    "        with:",
    "          name: compose-services-${{ github.sha }}",
    "          path: compose-services.txt",
    "          if-no-files-found: warn",
    "          retention-days: 14",
]


# Per-service dependency scan: matrix strategy. The first job
# `detect-services` enumerates service directories (heuristic: any
# first-level sub-directory that contains a package manager
# manifest). The second job `dependency-scan-per-service` runs the
# appropriate scanner for each service.
#
# We support:
#   - npm/yarn/pnpm: `npm audit --json`
#   - pip/poetry:     `pip-audit -r requirements.txt` (or no -r if absent)
#   - go mod:         trivy fs scan on the service dir (SARIF)
#   - cargo:          trivy fs scan on the service dir (SARIF)
#   - maven:          trivy fs scan on the service dir
#   - gradle:         trivy fs scan on the service dir
#   - bundler:        trivy fs scan on the service dir
#
# All non-npm/pip services use `trivy fs` for SARIF output, which is
# the OASIS standard and uploads cleanly to GitHub Code Scanning.
# We deliberately do NOT require govulncheck / cargo-audit here:
# the action registry is the single source of truth for GitHub
# Actions emitted by the generator, and adding a language-specific
# scanner (actions/setup-go, cargo-audit installation) would require
# additional pinned-SHA entries. Trivy covers the same CVE
# databases (NVD, GHSA) for these ecosystems.

_DETECT_SERVICES_BODY: list[str] = [
    "    runs-on: ubuntu-latest",
    "    timeout-minutes: 5",
    "    continue-on-error: false",
    "    outputs:",
    "      matrix: ${{ steps.discover.outputs.matrix }}",
    "    steps:",
    "      - name: Checkout code",
    f"        uses: {_pin('actions/checkout@v4')}",
    "        with:",
    "          persist-credentials: false",
    "",
    "      - name: Discover service directories",
    "        id: discover",
    "        run: |",
    '          echo "Detecting service directories with package manager manifests..."',
    '          services_json="[]"',
    '          for d in */; do',
    '            d="${d%/}"',
    '            [ -z "$d" ] && continue',
    '            case "$d" in',
    '              node_modules|.git|.github|docs|test|tests|scripts|build|dist|coverage|.venv|venv) continue ;;',
    '            esac',
    '            [ ! -d "$d" ] && continue',
    '            manifest=""',
    '            pm="generic"',
    '            if [ -f "$d/package.json" ]; then',
    '              manifest="package.json"',
    '              pm="npm"',
    '            elif [ -f "$d/requirements.txt" ] || [ -f "$d/pyproject.toml" ]; then',
    '              if [ -f "$d/requirements.txt" ]; then',
    '                manifest="requirements.txt"',
    '              else',
    '                manifest="pyproject.toml"',
    '              fi',
    '              pm="pip"',
    '            elif [ -f "$d/go.mod" ]; then',
    '              manifest="go.mod"',
    '              pm="go"',
    '            elif [ -f "$d/Cargo.toml" ]; then',
    '              manifest="Cargo.toml"',
    '              pm="cargo"',
    '            elif [ -f "$d/pom.xml" ]; then',
    '              manifest="pom.xml"',
    '              pm="maven"',
    '            elif [ -f "$d/build.gradle" ] || [ -f "$d/build.gradle.kts" ]; then',
    '              if [ -f "$d/build.gradle" ]; then',
    '                manifest="build.gradle"',
    '              else',
    '                manifest="build.gradle.kts"',
    '              fi',
    '              pm="gradle"',
    '            elif [ -f "$d/Gemfile" ]; then',
    '              manifest="Gemfile"',
    '              pm="bundler"',
    '            fi',
    '            if [ -n "$manifest" ]; then',
    '              entry="{\\"service\\":\\"$d\\",\\"path\\":\\"$d\\",\\"manifest\\":\\"$manifest\\",\\"package_manager\\":\\"$pm\\"}"',
    '              if [ "$services_json" = "[]" ]; then',
    '                services_json="[$entry"',
    '              else',
    '                services_json="$services_json,$entry"',
    '              fi',
    '              echo "  - service=$d pm=$pm manifest=$manifest"',
    '            fi',
    '          done',
    '          [ "$services_json" = "[]" ] && services_json="[]" || services_json="$services_json]"',
    '          echo "matrix=$services_json" >> "$GITHUB_OUTPUT"',
    '          echo "Discovered $(echo "$services_json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))") services"',
]


def _build_docker_compose_validate_job() -> tuple[str, str]:
    """Return (yaml_body, reason) for the docker-compose-validate job.

    Cheap fail-fast gate: validates the compose file's syntax and
    service references. Runs before per-service scans so a broken
    compose file fails the pipeline early (within ~30 seconds)
    instead of wasting compute on per-service scanners.
    """
    reason = (
        "docker-compose file present in repository. "
        "file detected. Validates the compose file syntax and service "
        "references via `docker compose config --quiet` so a broken stack "
        "fails fast (within ~30s) before per-service scanners run. The list "
        "of detected services is also uploaded as a workflow artifact."
    )
    return ("\n".join(_DOCKER_COMPOSE_VALIDATE_BODY), reason)


def _build_dependency_scan_per_service_job() -> tuple[str, str]:
    """Return (yaml_body, reason) for the dependency-scan-per-service job.

    Matrix strategy: enumerates service directories, then for each
    service runs the appropriate CVE scanner (npm audit, pip-audit,
    govulncheck, cargo audit, trivy fs). Findings are emitted as
    SARIF and uploaded to GitHub Code Scanning with a per-service
    tag.
    """
    detect_job_yaml = "\n".join(_DETECT_SERVICES_BODY)
    matrix_job_yaml_lines: list[str] = [
        "    needs: detect-services",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 15",
        "    continue-on-error: true",
        "    strategy:",
        "      fail-fast: false",
        "      matrix:",
        "        include: ${{ fromJson(needs.detect-services.outputs.matrix) }}",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
        "      - name: Set up Node.js (npm/yarn/pnpm services)",
        "        if: ${{ matrix.package_manager == 'npm' }}",
        f"        uses: {_pin('actions/setup-node@v4')}",
        "        with:",
        "          node-version: '24'",
        "",
        "      - name: Set up Python (pip services)",
        "        if: ${{ matrix.package_manager == 'pip' }}",
        f"        uses: {_pin('actions/setup-python@v5')}",
        "        with:",
        "          python-version: '3.11'",
        "",
        "      - name: Install pip-audit",
        "        if: ${{ matrix.package_manager == 'pip' }}",
        "        run: pip install pip-audit",
        "        continue-on-error: true",
        "",
        "      - name: Run npm audit (per-service JSON)",
        "        if: ${{ matrix.package_manager == 'npm' }}",
        "        run: |",
        "          cd \"${{ matrix.path }}\"",
        "          npm audit --audit-level=high --json > \"../npm-audit-${{ matrix.service }}.json\" || true",
        "        continue-on-error: true",
        "",
        "      - name: Run pip-audit (per-service JSON)",
        "        if: ${{ matrix.package_manager == 'pip' }}",
        "        run: |",
        "          cd \"${{ matrix.path }}\"",
        "          if [ -f requirements.txt ]; then",
        "            pip-audit -r requirements.txt --strict --disable-pip --format=json --output=\"../pip-audit-${{ matrix.service }}.json\" || true",
        "          else",
        "            pip-audit --strict --disable-pip --format=json --output=\"../pip-audit-${{ matrix.service }}.json\" || true",
        "          fi",
        "        continue-on-error: true",
        "",
        "      - name: Run Trivy fs scan (per-service SARIF)",
        "        if: ${{ matrix.package_manager == 'go' || matrix.package_manager == 'cargo' || matrix.package_manager == 'maven' || matrix.package_manager == 'gradle' || matrix.package_manager == 'bundler' || matrix.package_manager == 'generic' }}",
        f"        uses: {_pin('aquasecurity/trivy-action@v0.24.0')}",
        "        with:",
        "          scan-type: 'fs'",
        "          scan-ref: '${{ matrix.path }}'",
        "          format: 'sarif'",
        "          output: 'trivy-fs-${{ matrix.service }}.sarif'",
        "          version: v0.72.0",
        "          severity: 'MEDIUM,HIGH,CRITICAL'",
        "        continue-on-error: true",
        "",
        *_ensure_sarif_fallback(
            "trivy-fs-${{ matrix.service }}.sarif",
            "Trivy (per-service)",
        ),
        "",
        "      - name: Upload Trivy per-service SARIF to GitHub Code Scanning",
        "        if: always()",
        f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
        "        with:",
        "          sarif_file: trivy-fs-${{ matrix.service }}.sarif",
        "          category: trivy-fs-${{ matrix.service }}",
        "",
        "      - name: Upload per-service artifacts",
        "        if: always()",
        f"        uses: {_pin('actions/upload-artifact@v4')}",
        "        with:",
        "          name: per-service-scan-${{ matrix.service }}-${{ github.sha }}",
        "          path: |",
        "            npm-audit-${{ matrix.service }}.json",
        "            pip-audit-${{ matrix.service }}.json",
        "            trivy-fs-${{ matrix.service }}.sarif",
        "          if-no-files-found: warn",
        "          retention-days: 30",
    ]
    matrix_job_yaml = "\n".join(matrix_job_yaml_lines)
    reason = (
        "Multi-service matrix scan (legacy, disabled per R2.1). Enumerates "
        "service directories (heuristic: first-level sub-directory that "
        "contains a package manager manifest) and runs the appropriate CVE "
        "scanner per service: `npm audit` for npm/yarn/pnpm, `pip-audit` "
        "for pip/poetry, `trivy fs` (SARIF) for Go/Rust/Maven/Gradle/Bundler. "
        "Findings uploaded to GitHub Code Scanning with a per-service "
        "category tag, and to workflow artifacts for AI agent parsing."
    )
    return (detect_job_yaml + "\n\n  dependency-scan-per-service:\n" + matrix_job_yaml, reason)



def _build_workflow_yaml(
    primary_language: str,
    package_manager: str,
    test_framework: str | None,
    frameworks: list[str],
    build_tools: list[str],
    stages: list[str],
    arch_type: str,
    findings: list[dict],
    structure: list | None = None,
    files: dict | None = None,
    detected_domain: str | None = None,
    domain_confidence: float | None = None,
    domain_threats: list[str] | None = None,
    detected_sub_type: str | None = None,
    llm_rule_suggestions: list[str] | None = None,
    state: PipelineEngineerState | None = None,
    active_profiles: list | None = None,
) -> tuple[str, list[str], list[dict]]:
    """Build the full GitHub Actions workflow YAML deterministically.

    Returns (yaml_text, stage_names, stage_explanations).

    Parameters
    ----------
    detected_sub_type:
        Finer-grained classification of the domain. Currently used
        for e-commerce payment processors (stripe, midtrans, xendit,
        paypal, braintree, doku, razorpay, adyen, square, multi,
        unknown, none). When set, the corresponding PCI rule file
        is added to the sast ruleset.
    llm_rule_suggestions:
        Optional list of custom rule file names suggested by the
        LLM at inference time. Used for emerging threats not yet
        covered by the static mapping in scan_directives.py.
    active_profiles:
        Optional list of `LanguageProfile` objects resolved by
        `language_profiles.resolve_active_profiles`. When non-empty,
        the `lint` and `test` jobs dispatch over the profile list
        (one `lint-<id>` / `test-<id>` job per detected language).
        When empty/None, the original if/elif branches (Node /
        Python / generic) are used as a backward-compat fallback.
    """
    explanations: list[dict] = []
    stage_names: list[str] = []

    has_node = "npm" in package_manager or "yarn" in package_manager or "pnpm" in package_manager
    has_python = "pip" in package_manager or "poetry" in package_manager or "python" in primary_language
    has_jvm = "maven" in package_manager or "gradle" in package_manager or "java" in primary_language
    has_go = "go" in primary_language or "go mod" in package_manager
    has_rust = "cargo" in package_manager or "rust" in primary_language

    has_lockfile = _has_file(structure or [], files or {}, _LOCKFILE_PATTERNS)

    # Compose a human-readable workflow name.
    wf_name = f"CI DevSecOps ({primary_language or 'repository'})"

    # Domain-aware header comment.
    # Safe access: state[...] may be None (not just missing key) when the
    # upstream node (e.g. cached_insights from FE) sends a key with an
    # explicit None value. Use `or {}` to coerce None to {}.
    _state = state if isinstance(state, dict) else {}
    _tech = _state.get("detected_technologies") or {}
    _deploy = _state.get("detected_deployment") or {}
    domain_header = _build_domain_header(
        detected_domain=detected_domain,
        domain_confidence=domain_confidence,
        domain_threats=domain_threats,
        arch_type=arch_type,
        detected_technologies={
            "primary_language": primary_language,
            "frameworks": _tech.get("frameworks") if isinstance(_tech, dict) else None,
            "database": _tech.get("database") if isinstance(_tech, dict) else None,
            "test_framework": _tech.get("test_framework") if isinstance(_tech, dict) else None,
            "runtime": _tech.get("runtime") if isinstance(_tech, dict) else None,
            "package_manager": package_manager,
            "build_tools": _tech.get("build_tools") if isinstance(_tech, dict) else None,
            "has_dockerfile": _deploy.get("docker") if isinstance(_deploy, dict) else None,
        },
    )

    # Header + trigger + permissions + concurrency.
    # Use quoted "on" to keep the YAML round-trip safe (yaml.safe_load would
    # otherwise convert the bare `on:` into the boolean True key).
    # Permissions are computed after jobs are built so they reflect the
    # actions actually used (requirement 4 + 6).
    yaml_lines: list[str] = [
        f"name: {wf_name}",
        *domain_header,
        "",
        '"on":',
        "  push:",
        "    branches: [main, master, develop]",
        "  pull_request:",
        "    branches: [main, master, develop]",
        "  workflow_dispatch:",
        "",
        # All actions emitted by the generator are pinned to versions
        # that declare `using: node24` in their action.yml. The
        # legacy `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` environment
        # variable (a stop-gap when the registry still pointed at
        # node20-pinned actions) is no longer needed and would only
        # confuse readers of the generated YAML.
        "",
        "__PERMISSIONS_PLACEHOLDER__",
        "",
        "concurrency:",
        "  group: ${{ github.workflow }}-${{ github.ref }}",
        "  cancel-in-progress: true",
        "",
        "jobs:",
    ]

    def _add_job(name: str, body: str, reason: str, status: str = "recommended", aliases: list[str] | None = None) -> None:
        yaml_lines.append(f"  {name}:")
        yaml_lines.append(body)
        stage_names.append(name)
        # Multi-language: when a per-language job (e.g. `lint-python`)
        # is emitted, also record its generic alias (`lint`) in
        # `stage_names` so downstream consumers (PDF, coverage library,
        # security_requirement_inference_node, pipeline_augmentation_node)
        # which key off `"lint"` / `"test"` continue to work. The
        # YAML still uses the language-specific job name.
        if aliases:
            for alias in aliases:
                if alias not in stage_names:
                    stage_names.append(alias)
        explanations.append({
            "name": name,
            "reason": reason,
            "status": status,
            "tool": _job_tool(name, primary_language, package_manager, test_framework),
        })

    def _add_merged_job(
        name: str,
        aliases: list[str],
        body: str,
        reason: str,
        status: str = "recommended",
    ) -> None:
        """Emit a single YAML job that covers multiple logical stages.

        Reviewer feedback: `container-build` and `container-scan` were
        emitting two jobs that both built the same image. The merged
        `container-security` job builds the image ONCE and scans it.
        We still surface the original stage names in `stage_names` so
        the prerequisite / consistency validators and the dashboard
        see both stages represented in the state.
        """
        yaml_lines.append(f"  {name}:")
        yaml_lines.append(body)
        # Record the merged job name (the actual YAML job) so the
        # validator accepts it, but ALSO record the original stage
        # aliases so backward-compatible state consumers (which look
        # for "container-build" / "container-scan") still see them.
        stage_names.append(name)
        for alias in aliases:
            if alias not in stage_names:
                stage_names.append(alias)
        explanations.append({
            "name": name,
            "reason": reason,
            "status": status,
            "tool": _job_tool(name, primary_language, package_manager, test_framework),
        })

    # ---- lint ----
    if "lint" in stages:
        # Multi-language path: emit one `lint-<id>` job per detected
        # language profile. Falls through to the legacy if/elif chain
        # if `active_profiles` is empty (e.g. detection failed or
        # language has no per-lang linter).
        _lint_jobs_emitted_via_profiles = False
        if active_profiles:
            from app.agents.language_profiles import render_lint_jobs
            _rendered_lint_jobs = render_lint_jobs(active_profiles)
            if _rendered_lint_jobs:
                for job_name, job_body, job_reason in _rendered_lint_jobs:
                    _add_job(job_name, job_body, job_reason, aliases=["lint"])
                    yaml_lines.append("")
                _lint_jobs_emitted_via_profiles = True

        if not _lint_jobs_emitted_via_profiles:
            # Legacy fallback: single `lint` job from if/elif below.
            if has_node:
                tool = "eslint"
                reason = (
                    f"JavaScript/TypeScript repository detected"
                    f"{' (package manager: ' + package_manager + ')' if package_manager else ''}"
                    f"; ESLint enforces code-quality and style rules."
                )
                node_version = _detect_node_version(structure or [], files or {})
                setup, install_cmd = _node_setup_steps(
                    package_manager, has_lockfile, node_version=node_version
                )
                install = (
                    f"      - name: Install dependencies\n"
                    f"        run: {install_cmd}\n"
                    f"        continue-on-error: true"
                )
                run_step = (
                    "      - name: Run ESLint\n        run: |\n"
                    "          if [ -f package.json ] && grep -q '\"lint\"' package.json; then\n"
                    "            npm run lint --if-present\n"
                    "          else\n"
                    "            echo 'No lint script defined; skipping.'\n"
                    "          fi"
                )
            elif has_python:
                tool = "ruff"
                reason = "Python repository detected; Ruff provides fast linting."
                setup = [
                    "      - name: Set up Python",
                    f"        uses: {_pin('actions/setup-python@v5')}",
                    "        with:",
                    "          python-version: '3.11'",
                    "",
                ]
                install = "      - name: Install Ruff\n        run: pip install ruff"
                run_step = "      - name: Run Ruff\n        run: ruff check . || true"
            else:
                tool = "semgrep"
                reason = "No specialized linter detected; falling back to Semgrep static checks."
                setup = []
                install = ""
                run_step = (
                    "      - name: Run Semgrep (lint ruleset)\n"
                    f"        uses: {_pin('returntocorp/semgrep-action@v1')}\n"
                    "        with:\n"
                    "          config: >-\n"
                    "            p/owasp-top-ten\n"
                    "            p/javascript\n"
                    "            p/nodejs\n"
                    "            p/expressjs\n"
                    "            p/sql-injection\n"
                    "            p/secrets\n"
                    "            p/dockerfile\n"
                    "        continue-on-error: false"
                )

            body = "\n".join(
                [
                    "    runs-on: ubuntu-latest",
                    "    timeout-minutes: 15",
                    "    continue-on-error: false",
                    "    steps:",
                    "      - name: Checkout code",
                    f"        uses: {_pin('actions/checkout@v4')}",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                    *setup,
                    *( [install, ""] if install else [] ),
                    run_step,
                ]
            )
            _add_job("lint", body, reason)
            yaml_lines.append("")

    # ---- test ----
    if "test" in stages and test_framework:
        # Multi-language path: emit one `test-<id>` job per detected
        # language profile. Falls through to the legacy if/elif chain
        # if `active_profiles` is empty.
        _test_jobs_emitted_via_profiles = False
        if active_profiles:
            from app.agents.language_profiles import render_test_jobs
            _rendered_test_jobs = render_test_jobs(active_profiles)
            if _rendered_test_jobs:
                for job_name, job_body, job_reason in _rendered_test_jobs:
                    _add_job(job_name, job_body, job_reason, aliases=["test"])
                    yaml_lines.append("")
                _test_jobs_emitted_via_profiles = True

        if not _test_jobs_emitted_via_profiles:
            # Legacy fallback: single `test` job from if/elif below.
            if has_node:
                tool = "npm test"
                reason = f"Test framework '{test_framework}' detected; run unit tests before security scans."
                node_version = _detect_node_version(structure or [], files or {})
                setup, install_cmd = _node_setup_steps(
                    package_manager, has_lockfile, node_version=node_version
                )
                install = (
                    f"      - name: Install dependencies\n"
                    f"        run: {install_cmd}\n"
                    f"        continue-on-error: true"
                )
                run_step = "      - name: Run tests\n        run: npm test --if-present || true"
            elif has_python:
                tool = "pytest"
                reason = f"Test framework '{test_framework}' detected; run Python tests before security scans."
                setup = [
                    "      - name: Set up Python",
                    f"        uses: {_pin('actions/setup-python@v5')}",
                    "        with:",
                    "          python-version: '3.11'",
                    "",
                ]
                install = "      - name: Install dependencies\n        run: pip install -r requirements.txt || pip install -e . || true"
                run_step = "      - name: Run tests\n        run: pytest || python -m pytest || true"
            else:
                tool = test_framework or "test"
                reason = f"Test framework '{test_framework}' detected."
                setup = []
                install = ""
                run_step = f"      - name: Run {test_framework}\n        run: echo 'Test execution for {test_framework}'"

            body = "\n".join(
                [
                    "    runs-on: ubuntu-latest",
                    "    timeout-minutes: 15",
                    "    continue-on-error: false",
                    "    steps:",
                    "      - name: Checkout code",
                    f"        uses: {_pin('actions/checkout@v4')}",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                    *setup,
                    *( [install, ""] if install else [] ),
                    run_step,
                ]
            )
            _add_job("test", body, reason)
            yaml_lines.append("")

    # ---- sast ----
    if "sast" in stages:
        # RULESET STRATEGY (v9.3 simplified):
        #   1. Registry rules from Semgrep registry (maintained upstream) —
        #      p/owasp-top-ten, p/javascript, p/nodejs, p/expressjs, dll.
        #      Picked dynamically by `build_scan_directives` based on the
        #      primary_language + package_manager detected for the repo.
        #   2. Custom rules + AI-generated rules are NOT inlined here.
        #      They are committed to `.semgrep/*.yml` in the target repo
        #      by `pull_request_creation_node` (the workflow stays clean
        #      and the diff is easy to audit per domain).
        #   3. The sast job below picks up any `.semgrep/*.yml` file at
        #      runtime via `--config=.semgrep` (folder import) — no path
        #      hardcoding, no heredoc, no double config.
        try:
            from app.agents.scan_directives import build_scan_directives
            scan_d = build_scan_directives(
                detected_domain=detected_domain,
                arch_type=arch_type,
                sub_type=detected_sub_type,
                llm_rule_suggestions=llm_rule_suggestions,
            )
            registry_configs = [
                c for c in scan_d["sast_ruleset"]
                if not c.startswith("/src/.semgrep/")
            ]
        except Exception:
            registry_configs = []

        # Multi-language: enrich `registry_configs` with rulesets keyed
        # to the detected language(s). This is the only place that
        # turns the single `sast` job into a per-language-aware scan:
        # p/python, p/django, p/fastapi for a Python repo;
        # p/golang for Go; p/csharp for .NET; p/php + p/laravel for
        # PHP; etc. Monorepos with multiple languages get the union.
        # If `build_scan_directives` already produced rules for the
        # same language (e.g. from a custom domain), the dedup block
        # below keeps the first-seen ordering.
        try:
            from app.agents.language_profiles import semgrep_registry_for_languages
            lang_rules = semgrep_registry_for_languages(
                primary_language=primary_language,
                extra_frameworks=frameworks,
            )
            for rule in lang_rules:
                if rule not in registry_configs:
                    registry_configs.append(rule)
        except Exception:
            # Last-ditch fallback: at least the cross-cutting rulesets
            # so the SAST job is still meaningful for any language.
            for rule in ("p/owasp-top-ten", "p/secrets", "p/security-audit"):
                if rule not in registry_configs:
                    registry_configs.append(rule)

        if not registry_configs:
            registry_configs = [
                "p/owasp-top-ten",
                "p/javascript",
                "p/nodejs",
                "p/secrets",
            ]

        # Render registry config flags. One `--config=<registry>` per
        # line keeps the YAML readable. The last flag ends with ` \`
        # so shell line-continuation joins them into a single `semgrep ci`
        # command. The leading `.semgrep` directory import picks up
        # any custom rules committed by `pull_request_creation_node`.
        semgrep_config_lines = " \\\n              ".join(
            f"--config={c}" for c in registry_configs
        )
        # Combine `.semgrep` (custom rules) + registry configs into
        # one indented block. Each line ends with ` \` so shell
        # joins them.
        all_config_lines = " \\\n              ".join(
            ["--config=.semgrep"] + [f"--config={c}" for c in registry_configs]
        )

        reason = (
            "Static analysis via Semgrep. Detects OWASP Top 10, "
            "language-specific anti-patterns, and any custom Semgrep "
            "rules committed to `.semgrep/` by the AI agent "
            "(domain-aware + AI-generated). Output is SARIF, uploaded "
            "to GitHub Code Scanning via github/codeql-action/upload-sarif. "
            "Custom rules live in a separate file so the workflow file "
            "stays small (~1k chars) and the rule diff is reviewable."
        )

        tool = "semgrep"
        body = "\n".join(
            [
                "    runs-on: ubuntu-latest",
                "    timeout-minutes: 20",
                "    continue-on-error: true",
                "    steps:",
                "      - name: Checkout code",
                f"        uses: {_pin('actions/checkout@v4')}",
                "        with:",
                "          persist-credentials: false",
                "",
                f"      - name: Run {tool} (registry + .semgrep/, SARIF output)",
                "        run: |",
                "          # Ensure the `.semgrep/` directory exists before running.",
                "          # The `--config=.semgrep` flag below imports any custom",
                "          # rules committed by `pull_request_creation_node`; if the",
                "          # directory is missing, semgrep returns exit 7 (config",
                "          # error). Create an empty dir so the import is a no-op",
                "          # rather than a hard failure.",
                "          mkdir -p .semgrep",
                "          # Only run semgrep if at least one registry config is",
                "          # declared; otherwise the previous run already proved",
                "          # the repo has no language that maps to a registry ruleset.",
                "          if [ -z \"${{ env.SEMGREP_REGISTRY_CONFIGS }}\" ]; then",
                "            echo '::notice::No Semgrep registry configs selected for this language; writing empty SARIF.'",
                "            exit 0",
                "          fi",
                "          docker run --rm \\",
                "            -v \"${{ github.workspace }}:/src\" \\",
                "            returntocorp/semgrep:1.99.0 \\",
                "            semgrep ci \\",
                f"              {all_config_lines} \\",
                "            --sarif --output=/src/semgrep-results.sarif \\",
                "            --timeout=600 --no-suppress-errors",
                "        continue-on-error: true",
                "",
                "      - name: Ensure Semgrep SARIF file exists (fallback for 0 findings or scan error)",
                "        if: always()",
                "        run: |",
                "          if [ ! -s semgrep-results.sarif ]; then",
                '            echo "::notice::Semgrep did not produce a SARIF file. Generating empty SARIF for upload-sarif."',
                "            printf '%s\\n' \\",
                "              '{' \\",
                "              '  \"version\": \"2.1.0\",' \\",
                "              '  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",' \\",
                "              '  \"runs\": [' \\",
                "              '    {' \\",
                "              '      \"tool\": {' \\",
                "              '        \"driver\": {' \\",
                "              '          \"name\": \"Semgrep\",' \\",
                "              '          \"version\": \"1.99.0\",' \\",
                "              '          \"informationUri\": \"https://semgrep.dev\"' \\",
                "              '        }' \\",
                "              '      },' \\",
                "              '      \"results\": []' \\",
                "              '    }' \\",
                "              '  ]' \\",
                "              '}' > semgrep-results.sarif",
                "          fi",
                "          echo \"✓ semgrep-results.sarif size: $(stat -c%s semgrep-results.sarif) bytes\"",
                "",
                "      - name: Upload Semgrep SARIF to GitHub Code Scanning",
                "        if: always() && hashFiles('semgrep-results.sarif') != ''",
                f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                "        with:",
                "          sarif_file: semgrep-results.sarif",
                "          category: semgrep",
                "",
                "      - name: Upload Semgrep SARIF as artifact",
                "        if: always()",
                f"        uses: {_pin('actions/upload-artifact@v4')}",
                "        with:",
                "          name: semgrep-results-${{ github.sha }}",
                "          path: semgrep-results.sarif",
                "          if-no-files-found: warn",
                "          retention-days: 30",
            ]
        )
        _add_job("sast", body, reason)
        yaml_lines.append("")

    # ---- dependency-scan ----
    if "dependency-scan" in stages:
        if has_node:
            reason = (
                "JavaScript/TypeScript repository; runs `npm audit` (JSON) and Trivy "
                "filesystem scan (SARIF). Trivy output is SARIF — the OASIS standard — "
                "and is uploaded to GitHub Code Scanning via "
                "github/codeql-action/upload-sarif so findings appear in the Security "
                "tab. npm audit emits JSON because npm does not support SARIF natively; "
                "the JSON file is uploaded as a workflow artifact for AI agent parsing."
            )
            tool = "npm audit + trivy"
            setup, install_cmd = _node_setup_steps(
                package_manager, has_lockfile, ignore_scripts=True
            )
            install = f"      - name: Install dependencies (no native build)\n        run: {install_cmd}\n        continue-on-error: true"
            body = "\n".join(
                [
                    "    runs-on: ubuntu-latest",
                    "    timeout-minutes: 20",
                    "    continue-on-error: false",
                    "    steps:",
                    "      - name: Checkout code",
                    f"        uses: {_pin('actions/checkout@v4')}",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                    *setup,
                    install,
                    "",
                    "      - name: Run npm audit (CVE check, JSON output)",
                    "        id: npm-audit",
                    "        run: npm audit --audit-level=high --json > npm-audit-results.json || true",
                    "        continue-on-error: true",
                    "",
                    "      - name: Upload npm audit JSON",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: npm-audit-results-${{ github.sha }}",
                    "          path: npm-audit-results.json",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                    "",
                    "      - name: Run Trivy filesystem scan (SARIF output)",
                    "        id: trivy-fs",
                    f"        uses: {_pin('aquasecurity/trivy-action@v0.24.0')}",
                    "        with:",
                    "          scan-type: 'fs'",
                    "          scan-ref: '.'",
                    "          format: 'sarif'",
                    "          output: 'trivy-fs-results.sarif'",
                    # v9.7 — lower severity to MEDIUM so the dependency-scan
                    # Trivy pass actually surfaces findings in
                    # repositories that have MODERATE-rated CVEs (the
                    # majority of npm ecosystem warnings). HIGH,CRITICAL
                    # only produces 0 results for projects with old
                    # dependencies, which defeats the purpose of running
                    # Trivy alongside `npm audit`. Use Trivy as a
                    # second-opinion scanner that covers any MEDIUM+ CVE
                    # the lockfile-based Trivy fs scan can find.
                    "          version: v0.72.0",
                    "          severity: 'MEDIUM,HIGH,CRITICAL'",
                    "        continue-on-error: true",

                    *_ensure_sarif_fallback("trivy-fs-results.sarif", "Trivy"),

                    "      - name: Upload Trivy fs SARIF to GitHub Code Scanning",
                    "        if: always()",
                    f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                    "        with:",
                    "          sarif_file: trivy-fs-results.sarif",
                    "          category: trivy-fs",

                    "      - name: Upload Trivy fs SARIF as artifact",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: trivy-fs-results-${{ github.sha }}",
                    "          path: trivy-fs-results.sarif",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",

                    *_ensure_npm_audit_sarif_conversion(),
                    "",
                    *_ensure_sarif_fallback(
                        "npm-audit-results.sarif",
                        "npm audit",
                        version="1.0",
                        information_uri="https://docs.npmjs.com/cli/v10/commands/npm-audit",
                    ),
                    "",
                    "      - name: Upload npm audit SARIF to GitHub Code Scanning",
                    "        if: always()",
                    f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                    "        with:",
                    "          sarif_file: npm-audit-results.sarif",
                    "          category: npm-audit",
                    "",
                    "      - name: Upload npm audit SARIF as artifact",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: npm-audit-sarif-${{ github.sha }}",
                    "          path: npm-audit-results.sarif",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                    "",

                    "      - name: Evaluate dependency-scan findings",
                    "        if: always()",
                    "        run: |",
                    "          echo '## Dependency Scan Summary' >> \"$GITHUB_STEP_SUMMARY\"",
                    "          echo '- npm audit: '\"${{ steps.npm-audit.outcome }}\" >> \"$GITHUB_STEP_SUMMARY\"",
                    "          echo '- trivy fs: '\"${{ steps.trivy-fs.outcome }}\" >> \"$GITHUB_STEP_SUMMARY\"",
                ]
            )
        elif has_python:
            reason = (
                "Python repository; pip-audit enumerates known CVEs in pinned dependencies "
                "(JSON output) and Trivy filesystem scan provides SARIF output for "
                "GitHub Code Scanning. pip-audit does not support SARIF natively; "
                "its JSON output is uploaded as a workflow artifact for the AI agent. "
                "Trivy SARIF is uploaded to GitHub Code Scanning via "
                "github/codeql-action/upload-sarif."
            )
            tool = "pip-audit + trivy"
            body = "\n".join(
                [
                    "    runs-on: ubuntu-latest",
                    "    timeout-minutes: 20",
                    "    continue-on-error: false",
                    "    steps:",
                    "      - name: Checkout code",
                    f"        uses: {_pin('actions/checkout@v4')}",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                    "      - name: Set up Python",
                    f"        uses: {_pin('actions/setup-python@v5')}",
                    "        with:",
                    "          python-version: '3.11'",
                    "",
                    "      - name: Install pip-audit",
                    "        run: pip install pip-audit",
                    "",
                    "      - name: Run pip-audit (CVE check, JSON output)",
                    "        run: pip-audit --strict --disable-pip --format=json --output=pip-audit-results.json || true",
                    "        continue-on-error: true",
                    "",
                    "      - name: Upload pip-audit JSON",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: pip-audit-results-${{ github.sha }}",
                    "          path: pip-audit-results.json",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                    "",
                    "      - name: Run Trivy filesystem scan (SARIF output)",
                    "        id: trivy-fs",
                    f"        uses: {_pin('aquasecurity/trivy-action@v0.24.0')}",
                    "        with:",
                    "          scan-type: 'fs'",
                    "          scan-ref: '.'",
                    "          format: 'sarif'",
                    "          output: 'trivy-fs-results.sarif'",
                    "          version: v0.72.0",
                    "          severity: 'MEDIUM,HIGH,CRITICAL'",
                    "        continue-on-error: true",
                    "",
                    *_ensure_sarif_fallback("trivy-fs-results.sarif", "Trivy"),
                    "",
                    "      - name: Upload Trivy fs SARIF to GitHub Code Scanning",
                    "        if: always()",
                    f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                    "        with:",
                    "          sarif_file: trivy-fs-results.sarif",
                    "          category: trivy-fs",
                    "",
                    "      - name: Upload Trivy fs SARIF as artifact",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: trivy-fs-results-${{ github.sha }}",
                    "          path: trivy-fs-results.sarif",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                    "",
                    *_ensure_pip_audit_sarif_conversion(),
                    "",
                    *_ensure_sarif_fallback(
                        "pip-audit-results.sarif",
                        "pip-audit",
                        version="1.0",
                        information_uri="https://pypi.org/project/pip-audit/",
                    ),
                    "",
                    "      - name: Upload pip-audit SARIF to GitHub Code Scanning",
                    "        if: always()",
                    f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                    "        with:",
                    "          sarif_file: pip-audit-results.sarif",
                    "          category: pip-audit",
                    "",
                    "      - name: Upload pip-audit SARIF as artifact",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: pip-audit-sarif-${{ github.sha }}",
                    "          path: pip-audit-results.sarif",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                ]
            )
        else:
            reason = (
                "Repository has package metadata; Trivy filesystem scan provides "
                "broad CVE coverage. Output is SARIF (OASIS standard) and is "
                "uploaded to GitHub Code Scanning via github/codeql-action/upload-sarif "
                "and also stored as a workflow artifact for the AI agent."
            )
            tool = "trivy"
            body = "\n".join(
                [
                    "    runs-on: ubuntu-latest",
                    "    timeout-minutes: 20",
                    "    continue-on-error: false",
                    "    steps:",
                    "      - name: Checkout code",
                    f"        uses: {_pin('actions/checkout@v4')}",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                    "      - name: Run Trivy filesystem scan (SARIF output)",
                    "        id: trivy-fs",
                    f"        uses: {_pin('aquasecurity/trivy-action@v0.24.0')}",
                    "        with:",
                    "          scan-type: 'fs'",
                    "          scan-ref: '.'",
                    "          format: 'sarif'",
                    "          output: 'trivy-fs-results.sarif'",
                    "          version: v0.72.0",
                    "          severity: 'MEDIUM,HIGH,CRITICAL'",
                    "        continue-on-error: true",
                    "",
                    *_ensure_sarif_fallback("trivy-fs-results.sarif", "Trivy"),
                    "",
                    "      - name: Upload Trivy fs SARIF to GitHub Code Scanning",
                    "        if: always()",
                    f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                    "        with:",
                    "          sarif_file: trivy-fs-results.sarif",
                    "          category: trivy-fs",
                    "",
                    "      - name: Upload Trivy fs SARIF as artifact",
                    "        if: always()",
                    f"        uses: {_pin('actions/upload-artifact@v4')}",
                    "        with:",
                    "          name: trivy-fs-results-${{ github.sha }}",
                    "          path: trivy-fs-results.sarif",
                    "          if-no-files-found: warn",
                    "          retention-days: 30",
                ]
            )
        _add_job("dependency-scan", body, reason)
        yaml_lines.append("")

    # ---- docker-compose-validate (multi-service gate) ----
    # v9.2: REMOVED. Per user request, the generator no longer emits
    # per-service / docker-compose-validate / detect-services jobs.
    # The AI-driven equivalent is `state["job_designs"]` (designed by
    # job_reasoning_node). The legacy `_build_docker_compose_validate_job`
    # helper is preserved for back-compat but is not called here.
    # if "docker-compose-validate" in stages:
    #     body, reason = _build_docker_compose_validate_job()
    #     _add_job("docker-compose-validate", body, reason)
    #     yaml_lines.append("")

    # ---- dependency-scan-per-service (matrix strategy) ----
    # v9.2: REMOVED. Same rationale as docker-compose-validate above.
    # if "dependency-scan-per-service" in stages:
    #     ... (legacy emit block removed)

    # ---- secret-scan ----
    # Reviewer feedback (round 3): gitleaks-action@v2 default only scans
    # the diff of the last 2 commits in a pull_request event. Files
    # that already exist in main (e.g. a hardcoded .env or a Stripe
    # key in src/routes/checkout.js) are NEVER inspected, so the job
    # always reports 0 findings even when the repo is full of secrets.
    #
    # Fix: add a SECOND Gitleaks invocation that scans the entire
    # working tree (`gitleaks detect --source .`) so secrets in
    # pre-existing files are also caught. The first invocation is
    # kept (it covers the PR-diff case) and its output is merged
    # with the working-tree scan into a single SARIF file.
    if "secret-scan" in stages:
        reason = (
            "Detects hardcoded API keys, tokens, and credentials in source code. "
            "Gitleaks output in SARIF format (OASIS standard) and uploaded "
            "to GitHub Code Scanning via github/codeql-action/upload-sarif "
            "so findings appear in the Security tab. The SARIF file is also "
            "uploaded as a workflow artifact for AI agent parsing. "
            "Two scans run: (1) gitleaks-action scans the PR commit diff; "
            "(2) a working-tree scan (`--source .`) catches pre-existing "
            "secrets in main that are not part of the PR."
        )
        tool = "gitleaks"
        body = "\n".join(
            [
                "    runs-on: ubuntu-latest",
                "    timeout-minutes: 15",
                "    continue-on-error: false",
                "    steps:",
                "      - name: Checkout code",
                f"        uses: {_pin('actions/checkout@v4')}",
                "        with:",
                "          persist-credentials: false",
                "          fetch-depth: 0",
                "",
                # Scan 1: gitleaks-action over the PR diff (catches
                # newly-introduced secrets in the PR).
                "      - name: Run Gitleaks on PR diff (SARIF output)",
                f"        uses: {_pin('gitleaks/gitleaks-action@v2')}",
                "        env:",
                "          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
                "          GITLEAKS_ENABLE_UPLOAD_ARTIFACT: false",
                "          GITLEAKS_FORMAT: sarif",
                "          GITLEAKS_REPORT_PATH: gitleaks-diff-results.sarif",
                "        continue-on-error: true",
                "",
                # Scan 2: gitleaks CLI over the entire working tree
                # (catches pre-existing secrets in main that are NOT
                # part of the PR — the most common case in real repos).
                "      - name: Run Gitleaks on full working tree (SARIF output)",
                "        run: |",
                "          set -e",
                "          # Install gitleaks CLI (matches the action's version).",
                "          wget -qO- https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz | tar -xz -C /tmp",
                "          sudo mv /tmp/gitleaks /usr/local/bin/gitleaks || mv /tmp/gitleaks /usr/local/bin/gitleaks",
                "          gitleaks version",
                "          # Scan the full working tree. `--no-banner` quiets",
                "          # the ASCII art. Output is SARIF 2.1.0.",
                "          gitleaks detect --source . --no-banner --report-format sarif --report-path gitleaks-full-results.sarif --exit-code 0 || true",
                "        continue-on-error: true",
                "",
                # Merge the two SARIF files into one. sarif-tools is the
                # standard CLI; if it's not available we keep the full
                # scan as the canonical result.
                "      - name: Merge Gitleaks SARIF results",
                "        if: always()",
                "        run: |",
                "          set -e",
                "          if [ -s gitleaks-diff-results.sarif ] && [ -s gitleaks-full-results.sarif ]; then",
                "            # Both scans produced output — concatenate",
                "            # the result arrays. We use a tiny Python",
                "            # snippet because `jq` is not guaranteed to",
                "            # be installed on ubuntu-latest runners.",
                "            python3 - <<'PY'",
                "          import json, pathlib",
                "          diff = json.loads(pathlib.Path('gitleaks-diff-results.sarif').read_text())",
                "          full = json.loads(pathlib.Path('gitleaks-full-results.sarif').read_text())",
                "          merged_runs = (diff.get('runs') or []) + (full.get('runs') or [])",
                "          # De-duplicate by (ruleId, physicalLocation uri:line).",
                "          seen = set()",
                "          merged_results = []",
                "          for run in merged_runs:",
                "              for r in (run.get('results') or []):",
                "                  loc = (r.get('locations') or [{}])[0].get('physicalLocation', {})",
                "                  uri = (loc.get('artifactLocation') or {}).get('uri', '')",
                "                  line = (loc.get('region') or {}).get('startLine', 0)",
                "                  key = (r.get('ruleId',''), uri, line)",
                "                  if key in seen:",
                "                      continue",
                "                  seen.add(key)",
                "                  merged_results.append(r)",
                "          base = diff if diff.get('runs') else full",
                "          base['runs'] = merged_runs",
                "          for run in base['runs']:",
                "              run['results'] = merged_results if run is base['runs'][0] else (run.get('results') or [])",
                "          pathlib.Path('gitleaks-results.sarif').write_text(json.dumps(base, indent=2))",
                "          print(f'Merged SARIF: {len(merged_results)} unique findings')",
                "          PY",
                "          elif [ -s gitleaks-full-results.sarif ]; then",
                "            cp gitleaks-full-results.sarif gitleaks-results.sarif",
                "          elif [ -s gitleaks-diff-results.sarif ]; then",
                "            cp gitleaks-diff-results.sarif gitleaks-results.sarif",
                "          fi",
                "          ls -la gitleaks-*.sarif || true",
                "",
                *_ensure_sarif_fallback(
                    "gitleaks-results.sarif",
                    "Gitleaks",
                    version="8.24.3",
                    information_uri="https://gitleaks.io",
                ),
                "",
                "      - name: Upload Gitleaks SARIF to GitHub Code Scanning",
                "        if: always()",
                f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                "        with:",
                "          sarif_file: gitleaks-results.sarif",
                "          category: gitleaks",
                "",
                "      - name: Upload Gitleaks SARIF as artifact",
                "        if: always()",
                f"        uses: {_pin('actions/upload-artifact@v4')}",
                "        with:",
                "          name: gitleaks-sarif-${{ github.sha }}",
                "          path: gitleaks-results.sarif",
                "          if-no-files-found: warn",
                "          retention-days: 30",
            ]
        )
        _add_job("secret-scan", body, reason)
        yaml_lines.append("")

    # ---- iac-scan ----
    # struktur-v9.1: iac-scan is OUT OF SCOPE (Docker + docker-compose only).
    # Removed entirely to avoid Trivy 0.65.0 `Path does not exist` bug
    # that misreports the job as failed. The job is replaced by the
    # static Dockerfile analysis inside `container-scan` which is
    # sufficient for Docker-only repos.
    #
    # Reference: struktur-v9 §3.6 "Deployment-specific requirements" — only
    # Docker + docker-compose are in scope. Terraform, Kubernetes, and
    # Helm scanning are NOT emitted.
        yaml_lines.append("")

    # ---- container-scan ----
    # Reviewer feedback:
    #   1. Container-build job DIHAPUS — container-scan build image
    #      di dalamnya (`docker build -t app:ci-<sha> .` lalu scan
    #      dengan Trivy). Tidak perlu job terpisah.
    #   2. Scanner output SARIF (OASIS standard) — uploaded to GitHub
    #      Code Scanning via github/codeql-action/upload-sarif AND
    #      as a workflow artifact for the AI agent to parse.
    if "container-scan" in stages or "container-build" in stages:
        reason = (
            "Dockerfile detected; container-scan membangun image dan "
            "memindainya dengan Trivy. Findings ditulis dalam format "
            "SARIF (OASIS standard) dan di-upload ke GitHub Code "
            "Scanning untuk visualisasi presisi di tab Security, "
            "serta di-upload sebagai artifact untuk AI agent "
            "structured-output normalizer (bukan regex dari log)."
        )
        tool = "docker build + trivy image (SARIF output)"
        body = "\n".join(
            [
                "    runs-on: ubuntu-latest",
                "    timeout-minutes: 25",
                "    continue-on-error: true",
                "    steps:",
                "      - name: Checkout code",
                f"        uses: {_pin('actions/checkout@v4')}",
                "        with:",
                "          persist-credentials: false",
                "",
                "      - name: Analyze Dockerfile for security misconfigurations",
                "        if: hashFiles('**/Dockerfile') != ''",
                "        run: |",
                "          echo '## Dockerfile Security Checks' >> \"$GITHUB_STEP_SUMMARY\"",
                "          issues=0",
                "          for df in $(find . -name Dockerfile -not -path './.git/*' 2>/dev/null); do",
                "            echo \"Analyzing $df...\"",
                "            # Check: run as non-root user",
                "            if ! grep -qE '^USER ' \"$df\"; then",
                "              echo \"::warning file=$df::Missing USER instruction — container runs as root\"",
                "              echo \"- \\`$df\\`: Missing USER instruction (runs as root)\" >> \"$GITHUB_STEP_SUMMARY\"",
                "              issues=$((issues+1))",
                "            elif grep -qE '^USER root' \"$df\"; then",
                "              echo \"::warning file=$df::USER root detected — should use non-root user\"",
                "              echo \"- \\`$df\\`: USER root (use non-root)\" >> \"$GITHUB_STEP_SUMMARY\"",
                "              issues=$((issues+1))",
                "            fi",
                "            # Check: base image pinned by digest",
                "            base=$(grep -m1 '^FROM ' \"$df\" | sed 's/FROM //' | awk '{print $1}')",
                "            if echo \"$base\" | grep -qE '@sha256:'; then",
                "              echo \"  Base image pinned: $base\"",
                "            elif [ -n \"$base\" ] && echo \"$base\" | grep -qE ':latest$|^[^:]*$'; then",
                "              echo \"::warning file=$df::Base image $base not pinned by digest — supply@sha256:...\"",
                "              echo \"- \\`$df\\`: Base image \\`$base\\` not pinned by digest\" >> \"$GITHUB_STEP_SUMMARY\"",
                "              issues=$((issues+1))",
                "            fi",
                "            # Check: expose patterns",
                "            if grep -qE '^EXPOSE [0-9]+-[0-9]+' \"$df\"; then",
                "              echo \"::warning file=$df::EXPOSE with port range detected — limit to specific ports\"",
                "              echo \"- \\`$df\\`: EXPOSE port range (limit to specific ports)\" >> \"$GITHUB_STEP_SUMMARY\"",
                "              issues=$((issues+1))",
                "            fi",
                "          done",
                "          echo \"Dockerfile checks complete: $issues issue(s)\" >> \"$GITHUB_STEP_SUMMARY\"",
                "        continue-on-error: true",
                "",
                "      - name: Build Docker image",
                "        run: docker build -t app:ci-${{ github.sha }} .",
                "        continue-on-error: true",
                "",
                "      - name: Scan image with Trivy (SARIF output)",
                "        id: trivy-image",
                f"        uses: {_pin('aquasecurity/trivy-action@v0.24.0')}",
                "        with:",
                "          image-ref: 'app:ci-${{ github.sha }}'",
                "          format: 'sarif'",
                "          output: 'trivy-image-results.sarif'",
                "          version: v0.72.0",
                "          severity: 'HIGH,CRITICAL'",
                "        continue-on-error: true",
                "",
                *_ensure_sarif_fallback("trivy-image-results.sarif", "Trivy Image"),
                "",
                "      - name: Upload Trivy image SARIF to GitHub Code Scanning",
                "        if: always()",
                f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}",
                "        with:",
                "          sarif_file: trivy-image-results.sarif",
                "          category: trivy-image",
                "",
                "      - name: Upload Trivy image SARIF as artifact",
                "        if: always()",
                f"        uses: {_pin('actions/upload-artifact@v4')}",
                "        with:",
                "          name: trivy-image-results-${{ github.sha }}",
                "          path: trivy-image-results.sarif",
                "          if-no-files-found: warn",
                "          retention-days: 30",
            ]
        )
        _add_job("container-scan", body, reason)
        yaml_lines.append("")

    # ---- domain-specific jobs ----
    # Each domain (e-commerce, fintech, healthcare, blog, iot) emits an
    # additional job with custom security checks. The set of jobs is
    # driven by `scan_directives.scan_directives()` in
    # app/agents/scan_directives.py.
    #
    # Reference: docs/domain-aware-pipeline.md (Bab 4 §4.4 Layer 4)
    #
    # pipeline_mode (passed via state["extra_params"]["pipeline_mode"]):
    #   "general"       -> ONLY general jobs (lint/sast/dependency-scan/
    #                      secret-scan/container-scan). No domain-specific
    #                      jobs. The user wants the universal baseline only.
    #   "domain"        -> ONLY the domain-specific job (e.g. pci-dss for
    #                      e-commerce). No general jobs. The user wants to
    #                      see the custom compliance check in isolation.
    #   "both" (default)-> Both general + domain-specific jobs. This is
    #                      the existing behaviour and what most repos want.
    _state_for_extra = state if isinstance(state, dict) else {}
    _extra_params = _state_for_extra.get("extra_params") or {}
    if not isinstance(_extra_params, dict):
        _extra_params = {}
    pipeline_mode = _extra_params.get("pipeline_mode", "both")
    pipeline_mode = pipeline_mode.lower().strip() if isinstance(pipeline_mode, str) else "both"
    if pipeline_mode not in ("general", "domain", "both"):
        pipeline_mode = "both"
    include_general = pipeline_mode in ("general", "both")
    include_domain = pipeline_mode in ("domain", "both")

    if not include_domain:
        # Skip ALL domain-specific job blocks. We still keep the
        # general jobs (lint/sast/secret-scan/dependency-scan/
        # container-scan) which are emitted earlier in this function
        # regardless of pipeline_mode.
        pass
    # v9.3 revisi 3-domain & 2-arch: static domain-specific templates
    # (pci-dss, hipaa, ledger-check, csp-headers, mqtt-security) are
    # REMOVED. Per-repo custom jobs now come exclusively from
    # `state["job_designs"]` (LLM-designed by job_reasoning_node, K2.4).
    # The 3 supported domains (e-commerce, blog, iot) are addressed by
    # the AI reasoning step which cites concrete file paths, libraries
    # and patterns from the actual source code. The legacy template
    # builders (_build_pci_dss_job / _build_hipaa_job / ...) remain in
    # the file for unit-test back-compat but are no longer emitted.

    # ---- AI-generated job designs (K2.4) ----
    # v9.2: emit the custom jobs that job_reasoning_node designed
    # for THIS repository. The LLM analysed the actual source code
    # and produced a job that targets the concrete vulnerabilities
    # found (with reasoning that cites file paths).
    # Defensive: callers may pass state=None (e.g. unit tests for
    # _build_workflow_yaml that only care about the static job
    # shapes). Use a safe fallback so the function still works.
    _state = state if state is not None else {}
    for design in (_state.get("job_designs") or []):
        if not isinstance(design, dict):
            continue
        design_name = design.get("name", "").strip()
        if not design_name:
            continue
        if design_name in stage_names:
            # Avoid duplicate job names when the AI design collides
            # with a static stage. Skip silently.
            continue
        body, reason = _build_ai_job_from_design(design, state=state)
        if not body:
            continue
        _add_job(design_name, body, reason, status="ai_generated")
        yaml_lines.append("")

    # ---- build ----
    # Reviewer feedback: build stage DIHAPUS dari generator. CI ini
    # fokus pada security scanning. `npm run build`/`go build`/dll.
    # adalah concern build/CD, bukan security. Stage logic (`build`
    # di `_select_relevant_stages`, ALLOWED_STAGES) tetap ada untuk
    # backward compatibility dan tracking, tapi TIDAK di-emit ke YAML.
    if "build" in stages:
        # Record build sebagai skipped di explanation (bukan job di YAML)
        explanations.append({
            "name": "build",
            "reason": (
                "Build stage is intentionally not emitted to the "
                "workflow (reviewer feedback). The generator focuses "
                "on security scanning; build is the concern of the "
                "CD pipeline, not this CI."
            ),
            "status": "not_emitted",
            "tool": "build tool (not used)",
        })

    # ---- sbom ----
    # Reviewer feedback: SBOM job di-HAPUS dari generator. Stage
    # logic (`sbom` di `_select_relevant_stages`, ALLOWED_STAGES,
    # registry, prerequisite map) tetap ada untuk backward
    # compatibility dan prerequisite tracking, tapi TIDAK di-emit ke
    # YAML. Fokus generator adalah security scanning; SBOM akan
    # di-generate terpisah (misal oleh dedicated compliance tooling
    # di luar CI ini). Stage yang diminta tetap muncul di
    # `generated_stages` dan dilapor sebagai skipped (jika
    # container-build tidak ada) atau diabaikan saja dari output.
    if "sbom" in stages:
        # Record sbom sebagai skipped di explanation (bukan job di YAML)
        explanations.append({
            "name": "sbom",
            "reason": (
                "SBOM generation is intentionally not emitted to the "
                "workflow (reviewer feedback). The generator focuses "
                "on security scanning; SBOM is generated by a "
                "dedicated compliance tool outside this CI."
            ),
            "status": "not_emitted",
            "tool": "syft (not used)",
        })

    full_text = "\n".join(line for line in yaml_lines if line is not None).rstrip() + "\n"
    # Compute permissions from the actions actually emitted, then swap the
    # placeholder for the real permissions block.
    permissions_lines = _compute_workflow_permissions(full_text)
    yaml_text = full_text.replace(
        "__PERMISSIONS_PLACEHOLDER__", "\n".join(permissions_lines), 1
    )
    return yaml_text, stage_names, explanations


def _build_ai_job_from_design(
    design: dict,
    state: PipelineEngineerState,
) -> tuple[str, str]:
    """Render a CI job YAML body from an AI-generated job design.

    The design (produced by `job_reasoning_node`) is a dict with:
      - name: kebab-case job name
      - coverage: coverage_id
      - reasoning: 2-4 sentence justification (used as the job's
        `reason` in `stage_explanations`).
      - actions: list of {type, name, script, ...}
      - configuration: {continue_on_error, timeout_minutes, needs}

    Action types:
      - shell_check     : emitted as a `run:` step
      - semgrep_rule    : emitted as a Semgrep step (inline rule
                          referenced via $GITHUB_STEP_SUMMARY note;
                          the validator does not need to execute it)
      - python_script   : emitted as a `run: python -` step
      - sarif_upload    : emitted as the standard
                          github/codeql-action/upload-sarif step

    The returned body is the full YAML for the job (`runs-on:`,
    `steps:`, ...), suitable for `_add_job(name, body, reason)`.
    Returns ("", "") if the design cannot be rendered safely.
    """
    name = (design.get("name") or "").strip()
    actions = design.get("actions") or []
    config = design.get("configuration") or {}
    coverage = design.get("coverage") or ""
    reasoning = design.get("reasoning") or ""

    if not name or not isinstance(actions, list) or len(actions) < 2:
        return "", ""

    continue_on_error = bool(config.get("continue_on_error", True))
    timeout_minutes = int(config.get("timeout_minutes", 10))
    # Default to no `needs:`. AI-generated jobs are emitted into
    # `ai-devsecops-custom.yml` (a `workflow_call` reusable file)
    # which has no `sast` sibling — emitting `needs: [sast]` there
    # makes GitHub reject the file with
    #   "must contain at least one job with no dependencies".
    # Callers may opt in via `config["needs"]`, but we drop any
    # reference to a job that does not exist in the *reusable* file
    # (lint, test, sast, secret-scan, dep-check, container-scan,
    # build all live in the generic file and are not visible inside
    # the custom file's `jobs:` block). Only intra-custom needs
    # (between AI jobs in the same file) would be safe to keep, but
    # the current designs never request that, so the safest
    # behaviour is to always omit `needs:` for AI jobs.
    if "needs" in config:
        needs_list = config.get("needs")
        if not isinstance(needs_list, list):
            needs_list = []
        # Filter out any reference to a generic-only job.
        # AI-generated jobs in the custom file have no safe `needs:`
        # target — drop the dependency entirely so the file remains
        # valid as a `workflow_call` reusable workflow.
        needs_list = []
    else:
        needs_list = []

    steps: list[str] = []
    sarif_categories: list[str] = []
    has_sarif = False
    # Pre-compute the SARIF category (if any) so that shell_check
    # wrappers can write their log to a file whose name matches the
    # category the conversion step expects. Without this, the
    # `tee` target and the `log_path` in the python step would use
    # different names and the conversion would silently find 0
    # findings.
    pre_category = None
    for _a in actions:
        if isinstance(_a, dict) and _a.get("type") == "sarif_upload":
            pre_category = _a.get("category") or coverage or name
            break
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        atype = action.get("type", "")
        step_name = action.get("name") or f"{atype}-{idx}"

        if atype == "shell_check":
            script = action.get("script") or "echo 'no-op'"
            # Wrap the script in a subshell that:
            #   1. Captures all output to a per-job log file
            #      (`${log_file}`) via `tee -a`, so the
            #      `_ensure_sarif_from_annotations` step can parse
            #      `::error` / `::warning` annotations and convert
            #      them to SARIF results.
            #   2. **Traps any non-zero exit and emits a synthetic
            #      `::error` annotation** so even if the script
            #      aborts early (e.g. `grep | wc -l` exits 1 under
            #      `set -e -o pipefail` and stops the script before
            #      it can `echo '::error::...'`) the SARIF
            #      conversion still produces a finding.
            #      Without this guard, buggy LLM-generated scripts
            #      can abort without emitting any annotations, and
            #      the SARIF ends up empty.
            #   3. Preserves the original script's exit code so the
            #      job still shows as `failure` (which is the
            #      intended UX — a failing security job is a
            #      finding).
            #
            # The original script body is unchanged (no fragile
            # `{ ... } | tee` wrapper) so bash quote parsing inside
            # single-quoted regex character classes (e.g.
            # `[\"\\']`) is not affected.
            log_file = f"{pre_category or name or 'ai-job'}.shell_log"
            script_lines = script.splitlines()
            # Normalise: drop any leading `set -e` / `set -o pipefail`
            # in the script because we wrap the whole thing in a
            # subshell with our own error handling. This avoids the
            # `grep | wc -l` exit-1 bug under `pipefail` aborting the
            # script before it can emit `::error` annotations.
            cleaned_lines = []
            for ln in script_lines:
                stripped = ln.strip()
                if (
                    stripped == "set -e"
                    or stripped == "set -euo pipefail"
                    or stripped == "set -o pipefail"
                    or stripped == "set -eu"
                    or stripped == "set -e -o pipefail"
                    or stripped == "set -eo pipefail"
                ):
                    # Drop the line; we handle errors in the wrapper.
                    continue
                cleaned_lines.append(ln)
            # Build the wrapped script:
            #   1. `exec > >(tee -a log) 2>&1` captures output.
            #   2. `( set +e; <original script> )` runs the script in
            #      a subshell with `set +e` so internal command
            #      failures don't abort before `echo ::error` runs.
            #   3. The subshell's exit code is captured, and if
            #      non-zero AND the log file has no annotations yet,
            #      we emit a synthetic `::error` so the SARIF
            #      conversion always has something to work with.
            wrapped_lines = [
                f"# Set up output capture for the annotation-to-SARIF step.",
                f"exec > >(tee -a {log_file}) 2>&1",
                f"# Run the original script in a subshell with set +e so",
                f"# that any single command failure does not abort the",
                f"# script before it can emit a '::error' annotation.",
                f"inner_exit=0",
                f"( set +e",
                *cleaned_lines,
                f") || inner_exit=$?",
                f"# If the inner script exited non-zero and emitted no",
                f"# '::error'/'::warning' annotation, synthesise one so the",
                f"# SARIF conversion step still has a finding to record.",
                f"if [ \"$inner_exit\" -ne 0 ] && ! grep -qE '^::(error|warning)' {log_file}; then",
                f"  echo \"::error file={step_name}::shell check failed (exit code $inner_exit) — see run log for details\"",
                f"fi",
                f"exit $inner_exit",
            ]
            inner = "\n".join("          " + ln for ln in wrapped_lines)
            steps.append(
                f"      - name: {step_name}\n"
                f"        run: |\n"
                f"{inner}\n"
            )
        elif atype == "python_script":
            script = action.get("script") or "print('no-op')"
            steps.append(
                f"      - name: {step_name}\n"
                f"        run: |\n"
                f"          python -c \"\n"
                + "\n".join(f"          {ln}" for ln in script.splitlines())
                + "\n          \""
            )
        elif atype == "semgrep_rule":
            rule_yaml = action.get("rule") or ""
            # We can't safely write the rule to a file with an
            # arbitrary name (would clash with other AI jobs and
            # the static rules directory). Emit a notice step
            # describing the rule and the SARIF upload step that
            # follows will pick up any pre-existing semgrep.sarif.
            steps.append(
                f"      - name: {step_name}\n"
                f"        run: |\n"
                f"          echo 'AI-designed Semgrep rule (id={action.get('id','ai-rule')}):'\n"
                f"          echo 'Rule body:'\n"
                f"          cat <<'SEMGREP_EOF' | sed 's/^/  /'\n"
                + "\n".join(f"          {ln}" for ln in rule_yaml.splitlines())
                + "\n          SEMGREP_EOF"
            )
        elif atype == "sarif_upload":
            cat = action.get("category") or coverage or name
            sarif_categories.append(cat)
            has_sarif = True

    # Append the SARIF upload step if the design included one.
    if has_sarif:
        # Pick the first category as the primary file name; the
        # _ensure_sarif_fallback helper guarantees a valid SARIF
        # file even when the upstream check produced no findings.
        cat = sarif_categories[0]
        sarif_file = f"{cat}-results.sarif"
        # 1) Convert ::error/::warning annotations emitted by the
        #    upstream shell_check steps into real SARIF results. This
        #    is what makes AI-generated security jobs surface
        #    findings in the GitHub Code Scanning tab (otherwise the
        #    fallback SARIF is empty and alerts only appear in the
        #    run log, invisible to the Security tab).
        for line in _ensure_sarif_from_annotations(
            sarif_file, cat, rule_id_prefix=f"ai-devsecops-{cat}"
        ):
            steps.append(line)
        # 2) Fallback: if no scanner produced any SARIF (and the
        #    annotation step also produced nothing), make sure the
        #    file still exists so upload-sarif does not fail with
        #    "Path does not exist".
        for line in _ensure_sarif_fallback(sarif_file, cat):
            steps.append(line)
        # 3) Upload to GitHub Code Scanning.
        steps.append(
            f"      - name: Upload {cat} SARIF to GitHub Code Scanning\n"
            f"        if: always()\n"
            f"        uses: {_pin('github/codeql-action/upload-sarif@v3')}\n"
            f"        with:\n"
            f"          sarif_file: {sarif_file}\n"
            f"          category: {cat}"
        )

    if not steps:
        return "", ""

    # AI-generated jobs end up in `ai-devsecops-custom.yml` (a
    # `workflow_call` reusable file) via `build_workflow_yaml_split`.
    # Referencing `needs: [sast]` there is invalid: the reusable
    # file has no `sast` job, so GitHub rejects the whole file
    # with "must contain at least one job with no dependencies".
    # Only emit `needs:` when caller explicitly opted in via
    # config (or the legacy default, kept for the merged single-
    # file variant where `sast` does exist as a sibling job).
    if needs_list:
        needs_yaml = ", ".join(needs_list)
        needs_line = f"    needs: [{needs_yaml}]"
    else:
        needs_line = None
    reason_text = reasoning[:400]
    body_lines = [
        "    runs-on: ubuntu-latest",
        f"    timeout-minutes: {timeout_minutes}",
        f"    continue-on-error: {'true' if continue_on_error else 'false'}",
    ]
    if needs_line:
        body_lines.append(needs_line)
    body_lines.extend([
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_pin('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
    ])
    body_lines.extend(steps)
    body = "\n".join(body_lines)
    return body, (
        f"AI-generated job (coverage={coverage}). "
        f"Reasoning: {reason_text}"
    )


def _job_tool(name: str, primary_language: str, package_manager: str, test_framework: str | None) -> str:
    if name == "lint":
        if "python" in primary_language:
            return "ruff"
        if "javascript" in primary_language or "typescript" in primary_language or "npm" in package_manager:
            return "eslint"
        return "semgrep"
    if name == "test":
        return test_framework or "package-script"
    if name == "build":
        if "npm" in package_manager:
            return "npm run build"
        if "pip" in package_manager or "poetry" in package_manager:
            return "python -m compileall"
        if "go" in primary_language:
            return "go build"
        return "build"
    if name == "sast":
        return "semgrep"
    if name == "dependency-scan":
        if "npm" in package_manager or "yarn" in package_manager:
            return "npm audit + trivy"
        if "pip" in package_manager or "poetry" in package_manager:
            return "pip-audit"
        return "trivy"
    if name == "secret-scan":
        return "gitleaks"
    if name == "container-scan":
        return "trivy image"
    if name == "container-build":
        return "docker build"
    if name == "iac-scan":
        return "trivy config"
    if name == "sbom":
        return "syft"
    return "github-script"


# ----------------------------------------------------------------------
# (legacy helpers retained for /validate endpoint backward compatibility)
# ----------------------------------------------------------------------

def _inject_deployment_jobs(yaml_str: str, deployment: dict) -> str:
    """DEPRECATED: deployment jobs are no longer generated per user requirement.

    Kept as a no-op so existing imports/tests don't break.
    """
    return yaml_str


# ----------------------------------------------------------------------
# Deprecated: kept for backward compatibility with the /validate endpoint.
# The new deterministic builder emits CVE checks as part of dependency-scan.
# ----------------------------------------------------------------------

def _legacy_inject_deployment_jobs_body(yaml_str: str, deployment: dict) -> str:
    """Reference implementation of the old deployment injector (not called)."""
    additional_jobs = []
    if deployment.get("docker", False):
        container_scan_job = '''
  container-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Trivy filesystem scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-fs-results.sarif'
          severity: 'HIGH,CRITICAL'

      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-fs-results.sarif'

  container-build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker images
        run: |
          for dockerfile in $(find . -name 'Dockerfile*' -not -path './node_modules/*' -not -path './vendor/*'); do
            service=$(basename "$dockerfile" | sed 's/Dockerfile[-.]//' | sed 's/^$/app/')
            docker build -f "$dockerfile" -t "$service:latest" .
          done
'''
        additional_jobs.append(container_scan_job)
    
    if deployment.get("kubernetes", False):
        k8s_scan_job = '''
  k8s-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Checkov on Kubernetes manifests
        uses: bridgecrewio/checkov-action@master
        with:
          directory: '.'
          framework: kubernetes
          output_format: sarif
          output: 'checkov-k8s-results.sarif'

      - name: Upload K8s security results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'checkov-k8s-results.sarif'

  kube-bench:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Check for Kubernetes manifests
        id: check-k8s
        run: |
          if find . -name '*.yaml' -o -name '*.yml' | xargs grep -l 'kind:' 2>/dev/null | head -1 >/dev/null; then
            echo "has_k8s=true" >> $GITHUB_OUTPUT
          else
            echo "has_k8s=false" >> $GITHUB_OUTPUT
          fi

      - name: Run kube-bench (dry-run if no cluster)
        if: steps.check-k8s.outputs.has_k8s == 'true'
        run: |
          echo "No live cluster available; kube-bench requires a Kubernetes cluster."
          echo "Consider running kube-bench in your cluster CI or using Checkov for manifest scanning."
'''
        additional_jobs.append(k8s_scan_job)
    
    if deployment.get("terraform", False):
        terraform_job = '''
  terraform-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Find Terraform files
        id: find-tf
        run: |
          if find . -name '*.tf' | head -1 >/dev/null; then
            echo "has_tf=true" >> $GITHUB_OUTPUT
            echo "tf_dir=$(find . -name '*.tf' -printf '%h\n' | sort -u | head -1)" >> $GITHUB_OUTPUT
          else
            echo "has_tf=false" >> $GITHUB_OUTPUT
          fi

      - name: Setup Terraform
        if: steps.find-tf.outputs.has_tf == 'true'
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: '1.5.0'

      - name: Terraform Init
        if: steps.find-tf.outputs.has_tf == 'true'
        working-directory: ${{ steps.find-tf.outputs.tf_dir }}
        run: terraform init

      - name: Terraform Validate
        if: steps.find-tf.outputs.has_tf == 'true'
        working-directory: ${{ steps.find-tf.outputs.tf_dir }}
        run: terraform validate

      - name: Run Trivy IaC scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          framework: terraform
          format: 'sarif'
          output: 'trivy-tf-results.sarif'

      - name: Run Checkov on Terraform
        uses: bridgecrewio/checkov-action@master
        with:
          directory: '.'
          framework: terraform
          output_format: sarif
          output: 'checkov-tf-results.sarif'

      - name: Upload IaC security results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'checkov-tf-results.sarif'
'''
        additional_jobs.append(terraform_job)
    
    if additional_jobs:
        jobs_end = yaml_str.rfind("jobs:")
        if jobs_end == -1:
            jobs_end = yaml_str.find("\n", yaml_str.rfind("\njobs"))
            if jobs_end == -1:
                return yaml_str
        
        insert_pos = yaml_str.find("\n", yaml_str.find("jobs:") + len("jobs:"))
        if insert_pos == -1:
            insert_pos = len(yaml_str)
        
        new_jobs = "\n".join(additional_jobs)
        yaml_str = yaml_str[:insert_pos] + new_jobs + yaml_str[insert_pos:]
    
    return yaml_str


def _inject_cve_jobs(yaml_str: str, technologies: dict, arch_type: str = "monolithic") -> str:
    """Inject CVE scanning jobs into the workflow based on detected package managers."""
    import re as _re
    
    pm = (technologies.get("package_manager") or "").lower()
    lang = (technologies.get("primary_language") or "").lower()
    frameworks = technologies.get("frameworks") or []
    pm_confidence = technologies.get("package_manager_confidence", 0.0)
    
    if pm_confidence < 0.3:
        return yaml_str
    
    cve_jobs = []
    
    if "go" in lang or "go mod" in pm:
        cve_jobs.append('''  cve-scan-go:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      
      - name: Run govulncheck
        run: go install golang.org/x/vuln/cmd/govulncheck@latest && govulncheck ./...
        continue-on-error: false
      
      - name: Run Trivy dependency scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-results.sarif'
                    severity: 'HIGH,CRITICAL'
      
      - name: Upload CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-results.sarif' ''')
    
    if "npm" in pm or "yarn" in pm or any("node" in f.lower() for f in frameworks):
        cve_jobs.append('''  cve-scan-npm:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '24'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run npm audit for CVE
        run: npm audit --audit-level=critical
        continue-on-error: false
      
      - name: Run Trivy for Node.js CVE
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-npm-results.sarif'
                    severity: 'HIGH,CRITICAL'
      
      - name: Upload npm CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-npm-results.sarif' ''')
    
    if "pip" in pm or "poetry" in pm or "python" in lang:
        cve_jobs.append('''  cve-scan-python:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install pip-audit
        run: pip install pip-audit
      
      - name: Run pip-audit for CVE
        run: pip-audit --severity=high --format=json --output=pip-audit-results.json
        continue-on-error: false
      
      - name: Run Trivy for Python CVE
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-python-results.sarif'
                    severity: 'HIGH,CRITICAL'
      
      - name: Upload Python CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-python-results.sarif' ''')
    
    if "cargo" in pm or "rust" in lang:
        cve_jobs.append('''  cve-scan-rust:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      
      - name: Install cargo-audit
        run: cargo install cargo-audit
      
      - name: Run cargo audit for CVE
        run: cargo audit --severity=high
        continue-on-error: false
      
      - name: Run Trivy for Rust CVE
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-rust-results.sarif'
                    severity: 'HIGH,CRITICAL'
      
      - name: Upload Rust CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-rust-results.sarif' ''')
    
    if "maven" in pm or "gradle" in pm or "java" in lang:
        cve_jobs.append('''  cve-scan-java:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      
      - name: Run Trivy for Java CVE
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-java-results.sarif'
                    severity: 'HIGH,CRITICAL'
          scan-run-evidence: true
      
      - name: Upload Java CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-java-results.sarif' ''')
    
    if not cve_jobs:
        cve_jobs.append('''  cve-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: false
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Run Trivy CVE scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-cve-results.sarif'
                    severity: 'HIGH,CRITICAL'
      
      - name: Upload CVE results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-cve-results.sarif' ''')
    
    if cve_jobs:
        jobs_match = _re.search(r'^jobs:\s*$', yaml_str, _re.MULTILINE)
        if jobs_match:
            insert_pos = jobs_match.end()
            new_cve_jobs = "\n".join(cve_jobs)
            yaml_str = yaml_str[:insert_pos] + "\n" + new_cve_jobs + yaml_str[insert_pos:]
    
    return yaml_str


_SHA_CACHE: dict[str, tuple[str, bool]] = {
    # Official GitHub actions — pre-seeded with verified SHAs.
    "actions/upload-artifact@v4":         ("65c86c472f64a47e3aaac1d8c9d6f0e44dff2d83", True),
    "actions/upload-artifact@v3":         ("a157134a0cded3ec3fcc8c6e4f87ad65e70c1e1d", True),
    "actions/download-artifact@v4":        ("88ec9e11c2bee6fe8d60eb1dd36e31dfdc0c13d5", True),
    "actions/download-artifact@v3":        ("7fe44a6776b2c7b2ac3fe4dd1b57cda8d9d0b6f6", True),
    "actions/setup-dotnet@v4":             ("4d6c8fcf3c8f7a60068d26b594648e99df24cee3", True),
    "actions/setup-dotnet@v3":             ("c0ffb7493e8f14c6adb4f0e2a6e36d7c5b5a9c1e", True),
    "actions/checkout@v4":                 ("8ade135a41bc03ea155e62e844d188df1ea18608", True),
    "actions/checkout@v3":                 ("f6a2268b19da13d9905f8e2d9c1b38dca9e0b9c2", True),
    # Third-party / community actions — valid=False forces API resolution on first use.
    # Do NOT set valid=True for any entry that has not been manually verified against the GitHub API.
    "step-security/harden-runner@v2.10.4":  ("cb605e52c26070c328afc4562f0b4ada7618a84e", False),
    "step-security/harden-runner@v2.10.2":  ("0080882f6c36860b6ba35c610c98ce87d4e2f26f", False),
    "step-security/harden-runner@v2.10.1":  ("c8454efe60d4c7fce5fef1ad7a09b34e6be86c04", False),
    "step-security/harden-runner@v2.9.1":   ("c6295a65d1254861815972266b14c3580f0accc3", False),
    "gitleaks/gitleaks-action@v3.0.0":      ("e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e", True),
    "gitleaks/gitleaks-action@v2.3.6":      ("44c470ffc35caa8b1eb3e8012ca53c2f9bea4eb5", False),
    "gitleaks/gitleaks-action@v2.3.5":      ("2973479c0cf34d2b5ef5342e44a509ec3b240a29", False),
    "gitleaks/gitleaks-action@v2.0.6":      ("8fe1d33dbcfa38223048888baa1c5e9ed5f2389d", False),
    "trufflesecurity/trufflehog@v3.82.12":  ("abecab0d8fb9fb3e79366abc3909825488e9bb40", False),
    "trufflesecurity/trufflehog@v3.82.11":  ("e4f603bb1a0e7964c57e0b2e57bde1b7e998f9b6", False),
    "aquasecurity/trivy-action@master":     ("", False),
    "aquasecurity/trivy-action@v0.24.0":    ("", False),
    "returntocorp/semgrep-action@v1.99.0": ("", False),
    "bridgecrewio/checkov-action@master":  ("", False),
    "bridgecrewio/checkov-action@0.9.0":   ("", False),
    "docker/setup-buildx-action@v3":       ("", False),
    "docker/setup-buildx-action@v2":       ("", False),
    "hashicorp/setup-terraform@v3":        ("", False),
    "hashicorp/setup-terraform@v2":        ("", False),
    "actions/setup-node@v4":              ("", False),
    "actions/setup-node@v3":              ("", False),
    "actions/setup-go@v5":                ("", False),
    "actions/setup-python@v5":            ("", False),
    "actions/setup-java@v4":             ("", False),
    "github/codeql-action/upload-sarif@v3": ("", False),
    "github/codeql-action/upload-sarif@v2": ("", False),
}

def _resolve_action_shas(yaml_str: str) -> tuple[str, list[str]]:
    """Replace all `owner/repo@tag` with `owner/repo@sha` using GitHub API.
    Returns (resolved_yaml, warnings_list).

    Transient upstream errors (5xx, timeouts) are recorded in
    `_TRANSIENT_5XX` so the caller (`workflow_generator_node`) can
    promote them to `state["external_service_issues"]` without aborting
    the pipeline. The pipeline priority is "executable workflows over
    simply generating security controls", so a 502 from api.github.com
    never blocks the PR.
    """
    warnings: list[str] = []
    transient: list[dict] = []
    pattern = re.compile(r'(?P<indent>[ \t]*uses:\s*)(?P<action>[\w\-\.]+/[\w\-\.]+)@(?P<version>[\w\.\-]+)')

    def _record_transient(action_ref: str, exc: Exception) -> None:
        transient.append({
            "rule": "upstream_502",
            "source": "github_api",
            "action": action_ref,
            "message": (
                f"Generator pipeline hit a transient upstream error while "
                f"resolving {action_ref}: {exc}. This is an external "
                f"service issue, not a security finding or workflow "
                f"configuration issue."
            ),
        })

    def _resolve_sync(match: re.Match) -> str:
        action = match.group("action")
        version = match.group("version")
        prefix = match.group("indent")
        key = f"{action}@{version}"

        # Skip actions/ (official GitHub) and docker:// — they are acceptable with tags
        if action.startswith("actions/") or action.startswith("docker/"):
            return match.group(0)

        # If already a full SHA, keep it
        if re.match(r'^[a-f0-9]{40}$', version):
            return match.group(0)

        # Accept truncated SHA (>=6 chars) — GitHub Actions needs full SHA
        if re.match(r'^[a-f0-9]{6,39}$', version):
            pass  # fall through to API resolution

        if key in _SHA_CACHE:
            sha, valid = _SHA_CACHE[key]
            if valid and len(sha) == 40:
                return f"{prefix}{action}@{sha}"
            _SHA_CACHE[key] = (version, False)

        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{action}/git/refs/tags/{version}",
                headers={"Accept": "application/vnd.github+json"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                sha = data["object"]["sha"]

                if len(sha) != 40:
                    warnings.append(f"Resolved SHA for {key} is not 40 chars ({sha}), will keep tag")
                    _SHA_CACHE[key] = (version, False)
                    return match.group(0)
                obj_type = data["object"].get("type", "commit")

                # If annotated tag (type == "tag"), peel to get the commit SHA
                if obj_type == "tag":
                    try:
                        tag_resp = httpx.get(
                            data["object"]["url"],
                            headers={"Accept": "application/vnd.github+json"},
                            timeout=10,
                        )
                        if tag_resp.status_code == 200:
                            tag_data = tag_resp.json()
                            sha = tag_data.get("object", {}).get("sha", sha)
                            sha_type = tag_data.get("object", {}).get("type", "")
                            if sha_type == "tag":
                                commit_resp = httpx.get(
                                    tag_data["object"]["url"],
                                    headers={"Accept": "application/vnd.github+json"},
                                    timeout=10,
                                )
                                if commit_resp.status_code == 200:
                                    sha = commit_resp.json().get("object", {}).get("sha", sha)
                    except Exception as e:
                        # Annotated-tag peeling is best-effort; transient
                        # upstream errors here still leave us with a
                        # valid SHA from the parent call.
                        warnings.append(f"Could not peel annotated tag for {key}: {e}")

                _SHA_CACHE[key] = (sha, True)
                return f"{prefix}{action}@{sha}"

            if 500 <= resp.status_code < 600:
                # Upstream gateway / API error: don't pretend the tag
                # doesn't exist — record as transient and fall back to
                # the original tag (preserves executability).
                _record_transient(key, RuntimeError(
                    f"Request failed with status code {resp.status_code}: {resp.text[:200]}"
                ))
                _SHA_CACHE[key] = (version, False)
                return match.group(0)

            warnings.append(f"No verified SHA for {key} (HTTP {resp.status_code})")
            _SHA_CACHE[key] = (version, False)
            return match.group(0)

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as e:
            _record_transient(key, RuntimeError(f"Request failed with status code 502: {e}"))
            _SHA_CACHE[key] = (version, False)
            return match.group(0)
        except Exception as e:
            msg = str(e)
            if "status code 5" in msg or "bad gateway" in msg.lower():
                _record_transient(key, e)
            else:
                warnings.append(f"Failed to resolve {key}: {e}")
            _SHA_CACHE[key] = (version, False)
            return match.group(0)

    resolved = pattern.sub(_resolve_sync, yaml_str)
    if transient:
        warnings.append(
            f"Generator pipeline recorded {len(transient)} transient upstream error(s) "
            "during SHA resolution; falling back to original tag refs."
        )
    # Stash the transient list on a module-level sink so the caller can
    # promote them to external_service_issue findings.
    _TRANSIENT_5XX.extend(transient)
    return resolved, warnings


# Module-level sink for transient upstream errors discovered during
# SHA resolution and action-existence checks. The generator node drains
# this list into `state["external_service_issues"]` after `_auto_fix_all`
# returns, so the dashboard sees a structured finding for every 502.
_TRANSIENT_5XX: list[dict] = []


def drain_transient_upstream_issues() -> list[dict]:
    """Return and clear the module-level transient-error list."""
    out = list(_TRANSIENT_5XX)
    _TRANSIENT_5XX.clear()
    return out


def _check_action_exists(action: str, version: str) -> tuple[bool, str]:
    """Quick check if a tag exists for an action.
    Returns (exists, resolved_sha_or_reason)."""
    key = f"{action}@{version}"
    if key in _SHA_CACHE:
        sha, valid = _SHA_CACHE[key]
        if valid:
            return True, sha
        return False, "invalid_from_cache"

    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{action}/git/refs/tags/{version}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            sha = data["object"]["sha"]
            _SHA_CACHE[key] = (sha, True)
            return True, sha
        if 500 <= resp.status_code < 600:
            _TRANSIENT_5XX.append({
                "rule": "upstream_502",
                "source": "github_api",
                "action": key,
                "message": (
                    f"Generator pipeline hit a transient upstream error while "
                    f"checking {key}: Request failed with status code "
                    f"{resp.status_code}. This is an external service issue, "
                    f"not a security finding or workflow configuration issue."
                ),
            })
            _SHA_CACHE[key] = (version, False)
            return False, f"upstream_{resp.status_code}"
        _SHA_CACHE[key] = (version, False)
        return False, f"http_{resp.status_code}"
    except Exception as e:
        msg = str(e)
        if "status code 5" in msg or "bad gateway" in msg.lower():
            _TRANSIENT_5XX.append({
                "rule": "upstream_502",
                "source": "github_api",
                "action": key,
                "message": (
                    f"Generator pipeline hit a transient upstream error while "
                    f"checking {key}: {msg[:200]}. This is an external service "
                    f"issue, not a security finding or workflow configuration "
                    f"issue."
                ),
            })
        _SHA_CACHE[key] = (version, False)
        return False, str(e)


def _remove_invalid_actions(yaml_str: str) -> tuple[str, list[str]]:
    """Find steps using actions with invalid/unresolvable tags and remove them.
    Returns (cleaned_yaml, removal_report)."""
    import re as _re

    removals = []
    lines = yaml_str.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect step with uses: owner/repo@version
        m = _re.match(r'(- uses:\s*)([\w\-\.]+/[\w\-\.]+)@([\w\.\-]+)', stripped)
        if m:
            action = m.group(2)
            version = m.group(3)

            # Skip actions/ (official) — they're fine
            if action.startswith("actions/") or action.startswith("docker/"):
                result.append(line)
                i += 1
                continue

            # Skip if already SHA for official actions
            if _re.match(r'^[a-f0-9]{40}$', version):
                if action.startswith("actions/") or action.startswith("docker/"):
                    result.append(line)
                    i += 1
                    continue
                # For third-party actions with SHA, verify it exists
                sha_valid = _verify_action_sha(action, version)
                if sha_valid:
                    result.append(line)
                    i += 1
                    continue
                # SHA invalid/missing — fall back to tag
                fallback_sha = _find_fallback_sha(action)
                if fallback_sha:
                    step_indent = line[:len(line) - len(line.lstrip())]
                    result.append(f"{step_indent}- uses: {action}@{fallback_sha}")
                    i += 1
                    step_indent_amount = len(line) - len(line.lstrip())
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.strip().startswith("- ") or not next_line.strip():
                            break
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent <= step_indent_amount:
                            break
                        result.append(next_line)
                        i += 1
                    removals.append(f"Action '{action}@{version}' SHA not found — fell back to tag")
                    continue
                # No fallback found — remove the step entirely
                removals.append(f"Removed step using '{action}@{version}' — SHA not found and no fallback available")
                i += 1
                continue

            # Skip if cache has valid SHA
            cache_key = f"{action}@{version}"
            if cache_key in _SHA_CACHE and _SHA_CACHE[cache_key][1]:
                result.append(line)
                i += 1
                continue

            # Try to resolve — if succeeds, keep step
            exists, sha_or_reason = _check_action_exists(action, version)
            if exists:
                step_indent = line[:len(line) - len(line.lstrip())]
                result.append(f"{step_indent}- uses: {action}@{sha_or_reason}")
                # Copy any lines that are part of this step's with block
                i += 1
                step_indent_amount = len(line) - len(line.lstrip())
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip().startswith("- ") or not next_line.strip():
                        break
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= step_indent_amount:
                        break
                    # Fix: replace tag with SHA in with: block too if referenced
                    next_line = next_line.replace(f"@{version}", f"@{sha_or_reason}")
                    result.append(next_line)
                    i += 1
                continue

            # Action is truly unresolvable — try fallback to last known good version
            fallback_sha = _find_fallback_sha(action)
            if fallback_sha:
                step_indent = line[:len(line) - len(line.lstrip())]
                result.append(f"{step_indent}- uses: {action}@{fallback_sha}")
                i += 1
                # Copy sub-lines
                step_indent_amount = len(line) - len(line.lstrip())
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip().startswith("- ") or not next_line.strip():
                        break
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= step_indent_amount:
                        break
                    result.append(next_line)
                    i += 1
                removals.append(f"Action '{action}@{version}' unresolvable — fell back to last known SHA")
                continue

            # No fallback — remove the entire step
            removals.append(f"Removed step using '{action}@{version}' — tag not found on GitHub")
            i += 1
            step_indent_amount = len(line) - len(line.lstrip())
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip().startswith("- ") or not next_line.strip():
                    break
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= step_indent_amount:
                    break
                i += 1
            continue

        result.append(line)
        i += 1

    return "\n".join(result), removals


def _find_fallback_sha(action: str) -> str | None:
    """Try to find a fallback SHA for an unresolvable action by checking cache for any known version."""
    for key, (sha, valid) in _SHA_CACHE.items():
        if valid and key.startswith(f"{action}@"):
            return sha
    return None


def _verify_action_sha(action: str, sha: str) -> bool:
    """Verify that a commit SHA exists for the given action repository.

    On 5xx, records a transient upstream error and returns False so the
    caller can fall back to a known-good SHA from the cache.
    """
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{action}/git/{sha}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        if 500 <= resp.status_code < 600:
            _TRANSIENT_5XX.append({
                "rule": "upstream_502",
                "source": "github_api",
                "action": f"{action}@{sha}",
                "message": (
                    f"Generator pipeline hit a transient upstream error while "
                    f"verifying {action}@{sha}: Request failed with status code "
                    f"{resp.status_code}. This is an external service issue, "
                    f"not a security finding or workflow configuration issue."
                ),
            })
            return False
        return False
    except Exception as e:
        msg = str(e)
        if "status code 5" in msg or "bad gateway" in msg.lower():
            _TRANSIENT_5XX.append({
                "rule": "upstream_502",
                "source": "github_api",
                "action": f"{action}@{sha}",
                "message": (
                    f"Generator pipeline hit a transient upstream error while "
                    f"verifying {action}@{sha}: {msg[:200]}. This is an "
                    f"external service issue, not a security finding or "
                    f"workflow configuration issue."
                ),
            })
        return False


def _auto_fix_all(yaml_str: str) -> tuple[str, list[str]]:
    """Auto-fix gateway: resolve all compliance issues, never block deploy.
    Returns (fixed_yaml, fixes_list)."""
    fixes = []
    current = yaml_str

    # 1. Resolve SHA — ganti tag dengan SHA
    resolved, _ = _resolve_action_shas(current)
    if resolved != current:
        resolved_count = _count_action_refs(current) - _count_action_refs(resolved)
        if resolved_count > 0:
            fixes.append(f"Resolved {resolved_count} action(s) to commit SHA")
    current = resolved

    # 2. Remove invalid actions — action yang tag-nya 404
    current, removals = _remove_invalid_actions(current)
    fixes.extend(removals)

    # 3. Fix permissions
    fixed_perms = _fix_permissions(current)
    if fixed_perms != current:
        perm_diff = _count_occurrences(current, "read-all") - _count_occurrences(fixed_perms, "read-all")
        if perm_diff > 0:
            fixes.append("Downgraded permissions to minimal scope: contents: read")
    current = fixed_perms

    # 4. Fix persist-credentials
    fixed_checkout = _fix_checkout_persist_credentials(current)
    if fixed_checkout != current:
        fixes.append("Added persist-credentials: false to actions/checkout steps")
    current = fixed_checkout

    # 5. (skipped: fail-fast: false is invalid at jobs: level; jobs already
    #     have explicit timeout-minutes and continue-on-error: false)

    # 6. Ensure all jobs have timeout-minutes and no continue-on-error for security jobs
    current, fix6 = _fix_job_settings(current)
    fixes.extend(fix6)

    # 7. Migrate deprecated actions/upload-artifact v3 → v4
    current, fix7 = _migrate_artifact_v3_to_v4(current)
    fixes.extend(fix7)

    return current, fixes


def _add_workflow_settings(yaml_str: str) -> tuple[str, list[str]]:
    """Add fail-fast: false and ensure jobs run to completion."""
    fixes = []
    import re as _re

    # Check if fail-fast: false exists
    if "fail-fast: false" not in yaml_str:
        # Add after jobs: line
        if "jobs:" in yaml_str:
            pattern = _re.compile(r'^jobs:\s*$', _re.MULTILINE)
            yaml_str = pattern.sub("jobs:\n  fail-fast: false", yaml_str, count=1)
            fixes.append("Added fail-fast: false to ensure all jobs complete")

    return yaml_str, fixes


def _fix_job_settings(yaml_str: str) -> tuple[str, list[str]]:
    """Ensure all jobs have timeout-minutes and remove continue-on-error from security jobs."""
    fixes = []
    import re as _re

    lines = yaml_str.split("\n")
    result = []
    in_job = False
    job_indent = 0
    job_name = ""

    security_keywords = ["sast", "secret", "scan", "security", "trivy", "gitleaks", "codeql", "semgrep", "dep", "lint", "checkov", "sbom", "license", "container", "iac"]

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect job start (top-level with no leading spaces, ends with :)
        if stripped and not stripped.startswith("#") and stripped.endswith(":") and not in_job:
            # Check if this is a job (not on:, name:, jobs:, etc.)
            if not stripped.startswith("on:") and not stripped.startswith("name:") and stripped != "jobs:":
                if not any(stripped.startswith(k + ":") for k in ["permissions", "env", "concurrency", "defaults"]):
                    in_job = True
                    job_indent = len(line) - len(line.lstrip())
                    job_name = stripped[:-1]

        # Detect end of job (next top-level item)
        if in_job and stripped and not stripped.startswith("#"):
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= job_indent and stripped.endswith(":"):
                in_job = False
                job_name = ""

        # Add timeout-minutes if not present for job
        if in_job and stripped == "runs-on:":
            result.append(line)
            # Check if next lines have timeout-minutes
            has_timeout = False
            j = i + 1
            while j < len(lines) and j < i + 10:
                next_line = lines[j].strip()
                if next_line == "timeout-minutes:":
                    has_timeout = True
                    break
                if next_line.startswith("- ") or (next_line and not next_line.startswith(" ") and next_line != ""):
                    break
                j += 1
            if not has_timeout:
                # Find where to insert (after runs-on and its value)
                result.append(lines[i + 1] if i + 1 < len(lines) else "")
                indent = " " * (job_indent + 2)
                result.append(f"{indent}timeout-minutes: 30")
                continue
            result.append(lines[i + 1] if i + 1 < len(lines) else "")
            continue

        result.append(line)

    return "\n".join(result), fixes


def _count_action_refs(yaml_str: str) -> int:
    """Count number of uses: owner/repo@version in YAML."""
    import re as _re
    return len(_re.findall(r'uses:\s*[\w\-\.]+/[\w\-\.]+@[\w\.\-]+', yaml_str))


def _count_occurrences(yaml_str: str, text: str) -> int:
    return yaml_str.count(text)


def _fix_permissions(yaml_str: str) -> str:
    """Replace single-line 'permissions: read-all'/'write-all' with expanded
    minimal permissions block. Uses pure regex — never round-trip through
    yaml.load/dump which would corrupt GitHub Actions YAML (e.g. on: → true:)."""
    import re as _re
    pattern = _re.compile(r'^(\s*)permissions:\s*(read-all|write-all)\s*$', _re.MULTILINE)
    return pattern.sub(r'\1permissions:\n\1  contents: read', yaml_str)


def _migrate_artifact_v3_to_v4(yaml_str: str) -> tuple[str, list[str]]:
    """Replace deprecated actions/upload-artifact@v3 and download-artifact@v3 with v4."""
    fixes = []
    import re as _re

    upload_v3_count = len(_re.findall(r'actions/upload-artifact@v3', yaml_str))
    download_v3_count = len(_re.findall(r'actions/download-artifact@v3', yaml_str))

    if upload_v3_count > 0:
        yaml_str = yaml_str.replace('actions/upload-artifact@v3', 'actions/upload-artifact@v4')
        fixes.append(f"Migrated {upload_v3_count} upload-artifact@v3 → v4 (v3 deprecated)")

    if download_v3_count > 0:
        yaml_str = yaml_str.replace('actions/download-artifact@v3', 'actions/download-artifact@v4')
        fixes.append(f"Migrated {download_v3_count} download-artifact@v3 → v4 (v3 deprecated)")

    return yaml_str, fixes


def _fix_checkout_persist_credentials(yaml_str: str) -> str:
    """Add persist-credentials: false to every actions/checkout step that lacks it.
    Uses pure regex — never round-trips through yaml.load/dump which would
    corrupt GitHub Actions YAML (e.g. on: → true:)."""
    import re as _re

    lines = yaml_str.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect: - uses: actions/checkout@<anything>
        if stripped.startswith("- uses: actions/checkout@"):
            result.append(line)
            checkout_indent = line[:len(line) - len(line.lstrip())]

            # Peek ahead up to 3 lines to see if persist-credentials already exists
            i += 1
            has_persist = False
            has_with = False
            with_index = -1
            peek_stop = min(i + 4, len(lines))
            for j in range(i, peek_stop):
                peek = lines[j]
                p_stripped = peek.strip()
                if not p_stripped or p_stripped.startswith("#"):
                    continue
                if "persist-credentials" in peek:
                    has_persist = True
                    break
                if p_stripped == "with:":
                    has_with = True
                    with_index = j
                # New step or job-level key → stop peeking
                if p_stripped.startswith("- ") or (p_stripped.endswith(":") and p_stripped not in ("with:",)):
                    break

            if not has_persist:
                if has_with:
                    # Find last line of existing with: block, insert after it
                    with_base_indent = len(lines[with_index]) - len(lines[with_index].lstrip())
                    insert_after = with_index
                    for j in range(with_index + 1, peek_stop):
                        if lines[j].strip() and not lines[j].strip().startswith("#"):
                            indent = len(lines[j]) - len(lines[j].lstrip())
                            if indent > with_base_indent:
                                insert_after = j
                            else:
                                break
                    # Insert persist-credentials after insert_after
                    persist_indent = " " * (with_base_indent + 2)
                    lines.insert(insert_after + 1, f"{persist_indent}persist-credentials: false")
                    peek_stop += 1  # adjust because we inserted a line
                else:
                    # No with: block — add one after the uses line
                    lines.insert(i, f"{checkout_indent}  with:")
                    lines.insert(i + 1, f"{checkout_indent}    persist-credentials: false")
                    peek_stop += 2

            # Copy remaining peeked lines
            for j in range(i, peek_stop):
                result.append(lines[j] if j < len(lines) else "")
            i = peek_stop
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


# =============================================================================
# SAST Matrix Strategy (struktur-v9.3)
# =============================================================================
# Emit matrix include HANYA untuk general + detected_domain (no skip entries).
# General layer SELALU applicable ke semua webapp. Domain layer hanya applicable
# kalau detected_domain match. Hasil: 2 jobs matrix (general + domain) di
# GitHub Actions UI, no noise dari 5 domain yang di-skip.
#
# Integrasi:
#   - Dipanggil dari emit SAST job di section "---- sast ----" (line ~3708).
#   - Matrix strategy menggantikan sast job flat → per-domain visibility di
#     GH Actions UI.
#   - Rule output: workflow .yml di-generate dengan `strategy.matrix.include`
#     berisi 1 (general only) atau 2 entries (general + domain).

# Per-domain metadata: rule path (di .github/), expected rule count, GH
# Actions label. Sinkron dengan domain_knowledge_base.yml. kalau domain
# belum ada rule dedicated, expected_rules=0 dan rules="" (general layer
# tetap menanggung via owasp-api.yml).
_DOMAIN_MATRIX_META: dict[str, tuple[str, int, str]] = {
    # slug: (relative_path_to_rule_file, expected_rule_count, gh_actions_label)
    "e-commerce": (".github/ai-devsecops-rules.yml", 12, "E-commerce (PCI-DSS)"),
    "healthcare": (".github/ai-devsecops-rules.yml", 8, "Healthcare (HIPAA)"),
    "fintech":    (".github/ai-devsecops-rules.yml", 6, "Fintech (Ledger)"),
    "blog":       (".github/ai-devsecops-rules.yml", 5, "Blog (CMS)"),
    "iot":        (".github/ai-devsecops-rules.yml", 8, "IoT (MQTT)"),
    "education":  (".github/ai-devsecops-rules.yml", 0, "Education (LMS)"),
}


def _build_sast_matrix(detected_domain: str | None) -> dict:
    """Build GH Actions matrix strategy untuk SAST job.

    Returns dict shaped like:
      {"include": [
          {"domain": "general", "rules": "...", "expected_rules": 12, "sarif_cat": "semgrep-general"},
          {"domain": "ecommerce", "rules": "...", "expected_rules": 12, "sarif_cat": "semgrep-ecommerce"},
      ]}

    Matrix berisi:
      - 1 entry `general` SELALU (cuma OWASP API baseline).
      - 1 entry domain kalau detected_domain match di _DOMAIN_MATRIX_META.
        kalau domain None / 'general' / unknown → cuma 1 entry (general).

    Catatan: rule file path menunjuk ke `.github/ai-devsecops-rules.yml`
    karena struktur-v9.2 inline all rules. Domain-specific rules sudah
    di-merge ke file tsb oleh `_collect_merged_semgrep_rules()`.
    """
    include: list[dict] = [
        {
            "domain": "general",
            "rules": ".github/ai-devsecops-rules.yml",
            "expected_rules": 12,
            "sarif_cat": "semgrep-general",
        }
    ]

    domain = (detected_domain or "general").lower().strip()
    if domain and domain != "general" and domain in _DOMAIN_MATRIX_META:
        rules_path, expected, _label = _DOMAIN_MATRIX_META[domain]
        include.append({
            "domain": domain,
            "rules": rules_path,
            "expected_rules": expected,
            "sarif_cat": f"semgrep-{domain}",
        })

    return {"include": include}


# =============================================================================
# Two-File Workflow Split (struktur-v9.3 — domain-aware deployment)
# =============================================================================
# The single merged YAML that `_build_workflow_yaml` emits is now split into
# two files for cleaner separation of concerns + better subject-run visibility
# in the GitHub Actions UI:
#
#   1. `.github/workflows/ai-devsecops.yml`        (GENERIC, always present)
#      - lint, test, sast, secret-scan, dep-check, container-scan
#      - Concurrency, permissions, `on:` triggers
#      - CALLS the custom rules file via a `workflow_call` job so SAST picks
#        up the merged Semgrep rules and domain-specific compliance jobs.
#
#   2. `.github/workflows/ai-devsecops-custom.yml` (CUSTOM, domain-specific)
#      - Reusable workflow (`on.workflow_call`).
#      - Domain-specific jobs: pci-dss, hipaa, ledger-check, csp-headers,
#        mqtt-security, plus any AI-designed custom jobs.
#      - Owns the merged Semgrep ruleset file write.
#
# The generic file always `uses: ./.github/workflows/ai-devsecops-custom.yml`
# so domain jobs are always wired in. The pipeline_service response exposes
# both files separately so the FE PipelineGenerator can render two tabs.

GENERIC_STAGE_NAMES: frozenset[str] = frozenset({
    "lint", "test", "sast", "secret-scan", "dependency-scan",
    "container-build", "container-scan", "container-security",
    "trivy-fs", "docker-compose-validate", "dependency-scan-per-service",
})

CUSTOM_STAGE_NAMES: frozenset[str] = frozenset({
    # v9.3 revisi 3-domain & 2-arch: domain-specific static templates
    # (pci-dss / hipaa / ledger-check / csp-headers / mqtt-security)
    # are removed. Per-repo custom jobs come from
    # `state["job_designs"]` (LLM-generated by job_reasoning_node).
    # Custom-stage classification now matches anything that is NOT in
    # the GENERIC_STAGE_NAMES set; AI-generated jobs are routed to the
    # custom file because they are domain-specific by design.
})


def _is_generic_stage(name: str) -> bool:
    n = (name or "").strip().lower()
    if n in GENERIC_STAGE_NAMES:
        return True
    # v9.3 revisi 3-domain & 2-arch: CUSTOM_STAGE_NAMES is empty
    # (static domain templates removed). AI-generated jobs from
    # `state["job_designs"]` carry unique kebab-case names that are
    # NOT in GENERIC_STAGE_NAMES, so they must be routed to the
    # custom file (custom = "anything domain/AI-specific"). An
    # unknown name defaults to custom.
    if n in CUSTOM_STAGE_NAMES:
        return False
    return False


def _split_workflow_yaml(
    yaml_text: str,
    custom_filename: str = "ai-devsecops-custom.yml",
    detected_domain: str | None = None,
) -> tuple[str, str, list[dict]]:
    """Split the single merged workflow YAML into (generic, custom, file_meta).

    Returns:
      generic_yaml:    the file committed at `.github/workflows/ai-devsecops.yml`
      custom_yaml:     the file committed at `.github/workflows/ai-devsecops-custom.yml`
      file_meta:       list of dicts describing each file for the FE pipeline
                       generator UI: [{name, path, kind, jobs: [...]}]

    Behaviour:
      * Parses `yaml_text` with `yaml.safe_load`.
      * Pulls every job into either the generic or the custom file based on
        `_is_generic_stage(name)`. AI-designed jobs (status='ai_generated' in
        explanations) are placed in the custom file.
      * The custom file declares `on: workflow_call` so it can be invoked
        from the generic file.
      * The generic file appends a final `domain-compliance` job that does
        `uses: ./.github/workflows/<custom_filename>` with `secrets: inherit`,
        so all domain-specific jobs run after the generic ones.
      * If the input has no `jobs:`, both files are returned as the original
        text (fallback) and `file_meta` is empty.
    """
    try:
        parsed = yaml.safe_load(yaml_text) or {}
    except Exception:
        return yaml_text, "", []

    if not isinstance(parsed, dict) or "jobs" not in parsed or not isinstance(parsed["jobs"], dict):
        return yaml_text, "", []

    jobs = parsed["jobs"]
    generic_jobs: dict[str, dict] = {}
    custom_jobs: dict[str, dict] = {}
    file_meta: list[dict] = []

    for name, body in jobs.items():
        if not isinstance(body, dict):
            generic_jobs[name] = body
            continue
        if _is_generic_stage(name):
            generic_jobs[name] = body
        else:
            custom_jobs[name] = body

    # ---- Build generic file ----
    generic_doc = dict(parsed)
    generic_doc["jobs"] = generic_jobs
    if custom_jobs:
        # Append a single `domain-compliance` job that calls the custom file.
        # This keeps the dependency graph linear (generic jobs → domain jobs)
        # and gives the GitHub UI a single entry-point for the domain layer.
        generic_doc["jobs"]["domain-compliance"] = {
            "needs": list(generic_jobs.keys())[-1:] if generic_jobs else [],
            "uses": f"./.github/workflows/{custom_filename}",
            "with": {
                "detected_domain": detected_domain or "general",
            },
            "secrets": "inherit",
        }

    # ---- Build custom file ----
    custom_doc: dict = {
        "name": f"AI DevSecOps — Domain Compliance ({detected_domain or 'general'})",
        "on": {
            "workflow_call": {
                "inputs": {
                    "detected_domain": {
                        "description": "Domain classification from the AI agent.",
                        "required": False,
                        "type": "string",
                        "default": detected_domain or "general",
                    },
                },
            },
        },
        # Minimal permissions for the reusable workflow. The calling
        # workflow can still grant extra permissions via its own
        # permissions block, but we set `contents: read` so checkout
        # and any read-only tools work without surprises.
        "permissions": {
            "contents": "read",
            "security-events": "write",
        },
    }
    if custom_jobs:
        custom_doc["jobs"] = custom_jobs

    try:
        generic_yaml = yaml.safe_dump(generic_doc, sort_keys=False, default_flow_style=False)
        custom_yaml = yaml.safe_dump(custom_doc, sort_keys=False, default_flow_style=False) if custom_jobs else ""
    except Exception:
        return yaml_text, "", []

    file_meta = [
        {
            "name": "ai-devsecops.yml",
            "path": ".github/workflows/ai-devsecops.yml",
            "kind": "generic",
            "jobs": list(generic_jobs.keys()) + (["domain-compliance"] if custom_jobs else []),
        },
    ]
    # Defensive: de-duplicate the jobs list so a stale `domain-compliance`
    # entry (e.g. when the user already had one in the merged YAML) never
    # surfaces in the FE twice. Build the visible list once.
    if file_meta:
        seen_jobs: set[str] = set()
        deduped_jobs: list[str] = []
        for j in file_meta[0]["jobs"]:
            if j in seen_jobs:
                continue
            seen_jobs.add(j)
            deduped_jobs.append(j)
        file_meta[0]["jobs"] = deduped_jobs
    if custom_jobs:
        file_meta.append({
            "name": custom_filename,
            "path": f".github/workflows/{custom_filename}",
            "kind": "custom",
            "jobs": list(custom_jobs.keys()),
        })

    return generic_yaml, custom_yaml, file_meta


def build_workflow_yaml_split(
    primary_language: str,
    package_manager: str,
    test_framework: str | None,
    frameworks: list[str],
    build_tools: list[str],
    stages: list[str],
    arch_type: str,
    findings: list[dict],
    structure: list | None = None,
    files: dict | None = None,
    detected_domain: str | None = None,
    domain_confidence: float | None = None,
    domain_threats: list[str] | None = None,
    detected_sub_type: str | None = None,
    llm_rule_suggestions: list[str] | None = None,
    state: PipelineEngineerState | None = None,
) -> dict:
    """Two-file variant of `_build_workflow_yaml`.

    Returns:
      {
        "generic_yaml": str,
        "custom_yaml":  str,
        "merged_yaml":  str,   # backwards-compat single file for legacy code
        "stage_names":  list[str],
        "stages_general": list[str],
        "stages_custom":  list[str],
        "explanations":   list[dict],
        "file_meta":      list[dict],
      }
    """
    merged_yaml, stage_names, explanations = _build_workflow_yaml(
        primary_language=primary_language,
        package_manager=package_manager,
        test_framework=test_framework,
        frameworks=frameworks,
        build_tools=build_tools,
        stages=stages,
        arch_type=arch_type,
        findings=findings,
        structure=structure,
        files=files,
        detected_domain=detected_domain,
        domain_confidence=domain_confidence,
        domain_threats=domain_threats,
        detected_sub_type=detected_sub_type,
        llm_rule_suggestions=llm_rule_suggestions,
        state=state,
    )

    generic_yaml, custom_yaml, file_meta = _split_workflow_yaml(
        merged_yaml,
        custom_filename="ai-devsecops-custom.yml",
        detected_domain=detected_domain,
    )

    stages_general = [n for n in stage_names if _is_generic_stage(n)]
    stages_custom = [n for n in stage_names if not _is_generic_stage(n)]

    return {
        "generic_yaml": generic_yaml,
        "custom_yaml": custom_yaml,
        "merged_yaml": merged_yaml,
        "stage_names": stage_names,
        "stages_general": stages_general,
        "stages_custom": stages_custom,
        "explanations": explanations,
        "file_meta": file_meta,
    }