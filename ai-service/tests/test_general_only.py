"""Tests for the AI_DEVSECOPS_GENERAL_ONLY env-var toggle.

When the env var is set, the pipeline skips the AI-generated custom
jobs and emits only the standard set (lint, test, sast, secret-scan,
dependency-scan, container-scan). This is useful for:
  1. Operators testing the standard pipeline in isolation.
  2. Repos whose domain confidence fell below 0.5 (heuristic veto
     fell back to "general" because the LLM classifier over-fit
     on a weak signal).
"""
import sys
from unittest.mock import patch

import yaml

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

from app.agents import general_only
from app.agents.nodes import workflow_generator as wg
from app.agents.language_profiles import resolve_active_profiles


# ---------------------------------------------------------------------------
# Unit tests: env-var parsing
# ---------------------------------------------------------------------------

def test_general_only_default_false(monkeypatch):
    """With no env var set, the toggle is False."""
    monkeypatch.delenv("AI_DEVSECOPS_GENERAL_ONLY", raising=False)
    # Reload the module so the constant is re-evaluated.
    import importlib
    importlib.reload(general_only)
    assert general_only.is_general_only() is False


def test_general_only_true_values(monkeypatch):
    """`1`, `true`, `yes`, `on` (case-insensitive) all flip the toggle."""
    for truthy in ("1", "true", "TRUE", "yes", "YES", "on", "On"):
        monkeypatch.setenv("AI_DEVSECOPS_GENERAL_ONLY", truthy)
        import importlib
        importlib.reload(general_only)
        assert general_only.is_general_only() is True, f"Failed for value: {truthy!r}"


def test_general_only_false_values(monkeypatch):
    """Empty string / random text / missing var all leave the toggle False."""
    for falsy in ("", "0", "false", "no", "off", "random"):
        monkeypatch.setenv("AI_DEVSECOPS_GENERAL_ONLY", falsy)
        import importlib
        importlib.reload(general_only)
        assert general_only.is_general_only() is False, f"Failed for value: {falsy!r}"


# ---------------------------------------------------------------------------
# Integration: workflow_generator_node honours the flag
# ---------------------------------------------------------------------------

def _make_state(general_only_flag: bool, domain_confidence: float = 0.85):
    """Build a state that, without the flag, would emit a custom
    job (so we can prove the flag suppresses it)."""
    return {
        "request_type": "generate_pipeline",
        "github_token": "fake",
        "repository_full_name": "owner/test",
        "detected_technologies": {
            "primary_language": "python",
            "frameworks": ["fastapi"],
            "package_manager": "pip",
            "test_framework": "pytest",
            "build_tools": ["pip"],
        },
        "detected_architecture": {"architecture_type": "monolithic"},
        "detected_architecture_type": "monolithic",
        "detected_deployment": {"docker": False, "kubernetes": False, "terraform": False},
        "inferred_security_needs": {
            "required_stages": ["lint", "test", "sast", "dependency-scan", "secret-scan"]
        },
        "findings": [],
        "repository_structure": [
            {"name": "main.py", "type": "file"},
            {"name": "requirements.txt", "type": "file"},
        ],
        "repository_files": {"main.py": "print('hi')"},
        "detected_domain": "e-commerce",
        "domain_confidence": domain_confidence,
        "domain_threats": [],
        "security_coverages": ["payment_security"],
        "job_designs": [
            {
                "name": "payment-stripe-webhook-verify",
                "coverage": "payment_security",
                "reasoning": (
                    "Found main.py uses stripe in a way that webhook "
                    "signatures are not verified. This job scans for "
                    "missing stripe.webhooks.constructEvent() calls."
                ),
                "actions": [
                    {"type": "shell_check", "name": "scan", "script": "echo test"},
                    {"type": "sarif_upload", "category": "test"},
                ],
                "configuration": {"continue_on_error": True, "timeout_minutes": 10},
            },
        ],
        "errors": [],
        "auto_deploy": False,
        "pipeline_version": 1,
        "general_only": general_only_flag,
        "active_language_profiles": ["python"],
    }


def test_general_only_flag_skips_custom_jobs():
    """With general_only=True, the AI-designed job in job_designs
    is NOT emitted in the final workflow."""
    state = _make_state(general_only_flag=True, domain_confidence=0.85)
    profiles = resolve_active_profiles(state["detected_technologies"])
    state["active_language_profiles"] = [p.id for p in profiles]

    result = wg.workflow_generator_node(state)
    assert not result.get("errors"), f"unexpected errors: {result.get('errors')}"
    parsed = yaml.safe_load(result["generated_workflow"])
    jobs = list(parsed.get("jobs", {}).keys())
    assert "payment-stripe-webhook-verify" not in jobs
    # Standard jobs should still be present.
    assert "sast" in jobs
    assert "secret-scan" in jobs
    assert "dependency-scan" in jobs
    # The domain-compliance caller must not appear either.
    assert "domain-compliance" not in jobs


def test_general_only_false_keeps_custom_jobs():
    """With general_only=False and high domain confidence, the
    AI-designed custom job IS emitted."""
    state = _make_state(general_only_flag=False, domain_confidence=0.85)
    profiles = resolve_active_profiles(state["detected_technologies"])
    state["active_language_profiles"] = [p.id for p in profiles]

    result = wg.workflow_generator_node(state)
    parsed = yaml.safe_load(result["generated_workflow"])
    jobs = list(parsed.get("jobs", {}).keys())
    assert "payment-stripe-webhook-verify" in jobs


def test_low_confidence_also_skips_custom_jobs():
    """Even with general_only=False, when domain_confidence < 0.5
    (heuristic veto fell back to general), custom jobs are skipped."""
    state = _make_state(general_only_flag=False, domain_confidence=0.3)
    profiles = resolve_active_profiles(state["detected_technologies"])
    state["active_language_profiles"] = [p.id for p in profiles]

    result = wg.workflow_generator_node(state)
    parsed = yaml.safe_load(result["generated_workflow"])
    jobs = list(parsed.get("jobs", {}).keys())
    assert "payment-stripe-webhook-verify" not in jobs
    # Standard jobs are still emitted.
    assert "sast" in jobs
