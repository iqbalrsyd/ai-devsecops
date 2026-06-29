"""Robust JSON extraction utilities for LLM responses.

The LLM may return:
  - Plain JSON
  - JSON wrapped in ```json ... ``` or ``` ... ```
  - JSON embedded in prose ("Here is the JSON: {...} Hope that helps!")
  - Empty or non-JSON responses (returns empty dict/list)
  - Truncated JSON
"""
from __future__ import annotations

import json
from typing import Any


def extract_json(content: str) -> Any:
    """Extract a JSON object/array from arbitrary LLM response text.

    Robust against:
      - ```````json...````` code fences
      - `<think>...</think>` reasoning blocks (OpenCode Go / minimax-m3)
      - Prose surrounding the JSON payload
      - Slightly malformed JSON (e.g. trailing commas — see note)

    Returns:
        dict | list: parsed JSON, or {} if no parseable JSON is found.
    """
    if not content or not content.strip():
        return {}

    text = content.strip()

    # Strip <think>...</think> blocks (OpenCode Go / minimax-m3 prepend
    # these before the actual JSON payload).
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    if not text or text[0] not in "{[":
        start_obj = text.find("{")
        start_arr = text.find("[")
        if start_obj == -1 and start_arr == -1:
            return {}
        if start_obj == -1:
            start = start_arr
        elif start_arr == -1:
            start = start_obj
        else:
            start = min(start_obj, start_arr)
        text = text[start:]

    if text[-1] not in "}]":
        end_obj = text.rfind("}")
        end_arr = text.rfind("]")
        if end_obj == -1 and end_arr == -1:
            return {}
        if end_obj == -1:
            end = end_arr
        elif end_arr == -1:
            end = end_obj
        else:
            end = max(end_obj, end_arr)
        text = text[: end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def extract_json_object(content: str) -> dict:
    """Extract a JSON object (dict) from LLM response text.

    If the response parses to a list, returns {}. This is the most
    common case for structured-output prompts that expect a single
    record.
    """
    result = extract_json(content)
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0]
    return {}
