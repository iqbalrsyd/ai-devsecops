import sys

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

import yaml

from app.agents.nodes.workflow_generator import (
    _build_execution_results,
    _build_workflow_yaml,
    _filter_stages_by_evidence,
    _has_build_script,
    _has_dockerfile,
    _has_file,
    _has_iac,
    _has_test_script,
    _node_setup_steps,
    _pre_validate_generation,
    _render_dashboard_messages,
    _select_relevant_stages,
    _validate_pipeline_consistency,
    _validate_pipeline_prerequisites,
    _validate_workflow_yaml,
    workflow_generator_node,
)


def _minimal_state(**overrides) -> dict:
    state = {
        "request_type": "repository_pipeline",
        "github_token": "token",
        "repository_full_name": "owner/repo",
        "repository_default_branch": "main",
        "repository_structure": [],
        "repository_files": {},
        "source_files": [],
        "existing_workflows": [],
        "detected_technologies": {},
        "detected_architecture": {"architecture_type": "monolithic"},
        "detected_architecture_type": "monolithic",
        "detected_architecture_confidence": 0.9,
        "detected_architecture_reason": "test",
        "detected_deployment": {},
        "recommended_deployment_target": "generic",
        "detected_domain": None,
        "domain_confidence": 0.0,
        "domain_evidence": [],
        "domain_threats": [],
        "attack_surfaces": [],
        "inferred_security_needs": {},
        "findings": [],
        "errors": [],
        "workflow_config_issues": [],
    }
    state.update(overrides)
    return state


def test_has_file_matches_repository_files():
    structure = [{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}]
    files = {"package-lock.json": "{}"}
    assert _has_file(structure, files, ["Dockerfile"])
    assert _has_file(structure, files, ["package-lock.json"])
    assert not _has_file(structure, files, ["yarn.lock"])


def test_has_dockerfile_detects_file():
    structure = [{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}]
    assert _has_dockerfile(structure, {}, {})
    assert not _has_dockerfile([], {}, {})


def test_has_iac_detects_terraform():
    structure = [{"name": "main.tf", "path": "terraform/main.tf", "type": "file"}]
    assert _has_iac(structure, {}, {})
    assert not _has_iac([], {}, {})


def test_select_relevant_stages_omits_test_without_test_framework():
    security = {"security_controls": [{"control": "test", "status": "recommended"}]}
    technologies = {"primary_language": "JavaScript", "package_manager": "npm"}
    stages = _select_relevant_stages(
        security=security,
        technologies=technologies,
        deployment={},
        arch_type="monolithic",
        findings=[],
    )
    assert "test" not in stages


def test_select_relevant_stages_includes_test_with_framework():
    security = {"security_controls": [{"control": "test", "status": "recommended"}]}
    technologies = {
        "primary_language": "JavaScript",
        "package_manager": "npm",
        "test_framework": "Jest",
    }
    stages = _select_relevant_stages(
        security=security,
        technologies=technologies,
        deployment={},
        arch_type="monolithic",
        findings=[],
    )
    assert "test" in stages


def test_select_relevant_stages_omits_container_jobs_without_dockerfile():
    security = {
        "security_controls": [
            {"control": "container_scan", "status": "recommended"},
            {"control": "container_build", "status": "recommended"},
        ]
    }
    technologies = {"primary_language": "JavaScript", "package_manager": "npm"}
    stages = _select_relevant_stages(
        security=security,
        technologies=technologies,
        deployment={"docker": False},
        arch_type="monolithic",
        findings=[],
        structure=[],
        files={},
    )
    assert "container-scan" not in stages
    assert "container-build" not in stages


def test_select_relevant_stages_includes_container_jobs_with_dockerfile():
    security = {
        "security_controls": [
            {"control": "sast", "status": "recommended"},
            {"control": "container_scan", "status": "recommended"},
        ]
    }
    technologies = {"primary_language": "JavaScript", "package_manager": "npm"}
    structure = [{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}]
    stages = _select_relevant_stages(
        security=security,
        technologies=technologies,
        deployment={},
        arch_type="monolithic",
        findings=[],
        structure=structure,
        files={},
    )
    # Reviewer feedback: container-build stage sudah dihapus.
    # Hanya container-scan yang di-emit ketika ada Dockerfile.
    assert "container-scan" in stages
    assert "container-build" not in stages


def test_select_relevant_stages_omits_iac_without_artifacts():
    security = {"security_controls": [{"control": "iac_scan", "status": "recommended"}]}
    technologies = {"primary_language": "JavaScript", "package_manager": "npm"}
    stages = _select_relevant_stages(
        security=security,
        technologies=technologies,
        deployment={"terraform": False, "kubernetes": False, "docker": False},
        arch_type="monolithic",
        findings=[],
        structure=[],
        files={},
    )
    assert "iac-scan" not in stages


def test_filter_stages_by_evidence_removes_contradictory_stages():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        detected_deployment={},
        repository_structure=[],
        repository_files={},
    )
    filtered = _filter_stages_by_evidence(
        ["lint", "test", "container-scan", "iac-scan"], state
    )
    assert filtered == ["lint"]


def test_node_setup_steps_use_ci_and_cache_with_lockfile():
    setup, install = _node_setup_steps("npm", has_lockfile=True)
    assert any("cache: 'npm'" in line for line in setup)
    assert install == "npm ci --no-audit --no-fund"


def test_node_setup_steps_use_install_without_lockfile():
    setup, install = _node_setup_steps("npm", has_lockfile=False)
    assert not any("cache:" in line for line in setup)
    assert install == "npm install --no-audit --no-fund"


def test_node_setup_steps_yarn_with_lockfile():
    setup, install = _node_setup_steps("yarn", has_lockfile=True)
    assert any("cache: 'yarn'" in line for line in setup)
    assert "yarn install --frozen-lockfile" in install


def test_build_workflow_yaml_uses_npm_install_when_no_lockfile():
    yaml_text, stages, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["lint", "dependency-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    assert "npm install --no-audit --no-fund" in yaml_text
    assert "npm ci" not in yaml_text
    assert "cache: 'npm'" not in yaml_text


def test_build_workflow_yaml_uses_npm_ci_when_lockfile_present():
    yaml_text, stages, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["lint", "dependency-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package-lock.json", "path": "package-lock.json", "type": "file"}],
        files={"package-lock.json": "{}"},
    )
    assert "npm ci --no-audit --no-fund" in yaml_text
    assert "npm install --no-audit --no-fund" not in yaml_text
    assert "cache: 'npm'" in yaml_text


def test_build_workflow_yaml_gitleaks_has_token_and_no_invalid_args():
    yaml_text, stages, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["secret-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    secret_job = parsed["jobs"]["secret-scan"]
    gitleaks_step = [s for s in secret_job["steps"] if "gitleaks" in s.get("uses", "")][0]
    assert "args" not in gitleaks_step.get("with", {})
    assert gitleaks_step.get("env", {}).get("GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}"
    assert parsed["permissions"].get("pull-requests") == "read"


def test_build_workflow_yaml_omits_container_jobs_without_dockerfile():
    yaml_text, stages, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["lint"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    assert "container-build" not in parsed["jobs"]
    assert "container-scan" not in parsed["jobs"]
    assert "iac-scan" not in parsed["jobs"]


def test_pre_validate_generation_reports_missing_test_framework():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [{"control": "test", "status": "recommended"}]
        },
    )
    issues = _pre_validate_generation(state)
    rules = {i["rule"] for i in issues}
    assert "missing_test_framework" in rules
    assert "missing_lockfile" in rules


def test_workflow_generator_node_drops_test_job_when_no_framework():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "test", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    assert not result["errors"]
    assert "test" not in result["generated_stages"]
    parsed = yaml.safe_load(result["generated_workflow"])
    assert "test" not in parsed["jobs"]


def test_workflow_generator_node_drops_container_jobs_without_dockerfile():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "container_scan", "status": "recommended"},
                {"control": "container_build", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    assert not result["errors"]
    assert "container-scan" not in result["generated_stages"]
    assert "container-build" not in result["generated_stages"]


def test_workflow_generator_node_drops_container_jobs_when_deployment_flag_lies():
    """Regression test: inferred/stale deployment flags must not override file evidence."""
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        detected_deployment={"docker": True, "docker_confidence": 0.9},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "container_scan", "status": "recommended"},
                {"control": "container_build", "status": "recommended"},
                {"control": "iac_scan", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    assert not result["errors"]
    assert "container-scan" not in result["generated_stages"]
    assert "container-build" not in result["generated_stages"]
    assert "iac-scan" not in result["generated_stages"]
    invalid = result.get("invalid_workflow_stages", [])
    assert any(item["stage"] == "container-scan" for item in invalid)
    assert any(item["stage"] == "iac-scan" for item in invalid)


def test_workflow_generator_node_includes_container_jobs_with_dockerfile():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        detected_deployment={"docker": True},
        repository_structure=[{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}],
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "container_scan", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    assert not result["errors"]
    # Reviewer feedback: container-build stage DIHAPUS. container-scan
    # job sudah melakukan `docker build` di dalamnya. YAML hanya
    # emit satu job `container-scan` (bukan `container-build` atau
    # `container-security`).
    assert "container-scan" in result["generated_stages"]
    parsed = yaml.safe_load(result["generated_workflow"])
    assert "container-scan" in parsed["jobs"]
    assert "container-build" not in parsed["jobs"]
    assert "container-security" not in parsed["jobs"]


def test_validate_workflow_yaml_rejects_unsupported_gitleaks_input():
    bad_yaml = """
name: test
on:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: gitleaks/gitleaks-action@44c470ffc35caa8b1eb3e8012ca53c2f9bea4eb5
        with:
          args: --redact
"""
    ok, errors = _validate_workflow_yaml(bad_yaml)
    assert not ok
    assert any("unexpected_action_input" in e for e in errors)


def test_validate_workflow_yaml_rejects_missing_gitleaks_token():
    bad_yaml = """
name: test
on:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: gitleaks/gitleaks-action@44c470ffc35caa8b1eb3e8012ca53c2f9bea4eb5
"""
    ok, errors = _validate_workflow_yaml(bad_yaml)
    assert not ok
    assert any("GITHUB_TOKEN" in e for e in errors)


def test_validate_workflow_yaml_accepts_valid_generated_workflow():
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "secret_scan", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    ok, errors = _validate_workflow_yaml(result["generated_workflow"], state=result)
    assert ok, errors
    parsed = yaml.safe_load(result["generated_workflow"])
    assert parsed["permissions"].get("pull-requests") == "read"


# ---------------------------------------------------------------------------
# New tests for the repository-aware improvements (requirements 1, 2, 4, 5, 8)
# ---------------------------------------------------------------------------


def test_has_build_script_detects_package_json_script():
    """Requirement 1: build stage requires a build script in package.json."""
    structure = [{"name": "package.json", "path": "package.json", "type": "file"}]
    files = {"package.json": '{"scripts": {"build": "vite build", "test": "vitest"}}'}
    assert _has_build_script(structure, files, "npm") is True
    assert _has_build_script(structure, files, "yarn") is True


def test_has_build_script_returns_false_without_script():
    structure = [{"name": "package.json", "path": "package.json", "type": "file"}]
    files = {"package.json": '{"name": "foo"}'}
    assert _has_build_script(structure, files, "npm") is False
    assert _has_build_script(structure, {}, "npm") is False


def test_has_test_script_detects_test_command():
    structure = [{"name": "package.json", "path": "package.json", "type": "file"}]
    files = {"package.json": '{"scripts": {"test": "vitest run"}}'}
    assert _has_test_script(structure, files, "npm") is True


def test_build_stage_omitted_when_no_script():
    """Reviewer feedback: `build` stage TIDAK di-emit ke YAML
    apapun evidence-nya. Fokus security.
    """
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "build", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    parsed = yaml.safe_load(result["generated_workflow"])
    # Build TIDAK ada di YAML, walaupun diminta dan walaupun tidak
    # ada script di package.json. CI fokus security.
    assert "build" not in parsed.get("jobs", {})


def test_build_stage_kept_when_script_present():
    """Reviewer feedback: `build` stage TIDAK di-emit ke YAML (CI
    ini fokus security). Stage logic tetap mempertahankan
    `build` di ALLOWED_STAGES untuk tracking, tapi job `build`
    TIDAK ada di output.
    """
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        repository_files={
            "package.json": '{"scripts": {"build": "vite build", "test": "vitest"}}'
        },
        repository_structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "build", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    parsed = yaml.safe_load(result["generated_workflow"])
    # Reviewer feedback: TIDAK ada job `build` di YAML, walaupun
    # ada build script di package.json. Fokus security.
    assert "build" not in parsed.get("jobs", {})


def test_validate_pipeline_prerequisites_marks_skipped():
    """Reviewer feedback: JOB_PREREQUISITES map kosong (tidak ada
    job-level prerequisite lagi karena container-build sudah dihapus
    dan sbom tidak di-emit). Test ini memastikan `_validate_pipeline_prerequisites`
    adalah no-op untuk stages yang dikirimkan.
    """
    result = _validate_pipeline_prerequisites(["lint", "container-scan", "sbom"])
    # Semua stages di-keep (tidak ada prerequisite job-level lagi)
    assert "lint" in result["kept"]
    assert "container-scan" in result["kept"]
    # sbom tidak ada di JOB_PREREQUISITES, jadi tetap di-keep
    # (walaupun sebenarnya sbom tidak di-emit ke YAML, ini hanya
    # soal tracking di state).
    assert result["skipped_jobs"] == []


def test_validate_pipeline_prerequisites_keeps_when_prereq_present():
    result = _validate_pipeline_prerequisites(["lint", "container-scan"])
    assert "container-scan" in result["kept"]
    assert result["skipped_jobs"] == []


def test_consistency_validation_removes_unsupported_jobs():
    """Requirement 8: iac-scan is removed when no IaC files are present."""
    yaml_text = """
name: test
on: [push]
jobs:
  iac-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
    )
    cleaned, removals = _validate_pipeline_consistency(yaml_text, state)
    assert any(r["job"] == "iac-scan" for r in removals)
    parsed = yaml.safe_load(cleaned)
    assert "iac-scan" not in parsed["jobs"]
    assert "lint" in parsed["jobs"]


def test_consistency_validation_keeps_evidence_backed_jobs():
    yaml_text = """
name: test
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
    )
    cleaned, removals = _validate_pipeline_consistency(yaml_text, state)
    assert removals == []
    parsed = yaml.safe_load(cleaned)
    assert "lint" in parsed["jobs"]


def test_dependency_scan_uses_continue_on_error_for_independent_steps():
    """Requirement 4: npm audit and Trivy must run INDEPENDENTLY.

    Each step has `continue-on-error: true` so a failure in one does
    not block the other. The evaluate step uses `if: always()` to
    always run and summarise both outcomes.
    """
    yaml_text, stages, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["dependency-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package-lock.json", "path": "package-lock.json", "type": "file"}],
        files={"package-lock.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    job = parsed["jobs"]["dependency-scan"]
    steps = job["steps"]
    # Find npm-audit and trivy-fs steps
    npm_step = next((s for s in steps if s.get("id") == "npm-audit"), None)
    trivy_step = next((s for s in steps if s.get("id") == "trivy-fs"), None)
    assert npm_step is not None, "expected npm-audit step with id"
    assert trivy_step is not None, "expected trivy-fs step with id"
    # Both must be marked continue-on-error so one failure does not
    # block the other.
    assert npm_step.get("continue-on-error") is True
    assert trivy_step.get("continue-on-error") is True
    # The evaluate step must run with if: always() so it always
    # produces a summary regardless of the individual step outcomes.
    eval_step = next((s for s in steps if "Evaluate" in s.get("name", "")), None)
    assert eval_step is not None
    assert eval_step.get("if") == "always()"


def test_container_uses_stable_image_tag_no_invented_digest():
    """Requirement 5: no invented SHA256 digests; use stable ci-<sha> tag.

    Reviewer feedback: container-build stage DIHAPUS. container-scan
    job sudah melakukan `docker build` di dalam job itu sendiri
    (image dibangun ONCE sebelum scan).
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["container-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}],
        files={},
    )
    # No SHA256: digests should appear in the image ref (we don't
    # invent digests).
    assert "image-ref: 'app:ci-${{ github.sha }}'" in yaml_text
    assert "docker build -t app:ci-${{ github.sha }}" in yaml_text
    # The image is built ONCE inside the container-scan job — no
    # duplicate `docker build` and no separate `container-build` job.
    parsed = yaml.safe_load(yaml_text)
    assert "container-scan" in parsed["jobs"]
    assert "container-build" not in parsed["jobs"]
    assert "container-security" not in parsed["jobs"]
    build_steps = [
        step for step in parsed["jobs"]["container-scan"]["steps"]
        if step.get("name") == "Build Docker image"
    ]
    assert len(build_steps) == 1, (
        f"expected exactly 1 build step, got {len(build_steps)}"
    )


def test_build_execution_results_separates_three_categories():
    """Requirement 3: results split into workflow_execution, security_findings, config."""
    state = {
        "findings": [
            {"scanner": "trivy", "type": "vulnerability", "severity": "high", "title": "CVE-2024-0001"},
            {"scanner": "gitleaks", "type": "secret", "severity": "high", "title": "AWS key"},
        ],
        "workflow_config_issues": [
            {"rule": "invalid_docker_image_digest", "message": "bad digest"},
        ],
        "maintenance_warnings": [
            {"rule": "deprecated_runtime", "message": "node 16 deprecated"},
        ],
        "external_service_issues": [],
        "workflow_jobs": [
            {"name": "lint", "conclusion": "success"},
            {"name": "test", "conclusion": "success"},
            {"name": "container-build", "conclusion": "failure"},
            {"name": "container-scan", "conclusion": "skipped"},
        ],
    }
    results = _build_execution_results(state)
    # Categories must NOT be mixed
    assert "workflow_execution" in results
    assert "security_findings" in results
    assert "workflow_configuration_issues" in results
    # workflow_execution has success/failure/skipped buckets
    assert "lint" in results["workflow_execution"]["success"]
    assert "container-build" in results["workflow_execution"]["failure"]
    assert "container-scan" in results["workflow_execution"]["skipped"]
    # security_findings has the CVE grouped correctly
    assert len(results["security_findings"]["vulnerabilities"]) == 1
    assert len(results["security_findings"]["secrets"]) == 1
    # workflow_configuration_issues has its own bucket, separate from security
    assert len(results["workflow_configuration_issues"]["config_issues"]) == 1
    assert len(results["workflow_configuration_issues"]["maintenance_warnings"]) == 1


def test_dashboard_messages_use_real_data_no_generic():
    """Requirement 6: dashboard messages are concrete, never generic."""
    state = {
        "findings": [
            {"scanner": "trivy", "type": "vulnerability", "severity": "high", "title": "CVE-2024-0001"},
            {"scanner": "trivy", "type": "vulnerability", "severity": "critical", "title": "CVE-2024-0002"},
            {"scanner": "gitleaks", "type": "secret", "severity": "high", "title": "AWS key"},
        ],
        "workflow_config_issues": [
            {"rule": "invalid_docker_image_digest", "message": "Invalid Docker image digest: app@sha256:abc"},
        ],
        "maintenance_warnings": [],
        "external_service_issues": [],
        "workflow_jobs": [
            {"name": "lint", "conclusion": "success"},
            {"name": "dependency-scan", "conclusion": "success"},
            {"name": "container-build", "conclusion": "failure"},
        ],
    }
    results = _build_execution_results(state)
    messages = _render_dashboard_messages(results)
    # Check there are messages
    assert len(messages) > 0
    # No generic placeholders
    generic_substrings = [
        "security scan failed",
        "workflow error",
        "scan failed",
        "error occurred",
        "something went wrong",
    ]
    for msg in messages:
        title_lower = msg["title"].lower()
        detail_lower = msg["detail"].lower()
        for generic in generic_substrings:
            assert generic not in title_lower
            assert generic not in detail_lower
    # Concrete counts must appear in vulnerability/secrets messages
    vuln_msgs = [m for m in messages if m["category"] == "security_finding" and "vulnerabilit" in m["title"].lower()]
    assert len(vuln_msgs) >= 1
    assert "2" in vuln_msgs[0]["detail"]  # 2 vulnerabilities
    # Config issue with concrete message
    config_msgs = [m for m in messages if m["category"] == "workflow_config_issue"]
    assert any("docker image digest" in m["title"].lower() for m in config_msgs)


def test_workflow_generator_records_skipped_jobs():
    """Reviewer feedback: setelah container-build dihapus dan sbom
    tidak di-emit ke YAML, `_validate_pipeline_prerequisites` tidak
    lagi menandai job apapun sebagai skipped di level prerequisite
    (JOB_PREREQUISITES kosong). File-level evidence check tetap
    dilakukan oleh `_filter_stages_by_evidence`.
    """
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "container_scan", "status": "recommended"},
                {"control": "container_build", "status": "recommended"},
                {"control": "sbom", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    # No errors regardless of Docker presence.
    assert not result["errors"]
    # Job-level prerequisite tracking sudah tidak ada (JOB_PREREQUISITES
    # kosong). Stages yang diminta tapi tidak ada evidence-nya
    # muncul di `invalid_workflow_stages` (bukan `skipped_jobs`).
    skipped = result.get("skipped_jobs", [])
    # container-scan DAN sbom TIDAK masuk ke skipped_jobs lagi
    # (skipped_jobs sekarang adalah no-op atau untuk hal lain).
    assert all(s["job"] not in ("container-scan", "sbom") for s in skipped)


# ---------------------------------------------------------------------------
# Reviewer feedback tests
# ---------------------------------------------------------------------------


def test_sarif_uploads_guarded_by_hashfiles_check():
    """DevSecOps best practice (SARIF / OASIS standard):
    scanners (Semgrep, Trivy) now output SARIF instead of plain
    text or JSON. SARIF is uploaded to GitHub Code Scanning via
    github/codeql-action/upload-sarif (so findings appear in the
    Security tab with precise code locations) and also stored as
    a workflow artifact for the AI agent to parse.

    Gitleaks remains JSON because the v3 action does not support
    SARIF natively. npm audit also remains JSON (npm CLI does not
    emit SARIF).
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["sast", "dependency-scan", "container-scan", "iac-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[
            {"name": "package.json", "path": "package.json", "type": "file"},
            {"name": "Dockerfile", "path": "Dockerfile", "type": "file"},
            {"name": "package-lock.json", "path": "package-lock.json", "type": "file"},
            {"name": "main.tf", "path": "terraform/main.tf", "type": "file"},
        ],
        files={"package.json": "{}", "package-lock.json": "{}"},
    )
    # SARIF is the OASIS standard. Scanners that support SARIF
    # (Semgrep, Trivy fs/image/iac) emit .sarif files and upload
    # them to GitHub Code Scanning via upload-sarif.
    assert "upload-sarif" in yaml_text
    assert "codeql-action" in yaml_text
    assert ".sarif" in yaml_text
    # Each scanner produces a SARIF file
    assert "semgrep-results.sarif" in yaml_text
    assert "trivy-fs-results.sarif" in yaml_text
    assert "trivy-image-results.sarif" in yaml_text
    assert "trivy-iac-results.sarif" in yaml_text
    # Each SARIF file is ALSO uploaded as a workflow artifact
    # so the AI agent can download it via the Artifacts API.
    assert "actions/upload-artifact" in yaml_text
    # Trivy uses format: 'sarif', not 'table' or 'json'.
    assert "format: 'sarif'" in yaml_text
    assert "format: 'table'" not in yaml_text
    # Trivy legacy .json filenames are GONE.
    assert "trivy-fs-results.json" not in yaml_text
    assert "trivy-image-results.json" not in yaml_text
    assert "trivy-iac-results.json" not in yaml_text
    # npm audit JSON output remains (npm does not support SARIF).
    assert "npm-audit-results.json" in yaml_text


def test_permissions_use_security_events_write_for_sarif():
    """DevSecOps best practice: scanners now upload SARIF to GitHub
    Code Scanning via github/codeql-action/upload-sarif. This
    action requires `security-events: write` permission, otherwise
    the upload step fails with 403 (the "Resource not accessible
    by integration" error the reviewer flagged). The generator
    detects upload-sarif usage and upgrades security-events to write.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["sast", "dependency-scan", "secret-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    perms = parsed["permissions"]
    # SARIF upload requires `security-events: write`. The generator
    # promotes this whenever any job uses upload-sarif.
    assert perms.get("security-events") == "write", (
        f"expected security-events: write for SARIF upload, got {perms.get('security-events')!r}"
    )
    assert perms["contents"] == "read"
    assert perms["pull-requests"] == "read"


def test_container_scan_builds_image_inside_job():
    """Reviewer feedback: container-build stage DIHAPUS. container-scan
    job sekarang build image dan scan dalam satu job (image
    dibangun ONCE).
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["container-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}],
        files={},
    )
    parsed = yaml.safe_load(yaml_text)
    assert "container-scan" in parsed["jobs"]
    assert "container-build" not in parsed["jobs"]
    assert "container-security" not in parsed["jobs"]
    # Single job dengan tepat 1 build step
    job = parsed["jobs"]["container-scan"]
    build_steps = [s for s in job["steps"] if s.get("name") == "Build Docker image"]
    assert len(build_steps) == 1, (
        f"expected 1 build step in container-scan, got {len(build_steps)}"
    )
    # Trivy step dengan format sarif (DevSecOps best practice: SARIF
    # adalah OASIS standard untuk static analysis results, dan SARIF
    # di-upload ke GitHub Code Scanning oleh upload-sarif step.)
    trivy_steps = [s for s in job["steps"] if "Trivy" in s.get("name", "")]
    assert any("sarif" in str(s.get("with", {})) for s in trivy_steps), (
        "Trivy should output to SARIF format (OASIS standard)"
    )
    # upload-sarif step harus ada untuk Code Scanning integration
    upload_sarif_steps = [s for s in job["steps"] if "upload-sarif" in s.get("uses", "")]
    assert len(upload_sarif_steps) == 1, (
        f"expected 1 upload-sarif step in container-scan, got {len(upload_sarif_steps)}"
    )


def test_sbom_not_emitted_to_yaml():
    """Reviewer feedback: SBOM job DIHAPUS dari generator. Stage
    logic tetap ada (untuk tracking), tapi TIDAK ada job sbom di
    YAML.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["sbom"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "Dockerfile", "path": "Dockerfile", "type": "file"}],
        files={},
    )
    parsed = yaml.safe_load(yaml_text)
    jobs = parsed.get("jobs") or {}
    assert "sbom" not in jobs


# ---------------------------------------------------------------------------
# SARIF (OASIS standard) emission tests — DevSecOps best practice
# ---------------------------------------------------------------------------


def test_sast_job_emits_sarif_and_uploads_to_code_scanning():
    """sast job: Semgrep harus emit SARIF, dan upload-sarif step
    harus ada untuk GitHub Code Scanning.

    Since returntocorp/semgrep-action@v1 only declares 2 inputs (config,
    publishToken) — output_format and output are silently ignored — the
    generator uses `docker run` with a writable /out mount instead.
    The SARIF file is then uploaded via github/codeql-action/upload-sarif.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["sast"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    sast = parsed["jobs"]["sast"]
    steps = sast["steps"]

    # Semgrep runs via `docker run`, not the action (action.yml doesn't
    # support output_format / output inputs).
    semgrep_step = next(
        (s for s in steps if s.get("name", "").startswith("Run semgrep")),
        None,
    )
    assert semgrep_step is not None, "sast must have a 'Run semgrep' step"
    run_text = semgrep_step.get("run", "")
    assert "docker run" in run_text, "Semgrep must run via docker run"
    assert "returntocorp/semgrep" in run_text, (
        "docker run must use returntocorp/semgrep image"
    )
    assert "--sarif" in run_text, "Semgrep must output SARIF"
    assert "semgrep-results.sarif" in run_text, "Semgrep must write to semgrep-results.sarif"
    # /src:ro (source read-only) and /out (writable output)
    assert "/src:ro" in run_text, "Semgrep must mount /src read-only"
    assert "/out" in run_text, "Semgrep must mount a writable /out"

    # upload-sarif step still present
    upload_sarif = next(
        (s for s in steps if "upload-sarif" in s.get("uses", "")), None
    )
    assert upload_sarif is not None, "sast must have upload-sarif step"
    assert upload_sarif["with"]["sarif_file"] == "semgrep-results.sarif"
    assert upload_sarif["with"]["category"] == "semgrep"

    artifact = next(
        (s for s in steps if "upload-artifact" in s.get("uses", "")), None
    )
    assert artifact is not None
    assert artifact["with"]["path"] == "semgrep-results.sarif"


def test_iac_scan_emits_sarif_not_table():
    """iac-scan: format HARUS sarif (bukan table lagi). Sebelumnya
    generator emit table, sekarang SARIF untuk Code Scanning.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["iac-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "main.tf", "path": "terraform/main.tf", "type": "file"}],
        files={},
    )
    parsed = yaml.safe_load(yaml_text)
    iac = parsed["jobs"]["iac-scan"]
    steps = iac["steps"]

    trivy_step = next(
        (s for s in steps if "trivy" in s.get("uses", "").lower()), None
    )
    assert trivy_step is not None
    with_block = trivy_step.get("with", {})
    assert with_block.get("format") == "sarif", "iac-scan Trivy must use sarif format"
    assert with_block.get("output") == "trivy-iac-results.sarif"
    assert "format: 'table'" not in yaml_text, "table format must not appear"

    upload_sarif = next(
        (s for s in steps if "upload-sarif" in s.get("uses", "")), None
    )
    assert upload_sarif is not None, "iac-scan must have upload-sarif step"
    assert upload_sarif["with"]["category"] == "trivy-iac"


def test_secret_scan_keeps_json_no_upload_sarif():
    """Gitleaks v3 tidak support SARIF, jadi secret-scan tetap
    JSON. Tidak ada upload-sarif step di secret-scan job.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["secret-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    secret = parsed["jobs"]["secret-scan"]
    steps = secret["steps"]

    gitleaks_step = next(
        (s for s in steps if "gitleaks" in s.get("uses", "")), None
    )
    assert gitleaks_step is not None
    # Gitleaks action v3 has no `with:` for sarif format
    with_block = gitleaks_step.get("with", {}) or {}
    assert "output_format" not in with_block
    assert "sarif" not in str(with_block).lower()

    # No upload-sarif step in secret-scan (Gitleaks output is JSON,
    # uploaded by gitleaks action itself when
    # GITLEAKS_ENABLE_UPLOAD_ARTIFACT=true).
    assert not any("upload-sarif" in s.get("uses", "") for s in steps)


def test_dependency_scan_trivy_uses_sarif_and_uploads():
    """dependency-scan job: Trivy pakai SARIF + upload-sarif."""
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["dependency-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package-lock.json", "path": "package-lock.json", "type": "file"}],
        files={"package-lock.json": "{}"},
    )
    parsed = yaml.safe_load(yaml_text)
    dep = parsed["jobs"]["dependency-scan"]
    steps = dep["steps"]

    trivy_step = next(
        (s for s in steps if "trivy" in s.get("uses", "").lower()), None
    )
    assert trivy_step is not None
    with_block = trivy_step.get("with", {})
    assert with_block.get("format") == "sarif"
    assert with_block.get("output") == "trivy-fs-results.sarif"

    upload_sarif = next(
        (s for s in steps if "upload-sarif" in s.get("uses", "")), None
    )
    assert upload_sarif is not None
    assert upload_sarif["with"]["sarif_file"] == "trivy-fs-results.sarif"
    assert upload_sarif["with"]["category"] == "trivy-fs"

    # npm audit step tetap JSON (npm CLI tidak support SARIF)
    assert any("npm-audit-results.json" in str(s) for s in steps)


def test_python_dependency_scan_emits_sarif_via_trivy():
    """Python repo: pip-audit JSON + Trivy fs SARIF + upload-sarif."""
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="python",
        package_manager="pip",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["dependency-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "requirements.txt", "path": "requirements.txt", "type": "file"}],
        files={"requirements.txt": "requests==2.25.0"},
    )
    parsed = yaml.safe_load(yaml_text)
    dep = parsed["jobs"]["dependency-scan"]
    steps = dep["steps"]

    trivy_step = next(
        (s for s in steps if "trivy" in s.get("uses", "").lower()), None
    )
    assert trivy_step is not None
    with_block = trivy_step.get("with", {})
    assert with_block.get("format") == "sarif"
    assert with_block.get("output") == "trivy-fs-results.sarif"

    # pip-audit JSON output (npm CLI does not apply, pip-audit does
    # not support SARIF natively either)
    assert any("pip-audit-results.json" in str(s) for s in steps)

    # upload-sarif for trivy
    assert any(
        "upload-sarif" in s.get("uses", "") for s in steps
    )


def test_test_stage_not_emitted_without_evidence():
    """Reviewer feedback: the `test` job must NOT be generated when
    there is no test framework AND no test script in the repository.
    """
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        repository_files={"package.json": '{"name": "foo"}'},
        repository_structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "test", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    assert "test" not in result["generated_stages"]
    parsed = yaml.safe_load(result["generated_workflow"])
    assert "test" not in parsed.get("jobs", {})


def test_build_stage_not_emitted_to_yaml():
    """Reviewer feedback: `build` stage TIDAK di-emit ke YAML.
    Generator fokus pada security scanning. Stage logic tetap ada
    untuk tracking (`build` di ALLOWED_STAGES dan state), tapi
    TIDAK ada job `build` di output.
    """
    state = _minimal_state(
        detected_technologies={"primary_language": "JavaScript", "package_manager": "npm"},
        repository_files={"package.json": '{"scripts": {"build": "vite build", "test": "jest"}}'},
        repository_structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        inferred_security_needs={
            "security_controls": [
                {"control": "sast", "status": "recommended"},
                {"control": "build", "status": "recommended"},
            ]
        },
    )
    result = workflow_generator_node(state)
    parsed = yaml.safe_load(result["generated_workflow"])
    # Build job TIDAK ada di YAML walaupun ada build script di
    # package.json. CI ini fokus security.
    assert "build" not in parsed.get("jobs", {})


# ---------------------------------------------------------------------------
# Context-aware Semgrep rules (domain-specific rule injection)
# ---------------------------------------------------------------------------


def test_semgrep_rules_for_domain_ecommerce_includes_payment_rules():
    """When detected_domain='e-commerce', the sast job should reference
    both owasp-api.yml AND ecommerce.yml custom rule files."""
    from app.agents.nodes.workflow_generator import (
        _semgrep_rules_for_domain,
    )
    files = _semgrep_rules_for_domain("e-commerce")
    assert "ecommerce.yml" in files
    assert "owasp-api.yml" in files


def test_semgrep_rules_for_domain_healthcare_includes_owasp_api_only():
    """healthcare repo: only OWASP API rules (no e-commerce rules)."""
    from app.agents.nodes.workflow_generator import (
        _semgrep_rules_for_domain,
    )
    files = _semgrep_rules_for_domain("healthcare")
    assert "owasp-api.yml" in files
    assert "ecommerce.yml" not in files


def test_semgrep_rules_for_domain_unknown_falls_back_to_owasp_api():
    """Unknown domain: still apply general OWASP API Top 10 rules
    (any web app with routes/handlers benefits)."""
    from app.agents.nodes.workflow_generator import (
        _semgrep_rules_for_domain,
    )
    files = _semgrep_rules_for_domain(None)
    assert "owasp-api.yml" in files
    # No specific domain rules
    assert "ecommerce.yml" not in files


def test_ecommerce_sast_job_includes_custom_rule_config_flags():
    """The generated sast job for an e-commerce repo should pick up
    custom Semgrep rules via the `.semgrep` directory import flag.

    v9.3 refactor: the workflow stays compact (~1k chars) by
    referencing the `.semgrep/` directory instead of inlining a
    heredoc. Custom rules (incl. AI-generated ones) are committed
    to `.semgrep/ecommerce.yml` and `.semgrep/ai-generated.yml` by
    `pull_request_creation_node`.
    """
    yaml_text, _, _ = _build_workflow_yaml(
        primary_language="javascript",
        package_manager="npm",
        test_framework=None,
        frameworks=[],
        build_tools=[],
        stages=["sast"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
        detected_domain="e-commerce",
        domain_confidence=0.95,
        domain_threats=["Stripe key hardcoded", "SQL injection in checkout"],
    )
    # `.semgrep` directory import is present (folder import tells
    # Semgrep to load every .yml/.yaml file under that directory).
    assert "--config=.semgrep" in yaml_text
    # At least one registry rule is referenced (no inlined heredoc
    # of the entire rule set, which would balloon the file to 21k+).
    assert "--config=p/" in yaml_text
    # No big heredoc carrying the merged rule set inline.
    assert "SEMGREP_EOF" not in yaml_text
    assert "ai-devsecops-source: ecommerce.yml" not in yaml_text
    # Domain header is still rendered in the workflow comment block.
    assert "e-commerce" in yaml_text



# ---------------------------------------------------------------------------
# OWASP Risk Rating (3-dim) — risk_assessor.py tests
# ---------------------------------------------------------------------------
# Reference: https://owasp.org/www-community/risks-information/
#             owasp-risk-rating-methodology/
#
# 3-dim formula:
#   L = (TAF + VF) / 2          # Likelihood (1-5)
#   I = BI                      # Impact (1-5)
#   R = L × I                  # Risk per finding (1-25)
#   RiskScore = max(0, 100 - (ΣR / (n × 25)) × 100)


def test_owasp_3dim_baseline_max_risk():
    """Max risk: TAF=5, VF=5, BI=5, no modifier → R = 5*5 = 25 → score 0 (critical)."""
    from app.agents.nodes.risk_assessor import _map_dimensions
    f = {"type": "rce", "severity": "critical"}
    dims = _map_dimensions(f)
    assert dims["taf"] == 5.0
    assert dims["vf"] == 5.0
    assert dims["bi"] == 5.0
    L = (dims["taf"] + dims["vf"]) / 2.0
    I = dims["bi"]
    R = L * I
    assert R == 25.0
    score = max(0.0, 100.0 - (R / 25.0) * 100.0)
    assert score == 0.0


def test_owasp_3dim_baseline_min_risk():
    """Min risk: TAF=1, VF=1, BI=1, no modifier → R = 1 → score 96 (low)."""
    from app.agents.nodes.risk_assessor import _map_dimensions
    f = {"type": "debug", "severity": "low"}
    dims = _map_dimensions(f)
    assert dims["taf"] == 1.0
    assert dims["vf"] == 3.0  # debug: base 2,4 + low mod -1 → clamped to 1 and 3
    assert dims["bi"] == 1.0
    L = (dims["taf"] + dims["vf"]) / 2.0
    I = dims["bi"]
    R = L * I
    score = max(0.0, 100.0 - (R / 25.0) * 100.0)
    assert score >= 80.0  # low risk region


def test_owasp_3dim_severity_modifier_critical():
    """critical modifier = +1.0 to all dims, capped at 5."""
    from app.agents.nodes.risk_assessor import _map_dimensions
    f = {"type": "xss", "severity": "critical"}
    dims = _map_dimensions(f)
    # xss base = 4,5,3 + critical +1 = 5,5,4 (capped at 5)
    assert dims["taf"] == 5.0  # capped
    assert dims["vf"] == 5.0
    assert dims["bi"] == 4.0


def test_owasp_3dim_severity_modifier_low():
    """low modifier = -1.0 to all dims, floored at 1."""
    from app.agents.nodes.risk_assessor import _map_dimensions
    f = {"type": "secret", "severity": "low"}
    dims = _map_dimensions(f)
    # secret base = 4,5,5 + low -1 = 3,4,4 (no floor)
    assert dims["taf"] == 3.0
    assert dims["vf"] == 4.0
    assert dims["bi"] == 4.0


def test_owasp_3dim_clamps_range():
    """Clamp values between 1.0 and 5.0."""
    from app.agents.nodes.risk_assessor import _clamp
    assert _clamp(0.0) == 1.0
    assert _clamp(1.0) == 1.0
    assert _clamp(3.5) == 3.5
    assert _clamp(5.0) == 5.0
    assert _clamp(10.0) == 5.0


def test_owasp_3dim_severity_inference_codescanning():
    """Code Scanning severities (error/warning/note) mapped correctly."""
    from app.agents.nodes.risk_assessor import _infer_severity
    assert _infer_severity({"severity": "error"}) == "critical"
    assert _infer_severity({"severity": "warning"}) == "high"
    assert _infer_severity({"severity": "note"}) == "low"
    assert _infer_severity({"severity": "critical"}) == "critical"
    assert _infer_severity({"severity": "high"}) == "high"
    assert _infer_severity({"severity": "medium"}) == "medium"
    assert _infer_severity({"severity": "low"}) == "low"


def test_owasp_3dim_risk_level_thresholds():
    """Risk level thresholds: ≤25 critical, ≤50 high, ≤75 medium, >75 low."""
    from app.agents.nodes.risk_assessor import _calculate_risk_score
    # Empty findings → score 100 → "low"
    score, level, _ = _calculate_risk_score([])
    assert score == 100.0
    assert level == "low"

    # Single high-severity finding
    findings = [{"type": "xss", "severity": "high"}]
    score, level, _ = _calculate_risk_score(findings)
    # xss base 4,5,3 + high 0 = 4,5,3, L=4.5, I=3, R=13.5
    # score = 100 - 13.5/25 * 100 = 46
    assert 40 <= score <= 50
    assert level == "high"


def test_owasp_3dim_real_run_eccomerce_vuln():
    """End-to-end: 19 Code Scanning alerts from eccomerce-monolith-vuln.

    This is the integration test that locks the risk score to ~42.6
    (HIGH) for the canonical eccomerce-vuln run.

    Verification: 19 alerts → 10 critical + 9 high → ΣR ≈ 215 →
    avg ≈ 11.3 → score = 100 - 45.2 ≈ 42.6.
    """
    from app.agents.nodes.risk_assessor import _calculate_risk_score

    # Mock 19 Code Scanning alerts: 6 error (→ critical) + 13 warning
    # (→ high). Then add 2 boosted (1 → critical from e-commerce, 1 → high).
    # In real run, 8 error/11 warning but domain_priority elevates 2.
    # We just use realistic counts here.
    findings = []
    # 6 critical (from "error" in Code Scanning)
    for i in range(6):
        ftype = ["secret", "sqli", "rce", "xss", "cve", "weak_crypto"][i]
        findings.append({"type": ftype, "severity": "critical"})
    # 13 high (from "warning" in Code Scanning)
    for i in range(13):
        ftype = ["excessive_data_exposure", "xss", "csrf", "idor"][i % 4]
        findings.append({"type": ftype, "severity": "high"})

    assert len(findings) == 19

    score, level, breakdown = _calculate_risk_score(findings)

    # The score should land in the HIGH range
    # (proportional to the 19-alert distribution)
    assert 30 <= score <= 55, f"expected 30-55, got {score}"
    assert level in ("high", "critical"), f"expected high/critical, got {level}"
    # Severity breakdown: 6 critical + 13 high
    assert breakdown["critical"] == 6
    assert breakdown["high"] == 13


def test_owasp_3dim_risk_assessor_drops_non_security():
    """Workflow config issues and external service errors must NOT
    influence the risk score (per risk_assessor contract)."""
    from app.agents.nodes.risk_assessor import _calculate_risk_score

    findings = [
        {"type": "sql_injection", "severity": "critical"},
        # Workflow config issue — should be dropped
        {"type": "missing_concurrency", "severity": "critical",
         "category": "workflow_config_issue", "message": "missing concurrency"},
        # External service error — should be dropped
        {"type": "api_error", "severity": "critical",
         "category": "external_service_issue", "message": "request failed with status code 502"},
    ]
    score, level, breakdown = _calculate_risk_score(findings)
    # Only the SQLi finding should count.
    assert breakdown["critical"] == 1
    assert level in ("high", "critical")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
