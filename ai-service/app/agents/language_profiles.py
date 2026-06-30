"""Language profiles for multi-language pipeline generation.

Each profile is a data table that the workflow generator dispatches
against to render the correct setup / install / lint / test / SCA
steps for a given detected language. The 8 supported languages cover
the most common ecosystems in 2024+:

  - python   : pip / poetry / pipenv
  - node     : npm / yarn / pnpm (covers JS + TS)
  - go       : Go modules
  - java     : JVM (maven / gradle) — covers Java / Kotlin / Scala
  - rust     : cargo
  - ruby     : bundler (covers Ruby / Rails)
  - dotnet   : .NET SDK (covers C# / F# / VB.NET)
  - php      : composer (covers PHP / Laravel / Symfony)

Design principles
-----------------

1. **Lint & Test** are per-language because each toolchain has its own
   linter and test runner. They require the matching `actions/setup-*`
   step.

2. **Dependency-scan** uses Trivy filesystem scan as the universal
   SCA backend for all 8 languages. Trivy supports SARIF natively and
   the resulting file is uploaded to GitHub Code Scanning via
   `github/codeql-action/upload-sarif@v3` — no per-language JSON→SARIF
   converter is required.

3. Tool-specific SCA (pip-audit, npm audit) is only emitted as an
   *additional* step on top of Trivy for the 2 languages where Trivy
   alone is known to miss important classes of CVE (e.g. pip-audit
   detects dependency confusion; npm audit detects license issues).

4. The profile lookup is a deterministic mapping — the runtime path
   does NOT call the LLM to decide what tool to use. The LLM is
   called only in `technology_detection_node` to identify the
   primary_language, and the workflow generator just does a table
   lookup. This keeps the output reproducible and the token cost
   minimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Profile component specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LinterSpec:
    """How to run a linter for a language.

    `install` runs in its own step (skip if empty / already in setup).
    `run` is a single shell command. Always `|| true` to avoid
    failing the workflow on style violations.
    """
    install: str
    run: str
    notes: str = ""


@dataclass(frozen=True)
class TestSpec:
    """How to install deps and run tests for a language."""
    install: str           # primary install command
    install_fallback: str  # tried if `install` fails
    run: str               # test invocation, always `|| true`
    notes: str = ""


@dataclass(frozen=True)
class ScaSpec:
    """Software Composition Analysis (dependency vulnerability scan).

    Two strategies:
      - `tool="trivy"`      : Trivy fs scan — SARIF native, no converter
      - `tool="pip-audit"`  : pip-audit JSON — needs converter
      - `tool="npm-audit"`  : npm audit JSON — needs converter

    For tools other than "trivy" the generator ALSO runs Trivy fs in
    the universal `dependency-scan` job, so there is no loss of
    coverage.
    """
    tool: str                  # "trivy" | "pip-audit" | "npm-audit" | ""
    native_sarif: bool         # True if tool output is SARIF directly
    install: str               # tool install (or empty)
    run: str                   # scan invocation (or empty)
    output_json: str           # JSON output file (or empty)
    output_sarif: str          # SARIF output file (or empty)
    converter: str             # converter function name (or empty)
    notes: str = ""


@dataclass(frozen=True)
class LanguageProfile:
    """A complete language-specific build profile."""
    id: str                                  # "python" | "node" | "go" | ...
    label: str                               # "Python"
    setup_action: str                        # e.g. "actions/setup-python@v5"
    version_input: str                       # e.g. "python-version"
    default_version: str                     # e.g. "3.11"
    cache: Optional[str]                     # "pip" | "npm" | None
    linter: Optional[LinterSpec]             # None = no per-lang linter
    test: Optional[TestSpec]                 # None = no per-lang test runner
    sca: ScaSpec                             # Trivy universal fallback
    frameworks: tuple[str, ...] = field(default_factory=tuple)
    """Common framework identifiers that should map to this language
    (used by `resolve_profile_for` as a fallback for LLM-detected
    `frameworks[]` array)."""
    notes: str = ""


# ---------------------------------------------------------------------------
# 8 language profiles
# ---------------------------------------------------------------------------

LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        id="python",
        label="Python",
        setup_action="actions/setup-python@v5",
        version_input="python-version",
        default_version="3.11",
        cache="pip",
        linter=LinterSpec(
            install="pip install ruff",
            run="ruff check . || true",
            notes="Ruff: fast, drop-in replacement for flake8+isort+black",
        ),
        test=TestSpec(
            install="pip install -r requirements.txt || true",
            install_fallback="pip install -e . || true",
            run="pytest || python -m pytest || true",
        ),
        sca=ScaSpec(
            tool="pip-audit",
            native_sarif=False,
            install="pip install pip-audit",
            run="pip-audit --strict --disable-pip --format=json --output=pip-audit-results.json || true",
            output_json="pip-audit-results.json",
            output_sarif="pip-audit-results.sarif",
            converter="pip-audit",
            notes="pip-audit detects dependency confusion, Trivy does not",
        ),
        frameworks=("django", "flask", "fastapi", "starlette", "pyramid"),
        notes="Most mature pipeline. pip-audit is emitted as ADDITIONAL step on top of Trivy.",
    ),

    "node": LanguageProfile(
        id="node",
        label="Node.js",
        setup_action="actions/setup-node@v5",
        version_input="node-version",
        default_version="20",
        cache="npm",
        linter=LinterSpec(
            install="",
            run="npm run lint --if-present || true",
            notes="Delegated to package.json `lint` script (ESLint / Prettier / etc.)",
        ),
        test=TestSpec(
            install="npm ci --no-audit --no-fund",
            install_fallback="npm install --prefer-offline",
            run="npm test --if-present || true",
        ),
        sca=ScaSpec(
            tool="npm-audit",
            native_sarif=False,
            install="",
            run="npm audit --audit-level=high --json > npm-audit-results.json || true",
            output_json="npm-audit-results.json",
            output_sarif="npm-audit-results.sarif",
            converter="npm-audit",
            notes="npm audit detects license issues, Trivy does not",
        ),
        frameworks=("react", "vue", "angular", "svelte", "next", "nuxt", "express", "fastify", "nestjs"),
        notes="Covers JavaScript + TypeScript monorepos. Node version auto-detected from package.json engines.node, capped at 20 LTS.",
    ),

    "go": LanguageProfile(
        id="go",
        label="Go",
        setup_action="actions/setup-go@v5",
        version_input="go-version",
        default_version="1.22",
        cache=None,
        linter=LinterSpec(
            install="",
            run="go vet ./... || true",
            notes="Standard `go vet` covers shadowing, printf format, build tags, etc.",
        ),
        test=TestSpec(
            install="",
            install_fallback="",
            run="go test -race -count=1 ./... || true",
            notes="Race detector + fresh test cache; CI-safe defaults",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan go.sum + Go binary. SARIF native, uploaded to Code Scanning.",
        ),
        frameworks=("gin", "echo", "fiber", "chi", "gorm"),
        notes="Tool-specific SCA (govulncheck) is NOT emitted by default — Trivy covers go.sum CVEs.",
    ),

    "java": LanguageProfile(
        id="java",
        label="Java (JVM)",
        setup_action="actions/setup-java@v4",
        version_input="java-version",
        default_version="17",
        cache=None,
        linter=LinterSpec(
            install="",
            run="echo 'No standard linter step — checkerframework is too heavy for CI; using semgrep as fallback.'",
            notes="For Java, SAST (Semgrep with p/java) provides the security-focused checks; the per-lang linter step is a no-op.",
        ),
        test=TestSpec(
            install="",
            install_fallback="",
            run='mvn -q test || gradle test || true',
            notes="Tries mvn first, falls back to gradle",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan pom.xml / build.gradle / *.jar. SARIF native.",
        ),
        frameworks=("spring", "spring-boot", "micronaut", "quarkus", "play", "ktor"),
        notes="Covers Java / Kotlin / Scala / Groovy — all use the same JDK and SCA tooling.",
    ),

    "rust": LanguageProfile(
        id="rust",
        label="Rust",
        setup_action="dtolnay/rust-toolchain@stable",
        version_input="toolchain",
        default_version="stable",
        cache=None,
        linter=LinterSpec(
            install="",
            run="cargo check --all-targets || true",
            notes="cargo check is faster than clippy and still catches type/borrow errors",
        ),
        test=TestSpec(
            install="",
            install_fallback="",
            run="cargo test --all-features || true",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan Cargo.lock. SARIF native.",
        ),
        frameworks=("actix-web", "rocket", "axum", "tokio", "diesel", "sqlx"),
    ),

    "ruby": LanguageProfile(
        id="ruby",
        label="Ruby",
        setup_action="actions/setup-ruby@v2",
        version_input="ruby-version",
        default_version="3.2",
        cache="bundler",
        linter=LinterSpec(
            install="bundle install",
            run="bundle exec rubocop --no-fail-level=convention || true",
            notes="RuboCop is the de-facto Ruby linter; --no-fail-level keeps CI green on style violations",
        ),
        test=TestSpec(
            install="bundle install",
            install_fallback="bundle install --jobs=4",
            run="bundle exec rspec || true",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan Gemfile.lock. SARIF native.",
        ),
        frameworks=("rails", "sinatra", "hanami", "grape"),
        notes="Covers Ruby on Rails / Sinatra.",
    ),

    "dotnet": LanguageProfile(
        id="dotnet",
        label=".NET (C#/F#/VB)",
        setup_action="actions/setup-dotnet@v4",
        version_input="dotnet-version",
        default_version="8.0.x",
        cache=None,
        linter=LinterSpec(
            install="dotnet restore",
            run="dotnet format --verify-no-changes --severity warning || true",
            notes="dotnet format is the official formatter; --verify-no-changes runs as a check",
        ),
        test=TestSpec(
            install="dotnet restore",
            install_fallback="dotnet restore --locked-mode",
            run="dotnet test --no-restore --verbosity normal || true",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan packages.lock.json + *.deps.json. SARIF native.",
        ),
        frameworks=("aspnet-core", "blazor", "entityframework", "xunit", "nunit"),
        notes="One profile covers C#, F#, VB.NET — all share the .NET SDK.",
    ),

    "php": LanguageProfile(
        id="php",
        label="PHP (Laravel/Symfony)",
        setup_action="shivammathur/setup-php@v2",
        version_input="php-version",
        default_version="8.2",
        cache="composer",
        linter=LinterSpec(
            install="composer install --prefer-dist --no-progress",
            run="vendor/bin/phpcs --standard=PSR12 app/ || true",
            notes="PHP_CodeSniffer with PSR-12; Laravel projects often extend with custom ruleset",
        ),
        test=TestSpec(
            install="composer install --prefer-dist --no-progress",
            install_fallback="composer install --no-scripts",
            run="vendor/bin/phpunit --testdox || true",
        ),
        sca=ScaSpec(
            tool="trivy",
            native_sarif=True,
            install="",
            run="",
            output_json="",
            output_sarif="trivy-fs-results.sarif",
            converter="",
            notes="Trivy fs scan composer.lock. SARIF native.",
        ),
        frameworks=("laravel", "symfony", "codeigniter", "yii", "phalcon", "slim"),
        notes="Covers Laravel + Symfony + plain PHP. shivammathur/setup-php provides the broadest PHP version coverage.",
    ),
}


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------
# LLM-detected primary_language values can be loose ("C#", "TypeScript",
# "JavaScript", "Kotlin", etc.). This table normalises them to a
# canonical profile key. The lookup is case-insensitive.

LANGUAGE_ALIASES: dict[str, str] = {
    # .NET family
    "csharp": "dotnet",
    "c#": "dotnet",
    "fsharp": "dotnet",
    "f#": "dotnet",
    "vb": "dotnet",
    "vb.net": "dotnet",
    ".net": "dotnet",
    "dotnet": "dotnet",
    # Node family
    "javascript": "node",
    "js": "node",
    "typescript": "node",
    "ts": "node",
    # JVM family
    "java": "java",
    "kotlin": "java",
    "scala": "java",
    "groovy": "java",
    # Others
    "python": "python",
    "py": "python",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "rs": "rust",
    "ruby": "ruby",
    "rb": "ruby",
    "php": "php",
}

# Reverse map: canonical framework name → profile id. Used when
# `detected_technologies.frameworks` is the only signal (e.g. primary
# language is "unknown" but a `requirements.txt` has Django).

FRAMEWORK_TO_PROFILE: dict[str, str] = {
    # Python
    "django": "python",
    "flask": "python",
    "fastapi": "python",
    "starlette": "python",
    "pyramid": "python",
    # Node
    "react": "node",
    "vue": "node",
    "angular": "node",
    "svelte": "node",
    "next": "node",
    "nextjs": "node",
    "nuxt": "node",
    "express": "node",
    "fastify": "node",
    "nestjs": "node",
    # Go
    "gin": "go",
    "echo": "go",
    "fiber": "go",
    "chi": "go",
    "gorm": "go",
    # Java
    "spring": "java",
    "spring-boot": "java",
    "springboot": "java",
    "micronaut": "java",
    "quarkus": "java",
    "play": "java",
    "ktor": "java",
    # Rust
    "actix-web": "rust",
    "actix": "rust",
    "rocket": "rust",
    "axum": "rust",
    "tokio": "rust",
    "diesel": "rust",
    "sqlx": "rust",
    # Ruby
    "rails": "ruby",
    "sinatra": "ruby",
    "hanami": "ruby",
    "grape": "ruby",
    # .NET
    "aspnet-core": "dotnet",
    "aspnetcore": "dotnet",
    "blazor": "dotnet",
    "entityframework": "dotnet",
    "xunit": "dotnet",
    "nunit": "dotnet",
    # PHP
    "laravel": "php",
    "symfony": "php",
    "codeigniter": "php",
    "yii": "php",
    "phalcon": "php",
    "slim": "php",
}


def resolve_profile_for(
    primary_language: str | None,
    frameworks: list[str] | None = None,
    package_manager: str | None = None,
) -> LanguageProfile | None:
    """Map detected language/framework to a LanguageProfile.

    Resolution order (first match wins):
      1. `primary_language` (normalised via LANGUAGE_ALIASES)
      2. First framework in `frameworks` (normalised via FRAMEWORK_TO_PROFILE)
      3. Heuristic from `package_manager` ("pip" → python, "npm" → node, ...)

    Returns None if no profile matches — caller should treat the repo
    as language-agnostic and rely on the universal Trivy fs scan.
    """
    if primary_language:
        key = primary_language.lower().strip()
        canonical = LANGUAGE_ALIASES.get(key, key)
        if canonical in LANGUAGE_PROFILES:
            return LANGUAGE_PROFILES[canonical]

    if frameworks:
        for fw in frameworks:
            fw_key = fw.lower().strip()
            canonical = FRAMEWORK_TO_PROFILE.get(fw_key)
            if canonical and canonical in LANGUAGE_PROFILES:
                return LANGUAGE_PROFILES[canonical]

    if package_manager:
        pm = package_manager.lower().strip()
        pm_map = {
            "pip": "python", "poetry": "python", "pipenv": "python", "pdm": "python",
            "npm": "node", "yarn": "node", "pnpm": "node",
            "go mod": "go", "gopath": "go",
            "maven": "java", "gradle": "java",
            "cargo": "rust",
            "bundler": "ruby", "gem": "ruby",
            "composer": "php",
            "nuget": "dotnet", "dotnet": "dotnet",
        }
        for token, profile_id in pm_map.items():
            if token in pm and profile_id in LANGUAGE_PROFILES:
                return LANGUAGE_PROFILES[profile_id]

    return None


def resolve_active_profiles(
    detected_technologies: dict | None,
) -> list[LanguageProfile]:
    """Return a deduplicated, ordered list of profiles to emit jobs for.

    Order: 1) primary language, 2) each unique framework's profile.
    Falls back to a single profile inferred from package_manager.
    Returns an empty list if nothing can be determined — the caller
    should then rely on the universal Trivy fs scan.
    """
    if not detected_technologies:
        return []

    primary = detected_technologies.get("primary_language")
    frameworks = detected_technologies.get("frameworks") or []
    package_manager = detected_technologies.get("package_manager")

    seen: set[str] = set()
    out: list[LanguageProfile] = []

    primary_profile = resolve_profile_for(primary, frameworks, package_manager)
    if primary_profile and primary_profile.id not in seen:
        out.append(primary_profile)
        seen.add(primary_profile.id)

    for fw in frameworks:
        fw_profile = resolve_profile_for(None, [fw], None)
        if fw_profile and fw_profile.id not in seen:
            out.append(fw_profile)
            seen.add(fw_profile.id)

    if not out and package_manager:
        pm_profile = resolve_profile_for(None, None, package_manager)
        if pm_profile and pm_profile.id not in seen:
            out.append(pm_profile)
            seen.add(pm_profile.id)

    return out


def list_supported_languages() -> list[dict]:
    """Return a JSON-friendly list of supported languages for the API."""
    return [
        {
            "id": p.id,
            "label": p.label,
            "default_version": p.default_version,
            "setup_action": p.setup_action,
            "has_linter": p.linter is not None,
            "has_test": p.test is not None,
            "sca_tool": p.sca.tool,
            "native_sarif": p.sca.native_sarif,
            "frameworks": list(p.frameworks),
        }
        for p in LANGUAGE_PROFILES.values()
    ]
