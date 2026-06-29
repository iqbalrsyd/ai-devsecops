import json

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm

DEPLOYMENT_DETECTION_PROMPT = """You are a DevSecOps engineer analyzing deployment infrastructure.

Given the repository structure and files, detect deployment technologies and recommend deployment target.

Repository structure:
{structure}

Key files:
{files}

Existing workflows:
{workflows}

Analyze and return JSON with:
- docker: boolean, true if Dockerfile detected
- docker_confidence: confidence score 0.0-1.0
- docker_reason: explanation of Docker detection
- docker_compose: boolean, true if docker-compose.yml detected
- docker_compose_confidence: confidence score 0.0-1.0
- kubernetes: boolean, true if Kubernetes manifests detected (k8s/, *.yaml with kind: Deployment/Service)
- kubernetes_confidence: confidence score 0.0-1.0
- kubernetes_reason: explanation of Kubernetes detection
- terraform: boolean, true if *.tf files detected
- terraform_confidence: confidence score 0.0-1.0
- helm: boolean, true if Chart.yaml or values.yaml detected
- cloud_provider: detected cloud provider ("AWS", "Azure", "GCP") or null
- recommended_deployment_target: recommended deployment target string
- alternative_deployment_targets: list of alternative targets
- deployment_reason: explanation of why this target is recommended

Deployment targets to consider:
- Docker Host (for Dockerfile without K8s)
- Kubernetes (for K8s manifests)
- Serverless (for Lambda/Cloud Functions configs)
- Railway (easy Docker deployment)
- Render (easy deployment)
- Azure App Service
- AWS ECS/EKS
- GCP Cloud Run

Return ONLY valid JSON. No markdown.
"""


def deployment_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    structure = state.get("repository_structure", [])
    files = state.get("repository_files", {}) or {}
    workflows = state.get("existing_workflows", [])

    deployment_info = _detect_from_files(structure, files)
    state["detected_deployment"] = deployment_info

    try:
        prompt = DEPLOYMENT_DETECTION_PROMPT.format(
            structure=json.dumps(structure, indent=2)[:2000],
            files=json.dumps(list(files.keys())[:100], indent=2),
            workflows=json.dumps(workflows, indent=2)[:1000],
        )

        llm = get_llm()
        response = llm.invoke(prompt)
        from app.agents.llm_response_parser import parse_llm_json_object
        deployment = parse_llm_json_object(response.content) or {}

        for key, default_value in [
            ("docker", False),
            ("docker_confidence", 0.8),
            ("docker_reason", ""),
            ("docker_compose", False),
            ("docker_compose_confidence", 0.8),
            ("kubernetes", False),
            ("kubernetes_confidence", 0.8),
            ("kubernetes_reason", ""),
            ("terraform", False),
            ("terraform_confidence", 0.8),
            ("helm", False),
            ("cloud_provider", None),
            ("recommended_deployment_target", "docker"),
            ("alternative_deployment_targets", []),
            ("deployment_reason", ""),
        ]:
            if key not in deployment:
                deployment[key] = default_value

        deployment = {**deployment_info, **deployment}

        state["detected_deployment"] = deployment
        state["recommended_deployment_target"] = deployment.get("recommended_deployment_target", "docker")

    except json.JSONDecodeError as e:
        state["errors"].append(f"Deployment detection JSON parse failed: {e}")
        state["error_stage"] = "deployment_detection"
    except Exception as e:
        state["errors"].append(f"Deployment detection failed: {e}")
        state["error_stage"] = "deployment_detection"

    return state


def _detect_from_files(structure: list, files: dict) -> dict:
    result = {
        "docker": False,
        "docker_confidence": 0.0,
        "docker_reason": "",
        "docker_compose": False,
        "docker_compose_confidence": 0.0,
        "kubernetes": False,
        "kubernetes_confidence": 0.0,
        "kubernetes_reason": "",
        "terraform": False,
        "terraform_confidence": 0.0,
        "helm": False,
        "cloud_provider": None,
        "recommended_deployment_target": "docker",
        "alternative_deployment_targets": [],
        "deployment_reason": "",
    }

    docker_count = 0
    k8s_count = 0
    tf_count = 0

    def check_file(name: str) -> None:
        nonlocal docker_count, k8s_count, tf_count
        name_lower = name.lower()

        if name_lower == "dockerfile" or name_lower.startswith("dockerfile."):
            docker_count += 1

        if "docker-compose" in name_lower or name_lower == "docker-compose.yml" or name_lower == "docker-compose.yaml":
            result["docker_compose"] = True
            result["docker_compose_confidence"] = 0.95

        if "k8s" in name_lower or "kubernetes" in name_lower or "/k8s/" in name_lower:
            k8s_count += 1

        if name_lower.endswith(".tf") or "/k8s/" in name_lower or name_lower.endswith(".yaml"):
            if "deployment" in name_lower or "service" in name_lower or "ingress" in name_lower:
                k8s_count += 1

        if name_lower.endswith(".tf"):
            tf_count += 1

        if "chart.yaml" in name_lower or "values.yaml" in name_lower:
            result["helm"] = True

        if "aws" in name_lower or "azure" in name_lower or "gcp" in name_lower:
            if "terraform" in name_lower:
                if "aws" in name_lower:
                    result["cloud_provider"] = "AWS"
                elif "azure" in name_lower:
                    result["cloud_provider"] = "Azure"
                elif "gcp" in name_lower:
                    result["cloud_provider"] = "GCP"

    for item in structure or []:
        if isinstance(item, dict):
            name = item.get("name", "")
            check_file(name)
        elif isinstance(item, str):
            check_file(item)

    for fname in (files or {}).keys():
        check_file(fname)

    if docker_count > 0:
        result["docker"] = True
        result["docker_confidence"] = min(0.95, 0.7 + docker_count * 0.1)
        result["docker_reason"] = f"Detected {docker_count} Dockerfile(s)"

    if k8s_count > 0:
        result["kubernetes"] = True
        result["kubernetes_confidence"] = min(0.95, 0.7 + k8s_count * 0.1)
        result["kubernetes_reason"] = f"Detected {k8s_count} Kubernetes manifest(s)"

    if tf_count > 0:
        result["terraform"] = True
        result["terraform_confidence"] = min(0.95, 0.7 + tf_count * 0.1)

    if result["kubernetes"]:
        result["recommended_deployment_target"] = "kubernetes"
        result["alternative_deployment_targets"] = ["aks", "eks", "gke"]
        result["deployment_reason"] = "Kubernetes manifests detected - recommended deployment is Kubernetes"
    elif result["docker"]:
        result["recommended_deployment_target"] = "docker"
        result["alternative_deployment_targets"] = ["railway", "render", "azure_app_service"]
        result["deployment_reason"] = "Dockerfile detected - recommended deployment is Docker host"
    else:
        result["recommended_deployment_target"] = "generic"
        result["alternative_deployment_targets"] = ["github_pages", "vercel", "netlify"]
        result["deployment_reason"] = "No containerization detected - using generic deployment"

    return result