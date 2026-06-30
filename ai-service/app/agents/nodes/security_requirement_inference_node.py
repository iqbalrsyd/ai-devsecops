import json

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm

SECURITY_INFERENCE_PROMPT = """You are a DevSecOps engineer determining security requirements for a project.

Based on the detected technologies, architecture, and deployment, determine which security controls are needed with detailed explanations.

Technologies:
{technologies}

Architecture:
{architecture}

Deployment:
{deployment}

Return a JSON object with detailed security requirements:

{{
  "security_controls": [
    {{
      "control": "lint",
      "status": "recommended|optional|not_required",
      "reason": "Why this status",
      "tool": "recommended tool name or null",
      "tool_version": "specific version or 'latest'"
    }},
    ... for each control
  ],
  "all_controls": [
    "lint", "test", "build", "sast", "dependency_scan", "secret_scan",
    "container_scan", "container_build", "iac_scan", "license_check",
    "sbom", "deploy", "per_service_sast", "per_service_dep_scan",
    "api_gateway_test", "service_mesh_audit"
  ],
  "required_tools": [
    {{
      "name": "tool_name",
      "purpose": "what it does",
      "language": "applicable language or 'generic'"
    }}
  ],
  "pipeline_stages": [
    {{
      "name": "stage_name",
      "order": 1,
      "required_for": ["control1", "control2"],
      "estimated_duration_minutes": 2
    }}
  ]
}}

Controls list with definitions:
- lint: code quality check (always recommended)
- test: unit tests (recommended if test framework detected)
- build: compilation/build (recommended if build tool detected)
- sast: static application security testing (always recommended for codebases)
- dependency_scan: dependency vulnerability scanning (recommended if package manager detected)
- secret_scan: secret detection (always recommended)
- container_scan: container vulnerability scanning (recommended if containerized)
- container_build: container image build (recommended if Dockerfile present)
- iac_scan: infrastructure as code scanning (recommended if Terraform/K8s detected)
- license_check: license compliance (optional if package manager detected)
- sbom: software bill of materials (recommended if containerized)
- deploy: deployment (recommended if deployment config detected)
- per_service_sast: run SAST per service directory (DISABLED per R2.1)
- per_service_dep_scan: dependency scan per service directory (DISABLED per R2.1)
- api_gateway_test: API gateway configuration audit (if api gateway detected)

For monolitik: use single scan approach. Arsitektur bukan variabel
eksperimen per R2.1, sehingga per_service_* stages TIDAK di-emit.

Return ONLY valid JSON. No markdown.
"""


def _get_arch_type(architecture) -> str:
    if isinstance(architecture, dict):
        return architecture.get("architecture_type", "monolithic")
    if isinstance(architecture, str):
        return architecture
    return "monolithic"


_MODULAR_STAGES = [
    "per_service_sast",
    "per_service_dep_scan",
    "api_gateway_test",
    "service_mesh_audit",
    "secret_scan_all",
]

_MODULAR_TOOLS = ["checkov", "kubeaudit"]


def _get_default_controls(technologies: dict, architecture: dict, deployment: dict) -> list[dict]:
    controls = []
    arch_type = architecture.get("architecture_type", "monolithic") if isinstance(architecture, dict) else "monolithic"
    
    controls.append({
        "control": "lint",
        "status": "recommended",
        "reason": "Code quality linting is essential for maintaining code standards",
        "tool": _get_lint_tool(technologies),
        "tool_version": "latest"
    })
    
    if technologies.get("test_framework"):
        controls.append({
            "control": "test",
            "status": "recommended",
            "reason": f"Test framework '{technologies.get('test_framework')}' detected",
            "tool": technologies.get("test_framework"),
            "tool_version": "latest"
        })
    
    if technologies.get("build_tools"):
        controls.append({
            "control": "build",
            "status": "recommended",
            "reason": "Build tool detected - verify compilation succeeds",
            "tool": technologies.get("build_tools", [None])[0] or "generic",
            "tool_version": "latest"
        })
    
    controls.append({
        "control": "sast",
        "status": "recommended",
        "reason": f"SAST is essential for {technologies.get('primary_language', 'code')} codebase security",
        "tool": _get_sast_tool(technologies),
        "tool_version": "latest"
    })
    
    if technologies.get("package_manager"):
        controls.append({
            "control": "dependency_scan",
            "status": "recommended",
            "reason": f"Package manager '{technologies.get('package_manager')}' detected - scan for vulnerabilities",
            "tool": _get_dep_scan_tool(technologies),
            "tool_version": "latest"
        })
    
    controls.append({
        "control": "secret_scan",
        "status": "recommended",
        "reason": "Secret scanning prevents credential leaks in codebase",
        "tool": "gitleaks",
        "tool_version": "latest"
    })
    
    if deployment.get("docker", False):
        controls.append({
            "control": "container_scan",
            "status": "recommended",
            "reason": "Docker container detected - scan image for vulnerabilities",
            "tool": "trivy",
            "tool_version": "latest"
        })
        controls.append({
            "control": "container_build",
            "status": "recommended",
            "reason": "Dockerfile detected - build and scan container image",
            "tool": "docker",
            "tool_version": "latest"
        })
        controls.append({
            "control": "sbom",
            "status": "recommended",
            "reason": "Containerized deployment - generate SBOM for compliance",
            "tool": "syft",
            "tool_version": "latest"
        })
    
    if deployment.get("kubernetes", False):
        controls.append({
            "control": "iac_scan",
            "status": "recommended",
            "reason": "Kubernetes manifests detected - scan for misconfigurations",
            "tool": "trivy",
            "tool_version": "latest"
        })
        controls.append({
            "control": "service_mesh_audit",
            "status": "recommended",
            "reason": "Kubernetes detected - audit network policies and mTLS",
            "tool": "kube-bench",
            "tool_version": "latest"
        })
    
    if deployment.get("terraform", False):
        controls.append({
            "control": "iac_scan",
            "status": "recommended",
            "reason": "Terraform files detected - scan for IaC misconfigurations",
            "tool": "checkov",
            "tool_version": "latest"
        })
    
    controls.append({
        "control": "license_check",
        "status": "optional",
        "reason": "License compliance checking is optional but recommended for enterprises",
        "tool": "fossology",
        "tool_version": "latest"
    })
    
    if arch_type == "modular_monolith":
        # Per R2.1, arsitektur bukan variabel eksperimen. Branch ini TIDAK
        # akan pernah dieksekusi (arch_type selalu "monolithic"). Disimpan
        # untuk backward compatibility.
        controls.append({
            "control": "per_service_sast",
            "status": "disabled",
            "reason": f"{arch_type} architecture - per-service SAST disabled per R2.1 (monolithic only)",
            "tool": "semgrep",
            "tool_version": "latest"
        })
        controls.append({
            "control": "per_service_dep_scan",
            "status": "disabled",
            "reason": f"{arch_type} architecture - per-service dep scan disabled per R2.1 (monolithic only)",
            "tool": "trivy",
            "tool_version": "latest"
        })
    
    if architecture.get("has_api_gateway", False):
        controls.append({
            "control": "api_gateway_test",
            "status": "recommended",
            "reason": "API gateway detected - test rate limiting, CORS, and authentication",
            "tool": "curl",
            "tool_version": "latest"
        })
    
    return controls


def _get_lint_tool(technologies: dict) -> str:
    pm = technologies.get("package_manager", "").lower()
    if "npm" in pm or "yarn" in pm:
        return "eslint"
    elif "pip" in pm or "poetry" in pm:
        return "ruff"
    elif "go mod" in pm:
        return "golangci-lint"
    elif "cargo" in pm:
        return "clippy"
    return "semgrep"


def _get_sast_tool(technologies: dict) -> str:
    lang = technologies.get("primary_language", "").lower()
    if lang == "go":
        return "codeql"
    elif lang == "python":
        return "bandit"
    elif lang in ("typescript", "javascript"):
        return "eslint"
    elif lang == "java":
        return "spotbugs"
    return "semgrep"


def _get_dep_scan_tool(technologies: dict) -> str:
    pm = technologies.get("package_manager", "").lower()
    if "npm" in pm:
        return "npm audit"
    elif "pip" in pm:
        return "safety"
    elif "go mod" in pm:
        return "govulncheck"
    return "trivy"


def security_requirement_inference_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    technologies = state.get("detected_technologies", {})
    architecture = state.get("detected_architecture", {})
    deployment = state.get("detected_deployment", {})
    arch_type = state.get("detected_architecture_type") or _get_arch_type(architecture)

    prompt = SECURITY_INFERENCE_PROMPT.format(
        technologies=json.dumps(technologies, indent=2),
        architecture=json.dumps(architecture, indent=2),
        deployment=json.dumps(deployment, indent=2),
    )

    llm = get_llm()
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        inferred = json.loads(content)
        state["inferred_security_needs"] = inferred
    except json.JSONDecodeError:
        inferred = {"security_controls": _get_default_controls(technologies, architecture, deployment)}
        state["inferred_security_needs"] = inferred
    except Exception as e:
        state["errors"].append(f"Security requirement inference failed: {e}")
        state["error_stage"] = "security_inference"
        inferred = {"security_controls": _get_default_controls(technologies, architecture, deployment)}
        state["inferred_security_needs"] = inferred

    inferred = state.get("inferred_security_needs", {})
    
    if arch_type == "modular_monolith":
        # Per R2.1, arsitektur bukan variabel eksperimen. Branch ini TIDAK
        # akan pernah dieksekusi (arch_type selalu "monolithic"). Disimpan
        # untuk backward compatibility.
        stages = inferred.get("required_stages", [])
        tools = inferred.get("required_tools", [])
        # Disabled per R2.1 — no-op instead of appending modular stages
        inferred["required_stages"] = stages
        inferred["required_tools"] = tools
        state["inferred_security_needs"] = inferred

    return state