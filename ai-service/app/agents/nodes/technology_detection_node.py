import json

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm, analyze_structured
from app.models.schemas import TechnologyDetection
from app.utils.json_extractor import extract_json_object

EXTENSION_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".java": "Java", ".go": "Go", ".rs": "Rust",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".c": "C",
    ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala", ".r": "R",
    ".m": "Objective-C", ".h": "C/C++ Header", ".sh": "Shell", ".bash": "Shell",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".xml": "XML",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".less": "LESS",
    ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro",
    "Dockerfile": "Docker", "Makefile": "Make", "CMakeLists.txt": "CMake",
}

TECHNOLOGY_DETECTION_PROMPT = """You are a DevSecOps engineer analyzing a GitHub repository.

Given the repository files and structure below, identify the technology stack with confidence scores.

Repository structure:
{structure}

Key files found:
{files}

Existing workflows:
{workflows}

Analyze the files and identify:
- primary_language: the main programming language (e.g. "TypeScript", "Python", "Go", "Java", "Rust")
- primary_language_confidence: confidence score 0.0-1.0 based on evidence (file counts, build configs)
- primary_language_reason: brief explanation of why this language was detected
- frameworks: list of web/app frameworks detected (e.g. ["React", "Express", "Django"])
- framework_confidences: confidence scores for each framework 0.0-1.0
- build_tools: list of build tools detected (e.g. ["Vite", "npm", "tsc", "webpack"])
- package_manager: the package manager used (e.g. "npm", "pip", "go mod", "maven")
- package_manager_confidence: confidence score 0.0-1.0
- test_framework: the testing framework (e.g. "Vitest", "Jest", "pytest") or null if not detected
- database: primary database if detected (e.g. "PostgreSQL", "MongoDB", "Redis") or null
- runtime: runtime environment if detected (e.g. "Node.js 20", "Python 3.11", "Go 1.22") or null

Return ONLY valid JSON matching this schema. Be precise based on actual files.
"""

TECHNOLOGY_INFERENCE_SCHEMA = """
{
  "primary_language": string,
  "primary_language_confidence": number (0.0-1.0),
  "primary_language_reason": string,
  "frameworks": list[string],
  "framework_confidences": list[number],
  "build_tools": list[string],
  "package_manager": string,
  "package_manager_confidence": number (0.0-1.0),
  "test_framework": string | null,
  "database": string | null,
  "runtime": string | null
}
"""


def _extract_json(content: str) -> dict:
    """Backward-compatible wrapper; delegates to shared json_extractor."""
    return extract_json_object(content)


def technology_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    # v9 fix: keep running even with prior errors so Tahap 1 LLM
    # outputs are not silently skipped. The node reads from
    # `state.repository_files` which may be empty if the scan
    # failed, but it can still detect a primary language from
    # the repo name and the LLM call itself.
    if state.get("errors"):
        print(
            f"[technology_detection] running with prior errors: "
            f"{state['errors'][:2]}"
        )

    structure = state.get("repository_structure", [])
    files = state.get("repository_files", {}) or {}
    workflows = state.get("existing_workflows", [])

    try:
        prompt = TECHNOLOGY_DETECTION_PROMPT.format(
            structure=json.dumps(structure, indent=2)[:3000],
            files=json.dumps(files, indent=2)[:5000],
            workflows=json.dumps(workflows, indent=2)[:2000],
        )

        llm = get_llm()
        last_error: Exception | None = None
        tech_dict: dict = {}

        for attempt in range(3):
            try:
                response = llm.invoke(prompt)
                content = (response.content or "").strip()

                if not content:
                    last_error = ValueError("LLM returned empty content")
                    continue

                tech_dict = _extract_json(content)
                # An empty {} from the LLM (valid JSON but no
                # fields) is treated the same as a parse failure
                # so the extension-based fallback below kicks in.
                if tech_dict and tech_dict.get("primary_language"):
                    break

                last_error = json.JSONDecodeError(
                    f"No usable tech dict in response (first 200 chars: {content[:200]!r})",
                    content,
                    0,
                )
            except Exception as e:
                last_error = e
                continue

        if not tech_dict or not tech_dict.get("primary_language"):
            # LLM failed or returned an empty dict (e.g. when
            # the upstream provider is rate-limited, the LLM
            # responds with an empty body or a JSON object that
            # has no fields). Raise so the except block below
            # runs the extension-based fallback — the alternative
            # (silently committing an empty tech_dict) leaves
            # every downstream node with `Unknown` language.
            raise last_error or ValueError("LLM returned no usable tech dict")

        if not tech_dict.get("primary_language"):
            lang_scores = _detect_from_extensions(structure, files)
            if lang_scores:
                tech_dict["primary_language"] = lang_scores[0][0]
                tech_dict["primary_language_confidence"] = min(0.6, lang_scores[0][1] * 0.1)
                tech_dict["primary_language_reason"] = f"Detected via file extension analysis ({lang_scores[0][1]} files)"

        tech_dict.setdefault("primary_language_confidence", 0.8)
        tech_dict.setdefault("primary_language_reason", "Based on repository analysis")
        tech_dict.setdefault("framework_confidences", [0.8] * len(tech_dict.get("frameworks", [])))
        tech_dict.setdefault("package_manager_confidence", 0.8)
        tech_dict.setdefault("build_tools", [])
        tech_dict.setdefault("frameworks", [])

        state["detected_technologies"] = tech_dict
        state["detected_architecture"] = tech_dict.get("architecture") or "monolithic"

    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        # Non-fatal: fall back to extension-based detection so downstream
        # nodes can still produce a useful pipeline. The catch
        # covers JSONDecodeError (LLM returned unparseable JSON),
        # ValueError (LLM returned empty content / no usable
        # tech dict), and RuntimeError (LangChain wraps the
        # upstream 429 / 4xx / 5xx in RuntimeError when the
        # provider is rate-limited or the API key is bad).
        print(f"[DEBUG technology_detection] LLM path failed ({type(e).__name__}: {str(e)[:120]}), using extension fallback")
        fallback = _detect_from_extensions(structure, files)
        if fallback:
            tech_dict = {
                "primary_language": fallback[0][0],
                "primary_language_confidence": min(0.6, fallback[0][1] * 0.1),
                "primary_language_reason": f"Detected via file extension analysis ({fallback[0][1]} files)",
                "frameworks": [],
                "framework_confidences": [],
                "build_tools": [],
                "package_manager": "",
                "package_manager_confidence": 0.0,
                "test_framework": None,
                "database": None,
                "runtime": None,
            }
            tech_dict.setdefault("framework_confidences", [])
            state["detected_technologies"] = tech_dict
        else:
            state["warnings"] = state.get("warnings", []) + [
                f"Technology detection LLM path failed and no file extension signal was found: {str(e)[:200]}"
            ]

    except Exception as e:
        state["warnings"] = state.get("warnings", []) + [
            f"Technology detection failed: {str(e)[:200]}"
        ]

    return state


def _detect_from_extensions(structure: list, files: dict) -> list[tuple[str, int]]:
    """Tally file extensions and return them sorted by frequency.

    Configuration files (package.json, tsconfig.json, etc.) are
    skipped from the count because they are not source code —
    a repo with 5 .js source files and 4 .json config files
    is JavaScript, not JSON. The same logic applies to YAML /
    XML / Dockerfile: useful as build / infra signal but
    never the primary language.

    We also deduplicate by basename so a monorepo with 200
    package.json files (one per package) does not skew the
    count.
    """
    # Config-file basenames that should NOT be counted as source
    # code. The language they are written in (.json, .yaml) is
    # irrelevant to the primary language of the project.
    _CONFIG_BASENAMES: frozenset[str] = frozenset({
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "tsconfig.json", "tsconfig.build.json", "jsconfig.json",
        "composer.json", "composer.lock", "Gemfile.lock",
        "vite.config.js", "vite.config.ts", "vite.config.mjs",
        "next.config.js", "next.config.mjs", "nuxt.config.js", "nuxt.config.ts",
        "angular.json", ".eslintrc.json", ".prettierrc.json",
    })

    ext_count: dict[str, int] = {}
    seen_basenames: set[str] = set()

    def count_ext(name: str):
        if not name:
            return
        name_lower = name.lower()
        basename = name_lower.rsplit("/", 1)[-1]
        # Deduplicate by basename so a monorepo with 200
        # package.json files (one per package) does not skew
        # the count.
        if basename in seen_basenames:
            return
        # Skip config files.
        if basename in _CONFIG_BASENAMES:
            return
        seen_basenames.add(basename)
        for pattern, lang in EXTENSION_MAP.items():
            if pattern.startswith("."):
                if name_lower.endswith(pattern):
                    ext_count[lang] = ext_count.get(lang, 0) + 1
                    break
            else:
                if name_lower == pattern.lower():
                    ext_count[lang] = ext_count.get(lang, 0) + 1
                    break

    for item in structure or []:
        if isinstance(item, dict):
            name = item.get("name", "")
            count_ext(name)
        elif isinstance(item, str):
            count_ext(item)

    for fname in (files or {}).keys():
        count_ext(fname)

    return sorted(ext_count.items(), key=lambda x: -x[1])

    return sorted(ext_count.items(), key=lambda x: -x[1])
