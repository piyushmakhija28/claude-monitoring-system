"""
Tests for Jenkins MCP Server (src/mcp/jenkins_mcp_server.py).

Coverage:
  - All 10 tool functions
  - Build trigger with and without parameters
  - Console output truncation at 10,000 chars
  - wait_for_build polling logic (completes, times out)
  - Error handling (HTTP 404, 401, connection error)
  - Folder job path encoding (single + nested)
  - Missing environment variable detection
  - Queue info parsing
  - Health check response

Strategy: mock urllib.request.urlopen at the module level so all HTTP is
intercepted without touching a real Jenkins instance.
"""

import importlib.util
import json
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors the pattern used in test_git_mcp_server.py)
# ---------------------------------------------------------------------------

_MCP_DIR = Path(__file__).parent.parent / "src" / "mcp"


def _load_module(name, file_path):
    """Load a module from an absolute path."""
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_jenkins_mod = _load_module(
    "jenkins_mcp_server",
    _MCP_DIR / "jenkins_mcp_server.py",
)

jenkins_trigger_build = _jenkins_mod.jenkins_trigger_build
jenkins_get_build_status = _jenkins_mod.jenkins_get_build_status
jenkins_get_console_output = _jenkins_mod.jenkins_get_console_output
jenkins_list_jobs = _jenkins_mod.jenkins_list_jobs
jenkins_get_job_info = _jenkins_mod.jenkins_get_job_info
jenkins_list_builds = _jenkins_mod.jenkins_list_builds
jenkins_abort_build = _jenkins_mod.jenkins_abort_build
jenkins_get_queue_info = _jenkins_mod.jenkins_get_queue_info
jenkins_wait_for_build = _jenkins_mod.jenkins_wait_for_build
jenkins_health_check = _jenkins_mod.jenkins_health_check
_encode_job_path = _jenkins_mod._encode_job_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result: str) -> dict:
    """Parse JSON result returned by an MCP tool."""
    return json.loads(result)


def _fake_response(body: str, status: int = 200, headers: dict = None):
    """Build a mock HTTP response object compatible with urlopen context manager."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = body.encode("utf-8")
    mock_resp.headers = headers or {}
    mock_resp.__enter__ = lambda self: self
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _http_error(code: int, reason: str = "Error"):
    """Raise a urllib.error.HTTPError with the given code."""
    return urllib.error.HTTPError(
        url="http://jenkins/api",
        code=code,
        msg=reason,
        hdrs={},
        fp=BytesIO(b""),
    )


_ENV = {
    "JENKINS_URL": "http://jenkins.test",
    "JENKINS_USER": "admin",
    "JENKINS_API_TOKEN": "secret-token",
    "JENKINS_VERIFY_SSL": "false",
}


# ---------------------------------------------------------------------------
# Test: job path encoding
# ---------------------------------------------------------------------------

class TestEncodeJobPath:
    """Unit tests for the internal _encode_job_path helper."""

    def test_single_job(self):
        assert _encode_job_path("my-job") == "/job/my-job"

    def test_two_level_folder(self):
        assert _encode_job_path("folder/my-job") == "/job/folder/job/my-job"

    def test_three_level_folder(self):
        path = _encode_job_path("team/project/deploy")
        assert path == "/job/team/job/project/job/deploy"

    def test_job_with_spaces_encoded(self):
        path = _encode_job_path("my job")
        assert "my%20job" in path or "my+job" in path or "my%20job" in path

    def test_leading_slash_stripped(self):
        assert _encode_job_path("/my-job") == "/job/my-job"


# ---------------------------------------------------------------------------
# Test: jenkins_health_check
# ---------------------------------------------------------------------------

class TestJenkinsHealthCheck:
    """Tests for jenkins_health_check tool."""

    def test_reachable_returns_version(self):
        payload = json.dumps({
            "version": "2.414.3",
            "numExecutors": 4,
            "description": "CI server",
            "mode": "NORMAL",
            "nodeName": "",
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_health_check())

        assert result["success"] is True
        assert result["reachable"] is True
        assert result["version"] == "2.414.3"
        assert result["num_executors"] == 4

    def test_connection_error_fails_gracefully(self):
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.side_effect = urllib.error.URLError("Connection refused")
                result = _parse(jenkins_health_check())

        assert result["success"] is False
        assert "error" in result

    def test_missing_jenkins_url_raises(self):
        env = {k: v for k, v in _ENV.items() if k != "JENKINS_URL"}
        with patch.dict("os.environ", env, clear=True):
            result = _parse(jenkins_health_check())
        assert result["success"] is False
        assert "JENKINS_URL" in result["error"]


# ---------------------------------------------------------------------------
# Test: jenkins_trigger_build
# ---------------------------------------------------------------------------

class TestJenkinsTriggerBuild:
    """Tests for jenkins_trigger_build tool."""

    def test_trigger_without_params(self):
        """POST to /build when no parameters given."""
        mock_resp = _fake_response(
            "", status=201,
            headers={"Location": "http://jenkins.test/queue/item/42/"}
        )
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = mock_resp
                result = _parse(jenkins_trigger_build("my-job"))

        assert result["success"] is True
        assert result["queued"] is True
        assert result["job_name"] == "my-job"
        assert "42" in result["queue_url"]

    def test_trigger_with_parameters(self):
        """POST to /buildWithParameters when parameters provided."""
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response("", status=201)

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                result = _parse(
                    jenkins_trigger_build("my-job", parameters="BRANCH=main&ENV=staging")
                )

        assert result["success"] is True
        assert "buildWithParameters" in called_url[0]
        assert "BRANCH=main" in called_url[0]

    def test_trigger_404_raises_error(self):
        """Returns error dict when job does not exist."""
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.side_effect = _http_error(404, "Not Found")
                result = _parse(jenkins_trigger_build("nonexistent-job"))

        assert result["success"] is False
        assert "error" in result

    def test_trigger_401_raises_error(self):
        """Returns error dict on authentication failure."""
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.side_effect = _http_error(401, "Unauthorized")
                result = _parse(jenkins_trigger_build("my-job"))

        assert result["success"] is False

    def test_trigger_folder_job(self):
        """Correctly encodes folder/job path."""
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response("", status=201)

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                jenkins_trigger_build("team/deploy")

        assert "/job/team/job/deploy/build" in called_url[0]


# ---------------------------------------------------------------------------
# Test: jenkins_get_build_status
# ---------------------------------------------------------------------------

class TestJenkinsGetBuildStatus:
    """Tests for jenkins_get_build_status tool."""

    def test_completed_build_status(self):
        payload = json.dumps({
            "number": 42,
            "result": "SUCCESS",
            "building": False,
            "duration": 12345,
            "url": "http://jenkins.test/job/my-job/42/",
            "timestamp": 1700000000000,
            "displayName": "#42",
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_build_status("my-job", 42))

        assert result["success"] is True
        assert result["result"] == "SUCCESS"
        assert result["building"] is False
        assert result["build_number"] == 42

    def test_running_build_status(self):
        payload = json.dumps({
            "number": 43,
            "result": None,
            "building": True,
            "duration": 0,
            "url": "http://jenkins.test/job/my-job/43/",
            "timestamp": 1700000001000,
            "displayName": "#43",
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_build_status("my-job", 43))

        assert result["success"] is True
        assert result["building"] is True
        assert result["result"] is None

    def test_build_number_zero_uses_lastbuild(self):
        """build_number=0 should target 'lastBuild' in the URL."""
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response(json.dumps({
                "number": 99, "result": "SUCCESS", "building": False,
                "duration": 100, "url": "", "timestamp": 0, "displayName": "#99",
            }))

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                jenkins_get_build_status("my-job", 0)

        assert "lastBuild" in called_url[0]


# ---------------------------------------------------------------------------
# Test: jenkins_get_console_output
# ---------------------------------------------------------------------------

class TestJenkinsGetConsoleOutput:
    """Tests for jenkins_get_console_output tool."""

    def test_short_log_not_truncated(self):
        log_text = "Build started\nBuild finished\n"
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(log_text)
                result = _parse(jenkins_get_console_output("my-job", 1))

        assert result["success"] is True
        assert result["truncated"] is False
        assert result["console_output"] == log_text
        assert result["total_chars"] == len(log_text)

    def test_long_log_truncated_to_10k(self):
        """Console output longer than 10,000 chars is truncated to last 10K."""
        long_log = "X" * 50_000
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(long_log)
                result = _parse(jenkins_get_console_output("my-job", 2))

        assert result["success"] is True
        assert result["truncated"] is True
        assert result["total_chars"] == 50_000
        assert len(result["console_output"]) == 10_000
        # Truncated output should be the LAST 10K characters
        assert result["console_output"] == long_log[-10_000:]

    def test_exactly_10k_not_truncated(self):
        """Log of exactly 10,000 chars is not truncated."""
        exact_log = "Y" * 10_000
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(exact_log)
                result = _parse(jenkins_get_console_output("my-job", 3))

        assert result["truncated"] is False
        assert len(result["console_output"]) == 10_000

    def test_console_404_returns_error(self):
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.side_effect = _http_error(404)
                result = _parse(jenkins_get_console_output("no-such-job", 1))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Test: jenkins_list_jobs
# ---------------------------------------------------------------------------

class TestJenkinsListJobs:
    """Tests for jenkins_list_jobs tool."""

    def test_list_top_level_jobs(self):
        payload = json.dumps({
            "jobs": [
                {
                    "name": "job-a",
                    "url": "http://jenkins.test/job/job-a/",
                    "color": "blue",
                    "lastBuild": {"number": 10, "url": "http://jenkins.test/job/job-a/10/"},
                },
                {
                    "name": "job-b",
                    "url": "http://jenkins.test/job/job-b/",
                    "color": "red",
                    "lastBuild": None,
                },
            ]
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_list_jobs())

        assert result["success"] is True
        assert result["total"] == 2
        assert result["jobs"][0]["name"] == "job-a"
        assert result["jobs"][0]["last_build_number"] == 10
        assert result["jobs"][1]["last_build_number"] is None

    def test_list_jobs_in_folder(self):
        payload = json.dumps({"jobs": [{"name": "child-job", "url": "", "color": "blue", "lastBuild": None}]})
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response(payload)

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                result = _parse(jenkins_list_jobs(folder="my-folder"))

        assert result["success"] is True
        assert "/job/my-folder/" in called_url[0]

    def test_list_jobs_empty(self):
        payload = json.dumps({"jobs": []})
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_list_jobs())
        assert result["total"] == 0
        assert result["jobs"] == []


# ---------------------------------------------------------------------------
# Test: jenkins_get_job_info
# ---------------------------------------------------------------------------

class TestJenkinsGetJobInfo:
    """Tests for jenkins_get_job_info tool."""

    def test_full_job_info(self):
        payload = json.dumps({
            "name": "my-job",
            "description": "Main pipeline",
            "buildable": True,
            "url": "http://jenkins.test/job/my-job/",
            "healthReport": [{"score": 80, "description": "Build stability: 1 out of 5"}],
            "builds": [{"number": 5, "url": ""}, {"number": 4, "url": ""}],
            "lastBuild": {"number": 5, "url": ""},
            "lastSuccessfulBuild": {"number": 4, "url": ""},
            "lastFailedBuild": {"number": 3, "url": ""},
            "inQueue": False,
            "concurrentBuild": False,
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_job_info("my-job"))

        assert result["success"] is True
        assert result["name"] == "my-job"
        assert result["health_score"] == 80
        assert result["last_build_number"] == 5
        assert result["last_successful_build"] == 4
        assert len(result["recent_builds"]) == 2

    def test_job_with_no_health_report(self):
        payload = json.dumps({
            "name": "bare-job",
            "description": "",
            "buildable": False,
            "url": "",
            "healthReport": [],
            "builds": [],
            "lastBuild": None,
            "lastSuccessfulBuild": None,
            "lastFailedBuild": None,
            "inQueue": False,
            "concurrentBuild": False,
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_job_info("bare-job"))

        assert result["health_score"] is None
        assert result["recent_builds"] == []


# ---------------------------------------------------------------------------
# Test: jenkins_list_builds
# ---------------------------------------------------------------------------

class TestJenkinsListBuilds:
    """Tests for jenkins_list_builds tool."""

    def test_list_builds_returns_correct_count(self):
        builds = [
            {"number": i, "result": "SUCCESS", "building": False,
             "duration": 1000, "url": "", "timestamp": i * 1000}
            for i in range(1, 6)
        ]
        payload = json.dumps({"builds": builds})
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_list_builds("my-job", max_builds=5))

        assert result["success"] is True
        assert result["total_returned"] == 5

    def test_max_builds_capped_at_50(self):
        """max_builds is capped at 50 internally."""
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response(json.dumps({"builds": []}))

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                jenkins_list_builds("my-job", max_builds=200)

        assert "{0,50}" in called_url[0]


# ---------------------------------------------------------------------------
# Test: jenkins_abort_build
# ---------------------------------------------------------------------------

class TestJenkinsAbortBuild:
    """Tests for jenkins_abort_build tool."""

    def test_abort_running_build(self):
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response("", status=200)
                result = _parse(jenkins_abort_build("my-job", 7))

        assert result["success"] is True
        assert result["aborted"] is True
        assert result["job_name"] == "my-job"
        assert result["build_number"] == 7

    def test_abort_uses_stop_endpoint(self):
        called_url = []

        def capture_urlopen(req, **kwargs):
            called_url.append(req.full_url)
            return _fake_response("", status=200)

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=capture_urlopen):
                jenkins_abort_build("my-job", 7)

        assert "/stop" in called_url[0]

    def test_abort_404_returns_error(self):
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.side_effect = _http_error(404, "Not Found")
                result = _parse(jenkins_abort_build("my-job", 999))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Test: jenkins_get_queue_info
# ---------------------------------------------------------------------------

class TestJenkinsGetQueueInfo:
    """Tests for jenkins_get_queue_info tool."""

    def test_queue_with_items(self):
        payload = json.dumps({
            "items": [
                {
                    "id": 1,
                    "why": "Waiting for executor",
                    "blocked": False,
                    "buildable": True,
                    "task": {"name": "my-job", "url": "http://jenkins.test/job/my-job/"},
                    "params": "",
                    "inQueueSince": 1700000000000,
                },
            ]
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_queue_info())

        assert result["success"] is True
        assert result["queue_length"] == 1
        assert result["items"][0]["job_name"] == "my-job"
        assert result["items"][0]["why"] == "Waiting for executor"

    def test_empty_queue(self):
        payload = json.dumps({"items": []})
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(payload)
                result = _parse(jenkins_get_queue_info())

        assert result["queue_length"] == 0
        assert result["items"] == []


# ---------------------------------------------------------------------------
# Test: jenkins_wait_for_build
# ---------------------------------------------------------------------------

class TestJenkinsWaitForBuild:
    """Tests for jenkins_wait_for_build polling logic."""

    def test_build_completes_on_first_poll(self):
        """Build is already done on the first poll -- no sleep needed."""
        payload = json.dumps({
            "number": 10,
            "result": "SUCCESS",
            "building": False,
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                with patch("time.sleep") as mock_sleep:
                    mock_open.return_value = _fake_response(payload)
                    result = _parse(jenkins_wait_for_build("my-job", 10, timeout_seconds=60))

        assert result["success"] is True
        assert result["result"] == "SUCCESS"
        assert result["building"] is False
        assert result["timed_out"] is False
        # Sleep should not be called since build finished immediately
        mock_sleep.assert_not_called()

    def test_build_completes_after_two_polls(self):
        """Build is running on first poll, done on second poll."""
        responses = [
            json.dumps({"number": 11, "result": None, "building": True}),
            json.dumps({"number": 11, "result": "FAILURE", "building": False}),
        ]
        call_count = [0]

        def urlopen_side_effect(req, **kwargs):
            resp = _fake_response(responses[call_count[0]])
            call_count[0] += 1
            return resp

        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
                with patch("time.sleep"):
                    result = _parse(jenkins_wait_for_build("my-job", 11, timeout_seconds=60))

        assert result["result"] == "FAILURE"
        assert result["timed_out"] is False

    def test_wait_times_out(self):
        """Returns timed_out=True when timeout_seconds is exceeded."""
        running_payload = json.dumps({
            "number": 12,
            "result": None,
            "building": True,
        })
        with patch.dict("os.environ", _ENV):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_response(running_payload)
                # Use a tiny timeout and mock time so it expires fast
                with patch("time.sleep"):
                    with patch("time.time") as mock_time:
                        # Return 0 on first call (start), then 400 (past timeout)
                        mock_time.side_effect = [0, 400, 400]
                        result = _parse(jenkins_wait_for_build("my-job", 12, timeout_seconds=300))

        assert result["timed_out"] is True
        assert result["building"] is True


# ---------------------------------------------------------------------------
# Test: missing environment variables
# ---------------------------------------------------------------------------

class TestMissingEnvVars:
    """Tests that missing env vars produce meaningful error messages."""

    def test_missing_jenkins_user(self):
        env = {k: v for k, v in _ENV.items() if k != "JENKINS_USER"}
        with patch.dict("os.environ", env, clear=True):
            result = _parse(jenkins_health_check())
        assert result["success"] is False
        assert "JENKINS_USER" in result["error"]

    def test_missing_jenkins_token(self):
        env = {k: v for k, v in _ENV.items() if k != "JENKINS_API_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            result = _parse(jenkins_health_check())
        assert result["success"] is False
        assert "JENKINS_API_TOKEN" in result["error"]
