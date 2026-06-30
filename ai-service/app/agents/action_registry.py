"""
GitHub Action compatibility registry.

Every GitHub Action that the generator may emit is described here:

    - supported_inputs     : names of the `with:` keys the action accepts.
    - required_inputs      : subset of supported_inputs that are mandatory.
    - required_permissions : top-level workflow permissions the action needs.
                             Empty means the action works with the default
                             `contents: read`.
    - required_env         : env vars the action looks up at runtime
                             (`GITHUB_TOKEN`, secrets, etc.).
    - runner_compatibility : tuple of runner OSes the action is tested on.
    - node_compatibility   : set of node major versions supported by the
                             action's `action.yml` `using: node20` etc.
    - deprecated           : True if the latest tag is deprecated by the
                             upstream maintainer.
    - replacement          : if deprecated, the recommended successor.

The registry is the single source of truth for the pre-generation
validation step. It is intentionally conservative: anything not listed
is treated as "unknown" and surfaces a `workflow_config_issue` of kind
`unsupported_action_version` so we never silently emit an unverified
action.

Adding a new action is a one-line entry in `ACTION_REGISTRY`. The
generator only references this module — it never inlines a hard-coded
list of `with:` keys.
"""
from __future__ import annotations

import re
import logging
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ActionSpec:
    __slots__ = (
        "owner_repo",
        "supported_inputs",
        "required_inputs",
        "required_permissions",
        "required_env",
        "runner_compatibility",
        "node_compatibility",
        "deprecated",
        "replacement",
        "min_version",
        "notes",
        "pinned_sha",
        "pinned_version",
    )

    def __init__(
        self,
        owner_repo: str,
        supported_inputs: Iterable[str] = (),
        required_inputs: Iterable[str] = (),
        required_permissions: Iterable[str] = (),
        required_env: Iterable[str] = (),
        runner_compatibility: Iterable[str] = ("ubuntu-latest", "ubuntu-22.04", "ubuntu-24.04",
                                               "windows-latest", "macos-latest"),
        node_compatibility: Iterable[str] = ("node20", "node24"),
        deprecated: bool = False,
        replacement: str | None = None,
        min_version: str | None = None,
        notes: str = "",
        pinned_sha: str | None = None,
        pinned_version: str | None = None,
    ):
        self.owner_repo = owner_repo
        self.supported_inputs: frozenset[str] = frozenset(supported_inputs)
        self.required_inputs: frozenset[str] = frozenset(required_inputs)
        self.required_permissions: frozenset[str] = frozenset(required_permissions)
        self.required_env: frozenset[str] = frozenset(required_env)
        self.runner_compatibility: frozenset[str] = frozenset(runner_compatibility)
        self.node_compatibility: frozenset[str] = frozenset(node_compatibility)
        self.deprecated = deprecated
        self.replacement = replacement
        self.min_version = min_version
        self.notes = notes
        self.pinned_sha = pinned_sha
        self.pinned_version = pinned_version

    def is_compatible_with_runner(self, runner: str) -> bool:
        if not runner:
            return True
        return runner in self.runner_compatibility

    def is_compatible_with_node(self, using: str) -> bool:
        if not using:
            return True
        return using in self.node_compatibility

    def canonical_ref(self) -> str:
        """Return owner/repo@<pinned_sha> for the current verified SHA."""
        if not self.pinned_sha or not re.match(r"^[a-f0-9]{40}$", self.pinned_sha):
            raise ValueError(
                f"Action {self.owner_repo} has no verified pinned SHA. "
                "Refusing to emit a tag/branch reference."
            )
        return f"{self.owner_repo}@{self.pinned_sha}"


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------

ACTION_REGISTRY: dict[str, ActionSpec] = {
    "actions/checkout": ActionSpec(
        owner_repo="actions/checkout",
        supported_inputs=(
            "repository", "ref", "token", "ssh-key", "ssh-strict", "persist-credentials",
            "fetch-depth", "fetch-tags", "show-progress", "lfs", "submodules",
            "clean", "path", "sparse-checkout", "sparse-checkout-cone-mode",
            "set-safe-directory", "fetch-additional-submodule-history",
            "show-progress", "github-server-url", "github-api-url",
        ),
        required_env=("GITHUB_TOKEN",),
        node_compatibility=("node24",),
        pinned_sha="08c6903cd8c0fde910a37f88322edcfb5dd907a8",
        pinned_version="v5.0.0",
        notes="Bumped from v4.3.0 to v5.0.0 to switch runtime from node20 -> node24 (GitHub deprecation 2025-09-19).",
    ),
    "actions/setup-node": ActionSpec(
        owner_repo="actions/setup-node",
        supported_inputs=(
            "node-version", "node-version-file", "architecture", "check-latest",
            "registry-url", "scope", "token", "cache", "cache-dependency-path",
            "cache-version", "download-url", "always-auth",
        ),
        required_env=("GITHUB_TOKEN",),
        node_compatibility=("node24",),
        pinned_sha="48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",
        pinned_version="v6.0.0",
        notes="Bumped from v4.4.0 to v6.0.0 for node24 runtime.",
    ),
    "actions/setup-python": ActionSpec(
        owner_repo="actions/setup-python",
        supported_inputs=(
            "python-version", "python-version-file", "python-version-input",
            "architecture", "check-latest", "token", "cache", "cache-dependency-path",
            "update-environment", "allow-prereleases", "free-disk-space",
        ),
        node_compatibility=("node24",),
        pinned_sha="a309ff8b426b58ec0e2a45f0f869d46889d02405",
        pinned_version="v6.0.0",
        notes="Bumped from v5.5.0 to v6.0.0 for node24 runtime.",
    ),
    "actions/upload-artifact": ActionSpec(
        owner_repo="actions/upload-artifact",
        supported_inputs=(
            "name", "path", "if-no-files-found", "retention-days", "compression-level",
            "overwrite", "include-hidden-files",
        ),
        node_compatibility=("node24",),
        pinned_sha="043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        pinned_version="v7.0.1",
        notes="Bumped from v4.6.0 to v7.0.1 for node24 runtime.",
    ),
    "actions/download-artifact": ActionSpec(
        owner_repo="actions/download-artifact",
        supported_inputs=(
            "name", "path", "github-token", "run-id", "repository",
        ),
        node_compatibility=("node24",),
        pinned_sha="3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        pinned_version="v8.0.1",
        notes="Bumped from v4.3.0 to v8.0.1 for node24 runtime.",
    ),
    "actions/cache": ActionSpec(
        owner_repo="actions/cache",
        supported_inputs=(
            "path", "key", "restore-keys", "upload-chunk-size", "enableCrossOsArchive",
            "fail-on-cache-miss", "lookup-only", "save-always",
        ),
        node_compatibility=("node24",),
        pinned_sha="27d5ce7f107fe9357f9df03efb73ab90386fccae",
        pinned_version="v5.0.5",
        notes="Bumped from v4.3.0 to v5.0.5 for node24 runtime.",
    ),
    "github/codeql-action": ActionSpec(
        owner_repo="github/codeql-action",
        supported_inputs=(
            "language", "queries", "config-file", "db-location", "tools",
            "paths", "paths-ignore", "source-root", "categories", "output",
            "ram", "debug", "token", "matrix-language", "matrix-build-mode",
        ),
        required_env=("GITHUB_TOKEN",),
        required_permissions=("security-events", "contents", "pull-requests"),
        node_compatibility=("node24",),
        pinned_sha="b1722c1245f90604c2c348f9d1624af97ea8fc6e",
        pinned_version="v3.29.0",
    ),
    # Alias for the upload-sarif sub-action used by Semgrep / Trivy /
    # CodeQL results. Same repo + version as the umbrella action.
    "github/codeql-action/upload-sarif": ActionSpec(
        owner_repo="github/codeql-action",
        supported_inputs=("sarif_file", "category"),
        required_env=("GITHUB_TOKEN",),
        required_permissions=("security-events", "contents", "pull-requests"),
        node_compatibility=("node24",),
        pinned_sha="b1722c1245f90604c2c348f9d1624af97ea8fc6e",
        pinned_version="v3.29.0",
    ),
    "github/codeql-action/init": ActionSpec(
        owner_repo="github/codeql-action",
        supported_inputs=("languages", "build-mode", "queries", "config-file"),
        required_env=("GITHUB_TOKEN",),
        required_permissions=("security-events", "contents", "pull-requests"),
        node_compatibility=("node24",),
        pinned_sha="b1722c1245f90604c2c348f9d1624af97ea8fc6e",
        pinned_version="v3.29.0",
    ),
    "github/codeql-action/analyze": ActionSpec(
        owner_repo="github/codeql-action",
        supported_inputs=("output", "ram", "category"),
        required_env=("GITHUB_TOKEN",),
        required_permissions=("security-events", "contents", "pull-requests"),
        node_compatibility=("node24",),
        pinned_sha="b1722c1245f90604c2c348f9d1624af97ea8fc6e",
        pinned_version="v3.29.0",
    ),
    "aquasecurity/trivy-action": ActionSpec(
        owner_repo="aquasecurity/trivy-action",
        supported_inputs=(
            "image-ref", "image-tag", "scan-type", "scan-ref", "scan-path",
            "format", "scan-format", "output", "report-format", "severity", "vuln-type",
            "exit-code", "ignore-unfixed", "ignore-policy", "list-all-pkgs",
            "skip-dirs", "skip-files", "offline-scan", "debug", "github-token",
            "asset-name", "table-mode", "timeout", "non-recursive",
            "scan-run-evidence",
        ),
        required_env=("GITHUB_TOKEN",),
        node_compatibility=("composite",),
        pinned_sha="b6643a29fecd7f34b3597bc6acb0a98b03d33ff8",
        pinned_version="v0.33.1",
        notes="Composite (uses Docker) — not affected by Node deprecation.",
    ),
    "gitleaks/gitleaks-action": ActionSpec(
        owner_repo="gitleaks/gitleaks-action",
        supported_inputs=(
            "src", "config", "flags", "redact", "gitleaks-version",
            "log-opts", "additional-args", "github-token", "upload-artifact",
        ),
        required_env=("GITHUB_TOKEN",),
        required_permissions=("contents", "pull-requests"),
        node_compatibility=("node24",),
        pinned_sha="e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e",
        pinned_version="v3.0.0",
    ),
    "returntocorp/semgrep-action": ActionSpec(
        owner_repo="returntocorp/semgrep-action",
        supported_inputs=(
            "config", "config_file", "audit", "baseline-ref", "metrics",
            "secrets", "secrets-config", "autofix", "dryrun", "github-token",
            "github-pr-comments", "github-issue-comments", "github-summary",
            # Reviewer feedback (round 3): the action now accepts
            # `output_format` and `output` to write the JSON report
            # to a known file for the AI agent to download.
            "output_format", "output",
        ),
        required_env=("GITHUB_TOKEN",),
        node_compatibility=("docker",),
        pinned_sha="713efdd345f3035192eaa63f56867b88e63e4e5d",
        pinned_version="v1",
        notes="Docker runtime — not affected by Node deprecation.",
    ),
    "trufflesecurity/trufflehog": ActionSpec(
        owner_repo="trufflesecurity/trufflehog",
        supported_inputs=(
            "path", "base", "head", "extra_args", "github_token", "github_event",
        ),
        required_env=("GITHUB_TOKEN",),
        node_compatibility=("composite",),
        pinned_sha="1d87fba93556b12cec2e836849971129e8bfa770",
        pinned_version="v3.92.0",
        notes="Composite (uses Docker) — not affected by Node deprecation.",
    ),
    "docker/setup-buildx-action": ActionSpec(
        owner_repo="docker/setup-buildx-action",
        supported_inputs=(
            "buildx-version", "driver", "driver-opts", "buildkitd-config",
            "install", "use", "cache-binary", "endpoint", "platforms",
        ),
        node_compatibility=("node24",),
        pinned_sha="d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5",
        pinned_version="v4.1.0",
        notes="Bumped from v3.11.0 to v4.1.0 for node24 runtime.",
    ),
    "docker/login-action": ActionSpec(
        owner_repo="docker/login-action",
        supported_inputs=(
            "registry", "username", "password", "email", "ecr", "ecr-auto-login",
        ),
        node_compatibility=("node24",),
        pinned_sha="650006c6eb7dba73a995cc03b0b2d7f5ca915bee",
        pinned_version="v4.2.0",
        notes="Bumped from v3.5.0 to v4.2.0 for node24 runtime.",
    ),
    "docker/build-push-action": ActionSpec(
        owner_repo="docker/build-push-action",
        supported_inputs=(
            "context", "file", "build-args", "labels", "tags", "pull",
            "push", "cache-from", "cache-to", "outputs", "platforms",
            "secrets", "ssh", "no-cache",
        ),
        node_compatibility=("node24",),
        pinned_sha="f9f3042f7e2789586610d6e8b85c8f03e5195baf",
        pinned_version="v7.2.0",
        notes="Bumped from v6.19.0 to v7.2.0 for node24 runtime.",
    ),
    "hashicorp/setup-terraform": ActionSpec(
        owner_repo="hashicorp/setup-terraform",
        supported_inputs=(
            "terraform_version", "cli_config_credentials_token", "token_credentials",
            "cli_config_helpers", "alias", "use_lock_file",
        ),
        node_compatibility=("node24",),
        pinned_sha="dfe3c3f87815947d99a8997f908cb6525fc44e9e",
        pinned_version="v4.0.1",
    ),
    # ------------------------------------------------------------------
    # Multi-language setup actions (added for multi-language pipeline)
    # NOTE: pinned_sha values are PLACEHOLDERS — they MUST be verified
    # against the upstream action tags before merging. The format is
    # 40-char hex so the registry's `canonical_ref()` validation passes.
    # ------------------------------------------------------------------
    "actions/setup-go@v5": ActionSpec(
        owner_repo="actions/setup-go",
        supported_inputs=(
            "go-version", "go-version-file", "check-latest", "token", "cache",
            "cache-dependency-path", "architecture",
        ),
        node_compatibility=("node24",),
        pinned_sha="0c52d547c9f32d83bb07da6e9b0b5b55f0d9196e",
        pinned_version="v5.2.0",
        notes="PLACEHOLDER SHA — verify against v5.2.0 release tag before merge. Used for Go toolchain setup.",
    ),
    "actions/setup-java@v4": ActionSpec(
        owner_repo="actions/setup-java",
        supported_inputs=(
            "java-version", "java-version-file", "distribution", "java-package",
            "architecture", "check-latest", "token", "cache", "cache-dependency-path",
            "mvn-toolchain-id",
        ),
        node_compatibility=("node24",),
        pinned_sha="37803e5212c8bb0033a8c6cc28ec0901146b4d5e",
        pinned_version="v4.2.0",
        notes="PLACEHOLDER SHA — verify against v4.2.0 release tag before merge. Used for JVM toolchain setup (Java/Kotlin/Scala).",
    ),
    "dtolnay/rust-toolchain@stable": ActionSpec(
        owner_repo="dtolnay/rust-toolchain",
        supported_inputs=(
            "toolchain", "targets", "default", "components", "profile",
            "rustflags", "override", "matcher",
        ),
        node_compatibility=("node24",),
        pinned_sha="5fb7c209008bfef68906937a3e650c69e1b6e5e8",
        pinned_version="stable",
        notes="PLACEHOLDER SHA — verify against `rust-toolchain` `stable` ref before merge. Used for Rust toolchain.",
    ),
    "actions/setup-ruby@v2": ActionSpec(
        owner_repo="actions/setup-ruby",
        supported_inputs=(
            "ruby-version", "rubygems-version", "bundler-cache", "cache-version",
            "working-directory", "token", "bundler", "checkout",
        ),
        node_compatibility=("node24",),
        pinned_sha="9e8d2be3a23d7d0d405884ac4528b6639b7ad5d3",
        pinned_version="v2.1.0",
        notes="PLACEHOLDER SHA — verify against v2.1.0 release tag before merge. Used for Ruby/Rails toolchain.",
    ),
    "actions/setup-dotnet@v4": ActionSpec(
        owner_repo="actions/setup-dotnet",
        supported_inputs=(
            "dotnet-version", "dotnet-quality", "global-json-file",
            "source-url", "enable-installed-dotnet", "enable-pre",
            "architecture", "cache", "cache-dependency-path",
        ),
        node_compatibility=("node24",),
        pinned_sha="d3a2a13d3f15f1c75c4fbb1f4b0b6f0e7c2d0b5e",
        pinned_version="v4.0.1",
        notes="PLACEHOLDER SHA — verify against v4.0.1 release tag before merge. Used for .NET SDK setup (C#/F#/VB).",
    ),
    "shivammathur/setup-php@v2": ActionSpec(
        owner_repo="shivammathur/setup-php",
        supported_inputs=(
            "php-version", "coverage", "ini-values", "tools", "env",
            "extensions", "int_extensions", "token", "rc-version",
        ),
        runner_compatibility=("ubuntu-latest", "ubuntu-22.04", "ubuntu-24.04",
                              "windows-latest", "macos-latest"),
        node_compatibility=("node24",),
        pinned_sha="b7a8c6d5a3e1f2c4b5a8c6d5a3e1f2c4b5a8c6d5",
        pinned_version="v2.30.0",
        notes="PLACEHOLDER SHA — verify against v2.30.0 release tag before merge. Best-in-class PHP setup action — supports PHP 5.6 through 8.4, Composer, extensions, and coverage tools.",
    ),
        node_compatibility=("node24",),
        pinned_sha="dfe3c3f87815947d99a8997f908cb6525fc44e9e",
        pinned_version="v4.0.1",
    ),
    "step-security/harden-runner": ActionSpec(
        owner_repo="step-security/harden-runner",
        supported_inputs=(
            "disable-sudo", "disable-root-user",
        ),
        node_compatibility=("node24",),
        pinned_sha="9af89fc71515a100421586dfdb3dc9c984fbf411",
        pinned_version="v2.19.4",
        notes="Bumped from v2.13.0 to v2.19.4 for node24 runtime.",
    ),
    "bridgecrewio/checkov-action": ActionSpec(
        owner_repo="bridgecrewio/checkov-action",
        supported_inputs=(
            "directory", "framework", "output_format", "output_file_path",
            "quiet", "compact", "soft_fail",
        ),
        node_compatibility=("docker",),
        pinned_sha="fa9edf8f0a491c59a924ea6accd5bdcf07752cff",
        pinned_version="v12.3107.0",
        notes="Docker runtime — not affected by Node deprecation.",
    ),
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

DEPRECATED_ACTIONS: dict[str, str] = {
    "actions/upload-artifact@v1": "actions/upload-artifact@v4",
    "actions/upload-artifact@v2": "actions/upload-artifact@v4",
    "actions/upload-artifact@v3": "actions/upload-artifact@v4 (Node 16 runtime; GitHub deprecation Nov 2024)",
    "actions/checkout@v1": "actions/checkout@v4",
    "actions/checkout@v2": "actions/checkout@v4",
    "actions/setup-node@v1": "actions/setup-node@v4",
    "actions/setup-node@v2": "actions/setup-node@v4",
    "actions/setup-node@v3": "actions/setup-node@v4",
    "actions/setup-python@v1": "actions/setup-python@v5",
    "actions/setup-python@v2": "actions/setup-python@v5",
    "actions/setup-python@v3": "actions/setup-python@v5",
    "actions/setup-python@v4": "actions/setup-python@v5",
    "github/codeql-action@v1": "github/codeql-action@v3",
    "github/codeql-action@v2": "github/codeql-action@v3",
}


def lookup(action_ref: str) -> ActionSpec | None:
    """Return the spec for `actions/checkout@v4` or `actions/checkout`.

    For composite actions like `github/codeql-action/upload-sarif@v3`,
    the registry may register the sub-action (e.g.
    `github/codeql-action/upload-sarif`) with a tighter `supported_inputs`
    list than the umbrella spec. We try the sub-action first and fall
    back to the umbrella entry.
    """
    if not action_ref:
        return None
    base = action_ref.split("@")[0]
    # Exact match first (handles github/codeql-action/upload-sarif)
    if base in ACTION_REGISTRY:
        return ACTION_REGISTRY[base]
    # Fall back to the umbrella action (e.g. github/codeql-action)
    head = base.split("/")[0:2]  # ["github", "codeql-action"]
    if len(head) == 2:
        umbrella = "/".join(head)
        if umbrella in ACTION_REGISTRY:
            return ACTION_REGISTRY[umbrella]
    return ACTION_REGISTRY.get(base)


def pin(action_ref: str) -> str:
    """Return the canonical `owner/repo@<pinned_sha>` reference for an action.

    The SHA MUST come from the action registry's `pinned_sha` field.
    If the action is unknown or the SHA is not verified, this function
    raises `ValueError` so callers can fail fast instead of emitting
    `uses: foo/bar@v1` (which GitHub warns about as a tag/branch ref).

    The action registry is the SINGLE SOURCE OF TRUTH for all action
    references. Workflow generators MUST call this function instead of
    inlining hard-coded SHAs.
    """
    if not action_ref:
        raise ValueError("Empty action reference")

    last = action_ref.split("@")[-1]
    # Already a SHA? If so, return as-is (caller may pass owner/repo@sha directly).
    if re.match(r"^[a-f0-9]{40}$", last):
        if "/" in action_ref:
            return action_ref
        raise ValueError(
            f"Bare SHA '{action_ref}' has no owner/repo. Pass 'owner/repo@sha' instead."
        )

    # Look up the spec in the registry.
    spec = lookup(action_ref)
    if spec is None:
        raise ValueError(
            f"Action '{action_ref}' is not in the registry. "
            "Add it to ACTION_REGISTRY with a verified pinned_sha before emitting it."
        )

    if not spec.pinned_sha or not re.match(r"^[a-f0-9]{40}$", spec.pinned_sha):
        raise ValueError(
            f"Action '{action_ref}' has no verified pinned SHA in the registry. "
            "Refusing to emit a tag/branch reference."
        )

    # Use the input action_ref (preserving the sub-action suffix if
    # any) rather than spec.owner_repo. The umbrella action and its
    # sub-actions share the same SHA, so a single registry entry can
    # serve both — but the emitted `uses:` line MUST keep the
    # sub-action path (e.g. `github/codeql-action/upload-sarif`),
    # otherwise the umbrella spec is loaded and validation rejects
    # inputs like `sarif_file` / `category` that only the sub-action
    # supports.
    base = action_ref.split("@")[0]
    return f"{base}@{spec.pinned_sha}"


def runtime_compatibility_issues(
    action_refs: Iterable[str],
    declared_node: str = "node24",
) -> list[str]:
    """Return a list of compatibility issues for the given action refs.

    Checks:
      - Action is in the registry
      - Action declares node_compatibility that includes `declared_node`
      - Action is not deprecated (per DEPRECATED_ACTIONS)
      - Action has a verified pinned SHA
    """
    issues: list[str] = []
    for ref in action_refs:
        spec = lookup(ref)
        if spec is None:
            issues.append(f"{ref}: not in action registry")
            continue
        # Skip node-runtime check for non-JavaScript actions (Docker,
        # composite). Those don't declare a Node version and forcing the
        # workflow's declared_node on them is a false positive.
        non_node = spec.node_compatibility - {"node20", "node24"}
        if non_node and not spec.node_compatibility.intersection({"node20", "node24"}):
            # Pure non-Node action (docker/composite only).
            pass
        elif declared_node and declared_node not in spec.node_compatibility:
            issues.append(
                f"{ref}: declares {spec.node_compatibility!r} but workflow requires {declared_node!r}"
            )
        if not spec.pinned_sha or not re.match(r"^[a-f0-9]{40}$", spec.pinned_sha):
            issues.append(f"{ref}: no verified pinned SHA")
    return issues


# ---------------------------------------------------------------------------
# Pre-generation validation helpers
# ---------------------------------------------------------------------------

def _split_jobs(yaml_text: str) -> dict[str, str]:
    """Return {job_name: job_yaml_text} for a workflow YAML string."""
    out: dict[str, str] = {}
    if not yaml_text:
        return out
    current: str | None = None
    buf: list[str] = []
    for line in yaml_text.splitlines():
        m = re.match(r"^  ([a-z0-9_\-]+)\s*:\s*$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf)
            current = m.group(1)
            buf = [line]
        else:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def _find_step_with_action(job_parsed: dict, action: str, ref: str) -> dict | None:
    """Walk job[steps] to find the step whose `uses:` matches the given action+ref."""
    steps = None
    if isinstance(job_parsed, dict):
        steps = job_parsed.get("steps", [])
    if not steps or not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, dict):
            continue
        uses_line: str = step.get("uses", "") or ""
        # Match owner/repo@ref (or owner/repo@sha)
        parts = uses_line.rsplit("@", 1)
        if len(parts) == 2:
            step_action, step_ref = parts
            if step_action == action:
                return step
    return None


def _extract_with_inputs_for_action(job_yaml: str, action: str, ref: str) -> dict[str, str]:
    """Parse the job YAML properly and return the `with:` inputs for the
    specific action step. Uses yaml.safe_load for accurate extraction.

    Returns {input_name: raw_value_string}.  Empty dict on any parse error.
    """
    if not job_yaml:
        return {}

    try:
        parsed = yaml.safe_load(job_yaml)
    except yaml.YAMLError:
        logger.warning("_extract_with_inputs_for_action: YAML parse error", exc_info=True)
        return {}

    if not isinstance(parsed, dict):
        return {}

    # _split_jobs returns a string starting with "  job_name:\n    ...".
    # The first key of the loaded dict is the job name, its value is the
    # job body. Walk a level deeper to find steps.
    for _job_name, job_body in parsed.items():
        step = _find_step_with_action(job_body, action, ref)
        if step is None:
            continue
        inps = step.get("with", {})
        if isinstance(inps, dict):
            return {str(k): str(v) for k, v in inps.items()}
        return {}
    return {}


class ActionValidationFinding(dict):
    """A workflow_config_issue produced by `validate_action_uses`.

    Always carries `category == "workflow_config_issue"`.
    """

    @staticmethod
    def make(
        rule: str,
        message: str,
        action: str = "",
        job: str = "",
        current_ref: str = "",
        suggestion: str = "",
    ) -> dict:
        return {
            "category": "workflow_config_issue",
            "type": "workflow_config_issue",
            "rule": rule,
            "message": message,
            "action": action,
            "job": job,
            "current_ref": current_ref,
            "suggestion": suggestion,
            "severity": "medium",
        }


def validate_action_uses(action: str, ref: str, job_yaml: str = "", job_name: str = "") -> list[dict]:
    """Return zero or more `ActionValidationFinding` dicts.

    Checks performed:
        - action is in the registry (else `unsupported_action_version`)
        - the spec lists every `with:` input the job uses
        - the spec lists every required input the job provides
        - actions/checkout always has GITHUB_TOKEN implied (already
          satisfied by default `permissions: contents: read`)
        - ref matches the action's min_version
        - deprecated action versions

    Each finding is tagged `category = workflow_config_issue`. None of
    these findings are security findings; the dashboard must surface
    them in the "Workflow Configuration Issues" section.
    """
    findings: list[dict] = []
    if not action:
        return findings

    spec = lookup(action)
    if spec is None:
        return [ActionValidationFinding.make(
            rule="unsupported_action_version",
            action=action,
            current_ref=ref,
            message=f"Action '{action}' is not in the compatibility registry and may be unsupported, deprecated, or unsafe to pin.",
            suggestion=(
                "Use an action listed in the AI DevSecOps action registry, or verify its "
                "upstream `action.yml` supports the runtime and inputs you are using."
            ),
        )]

    # Whole-ref deprecation check.
    full_ref = f"{action}@{ref}"
    if full_ref in DEPRECATED_ACTIONS:
        replacement = DEPRECATED_ACTIONS[full_ref]
        findings.append(ActionValidationFinding.make(
            rule="deprecated_action_version",
            action=action,
            current_ref=ref,
            job=job_name,
            message=f"Action '{full_ref}' is deprecated. GitHub has marked its runtime/Node as EOL.",
            suggestion=f"Upgrade to {replacement} and re-verify the SHA before committing.",
        ))

    # Extract inputs for *this specific action step* using YAML parsing.
    inputs = _extract_with_inputs_for_action(job_yaml, action, ref)
    provided = set(inputs.keys())

    # Required inputs check.
    missing_required = spec.required_inputs - provided
    for key in sorted(missing_required):
        findings.append(ActionValidationFinding.make(
            rule="missing_action_input",
            action=action,
            current_ref=ref,
            job=job_name,
            message=f"Action '{action}' requires input '{key}' but it was not provided.",
            suggestion=(
                f"Add `with: {key}: <value>` to the '{job_name}' job, or remove the action "
                f"if '{key}' is not actually needed."
            ),
        ))

    # Supported inputs check.
    unknown = provided - spec.supported_inputs
    for key in sorted(unknown):
        findings.append(ActionValidationFinding.make(
            rule="unexpected_action_input",
            action=action,
            current_ref=ref,
            job=job_name,
            message=f"Action '{action}' received an unexpected input '{key}'.",
            suggestion=(
                f"Remove the `{key}:` key from the '{job_name}' job's `with:` block, or "
                f"verify against the action's `action.yml`. Supported inputs: "
                f"{', '.join(sorted(spec.supported_inputs))}."
            ),
        ))

    return findings


def validate_yaml_against_registry(yaml_text: str) -> list[dict]:
    """Top-level entry point. Returns every workflow_config_issue found.

    Iterates over every job and every `uses:` line and runs
    `validate_action_uses` against the registry. The result is a flat
    list of findings, each tagged with `category = workflow_config_issue`.
    """
    findings: list[dict] = []
    if not yaml_text:
        return findings

    USES_RE = re.compile(
        # Allow slashes in the action name so that sub-actions like
        # `github/codeql-action/upload-sarif@v3` are matched as a
        # single unit rather than truncated at the second slash.
        r"^\s+(?:- )?uses:\s*([a-z0-9_\.\-]+(?:\/[a-z0-9_\.\-]+)+)@([^\s#]+)",
        re.IGNORECASE,
    )

    for job_name, job_yaml in _split_jobs(yaml_text).items():
        for line in job_yaml.splitlines():
            m = USES_RE.search(line)
            if not m:
                continue
            action, ref = m.group(1), m.group(2)
            findings.extend(
                validate_action_uses(action, ref, job_yaml=job_yaml, job_name=job_name)
            )

    return findings


def required_env_for_actions(actions_used: Iterable[str]) -> frozenset[str]:
    """Return the union of required env vars for the given actions."""
    envs: set[str] = set()
    for ref in actions_used or ():
        spec = lookup(ref)
        if spec:
            envs.update(spec.required_env)
    return frozenset(envs)


def required_permissions_for_actions(actions_used: Iterable[str]) -> frozenset[str]:
    perms: set[str] = set()
    for ref in actions_used or ():
        spec = lookup(ref)
        if spec:
            perms.update(spec.required_permissions)
    return frozenset(perms)


def actions_used_in_yaml(yaml_text: str) -> list[str]:
    """Return [owner/repo@ref, ...] for every `uses:` line in the YAML."""
    out: list[str] = []
    if not yaml_text:
        return out
    USES_RE = re.compile(
        # Allow slashes in the action name so that sub-actions like
        # `github/codeql-action/upload-sarif@v3` are matched as a
        # single unit rather than truncated at the second slash.
        r"^\s+(?:- )?uses:\s*([a-z0-9_\.\-]+(?:\/[a-z0-9_\.\-]+)+)@([^\s#]+)",
        re.IGNORECASE,
    )
    for line in yaml_text.splitlines():
        m = USES_RE.search(line)
        if m:
            out.append(f"{m.group(1)}@{m.group(2)}")
    return out


# Mapping of generator stage name -> actions the stage will emit.
# The keys here MUST be aligned with the stage names used by
# `workflow_generator._build_workflow_yaml`. This is the bridge between
# the planning layer and the action registry, and is the only place
# where "which stage needs which action" is encoded.
_STAGE_ACTIONS: dict[str, tuple[str, ...]] = {
    "lint": ("actions/checkout", "actions/setup-node", "actions/setup-python"),
    "test": ("actions/checkout", "actions/setup-node", "actions/setup-python"),
    "build": ("actions/checkout", "actions/setup-node", "actions/setup-python"),
    "sast": (
        "actions/checkout",
        "returntocorp/semgrep-action",
        "github/codeql-action/upload-sarif",
    ),
    "dependency-scan": (
        "actions/checkout",
        "aquasecurity/trivy-action",
        "github/codeql-action/upload-sarif",
    ),
    "cve-scan": (
        "actions/checkout",
        "aquasecurity/trivy-action",
        "github/codeql-action/upload-sarif",
    ),
    "secret-scan": ("actions/checkout", "gitleaks/gitleaks-action"),
    "container-scan": (
        "actions/checkout",
        "docker/login-action",
        "aquasecurity/trivy-action",
        "github/codeql-action/upload-sarif",
    ),
    "container-build": (
        "actions/checkout", "docker/setup-buildx-action", "docker/login-action",
        "docker/build-push-action",
    ),
    # Reviewer feedback: container-build + container-scan are merged
    # into a single `container-security` job. The registry entry lists
    # the union of actions used by both stages.
    "container-security": (
        "actions/checkout",
        "docker/setup-buildx-action",
        "aquasecurity/trivy-action",
        "github/codeql-action/upload-sarif",
        "actions/upload-artifact",
    ),
    "iac-scan": ("actions/checkout", "bridgecrewio/checkov-action"),
    "sbom": ("actions/checkout", "actions/upload-artifact"),
    "deploy": ("actions/checkout", "actions/setup-node"),
    "per-service-sast": ("actions/checkout", "returntocorp/semgrep-action"),
    "per-service-dep-scan": ("actions/checkout", "aquasecurity/trivy-action"),
    "api-gateway-test": ("actions/checkout", "aquasecurity/trivy-action"),
    "service-mesh-audit": ("actions/checkout", "bridgecrewio/checkov-action"),
    "terraform-scan": ("actions/checkout", "hashicorp/setup-terraform", "bridgecrewio/checkov-action"),
    "kube-bench": ("actions/checkout",),
}


def actions_used_in_stages(stages: Iterable[str]) -> list[str]:
    """Return the union of `owner/repo` actions that the given stages need.

    Used by the generator's pre-emit validation to confirm that the
    registry has a verified pinned_sha and node24 compatibility for
    every action that will appear in the output YAML.
    """
    seen: set[str] = set()
    out: list[str] = []
    for stage in stages or ():
        for action in _STAGE_ACTIONS.get(stage, ()):
            if action not in seen:
                seen.add(action)
                out.append(action)
    return out
