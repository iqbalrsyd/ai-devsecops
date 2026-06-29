"""Configuration for LLM-generated Semgrep rules (Tier 3).

This module centralises every knob that controls when and how the
pipeline asks the LLM to produce custom Semgrep rules for a
detected domain. Keeping it as a single DICT-driven module means:

  * The pipeline graph stays declarative.
  * Tests can monkeypatch the values without touching LLM code.
  * The docs (docs/domain-rules-table.md) can be regenerated from
    this file as the single source of truth.

v9.4 (sinkron naskah baru) — per rekomendasi-judul.md:
  * Judul skripsi: "Model Adaptive Security Assessment Pipeline
    Berbasis Analisis Domain-Aware Repository untuk Evaluasi Keamanan"
  * 3 domain aktif (R2.2 — pengerucutan 7→3): e-commerce, blog, iot
  * 2 arsitektur aktif (R2.1 — pengerucutan 6→2): monolitik tradisional,
    modular monolith
  * Domain fintech/healthcare/education DIHAPUS dari sistem
  * `MAX_RULES_PER_DOMAIN` mengikuti rekomendasi "3-8 rules per run
    untuk keep PR diff readable" (sesuai guidance di komentar lama)

Reference: docs/domain-rules-table.md (skripsi Bab 4 §4.4)
Naskah source: naskah/rekomendasi-judul.md (R1, R2, R3, R4, R5)
"""

from __future__ import annotations

import hashlib
import os
from typing import Any


# =============================================================================
# Feature flag
# =============================================================================
# Master switch for Tier 3. Default OFF so the existing pipeline
# behaviour is preserved out of the box. Set the env var to "true"
# to opt in.
ENABLE_LLM_GENERATED_RULES: bool = (
    os.environ.get("ENABLE_LLM_GENERATED_RULES", "false").lower() == "true"
)


# =============================================================================
# Domain scope
# =============================================================================
# Domains in which Tier 3 is allowed to produce extra rules. The
# `general` fallback is INTENTIONALLY excluded: if no domain signal
# is present, the pipeline must not invent new attack surfaces.
#
# MUST stay in sync with VALID_DOMAINS in domain_detection_node.py
# (minus the `general` entry).
#
# v9.4 (sinkron naskah baru) — per rekomendasi-judul.md R2.2:
#   Pengerucutan dari 7 domain menjadi 3 domain aktif. Alasan (naskah T3):
#   - e-commerce: representasi domain transactional (Internet Systems)
#   - blog: representasi domain content-driven (Internet/Business hybrid)
#   - IoT: representasi domain device-centric (Internet/Business hybrid)
#   - Domain fintech/healthcare/education DIHAPUS karena overlap profil
#     ancaman dengan e-commerce/blog + keterbatasan dataset repositori
#     publik yang memenuhi kriteria seleksi.
LLM_GENERATION_DOMAINS: frozenset[str] = frozenset({
    "e-commerce",
    "blog",
    "iot",
})


# =============================================================================
# Confidence / safety knobs
# =============================================================================
# Minimum LLM-reported confidence for a generated rule to be kept.
# Rules below this threshold are dropped silently (still recorded in
# the state for observability).
MIN_LLM_CONFIDENCE: float = float(os.environ.get("MIN_LLM_CONFIDENCE", "0.7"))

# Cap on the number of rules generated per domain per pipeline run.
# Prevents runaway token usage and PR noise. Bumped from 5 to 8
# because the Tier-1 static set now covers ~17-27 patterns per
# domain and we want enough headroom for the LLM to fill genuine
# codebase-specific gaps (Bab 5.13.5: "Tier 3 should add 3-8
# rules per run to keep the PR diff readable").
#
# v9.4: dipertahankan 8 mengikuti guidance di atas (sesuai naskah
# R2 + B5 yang mengizinkan ruang eksplorasi untuk 3 domain aktif).
MAX_RULES_PER_DOMAIN: int = int(os.environ.get("MAX_RULES_PER_DOMAIN", "8"))

# Default severity for LLM-generated rules. Intentionally not
# ERROR on first generation — we want these to be visible but not
# break the build for users. A maintainer can promote to ERROR
# after reviewing the rule in the PR.
DEFAULT_LLM_RULE_SEVERITY: str = "WARNING"

# Allowed severities the LLM may emit. Any value outside this set
# is coerced to DEFAULT_LLM_RULE_SEVERITY.
ALLOWED_LLM_SEVERITIES: frozenset[str] = frozenset({
    "INFO", "WARNING", "ERROR",
})


# =============================================================================
# Naming convention
# =============================================================================
# Every LLM-generated rule id MUST start with this prefix. The slug
# after the prefix is derived from the rule's intent (e.g.
# `ecommerce-custom-price-tampering`). The prefix makes the rule
# trivial to grep and to mark as `experimental` in the sast
# skip_rules list if needed.
RULE_ID_PREFIX_TEMPLATE: str = "{domain}-custom-{slug}"

# Max length of the slug portion of a rule id. Semgrep does not
# impose a hard limit, but very long ids clutter the SARIF output.
MAX_SLUG_LENGTH: int = 40

# Filename pattern for the merged Tier-1-and-Tier-3 rule file.
# Per design decision, static (Tier 1) and LLM-generated (Tier 3)
# rules for the SAME domain are merged into a single `.yml` file
# before being committed to `.semgrep/` in the target repo. This
# keeps the PR diff minimal and the rule surface easy to audit per
# domain. A short hash is appended to allow rotation when the
# merged content changes.
MERGED_FILENAME_TEMPLATE: str = "{domain}-combined-{short_hash}.yml"


# =============================================================================
# Cache
# =============================================================================
# Cache key: deterministic hash of the inputs that influence the
# generated rules. If any of these change, the cache is invalidated
# and the LLM is called again.
CACHE_KEY_COMPONENTS: tuple[str, ...] = (
    "domain",
    "domain_threats",
    "primary_language",
    "frameworks",
)


def compute_cache_key(components: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest for the given input dict.

    The dict is serialised as compact JSON with sorted keys so the
    hash is order-independent. `None` values are dropped to avoid
    spurious cache misses.
    """
    import json

    payload = {
        k: components.get(k)
        for k in CACHE_KEY_COMPONENTS
        if components.get(k) is not None
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def short_hash(key: str, length: int = 8) -> str:
    """Return the first `length` chars of the cache key for use in
    the committed filename. Keeps diffs minimal.
    """
    return key[:length]


# =============================================================================
# Cache backend
# =============================================================================
# In-process dict by default. The cache lifetime is the lifetime
# of the ai-service process — fine for development and skripsi
# demos. The cache is intentionally NOT persisted to disk or DB
# to avoid stale-rule footguns across model upgrades.
_CACHE: dict[str, list[dict[str, Any]]] = {}


def cache_get(key: str) -> list[dict[str, Any]] | None:
    return _CACHE.get(key)


def cache_put(key: str, value: list[dict[str, Any]]) -> None:
    _CACHE[key] = value


def cache_clear() -> None:
    """Test helper."""
    _CACHE.clear()


# =============================================================================
# Convenience accessors
# =============================================================================
def is_domain_eligible(detected_domain: str | None) -> bool:
    """Return True if Tier 3 should run for this domain.

    Conditions (all must be true):
      1. Feature flag is ON.
      2. Detected domain is in LLM_GENERATION_DOMAINS.
    """
    if not ENABLE_LLM_GENERATED_RULES:
        return False
    if not detected_domain:
        return False
    return detected_domain.lower().strip() in LLM_GENERATION_DOMAINS


def build_rule_id(domain: str, slug: str) -> str:
    """Return a normalised rule id. `slug` is lowercased, stripped
    of non-alphanumerics, and truncated to MAX_SLUG_LENGTH.
    """
    import re
    domain_n = (domain or "general").lower().strip()
    slug_n = re.sub(r"[^a-z0-9-]+", "-", (slug or "").lower().strip()).strip("-")
    if len(slug_n) > MAX_SLUG_LENGTH:
        slug_n = slug_n[:MAX_SLUG_LENGTH].rstrip("-")
    return RULE_ID_PREFIX_TEMPLATE.format(domain=domain_n, slug=slug_n or "rule")


def build_merged_filename(domain: str, cache_key: str) -> str:
    """Return the filename for the merged Tier-1 + Tier-3 rule file.

    Per design decision, static (Tier 1) and LLM-generated (Tier 3)
    rules for the same domain are merged into a single `.yml` file
    and committed to `.semgrep/` in the target repo. This keeps the
    PR diff minimal and the rule surface easy to audit per domain.
    """
    import re
    domain_n = re.sub(r"[^a-z0-9-]+", "-", (domain or "general").lower().strip()).strip("-") or "general"
    return MERGED_FILENAME_TEMPLATE.format(
        domain=domain_n,
        short_hash=short_hash(cache_key),
    )
