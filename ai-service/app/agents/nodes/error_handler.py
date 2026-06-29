from app.agents.pipeline_state import PipelineEngineerState


def error_handler_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if not state.get("summary"):
        errors = state.get("errors", [])
        error_stage = state.get("error_stage", "unknown")
        if errors:
            state["summary"] = f"Pipeline generation failed at '{error_stage}' stage: {'; '.join(errors[:3])}"
        else:
            state["summary"] = "Pipeline generation completed with warnings."
    return state