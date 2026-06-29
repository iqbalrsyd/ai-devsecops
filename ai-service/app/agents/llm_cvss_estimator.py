"""LLM-driven CVSS 3.1 estimator (Bab 5.13.3 fallback layer).

The deterministic 3-tier lookup in `cvss_mapper.py` resolves roughly
80% of the findings via rule_id, type, or severity. The remaining
20% (custom Semgrep rules, novel CVEs, or findings uploaded by a
scanner that does not provide CWE) need a language-model judgment
call.

The LLM sees a *summary* of the SARIF file (`rules` block + `results`
block) and the list of findings that need scoring. It returns a JSON
array with one entry per input finding so the order is preserved
and the caller can zip them back together.

The LLM is instructed to be conservative (it never invents a higher
score than the rule's documented severity) and to fall back to
5.0/Medium when it cannot determine a CVSS base score.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.llm_service import get_llm


CVSS_ESTIMATOR_PROMPT = """You are a security analyst specialising in CVSS 3.1 base scoring.

You will receive:
  1. A SARIF summary (rules + first 20 results) from a security scan.
  2. A list of findings that need a CVSS base score (in order).

For each finding, decide the CVSS 3.1 base score from the rule's
description, the result's message, and the file context. Use the
official CVSS 3.1 specification:
  https://www.first.org/cvss/v3.1/specification-document

Scoring bands (use as guidance):
  - 9.0-10.0 = Critical (RCE, SQLi, auth bypass, exposed secrets)
  - 7.0-8.9   = High (XSS, SSRF, deserialisation, weak crypto)
  - 4.0-6.9   = Medium (CSRF, info disclosure, insecure config)
  - 0.1-3.9   = Low (verbose logging, missing best-practice headers)
  - 0.0       = Informational only

Constraints:
  - Be conservative. If the rule's documented severity is "warning"
    (medium), do not invent a Critical score.
  - If you cannot decide, default to 5.0 / Medium.
  - Output MUST be valid JSON (no markdown, no commentary).
  - The response must have exactly the same number of items as the
    findings list, in the same order.

Output format (JSON array):
[
  {{
    "rule_id": "<rule_id of the finding>",
    "cvss_score": 7.5,
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
    "cvss_severity": "High",
    "rationale": "one short sentence explaining the score"
  }}
]

## SARIF summary
```
{sarif_summary}
```

## Findings needing CVSS (in order)
{findings}
"""


def _summarise_sarif(sarif_text: str, max_chars: int = 12000) -> str:
    """Trim the SARIF text to the bits the LLM actually needs.

    We keep the `rules` block (descriptions) and the first 20 `results`
    (file/line/message). Anything else (artifacts, properties, fixes)
    is dropped because it bloats the prompt without changing the
    CVSS decision.
    """
    if not sarif_text:
        return ""
    try:
        parsed = json.loads(sarif_text)
    except (json.JSONDecodeError, ValueError):
        return sarif_text[:max_chars]

    runs = parsed.get("runs") or []
    rules: list[dict] = []
    results: list[dict] = []

    for run in runs:
        tool = (run.get("tool") or {}).get("driver") or {}
        rules.extend(tool.get("rules") or [])
        results.extend(run.get("results") or [])

    trimmed = {
        "rules": rules[:50],
        "results": results[:20],
    }
    text = json.dumps(trimmed, indent=2)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _parse_llm_json(text: str) -> list[dict[str, Any]]:
    """Parse a JSON array from the LLM response, tolerating code fences."""
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("\n", 1)
        text = parts[1] if len(parts) > 1 else ""
        if text.endswith("```"):
            text = text[:-3]
    text = text.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Try to extract a list with regex as a last resort.
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _format_findings_for_prompt(findings: list[dict[str, Any]]) -> str:
    """Compact per-finding payload for the prompt (id + rule_id + file + message)."""
    lines: list[str] = []
    for i, f in enumerate(findings):
        rule_id = f.get("rule_id") or f.get("type") or "?"
        file_loc = f.get("file_location") or f.get("file") or "?"
        line = f.get("line") or ""
        evidence = (f.get("evidence") or f.get("message") or "")[:200]
        lines.append(
            f"{i+1}. rule_id={rule_id} | file={file_loc}:{line} | evidence={evidence}"
        )
    return "\n".join(lines) if lines else "(none)"


def llm_estimate_cvss_for_findings(
    sarif_text: str,
    findings: list[dict[str, Any]],
    max_findings: int = 10,
) -> list[dict[str, Any]]:
    """Use the LLM to estimate a CVSS 3.1 score for each finding.

    Returns a list (same order as `findings`) with the LLM-estimated
    fields. The caller should merge these back into the original
    finding dicts.
    """
    if not findings:
        return []
    findings = findings[:max_findings]
    sarif_summary = _summarise_sarif(sarif_text)
    findings_blob = _format_findings_for_prompt(findings)

    try:
        llm = get_llm()
    except Exception as e:
        print(f"[llm_cvss_estimator] LLM init failed: {e}")
        return []

    try:
        prompt = CVSS_ESTIMATOR_PROMPT.format(
            sarif_summary=sarif_summary,
            findings=findings_blob,
        )
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"[llm_cvss_estimator] LLM call failed: {e}")
        return []

    parsed = _parse_llm_json(raw)
    if len(parsed) < len(findings):
        # Pad with empty dicts so zip() in the caller is safe.
        parsed.extend({} for _ in range(len(findings) - len(parsed)))
    parsed = parsed[:len(findings)]

    # Fallback: for any finding where the LLM did not return a
    # confident CVSS, run the deterministic 3-tier lookup
    # (RULE_CVSS_MAP → TYPE_CVSS_FALLBACK → SEVERITY_DEFAULT) so
    # the dashboard never has to fall back to 5.0/Medium just
    # because the LLM was unsure.
    from app.agents.cvss_mapper import score_finding

    for i, original in enumerate(findings):
        est = parsed[i] or {}
        score = est.get("cvss_score")
        vector = est.get("cvss_vector")
        band = est.get("cvss_severity")
        if not isinstance(score, (int, float)) or not vector or not band:
            manual = score_finding(dict(original))
            # Merge: keep LLM rationale (if any), use the manual
            # CVSS score / vector / band because it is the spec.
            if not isinstance(score, (int, float)):
                score = manual.get("cvss_score")
            if not vector:
                vector = manual.get("cvss_vector")
            if not band:
                band = manual.get("cvss_severity")
            parsed[i] = {
                **est,
                "cvss_score": score,
                "cvss_vector": vector,
                "cvss_severity": band,
                "rationale": (est.get("rationale") or "manual mapping"),
            }
        else:
            parsed[i] = est

    return parsed
