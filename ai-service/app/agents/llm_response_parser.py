"""Robust LLM response parser for JSON objects and arrays.

Some LLM providers (notably OpenCode Go / minimax-m3) prepend a
`<think>...</think>` reasoning block before the actual JSON payload,
and may also wrap the answer in markdown code fences. This module
strips both wrappers and falls back to regex extraction when the
JSON cannot be parsed as-is.

Used by every LangGraph node that consumes LLM output so the entire
pipeline is robust to model-version changes.
"""

from __future__ import annotations

import json
import re
from typing import Any


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.MULTILINE)


def _strip_wrappers(content: str) -> str:
    """Remove <think> tags and ```json fences from the LLM response."""
    content = (content or "").strip()
    content = _THINK_RE.sub("", content)
    if content.startswith("```"):
        # Strip leading ```json or ``` line.
        first_nl = content.find("\n")
        if first_nl > 0:
            content = content[first_nl + 1:]
        # Strip trailing ``` line.
        if content.endswith("```"):
            last_nl = content.rfind("\n")
            if last_nl > 0:
                content = content[:last_nl]
    return content.strip()


def parse_llm_json_object(content: str) -> dict[str, Any] | None:
    """Extract a single JSON object from the LLM response.

    Returns the parsed dict, or None if no object could be found.
    Order of attempts:
      1. Strip wrappers and parse directly.
      2. Find the first balanced {...} block and parse it.
      3. Find the first balanced {...} block via brace counting and parse.
    """
    cleaned = _strip_wrappers(content or "")
    if cleaned:
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    # Regex fallbacks
    match = re.search(r"\{[\s\S]*\}", cleaned, flags=re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            # Brace-counted scan in case the regex over-matched.
            depth = 0
            start = -1
            for i, ch in enumerate(candidate):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            parsed = json.loads(candidate[start:i + 1])
                            if isinstance(parsed, dict):
                                return parsed
                        except (json.JSONDecodeError, ValueError):
                            continue
    return None


def parse_llm_json_array(content: str) -> list[Any] | None:
    """Extract a JSON array from the LLM response.

    Returns the parsed list, or None if no array could be found.
    """
    cleaned = _strip_wrappers(content or "")
    if cleaned:
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    match = re.search(r"\[[\s\S]*\]", cleaned, flags=re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            # Try brace counting
            depth = 0
            start = -1
            for i, ch in enumerate(candidate):
                if ch == "[":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            parsed = json.loads(candidate[start:i + 1])
                            if isinstance(parsed, list):
                                return parsed
                        except (json.JSONDecodeError, ValueError):
                            continue
    return None
