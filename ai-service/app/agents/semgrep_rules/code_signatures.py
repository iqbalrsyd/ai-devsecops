"""Code-level domain signatures loader (v1.1).

Loads the `code_signatures` section from `domain_knowledge_base.yml`.
The signatures are the ground-truth-anchored set of folder / file /
import / library patterns that confirm a domain. Used by
`app/agents/nodes/domain_detection_node.py` to break ties when the
LLM-only classifier falls back to "general" (which is the failure mode
called out in skripsi Bab 4 §4.4 — Java/Maven repos like ThingsBoard
have no library imports in package.json so the LLM never sees the
IoT signal).

Each signature is a dict with optional keys:
    id                  - unique slug
    repo_name_contains  - substring match (case-insensitive) on repo name
    path_globs          - glob match on file structure (case-insensitive)
    path_contains       - substring match on file path (case-insensitive)
    import_patterns     - regex match on source file content
    libraries           - exact library name (matched against detected libs)
    keywords_desc       - substring match on repository description
    frameworks          - framework identifier (currently informational)
    required            - if True, the heuristic veto can be bypassed when
                          this signature matches

Returns a `dict[domain, list[signature]]` ready to be passed into
`domain_detection_node`.
"""

from __future__ import annotations

import os
import re
from typing import Any


def _kb_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "domain_knowledge_base.yml",
    )


def _yaml_load(path: str) -> dict[str, Any]:
    try:
        import yaml as _yaml  # type: ignore
    except ImportError:  # pragma: no cover - PyYAML is in requirements.txt
        return {}
    try:
        with open(path) as f:
            data = _yaml.safe_load(f)
            return data or {}
    except Exception:
        return {}


def load_code_signatures() -> dict[str, list[dict[str, Any]]]:
    """Return the parsed `code_signatures` block from the KB.

    Empty dict if the file is missing or the block is absent.
    """
    data = _yaml_load(_kb_path())
    sigs = data.get("code_signatures")
    if not isinstance(sigs, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for domain, items in sigs.items():
        if isinstance(items, list):
            out[str(domain)] = [it for it in items if isinstance(it, dict)]
    return out


# ----------------------------------------------------------------------------
# Scoring helper (used by domain_detection_node).
# ----------------------------------------------------------------------------
# A repo's signal set is:
#   - repo_name              : string
#   - repo_description       : string
#   - detected_libraries     : set[str] (lowercased)
#   - repository_structure   : list of path strings (mixed dict/str)
#   - source_files           : list of {path, content}
#
# Each signature contributes:
#   repo_name_contains : +2.0 per hit (strong signal — almost always correct)
#   path_contains      : +1.5 per hit (a single folder is enough)
#   path_globs         : +1.5 per hit
#   import_patterns    : +1.0 per hit (regex on source content)
#   libraries          : +1.5 per hit (lib name match)
#   keywords_desc      : +1.0 per hit (description substring)
#
# `required` signatures get a 0.5 bonus on top of their total.
# Any domain with score >= 1.0 is considered "candidate"; the
# top-scoring domain is the winner (ties broken by `required`).
# ----------------------------------------------------------------------------


def _repo_name_matches(name: str, fragments: list[str]) -> int:
    if not name or not fragments:
        return 0
    name_l = name.lower()
    return sum(1 for f in fragments if f and f.lower() in name_l)


def _keywords_desc_matches(description: str, fragments: list[str]) -> int:
    if not description or not fragments:
        return 0
    desc_l = description.lower()
    return sum(1 for f in fragments if f and f.lower() in desc_l)


def _libraries_match(detected: set[str], candidates: list[str]) -> int:
    if not detected or not candidates:
        return 0
    detected_l = {d.lower() for d in detected}
    return sum(1 for c in candidates if c and c.lower() in detected_l)


def _path_contains_matches(structure: list, fragments: list[str]) -> int:
    if not structure or not fragments:
        return 0
    frags_l = [f.lower() for f in fragments if f]
    if not frags_l:
        return 0
    hits = 0
    for item in structure:
        if isinstance(item, dict):
            path = (item.get("path") or item.get("name") or "").lower()
        else:
            path = str(item or "").lower()
        if not path:
            continue
        for f in frags_l:
            if f in path:
                hits += 1
                break  # count each path once
    return hits


def _import_matches(source_files: list, patterns: list[str]) -> int:
    if not source_files or not patterns:
        return 0
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            continue
    if not compiled:
        return 0
    hits = 0
    for entry in source_files:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content") or ""
        if not content:
            continue
        for c in compiled:
            if c.search(content):
                hits += 1
                break
    return hits


def score_domain(
    domain: str,
    signatures: list[dict[str, Any]],
    *,
    repo_name: str = "",
    repo_description: str = "",
    detected_libraries: set[str] | None = None,
    repository_structure: list | None = None,
    source_files: list | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Return (score, matched_signatures) for one domain.

    `matched_signatures` is a list of dicts of the form:
        {id, repo_name, libs, paths, imports, required, score}
    so callers (or the audit trail) can show *why* a domain was chosen.
    """
    detected_libraries = detected_libraries or set()
    repository_structure = repository_structure or []
    source_files = source_files or []

    matched: list[dict[str, Any]] = []
    total = 0.0
    has_required_match = False

    for sig in signatures or []:
        sig_id = sig.get("id", "?")

        n_repo = _repo_name_matches(repo_name, sig.get("repo_name_contains") or [])
        n_path = _path_contains_matches(repository_structure, sig.get("path_contains") or [])
        # path_globs: case-insensitive substring match (we don't have
        # fnmatch here without a stdlib import; substring is good enough
        # for the patterns the KB uses).
        n_glob = _path_contains_matches(repository_structure, sig.get("path_globs") or [])
        n_import = _import_matches(source_files, sig.get("import_patterns") or [])
        n_libs = _libraries_match(detected_libraries, sig.get("libraries") or [])
        n_kw = _keywords_desc_matches(repo_description, sig.get("keywords_desc") or [])

        s = (
            n_repo * 2.0
            + n_path * 1.5
            + n_glob * 1.5
            + n_import * 1.0
            + n_libs * 1.5
            + n_kw * 1.0
        )
        if sig.get("required") and s > 0:
            s += 0.5
            has_required_match = True

        if s > 0:
            matched.append({
                "id": sig_id,
                "repo_name_hits": n_repo,
                "path_hits": n_path,
                "glob_hits": n_glob,
                "import_hits": n_import,
                "lib_hits": n_libs,
                "keyword_hits": n_kw,
                "required": bool(sig.get("required")),
                "score": round(s, 2),
            })
            total += s

    return round(total, 2), matched, has_required_match


def score_all_domains(
    signatures_by_domain: dict[str, list[dict[str, Any]]],
    *,
    repo_name: str = "",
    repo_description: str = "",
    detected_libraries: set[str] | None = None,
    repository_structure: list | None = None,
    source_files: list | None = None,
) -> list[dict[str, Any]]:
    """Score every domain, sorted by score desc.

    Each result has: domain, score, matched_signatures, has_required.
    """
    rows: list[dict[str, Any]] = []
    for domain, sigs in (signatures_by_domain or {}).items():
        s, matched, req = score_domain(
            domain,
            sigs,
            repo_name=repo_name,
            repo_description=repo_description,
            detected_libraries=detected_libraries,
            repository_structure=repository_structure,
            source_files=source_files,
        )
        if s <= 0 and not matched:
            continue
        rows.append({
            "domain": domain,
            "score": s,
            "matched_signatures": matched,
            "has_required": req,
        })
    rows.sort(key=lambda r: (r["score"], r["has_required"]), reverse=True)
    return rows
