"""Test the two-file workflow split (struktur-v9.3 — rev. 3-domain & 2-arch).

The generator now produces TWO workflow files:
  1. `.github/workflows/ai-devsecops.yml`        (generic — lint, test,
     sast, secret-scan, dep-check, container-scan)
  2. `.github/workflows/ai-devsecops-custom.yml` (AI-generated jobs from
     job_reasoning_node, plus any domain-specific jobs that survive the
     3-domain scope — e-commerce, blog, iot)

v9.3 revisi 3-domain & 2-arch: domain-specific static templates
(pci-dss, hipaa, ledger-check, csp-headers, mqtt-security) are
REMOVED. The 3 supported domains are addressed by the LLM-driven
job_reasoning_node (K2.4) which cites concrete file paths and
library usages from the actual source code.

The generic file always `uses:` the custom file via a `domain-compliance`
job, so domain jobs are wired in cleanly. This test exercises the splitter
on a minimal synthetic YAML and on real generator output for the most
common domains.
"""
import sys
import os

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.nodes.workflow_generator import (
    _split_workflow_yaml,
    _is_generic_stage,
    GENERIC_STAGE_NAMES,
    CUSTOM_STAGE_NAMES,
    build_workflow_yaml_split,
)


SAMPLE_MERGED = """\
name: CI DevSecOps (JavaScript)
'on':
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo lint
  sast:
    runs-on: ubuntu-latest
    steps:
      - run: echo sast
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - run: echo secret-scan
  payment-checkout-security:
    runs-on: ubuntu-latest
    steps:
      - run: echo payment-checkout-security
  blog-csp-headers:
    runs-on: ubuntu-latest
    steps:
      - run: echo blog-csp-headers
  mqtt-tls-audit:
    runs-on: ubuntu-latest
    steps:
      - run: echo mqtt-tls-audit
"""


def test_is_generic_stage_classifies_known_stages():
    assert _is_generic_stage("lint") is True
    assert _is_generic_stage("sast") is True
    assert _is_generic_stage("container-scan") is True
    # v9.3 revisi 3-domain: any non-generic name (including AI-generated
    # jobs and any leftover legacy names) is treated as custom because
    # the explicit CUSTOM_STAGE_NAMES set is empty in the new scope.
    assert _is_generic_stage("payment-checkout-security") is False
    assert _is_generic_stage("blog-csp-headers") is False
    assert _is_generic_stage("mqtt-tls-audit") is False
    # Legacy domain-specific names now classify as custom (route to
    # custom file) so any leftover references in tests still behave
    # consistently.
    assert _is_generic_stage("pci-dss") is False
    assert _is_generic_stage("hipaa") is False


def test_is_generic_stage_handles_unknown_as_custom():
    # v9.3 revisi 3-domain: unknown stage names (e.g. AI-generated
    # job designs that are not in the explicit GENERIC_STAGE_NAMES
    # set) are routed to the custom file.
    assert _is_generic_stage("some-future-stage") is False
    assert _is_generic_stage("") is False


def test_split_workflow_yaml_separates_generic_from_custom():
    generic, custom, meta = _split_workflow_yaml(SAMPLE_MERGED, detected_domain="e-commerce")

    assert generic, "generic file must not be empty"
    assert custom, "custom file must not be empty when domain jobs exist"
    assert len(meta) == 2, f"expected 2 file metadata entries, got {len(meta)}"

    gen_doc = yaml.safe_load(generic)
    cus_doc = yaml.safe_load(custom)

    # Generic file keeps the standard jobs + adds a domain-compliance caller.
    assert "lint" in gen_doc["jobs"]
    assert "sast" in gen_doc["jobs"]
    assert "secret-scan" in gen_doc["jobs"]
    assert "domain-compliance" in gen_doc["jobs"]
    assert "payment-checkout-security" not in gen_doc["jobs"]
    assert "blog-csp-headers" not in gen_doc["jobs"]

    # Custom file declares workflow_call + only domain jobs.
    assert "workflow_call" in cus_doc["on"]
    assert "lint" not in cus_doc["jobs"]
    assert "payment-checkout-security" in cus_doc["jobs"]
    assert "blog-csp-headers" in cus_doc["jobs"]
    assert "mqtt-tls-audit" in cus_doc["jobs"]


def test_split_workflow_yaml_generic_caller_references_custom_file():
    generic, _, _ = _split_workflow_yaml(SAMPLE_MERGED, detected_domain="e-commerce")
    gen_doc = yaml.safe_load(generic)
    caller = gen_doc["jobs"]["domain-compliance"]
    assert caller["uses"] == "./.github/workflows/ai-devsecops-custom.yml"
    assert caller["secrets"] == "inherit"


def test_split_workflow_yaml_no_custom_when_no_domain_jobs():
    only_generic = """\
name: test
on: push
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo
  sast:
    runs-on: ubuntu-latest
    steps:
      - run: echo
"""
    generic, custom, meta = _split_workflow_yaml(only_generic, detected_domain="general")
    assert custom == "", "no custom file when no domain jobs are present"
    assert len(meta) == 1
    assert meta[0]["kind"] == "generic"


def test_split_workflow_yaml_passes_through_invalid_yaml():
    # Defensive: if the input is unparseable, return original text as
    # generic and empty custom so the deploy step still works.
    bad = "this is :: not valid yaml [\n"
    generic, custom, meta = _split_workflow_yaml(bad)
    assert generic == bad
    assert custom == ""
    assert meta == []


def test_build_workflow_yaml_split_runs_end_to_end():
    """Smoke test: build_workflow_yaml_split must succeed on the same
    inputs that the production generator uses and return the expected
    shape with both files populated for an e-commerce domain (the
    custom file now contains AI-generated jobs, not the legacy
    static pci-dss template)."""
    result = build_workflow_yaml_split(
        primary_language="JavaScript",
        package_manager="npm",
        test_framework="Jest",
        frameworks=["Express"],
        build_tools=["npm"],
        stages=["lint", "test", "sast", "secret-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[{"name": "package.json", "path": "package.json", "type": "file"}],
        files={"package.json": "{}"},
        detected_domain="e-commerce",
        domain_confidence=0.9,
        domain_threats=["sql_injection", "credit_card"],
        state=None,
    )

    assert "generic_yaml" in result
    assert "custom_yaml" in result
    assert "merged_yaml" in result
    assert "stage_names" in result
    assert "stages_general" in result
    assert "stages_custom" in result
    assert "explanations" in result
    assert "file_meta" in result

    # Generic file is a valid YAML document.
    gen_doc = yaml.safe_load(result["generic_yaml"])
    assert isinstance(gen_doc, dict)
    assert "jobs" in gen_doc
    # Custom file is empty in this smoke test (no AI job_designs
    # supplied and no domain-specific static templates in the new
    # 3-domain scope). Empty string is the expected contract.
    assert result["custom_yaml"] == ""

    # Stage classification: the standard 4 jobs land in the generic file
    # and no custom jobs are present in this smoke test (no job_designs).
    assert "lint" in result["stages_general"]
    assert "sast" in result["stages_general"]
    # Without AI job_designs in state, the custom file is empty.
    assert result["stages_custom"] == []


def test_build_workflow_yaml_split_general_domain_has_no_custom():
    """A `general` domain must NOT produce a custom file (no domain jobs
    are needed, so the custom file is empty / dropped)."""
    result = build_workflow_yaml_split(
        primary_language="Python",
        package_manager="pip",
        test_framework="pytest",
        frameworks=["Flask"],
        build_tools=["pip"],
        stages=["lint", "test", "sast", "secret-scan"],
        arch_type="monolithic",
        findings=[],
        structure=[],
        files={},
        detected_domain="general",
        state=None,
    )
    assert result["custom_yaml"] == "", "general domain must not emit a custom file"
    assert all(m["kind"] == "generic" for m in result["file_meta"])
    assert result["stages_custom"] == []


def test_generic_and_custom_stage_names_disjoint():
    """Sanity: the two stage sets must not overlap, otherwise the splitter
    would emit the same job in both files."""
    overlap = GENERIC_STAGE_NAMES & CUSTOM_STAGE_NAMES
    assert not overlap, f"generic/custom stage sets must be disjoint, got overlap: {overlap}"


def test_ai_job_renderer_drops_generic_needs():
    """Regression: AI-generated jobs that declare `configuration.needs: [sast]`
    must NOT emit `needs: [sast]` in the custom file. The custom file is a
    `workflow_call` reusable workflow that has no `sast` sibling, so emitting
    that reference makes GitHub reject the file with
      "Job 'X' depends on unknown job 'sast'" or
      "must contain at least one job with no dependencies".
    """
    from app.agents.nodes.workflow_generator import _build_ai_job_from_design

    design = {
        "name": "blog-markdown-sanitize",
        "coverage": "cms_security",
        "reasoning": "test design",
        "actions": [
            {
                "type": "shell_check",
                "name": "noop",
                "script": "echo ok",
            },
            {
                "type": "sarif_upload",
                "category": "blog-markdown-xss",
            },
        ],
        "configuration": {
            "continue_on_error": True,
            "timeout_minutes": 10,
            "needs": ["sast"],  # the old default — must be dropped
        },
    }
    body, reason = _build_ai_job_from_design(design, state=None)
    assert body, "expected non-empty body"
    assert "needs:" not in body, (
        f"AI-generated job must not emit `needs:` in custom file, got:\n{body}"
    )


def test_domain_template_designs_count_per_domain():
    """Each of the 3 supported domains must contribute at least 6 job
    designs (3 originals + 3 extended) so the custom file is non-trivial
    and meaningfully covers domain threats."""
    from app.agents.nodes.job_reasoning_node import _domain_template_designs

    for domain in ("e-commerce", "blog", "iot"):
        designs = _domain_template_designs(domain)
        assert len(designs) >= 6, (
            f"domain '{domain}' must have >=6 template designs, got {len(designs)}: "
            f"{[d['name'] for d in designs]}"
        )
        # No duplicate job names within a domain
        names = [d["name"] for d in designs]
        assert len(names) == len(set(names)), f"duplicate names in {domain}: {names}"
