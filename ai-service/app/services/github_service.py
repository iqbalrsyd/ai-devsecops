import base64
import logging
import time
import zipfile
import io
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------

def _debug_error(source: str, exc: Exception, context: str = "") -> None:
    """Log a 5xx/network error at WARNING level with full context.

    This is the primary debug tool for "Request failed with status code 502"
    errors. When a 502 appears in logs, search for "[{source}] 502" to find
    the exact HTTP call that failed.
    """
    status = getattr(exc, "response", None)
    status_code = getattr(status, "status_code", None) if status is not None else None
    msg = str(exc)[:300]
    ctx = f" ({context})" if context else ""
    logger.warning(
        "[%s] 502/5xx from upstream%s | status=%s | exc_type=%s | msg='%s'",
        source, ctx, status_code, type(exc).__name__, msg,
    )


def _debug_info(source: str, message: str, context: str = "") -> None:
    """Log an info message for pipeline debugging."""
    ctx = f" ({context})" if context else ""
    logger.info("[%s] %s%s", source, message, ctx)


# ---------------------------------------------------------------------------
# Transient error handling
# ---------------------------------------------------------------------------
#
# When the GitHub API (or any upstream that api.github.com proxies to)
# returns a 5xx, httpx raises `HTTPStatusError("Request failed with
# status code 502")`. The generator pipeline must NOT treat that as a
# security finding or a workflow configuration error — it is an
# external service issue, exactly like "Our services aren't available
# right now". To make classification reliable, every 5xx response is
# funnelled through `_safe_request`, which:
#
#   1. Retries up to `MAX_TRANSIENT_RETRIES` times with exponential
#      back-off. Most 502s clear in a few seconds.
#   2. If every retry fails, raises `GitHubUpstreamError` whose message
#      embeds "Request failed with status code 502" so
#      `finding_categories.classify_httpx_exception` can route it
#      into the `external_service_issue` bucket.
#
# Callers that want to translate an exception into a structured finding
# can use `is_transient_http_error()` and `classify_external_error()`
# below.

MAX_TRANSIENT_RETRIES = 3
TRANSIENT_BACKOFF_SECONDS = 1.5


class GitHubUpstreamError(RuntimeError):
    r"""Raised when an upstream (GitHub API, registry, etc.) returns 5xx.

    The message is intentionally preserved verbatim from httpx so the
    finding_categories regex `r"request failed with status code\s*5\d\d"`
    matches.
    """

    def __init__(self, message: str, status_code: int | None = None, source: str = "github_api"):
        super().__init__(message)
        self.status_code = status_code
        self.source = source


def is_transient_http_error(exc: Exception) -> bool:
    """Return True if `exc` is a 5xx / network error that we should retry
    or classify as an external_service_issue.

    Works for both httpx.HTTPStatusError and any plain Exception whose
    message embeds the httpx "Request failed with status code NNN"
    wording (this is the exact text raised by raise_for_status()).
    """
    status = getattr(exc, "response", None)
    status_code = getattr(status, "status_code", None) if status is not None else None
    if isinstance(status_code, int) and 500 <= status_code < 600:
        return True
    msg = (str(exc) or "").lower()
    if "request failed with status code 5" in msg:
        return True
    if "bad gateway" in msg or "gateway timeout" in msg or "service unavailable" in msg:
        return True
    if "econnrefused" in msg or "connection reset" in msg or "timed out" in msg:
        return True
    return False


def classify_external_error(exc: Exception, source: str = "github_api") -> dict | None:
    """Convert a transient HTTP exception into an external_service_issue dict.

    This is a thin wrapper that defers to
    `app.agents.finding_categories.classify_httpx_exception` so the
    classification logic lives in exactly one place.
    """
    try:
        from app.agents.finding_categories import classify_httpx_exception
    except Exception:
        return None
    return classify_httpx_exception(exc, source=source)


def _safe_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    max_retries: int = MAX_TRANSIENT_RETRIES,
    **kwargs,
) -> httpx.Response:
    """Run an httpx request with retry-on-5xx and GitHubUpstreamError on
    final failure.

    This is the canonical entry point used by every helper below. It
    guarantees that a 502 from GitHub's edge surfaces as a
    `GitHubUpstreamError` whose message contains "Request failed with
    status code 502" so the dashboard classifies it as an
    `external_service_issue` and the risk score is never affected.
    """
    merged_headers = {**_get_headers(token), **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = httpx.request(
                method,
                url,
                headers=merged_headers,
                timeout=timeout,
                **kwargs,
            )
            if 500 <= resp.status_code < 600:
                _debug_error("github_api", RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}"), f"{method} {url} attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    logger.warning(
                        "[github_api] Retrying after 5xx (attempt %d/%d): %s %s",
                        attempt + 1, max_retries, resp.status_code, url,
                    )
                    time.sleep(TRANSIENT_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise GitHubUpstreamError(
                    f"Request failed with status code {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                    source="github_api",
                )
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as e:
            _debug_error("github_api", e, f"{method} {url} attempt {attempt+1}/{max_retries}")
            last_exc = e
            if attempt < max_retries - 1:
                logger.warning(
                    "[github_api] Retrying after network error (attempt %d/%d): %s %s",
                    attempt + 1, max_retries, type(e).__name__, url,
                )
                time.sleep(TRANSIENT_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise GitHubUpstreamError(
                f"Request failed with status code 502: {e}",
                status_code=502,
                source="github_api",
            ) from e
    # Defensive: should not reach here, but if we do, re-raise last.
    if last_exc:
        raise GitHubUpstreamError(
            f"Request failed with status code 502: {last_exc}",
            status_code=502,
            source="github_api",
        ) from last_exc
    raise GitHubUpstreamError(
        "Request failed with status code 502: unknown error",
        status_code=502,
        source="github_api",
    )


def _get_headers(github_token: str | None = None) -> dict:
    token = github_token or settings.GITHUB_TOKEN
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-devsecops-pipeline-engineer",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_api_url(repo: str, path: str) -> str:
    url = f"https://api.github.com/repos/{repo}/{path}"
    return url.rstrip("/")


def _get(url: str, token: str | None = None) -> dict | list:
    """GET that raises HTTPStatusError on any non-2xx (legacy contract)."""
    resp = httpx.get(url, headers=_get_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


# ----- GitHub Client -----

def get_github_client(token: str):
    """Get a PyGithub-like client interface using raw httpx."""
    return _GitHubClient(token)


class _GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def get_user(self):
        data = _get("https://api.github.com/user", self.token)
        return _User(data)

    def get_repo(self, full_name: str):
        data = _get(_github_api_url(full_name, ""), self.token)
        return _Repo(data, self.token)


class _User:
    def __init__(self, data: dict):
        self._data = data

    @property
    def login(self) -> str:
        return self._data.get("login", "")


class _Repo:
    def __init__(self, data: dict, token: str):
        self._data = data
        self._token = token
        self.full_name = data.get("full_name", "")

    @property
    def name(self) -> str:
        return self._data.get("name", "") or (self.full_name.split("/")[-1] if self.full_name else "")

    @property
    def description(self) -> str | None:
        return self._data.get("description")

    @property
    def html_url(self) -> str:
        return self._data.get("html_url", "")

    @property
    def default_branch(self) -> str:
        return self._data.get("default_branch", "main")

    def get_contents(self, path: str):
        url = _github_api_url(self.full_name, f"contents/{path}")
        resp = httpx.get(url, headers=_get_headers(self._token), timeout=30)
        resp.raise_for_status()
        items = resp.json()
        if isinstance(items, list):
            return [_Content(item, self._token) for item in items]
        return _Content(items, self._token)

    def get_workflows(self):
        url = _github_api_url(self.full_name, "actions/workflows")
        try:
            resp = httpx.get(url, headers=_get_headers(self._token), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return [_Workflow(wf) for wf in data.get("workflows", [])]
        except Exception:
            return []


class _Content:
    def __init__(self, data: dict, token: str):
        self._data = data
        self._token = token
        self.name = data.get("name", "")
        self.path = data.get("path", "")
        self.type = data.get("type", "")
        self.encoding = data.get("encoding", "")
        self.content = data.get("content", "")

    @property
    def decoded_content(self) -> bytes:
        if self.encoding == "base64" and self.content:
            return base64.b64decode(self.content)
        return self.content.encode() if self.content else b""


class _Workflow:
    def __init__(self, data: dict):
        self.name = data.get("name", "")
        self.path = data.get("path", "")
        self.state = data.get("state", "")


# ----- Repository Operations -----

def list_repo_contents(repo: str, path: str, github_token: str | None = None) -> list[dict]:
    try:
        url = _github_api_url(repo, f"contents/{path}")
        data = _get(url, github_token)
        if isinstance(data, list):
            return [{"name": item["name"], "path": item["path"], "type": item["type"]} for item in data]
        return [{"name": data.get("name", ""), "path": data.get("path", ""), "type": data.get("type", "")}]
    except Exception:
        return []


def get_file_content(repo: str, path: str, github_token: str | None = None) -> str | None:
    try:
        url = _github_api_url(repo, f"contents/{path}")
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return data.get("content", "")
    except Exception:
        return None


def get_default_branch_sha(repo: str, github_token: str | None = None) -> str | None:
    for branch in ["main", "master"]:
        try:
            url = _github_api_url(repo, f"git/refs/heads/{branch}")
            resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
            if resp.status_code == 200:
                return resp.json()["object"]["sha"]
        except Exception:
            continue
    return None


# ----- Branch Operations -----

def create_branch(repo: str, branch_name: str, base_branch: str, github_token: str | None = None) -> bool:
    sha = get_default_branch_sha(repo, github_token)
    if not sha:
        return False
    url = _github_api_url(repo, "git/refs")
    payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    try:
        resp = httpx.post(url, json=payload, headers=_get_headers(github_token), timeout=30)
        return resp.status_code == 201
    except Exception:
        return False


# ----- File Operations -----

def _get_file_sha(repo: str, path: str, branch: str, github_token: str | None) -> str | None:
    try:
        url = _github_api_url(repo, f"contents/{path}?ref={branch}")
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("sha")
    except Exception:
        pass
    return None


def commit_file(repo: str, branch: str, path: str, content: str, message: str, github_token: str | None = None) -> str | None:
    url = _github_api_url(repo, f"contents/{path}")
    encoded = base64.b64encode(content.encode()).decode()
    sha = _get_file_sha(repo, path, branch, github_token)
    payload = {"message": message, "content": encoded, "branch": branch}
    if sha:
        payload["sha"] = sha
    try:
        resp = httpx.put(url, json=payload, headers=_get_headers(github_token), timeout=30)
        if resp.status_code in (201, 200):
            return resp.json()["content"]["sha"]
        # GitHub returns 422 when the file content is identical to what's
        # already on the branch (no diff to commit). Treat as success —
        # the file is already what we wanted. Return a sentinel so the
        # caller can distinguish "no-op" from "actually committed".
        if resp.status_code == 422:
            try:
                err_msg = (resp.json().get("message") or "").lower()
            except Exception:
                err_msg = ""
            if "no changes" in err_msg or "same content" in err_msg or "file already exists" in err_msg:
                print(f"[commit_file] {repo}@{branch}:{path} — no changes (file identical, treated as success)")
                return sha or "UNCHANGED"
            print(f"[commit_file] {repo}@{branch}:{path} — 422: {resp.text[:200]}")
        else:
            print(f"[commit_file] {repo}@{branch}:{path} — HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[commit_file] {repo}@{branch}:{path} — exception: {type(e).__name__}: {e}")
    return None


def delete_file(repo: str, branch: str, path: str, message: str, github_token: str | None = None) -> bool:
    """Delete a file from the repository on a specific branch.

    Required for cleaning up legacy workflow files when a new one is added,
    so the PR checks reflect only the newly generated pipeline.
    Returns True if the file was deleted (or didn't exist), False on error.
    """
    sha = _get_file_sha(repo, path, branch, github_token)
    if not sha:
        return True  # Already gone — treat as success.
    url = _github_api_url(repo, f"contents/{path}")
    payload = {
        "message": message,
        "sha": sha,
        "branch": branch,
    }
    try:
        resp = httpx.delete(url, json=payload, headers=_get_headers(github_token), timeout=30)
        return resp.status_code in (200, 204)
    except Exception:
        return False


def list_workflow_files(repo: str, branch: str, github_token: str | None = None) -> list[str]:
    """List every workflow file path (.github/workflows/*.yml, *.yaml) on a branch."""
    paths: list[str] = []
    items = list_repo_contents(repo, ".github/workflows", github_token)
    for item in items:
        if item.get("type") != "file":
            continue
        path = item.get("path", "")
        if path.endswith(".yml") or path.endswith(".yaml"):
            # Confirm the file actually exists on this branch (not a stale listing)
            if _get_file_sha(repo, path, branch, github_token):
                paths.append(path)
    return paths


# ----- Pull Request Operations -----

def create_pull_request(repo: str, branch: str, title: str, body: str, base: str, github_token: str | None = None) -> dict | None:
    url = _github_api_url(repo, "pulls")
    payload = {"title": title, "body": body, "head": branch, "base": base}
    try:
        resp = httpx.post(url, json=payload, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 201:
            data = resp.json()
            return {"number": data["number"], "html_url": data["html_url"]}
    except Exception:
        pass
    return None


# ----- Workflow Operations -----

def trigger_workflow_dispatch(repo: str, workflow_filename: str, ref: str, github_token: str | None = None) -> bool:
    url = _github_api_url(repo, f"actions/workflows/{workflow_filename}/dispatches")
    payload = {"ref": ref}
    try:
        resp = httpx.post(url, json=payload, headers=_get_headers(github_token), timeout=30)
        return resp.status_code == 204
    except Exception:
        return False


def get_workflow_run(repo: str, run_id: int, github_token: str | None = None) -> dict | None:
    url = _github_api_url(repo, f"actions/runs/{run_id}")
    try:
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "id": data["id"],
                "status": data["status"],
                "conclusion": data.get("conclusion"),
                "html_url": data["html_url"],
                "started_at": data.get("run_started_at"),
                "completed_at": data.get("updated_at"),
            }
    except Exception:
        pass
    return None


def get_workflow_run_jobs(repo: str, run_id: int, github_token: str | None = None) -> list:
    url = _github_api_url(repo, f"actions/runs/{run_id}/jobs")
    try:
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("jobs", [])
    except Exception:
        pass
    return []


def get_workflow_run_artifacts(
    repo: str, run_id: int, github_token: str | None = None
) -> list:
    """List workflow run artifacts.

    Returns a list of {"id": int, "name": str, "size_in_bytes": int,
    "archive_download_url": str} dicts. Used by the AI agent to
    download scanner JSON outputs (npm audit, Trivy, Semgrep,
    Gitleaks) from the run's artifacts.
    """
    url = _github_api_url(repo, f"actions/runs/{run_id}/artifacts")
    try:
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("artifacts", [])
    except Exception as e:
        logger.warning("get_workflow_run_artifacts: %s", e)
    return []


def download_artifact(
    repo: str, run_id: int, artifact_id: int, github_token: str | None = None
) -> str:
    """Download a single artifact and return its text content.

    The GitHub Actions artifacts API returns a ZIP archive. The
    caller is expected to know what the archive contains
    (typically a single JSON file). This function extracts the
    first textual entry and returns it as a string.

    Returns "" on any error.
    """
    url = _github_api_url(repo, f"actions/runs/{run_id}/artifacts/{artifact_id}")
    try:
        resp = httpx.get(
            url,
            headers={**_get_headers(github_token), "Accept": "application/vnd.github.v3.raw"},
            timeout=60,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            logger.warning(
                "download_artifact: GitHub returned status %d for %s",
                resp.status_code, url,
            )
            return ""
        body = resp.content
        # Same zip handling as get_workflow_logs: extract the
        # first textual member and return it.
        import io
        import zipfile
        is_zip = (
            "zip" in resp.headers.get("Content-Type", "").lower()
            or (len(body) >= 4 and body[:4] == b"PK\x03\x04")
        )
        if not is_zip:
            return body.decode("utf-8", errors="replace")
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    return zf.read(name).decode("utf-8", errors="replace")
        except zipfile.BadZipFile:
            return body.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("download_artifact: %s", e)
    return ""


def get_workflow_logs(repo: str, run_id: int, github_token: str | None = None) -> str:
    """Fetch the consolidated workflow run log as text.

    GitHub's `actions/runs/{id}/logs` endpoint returns a ZIP archive
    (one txt file per job, plus per-step txt files). Reviewer feedback:
    the previous implementation read the response as text, which gave
    a binary blob that downstream scanners could not parse. This
    implementation downloads the zip, extracts the txt members, and
    concatenates them so the AI agent can scan the actual log content.
    """
    url = _github_api_url(repo, f"actions/runs/{run_id}/logs")
    try:
        resp = httpx.get(
            url,
            headers={**_get_headers(github_token), "Accept": "application/vnd.github.v3.raw"},
            timeout=60,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            logger.warning(
                "get_workflow_logs: GitHub returned status %d for %s",
                resp.status_code, url,
            )
            return ""
        content_type = resp.headers.get("Content-Type", "")
        body = resp.content
        # The logs endpoint returns a ZIP archive. Detect either by
        # content-type or by the magic bytes (PK\x03\x04).
        is_zip = (
            "zip" in content_type.lower()
            or (len(body) >= 4 and body[:4] == b"PK\x03\x04")
        )
        if not is_zip:
            # Plain text response (older API, debug, or empty run).
            try:
                return body.decode("utf-8", errors="replace")
            except Exception:
                return ""
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                parts: list[str] = []
                for name in zf.namelist():
                    # Skip directories and non-txt entries.
                    if name.endswith("/"):
                        continue
                    try:
                        text = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    parts.append(f"=== {name} ===\n{text}")
                return "\n".join(parts)
        except zipfile.BadZipFile as e:
            logger.warning("get_workflow_logs: invalid zip response: %s", e)
            # Fallback: try to decode as text in case the response is
            # not actually zipped despite the content-type.
            try:
                return body.decode("utf-8", errors="replace")
            except Exception:
                return ""
    except Exception as e:
        logger.warning("get_workflow_logs: failed to fetch logs: %s", e)
        return ""
    return ""


def get_workflow_id_by_name(repo: str, filename: str, github_token: str | None = None) -> int | None:
    url = _github_api_url(repo, "actions/workflows")
    try:
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            for wf in resp.json().get("workflows", []):
                if wf["path"].endswith(filename):
                    return wf["id"]
    except Exception:
        pass
    return None


def get_latest_workflow_run(repo: str, github_token: str | None = None) -> dict | None:
    try:
        token = github_token or settings.GITHUB_TOKEN
        url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=1"
        resp = httpx.get(url, headers=_get_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        runs = data.get("workflow_runs", [])
        if runs:
            r = runs[0]
            return {
                "run_id": r["id"],
                "status": r.get("status", ""),
                "conclusion": r.get("conclusion"),
                "html_url": r.get("html_url", ""),
                "display_title": r.get("display_title", ""),
                "run_started_at": r.get("run_started_at", ""),
                "workflow_path": r.get("path", ""),
            }
    except Exception:
        pass
    return None


def list_workflows(repo: str, github_token: str | None = None) -> list:
    url = _github_api_url(repo, "actions/workflows")
    try:
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("workflows", [])
    except Exception:
        pass
    return []


# ----- Check run annotations (workflow run / annotation API) -----

def get_check_runs_for_run(repo: str, run_id: int, github_token: str | None = None) -> list[dict]:
    """Return the list of check-runs attached to a workflow run.

    GitHub attaches a check-run to every step in a workflow that calls
    `actions/checkout` or any `using: node20` action. The annotations on
    each check-run are the primary source of truth for *why* a step
    failed (e.g. "GITHUB_TOKEN is now required", "Unexpected input(s)
    'args'", "Node.js 20 actions are deprecated").

    Returns an empty list on any error — callers must treat annotations
    as best-effort evidence, never as a hard requirement.
    """
    try:
        url = _github_api_url(repo, f"actions/runs/{run_id}")
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        head_sha = data.get("head_sha") or data.get("head_branch") and None
        if not head_sha:
            return []
        url = _github_api_url(repo, f"commits/{head_sha}/check-runs?per_page=100")
        resp = httpx.get(url, headers={**_get_headers(github_token), "Accept": "application/vnd.github+json"}, timeout=30)
        if resp.status_code != 200:
            return []
        return resp.json().get("check_runs", []) or []
    except Exception:
        return []


def get_check_run_annotations(repo: str, check_run_id: int, github_token: str | None = None) -> list[dict]:
    """Return annotations for a single check-run.

    Each annotation has the shape:
        {path, start_line, end_line, annotation_level, message, title, raw_details}
    """
    try:
        url = _github_api_url(repo, f"check-runs/{check_run_id}/annotations")
        resp = httpx.get(url, headers=_get_headers(github_token), timeout=30)
        if resp.status_code == 200:
            return resp.json() or []
    except Exception:
        pass
    return []


def collect_workflow_annotations(repo: str, run_id: int, github_token: str | None = None) -> list[dict]:
    """Top-level helper: every annotation attached to every check-run for a run.

    The output is normalized to a flat list of dicts with these keys:
        check_run_id, check_name, conclusion, path, line, level, message, title

    This is the new evidence source for the
    "Generated YAML → Workflow Validation → GitHub Workflow Runs → GitHub
    Annotations → Issue Categorization → Dashboard Findings" pipeline.
    """
    annotations: list[dict] = []
    for cr in get_check_runs_for_run(repo, run_id, github_token):
        cr_id = cr.get("id")
        cr_name = cr.get("name", "")
        cr_conclusion = cr.get("conclusion", "")
        for ann in get_check_run_annotations(repo, cr_id, github_token):
            annotations.append({
                "check_run_id": cr_id,
                "check_name": cr_name,
                "conclusion": cr_conclusion,
                "path": ann.get("path", ""),
                "line": ann.get("start_line") or ann.get("end_line"),
                "level": ann.get("annotation_level", "notice"),
                "message": ann.get("message", ""),
                "title": ann.get("title", ""),
            })
    return annotations


# ---------------------------------------------------------------------------
# Code Scanning alerts
# ---------------------------------------------------------------------------

def get_code_scanning_alerts(
    repo: str,
    run_id: int | None = None,
    state: str = "open",
    github_token: str | None = None,
) -> list[dict]:
    """Fetch Code Scanning alerts from GitHub's Code Scanning API.

    This is the primary source of structured security findings for the
    AI agent. Code Scanning alerts come from SARIF uploads by the
    GitHub Actions workflow (semgrep, trivy, gitleaks via upload-sarif).

    Parameters
    ----------
    repo:
        Repository in "owner/name" format.
    run_id:
        Optional GitHub Actions run ID. If provided, returns only
        alerts associated with that run (filter by analysis_key).
    state:
        Alert state filter. One of "open" (default), "fixed",
        "dismissed", or "all".
    github_token:
        GitHub personal access token or installation token with
        `security_events: read` scope.

    Returns
    -------
    List of normalized Code Scanning alert dicts with these keys:
        number, rule_id, severity, description, scanner, state,
        file, line, column, html_url, created_at, categories
    """
    if not repo:
        return []
    # Note: _github_api_url already prepends "/repos/<repo>/", so
    # the path argument must NOT include that prefix.
    path = f"code-scanning/alerts"
    params: list[tuple[str, str]] = [("state", state), ("per_page", "100")]
    if run_id is not None:
        # Filter by analysis_key (e.g. ".github/workflows/ai-devsecops-v2.yml:sast")
        # Note: GitHub API doesn't directly filter by run_id, so we
        # fetch all alerts and filter client-side by most_recent_instance
        pass
    url = _github_api_url(repo, path)
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"

    try:
        alerts_raw = _get(url, github_token) or []
    except Exception as e:
        _debug_error("get_code_scanning_alerts", e, context=f"repo={repo} run_id={run_id}")
        return []

    if not isinstance(alerts_raw, list):
        return []

    normalized: list[dict] = []
    for a in alerts_raw:
        if not isinstance(a, dict):
            continue

        rule = a.get("rule") or {}
        tool = a.get("tool") or {}
        most_recent = a.get("most_recent_instance") or {}
        location = most_recent.get("location") or {}

        # Skip alerts not associated with the requested run, if any
        # GitHub uses analysis_key to identify workflow runs; for
        # example ".github/workflows/ai-devsecops-v2.yml:sast"
        #
        # Treat 0 the same as None — `run_id=0` is what the FE
        # sends when no GitHub Actions run has been recorded yet
        # (the workflow file hasn't been deployed). Falling back
        # to "all open alerts" is the right behaviour in that
        # case, otherwise every alert is dropped because
        # `str(0)` rarely appears in the analysis_key.
        if run_id is not None and run_id > 0:
            analysis_key = most_recent.get("analysis_key", "")
            if str(run_id) not in analysis_key:
                # GitHub does not always include run_id in the key;
                # we keep the alert if it was created in the last
                # 30 days. The previous 24h window was too narrow
                # — Code Scanning alerts opened "5 days ago" or
                # "last week" (per the GitHub Security tab UI) were
                # silently dropped from the dashboard even though
                # they are still actionable. 30 days covers the
                # typical review window without flooding the
                # dashboard with ancient findings.
                created = a.get("created_at", "")
                if not created:
                    continue
                from datetime import datetime, timezone, timedelta
                try:
                    created_dt = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    )
                    if (
                        datetime.now(timezone.utc) - created_dt
                        > timedelta(days=30)
                    ):
                        continue
                except Exception:
                    pass

        # Map CWE tags to a single CWE field
        cwe = ""
        owasp = ""
        for tag in rule.get("tags", []) or []:
            if not isinstance(tag, str):
                continue
            if tag.upper().startswith("CWE-"):
                cwe = tag
            if "OWASP" in tag.upper():
                owasp = tag

        normalized.append({
            "number": a.get("number"),
            "rule_id": rule.get("id", "unknown"),
            "severity": (rule.get("severity") or "warning").lower(),
            "title": rule.get("name") or rule.get("id") or "Finding",
            "description": rule.get("description", ""),
            "scanner": tool.get("name", "unknown"),
            "scanner_version": tool.get("version", ""),
            "state": a.get("state", "open"),
            "file": location.get("path", ""),
            "line": location.get("start_line"),
            "end_line": location.get("end_line"),
            "column": location.get("start_column"),
            "cwe": cwe,
            "owasp": owasp,
            "html_url": a.get("html_url", ""),
            "created_at": a.get("created_at"),
            "category": most_recent.get("category", ""),
            "analysis_key": most_recent.get("analysis_key", ""),
            "message": (most_recent.get("message") or {}).get("text", "")
            if isinstance(most_recent.get("message"), dict)
            else str(most_recent.get("message", "")),
        })
    return normalized


def normalize_code_scanning_alerts(alerts: list[dict]) -> list[dict]:
    """Convert Code Scanning alerts into the AI agent's finding schema.

    Maps alert fields to the schema used by ``security_finding_normalizer``
    so that downstream nodes (security_analyzer, risk_assessor,
    response_formatter) can consume them without changes.

    The output schema matches what the rest of the AI pipeline expects:
        type, severity, scanner, source_tool, file_location, line,
        code_snippet, title, evidence, cwe, owasp, scanner_url,
        cvss_score, cvss_vector, cvss_severity
    """
    out: list[dict] = []
    for a in alerts or []:
        if not isinstance(a, dict):
            continue
        # Bab 5.13.3: attach CVSS via the 3-tier lookup so the FE
        # can render the badge without re-computing.
        cvss_score, cvss_vector = _estimate_cvss_from_alert(a)
        out.append({
            # Identifiers
            "type": a.get("rule_id", "code_scanning_alert"),
            "title": a.get("title") or a.get("rule_id", "Finding"),
            # Severity (Code Scanning uses warning|error|note)
            "severity": a.get("severity", "medium"),
            # Source
            "scanner": a.get("scanner", "github_code_scanning"),
            "source_tool": "github_code_scanning",
            "scanner_version": a.get("scanner_version", ""),
            "rule_id": a.get("rule_id", ""),
            # Location
            "file_location": a.get("file", ""),
            "line": a.get("line"),
            "column": a.get("column"),
            # Content
            "evidence": a.get("message", ""),
            "explanation": a.get("description") or a.get("message", ""),
            "code_snippet": "",  # Code Scanning API does not expose the snippet
            "recommendation": _code_scanning_recommendation(a),
            "remediation_recommendation": _code_scanning_recommendation(a),
            # Compliance metadata
            "cwe": a.get("cwe", ""),
            "owasp": a.get("owasp", ""),
            # CVSS 3.1 (Bab 5.13.3)
            "cvss_score": cvss_score,
            "cvss_vector": cvss_vector,
            "cvss_severity": _cvss_severity_band_from_score(cvss_score),
            # Reference
            "scanner_url": a.get("html_url", ""),
            # Raw alert (for the dashboard)
            "_raw": a,
        })
    return out


def normalize_code_scanning_alerts_with_summary(alerts: list[dict]) -> dict:
    """Same as `normalize_code_scanning_alerts` but returns a dict that
    also carries a `cvss_breakdown` summary keyed by severity band:

        {
          "alerts": [<enriched alert dict>, ...],
          "cvss_breakdown": {
            "by_band": {
              "critical": {"count": 35, "cvss_sum": 324.0},
              "high":     {"count": 19, "cvss_sum": 142.5},
              ...
            },
            "total_cvss": 466.5,
            "total_count": 54,
          }
        }

    Used by the PDF endpoint and by the FE's `CodeScanningAlertsCard`
    header pills (Bab 5.13.3).
    """
    enriched = normalize_code_scanning_alerts(alerts)
    cvss_by_band: dict[str, float] = {"critical": 0.0, "high": 0.0, "medium": 0.0, "low": 0.0, "none": 0.0}
    count_by_band: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "none": 0}
    total_cvss = 0.0
    for f in enriched:
        try:
            cvss_num = float(f.get("cvss_score") or 0.0)
        except (TypeError, ValueError):
            cvss_num = 0.0
        band = str(f.get("cvss_severity") or "none").lower()
        cvss_by_band[band] = cvss_by_band.get(band, 0.0) + cvss_num
        count_by_band[band] = count_by_band.get(band, 0) + 1
        total_cvss += cvss_num
    summary = {
        "by_band": {
            band: {
                "count": count_by_band.get(band, 0),
                "cvss_sum": round(cvss_by_band.get(band, 0.0), 1),
            }
            for band in ("critical", "high", "medium", "low", "none")
        },
        "total_cvss": round(total_cvss, 1),
        "total_count": len(enriched),
    }
    return {"alerts": enriched, "cvss_breakdown": summary}


def _estimate_cvss_from_alert(alert: dict) -> tuple[float, str]:
    """Return (base_score, vector) for a Code Scanning alert.

    Delegates to `cvss_mapper.score_finding` (Bab 5.13.3) so the lookup
    tables in the spec — RULE_CVSS_MAP, TYPE_CVSS_FALLBACK,
    SEVERITY_DEFAULT — are the single source of truth.
    """
    from app.agents.cvss_mapper import score_finding
    enriched = score_finding(dict(alert))
    return enriched.get("cvss_score", 5.0), enriched.get("cvss_vector", "")


def _cvss_severity_band_from_score(score: float) -> str:
    """Map a numeric CVSS score to a band label (helper shim)."""
    from app.agents.cvss_mapper import cvss_severity_band
    return cvss_severity_band(score)


def _code_scanning_recommendation(alert: dict) -> str:
    """Return a remediation hint derived from a Code Scanning alert.

    The Code Scanning API does not always provide a fix recipe, so we
    fall back to linking the alert and stating the rule id. For
    Semgrep findings we have a richer set of suggestions baked into
    the rule metadata; those flow through the alert's full_description
    when available.
    """
    rid = alert.get("rule_id", "")
    url = alert.get("html_url", "")
    if url:
        return f"Review the rule: {rid}. See {url}"
    if rid:
        return f"Review the rule: {rid}"
    return "Review the alert in GitHub Code Scanning."