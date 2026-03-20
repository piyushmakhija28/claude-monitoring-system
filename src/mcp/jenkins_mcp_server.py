"""
Jenkins MCP Server - FastMCP-based Jenkins CI/CD integration for Claude Code.

Provides direct Jenkins REST API access using stdlib urllib only (no external deps).
Authentication uses Basic auth with base64(user:api_token) -- API tokens are exempt
from CSRF crumb requirements.

Transport: stdio

Tools (10):
  jenkins_trigger_build, jenkins_get_build_status, jenkins_get_console_output,
  jenkins_list_jobs, jenkins_get_job_info, jenkins_list_builds,
  jenkins_abort_build, jenkins_get_queue_info, jenkins_wait_for_build,
  jenkins_health_check

Environment Variables:
  JENKINS_URL         - Base URL (e.g., https://jenkins.company.com)
  JENKINS_USER        - Username for authentication
  JENKINS_API_TOKEN   - API token (NOT password; tokens bypass CSRF crumb)
  JENKINS_VERIFY_SSL  - "true" (default) or "false" for self-signed certs

ASCII-only (cp1252 compatible for Windows)
"""

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.decorators import mcp_tool_handler

mcp = FastMCP(
    "jenkins-ci",
    instructions="Jenkins CI/CD integration via REST API (stdlib only, no external deps)"
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 60  # seconds; Jenkins can be slow to respond


def _get_env(name: str) -> str:
    """Return an environment variable or raise a descriptive ValueError."""
    val = os.environ.get(name, "").strip()
    if not val:
        raise ValueError(
            "Environment variable '{}' is not set. "
            "Set it before starting the MCP server.".format(name)
        )
    return val


def _build_auth_header() -> str:
    """Build the Basic-auth header value from JENKINS_USER and JENKINS_API_TOKEN."""
    user = _get_env("JENKINS_USER")
    token = _get_env("JENKINS_API_TOKEN")
    raw = "{}:{}".format(user, token)
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return "Basic {}".format(encoded)


def _ssl_context() -> Optional[ssl.SSLContext]:
    """Return an SSL context that skips verification when JENKINS_VERIFY_SSL=false."""
    verify = os.environ.get("JENKINS_VERIFY_SSL", "true").strip().lower()
    if verify == "false":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def _base_url() -> str:
    """Return the Jenkins base URL without a trailing slash."""
    url = _get_env("JENKINS_URL")
    return url.rstrip("/")


def _encode_job_path(job_name: str) -> str:
    """Convert a job name (including folder paths) to a Jenkins URL path segment.

    Supports folder paths:
      'folder/subfolder/job' -> '/job/folder/job/subfolder/job/job'
    Single jobs:
      'my-job' -> '/job/my-job'

    Each path component is URL-encoded to handle spaces and special chars.
    """
    parts = job_name.strip("/").split("/")
    encoded_parts = [urllib.parse.quote(p, safe="") for p in parts if p]
    return "/job/" + "/job/".join(encoded_parts)


def _jenkins_request(
    path: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    extra_headers: Optional[dict] = None,
) -> tuple:
    """Execute a Jenkins REST API request.

    Args:
        path: URL path starting with '/' (e.g., '/api/json').
        method: HTTP method (GET, POST).
        data: Optional POST body as bytes.
        extra_headers: Additional HTTP headers to merge.

    Returns:
        Tuple of (response_body_str, http_status_code).

    Raises:
        urllib.error.HTTPError: On 4xx/5xx responses.
        urllib.error.URLError: On connection errors.
    """
    url = _base_url() + path
    headers = {
        "Authorization": _build_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ssl_ctx = _ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ssl_ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return body, resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise urllib.error.HTTPError(
            exc.url, exc.code, exc.msg, exc.headers, None
        ) from None


def _jenkins_json(path: str) -> dict:
    """GET a Jenkins API endpoint and return parsed JSON."""
    if "?" in path:
        api_path = path + "&tree=*"
    else:
        api_path = path + "/api/json"
    body, _ = _jenkins_request(api_path)
    return json.loads(body)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def jenkins_trigger_build(
    job_name: str,
    parameters: Optional[str] = None,
) -> dict:
    """Trigger a Jenkins build for the specified job.

    Uses /build for parameterless jobs and /buildWithParameters when
    parameters are provided.

    Args:
        job_name: Job name or folder path (e.g., 'my-job' or 'folder/my-job').
        parameters: Optional query string of build parameters
                    (e.g., 'BRANCH=main&ENV=staging').
                    Each param is a key=value pair separated by '&'.

    Returns:
        dict with queued=True, queue_url (Location header), and job_name.
    """
    job_path = _encode_job_path(job_name)

    if parameters:
        endpoint = "{}/buildWithParameters?{}".format(job_path, parameters)
    else:
        endpoint = "{}/build".format(job_path)

    url = _base_url() + endpoint
    headers = {"Authorization": _build_auth_header()}
    req = urllib.request.Request(
        url, data=b"", headers=headers, method="POST"
    )
    ssl_ctx = _ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ssl_ctx) as resp:
            queue_url = resp.headers.get("Location", "")
            return {
                "queued": True,
                "job_name": job_name,
                "queue_url": queue_url,
                "status_code": resp.status,
            }
    except urllib.error.HTTPError as exc:
        raise ValueError(
            "Jenkins returned HTTP {}: {}".format(exc.code, exc.reason)
        ) from exc


@mcp.tool()
@mcp_tool_handler
def jenkins_get_build_status(
    job_name: str,
    build_number: int,
) -> dict:
    """Get the status of a specific build.

    Args:
        job_name: Job name or folder path.
        build_number: Build number (integer). Use 0 for the last build.

    Returns:
        dict with result, building (bool), duration_ms, url, and timestamp.
    """
    job_path = _encode_job_path(job_name)
    build_ref = "lastBuild" if build_number == 0 else str(build_number)
    api_path = "{}/{}/api/json".format(job_path, build_ref)

    body, _ = _jenkins_request(api_path)
    data = json.loads(body)

    return {
        "job_name": job_name,
        "build_number": data.get("number"),
        "result": data.get("result"),
        "building": data.get("building", False),
        "duration_ms": data.get("duration", 0),
        "url": data.get("url", ""),
        "timestamp": data.get("timestamp", 0),
        "display_name": data.get("displayName", ""),
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_get_console_output(
    job_name: str,
    build_number: int,
) -> dict:
    """Get the console log for a specific build.

    Truncates to the last 10,000 characters if the log is larger.

    Args:
        job_name: Job name or folder path.
        build_number: Build number. Use 0 for the last build.

    Returns:
        dict with console_output (str), truncated (bool), and total_chars (int).
    """
    job_path = _encode_job_path(job_name)
    build_ref = "lastBuild" if build_number == 0 else str(build_number)
    endpoint = "{}/{}/consoleText".format(job_path, build_ref)

    body, _ = _jenkins_request(endpoint)
    total_chars = len(body)
    max_chars = 10_000
    truncated = total_chars > max_chars
    output = body[-max_chars:] if truncated else body

    return {
        "job_name": job_name,
        "build_number": build_number,
        "console_output": output,
        "truncated": truncated,
        "total_chars": total_chars,
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_list_jobs(
    folder: Optional[str] = None,
) -> dict:
    """List all jobs (optionally filtered to a folder).

    Args:
        folder: Optional folder name to list jobs within. When None,
                lists top-level jobs on the Jenkins instance.

    Returns:
        dict with jobs list (each item has name, url, color, last_build).
    """
    if folder:
        path = _encode_job_path(folder) + "/api/json"
    else:
        path = "/api/json"

    body, _ = _jenkins_request(path)
    data = json.loads(body)

    raw_jobs = data.get("jobs", [])
    jobs = []
    for job in raw_jobs:
        last_build = job.get("lastBuild") or {}
        jobs.append({
            "name": job.get("name", ""),
            "url": job.get("url", ""),
            "color": job.get("color", ""),
            "last_build_number": last_build.get("number"),
            "last_build_url": last_build.get("url", ""),
        })

    return {
        "folder": folder or "/",
        "total": len(jobs),
        "jobs": jobs,
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_get_job_info(
    job_name: str,
) -> dict:
    """Get detailed information about a job.

    Args:
        job_name: Job name or folder path.

    Returns:
        dict with description, buildable, health_score, recent builds summary,
        and SCM config if available.
    """
    job_path = _encode_job_path(job_name)
    body, _ = _jenkins_request("{}/api/json".format(job_path))
    data = json.loads(body)

    health_reports = data.get("healthReport", [])
    health_score = health_reports[0].get("score", None) if health_reports else None

    builds_raw = data.get("builds", [])[:10]
    builds = [
        {
            "number": b.get("number"),
            "url": b.get("url", ""),
        }
        for b in builds_raw
    ]

    last_build = data.get("lastBuild") or {}
    last_success = data.get("lastSuccessfulBuild") or {}
    last_failure = data.get("lastFailedBuild") or {}

    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "buildable": data.get("buildable", False),
        "url": data.get("url", ""),
        "health_score": health_score,
        "last_build_number": last_build.get("number"),
        "last_successful_build": last_success.get("number"),
        "last_failed_build": last_failure.get("number"),
        "recent_builds": builds,
        "in_queue": data.get("inQueue", False),
        "concurrent_build": data.get("concurrentBuild", False),
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_list_builds(
    job_name: str,
    max_builds: int = 10,
) -> dict:
    """List recent builds for a job.

    Args:
        job_name: Job name or folder path.
        max_builds: Maximum number of builds to return (default 10, max 50).

    Returns:
        dict with builds list (number, result, duration_ms, url, timestamp).
    """
    max_builds = min(max_builds, 50)
    job_path = _encode_job_path(job_name)
    api_path = "{}/api/json?tree=builds[number,result,duration,url,timestamp,building]{{0,{}}}".format(
        job_path, max_builds
    )
    body, _ = _jenkins_request(api_path)
    data = json.loads(body)

    builds_raw = data.get("builds", [])
    builds = [
        {
            "number": b.get("number"),
            "result": b.get("result"),
            "building": b.get("building", False),
            "duration_ms": b.get("duration", 0),
            "url": b.get("url", ""),
            "timestamp": b.get("timestamp", 0),
        }
        for b in builds_raw
    ]

    return {
        "job_name": job_name,
        "total_returned": len(builds),
        "builds": builds,
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_abort_build(
    job_name: str,
    build_number: int,
) -> dict:
    """Abort (stop) a running build.

    Args:
        job_name: Job name or folder path.
        build_number: Build number to abort. Use 0 for the last build.

    Returns:
        dict with aborted=True, job_name, and build_number.
    """
    job_path = _encode_job_path(job_name)
    build_ref = "lastBuild" if build_number == 0 else str(build_number)
    endpoint = "{}/{}/stop".format(job_path, build_ref)

    url = _base_url() + endpoint
    headers = {"Authorization": _build_auth_header()}
    req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    ssl_ctx = _ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ssl_ctx) as resp:
            return {
                "aborted": True,
                "job_name": job_name,
                "build_number": build_number,
                "status_code": resp.status,
            }
    except urllib.error.HTTPError as exc:
        raise ValueError(
            "Failed to abort build: HTTP {}".format(exc.code)
        ) from exc


@mcp.tool()
@mcp_tool_handler
def jenkins_get_queue_info() -> dict:
    """Get the current Jenkins build queue status.

    Returns:
        dict with items list (each item has id, why, job_name, params, blocked).
    """
    body, _ = _jenkins_request("/queue/api/json")
    data = json.loads(body)

    raw_items = data.get("items", [])
    items = []
    for item in raw_items:
        task = item.get("task", {})
        items.append({
            "id": item.get("id"),
            "why": item.get("why", ""),
            "blocked": item.get("blocked", False),
            "buildable": item.get("buildable", False),
            "job_name": task.get("name", ""),
            "job_url": task.get("url", ""),
            "params": item.get("params", ""),
            "in_queue_since": item.get("inQueueSince", 0),
        })

    return {
        "queue_length": len(items),
        "items": items,
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_wait_for_build(
    job_name: str,
    build_number: int,
    timeout_seconds: int = 300,
) -> dict:
    """Poll a build until it completes or times out.

    Polls /api/json every 5 seconds. Returns when building=false or when
    timeout_seconds is reached.

    Args:
        job_name: Job name or folder path.
        build_number: Build number to wait for. Use 0 for the last build.
        timeout_seconds: Maximum seconds to wait before giving up (default 300).

    Returns:
        dict with result, building, timed_out, elapsed_seconds, and build_number.
    """
    job_path = _encode_job_path(job_name)
    build_ref = "lastBuild" if build_number == 0 else str(build_number)
    api_path = "{}/{}/api/json".format(job_path, build_ref)

    poll_interval = 5
    start = time.time()
    result = None
    building = True
    actual_build_number = build_number
    timed_out = False

    while building:
        elapsed = time.time() - start
        if elapsed >= timeout_seconds:
            timed_out = True
            break

        body, _ = _jenkins_request(api_path)
        data = json.loads(body)
        building = data.get("building", False)
        result = data.get("result")
        actual_build_number = data.get("number", build_number)

        if not building:
            break

        time.sleep(poll_interval)

    elapsed_seconds = round(time.time() - start, 1)

    return {
        "job_name": job_name,
        "build_number": actual_build_number,
        "result": result,
        "building": building,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed_seconds,
        "timeout_seconds": timeout_seconds,
    }


@mcp.tool()
@mcp_tool_handler
def jenkins_health_check() -> dict:
    """Verify Jenkins connectivity and return basic server information.

    Performs a GET /api/json to confirm the server is reachable and
    returns version info and system details.

    Returns:
        dict with reachable=True, version, num_executors, and url.
    """
    body, _ = _jenkins_request("/api/json")
    data = json.loads(body)

    return {
        "reachable": True,
        "url": _base_url(),
        "version": data.get("version", "unknown"),
        "num_executors": data.get("numExecutors", 0),
        "description": data.get("description", ""),
        "mode": data.get("mode", ""),
        "node_name": data.get("nodeName", ""),
    }


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
