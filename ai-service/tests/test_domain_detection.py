import json
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

from app.agents.nodes.domain_detection_node import (
    DOMAIN_LIBRARY_INDICATORS,
    _extract_entity_names,
    _extract_library_names,
    _extract_route_hints,
    _score_domain,
    domain_detection_node,
)


def _make_state(**overrides):
    state = {
        "errors": [],
        "repository_full_name": "owner/repo",
        "repository_name": "repo",
        "repository_description": "",
        "repository_files": {},
        "source_files": [],
    }
    state.update(overrides)
    return state


def test_extract_libraries_from_package_json():
    pkg_json = json.dumps({
        "dependencies": {
            "stripe": "^10.0.0",
            "react": "^18.0.0",
            "express": "^4.0.0",
        },
        "devDependencies": {"eslint": "^8.0.0"},
    })
    libs = _extract_library_names({"package.json": pkg_json})
    assert "stripe" in libs
    assert "react" in libs
    assert "eslint" in libs


def test_extract_libraries_from_requirements_txt():
    req = "stripe==4.0.0\nrequests>=2.0.0\nfastapi[all]>=0.100.0\n# comment\n"
    libs = _extract_library_names({"requirements.txt": req})
    assert "stripe" in libs
    assert "requests" in libs
    assert "fastapi" in libs


def test_extract_libraries_from_go_mod():
    gomod = """module example.com/foo

go 1.22

require (
\tgithub.com/stripe/stripe-go v74.0.0
\tgithub.com/gin-gonic/gin v1.9.0
)
"""
    libs = _extract_library_names({"go.mod": gomod})
    assert any("stripe" in l for l in libs)
    assert any("gin" in l for l in libs)


def test_extract_entity_names():
    source_files = [
        {"path": "models/Product.js"},
        {"path": "models/Order.py"},
        {"path": "models/Cart.ts"},
        {"path": "models/User.java"},
        {"path": "README.md"},
    ]
    entities = _extract_entity_names(source_files)
    assert "product" in entities
    assert "order" in entities
    assert "cart" in entities
    assert "user" in entities
    assert "readme" not in entities


def test_extract_route_hints():
    source_files = [
        {"content": '@app.get("/checkout")\nasync def checkout():\n    pass'},
        {"content": '@router.post("/payment")\nasync def pay():\n    pass'},
        {"content": '@Get("/patients")\nvoid getPatients() {}'},
    ]
    routes = _extract_route_hints(source_files)
    assert "/checkout" in routes
    assert "/payment" in routes
    assert "/patients" in routes


def test_score_domain_ecommerce():
    libs = {"stripe", "react", "express"}
    ents = {"order", "product", "cart", "payment"}
    routes = {"/checkout", "/cart"}
    scores = _score_domain(libs, ents, routes)
    assert scores.get("e-commerce", 0) > 0
    top = max(scores, key=scores.get)
    assert top == "e-commerce"


def test_score_domain_iot():
    libs = {"paho-mqtt", "flask"}
    ents = {"device", "sensor", "telemetry"}
    routes = {"/devices"}
    scores = _score_domain(libs, ents, routes)
    top = max(scores, key=scores.get)
    assert top == "iot"


def test_score_domain_no_signal_falls_back_to_general():
    scores = _score_domain(set(), set(), set())
    assert scores == {"general": 1.0}


def test_node_classifies_ecommerce_stripe():
    state = _make_state(
        repository_name="my-shop",
        repository_description="Online store with Stripe",
        repository_files={
            "package.json": json.dumps({
                "dependencies": {"stripe": "^10.0.0", "react": "^18.0.0"},
            }),
        },
        source_files=[
            {"path": "models/Product.js", "content": ""},
            {"path": "models/Order.js", "content": ""},
            {"content": '@app.post("/checkout")\nasync def c(): pass', "path": "routes/checkout.js"},
        ],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain": "e-commerce",
            "confidence": 0.92,
            "evidence": ["stripe dependency", "Order/Product entities"],
            "domain_threats": ["Stripe key hardcoded"],
        })
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        out = domain_detection_node(state)

    assert out["detected_domain"] == "e-commerce"
    assert out["domain_confidence"] >= 0.5
    assert any("stripe" in str(e).lower() for e in out["domain_evidence"])
    assert len(out["domain_threats"]) > 0
    assert "errors" not in out or not out["errors"]


def test_node_falls_back_to_general_on_low_confidence():
    state = _make_state(
        repository_name="misc-tool",
        repository_description="",
        repository_files={"package.json": json.dumps({"dependencies": {"lodash": "^4.0.0"}})},
        source_files=[],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain": "e-commerce",
            "confidence": 0.2,
            "evidence": [],
            "domain_threats": [],
        })
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        out = domain_detection_node(state)

    assert out["detected_domain"] == "general"
    assert out["domain_confidence"] == 1.0


def test_node_handles_llm_failure_gracefully():
    # v9.3 revisi 3-domain: only e-commerce, blog, iot are supported.
    # Old "healthcare" indicators no longer classify the repository, so
    # the heuristic falls back to "general" when no supported signal
    # matches. This test verifies the graceful LLM-failure path.
    state = _make_state(
        repository_name="patient-app",
        repository_description="Patient management",
        repository_files={"requirements.txt": "fhirclient==2.0.0\nflask==2.0.0\n"},
        source_files=[
            {"path": "models/Patient.py", "content": ""},
            {"content": '@app.get("/patients")\n', "path": "routes/patient.py"},
        ],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_get_llm.side_effect = RuntimeError("LLM unavailable")

        out = domain_detection_node(state)

    # Healthcare is no longer in the supported domain set, so the
    # deterministic fallback MUST resolve to "general" (no e-commerce
    # / blog / iot signal in the input).
    assert out["detected_domain"] == "general"
    assert "errors" not in out or not out["errors"]


def test_node_short_circuits_on_prior_errors():
    state = _make_state(errors=["prior failure"])
    out = domain_detection_node(state)
    assert out is state
    # Node still runs to populate detected_domain even when prior
    # errors are present (matches the policy in
    # technology_detection_node). The error from a prior node is
    # preserved and surfaced in the final pipeline response.
    assert "detected_domain" in out
    # Should fall back to the heuristic (general with confidence 1.0)
    # when no other evidence is available.
    assert out["detected_domain"] == "general"


def test_invalid_domain_from_llm_normalized_to_general():
    state = _make_state(repository_name="foo")
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain": "gaming",
            "confidence": 0.9,
            "evidence": [],
            "domain_threats": [],
        })
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        out = domain_detection_node(state)

    assert out["detected_domain"] == "general"


# ---------------------------------------------------------------------------
# New tests for requirement 7: do not default to "general" if clear
# repository evidence exists.
# ---------------------------------------------------------------------------


def test_node_detects_ecommerce_when_llm_fails():
    """Requirement 7: LLM failure must not cause us to default to 'general'
    when the deterministic heuristic has clear evidence for a domain.
    """
    state = _make_state(
        repository_name="my-shop",
        repository_description="Online store",
        repository_files={
            "package.json": json.dumps({
                "dependencies": {"stripe": "^10.0.0", "@stripe/stripe-js": "^1.0.0"},
            }),
        },
        source_files=[
            {"path": "models/Order.js", "content": ""},
            {"path": "models/Product.js", "content": ""},
            {"content": '@app.post("/checkout")\nasync def c(): pass', "path": "routes/checkout.js"},
        ],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_get_llm.side_effect = RuntimeError("LLM unavailable")
        out = domain_detection_node(state)

    assert out["detected_domain"] == "e-commerce"
    assert out["domain_confidence"] >= 0.5
    # Evidence should mention the libraries, entities, or routes
    evidence_str = " ".join(str(e) for e in out["domain_evidence"]).lower()
    assert any(kw in evidence_str for kw in ["stripe", "order", "product", "checkout"])


def test_node_overrides_llm_general_with_heuristic_evidence():
    """Requirement 7: LLM may say 'general' with high confidence but the
    heuristic has clear evidence. We should override to the heuristic
    domain, NOT silently fall back to general.
    """
    state = _make_state(
        repository_name="my-shop",
        repository_description="",
        repository_files={
            "package.json": json.dumps({
                "dependencies": {"stripe": "^10.0.0", "@stripe/stripe-js": "^1.0.0"},
            }),
        },
        source_files=[
            {"path": "models/Order.js", "content": ""},
            {"path": "models/Product.js", "content": ""},
            {"content": '@app.post("/checkout")', "path": "routes/checkout.js"},
        ],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain": "general",
            "confidence": 0.95,
            "evidence": [],
            "domain_threats": [],
        })
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        out = domain_detection_node(state)

    assert out["detected_domain"] == "e-commerce", (
        f"expected e-commerce, got {out['detected_domain']}"
    )


def test_node_detects_iot_when_llm_fails():
    # v9.3 revisi 3-domain: healthcare is no longer a supported domain.
    # Mirror test for the new IoT domain: a repository with clear IoT
    # signals must classify as "iot" when the LLM is unavailable.
    state = _make_state(
        repository_name="device-gateway",
        repository_description="MQTT telemetry broker",
        repository_files={
            "requirements.txt": "paho-mqtt==2.0.0\nflask==2.0.0\n",
        },
        source_files=[
            {"path": "models/Device.py", "content": ""},
            {"path": "models/Sensor.py", "content": ""},
            {"content": '@app.get("/telemetry")\n', "path": "routes/sensor.py"},
        ],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_get_llm.side_effect = RuntimeError("LLM unavailable")
        out = domain_detection_node(state)

    assert out["detected_domain"] == "iot"
    assert out["domain_confidence"] >= 0.5


def test_node_remains_general_without_evidence():
    state = _make_state(
        repository_name="misc-tool",
        repository_description="",
        repository_files={"package.json": json.dumps({"dependencies": {"lodash": "^4.0.0"}})},
        source_files=[],
    )
    with patch("app.agents.nodes.domain_detection_node.get_llm") as mock_get_llm:
        mock_get_llm.side_effect = RuntimeError("LLM unavailable")
        out = domain_detection_node(state)

    assert out["detected_domain"] == "general"


if __name__ == "__main__":
    test_extract_libraries_from_package_json()
    test_extract_libraries_from_requirements_txt()
    test_extract_libraries_from_go_mod()
    test_extract_entity_names()
    test_extract_route_hints()
    test_score_domain_ecommerce()
    test_score_domain_iot()
    test_score_domain_no_signal_falls_back_to_general()
    test_node_classifies_ecommerce_stripe()
    test_node_falls_back_to_general_on_low_confidence()
    test_node_handles_llm_failure_gracefully()
    test_node_short_circuits_on_prior_errors()
    test_invalid_domain_from_llm_normalized_to_general()
    test_node_detects_ecommerce_when_llm_fails()
    test_node_overrides_llm_general_with_heuristic_evidence()
    test_node_detects_iot_when_llm_fails()
    test_node_remains_general_without_evidence()
    print("All domain_detection tests passed")
