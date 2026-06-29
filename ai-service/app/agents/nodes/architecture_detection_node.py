import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm
from app.agents.llm_response_parser import parse_llm_json_object

ARCHITECTURE_DETECTION_PROMPT = """You are a DevSecOps engineer analyzing application architecture.

The supported architectures have been reduced to TWO (skripsi Bab 3, revisi 3-domain & 2-architecture):
- "monolithic"       (single deployable app, all layers in one process)
- "modular_monolith" (FE/BE split OR multiple modules deployed together
                      with shared database — also called frontend_backend)

DO NOT return "microservices", "serverless", or "library". Map every
repository into ONE of the two values above.

Given the repository structure and detected technologies, determine the
application architecture with confidence scores.

Repository structure:
{structure}

Detected technologies:
{technologies}

Analyze the architecture and return JSON with:
- architecture_type: one of "monolithic", "modular_monolith"
- architecture_confidence: confidence score 0.0-1.0 based on evidence
- architecture_reason: explanation of why this architecture was chosen
- service_count: number of distinct services/applications detected (integer, null if unknown)
- service_names: list of service names if modular_monolith detected, null otherwise
- has_api_gateway: boolean
- has_message_queue: boolean
- has_database_config: boolean
- is_containerized: boolean
- has_shared_libraries: boolean (true if multiple services share common libraries/packages)

Key distinction for modular_monolith:
- Multiple services/directories exist but share database or are deployed together
- Example: backend/api + frontend + worker all in one repo with shared DB
- Single deploy unit, NO service mesh, NO independent deployment

Return ONLY valid JSON. No markdown.
"""


def _strip_think_tags(content: str) -> str:
    """Remove <think>...</think> reasoning blocks some LLM providers
    (notably OpenCode Go / minimax-m3) prepend to their reply before
    the actual JSON payload. Falls through unchanged when no tags.
    """
    import re as _re
    return _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()


def architecture_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    structure = state.get("repository_structure", [])
    technologies = state.get("detected_technologies", {})

    prompt = ARCHITECTURE_DETECTION_PROMPT.format(
        structure=json.dumps(structure, indent=2)[:3000],
        technologies=json.dumps(technologies, indent=2),
    )

    llm = get_llm()
    try:
        response = llm.invoke(prompt)
        architecture = parse_llm_json_object(response.content)

        architecture.setdefault("architecture_confidence", 0.8)
        architecture.setdefault("architecture_reason", "Based on repository structure analysis")
        architecture.setdefault("has_api_gateway", False)
        architecture.setdefault("has_message_queue", False)
        architecture.setdefault("has_database_config", False)
        architecture.setdefault("is_containerized", False)
        architecture.setdefault("has_shared_libraries", False)
        architecture.setdefault("service_names", [])

        state["detected_architecture"] = architecture
        raw_arch = architecture.get("architecture_type", "monolithic")
        # Normalise: frontend_backend and any other variants collapse
        # into modular_monolith (one of the two supported arch types).
        if raw_arch in ("modular_monolith", "frontend_backend"):
            normalized_arch = "modular_monolith"
        else:
            normalized_arch = "monolithic"
        state["detected_architecture_type"] = normalized_arch

        state["detected_architecture_confidence"] = architecture.get("architecture_confidence", 0.8)
        state["detected_architecture_reason"] = architecture.get("architecture_reason", "")

    except json.JSONDecodeError as e:
        state["errors"].append(f"Architecture detection JSON parse failed: {e}")
        state["error_stage"] = "architecture_detection"
    except Exception as e:
        state["errors"].append(f"Architecture detection failed: {e}")
        state["error_stage"] = "architecture_detection"

    return state