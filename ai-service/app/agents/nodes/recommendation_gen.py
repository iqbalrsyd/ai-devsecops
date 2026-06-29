from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm

RECOMMENDATION_PROMPT = """You are a DevSecOps engineer. Given the following security findings and risk assessment, generate actionable fix recommendations.

Findings:
{findings}

Risk Score: {risk_score}

For each finding, provide:
1. A clear code-level fix recommendation
2. A before/after code example if applicable
3. Package update command if it's a dependency issue

Return a JSON object with:
- recommendations: list of recommendation strings
- fix_examples: list of {{"finding_type": str, "before": str, "after": str}}

Return ONLY valid JSON.
"""


def recommendation_gen_node(state: PipelineEngineerState) -> PipelineEngineerState:
    findings = state.get("findings", [])
    risk_score = state.get("risk_score", 0)

    prompt = RECOMMENDATION_PROMPT.format(
        findings=str(findings)[:6000], risk_score=risk_score
    )
    llm = get_llm()

    try:
        response = llm.invoke(prompt)
        import json
        import re

        content = (response.content or "").strip()

        # Try direct JSON parse first
        result = None
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from a code block (```json ... ```)
            md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if md_match:
                try:
                    result = json.loads(md_match.group(1).strip())
                except json.JSONDecodeError:
                    pass
        if result is None:
            # Last resort: extract the first balanced {...} block
            brace_match = re.search(r"\{.*\}", content, re.DOTALL)
            if brace_match:
                try:
                    result = json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not isinstance(result, dict):
            raise ValueError("LLM response is not a JSON object")

        state["recommendations"] = result.get("recommendations", [])
        if state.get("report") is None:
            state["report"] = {}
        state["report"]["fix_examples"] = result.get("fix_examples", [])
    except Exception as e:
        # Non-fatal: the OWASP risk score and findings are still
        # valid; recommendations are a nice-to-have. Persist a soft
        # error and a generic recommendation so the dashboard still
        # shows something useful.
        state["errors"].append(f"Recommendation generation failed: {type(e).__name__}: {e}")
        if not state.get("recommendations"):
            state["recommendations"] = ["Review findings manually and apply appropriate fixes."]

    return state