"""
Jira MCP Server - FastMCP-based Jira integration for Claude Code.

Supports both Jira Cloud (v3, ADF format) and Jira Server/Data Center (v2, plain text).
Backend: urllib.request (stdlib only, no external deps)
Transport: stdio

Tools (10):
  jira_create_issue, jira_get_issue, jira_search_issues,
  jira_transition_issue, jira_add_comment, jira_link_pr,
  jira_list_projects, jira_get_transitions, jira_update_issue,
  jira_health_check

Environment Variables:
  JIRA_URL          - Base URL (e.g. https://company.atlassian.net)
  JIRA_USER         - Email (Cloud) or username (Server)
  JIRA_API_TOKEN    - API token (Cloud) or PAT (Server)
  JIRA_API_VERSION  - "3" (Cloud, default) or "2" (Server/DC)
  JIRA_AUTH_METHOD  - "basic" (default) or "bearer" (PAT for Server)

Windows-Safe: ASCII only (cp1252 compatible)
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.decorators import mcp_tool_handler

mcp = FastMCP(
    "jira-api",
    instructions="Jira operations via REST API (Cloud v3 ADF + Server v2 plain text)"
)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 30  # seconds for all HTTP calls


def _get_config() -> Dict[str, str]:
    """Read Jira config from environment variables.

    Returns:
        Dict with url, user, token, api_version, auth_method keys.

    Raises:
        EnvironmentError: If JIRA_URL, JIRA_USER, or JIRA_API_TOKEN are missing.
    """
    url = os.environ.get("JIRA_URL", "").rstrip("/")
    user = os.environ.get("JIRA_USER", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    api_version = os.environ.get("JIRA_API_VERSION", "3")
    auth_method = os.environ.get("JIRA_AUTH_METHOD", "basic").lower()

    missing = []
    if not url:
        missing.append("JIRA_URL")
    if not user:
        missing.append("JIRA_USER")
    if not token:
        missing.append("JIRA_API_TOKEN")

    if missing:
        raise EnvironmentError(
            "Missing required Jira environment variables: "
            + ", ".join(missing)
            + ". Set them before using jira_* tools."
        )

    return {
        "url": url,
        "user": user,
        "token": token,
        "api_version": api_version,
        "auth_method": auth_method,
    }


def _build_auth_header(cfg: Dict[str, str]) -> str:
    """Build Authorization header value based on auth_method.

    Args:
        cfg: Config dict from _get_config().

    Returns:
        Authorization header string (e.g. "Basic ..." or "Bearer ...").
    """
    if cfg["auth_method"] == "bearer":
        return "Bearer " + cfg["token"]
    # Default: Basic auth with user:token
    credentials = cfg["user"] + ":" + cfg["token"]
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return "Basic " + encoded


def _api_url(cfg: Dict[str, str], path: str) -> str:
    """Build a full Jira REST API URL.

    Args:
        cfg: Config dict.
        path: API path starting with / (e.g. /issue/PROJ-123).
            Use the special prefix NOVERSION: to bypass version prefix
            (e.g. NOVERSION:/rest/serverInfo).

    Returns:
        Full URL string.
    """
    if path.startswith("NOVERSION:"):
        return cfg["url"] + path[len("NOVERSION:"):]
    return cfg["url"] + "/rest/api/" + cfg["api_version"] + path


def _request(
    cfg: Dict[str, str],
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Any:
    """Execute a Jira REST API request.

    Args:
        cfg: Config dict from _get_config().
        method: HTTP method (GET, POST, PUT, DELETE).
        path: API path starting with / (e.g. /issue/PROJ-123).
        body: Optional request body dict (serialized to JSON).

    Returns:
        Parsed JSON response as dict/list, or None for 204 responses.

    Raises:
        urllib.error.HTTPError: On HTTP error responses.
        RuntimeError: On non-HTTP errors.
    """
    url = _api_url(cfg, path)
    auth_header = _build_auth_header(cfg)

    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_body = exc.read()
        try:
            err_json = json.loads(raw_body.decode("utf-8"))
            messages = err_json.get("errorMessages", [])
            errors = err_json.get("errors", {})
            detail = "; ".join(messages) if messages else str(errors)
        except Exception:
            detail = raw_body.decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            "Jira API error " + str(exc.code) + ": " + detail
        ) from exc


# ---------------------------------------------------------------------------
# ADF (Atlassian Document Format) helpers for Cloud v3
# ---------------------------------------------------------------------------

def _is_cloud(cfg: Dict[str, str]) -> bool:
    """Return True when configured for Jira Cloud (API version 3)."""
    return cfg["api_version"] == "3"


def _text_to_adf(text: str) -> Dict[str, Any]:
    """Wrap plain text in minimal ADF document format (Cloud v3).

    Args:
        text: Plain text content to wrap.

    Returns:
        ADF document dict.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": text}
                ]
            }
        ]
    }


def _description_field(cfg: Dict[str, str], text: str) -> Any:
    """Return the appropriate description/body value for the API version.

    Args:
        cfg: Config dict.
        text: Plain text content.

    Returns:
        ADF dict for v3 (Cloud) or plain string for v2 (Server).
    """
    if _is_cloud(cfg):
        return _text_to_adf(text)
    return text


def _comment_body_field(cfg: Dict[str, str], text: str) -> Any:
    """Return the appropriate comment body for the API version.

    Args:
        cfg: Config dict.
        text: Plain text content.

    Returns:
        ADF dict for v3 (Cloud) or plain string for v2 (Server).
    """
    if _is_cloud(cfg):
        return _text_to_adf(text)
    return text


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def jira_create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str = "",
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[str] = None,
) -> dict:
    """Create a Jira issue.

    Args:
        project_key: Jira project key (e.g. PROJ).
        summary: Issue summary/title.
        issue_type: Issue type name (e.g. Task, Bug, Story). Default: Task.
        description: Issue description (plain text; converted to ADF for Cloud).
        priority: Priority name (e.g. High, Medium, Low). Optional.
        assignee: Assignee account ID (Cloud) or username (Server). Optional.
        labels: Comma-separated label names. Optional.
    """
    cfg = _get_config()

    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }

    if description:
        fields["description"] = _description_field(cfg, description)

    if priority:
        fields["priority"] = {"name": priority}

    if assignee:
        if _is_cloud(cfg):
            fields["assignee"] = {"accountId": assignee}
        else:
            fields["assignee"] = {"name": assignee}

    if labels:
        label_list = [lb.strip() for lb in labels.split(",") if lb.strip()]
        if label_list:
            fields["labels"] = label_list

    body = {"fields": fields}
    result = _request(cfg, "POST", "/issue", body)

    return {
        "issue_key": result.get("key"),
        "issue_id": result.get("id"),
        "issue_url": cfg["url"] + "/browse/" + result.get("key", ""),
        "project_key": project_key,
        "summary": summary,
        "issue_type": issue_type,
    }


@mcp.tool()
@mcp_tool_handler
def jira_get_issue(
    issue_key: str,
    fields: Optional[str] = None,
) -> dict:
    """Get Jira issue details by key.

    Args:
        issue_key: Issue key (e.g. PROJ-123).
        fields: Comma-separated field names to include. Optional (default: common fields).
    """
    cfg = _get_config()

    path = "/issue/" + issue_key
    if fields:
        path += "?fields=" + urllib.request.quote(fields)

    result = _request(cfg, "GET", path)
    raw_fields = result.get("fields", {})

    # Extract assignee safely across v2/v3
    assignee_raw = raw_fields.get("assignee") or {}
    assignee_name = (
        assignee_raw.get("displayName")
        or assignee_raw.get("name")
        or ""
    )

    # Extract reporter safely
    reporter_raw = raw_fields.get("reporter") or {}
    reporter_name = (
        reporter_raw.get("displayName")
        or reporter_raw.get("name")
        or ""
    )

    # Extract status
    status_raw = raw_fields.get("status") or {}
    status_name = status_raw.get("name", "")

    # Extract priority
    priority_raw = raw_fields.get("priority") or {}
    priority_name = priority_raw.get("name", "")

    # Extract issue type
    issuetype_raw = raw_fields.get("issuetype") or {}
    issuetype_name = issuetype_raw.get("name", "")

    return {
        "issue_key": result.get("key"),
        "issue_id": result.get("id"),
        "issue_url": cfg["url"] + "/browse/" + result.get("key", ""),
        "summary": raw_fields.get("summary", ""),
        "status": status_name,
        "issue_type": issuetype_name,
        "priority": priority_name,
        "assignee": assignee_name,
        "reporter": reporter_name,
        "created": raw_fields.get("created", ""),
        "updated": raw_fields.get("updated", ""),
        "labels": raw_fields.get("labels", []),
    }


@mcp.tool()
@mcp_tool_handler
def jira_search_issues(
    jql: str,
    max_results: int = 20,
    start_at: int = 0,
    fields: Optional[str] = None,
) -> dict:
    """Search Jira issues using JQL (Jira Query Language).

    Args:
        jql: JQL query string (e.g. 'project = PROJ AND status = "In Progress"').
        max_results: Maximum number of results to return (default: 20, max: 100).
        start_at: Zero-based index for pagination (default: 0).
        fields: Comma-separated field names to include. Optional.
    """
    cfg = _get_config()

    body: Dict[str, Any] = {
        "jql": jql,
        "maxResults": min(max_results, 100),
        "startAt": start_at,
    }

    if fields:
        body["fields"] = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        body["fields"] = ["summary", "status", "assignee", "priority", "issuetype", "created"]

    result = _request(cfg, "POST", "/issue/search", body)

    issues = []
    for issue in result.get("issues", []):
        raw_fields = issue.get("fields", {})
        assignee_raw = raw_fields.get("assignee") or {}
        status_raw = raw_fields.get("status") or {}
        priority_raw = raw_fields.get("priority") or {}
        issuetype_raw = raw_fields.get("issuetype") or {}

        issues.append({
            "issue_key": issue.get("key"),
            "issue_url": cfg["url"] + "/browse/" + issue.get("key", ""),
            "summary": raw_fields.get("summary", ""),
            "status": status_raw.get("name", ""),
            "issue_type": issuetype_raw.get("name", ""),
            "priority": priority_raw.get("name", ""),
            "assignee": (
                assignee_raw.get("displayName")
                or assignee_raw.get("name")
                or ""
            ),
            "created": raw_fields.get("created", ""),
        })

    return {
        "total": result.get("total", 0),
        "max_results": result.get("maxResults", 0),
        "start_at": result.get("startAt", 0),
        "issues": issues,
    }


@mcp.tool()
@mcp_tool_handler
def jira_get_transitions(issue_key: str) -> dict:
    """Get available workflow transitions for a Jira issue.

    Args:
        issue_key: Issue key (e.g. PROJ-123).
    """
    cfg = _get_config()

    result = _request(cfg, "GET", "/issue/" + issue_key + "/transitions")

    transitions = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "to_status": (t.get("to") or {}).get("name", ""),
        }
        for t in result.get("transitions", [])
    ]

    return {
        "issue_key": issue_key,
        "transitions": transitions,
        "count": len(transitions),
    }


@mcp.tool()
@mcp_tool_handler
def jira_transition_issue(
    issue_key: str,
    transition_name: str,
    comment: str = "",
) -> dict:
    """Move a Jira issue through its workflow by transition name.

    This first fetches available transitions (GET), then posts the matching one (POST).

    Args:
        issue_key: Issue key (e.g. PROJ-123).
        transition_name: Transition name (e.g. "In Progress", "Done"). Case-insensitive.
        comment: Optional comment to add when transitioning.
    """
    cfg = _get_config()

    # Step 1: GET available transitions
    transitions_result = _request(cfg, "GET", "/issue/" + issue_key + "/transitions")
    transitions = transitions_result.get("transitions", [])

    # Find matching transition (case-insensitive)
    matched = None
    for t in transitions:
        if t.get("name", "").lower() == transition_name.lower():
            matched = t
            break

    if matched is None:
        available = [t.get("name", "") for t in transitions]
        raise ValueError(
            "Transition '" + transition_name + "' not found for " + issue_key
            + ". Available: " + ", ".join(available)
        )

    # Step 2: POST the transition
    body: Dict[str, Any] = {
        "transition": {"id": matched["id"]}
    }

    if comment:
        body["update"] = {
            "comment": [
                {
                    "add": {
                        "body": _comment_body_field(cfg, comment)
                    }
                }
            ]
        }

    _request(cfg, "POST", "/issue/" + issue_key + "/transitions", body)

    return {
        "issue_key": issue_key,
        "transition_applied": matched["name"],
        "transition_id": matched["id"],
        "new_status": (matched.get("to") or {}).get("name", ""),
        "comment_added": bool(comment),
    }


@mcp.tool()
@mcp_tool_handler
def jira_add_comment(
    issue_key: str,
    body: str,
) -> dict:
    """Add a comment to a Jira issue.

    Args:
        issue_key: Issue key (e.g. PROJ-123).
        body: Comment text (plain text; converted to ADF for Cloud v3).
    """
    cfg = _get_config()

    payload: Dict[str, Any] = {
        "body": _comment_body_field(cfg, body)
    }

    result = _request(cfg, "POST", "/issue/" + issue_key + "/comment", payload)

    return {
        "issue_key": issue_key,
        "comment_id": result.get("id"),
        "comment_url": (
            cfg["url"] + "/browse/" + issue_key
            + "?focusedCommentId=" + str(result.get("id", ""))
        ),
        "created": result.get("created", ""),
    }


@mcp.tool()
@mcp_tool_handler
def jira_link_pr(
    issue_key: str,
    pr_url: str,
    pr_title: str = "",
    pr_number: Optional[int] = None,
) -> dict:
    """Create a remote link from a Jira issue to a GitHub Pull Request.

    Uses POST /rest/api/{version}/issue/{key}/remotelink

    Args:
        issue_key: Issue key (e.g. PROJ-123).
        pr_url: Full URL of the GitHub PR.
        pr_title: Display title for the link. Defaults to 'PR #{pr_number}'.
        pr_number: PR number for generating a default title. Optional.
    """
    cfg = _get_config()

    if not pr_title:
        if pr_number is not None:
            pr_title = "PR #" + str(pr_number)
        else:
            pr_title = pr_url

    payload: Dict[str, Any] = {
        "object": {
            "url": pr_url,
            "title": pr_title,
            "icon": {
                "url16x16": "https://github.com/favicon.ico",
                "title": "GitHub"
            }
        },
        "application": {
            "type": "com.github",
            "name": "GitHub"
        },
        "relationship": "is implemented in"
    }

    result = _request(cfg, "POST", "/issue/" + issue_key + "/remotelink", payload)

    return {
        "issue_key": issue_key,
        "remote_link_id": result.get("id"),
        "pr_url": pr_url,
        "pr_title": pr_title,
        "link_url": cfg["url"] + "/browse/" + issue_key,
    }


@mcp.tool()
@mcp_tool_handler
def jira_list_projects(
    max_results: int = 50,
    project_type: Optional[str] = None,
) -> dict:
    """List accessible Jira projects.

    Args:
        max_results: Maximum number of projects to return (default: 50).
        project_type: Filter by project type (e.g. 'software', 'business'). Optional.
    """
    cfg = _get_config()

    path = "/project/search?maxResults=" + str(min(max_results, 100))
    if project_type:
        path += "&typeKey=" + urllib.request.quote(project_type)

    result = _request(cfg, "GET", path)

    # Jira v3 returns {"values": [...], "total": N}
    # Jira v2 returns a flat list
    raw_list = result if isinstance(result, list) else result.get("values", [])

    projects = [
        {
            "key": p.get("key"),
            "name": p.get("name"),
            "project_type": p.get("projectTypeKey", ""),
            "lead": (p.get("lead") or {}).get("displayName", ""),
            "url": cfg["url"] + "/jira/software/projects/" + p.get("key", "") + "/boards",
        }
        for p in raw_list
    ]

    return {
        "total": result.get("total", len(projects)) if isinstance(result, dict) else len(projects),
        "projects": projects,
        "count": len(projects),
    }


@mcp.tool()
@mcp_tool_handler
def jira_update_issue(
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[str] = None,
    status_comment: Optional[str] = None,
) -> dict:
    """Update fields on an existing Jira issue.

    Only the provided (non-None) fields are updated.

    Args:
        issue_key: Issue key (e.g. PROJ-123).
        summary: New summary/title. Optional.
        description: New description (plain text). Optional.
        priority: Priority name (e.g. High, Medium). Optional.
        assignee: Assignee account ID (Cloud) or username (Server). Optional.
        labels: Comma-separated label names (replaces existing labels). Optional.
        status_comment: Comment to add alongside the update. Optional.
    """
    cfg = _get_config()

    fields: Dict[str, Any] = {}

    if summary is not None:
        fields["summary"] = summary

    if description is not None:
        fields["description"] = _description_field(cfg, description)

    if priority is not None:
        fields["priority"] = {"name": priority}

    if assignee is not None:
        if _is_cloud(cfg):
            fields["assignee"] = {"accountId": assignee}
        else:
            fields["assignee"] = {"name": assignee}

    if labels is not None:
        label_list = [lb.strip() for lb in labels.split(",") if lb.strip()]
        fields["labels"] = label_list

    if not fields and not status_comment:
        raise ValueError("At least one field to update or a status_comment must be provided.")

    body: Dict[str, Any] = {}
    if fields:
        body["fields"] = fields

    if status_comment:
        body["update"] = {
            "comment": [
                {
                    "add": {
                        "body": _comment_body_field(cfg, status_comment)
                    }
                }
            ]
        }

    # PUT /rest/api/{version}/issue/{key} returns 204 No Content on success
    _request(cfg, "PUT", "/issue/" + issue_key, body)

    updated_fields = list(fields.keys())
    if status_comment:
        updated_fields.append("comment")

    return {
        "issue_key": issue_key,
        "issue_url": cfg["url"] + "/browse/" + issue_key,
        "updated_fields": updated_fields,
    }


@mcp.tool()
@mcp_tool_handler
def jira_health_check() -> dict:
    """Verify Jira connectivity and configuration.

    Calls the Jira server-info endpoint to confirm the connection works.
    """
    cfg = _get_config()

    result = _request(cfg, "GET", "NOVERSION:/rest/serverInfo")

    return {
        "connected": True,
        "jira_url": cfg["url"],
        "api_version": cfg["api_version"],
        "auth_method": cfg["auth_method"],
        "server_title": result.get("serverTitle", ""),
        "version": result.get("version", ""),
        "deployment_type": result.get("deploymentType", ""),
        "cloud": _is_cloud(cfg),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
