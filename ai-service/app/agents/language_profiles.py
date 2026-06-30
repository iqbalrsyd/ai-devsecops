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
        cache=None,
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
    "typescript": "node",
    "ts": "node",
    "javascript": "node",
    "js": "node",
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


# ---------------------------------------------------------------------------
# Semgrep registry mapping (multi-language SAST)
# ---------------------------------------------------------------------------
# Each language maps to a list of Semgrep registry rulesets (the `p/*`
# shorthand in the Semgrep CLI). The SAST job emits one
# `--config=<ruleset>` flag per entry. The first entry is the most
# specific (language / framework); the rest are cross-cutting
# (OWASP / secrets / supply chain) and deduplicated against whatever
# domain-specific rules the user already enabled.
#
# Reference (verified Jan 2026):
#   https://semgrep.dev/r  (registry search for "p/<lang>")
#
# Note: Semgrep registry tags move occasionally. If a ruleset is
# renamed upstream, the generator's `semgrep ci` invocation will
# fail at runtime — fix by updating the entry here.

SEMGREP_REGISTRY_BY_LANGUAGE: dict[str, list[str]] = {
    "python": [
        "p/python",
        "p/django",
        "p/flask",
        "p/fastapi",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "node": [
        "p/javascript",
        "p/typescript",
        "p/nodejs",
        "p/expressjs",
        "p/react",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "go": [
        "p/golang",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "java": [
        "p/java",
        "p/kotlin",
        "p/spring",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "rust": [
        "p/rust",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "ruby": [
        "p/ruby",
        "p/rails",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "dotnet": [
        "p/csharp",
        "p/dotnet",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
    "php": [
        "p/php",
        "p/laravel",
        "p/owasp-top-ten",
        "p/secrets",
        "p/security-audit",
    ],
}

# Default ruleset when no language can be inferred (or before the
# new multi-language mapping was wired in). Kept narrow on purpose
# so the SAST job does not pull the entire registry.
SEMGREP_REGISTRY_FALLBACK: list[str] = [
    "p/owasp-top-ten",
    "p/secrets",
    "p/security-audit",
]


def semgrep_registry_for_languages(
    primary_language: str | None,
    extra_frameworks: list[str] | None = None,
) -> list[str]:
    """Build the Semgrep `--config` flag list for one or more languages.

    Resolution order:
      1. `primary_language` (after alias normalisation)
      2. First known framework in `extra_frameworks`
      3. SEMGREP_REGISTRY_FALLBACK (just the cross-cutting rulesets)

    The returned list preserves the per-language ordering (most
    specific first) and de-duplicates while keeping first-seen order.
    """
    seen: set[str] = set()
    out: list[str] = []

    def _add(rules: list[str]) -> None:
        for r in rules:
            if r and r not in seen:
                seen.add(r)
                out.append(r)

    # 1. Primary language
    if primary_language:
        key = primary_language.lower().strip()
        canonical = LANGUAGE_ALIASES.get(key, key)
        if canonical in SEMGREP_REGISTRY_BY_LANGUAGE:
            _add(SEMGREP_REGISTRY_BY_LANGUAGE[canonical])

    # 2. Each known framework → its host language
    if extra_frameworks:
        for fw in extra_frameworks:
            profile_id = FRAMEWORK_TO_PROFILE.get(fw.lower().strip())
            if profile_id and profile_id in SEMGREP_REGISTRY_BY_LANGUAGE:
                _add(SEMGREP_REGISTRY_BY_LANGUAGE[profile_id])

    # 3. Fallback
    if not out:
        _add(SEMGREP_REGISTRY_FALLBACK)

    return out


# ---------------------------------------------------------------------------
# YAML emission helpers
# ---------------------------------------------------------------------------
# These functions return GitHub Actions YAML as a list of string lines.
# The caller is expected to embed them in a job body. The `pin()`
# function from `action_registry` is used to resolve action refs to
# verified SHA-pinned forms; we import it lazily inside the helpers so
# this module stays importable in environments where the action
# registry has not been initialised yet (e.g. unit tests, CLI tools).

def _get_pinned_action(action_ref: str) -> str:
    """Resolve an action ref to its pinned SHA form.

    Defers to `action_registry.pin()`; if the action is not in the
    registry, falls back to the ref as-given so the workflow can still
    be inspected (a downstream validator will flag the unpinned ref).
    """
    try:
        from app.agents.action_registry import pin
        return pin(action_ref)
    except Exception:
        return action_ref


def _format_setup_step(profile: LanguageProfile) -> list[str]:
    """Render the setup-* step for a profile."""
    lines = [
        f"      - name: Set up {profile.label}",
        f"        uses: {_get_pinned_action(profile.setup_action)}",
        "        with:",
        f"          {profile.version_input}: '{profile.default_version}'",
    ]
    if profile.cache:
        lines.append(f"          cache: '{profile.cache}'")
    return lines


def _format_install_step(profile: LanguageProfile) -> list[str]:
    """Render the dependency install step for a profile (if any)."""
    if not profile.test or not profile.test.install:
        return []
    return [
        "      - name: Install dependencies",
        f"        run: {profile.test.install}",
        "        continue-on-error: true",
    ]


def _format_linter_step(profile: LanguageProfile) -> list[str]:
    """Render the linter install + run steps for a profile."""
    if not profile.linter:
        return []
    out: list[str] = []
    if profile.linter.install:
        out.extend([
            f"      - name: Install {profile.label} linter",
            f"        run: {profile.linter.install}",
            "        continue-on-error: true",
        ])
    out.append(
        f"      - name: Run {profile.label} linter",
    )
    out.append(f"        run: {profile.linter.run}")
    return out


def _format_test_step(profile: LanguageProfile) -> list[str]:
    """Render the test invocation step for a profile."""
    if not profile.test:
        return []
    return [
        f"      - name: Run {profile.label} tests",
        f"        run: {profile.test.run}",
    ]


def _format_lint_job(
    profile: LanguageProfile,
    pin_fn=None,
) -> str:
    """Render a complete `lint-<lang>` job body for a single profile.

    Returns the YAML body (the lines after the job name) as a single
    string with trailing newline. The caller prepends "  <name>:" and
    appends the job to the workflow.
    """
    setup = _format_setup_step(profile)
    linter = _format_linter_step(profile)

    steps: list[str] = []
    steps.extend([
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 15",
        "    continue-on-error: false",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_get_pinned_action('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
    ])
    steps.extend(setup)
    if linter:
        steps.append("")
        steps.extend(linter)
    return "\n".join(steps) + "\n"


def _format_test_job(
    profile: LanguageProfile,
) -> str:
    """Render a complete `test-<lang>` job body for a single profile."""
    setup = _format_setup_step(profile)
    install = _format_install_step(profile)
    test = _format_test_step(profile)

    steps: list[str] = []
    steps.extend([
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 15",
        "    continue-on-error: false",
        "    steps:",
        "      - name: Checkout code",
        f"        uses: {_get_pinned_action('actions/checkout@v4')}",
        "        with:",
        "          persist-credentials: false",
        "",
    ])
    steps.extend(setup)
    if install:
        steps.append("")
        steps.extend(install)
    if test:
        steps.append("")
        steps.extend(test)
    return "\n".join(steps) + "\n"


def render_lint_jobs(profiles: list[LanguageProfile]) -> list[tuple[str, str, str]]:
    """Render a list of `lint-<lang>` jobs for the given profiles.

    Returns a list of (job_name, job_body, reason) tuples ready to be
    appended to the workflow's jobs section.
    """
    out: list[tuple[str, str, str]] = []
    for p in profiles:
        if p.linter is None:
            continue
        job_name = f"lint-{p.id}"
        body = _format_lint_job(p)
        reason = (
            f"{p.label} detected; runs `{p.linter.run.split('||')[0].strip()}` "
            f"as a per-language linter. Multi-language monorepos get one "
            f"`lint-{p.id}` job per detected language."
        )
        out.append((job_name, body, reason))
    return out


def render_test_jobs(profiles: list[LanguageProfile]) -> list[tuple[str, str, str]]:
    """Render a list of `test-<lang>` jobs for the given profiles."""
    out: list[tuple[str, str, str]] = []
    for p in profiles:
        if p.test is None:
            continue
        job_name = f"test-{p.id}"
        body = _format_test_job(p)
        reason = (
            f"{p.label} tests; runs `{p.test.run.split('||')[0].strip()}`. "
            f"Multi-language monorepos get one `test-{p.id}` job per detected "
            f"language."
        )
        out.append((job_name, body, reason))
    return out


def has_tool_specific_sca(profiles: list[LanguageProfile]) -> list[LanguageProfile]:
    """Return profiles that need a tool-specific SCA job (e.g. pip-audit).

    Profiles with `sca.tool == "trivy"` are handled by the universal
    `dependency-scan` job and do not need their own SCA job.
    """
    return [p for p in profiles if p.sca.tool and p.sca.tool != "trivy"]

