from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import get_workflow_id_by_name, trigger_workflow_dispatch


def workflow_execution_node(state: PipelineEngineerState) -> PipelineEngineerState:
    repo = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN
    auto_deploy = state.get("auto_deploy", False)

    if not repo:
        state["errors"].append("No repository specified")
        return state

    if not auto_deploy:
        state["workflow_status"] = "pending_merge"
        state["workflow_conclusion"] = None
        return state

    filename = "ci-cd.yml"
    try:
        wf_id = get_workflow_id_by_name(repo, filename, github_token)
        if wf_id is None:
            state["errors"].append(f"Workflow '{filename}' not found in repository")
            return state

        success = trigger_workflow_dispatch(repo, filename, state.get("repository_default_branch", "main"), github_token)
        if success:
            state["workflow_status"] = "triggered"
        else:
            state["errors"].append("Failed to trigger workflow dispatch")
    except Exception as e:
        state["errors"].append(f"Workflow execution failed: {e}")

    return state