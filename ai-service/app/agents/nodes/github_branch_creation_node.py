import time

from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import create_branch


def github_branch_creation_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    if not state.get("validation_passed", False):
        state["errors"].append("Validation failed, cannot create branch")
        return state

    repo = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN
    base_branch = state.get("repository_default_branch", "main")
    timestamp = int(time.time())
    branch_name = f"ai-devsecops/generate-workflow-{timestamp}"

    try:
        success = create_branch(repo, branch_name, base_branch, github_token)
        if not success:
            state["errors"].append(f"Failed to create branch '{branch_name}'")
            return state
        state["github_branch"] = branch_name
    except Exception as e:
        state["errors"].append(f"Branch creation failed: {e}")

    return state