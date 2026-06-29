import base64

from app.agents.pipeline_state import PipelineEngineerState
from app.config import settings
from app.services.github_service import get_github_client

KEY_CONFIG_FILES = [
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "Pipfile", "Pipfile.lock", "pyproject.toml", "poetry.lock",
    "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.build",
    "Cargo.toml", "Cargo.lock",
    "Gemfile", "Gemfile.lock",
    "composer.json", "composer.lock",
    "*.csproj", "*.sln",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile",
    ".github/workflows/",
    "docker/", "k8s/", "kubernetes/", "helm/", "Chart.yaml",
    "*.tf", "*.tfvars",
    "serverless.yml", "serverless.yaml",
    ".env.example", ".env.sample",
    "tsconfig.json", "tsconfig.build.json",
    "webpack.config.js", "vite.config.ts", "vite.config.js",
    "next.config.js", "nuxt.config.js",
    "terraform/",
]

SOURCE_EXTENSIONS = {
    ".js", ".ts", ".jsx", ".tsx", ".py", ".go", ".java", ".php", ".rb",
    ".cs", ".swift", ".kt", ".rs", ".vue", ".svelte", ".c", ".cpp", ".h",
}

MAX_SOURCE_FILES = 30
MAX_FILE_SIZE = 50000


def repository_scan_node(state: PipelineEngineerState) -> PipelineEngineerState:
    if state.get("errors"):
        return state

    repo_full_name = state.get("repository_full_name", "")
    github_token = state.get("github_token", "") or settings.GITHUB_TOKEN

    try:
        gh = get_github_client(github_token)
        repo = gh.get_repo(repo_full_name)

        structure = _get_repo_tree(gh, repo_full_name)
        key_files = _get_key_files(gh, repo_full_name, KEY_CONFIG_FILES)
        existing_workflows = _get_workflows(gh, repo_full_name)
        source_files = _get_source_files_recursive(gh, repo_full_name)

        state["repository_structure"] = structure
        state["repository_files"] = key_files
        state["existing_workflows"] = existing_workflows
        state["source_files"] = source_files

        print(f"[DEBUG] Repository: {repo_full_name}")
        print(f"[DEBUG] Structure count: {len(structure)}")
        docker_files = [x for x in structure if 'dockerfile' in x.get('name', '').lower() or '/docker/' in x.get('path', '').lower()]
        k8s_files = [x for x in structure if 'k8s' in x.get('path', '').lower() or 'kubernetes' in x.get('path', '').lower()]
        tf_files = [x for x in structure if x.get('name', '').endswith('.tf') or '/terraform/' in x.get('path', '').lower()]
        print(f"[DEBUG] Docker files: {len(docker_files)}")
        print(f"[DEBUG] K8s files: {len(k8s_files)}")
        print(f"[DEBUG] Terraform files: {len(tf_files)}")

    except Exception as e:
        state["errors"].append(f"Repository scan failed: {e}")
        state["error_stage"] = "scan"

    return state


def _get_repo_tree(gh, repo_full_name: str) -> list:
    try:
        repo = gh.get_repo(repo_full_name)
        contents = repo.get_contents("")
        tree = []
        for item in contents:
            tree.append({
                "name": item.name,
                "path": item.path,
                "type": item.type,
            })
            # First-level subdirs that are common service layouts
            # (frontend/backend split, monorepo, microservice, etc.).
            # Recursing into ALL of them is too expensive on large
            # repos, but we at least want to surface top-level
            # subdirectories in the structure list so the LLM-based
            # technology detection can see a `client/` or `server/`
            # directory exists, and so `_has_frontend_backend_split`
            # in workflow_generator can find the side manifests.
            if item.type == "dir":
                if item.name in (
                    "docker", "k8s", "kubernetes", "terraform", "src",
                    "helm", "client", "server", "frontend", "backend",
                    "api", "web", "app", "services", "packages",
                    "apps", "libs", "modules",
                ):
                    sub_contents = _get_dir_contents(gh, repo_full_name, item.path)
                    for sub in sub_contents:
                        tree.append(sub)
        return tree
    except Exception:
        return []


def _get_dir_contents(gh, repo_full_name: str, path: str, depth: int = 0) -> list:
    """Recursively get directory contents for key directories.

    The recursive call is capped at depth=2 so a single call cannot
    blow up on a large monorepo. Most service layout directories
    (e.g. `client/src/components/...`) only need 1-2 levels of
    subdir enumeration for the LLM technology detection to make a
    confident decision.
    """
    result = []
    if depth > 2:
        return result
    try:
        contents = gh.get_repo(repo_full_name).get_contents(path)
        for item in contents:
            result.append({
                "name": item.name,
                "path": item.path,
                "type": item.type,
            })
            if item.type == "dir" and item.name in (
                "auth", "gateway", "common", "namespace", "notification",
                "order", "payment", "product", "user", "src",
                "controller", "model", "models", "routes", "view", "views",
                "components", "pages", "public", "middleware", "utils",
                "services", "database", "config", "constants",
            ):
                sub = _get_dir_contents(gh, repo_full_name, item.path, depth=depth + 1)
                result.extend(sub)
    except Exception:
        pass
    return result


# Top-level subdirectory names that look like a service boundary.
# When `_get_key_files` finds a `package.json` (or any other manifest)
# inside one of these, the file is captured with its full path so the
# technology detection can see the manifests and infer the per-service
# language / framework. Without this, repos with the classic
# `client/` + `server/` split report "Language: Unknown" because the
# root-level `package.json` does not exist.
_SERVICE_BOUNDARY_DIRS: tuple[str, ...] = (
    "client", "server", "frontend", "backend", "api", "web",
    "app", "services", "packages", "apps", "libs", "modules",
    "src", "admin", "worker", "gateway",
)
_SERVICE_BOUNDARY_MANIFESTS: tuple[str, ...] = (
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "pyproject.toml", "Pipfile", "poetry.lock",
    "go.mod", "Cargo.toml", "Gemfile", "composer.json",
    "tsconfig.json", "tsconfig.build.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile",
)


def _get_key_files(gh, repo_full_name: str, patterns: list) -> dict:
    repo = gh.get_repo(repo_full_name)
    files = {}
    for pattern in patterns:
        try:
            if pattern.endswith("/"):
                if pattern.rstrip("/") in ("docker", "k8s", "kubernetes", "terraform", "helm"):
                    subdir_files = _get_files_in_dir(gh, repo_full_name, pattern.rstrip("/"), [".tf", ".yaml", ".yml", ".json"])
                    files.update(subdir_files)
                continue
            content = repo.get_contents(pattern)
            if content.encoding == "base64":
                decoded = base64.b64decode(content.content).decode("utf-8", errors="replace")
            else:
                decoded = content.decoded_content.decode("utf-8", errors="replace")
            files[pattern] = decoded[:MAX_FILE_SIZE]
        except Exception:
            pass

    # Also probe every top-level subdirectory that looks like a
    # service boundary (client/, server/, frontend/, backend/, api/,
    # services/, ...). For each such subdir, look for a known
    # manifest at the top of that subdir. This is what enables
    # `client/package.json` and `server/package.json` to be picked up
    # so the technology detection can identify the languages in a
    # repo with a FE+BE split.
    try:
        for item in repo.get_contents(""):
            if item.type != "dir":
                continue
            if item.name not in _SERVICE_BOUNDARY_DIRS:
                continue
            for manifest in _SERVICE_BOUNDARY_MANIFESTS:
                manifest_path = f"{item.name}/{manifest}"
                if manifest_path in files:
                    continue  # already captured by the root-level probe
                try:
                    content = repo.get_contents(manifest_path)
                    if content.encoding == "base64":
                        decoded = base64.b64decode(content.content).decode("utf-8", errors="replace")
                    else:
                        decoded = content.decoded_content.decode("utf-8", errors="replace")
                    files[manifest_path] = decoded[:MAX_FILE_SIZE]
                except Exception:
                    pass
    except Exception:
        pass

    return files


def _get_files_in_dir(gh, repo_full_name: str, path: str, extensions: list) -> dict:
    """Get files with specific extensions from a directory recursively."""
    files = {}
    try:
        contents = gh.get_repo(repo_full_name).get_contents(path)
        for item in contents:
            if item.type == "dir":
                files.update(_get_files_in_dir(gh, repo_full_name, item.path, extensions))
            else:
                for ext in extensions:
                    if item.name.lower().endswith(ext):
                        try:
                            if item.encoding == "base64":
                                decoded = base64.b64decode(item.content).decode("utf-8", errors="replace")
                            else:
                                decoded = item.decoded_content.decode("utf-8", errors="replace")
                            files[item.path] = decoded[:MAX_FILE_SIZE]
                        except Exception:
                            pass
                        break
    except Exception:
        pass
    return files


def _get_workflows(gh, repo_full_name: str) -> list:
    try:
        repo = gh.get_repo(repo_full_name)
        workflows = repo.get_workflows()
        return [
            {"name": wf.name, "path": wf.path, "state": wf.state}
            for wf in workflows
        ]
    except Exception:
        return []


def _get_source_files_recursive(gh, repo_full_name: str) -> list[dict]:
    source_files = []
    try:
        _walk_dir(gh, repo_full_name, "", source_files)
    except Exception:
        pass
    return source_files


def _walk_dir(gh, repo_full_name: str, path: str, acc: list):
    if len(acc) >= MAX_SOURCE_FILES:
        return
    repo = gh.get_repo(repo_full_name)
    try:
        contents = repo.get_contents(path)
    except Exception:
        return
    for item in contents:
        if len(acc) >= MAX_SOURCE_FILES:
            break
        if item.type == "dir":
            name_lower = item.name.lower()
            if name_lower in ("node_modules", ".git", "vendor", "dist", "build", ".venv", "__pycache__", ".next", ".nuxt"):
                continue
            _walk_dir(gh, repo_full_name, item.path, acc)
        elif item.type == "file":
            ext = "." + item.name.rsplit(".", 1)[-1].lower() if "." in item.name else ""
            if ext in SOURCE_EXTENSIONS:
                try:
                    if item.encoding == "base64":
                        decoded = base64.b64decode(item.content).decode("utf-8", errors="replace")
                    else:
                        decoded = item.decoded_content.decode("utf-8", errors="replace")
                    lines = decoded.count("\n") + 1
                    acc.append({
                        "path": item.path,
                        "name": item.name,
                        "content": decoded[:MAX_FILE_SIZE],
                        "lines": lines,
                    })
                except Exception:
                    pass