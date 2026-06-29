"""Pattern Inference Node (K2.3 - struktur-v9.1).

Generate adaptive Semgrep rules tailored to a specific repository's
patterns using LLM. Complements the static rule library in
`app/agents/semgrep_rules/` (which is generic and framework-agnostic).

Reads:
  - detected_technologies (language, framework, libraries)
  - detected_domain
  - features
  - security_coverages (applicable ones)
  - source_files (sample for LLM context)
  - existing workflow YAMLs

Writes:
  - state.ai_generated_rules (list of validated Semgrep rule dicts)
  - state.pattern_inference_reasoning
  - state.pattern_inference_valid_count
"""
import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


PATTERN_INFERENCE_PROMPT = """You are a Semgrep rule author specialising in
{domain} web application security.

Generate adaptive Semgrep rules tailored to THIS repository's patterns.
The static rules already cover generic OWASP API + domain patterns, so
focus on project-specific patterns that the static library cannot catch.

## Repository Context

Language: {language}
Frameworks: {frameworks}
Domain: {domain}
Sub-type: {sub_type}
Package Manager: {package_manager}
Architecture: {architecture}

## Business Features (from domain_detection)

{features}

## Applicable Security Coverages

{coverages}

## Sample Routes (extracted from source)

{routes_sample}

## Sample Source Code Snippets

{source_sample}

## Static Rules Already Committed (do NOT duplicate these)

{static_rules}

## General Knowledge Base (cross-domain, applicable to all webapps)

{general_knowledge_base}

## Domain Knowledge Base (specific to this detected domain)

{domain_knowledge_base}

## Task

Generate adaptive Semgrep rules that target THIS repository's
project-specific patterns. The rules should catch vulnerabilities
that the static library cannot, such as:

1. **Project-specific URL routing patterns** (e.g. NestJS decorators,
   FastAPI path parameters, Express middleware chains)
2. **Custom authentication/authorization logic** (e.g. custom JWT
   verification, custom role checks, custom session handling)
3. **Project-specific business logic vulnerabilities** (e.g. custom
   pricing logic, custom discount calculations, custom payment
   processing)
4. **Library-specific misuse patterns** (e.g. incorrect usage of
   Stripe SDK, Sequelize transactions, Mongoose queries)
5. **Domain-specific data flow** (e.g. PHI in error messages, PII
   in logs, payment data in cookies)

Each rule MUST have:
- id: `ai-{coverage_id}-{slug}` (e.g. `ai-payment-stripe-charge-no-idempotency`)
- message: clear description of what the rule detects
- severity: ERROR | WARNING | INFO
- languages: list of languages
- patterns: Semgrep pattern syntax (pattern-either / pattern / pattern-regex)
- metadata.cwe: CWE id
- metadata.owasp: OWASP category
- metadata.ai-devsecops-coverage: which security coverage this rule supports
- metadata.ai-devsecops-reasoning: 1-sentence explanation of why this
  rule is needed for this repo

## Constraints

- DO NOT duplicate any rule from the static library
- DO NOT invent vulnerabilities that don't apply to this repo
- Each rule MUST be syntactically valid Semgrep YAML
- Pattern MUST match real code in the repository (when possible)
- Be conservative — better to generate 3 good rules than 10 noisy ones

## Return ONLY valid JSON

{{
  "ai_generated_rules": [
    {{
      "id": "ai-{coverage}-{slug}",
      "message": "...",
      "severity": "ERROR",
      "languages": ["javascript"],
      "patterns": [
        {{"pattern": "..."}}
      ],
      "metadata": {{
        "cwe": "CWE-XXX",
        "owasp": "A0X:2021",
        "ai-devsecops-coverage": "...",
        "ai-devsecops-reasoning": "..."
      }}
    }}
  ]
}}
"""


# ── Structural Validation ──────────────────────────────────────────────
# Lightweight validation: checks required fields, ID format, severity
# valid, languages non-empty, patterns non-empty. Does NOT run
# `semgrep --validate` (would add Docker overhead).

REQUIRED_FIELDS = {"id", "message", "severity", "languages", "patterns"}
VALID_SEVERITIES = {"ERROR", "WARNING", "INFO", "INFORMATION"}
VALID_ID_PATTERN = re.compile(r"^ai-[a-z_]+-[a-z0-9-]+$")


def _validate_ai_generated_rule(rule: dict) -> bool:
    """Structural validation for an AI-generated Semgrep rule.

    Returns True if the rule is valid, False otherwise. Logs the
    specific reason for failure via the `reason` parameter pattern.
    """
    if not isinstance(rule, dict):
        return False
    if not REQUIRED_FIELDS.issubset(rule.keys()):
        return False
    rule_id = rule.get("id", "")
    if not isinstance(rule_id, str) or not VALID_ID_PATTERN.match(rule_id):
        return False
    severity = rule.get("severity", "").upper()
    if severity not in VALID_SEVERITIES:
        return False
    languages = rule.get("languages", [])
    if not isinstance(languages, list) or len(languages) == 0:
        return False
    patterns = rule.get("patterns", [])
    if not isinstance(patterns, list) or len(patterns) == 0:
        return False
    message = rule.get("message", "")
    if not isinstance(message, str) or len(message) < 10:
        return False
    return True


def _parse_llm_response(content: str) -> dict:
    from app.agents.llm_response_parser import (
        parse_llm_json_object, parse_llm_json_array,
    )
    obj = parse_llm_json_object(content)
    if obj is not None:
        return obj
    arr = parse_llm_json_array(content)
    return arr if arr is not None else {}


def _extract_sample_routes(source_files: list, max_n: int = 20) -> list[str]:
    """Extract sample route patterns from source files for LLM context."""
    routes: list[str] = []
    route_pattern = re.compile(
        r'@(?:Get|Post|Put|Delete|Patch)\(["\']([^"\']+)',
        re.IGNORECASE,
    )
    route_pattern2 = re.compile(
        r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)',
        re.IGNORECASE,
    )
    for entry in source_files or []:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        if not content:
            continue
        for pat in (route_pattern, route_pattern2):
            for m in pat.finditer(content):
                route = m.group(1)
                if route not in routes:
                    routes.append(route)
                if len(routes) >= max_n:
                    return routes
    return routes


def _extract_source_sample(source_files: list, max_chars: int = 8000) -> str:
    """Extract a representative sample of source code for LLM context.

    Prioritises files likely to contain security-relevant patterns:
    - routes/, controllers/, handlers/, app.py, main.py, server.js
    - middleware/, auth.py
    - models/, services/
    """
    if not source_files:
        return "(no source files available)"

    priority_keywords = [
        "route", "controller", "handler", "auth", "middleware",
        "model", "service", "server", "app", "main", "index",
        "payment", "checkout", "order", "user", "session",
    ]

    scored: list[tuple[float, str]] = []
    seen_paths: set[str] = set()
    for entry in source_files:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or entry.get("name") or "").lower()
        content = entry.get("content", "")
        if not content or path in seen_paths:
            continue
        seen_paths.add(path)
        score = 0.0
        for kw in priority_keywords:
            if kw in path:
                score += 2.0
        if path.endswith((".js", ".ts")):
            score += 1.0
        if "test" in path or "spec" in path:
            score -= 5.0
        if len(content) > 500 and len(content) < 5000:
            score += 1.0
        snippet = f"// {path}\n{content[:1500]}"
        scored.append((score, snippet))

    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    total = 0
    for _, snippet in scored:
        if total + len(snippet) > max_chars:
            out.append(snippet[: max_chars - total] + "\n// ... (truncated)")
            break
        out.append(snippet)
        total += len(snippet)
    return "\n\n".join(out) if out else "(no source files available)"


def _list_static_rule_ids(detected_domain: str | None) -> list[str]:
    """List static rule IDs so LLM knows what NOT to duplicate."""
    from app.agents.nodes.workflow_generator import _semgrep_rules_for_domain
    import os
    import yaml as _yaml

    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "semgrep_rules",
    )
    files = _semgrep_rules_for_domain(detected_domain)
    ids: list[str] = []
    for fname in files:
        fpath = os.path.join(rules_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath) as f:
                doc = _yaml.safe_load(f) or {}
        except Exception:
            continue
        rules = doc.get("rules", []) if isinstance(doc, dict) else []
        for r in rules:
            if isinstance(r, dict) and r.get("id"):
                ids.append(r["id"])
    return ids


def _load_knowledge_base(filename: str) -> dict:
    """Load a knowledge base YAML file.

    Returns empty dict on any failure (missing file, parse error).
    Two KB files are loaded in K2.3:
      - general_knowledge_base.yml (cross-domain, always)
      - domain_knowledge_base.yml (per-domain, filtered by detected_domain)
    """
    import os
    import yaml as _yaml

    kb_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "semgrep_rules",
        filename,
    )
    try:
        with open(kb_path) as f:
            return _yaml.safe_load(f) or {}
    except Exception:
        return {}


def _format_kb_for_prompt(kb: dict, domain: str | None) -> str:
    """Render KB to plain text for prompt injection.

    For general KB: render cwe_focus + threats + rule_outlines.
    For domain KB: filter by detected_domain, render that domain's entry.
    Returns a fallback message when KB is empty or domain not found.
    """
    if not kb:
        return "(no KB available — rely on coverage inference + source_sample)"

    lines: list[str] = []

    # General section
    if "cwe_focus" in kb and "rule_outlines" in kb:
        lines.append("Cross-cutting CWE focus (applicable to all webapp domains):")
        for cwe in kb.get("cwe_focus", []):
            lines.append(f"  - {cwe}")
        threats = kb.get("threats", [])
        if threats:
            lines.append("\nCommon threats:")
            for t in threats:
                lines.append(f"  - {t}")
        outlines = kb.get("rule_outlines", [])
        if outlines:
            lines.append("\nRule outline examples (prefix = ai-{coverage}-{slug}):")
            for o in outlines:
                sid = o.get("id_skeleton", "")
                hint = o.get("hint", "")
                if sid:
                    lines.append(f"  - {sid}: {hint}")
        return "\n".join(lines)

    # Domain KB: filter by domain
    domains = kb.get("domains", {})
    if not domain or domain not in domains:
        return "(no domain-specific KB for this repo — rely on general KB + coverage inference)"

    d = domains[domain]
    lines.append(f"Domain: {domain}")
    if d.get("applicable_coverages"):
        lines.append(f"Applicable security coverages: {', '.join(d['applicable_coverages'])}")
    if d.get("cwe_focus"):
        lines.append("\nCWE focus:")
        for cwe in d["cwe_focus"]:
            lines.append(f"  - {cwe}")
    if d.get("threats"):
        lines.append("\nDomain-specific threats:")
        for t in d["threats"]:
            lines.append(f"  - {t}")
    outlines = d.get("rule_outlines", [])
    if outlines:
        lines.append("\nRule outline examples (prefix = ai-{coverage}-{slug}):")
        for o in outlines:
            sid = o.get("id_skeleton", "")
            hint = o.get("hint", "")
            if sid:
                lines.append(f"  - {sid}: {hint}")
    if d.get("frameworks"):
        lines.append(f"\nNotable frameworks: {', '.join(d['frameworks'])}")

    return "\n".join(lines)


def _llm_generate_patterns(signals: dict) -> list[dict]:
    """Call LLM to generate adaptive Semgrep rules."""
    try:
        # Load knowledge bases (general always, domain if applicable)
        general_kb = _load_knowledge_base("general_knowledge_base.yml")
        domain_kb = _load_knowledge_base("domain_knowledge_base.yml")
        detected_domain = signals.get("detected_domain") or "general"

        general_kb_text = _format_kb_for_prompt(general_kb, None)
        domain_kb_text = _format_kb_for_prompt(domain_kb, detected_domain)

        prompt = PATTERN_INFERENCE_PROMPT.format(
            domain=detected_domain,
            language=signals.get("primary_language") or "unknown",
            frameworks=", ".join(signals.get("frameworks", []) or []) or "(none)",
            sub_type=signals.get("sub_type") or "none",
            package_manager=signals.get("package_manager") or "(unknown)",
            architecture=signals.get("architecture_type") or "monolithic",
            features=json.dumps(signals.get("features", [])),
            coverages=json.dumps(signals.get("coverages", [])),
            routes_sample=json.dumps(signals.get("routes_sample", [])),
            source_sample=signals.get("source_sample", "(no source available)"),
            static_rules="\n".join(f"- {rid}" for rid in signals.get("static_rule_ids", [])),
            general_knowledge_base=general_kb_text,
            domain_knowledge_base=domain_kb_text,
        )
        llm = get_llm()
        response = llm.invoke(prompt)
        result = _parse_llm_response(response.content)
        return result.get("ai_generated_rules") or []
    except Exception:
        return []


def _fallback_empty() -> list[dict]:
    """When LLM unavailable or fails, return empty list."""
    return []


def pattern_inference_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """K2.3: Generate adaptive Semgrep rules tailored to this repository.

    Reads:
      - detected_technologies, detected_domain, features
      - security_coverages (applicable ones)
      - source_files

    Writes:
      - state.ai_generated_rules (validated list of rule dicts)
      - state.pattern_inference_reasoning
      - state.pattern_inference_valid_count
    """
    if state.get("errors"):
        print(
            f"[pattern_inference] running with prior errors: "
            f"{state['errors'][:2]}"
        )

    technologies = state.get("detected_technologies") or {}
    coverages = state.get("security_coverages") or []
    applicable = [c for c in coverages if c.get("applicable")]

    # If no coverages applicable, skip pattern generation
    if not applicable:
        state["ai_generated_rules"] = []
        state["pattern_inference_reasoning"] = (
            "No applicable coverages — skipping pattern generation"
        )
        state["pattern_inference_valid_count"] = 0
        return state

    detected_domain = state.get("detected_domain")
    source_files = state.get("source_files") or []

    signals = {
        "primary_language": technologies.get("primary_language"),
        "frameworks": technologies.get("frameworks", []),
        "package_manager": technologies.get("package_manager"),
        "architecture_type": state.get("detected_architecture_type") or "monolithic",
        "detected_domain": detected_domain,
        "sub_type": state.get("domain_sub_type"),
        "features": state.get("features", []),
        "coverages": [{"id": c.get("id"), "reason": c.get("reason", "")} for c in applicable],
        "routes_sample": _extract_sample_routes(source_files),
        "source_sample": _extract_source_sample(source_files),
        "static_rule_ids": _list_static_rule_ids(detected_domain),
    }

    raw_rules = _llm_generate_patterns(signals)
    if not raw_rules:
        raw_rules = _fallback_empty()

    # Validate each rule (structural only)
    validated: list[dict] = []
    rejected_count = 0
    for rule in raw_rules:
        if _validate_ai_generated_rule(rule):
            validated.append(rule)
        else:
            rejected_count += 1

    state["ai_generated_rules"] = validated
    state["pattern_inference_reasoning"] = (
        f"LLM generated {len(raw_rules)} rules, {len(validated)} valid "
        f"({rejected_count} rejected by structural validation). "
        f"Domain: {detected_domain or 'general'}, "
        f"applicable coverages: {len(applicable)}."
    )
    state["pattern_inference_valid_count"] = len(validated)

    return state
