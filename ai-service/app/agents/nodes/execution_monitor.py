import time

from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import get_workflow_run, get_workflow_run_jobs

POLL_INTERVAL = 5
TIMEOUT = 1800
TERMINAL_STATUSES = {"completed", "success", "failure", "cancelled", "skipped"}


def execution_monitor_node(state: PipelineEngineerState) -> PipelineEngineerState:
    run_id = state.get("workflow_run_id")
    repo = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN

    if not run_id:
        state["errors"].append("No workflow run ID to monitor")
        return state

    if not repo:
        state["errors"].append("No repository specified")
        return state

    all_logs = []
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > TIMEOUT:
            state["workflow_status"] = "timeout"
            state["errors"].append("Workflow execution timed out after 30 minutes")
            break

        try:
            run_data = get_workflow_run(repo, run_id, github_token)
            if not run_data:
                state["workflow_status"] = "unknown"
                time.sleep(POLL_INTERVAL)
                continue

            status = run_data.get("status", "unknown")
            conclusion = run_data.get("conclusion")

            state["workflow_status"] = status
            state["workflow_conclusion"] = conclusion

            try:
                jobs = get_workflow_run_jobs(repo, run_id, github_token)
                state["workflow_jobs"] = jobs
                for job in jobs:
                    for step in job.get("steps", []):
                        log_entry = {
                            "job": job.get("name", ""),
                            "step": step.get("name", ""),
                            "status": step.get("status", ""),
                            "conclusion": step.get("conclusion"),
                            "number": step.get("number", 0),
                        }
                        all_logs.append(log_entry)
            except Exception:
                pass

            state["workflow_logs"] = all_logs

            if status in TERMINAL_STATUSES or conclusion in TERMINAL_STATUSES:
                break

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            state["errors"].append(f"Monitoring error: {e}")
            time.sleep(POLL_INTERVAL)

    return state