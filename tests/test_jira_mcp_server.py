"""
Tests for jira_mcp_server.py

Coverage:
  - All 10 tool functions
  - Cloud (v3/ADF) and Server (v2/plain text) modes
  - Error handling: 404, 401, connection errors
  - Transition workflow (GET transitions -> POST transition)
  - Remote link creation
  - Auth header generation (basic and bearer)
  - ADF vs plain text body helpers
  - Missing env var detection

Windows-Safe: ASCII only (cp1252 compatible)
"""

import base64
import json
import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Add src/mcp to path so the server and its base imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "mcp"))

import jira_mcp_server as jira


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(extra: dict | None = None) -> dict:
    """Return a minimal env dict for monkeypatching."""
    base = {
        "JIRA_URL": "https://company.atlassian.net",
        "JIRA_USER": "user@example.com",
        "JIRA_API_TOKEN": "secret-token",
        "JIRA_API_VERSION": "3",
        "JIRA_AUTH_METHOD": "basic",
    }
    if extra:
        base.update(extra)
    return base


def _fake_response(data: dict | list, status: int = 200) -> MagicMock:
    """Build a fake urllib response with .read() returning JSON bytes."""
    body = json.dumps(data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _parse_tool_result(result: str) -> dict:
    """Parse JSON string returned by decorated tool functions."""
    return json.loads(result)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestConfigHelpers(unittest.TestCase):
    """Tests for _get_config and auth helpers."""

    def test_get_config_reads_env_vars(self):
        with patch.dict(os.environ, _env(), clear=True):
            cfg = jira._get_config()
        self.assertEqual(cfg["url"], "https://company.atlassian.net")
        self.assertEqual(cfg["user"], "user@example.com")
        self.assertEqual(cfg["token"], "secret-token")
        self.assertEqual(cfg["api_version"], "3")
        self.assertEqual(cfg["auth_method"], "basic")

    def test_get_config_strips_trailing_slash(self):
        with patch.dict(os.environ, _env({"JIRA_URL": "https://jira.example.com/"}), clear=True):
            cfg = jira._get_config()
        self.assertEqual(cfg["url"], "https://jira.example.com")

    def test_get_config_raises_on_missing_url(self):
        env = _env()
        del env["JIRA_URL"]
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                jira._get_config()
        self.assertIn("JIRA_URL", str(ctx.exception))

    def test_get_config_raises_on_missing_user_and_token(self):
        env = _env()
        del env["JIRA_USER"]
        del env["JIRA_API_TOKEN"]
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                jira._get_config()
        err_msg = str(ctx.exception)
        self.assertIn("JIRA_USER", err_msg)
        self.assertIn("JIRA_API_TOKEN", err_msg)

    def test_basic_auth_header(self):
        cfg = {"user": "u@e.com", "token": "tok", "auth_method": "basic"}
        header = jira._build_auth_header(cfg)
        expected = base64.b64encode(b"u@e.com:tok").decode("ascii")
        self.assertEqual(header, "Basic " + expected)

    def test_bearer_auth_header(self):
        cfg = {"user": "u@e.com", "token": "myPAT", "auth_method": "bearer"}
        header = jira._build_auth_header(cfg)
        self.assertEqual(header, "Bearer myPAT")

    def test_api_url_cloud(self):
        cfg = {"url": "https://x.atlassian.net", "api_version": "3"}
        url = jira._api_url(cfg, "/issue/PROJ-1")
        self.assertEqual(url, "https://x.atlassian.net/rest/api/3/issue/PROJ-1")

    def test_api_url_server(self):
        cfg = {"url": "https://jira.corp.com", "api_version": "2"}
        url = jira._api_url(cfg, "/issue/PROJ-1")
        self.assertEqual(url, "https://jira.corp.com/rest/api/2/issue/PROJ-1")

    def test_api_url_noversion_prefix(self):
        cfg = {"url": "https://jira.corp.com", "api_version": "3"}
        url = jira._api_url(cfg, "NOVERSION:/rest/serverInfo")
        self.assertEqual(url, "https://jira.corp.com/rest/serverInfo")


class TestAdfHelpers(unittest.TestCase):
    """Tests for ADF / plain text helpers."""

    def test_text_to_adf_structure(self):
        adf = jira._text_to_adf("hello world")
        self.assertEqual(adf["type"], "doc")
        self.assertEqual(adf["version"], 1)
        self.assertEqual(adf["content"][0]["type"], "paragraph")
        self.assertEqual(adf["content"][0]["content"][0]["text"], "hello world")

    def test_description_field_cloud(self):
        cfg = {"api_version": "3"}
        result = jira._description_field(cfg, "some desc")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "doc")

    def test_description_field_server(self):
        cfg = {"api_version": "2"}
        result = jira._description_field(cfg, "some desc")
        self.assertEqual(result, "some desc")

    def test_comment_body_cloud(self):
        cfg = {"api_version": "3"}
        result = jira._comment_body_field(cfg, "my comment")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "doc")

    def test_comment_body_server(self):
        cfg = {"api_version": "2"}
        result = jira._comment_body_field(cfg, "my comment")
        self.assertEqual(result, "my comment")


class TestCreateIssue(unittest.TestCase):
    """Tests for jira_create_issue tool."""

    @patch("urllib.request.urlopen")
    def test_create_issue_cloud_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"id": "10001", "key": "PROJ-1", "self": "..."}
        )
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_create_issue(
                    project_key="PROJ",
                    summary="Test issue",
                    issue_type="Bug",
                    description="Bug description",
                )
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["issue_key"], "PROJ-1")
        self.assertIn("/browse/PROJ-1", result["issue_url"])

    @patch("urllib.request.urlopen")
    def test_create_issue_server_mode(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"id": "10002", "key": "INT-5"})
        with patch.dict(os.environ, _env({"JIRA_API_VERSION": "2"}), clear=True):
            result = _parse_tool_result(
                jira.jira_create_issue(
                    project_key="INT",
                    summary="Server issue",
                )
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["issue_key"], "INT-5")

    @patch("urllib.request.urlopen")
    def test_create_issue_with_labels_and_priority(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"id": "10003", "key": "PROJ-2"})
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_create_issue(
                    project_key="PROJ",
                    summary="Labelled",
                    priority="High",
                    labels="bug, urgent",
                )
            )
        self.assertTrue(result["success"])
        # Inspect the request body to verify labels were set
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["fields"]["labels"], ["bug", "urgent"])
        self.assertEqual(body["fields"]["priority"]["name"], "High")

    def test_create_issue_missing_env_returns_error(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _parse_tool_result(
                jira.jira_create_issue(project_key="PROJ", summary="x")
            )
        self.assertFalse(result["success"])
        self.assertIn("JIRA_URL", result["error"])


class TestGetIssue(unittest.TestCase):
    """Tests for jira_get_issue tool."""

    @patch("urllib.request.urlopen")
    def test_get_issue_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "key": "PROJ-10",
            "id": "20000",
            "fields": {
                "summary": "Fix login",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "created": "2026-01-01T00:00:00.000Z",
                "updated": "2026-01-02T00:00:00.000Z",
                "labels": ["backend"],
            }
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_get_issue("PROJ-10"))
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "Fix login")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(result["assignee"], "Alice")
        self.assertEqual(result["labels"], ["backend"])

    @patch("urllib.request.urlopen")
    def test_get_issue_404_returns_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found",
            hdrs=None, fp=BytesIO(b'{"errorMessages":["Issue does not exist"]}')
        )
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_get_issue("PROJ-9999"))
        self.assertFalse(result["success"])
        self.assertIn("404", result["error"])


class TestSearchIssues(unittest.TestCase):
    """Tests for jira_search_issues tool."""

    @patch("urllib.request.urlopen")
    def test_search_issues_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "total": 2,
            "maxResults": 20,
            "startAt": 0,
            "issues": [
                {
                    "key": "PROJ-1",
                    "fields": {
                        "summary": "Issue one",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Alice"},
                        "priority": {"name": "Medium"},
                        "issuetype": {"name": "Story"},
                        "created": "2026-01-01T00:00:00.000Z",
                    }
                },
                {
                    "key": "PROJ-2",
                    "fields": {
                        "summary": "Issue two",
                        "status": {"name": "Done"},
                        "assignee": None,
                        "priority": {"name": "Low"},
                        "issuetype": {"name": "Task"},
                        "created": "2026-01-02T00:00:00.000Z",
                    }
                }
            ]
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_search_issues('project = PROJ AND status != Done')
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["issues"][0]["issue_key"], "PROJ-1")
        self.assertEqual(result["issues"][1]["assignee"], "")

    @patch("urllib.request.urlopen")
    def test_search_respects_max_results_cap(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"total": 0, "maxResults": 100, "startAt": 0, "issues": []}
        )
        with patch.dict(os.environ, _env(), clear=True):
            jira.jira_search_issues("project = X", max_results=200)
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertLessEqual(body["maxResults"], 100)


class TestGetTransitions(unittest.TestCase):
    """Tests for jira_get_transitions tool."""

    @patch("urllib.request.urlopen")
    def test_get_transitions_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "transitions": [
                {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
                {"id": "31", "name": "Done", "to": {"name": "Done"}},
            ]
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_get_transitions("PROJ-5"))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["transitions"][0]["name"], "In Progress")
        self.assertEqual(result["transitions"][1]["to_status"], "Done")


class TestTransitionIssue(unittest.TestCase):
    """Tests for jira_transition_issue tool (GET then POST)."""

    @patch("urllib.request.urlopen")
    def test_transition_success(self, mock_urlopen):
        # First call returns transitions, second returns empty (204)
        mock_urlopen.side_effect = [
            _fake_response({
                "transitions": [
                    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
                    {"id": "31", "name": "Done", "to": {"name": "Done"}},
                ]
            }),
            _fake_response({}),  # 204 body is empty; simulate with empty dict
        ]
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_transition_issue("PROJ-7", "Done")
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["transition_applied"], "Done")
        self.assertEqual(result["transition_id"], "31")

    @patch("urllib.request.urlopen")
    def test_transition_case_insensitive(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({
                "transitions": [
                    {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
                ]
            }),
            _fake_response({}),
        ]
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_transition_issue("PROJ-7", "in progress")
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["transition_applied"], "In Progress")

    @patch("urllib.request.urlopen")
    def test_transition_not_found_raises(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "transitions": [
                {"id": "11", "name": "Open", "to": {"name": "Open"}},
            ]
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_transition_issue("PROJ-7", "NonExistent")
            )
        self.assertFalse(result["success"])
        self.assertIn("NonExistent", result["error"])
        self.assertIn("Open", result["error"])

    @patch("urllib.request.urlopen")
    def test_transition_with_comment(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _fake_response({
                "transitions": [
                    {"id": "31", "name": "Done", "to": {"name": "Done"}},
                ]
            }),
            _fake_response({}),
        ]
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_transition_issue("PROJ-7", "Done", comment="Completed!")
            )
        self.assertTrue(result["success"])
        self.assertTrue(result["comment_added"])
        # Verify comment was included in POST body
        second_call = mock_urlopen.call_args_list[1]
        req = second_call[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("update", body)
        self.assertIn("comment", body["update"])


class TestAddComment(unittest.TestCase):
    """Tests for jira_add_comment tool."""

    @patch("urllib.request.urlopen")
    def test_add_comment_cloud(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "id": "55555",
            "created": "2026-01-10T10:00:00.000Z",
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_add_comment("PROJ-3", "Great work!")
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["comment_id"], "55555")
        self.assertIn("PROJ-3", result["comment_url"])
        # Verify ADF format was sent
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIsInstance(body["body"], dict)
        self.assertEqual(body["body"]["type"], "doc")

    @patch("urllib.request.urlopen")
    def test_add_comment_server_plain_text(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "id": "66666",
            "created": "2026-01-10T10:00:00.000Z",
        })
        with patch.dict(os.environ, _env({"JIRA_API_VERSION": "2"}), clear=True):
            result = _parse_tool_result(
                jira.jira_add_comment("INT-9", "Plain text comment")
            )
        self.assertTrue(result["success"])
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        # v2: body must be a plain string
        self.assertIsInstance(body["body"], str)
        self.assertEqual(body["body"], "Plain text comment")


class TestLinkPr(unittest.TestCase):
    """Tests for jira_link_pr tool (remote link creation)."""

    @patch("urllib.request.urlopen")
    def test_link_pr_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"id": "77777", "self": "..."})
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_link_pr(
                    issue_key="PROJ-42",
                    pr_url="https://github.com/org/repo/pull/99",
                    pr_title="Fix auth bug",
                    pr_number=99,
                )
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["remote_link_id"], "77777")
        self.assertEqual(result["pr_url"], "https://github.com/org/repo/pull/99")
        self.assertEqual(result["pr_title"], "Fix auth bug")

    @patch("urllib.request.urlopen")
    def test_link_pr_auto_title_from_number(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"id": "88888"})
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_link_pr(
                    issue_key="PROJ-42",
                    pr_url="https://github.com/org/repo/pull/55",
                    pr_number=55,
                )
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["pr_title"], "PR #55")
        # Verify request body structure
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("object", body)
        self.assertEqual(body["object"]["url"], "https://github.com/org/repo/pull/55")

    @patch("urllib.request.urlopen")
    def test_link_pr_auto_title_from_url_when_no_number(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"id": "99999"})
        pr_url = "https://github.com/org/repo/pull/77"
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_link_pr(issue_key="PROJ-1", pr_url=pr_url)
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["pr_title"], pr_url)


class TestListProjects(unittest.TestCase):
    """Tests for jira_list_projects tool."""

    @patch("urllib.request.urlopen")
    def test_list_projects_cloud_v3(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "total": 2,
            "values": [
                {"key": "PROJ", "name": "Project Alpha", "projectTypeKey": "software",
                 "lead": {"displayName": "Alice"}},
                {"key": "OPS", "name": "Operations", "projectTypeKey": "business",
                 "lead": {"displayName": "Bob"}},
            ]
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_list_projects())
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["projects"][0]["key"], "PROJ")
        self.assertEqual(result["projects"][1]["lead"], "Bob")

    @patch("urllib.request.urlopen")
    def test_list_projects_server_v2_flat_list(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response([
            {"key": "INT", "name": "Integration", "projectTypeKey": "software",
             "lead": {"displayName": "Carol"}},
        ])
        with patch.dict(os.environ, _env({"JIRA_API_VERSION": "2"}), clear=True):
            result = _parse_tool_result(jira.jira_list_projects())
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["projects"][0]["key"], "INT")


class TestUpdateIssue(unittest.TestCase):
    """Tests for jira_update_issue tool."""

    @patch("urllib.request.urlopen")
    def test_update_summary_and_priority(self, mock_urlopen):
        # PUT returns 204 (no content), simulate with empty response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_update_issue(
                    issue_key="PROJ-5",
                    summary="New summary",
                    priority="Critical",
                )
            )
        self.assertTrue(result["success"])
        self.assertIn("summary", result["updated_fields"])
        self.assertIn("priority", result["updated_fields"])

    @patch("urllib.request.urlopen")
    def test_update_with_comment(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_update_issue(
                    issue_key="PROJ-5",
                    status_comment="Updated via automation",
                )
            )
        self.assertTrue(result["success"])
        self.assertIn("comment", result["updated_fields"])
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("update", body)

    def test_update_no_fields_raises(self):
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(
                jira.jira_update_issue(issue_key="PROJ-5")
            )
        self.assertFalse(result["success"])
        self.assertIn("At least one field", result["error"])


class TestHealthCheck(unittest.TestCase):
    """Tests for jira_health_check tool."""

    @patch("urllib.request.urlopen")
    def test_health_check_success(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({
            "serverTitle": "ACME Jira",
            "version": "9.12.0",
            "deploymentType": "Cloud",
        })
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_health_check())
        self.assertTrue(result["success"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["server_title"], "ACME Jira")
        self.assertEqual(result["version"], "9.12.0")
        self.assertTrue(result["cloud"])

    @patch("urllib.request.urlopen")
    def test_health_check_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Connection refused")
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_health_check())
        self.assertFalse(result["success"])
        self.assertIn("Connection refused", result["error"])

    @patch("urllib.request.urlopen")
    def test_health_check_401_unauthorized(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"errorMessages":["Login required"]}')
        )
        with patch.dict(os.environ, _env(), clear=True):
            result = _parse_tool_result(jira.jira_health_check())
        self.assertFalse(result["success"])
        self.assertIn("401", result["error"])


class TestRequestErrorHandling(unittest.TestCase):
    """Tests for HTTP error handling in _request."""

    @patch("urllib.request.urlopen")
    def test_http_error_with_json_body(self, mock_urlopen):
        import urllib.error
        err_body = json.dumps({
            "errorMessages": ["Field 'assignee' is invalid"],
            "errors": {}
        }).encode("utf-8")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=400, msg="Bad Request",
            hdrs=None, fp=BytesIO(err_body)
        )
        cfg = {
            "url": "https://x.atlassian.net",
            "user": "u", "token": "t",
            "api_version": "3", "auth_method": "basic"
        }
        with self.assertRaises(RuntimeError) as ctx:
            jira._request(cfg, "POST", "/issue", {})
        self.assertIn("400", str(ctx.exception))
        self.assertIn("assignee", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_http_error_with_non_json_body(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=500, msg="Internal Server Error",
            hdrs=None, fp=BytesIO(b"<html>Server Error</html>")
        )
        cfg = {
            "url": "https://x.atlassian.net",
            "user": "u", "token": "t",
            "api_version": "3", "auth_method": "basic"
        }
        with self.assertRaises(RuntimeError) as ctx:
            jira._request(cfg, "GET", "/issue/X-1")
        self.assertIn("500", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
