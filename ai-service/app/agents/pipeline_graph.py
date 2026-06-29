from langgraph.graph import StateGraph, END

from app.agents.pipeline_state import PipelineEngineerState
from app.agents.nodes.repository_connection_node import repository_connection_node
from app.agents.nodes.repository_scan_node import repository_scan_node
from app.agents.nodes.technology_detection_node import technology_detection_node
from app.agents.nodes.architecture_detection_node import architecture_detection_node
from app.agents.nodes.deployment_detection_node import deployment_detection_node
from app.agents.nodes.domain_detection_node import domain_detection_node
from app.agents.nodes.coverage_inference_node import coverage_inference_node
from app.agents.nodes.pattern_inference_node import pattern_inference_node
from app.agents.nodes.pipeline_augmentation_node import pipeline_augmentation_node
from app.agents.nodes.job_reasoning_node import job_reasoning_node
from app.agents.nodes.workflow_generator import workflow_generator_node
from app.agents.nodes.workflow_validator import workflow_validator_node
from app.agents.nodes.workflow_repair_node import workflow_repair_node
from app.agents.nodes.github_branch_creation_node import github_branch_creation_node
from app.agents.nodes.pull_request_creation_node import pull_request_creation_node
from app.agents.nodes.security_analyzer import security_analyzer_node
from app.agents.nodes.recommendation_gen import recommendation_gen_node
from app.agents.nodes.response_formatter import response_formatter_node


def route_validation(state: PipelineEngineerState) -> str:
    return "passed" if state.get("validation_passed", False) else "failed"


VALIDATION_ROUTES = {
    "passed": "workflow_repair",
    "failed": "response_formatter",
}


def build_pipeline_graph() -> StateGraph:
    """Compiled graph v9.3: 18 nodes, 11 LLM calls across 4 stages.

    Stage 1 (6):  repository_connection → repository_scan →
                  technology_detection → architecture_detection →
                  deployment_detection → domain_detection
    Stage 2 (4):  coverage_inference → pattern_inference →
                  pipeline_augmentation → job_reasoning
    Stage 3 (5):  workflow_generation → workflow_validation →
                  workflow_repair (dormant) →
                  github_branch_creation → pull_request_creation
    Stage 4 (3):  security_analysis → recommendation_generation →
                  response_formatter
    """
    workflow = StateGraph(PipelineEngineerState)

    workflow.add_node("repository_connection", repository_connection_node)
    workflow.add_node("repository_scan", repository_scan_node)
    workflow.add_node("technology_detection", technology_detection_node)
    workflow.add_node("architecture_detection", architecture_detection_node)
    workflow.add_node("deployment_detection", deployment_detection_node)
    workflow.add_node("domain_detection", domain_detection_node)

    workflow.add_node("coverage_inference", coverage_inference_node)
    workflow.add_node("pattern_inference", pattern_inference_node)
    workflow.add_node("pipeline_augmentation", pipeline_augmentation_node)
    workflow.add_node("job_reasoning", job_reasoning_node)

    workflow.add_node("workflow_generation", workflow_generator_node)
    workflow.add_node("workflow_validation", workflow_validator_node)
    workflow.add_node("workflow_repair", workflow_repair_node)
    workflow.add_node("github_branch_creation", github_branch_creation_node)
    workflow.add_node("pull_request_creation", pull_request_creation_node)

    workflow.add_node("security_analysis", security_analyzer_node)
    workflow.add_node("recommendation_generation", recommendation_gen_node)
    workflow.add_node("response_formatter", response_formatter_node)

    workflow.set_entry_point("repository_connection")

    workflow.add_edge("repository_connection", "repository_scan")
    workflow.add_edge("repository_scan", "technology_detection")
    workflow.add_edge("technology_detection", "architecture_detection")
    workflow.add_edge("architecture_detection", "deployment_detection")
    workflow.add_edge("deployment_detection", "domain_detection")

    workflow.add_edge("domain_detection", "coverage_inference")
    workflow.add_edge("coverage_inference", "pattern_inference")
    workflow.add_edge("pattern_inference", "pipeline_augmentation")
    workflow.add_edge("pipeline_augmentation", "job_reasoning")

    workflow.add_edge("job_reasoning", "workflow_generation")
    workflow.add_edge("workflow_generation", "workflow_validation")

    workflow.add_conditional_edges(
        "workflow_validation", route_validation, VALIDATION_ROUTES,
    )

    workflow.add_edge("workflow_repair", "github_branch_creation")
    workflow.add_edge("github_branch_creation", "pull_request_creation")

    workflow.add_edge("pull_request_creation", "security_analysis")
    workflow.add_edge("security_analysis", "recommendation_generation")
    workflow.add_edge("recommendation_generation", "response_formatter")
    workflow.add_edge("response_formatter", END)

    return workflow.compile()


pipeline_graph = build_pipeline_graph()
