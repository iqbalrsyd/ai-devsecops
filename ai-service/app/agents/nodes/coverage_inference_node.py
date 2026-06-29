"""Node 7: coverage_inference (LLM #5, hybrid).

Maps the repository context to the 15 security coverages defined in
`coverage_library.COVERAGES`. The LLM is asked to mark each coverage
applicable or not with a concrete reason; a deterministic fallback
(`_fallback_coverages_from_heuristic`) marks coverages applicable when
the heuristic score is at least 1.0.

Spec: struktur-v9.md §Node 7.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.coverage_library import COVERAGES
from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


COVERAGE_INFERENCE_PROMPT = """You are a Security Coverage Inference Engine.

Given the repository context, determine which security coverages apply.

## Repository Context

Architecture: {architecture}
Framework: {framework}
Deployment: {deployment}
Detected Domain: {domain} (confidence: {domain_confidence})
Business Features: {features}
Libraries (top 30): {libraries}
Entities (top 20): {entities}
Routes (top 20): {routes}

## Available Security Coverages

{coverage_library}

## Heuristic Scores (from deterministic signal matching)

{heuristic_scores}

## Task

For each coverage, decide:
1. Is it applicable to this repository?
2. Why (cite concrete signals: library, entity, route, deployment)?

Be strict. Only mark a coverage as applicable if you can cite a clear
signal. When in doubt, mark it as not applicable.

## Return ONLY valid JSON

{{
  "security_coverages": [
    {{
      "id": "<coverage_id>",
      "applicable": true,
      "reason": "concrete evidence (e.g. 'Stripe SDK in dependencies, /checkout route detected')"
    }},
    {{
      "id": "<coverage_id>",
      "applicable": false,
      "reason": "no signal (e.g. 'no MQTT library, no sensor entity')"
    }}
  ]
}}
"""


def _format_coverage_library() -> str:
    lines = []
    for cov in COVERAGES:
        signals = cov.get("signals") or {}
        sig_parts = []
        for key, values in signals.items():
            if isinstance(values, list):
                sig_parts.append(f"{key}={','.join(values[:6])}")
        sig_str = "; ".join(sig_parts) if sig_parts else "(no fixed signals)"
        lines.append(f"- {cov['id']}: {cov['description']} [{sig_str}]")
    return "\n".join(lines)


def _score_coverage_heuristic(state: PipelineEngineerState) -> dict[str, float]:
    libraries = {x.lower() for x in _extract_libraries(state)}
    entities = {x.lower() for x in _extract_entities(state)}
    routes = {x.lower() for x in _extract_routes(state)}
    deployment = state.get("detected_deployment") or {}
    architecture = state.get("detected_architecture_type") or (
        (state.get("detected_architecture") or {}).get("architecture_type")
        if isinstance(state.get("detected_architecture"), dict)
        else None
    )
    domain = state.get("detected_domain")

    scores: dict[str, float] = {}
    for cov in COVERAGES:
        sig = cov.get("signals") or {}
        s = 0.0
        for lib in sig.get("libraries", []):
            if lib.lower() in libraries:
                s += 2.0
        for entity in sig.get("entities", []):
            if entity.lower() in entities:
                s += 1.5
        for route in sig.get("routes", []):
            if any(route.lower() in r for r in routes):
                s += 1.0
        if "deployment" in sig:
            for dep_key in sig["deployment"]:
                if deployment.get(dep_key):
                    s += 2.0
        if "architectures" in sig and architecture:
            if architecture in sig["architectures"]:
                s += 2.0
        if "package_managers" in sig:
            pm = (state.get("detected_technologies") or {}).get("package_manager")
            if pm and pm in sig["package_managers"]:
                s += 1.5
        if "domain" in sig and domain:
            if domain in sig["domain"]:
                s += 1.0
        scores[cov["id"]] = s
    return scores


def _extract_libraries(state: PipelineEngineerState) -> list[str]:
    files = state.get("repository_files") or {}
    libs: set[str] = set()
    for path, content in files.items():
        if not isinstance(content, str):
            continue
        if "package.json" in path:
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                deps = data.get(section) or {}
                if isinstance(deps, dict):
                    libs.update(deps.keys())
    return sorted(libs)[:30]


def _extract_entities(state: PipelineEngineerState) -> list[str]:
    src = state.get("source_files") or []
    entities: set[str] = set()
    pats = [
        re.compile(r"model\s*\(\s*[\"'](\w+)[\"']", re.IGNORECASE),
        re.compile(r"@Entity\s*\(\s*[\"']?(\w+)", re.IGNORECASE),
        re.compile(r"Schema\s*\(\s*[\"']?(\w+)", re.IGNORECASE),
    ]
    for entry in src:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        for p in pats:
            for m in p.finditer(content):
                entities.add(m.group(1))
                if len(entities) >= 20:
                    return sorted(entities)[:20]
    return sorted(entities)[:20]


def _extract_routes(state: PipelineEngineerState) -> list[str]:
    src = state.get("source_files") or []
    routes: set[str] = set()
    pats = [
        re.compile(r'@(?:Get|Post|Put|Delete|Patch)\(["\']([^"\']+)', re.IGNORECASE),
        re.compile(r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)', re.IGNORECASE),
        re.compile(r'@app\.route\(["\']([^"\']+)', re.IGNORECASE),
    ]
    for entry in src:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        for p in pats:
            for m in p.finditer(content):
                routes.add(m.group(1))
                if len(routes) >= 20:
                    return sorted(routes)[:20]
    return sorted(routes)[:20]


def _parse_llm_json(content: str) -> Any:
    from app.agents.llm_response_parser import (
        parse_llm_json_object,
        parse_llm_json_array,
    )
    obj = parse_llm_json_object(content)
    if obj is not None:
        return obj
    return parse_llm_json_array(content)


def _fallback_coverages_from_heuristic(scores: dict[str, float]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cov in COVERAGES:
        s = scores.get(cov["id"], 0.0)
        applicable = s >= 1.0
        out.append({
            "id": cov["id"],
            "applicable": applicable,
            "reason": (
                f"heuristic score {round(s, 2)} for {cov['id']}"
                if applicable
                else f"no signal for {cov['id']} (score {round(s, 2)})"
            ),
            "confidence": round(min(1.0, s * 0.2 + 0.5), 3) if applicable else 0.0,
        })
    return out


def coverage_inference_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    technologies = state.get("detected_technologies") or {}
    architecture = (
        state.get("detected_architecture_type")
        or (state.get("detected_architecture") or {}).get("architecture_type")
        or "monolithic"
    )
    deployment = state.get("detected_deployment") or {}

    libraries = _extract_libraries(state)
    entities = _extract_entities(state)
    routes = _extract_routes(state)
    heuristic_scores = _score_coverage_heuristic(state)

    llm_coverages: list[dict[str, Any]] = []
    llm_reasoning: str | None = None

    try:
        llm = get_llm()
        prompt = COVERAGE_INFERENCE_PROMPT.format(
            architecture=architecture,
            framework=", ".join(technologies.get("frameworks", []) or []) or "(none)",
            deployment=json.dumps(deployment),
            domain=state.get("detected_domain") or "general",
            domain_confidence=state.get("domain_confidence") or 0.0,
            features=json.dumps(state.get("features") or []),
            libraries=json.dumps(libraries),
            entities=json.dumps(entities),
            routes=json.dumps(routes),
            coverage_library=_format_coverage_library(),
            heuristic_scores=json.dumps({k: round(v, 2) for k, v in heuristic_scores.items()}),
        )
        response = llm.invoke(prompt)
        parsed = _parse_llm_json(response.content)
        if isinstance(parsed, dict):
            llm_coverages = parsed.get("security_coverages") or []
            llm_reasoning = parsed.get("reasoning")
    except Exception as e:
        state.setdefault("warnings", []).append(f"coverage_inference LLM failed: {e}")

    if not llm_coverages:
        final_coverages = _fallback_coverages_from_heuristic(heuristic_scores)
    else:
        by_id = {c["id"]: c for c in llm_coverages}
        final_coverages = []
        for cov in COVERAGES:
            entry = by_id.get(cov["id"], {})
            applicable = bool(entry.get("applicable", False))
            reason = entry.get("reason") or f"LLM did not produce a reason for {cov['id']}"
            confidence = entry.get("confidence")
            if confidence is None:
                confidence = round(
                    min(1.0, heuristic_scores.get(cov["id"], 0.0) * 0.2 + 0.5)
                    if applicable else 0.0, 3,
                )
            final_coverages.append({
                "id": cov["id"],
                "applicable": applicable,
                "reason": reason,
                "confidence": round(float(confidence), 3),
            })

    seen = {c["id"] for c in final_coverages}
    for cov in COVERAGES:
        if cov["id"] not in seen:
            final_coverages.append({
                "id": cov["id"],
                "applicable": False,
                "reason": f"missing from LLM output for {cov['id']}",
                "confidence": 0.0,
            })

    state["security_coverages"] = final_coverages
    state["coverage_inference_reasoning"] = llm_reasoning or (
        f"heuristic-only; top score {round(max(heuristic_scores.values(), default=0), 2)}"
    )
    applicable_count = sum(1 for c in final_coverages if c.get("applicable"))
    state.setdefault("warnings", []).append(
        f"coverage_inference: {applicable_count}/15 coverages applicable"
    )
    return state
