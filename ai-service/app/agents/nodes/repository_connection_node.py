from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import get_github_client


def repository_connection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    repo_full_name = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN

    if not repo_full_name:
        state["errors"].append("No repository specified")
        state["error_stage"] = "connection"
        return state

    if not github_token:
        state["errors"].append("No GitHub token available")
        state["error_stage"] = "connection"
        return state

    try:
        gh = get_github_client(github_token)
        user = gh.get_user().login
        repo = gh.get_repo(repo_full_name)
        state["repository_url"] = repo.html_url
        state["repository_default_branch"] = repo.default_branch
    except Exception as e:
        state["errors"].append(f"GitHub connection failed: {e}")
        state["error_stage"] = "connection"

    return state