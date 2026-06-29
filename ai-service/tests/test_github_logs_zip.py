"""Tests for the GitHub service log fetching.

Reviewer feedback: the previous `get_workflow_logs` implementation
read the response as text, but GitHub's `actions/runs/{id}/logs`
endpoint returns a ZIP archive. The fix decodes the zip and
concatenates the txt members so downstream scanners can parse the
real log content.
"""
import io
import sys
import zipfile

sys.path.insert(0, "/mnt/ssd/college-project/skripsi-code/coba-4/ai-service")

from unittest.mock import MagicMock, patch

import httpx

from app.services.github_service import get_workflow_logs


def _build_zip_response(members: dict[str, str]) -> bytes:
    """Build an in-memory zip file with the given members."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_get_workflow_logs_extracts_zip_members():
    """Real-world: GitHub returns a zip with one txt per job/step.
    The function must decode it and concatenate the members.
    """
    zip_bytes = _build_zip_response({
        "0_setup.txt": "Run actions/checkout@v4\nSet up Python 3.11\n",
        "1_lint.txt": "Run eslint\nCVE-2024-1234 in dependency\n",
    })
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/zip"}
    mock_resp.content = zip_bytes

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    assert "Run actions/checkout@v4" in log_text
    assert "CVE-2024-1234 in dependency" in log_text
    assert "0_setup.txt" in log_text
    assert "1_lint.txt" in log_text


def test_get_workflow_logs_handles_plain_text_response():
    """Fallback: if the response is plain text (older API, debug),
    return the decoded text.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/plain"}
    mock_resp.content = b"Run npm audit\nFound 3 vulnerabilities"

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    assert "Found 3 vulnerabilities" in log_text


def test_get_workflow_logs_returns_empty_on_404():
    """404 from GitHub (e.g. logs expired) → return empty string."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {}
    mock_resp.content = b""

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    assert log_text == ""


def test_get_workflow_logs_force_bypasses_cache(monkeypatch):
    """Reviewer feedback: the "Refresh Analysis" button sends
    `force=true` to the AI service. Verify the run_pipeline_analysis
    helper accepts a `force` kwarg. We don't run the full analysis
    pipeline here (that requires GitHub + DB); we just verify the
    signature and that the cache is bypassed.
    """
    from app.services import pipeline_service
    cache_called = []

    def fake_saved(run_id: int):
        cache_called.append(run_id)
        # Return a dict-like object so the run_pipeline_analysis
        # function can mutate it (line 1881: `saved["log_analysis"] = []`).
        return {
            "log_analysis": ["stale"],
            "validation_findings": ["stale"],
            "validation_errors": ["stale"],
            "validation_warnings": ["stale"],
        }

    monkeypatch.setattr(pipeline_service, "_get_saved_analysis", fake_saved)

    # When force=False (default), _get_saved_analysis is consulted and
    # the saved value is returned.
    result_default = pipeline_service.run_pipeline_analysis(
        repository_id="owner/repo",
        run_id=42,
        github_token="token",
        force=False,
    )
    # The function returns the saved object after clearing stale fields.
    assert isinstance(result_default, dict)
    assert result_default["log_analysis"] == []
    assert cache_called == [42]

    # When force=True, the cache must be bypassed. We abort the rest
    # of the function with a RuntimeError to confirm the cache check
    # is the only thing that differs between force=True and force=False.
    cache_called.clear()

    # Force the analysis path to fail predictably. Patch the
    # SessionLocal symbol on the *database* module (where it is
    # defined) so the pipeline_service call site picks up the mock.
    from app import database as db_module
    monkeypatch.setattr(db_module, "SessionLocal", fail_session)
    try:
        pipeline_service.run_pipeline_analysis(
            repository_id="owner/repo",
            run_id=42,
            github_token="token",
            force=True,
        )
    except RuntimeError as e:
        assert "cache bypassed" in str(e)
    # Cache must NOT have been called when force=True
    assert cache_called == []


def fail_session(*args, **kwargs):
    raise RuntimeError("cache bypassed as expected")


def test_get_workflow_logs_returns_empty_on_401():
    """401 (token invalid) → return empty string, don't crash."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    mock_resp.content = b""

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "bad-token")

    assert log_text == ""


def test_get_workflow_logs_handles_invalid_zip_fallback():
    """If the response claims to be a zip but isn't valid, fall back
    to text decoding instead of crashing.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/zip"}
    mock_resp.content = b"not a valid zip but still has text\nCVE-2024-1234"

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    # Should fall back to text decode
    assert "CVE-2024-1234" in log_text


def test_get_workflow_logs_detects_zip_by_magic_bytes():
    """If Content-Type is missing/wrong but the body starts with PK\\x03\\x04,
    still treat it as a zip.
    """
    zip_bytes = _build_zip_response({
        "0_log.txt": "Run npm audit\nCVE-2024-5678 in lodash\n",
    })
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/octet-stream"}  # wrong type
    mock_resp.content = zip_bytes

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    assert "CVE-2024-5678" in log_text


def test_get_workflow_logs_follows_redirect():
    """The previous implementation had follow_redirects default; verify
    we explicitly pass it so 302 redirects to the actual log zip are
    followed.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/zip"}
    mock_resp.content = _build_zip_response({
        "0_log.txt": "All clean\n",
    })

    with patch("app.services.github_service.httpx.get", return_value=mock_resp) as mock_get:
        get_workflow_logs("owner/repo", 12345, "token")
        # Verify the call used follow_redirects=True
        kwargs = mock_get.call_args.kwargs
        assert kwargs.get("follow_redirects") is True


def test_get_workflow_logs_handles_network_exception():
    """Network errors must not crash — return empty string."""
    with patch("app.services.github_service.httpx.get", side_effect=Exception("network down")):
        log_text = get_workflow_logs("owner/repo", 12345, "token")
    assert log_text == ""


def test_get_workflow_logs_zip_with_multiple_jobs():
    """End-to-end: a typical CI run with 6 jobs should produce a
    log text containing all of them.
    """
    members = {
        f"{i}_{name}.txt": f"=== Job {name} ===\nOutput of {name} step\n"
        for i, name in enumerate(
            ["lint", "sast", "dependency-scan", "secret-scan",
             "container-scan", "container-build"]
        )
    }
    members["0_lint.txt"] += "Run eslint\n"
    members["2_dependency-scan.txt"] += (
        "npm audit\n"
        "3 vulnerabilities (1 high, 2 critical)\n"
        "CVE-2024-1111 in lodash\n"
    )
    members["3_secret-scan.txt"] += (
        "gitleaks\n"
        "Finding: AWS Secret Key\n"
        "AKIAIOSFODNN7EXAMPLE\n"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/zip"}
    mock_resp.content = _build_zip_response(members)

    with patch("app.services.github_service.httpx.get", return_value=mock_resp):
        log_text = get_workflow_logs("owner/repo", 12345, "token")

    # All jobs should be present
    for name in ["lint", "sast", "dependency-scan", "secret-scan", "container-scan"]:
        assert f"Job {name}" in log_text
    # Real security findings should be in the log
    assert "CVE-2024-1111" in log_text
    assert "AKIAIOSFODNN7EXAMPLE" in log_text


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
