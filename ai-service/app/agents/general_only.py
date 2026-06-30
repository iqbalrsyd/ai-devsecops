"""Toggle: skip custom-domain jobs and emit only standard jobs.

Read at request time by `pipeline_service` and stored in
`PipelineEngineerState["general_only"]`. The `workflow_generator`
node honours the flag by skipping the custom-job builder entirely
when it is True.

Use cases
---------

1. Operators want to test the standard pipeline (lint, test, sast,
   secret-scan, dependency-scan, container-scan) on a repo before
   adding any domain-specific jobs.
2. The domain classifier falls back to "general" because the
   heuristic veto rejected the LLM's domain pick. In that case the
   custom-job builder is skipped automatically via the
   `domain_confidence < 0.5` path in `_build_workflow_yaml`. The
   env-var path is the manual override.

The env var name is `AI_DEVSECOPS_GENERAL_ONLY`. Truthy values:
`1`, `true`, `yes` (case-insensitive).
"""
from __future__ import annotations

import os

_ENV_VAR = "AI_DEVSECOPS_GENERAL_ONLY"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def is_general_only() -> bool:
    """Return True when the user wants to skip custom jobs."""
    val = os.environ.get(_ENV_VAR, "").strip().lower()
    return val in _TRUTHY


__all__ = ["is_general_only", "_ENV_VAR"]
