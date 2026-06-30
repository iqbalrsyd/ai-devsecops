"""Tests for domain misclassification fix (heuristic veto).

These tests verify the heuristic veto added to `domain_detection_node`
in support of the multi-language + business-feature-driven pipeline
fix. The veto prevents the LLM classifier from forcing a domain
pick (e.g. "e-commerce") when the deterministic heuristic scores
that domain below MIN_HEURISTIC_SCORE.
"""
import sys
from unittest.mock import patch

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

from app.agents.nodes.domain_detection_node import (
    MIN_HEURISTIC_SCORE,
    _score_domain_raw,
    domain_detection_node,
)


# ---------------------------------------------------------------------------
# Unit tests: pure score function
# ---------------------------------------------------------------------------

def test_min_heuristic_score_constant_is_three():
    """The threshold must stay at 3.0 to balance false positives
    (over-veto) vs false negatives (miss weak-signal repos)."""
    assert MIN_HEURISTIC_SCORE == 3.0


def test_healthcare_signals_score_below_threshold():
    """Healthcare-micro-vuln-style signals (patient, ssn, mrn, /patients)
    should produce a low e-commerce score (only `invoice` / `billing`
    might match weakly). Below 3.0 -> veto triggers if LLM says
    e-commerce."""
    libraries = {"fastapi", "uvicorn", "psycopg2-binary", "pyjwt"}
    entities = {"patient", "ssn", "dob", "mrn", "appointment", "invoice"}
    routes = {"/patients", "/auth/login", "/appointments", "/billing/invoice"}
    raw = _score_domain_raw(libraries, entities, routes)
    # E-commerce is the most likely false-positive pick from the LLM.
    assert raw["e-commerce"] < MIN_HEURISTIC_SCORE
    # Blog and IoT should score 0.
    assert raw["blog"] == 0.0
    assert raw["iot"] == 0.0


def test_laravel_signals_score_above_threshold():
    """Laravel + Stripe + cart/checkout signals produce a high
    e-commerce score (>= 3.0). The veto must NOT trigger and the
    domain should remain e-commerce."""
    libraries = {"stripe/stripe-php", "laravel/framework"}
    entities = {"order", "product", "cart", "payment", "customer",
                "invoice", "billing"}
    routes = {"/checkout", "/cart", "/payment"}
    raw = _score_domain_raw(libraries, entities, routes)
    assert raw["e-commerce"] >= MIN_HEURISTIC_SCORE


# ---------------------------------------------------------------------------
# Integration: end-to-end domain_detection_node with mocked LLM
# ---------------------------------------------------------------------------

def _llm_response(domain: str, confidence: float) -> dict:
    return {
        "domain": domain,
        "confidence": confidence,
        "domain_threats": [],
        "evidence": [],
    }


def test_healthcare_micro_vuln_veto_to_general():
    """Simulate the healthcare-micro-vuln case:
       LLM says 'e-commerce' (because of `PAYMENT_GATEWAY_KEY`
       in services/billing/main.py). Heuristic scores
       e-commerce < 3.0. The veto must override to 'general'."""
    state = {
        "errors": [],
        "repository_full_name": "iqbalrsyd/healthcare-micro-vuln",
        "repository_name": "healthcare-micro-vuln",
        "repository_description": "Healthcare microservices",
        "repository_files": {
            "docker-compose.yml": "version: 3.8\nservices:\n  auth:",
            "services/auth/main.py": "from fastapi import FastAPI",
            "services/patient/main.py": "from fastapi import FastAPI",
            "services/billing/main.py": "PAYMENT_GATEWAY_KEY = 'pg_live_xyz'",
        },
        "source_files": [],
        "detected_technologies": {
            "primary_language": "python",
            "frameworks": ["fastapi"],
            "package_manager": "pip",
        },
    }
    with patch(
        "app.agents.nodes.domain_detection_node._llm_classify",
        return_value=_llm_response("e-commerce", 0.85),
    ):
        result = domain_detection_node(state)
    # The veto overrides the LLM's "e-commerce" pick because the
    # heuristic scored e-commerce below MIN_HEURISTIC_SCORE. The
    # resulting domain is "general" (so the pipeline emits only
    # standard jobs and skips the misleading e-commerce custom
    # jobs that were injected by the LLM).
    assert result["detected_domain"] == "general"


def test_laravel_no_veto_kept_as_e_commerce():
    """Control: a repo with strong e-commerce signals (Laravel +
    Stripe + multiple entities) must NOT be vetoed."""
    state = {
        "errors": [],
        "repository_full_name": "iqbalrsyd/laravel-shop",
        "repository_name": "laravel-shop",
        "repository_description": "E-commerce shop",
        "repository_files": {
            "composer.json": (
                '{"name":"shop","require":{"laravel/framework":"^10.0",'
                '"stripe/stripe-php":"^10.0"}}'
            ),
        },
        # Strong e-commerce signals come from the source file paths
        # and the route files. _extract_entity_names looks at
        # `models|entities|services|routes|controllers` patterns and
        # _extract_route_hints looks at route decorator strings.
        "source_files": [
            {"name": "app/Models/Product.php", "type": "file"},
            {"name": "app/Models/Order.php", "type": "file"},
            {"name": "app/Models/Cart.php", "type": "file"},
            {"name": "app/Models/Payment.php", "type": "file"},
            {"name": "app/Models/Customer.php", "type": "file"},
            {"name": "app/Http/Controllers/CheckoutController.php", "type": "file"},
            {"name": "routes/web.php", "type": "file"},
        ],
        "repository_structure": [
            {"name": "app/Models/Product.php", "type": "file"},
            {"name": "app/Models/Order.php", "type": "file"},
            {"name": "app/Models/Cart.php", "type": "file"},
        ],
        "detected_technologies": {
            "primary_language": "php",
            "frameworks": ["laravel"],
            "package_manager": "composer",
        },
    }
    with patch(
        "app.agents.nodes.domain_detection_node._llm_classify",
        return_value=_llm_response("e-commerce", 0.90),
    ):
        result = domain_detection_node(state)
    assert result["detected_domain"] == "e-commerce", (
        f"Expected e-commerce (Laravel has strong signals), got "
        f"{result.get('detected_domain')!r}"
    )
    assert result["domain_confidence"] >= 0.5
