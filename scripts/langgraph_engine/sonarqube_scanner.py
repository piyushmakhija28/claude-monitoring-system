"""
SonarQube Scanner Integration

Integrates SonarQube/SonarCloud scanning into the pipeline after Step 10
(implementation) to detect bugs, vulnerabilities, and code smells.

API-FIRST design: all issue retrieval goes through the SonarQube REST API
(urllib only, no SDK).  The sonar-scanner CLI is used only for triggering a
new scan; results are always fetched via the API regardless of whether the
CLI ran.

Degradation chain:
  1. API available  -> fetch issues + measures via REST API
  2. API unavailable, CLI available -> CLI scan; results via report-task.txt
  3. Neither available -> run_basic_scan() fallback (AST + regex, Python only)

Configuration is read from environment variables; see get_sonar_config() for
the full list.  Defaults point at http://localhost:9000 so a local SonarQube
instance works out of the box.

All functions are standalone (no class state) so they can be imported and
called directly from the pipeline or from tests without any setup.
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env vars + defaults)
# ---------------------------------------------------------------------------

_DEFAULT_SONAR_URL = "http://localhost:9000"


def get_sonar_config() -> Dict[str, Any]:
    """Get SonarQube configuration from environment.

    Reads all SonarQube settings from environment variables and returns a
    single config dict.  Never raises; missing values are represented as
    empty strings or False.

    Environment variables:
        SONAR_HOST_URL       - Base URL of the SonarQube/SonarCloud server
                               (default: http://localhost:9000)
        SONAR_TOKEN          - Authentication token (user or project token)
        SONAR_PROJECT_KEY    - Project key for API calls
        SONAR_ORGANIZATION   - Organization key (required for SonarCloud)

    Returns:
        Dict with keys:
            host_url (str):       Server base URL.
            token (str):          Auth token, or empty string if not set.
            project_key (str):    Project key, or empty string if not set.
            organization (str):   Organization key, or empty string if not set.
            is_cloud (bool):      True when the host URL contains sonarcloud.io.
    """
    host_url = os.environ.get("SONAR_HOST_URL", _DEFAULT_SONAR_URL)
    return {
        "host_url": host_url,
        "token": os.environ.get("SONAR_TOKEN", ""),
        "project_key": os.environ.get("SONAR_PROJECT_KEY", ""),
        "organization": os.environ.get("SONAR_ORGANIZATION", ""),
        "is_cloud": "sonarcloud.io" in host_url,
    }


# ---------------------------------------------------------------------------
# Internal helpers - low-level utilities
# ---------------------------------------------------------------------------

def _read_lines_around(file_path: str, line: int, context: int = 10) -> str:
    """Return up to *context* lines before and after *line* from *file_path*.

    Args:
        file_path: Absolute or relative path to the source file.
        line:      1-based line number of the finding.
        context:   Number of lines to include on each side.

    Returns:
        A formatted code snippet string, or an empty string on read error.
    """
    try:
        p = Path(file_path)
        if not p.exists():
            return ""
        all_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line - 1 - context)
        end = min(len(all_lines), line - 1 + context + 1)
        snippet_lines = []
        for idx in range(start, end):
            marker = ">>>" if idx == line - 1 else "   "
            snippet_lines.append(f"{marker} {idx + 1:4d} | {all_lines[idx]}")
        return "\n".join(snippet_lines)
    except Exception as exc:
        logger.debug("Could not read context for %s:%d: %s", file_path, line, exc)
        return ""


def _parse_report_task(report_task_path: Path) -> Dict[str, str]:
    """Parse .scannerwork/report-task.txt into a key->value dict."""
    result: Dict[str, str] = {}
    try:
        for raw_line in report_task_path.read_text(encoding="utf-8").splitlines():
            if "=" in raw_line:
                key, _, value = raw_line.partition("=")
                result[key.strip()] = value.strip()
    except Exception as exc:
        logger.debug("Could not parse report-task.txt: %s", exc)
    return result


def _build_auth_header(token: str) -> str:
    """Build an HTTP Basic auth header value from a SonarQube token.

    SonarQube uses HTTP Basic auth with the token as the username and an
    empty password: base64("token:").

    Args:
        token: SonarQube user or project authentication token.

    Returns:
        String suitable for use as an Authorization header value.
    """
    token_bytes = f"{token}:".encode("utf-8")
    return "Basic " + base64.b64encode(token_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# SonarQube REST API client (urllib only, no SDK)
# ---------------------------------------------------------------------------

def _sonar_api_get(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Call the SonarQube REST API via GET.

    Args:
        endpoint: API path, e.g. "/api/issues/search".
        params:   Optional query parameters dict.
        config:   Sonar config dict from get_sonar_config().  If None, calls
                  get_sonar_config() internally.

    Returns:
        Parsed JSON response dict, or None on any error.
    """
    if config is None:
        config = get_sonar_config()

    try:
        base = config["host_url"].rstrip("/")
        url = base + endpoint
        if params:
            url = url + "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url)
        token = config.get("token", "")
        if token:
            req.add_header("Authorization", _build_auth_header(token))
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        logger.debug("SonarQube API GET %s failed: HTTP %d", endpoint, exc.code)
        return None
    except urllib.error.URLError as exc:
        logger.debug("SonarQube API GET %s unreachable: %s", endpoint, exc.reason)
        return None
    except Exception as exc:
        logger.debug("SonarQube API GET %s error: %s", endpoint, exc)
        return None


def _sonar_api_post(
    endpoint: str,
    data: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Call the SonarQube REST API via POST.

    Args:
        endpoint: API path, e.g. "/api/projects/create".
        data:     Optional form data dict (sent as application/x-www-form-urlencoded).
        config:   Sonar config dict from get_sonar_config().  If None, calls
                  get_sonar_config() internally.

    Returns:
        Parsed JSON response dict, or None on any error.
    """
    if config is None:
        config = get_sonar_config()

    try:
        base = config["host_url"].rstrip("/")
        url = base + endpoint

        encoded_data = urllib.parse.urlencode(data or {}).encode("utf-8")
        req = urllib.request.Request(url, data=encoded_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")

        token = config.get("token", "")
        if token:
            req.add_header("Authorization", _build_auth_header(token))

        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}

    except urllib.error.HTTPError as exc:
        logger.debug("SonarQube API POST %s failed: HTTP %d", endpoint, exc.code)
        return None
    except urllib.error.URLError as exc:
        logger.debug("SonarQube API POST %s unreachable: %s", endpoint, exc.reason)
        return None
    except Exception as exc:
        logger.debug("SonarQube API POST %s error: %s", endpoint, exc)
        return None


def _sonar_issue_to_finding(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw SonarQube API issue dict to the pipeline finding schema."""
    component = issue.get("component", "")
    # Strip module prefix (e.g. "myapp:src/foo.py" -> "src/foo.py")
    file_path = component.split(":", 1)[-1] if ":" in component else component

    text_range = issue.get("textRange", {})
    line_no = text_range.get("startLine", issue.get("line", 0))

    return {
        "file": file_path,
        "line": line_no,
        "severity": issue.get("severity", "UNKNOWN"),
        "type": issue.get("type", "UNKNOWN"),
        "rule": issue.get("rule", ""),
        "message": issue.get("message", ""),
        # Additional fields from API that enrich the finding
        "status": issue.get("status", ""),
        "effort": issue.get("effort", ""),
        "debt": issue.get("debt", ""),
        "tags": issue.get("tags", []),
    }


# ---------------------------------------------------------------------------
# Public API - installation detection
# ---------------------------------------------------------------------------

def detect_sonar_installation() -> Dict[str, Any]:
    """Check whether sonar-scanner CLI is installed and whether the API is reachable.

    Performs two independent checks:
      1. CLI check: runs ``sonar-scanner --version`` with a short timeout.
      2. API check: calls GET /api/system/status on the configured host URL.
         This succeeds even without sonar-scanner CLI, as long as the server
         is running.  When the API is reachable, scanning can work via the
         API alone (for SonarCloud or if a CI/CD system triggered the scan).

    Also reads *sonar-project.properties* for the host URL when SONAR_HOST_URL
    is not set in the environment.

    Returns:
        Dict with keys:
            installed (bool):        True if sonar-scanner CLI was found.
            version (str | None):    Reported CLI version string, or None.
            config_found (bool):     True if sonar-project.properties exists.
            sonar_host_url (str | None): Resolved host URL, or None.
            api_available (bool):    True if the SonarQube REST API responded.
            server_status (str):     "UP", "STARTING", "DOWN", or "UNKNOWN".
    """
    result: Dict[str, Any] = {
        "installed": False,
        "version": None,
        "config_found": False,
        "sonar_host_url": None,
        "api_available": False,
        "server_status": "UNKNOWN",
    }

    # 1. Check CLI availability
    try:
        proc = subprocess.run(
            ["sonar-scanner", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            result["installed"] = True
            for raw_line in (proc.stdout + proc.stderr).splitlines():
                if "sonarscanner" in raw_line.lower() or "sonar scanner" in raw_line.lower():
                    result["version"] = raw_line.strip()
                    break
    except FileNotFoundError:
        logger.debug("sonar-scanner not found in PATH")
    except subprocess.TimeoutExpired:
        logger.debug("sonar-scanner --version timed out")
    except Exception as exc:
        logger.debug("sonar-scanner check failed: %s", exc)

    # 2. Check for project config file
    config_path = Path("sonar-project.properties")
    result["config_found"] = config_path.exists()

    # 3. Determine host URL (env takes precedence over config file)
    config = get_sonar_config()
    host_url = config["host_url"] if config["host_url"] != _DEFAULT_SONAR_URL else None

    # Fall back to sonar-project.properties if env not set
    if not host_url and result["config_found"]:
        try:
            for raw_line in config_path.read_text(encoding="utf-8").splitlines():
                if raw_line.startswith("sonar.host.url"):
                    _, _, host_url = raw_line.partition("=")
                    host_url = host_url.strip()
                    break
        except Exception as exc:
            logger.debug("Could not read sonar-project.properties: %s", exc)

    # Use env value if available even if it is the default
    if not host_url:
        env_url = os.environ.get("SONAR_HOST_URL", "")
        host_url = env_url if env_url else _DEFAULT_SONAR_URL

    result["sonar_host_url"] = host_url

    # 4. API health check: GET /api/system/status
    api_config = dict(config)
    api_config["host_url"] = host_url
    status_data = _sonar_api_get("/api/system/status", config=api_config)
    if status_data is not None:
        server_status = status_data.get("status", "UNKNOWN")
        result["api_available"] = server_status == "UP"
        result["server_status"] = server_status
        logger.debug(
            "SonarQube API at %s responded: status=%s", host_url, server_status
        )
    else:
        logger.debug("SonarQube API at %s not reachable", host_url)

    return result


# ---------------------------------------------------------------------------
# Public API - SonarQube REST API wrappers
# ---------------------------------------------------------------------------

def get_project_issues(
    project_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    severities: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    """Get issues from the SonarQube API for a project.

    Calls GET /api/issues/search and returns all issues up to *page_size*.
    SonarQube handles language detection and project creation; the user only
    needs a project that has been analysed at least once (or SonarCloud with
    GitHub auto-analysis enabled).

    Args:
        project_key: Project key.  Falls back to SONAR_PROJECT_KEY env var.
        config:      Sonar config dict.  If None, calls get_sonar_config().
        severities:  Optional list of severity filters, e.g. ["CRITICAL", "MAJOR"].
        types:       Optional list of type filters, e.g. ["BUG", "VULNERABILITY"].
        page_size:   Maximum number of issues to return (max 500 per SonarQube
                     API page).

    Returns:
        List of finding dicts in the pipeline's standard format.
        Returns an empty list if the API is unavailable or the project has no
        issues.
    """
    if config is None:
        config = get_sonar_config()

    key = project_key or config.get("project_key", "")
    if not key:
        logger.debug("get_project_issues: no project_key available")
        return []

    params: Dict[str, str] = {
        "componentKeys": key,
        "ps": str(min(page_size, 500)),
    }
    if severities:
        params["severities"] = ",".join(severities)
    if types:
        params["types"] = ",".join(types)
    if config.get("organization"):
        params["organization"] = config["organization"]

    data = _sonar_api_get("/api/issues/search", params=params, config=config)
    if data is None:
        return []

    raw_issues = data.get("issues", [])
    return [_sonar_issue_to_finding(issue) for issue in raw_issues]


def get_project_measures(
    project_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get project quality measures from the SonarQube API.

    Calls GET /api/measures/component and returns a normalized dict of the
    most important quality metrics.

    Args:
        project_key: Project key.  Falls back to SONAR_PROJECT_KEY env var.
        config:      Sonar config dict.  If None, calls get_sonar_config().

    Returns:
        Dict with keys:
            bugs (int):            Number of open bug issues.
            vulnerabilities (int): Number of open vulnerability issues.
            code_smells (int):     Number of open code smell issues.
            coverage (float):      Test coverage percentage (0-100), or -1.0
                                   if not available.
            duplications (float):  Duplicated lines density percentage, or -1.0
                                   if not available.
            lines (int):           Total lines of code.
            quality_gate (str):    "OK", "ERROR", "WARN", or "UNKNOWN".
            raw (dict):            Raw metric key-value map from the API.
        Returns all numeric fields as their zero/default values if the API
        is unavailable.
    """
    if config is None:
        config = get_sonar_config()

    key = project_key or config.get("project_key", "")

    default: Dict[str, Any] = {
        "bugs": 0,
        "vulnerabilities": 0,
        "code_smells": 0,
        "coverage": -1.0,
        "duplications": -1.0,
        "lines": 0,
        "quality_gate": "UNKNOWN",
        "raw": {},
    }

    if not key:
        logger.debug("get_project_measures: no project_key available")
        return default

    metric_keys = (
        "bugs,vulnerabilities,code_smells,coverage,"
        "duplicated_lines_density,ncloc,sqale_rating,alert_status"
    )
    params: Dict[str, str] = {
        "component": key,
        "metricKeys": metric_keys,
    }
    if config.get("organization"):
        params["organization"] = config["organization"]

    data = _sonar_api_get("/api/measures/component", params=params, config=config)
    if data is None:
        return default

    component = data.get("component", {})
    measures = component.get("measures", [])

    raw: Dict[str, str] = {}
    for m in measures:
        raw[m["metric"]] = m.get("value", "")

    def _int(key_name: str) -> int:
        try:
            return int(raw.get(key_name, 0) or 0)
        except (ValueError, TypeError):
            return 0

    def _float(key_name: str) -> float:
        try:
            return float(raw.get(key_name, -1.0) or -1.0)
        except (ValueError, TypeError):
            return -1.0

    alert_status = raw.get("alert_status", "UNKNOWN")
    if alert_status not in ("OK", "ERROR", "WARN"):
        alert_status = "UNKNOWN"

    return {
        "bugs": _int("bugs"),
        "vulnerabilities": _int("vulnerabilities"),
        "code_smells": _int("code_smells"),
        "coverage": _float("coverage"),
        "duplications": _float("duplicated_lines_density"),
        "lines": _int("ncloc"),
        "quality_gate": alert_status,
        "raw": raw,
    }


def get_quality_gate_status(
    project_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get quality gate status from the SonarQube API.

    Calls GET /api/qualitygates/project_status and returns the gate result
    along with the individual condition outcomes.

    Args:
        project_key: Project key.  Falls back to SONAR_PROJECT_KEY env var.
        config:      Sonar config dict.  If None, calls get_sonar_config().

    Returns:
        Dict with keys:
            status (str):       "OK", "ERROR", "WARN", or "UNKNOWN".
            conditions (list):  List of condition dicts from the API (may be
                                empty if the API is unavailable).
            passed (bool):      True when status is "OK".
    """
    if config is None:
        config = get_sonar_config()

    key = project_key or config.get("project_key", "")

    default: Dict[str, Any] = {
        "status": "UNKNOWN",
        "conditions": [],
        "passed": False,
    }

    if not key:
        logger.debug("get_quality_gate_status: no project_key available")
        return default

    params: Dict[str, str] = {"projectKey": key}
    if config.get("organization"):
        params["organization"] = config["organization"]

    data = _sonar_api_get(
        "/api/qualitygates/project_status", params=params, config=config
    )
    if data is None:
        return default

    gate_data = data.get("projectStatus", {})
    status = gate_data.get("status", "UNKNOWN")
    if status not in ("OK", "ERROR", "WARN"):
        status = "UNKNOWN"

    return {
        "status": status,
        "conditions": gate_data.get("conditions", []),
        "passed": status == "OK",
    }


def create_sonar_project(
    project_key: str,
    project_name: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a SonarQube project via the API (first-time local setup).

    Calls POST /api/projects/create.  Most users will not need this because:
      - SonarCloud auto-creates projects from GitHub repositories.
      - Local SonarQube creates the project automatically on the first scan.

    This function is provided for programmatic first-time setup of local
    SonarQube instances where the project must exist before the first scan.

    Args:
        project_key:  Unique project key (e.g. "my-org_my-repo").
        project_name: Human-readable project name.
        config:       Sonar config dict.  If None, calls get_sonar_config().

    Returns:
        Dict with keys:
            created (bool):  True if the project was successfully created.
            key (str):       Project key (same as input on success).
            name (str):      Project name (same as input on success).
            error (str):     Error message if created is False.
    """
    if config is None:
        config = get_sonar_config()

    post_data: Dict[str, str] = {
        "project": project_key,
        "name": project_name,
    }
    if config.get("organization"):
        post_data["organization"] = config["organization"]

    data = _sonar_api_post("/api/projects/create", data=post_data, config=config)
    if data is None:
        return {
            "created": False,
            "key": project_key,
            "name": project_name,
            "error": "API call failed or server unreachable",
        }

    # API returns {"project": {"key": ..., "name": ..., ...}} on success
    project_data = data.get("project", {})
    if project_data:
        return {
            "created": True,
            "key": project_data.get("key", project_key),
            "name": project_data.get("name", project_name),
            "error": "",
        }

    # If the response has an "errors" field the project already exists or
    # there was a validation problem
    errors = data.get("errors", [])
    error_msg = "; ".join(e.get("msg", "") for e in errors) if errors else "Unknown error"
    return {
        "created": False,
        "key": project_key,
        "name": project_name,
        "error": error_msg,
    }


# ---------------------------------------------------------------------------
# Public API - scan execution
# ---------------------------------------------------------------------------

def run_sonar_scan(
    project_root: str,
    modified_files: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run sonar-scanner and return parsed findings.

    Execution strategy:
      1. Try the sonar-scanner CLI (existing behaviour) if installed.
      2. ALWAYS fetch results via the SonarQube REST API after the CLI scan,
         regardless of the CLI outcome.  This gives richer data than
         report-task.txt alone.
      3. If the CLI is not installed but the API is reachable, fetch existing
         results from the last scan (triggered externally or by CI/CD).

    If neither the CLI nor the API is available the function returns with
    ``scan_success=False`` and does **not** raise.

    Args:
        project_root:    Absolute path to the project root directory.
        modified_files:  Optional list of relative file paths to restrict
                         the scan scope.
        config:          Sonar config dict.  If None, calls get_sonar_config().

    Returns:
        Dict with keys:
            scan_success (bool):        True if results were obtained.
            findings (list):            List of finding dicts.
            summary (dict):             Aggregated counts + quality gate.
            scan_duration_ms (int):     Wall-clock time in milliseconds.
            error (str | None):         Error message if scan_success is False.
            api_used (bool):            True if results came from the REST API.
            cli_ran (bool):             True if sonar-scanner CLI was executed.
    """
    if config is None:
        config = get_sonar_config()

    empty_result: Dict[str, Any] = {
        "scan_success": False,
        "findings": [],
        "summary": {
            "bugs": 0,
            "vulnerabilities": 0,
            "code_smells": 0,
            "coverage_pct": None,
            "quality_gate": "UNKNOWN",
        },
        "scan_duration_ms": 0,
        "error": None,
        "api_used": False,
        "cli_ran": False,
    }

    install_info = detect_sonar_installation()
    root_path = Path(project_root)

    if not root_path.exists():
        result = dict(empty_result)
        result["error"] = f"project_root does not exist: {project_root}"
        return result

    scan_start = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1: Run sonar-scanner CLI if available
    # ------------------------------------------------------------------
    cli_ran = False
    cli_error: Optional[str] = None

    if install_info["installed"]:
        cmd: List[str] = [
            "sonar-scanner",
            f"-Dsonar.projectBaseDir={root_path}",
        ]
        if modified_files:
            inclusions = ",".join(modified_files)
            cmd.append(f"-Dsonar.inclusions={inclusions}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(root_path),
                timeout=300,
            )
            cli_ran = True
            if proc.returncode != 0:
                cli_error = f"sonar-scanner exited with code {proc.returncode}"
                logger.warning("sonar-scanner non-zero exit: %s", proc.stderr[:500])
        except subprocess.TimeoutExpired:
            cli_ran = True
            cli_error = "sonar-scanner timed out after 300 seconds"
            logger.warning("SonarQube scan timed out for %s", project_root)
        except Exception as exc:
            cli_ran = False
            cli_error = str(exc)
            logger.warning("SonarQube scan failed to start: %s", exc)

    # ------------------------------------------------------------------
    # Step 2: Resolve project key for API calls
    # ------------------------------------------------------------------
    # Priority: env var > sonar-project.properties > report-task.txt
    api_config = dict(config)
    project_key = api_config.get("project_key", "")

    if not project_key:
        # Try sonar-project.properties
        props_path = root_path / "sonar-project.properties"
        if props_path.exists():
            try:
                for raw_line in props_path.read_text(encoding="utf-8").splitlines():
                    if raw_line.startswith("sonar.projectKey"):
                        _, _, project_key = raw_line.partition("=")
                        project_key = project_key.strip()
                        break
            except Exception as exc:
                logger.debug("Could not read sonar-project.properties: %s", exc)

    if not project_key and cli_ran:
        # Fall back to report-task.txt written by the CLI
        report_task_path = root_path / ".scannerwork" / "report-task.txt"
        report_info = _parse_report_task(report_task_path)
        project_key = report_info.get("projectKey", "")
        # Also pick up server URL from report if not configured
        if not api_config.get("host_url") or api_config["host_url"] == _DEFAULT_SONAR_URL:
            server_from_report = report_info.get("serverUrl", "")
            if server_from_report:
                api_config["host_url"] = server_from_report

    if project_key:
        api_config["project_key"] = project_key

    # ------------------------------------------------------------------
    # Step 3: Fetch results via REST API
    # ------------------------------------------------------------------
    api_used = False
    findings: List[Dict[str, Any]] = []
    measures: Dict[str, Any] = {}
    gate_status: Dict[str, Any] = {}

    if install_info["api_available"] and project_key:
        findings = get_project_issues(project_key=project_key, config=api_config)
        measures = get_project_measures(project_key=project_key, config=api_config)
        gate_status = get_quality_gate_status(project_key=project_key, config=api_config)
        api_used = True
        logger.debug(
            "Fetched %d issues via SonarQube API for project %s",
            len(findings),
            project_key,
        )
    elif cli_ran and not install_info["api_available"]:
        # CLI ran but API is not reachable; parse report-task.txt for minimal
        # quality gate info and leave findings empty
        report_task_path = root_path / ".scannerwork" / "report-task.txt"
        report_info = _parse_report_task(report_task_path)
        raw_gate = report_info.get("qualityGateStatus", "UNKNOWN")
        gate_status = {
            "status": raw_gate if raw_gate in ("OK", "WARN", "ERROR") else "UNKNOWN",
            "conditions": [],
            "passed": raw_gate == "OK",
        }

    elapsed_ms = int((time.monotonic() - scan_start) * 1000)

    # ------------------------------------------------------------------
    # Step 4: Build result dict
    # ------------------------------------------------------------------
    # Determine scan success
    if api_used:
        scan_success = True
        error = None
    elif cli_ran and cli_error is None:
        scan_success = True
        error = None
    elif cli_ran and cli_error:
        scan_success = False
        error = cli_error
    elif not install_info["installed"] and not install_info["api_available"]:
        result = dict(empty_result)
        result["scan_duration_ms"] = elapsed_ms
        result["error"] = "sonar-scanner not installed and API not reachable"
        return result
    else:
        scan_success = False
        error = cli_error or "Unknown scan failure"

    # Build summary from API measures (preferred) or findings list
    if measures:
        quality_gate_str = measures.get("quality_gate", "UNKNOWN")
        summary: Dict[str, Any] = {
            "bugs": measures.get("bugs", 0),
            "vulnerabilities": measures.get("vulnerabilities", 0),
            "code_smells": measures.get("code_smells", 0),
            "coverage_pct": measures.get("coverage") if measures.get("coverage", -1.0) >= 0 else None,
            "quality_gate": "PASSED" if quality_gate_str == "OK" else (
                "FAILED" if quality_gate_str == "ERROR" else "UNKNOWN"
            ),
        }
    else:
        bugs = sum(1 for f in findings if f.get("type") == "BUG")
        vulnerabilities = sum(1 for f in findings if f.get("type") == "VULNERABILITY")
        code_smells = sum(1 for f in findings if f.get("type") == "CODE_SMELL")
        gate_str = gate_status.get("status", "UNKNOWN")
        summary = {
            "bugs": bugs,
            "vulnerabilities": vulnerabilities,
            "code_smells": code_smells,
            "coverage_pct": None,
            "quality_gate": "PASSED" if gate_str == "OK" else (
                "FAILED" if gate_str == "ERROR" else "UNKNOWN"
            ),
        }

    return {
        "scan_success": scan_success,
        "findings": findings,
        "summary": summary,
        "scan_duration_ms": elapsed_ms,
        "error": error,
        "api_used": api_used,
        "cli_ran": cli_ran,
    }


# ---------------------------------------------------------------------------
# Public API - GitHub issue creation
# ---------------------------------------------------------------------------

def create_issues_for_findings(
    project_root: str,
    findings: List[Dict[str, Any]],
    max_issues: int = 5,
) -> Dict[str, Any]:
    """Create GitHub issues for Critical/Major SonarQube findings.

    Reuses the existing Level 3 GitHub infrastructure in this order:
      1. MCP github_create_issue tool (same as Step 8 in the pipeline).
      2. Level3GitHubWorkflow from level3_steps8to12_github.py.
      3. gh CLI as final fallback.

    At most *max_issues* GitHub issues are created per call to avoid spam.
    Only CRITICAL, BLOCKER, and MAJOR severity findings are promoted to issues.

    Args:
        project_root:  Path to the project root (used as cwd for gh CLI).
        findings:      List of finding dicts to consider.
        max_issues:    Hard cap on the number of issues created (default 5).

    Returns:
        Dict with keys:
            issues_created (int):   Number of GitHub issues created.
            issue_ids (list):       GitHub issue numbers as ints.
            skipped (int):          Findings not promoted to a GitHub issue.
            method_used (str):      "mcp", "workflow", "gh_cli", or "none".
    """
    result: Dict[str, Any] = {
        "issues_created": 0,
        "issue_ids": [],
        "skipped": 0,
        "method_used": "none",
    }

    # Filter to actionable severity levels
    actionable = [
        f for f in findings
        if f.get("severity", "").upper() in ("CRITICAL", "BLOCKER", "MAJOR")
    ]
    result["skipped"] = len(findings) - len(actionable)

    if not actionable:
        logger.debug("No critical/major findings; no GitHub issues will be created")
        return result

    to_create = actionable[:max_issues]
    result["skipped"] += len(actionable) - len(to_create)

    # ------------------------------------------------------------------
    # Build issue payload for each finding
    # ------------------------------------------------------------------
    def _build_issue_payload(finding: Dict[str, Any]) -> Dict[str, str]:
        severity = finding.get("severity", "UNKNOWN")
        finding_type = finding.get("type", "UNKNOWN")
        file_path = finding.get("file", "unknown")
        line_no = finding.get("line", 0)
        rule = finding.get("rule", "")
        message = finding.get("message", "No message")
        title = f"[SonarQube] {severity} {finding_type}: {message[:80]}"
        body = (
            f"## SonarQube Finding\n\n"
            f"**Severity:** {severity}\n"
            f"**Type:** {finding_type}\n"
            f"**Rule:** {rule}\n"
            f"**File:** `{file_path}` (line {line_no})\n\n"
            f"### Message\n\n{message}\n\n"
            f"*Auto-detected by the Claude Workflow Engine SonarQube scanner.*"
        )
        return {"title": title, "body": body}

    # ------------------------------------------------------------------
    # Method 1: MCP github_create_issue tool
    # ------------------------------------------------------------------
    mcp_available = False
    try:
        from .github_mcp import create_issue_via_mcp  # type: ignore[import]
        mcp_available = True
    except ImportError:
        pass

    if mcp_available:
        created = 0
        for finding in to_create:
            payload = _build_issue_payload(finding)
            try:
                issue_result = create_issue_via_mcp(  # type: ignore[possibly-undefined]
                    title=payload["title"],
                    body=payload["body"],
                    labels=["sonarqube", "auto-detected"],
                )
                issue_number = issue_result.get("number")
                if issue_number:
                    result["issue_ids"].append(int(issue_number))
                created += 1
            except Exception as exc:
                logger.debug("MCP issue creation failed: %s", exc)
                result["skipped"] += 1
        result["issues_created"] = created
        if created > 0:
            result["method_used"] = "mcp"
            return result

    # ------------------------------------------------------------------
    # Method 2: Level3GitHubWorkflow
    # ------------------------------------------------------------------
    workflow_available = False
    try:
        from .level3_steps8to12_github import Level3GitHubWorkflow  # type: ignore[import]
        workflow_available = True
    except ImportError:
        pass

    if workflow_available:
        created = 0
        try:
            workflow = Level3GitHubWorkflow()  # type: ignore[possibly-undefined]
            for finding in to_create:
                payload = _build_issue_payload(finding)
                try:
                    issue_result = workflow.create_issue(
                        title=payload["title"],
                        body=payload["body"],
                        labels=["sonarqube", "auto-detected"],
                    )
                    issue_number = issue_result.get("number")
                    if issue_number:
                        result["issue_ids"].append(int(issue_number))
                    created += 1
                except Exception as exc:
                    logger.debug("Level3GitHubWorkflow issue creation failed: %s", exc)
                    result["skipped"] += 1
        except Exception as exc:
            logger.debug("Could not instantiate Level3GitHubWorkflow: %s", exc)
            workflow_available = False

        result["issues_created"] = created
        if created > 0:
            result["method_used"] = "workflow"
            return result

    # ------------------------------------------------------------------
    # Method 3: gh CLI fallback
    # ------------------------------------------------------------------
    try:
        check = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        gh_available = check.returncode == 0
    except Exception:
        gh_available = False

    if not gh_available:
        logger.debug(
            "gh CLI not available; skipping GitHub issue creation for %d findings",
            len(to_create),
        )
        result["skipped"] += len(to_create)
        return result

    created = 0
    for finding in to_create:
        payload = _build_issue_payload(finding)
        try:
            proc = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--title", payload["title"],
                    "--body", payload["body"],
                    "--label", "sonarqube",
                    "--label", "auto-detected",
                ],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=30,
            )
            if proc.returncode == 0:
                url = proc.stdout.strip()
                try:
                    issue_number = int(url.rstrip("/").rsplit("/", 1)[-1])
                    result["issue_ids"].append(issue_number)
                except ValueError:
                    pass
                created += 1
                logger.debug(
                    "Created GitHub issue for %s:%d",
                    finding.get("file", ""),
                    finding.get("line", 0),
                )
            else:
                logger.debug(
                    "gh issue create failed (rc=%d): %s",
                    proc.returncode,
                    proc.stderr[:200],
                )
                result["skipped"] += 1
        except Exception as exc:
            logger.debug("gh CLI issue creation error: %s", exc)
            result["skipped"] += 1

    result["issues_created"] = created
    if created > 0:
        result["method_used"] = "gh_cli"
    return result


# ---------------------------------------------------------------------------
# Public API - finding categorization and fix prompt generation
# ---------------------------------------------------------------------------

def categorize_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Categorize findings by severity and type for pipeline consumption.

    Args:
        findings: List of finding dicts as returned by run_sonar_scan or
                  get_project_issues.

    Returns:
        Dict with keys:
            critical (list):      Findings with severity CRITICAL or BLOCKER.
            major (list):         Findings with severity MAJOR.
            minor (list):         Findings with severity MINOR or INFO.
            by_type (dict):       Findings grouped by type key.
            auto_fixable (list):  Findings Claude can likely fix automatically.
            needs_review (list):  Findings requiring human judgment.
    """
    critical: List[Dict[str, Any]] = []
    major: List[Dict[str, Any]] = []
    minor: List[Dict[str, Any]] = []

    by_type: Dict[str, List[Dict[str, Any]]] = {
        "BUG": [],
        "VULNERABILITY": [],
        "CODE_SMELL": [],
    }

    auto_fixable: List[Dict[str, Any]] = []
    needs_review: List[Dict[str, Any]] = []

    # Rule patterns that are typically auto-fixable by an LLM
    _AUTO_FIXABLE_RULES = {
        # Python
        "python:S1481",   # unused local variable
        "python:S1854",   # useless assignment
        "python:S1192",   # string literals duplicated
        "python:S2095",   # resource not closed
        "python:S1172",   # unused method parameter
        "python:S125",    # commented-out code
        # General / multi-language
        "common-java:InlineComments",
        "Web:BoldAndItalicTagsCheck",
    }

    for finding in findings:
        severity = finding.get("severity", "").upper()
        finding_type = finding.get("type", "UNKNOWN")
        rule = finding.get("rule", "")

        # Severity buckets
        if severity in ("CRITICAL", "BLOCKER"):
            critical.append(finding)
        elif severity == "MAJOR":
            major.append(finding)
        else:
            minor.append(finding)

        # Type grouping
        if finding_type in by_type:
            by_type[finding_type].append(finding)
        else:
            by_type.setdefault(finding_type, []).append(finding)

        # Auto-fixable vs needs-review
        is_vulnerability = finding_type == "VULNERABILITY"
        is_complex_bug = (
            finding_type == "BUG"
            and severity in ("CRITICAL", "BLOCKER", "MAJOR")
            and rule not in _AUTO_FIXABLE_RULES
        )

        if is_vulnerability or is_complex_bug:
            needs_review.append(finding)
        elif finding_type == "CODE_SMELL" or rule in _AUTO_FIXABLE_RULES:
            auto_fixable.append(finding)
        else:
            # Simple bugs (null checks, unused vars) -> auto_fixable
            message = finding.get("message", "").lower()
            simple_patterns = (
                "null",
                "unused",
                "import",
                "empty catch",
                "todo",
                "deprecated",
            )
            if any(pat in message for pat in simple_patterns):
                auto_fixable.append(finding)
            else:
                needs_review.append(finding)

    return {
        "critical": critical,
        "major": major,
        "minor": minor,
        "by_type": by_type,
        "auto_fixable": auto_fixable,
        "needs_review": needs_review,
    }


def generate_fix_prompt(finding: Dict[str, Any]) -> str:
    """Generate a fix prompt for a single SonarQube finding.

    Reads up to 10 lines of source context around the finding's line number
    and produces a focused prompt instructing Claude (or another LLM) how to
    fix the issue.

    Args:
        finding: A single finding dict from run_sonar_scan, get_project_issues,
                 or run_basic_scan.

    Returns:
        A prompt string ready to be sent to an LLM.
    """
    file_path = finding.get("file", "")
    line_no = finding.get("line", 0)
    rule = finding.get("rule", "")
    message = finding.get("message", "")
    severity = finding.get("severity", "UNKNOWN")
    finding_type = finding.get("type", "UNKNOWN")

    code_context = _read_lines_around(file_path, line_no, context=10)

    # Build a rule-specific suggested approach
    rule_lower = rule.lower()
    if "null" in rule_lower or "none" in message.lower():
        approach = (
            "Add a None/null check before dereferencing the value, "
            "or use the Optional/Maybe pattern to express nullability explicitly."
        )
    elif "unused" in rule_lower or "unused" in message.lower():
        approach = (
            "Remove the unused variable, parameter, or import. "
            "If the value is intentionally unused (e.g. loop variable), "
            "rename it to `_` or use `_unused` as a convention."
        )
    elif "except" in message.lower() or "exception" in rule_lower:
        approach = (
            "Narrow the exception type being caught. "
            "Replace bare `except:` with `except SpecificException as exc:` "
            "and handle or re-raise it explicitly."
        )
    elif "eval" in message.lower() or "exec" in message.lower():
        approach = (
            "Replace eval()/exec() with a safe alternative: "
            "ast.literal_eval() for data parsing, "
            "importlib for dynamic imports, "
            "or a strategy pattern for dynamic dispatch."
        )
    elif "password" in message.lower() or "credential" in message.lower():
        approach = (
            "Move the credential to an environment variable or a secrets manager. "
            "Read it with os.getenv() and never commit it to source control."
        )
    elif "todo" in message.lower() or "fixme" in message.lower():
        approach = (
            "Implement the TODO/FIXME or convert it to a tracked GitHub issue "
            "and remove the comment from the code."
        )
    elif "complexity" in message.lower():
        approach = (
            "Reduce cyclomatic complexity by extracting helper functions, "
            "using early returns to eliminate nesting, "
            "or replacing long if/elif chains with a dispatch table."
        )
    elif finding_type == "VULNERABILITY":
        approach = (
            "This is a security vulnerability. "
            "Consult the OWASP guidelines for the relevant rule. "
            "Do not suppress without a documented justification."
        )
    else:
        approach = (
            "Review the rule documentation and apply the recommended fix. "
            "Ensure the fix does not change observable behaviour."
        )

    prompt_parts = [
        f"Fix the following SonarQube {severity} {finding_type} finding.",
        "",
        f"File:     {file_path}",
        f"Line:     {line_no}",
        f"Rule:     {rule}",
        f"Severity: {severity}",
        f"Message:  {message}",
        "",
    ]

    if code_context:
        prompt_parts += [
            "Code context (line marked with >>>):",
            "```",
            code_context,
            "```",
            "",
        ]

    prompt_parts += [
        "Suggested approach:",
        approach,
        "",
        "Instructions:",
        "1. Apply the minimal change needed to resolve the finding.",
        "2. Do not alter logic or formatting outside the affected area.",
        "3. Add or update a unit test if the change affects testable behaviour.",
        "4. Output only the corrected file content.",
    ]

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Lightweight fallback scanner (no SonarQube required)
# ---------------------------------------------------------------------------

def run_basic_scan(
    project_root: str,
    modified_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Lightweight code scan without SonarQube using AST and regex.

    Checks for a fixed set of patterns that are commonly problematic:
      - Bare ``except:`` clauses
      - ``eval()`` / ``exec()`` usage
      - Hardcoded passwords / tokens (regex heuristic)
      - TODO / FIXME / HACK comments
      - Unused imports (basic AST walk)
      - Functions longer than 50 lines
      - Cyclomatic complexity > 10 (rough AST estimate)

    Only Python (``.py``) files are analysed.

    Args:
        project_root:   Absolute path to the project root directory.
        modified_files: Optional list of relative paths to restrict the scan.
                        When omitted all ``.py`` files under *project_root*
                        are scanned.

    Returns:
        Dict with the same schema as run_sonar_scan:
            scan_success, findings, summary, scan_duration_ms, error,
            api_used, cli_ran.
    """
    start = time.monotonic()
    root_path = Path(project_root)

    if not root_path.exists():
        return {
            "scan_success": False,
            "findings": [],
            "summary": {
                "bugs": 0,
                "vulnerabilities": 0,
                "code_smells": 0,
                "coverage_pct": None,
                "quality_gate": "UNKNOWN",
            },
            "scan_duration_ms": 0,
            "error": f"project_root does not exist: {project_root}",
            "api_used": False,
            "cli_ran": False,
        }

    # Resolve target files
    if modified_files:
        target_files = [
            root_path / f for f in modified_files
            if f.endswith(".py") and (root_path / f).exists()
        ]
    else:
        target_files = list(root_path.rglob("*.py"))

    # Exclude virtual envs and common non-project dirs
    _SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build"}
    target_files = [
        p for p in target_files
        if not any(part in _SKIP_DIRS for part in p.parts)
    ]

    findings: List[Dict[str, Any]] = []

    # Regex patterns (compiled once)
    _RE_BARE_EXCEPT = re.compile(r"^\s*except\s*:")
    _RE_EVAL_EXEC = re.compile(r"\beval\s*\(|\bexec\s*\(")
    _RE_CREDENTIALS = re.compile(
        r"(?i)(password|passwd|secret|api_key|apikey|token|auth)\s*=\s*[\"'][^\"']{4,}[\"']"
    )
    _RE_TODO = re.compile(r"#\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)

    for file_path in target_files:
        rel_path = str(file_path.relative_to(root_path))

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug("Could not read %s: %s", file_path, exc)
            continue

        lines = source.splitlines()

        # --- Line-by-line regex checks ---
        for lineno, raw_line in enumerate(lines, start=1):
            if _RE_BARE_EXCEPT.match(raw_line):
                findings.append({
                    "file": rel_path,
                    "line": lineno,
                    "severity": "MAJOR",
                    "type": "BUG",
                    "rule": "python:bare-except",
                    "message": "Bare 'except:' clause catches all exceptions including SystemExit",
                })

            if _RE_EVAL_EXEC.search(raw_line):
                findings.append({
                    "file": rel_path,
                    "line": lineno,
                    "severity": "CRITICAL",
                    "type": "VULNERABILITY",
                    "rule": "python:eval-exec",
                    "message": "Use of eval()/exec() is a security risk",
                })

            if _RE_CREDENTIALS.search(raw_line):
                findings.append({
                    "file": rel_path,
                    "line": lineno,
                    "severity": "BLOCKER",
                    "type": "VULNERABILITY",
                    "rule": "python:hardcoded-credentials",
                    "message": "Potential hardcoded credential or secret detected",
                })

            if _RE_TODO.search(raw_line):
                findings.append({
                    "file": rel_path,
                    "line": lineno,
                    "severity": "INFO",
                    "type": "CODE_SMELL",
                    "rule": "python:todo-comment",
                    "message": f"TODO/FIXME/HACK comment: {raw_line.strip()[:100]}",
                })

        # --- AST-based checks ---
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            logger.debug("Syntax error in %s; skipping AST checks", file_path)
            continue

        # Unused imports (simple: names imported but not referenced in the file)
        import_names: Dict[str, int] = {}  # name -> lineno
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound_name = alias.asname if alias.asname else alias.name.split(".")[0]
                    import_names[bound_name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound_name = alias.asname if alias.asname else alias.name
                    if bound_name != "*":
                        import_names[bound_name] = node.lineno

        # Count name usages in the source (cheap proxy)
        for name, imp_lineno in import_names.items():
            other_lines = [
                line for idx, line in enumerate(lines, 1) if idx != imp_lineno
            ]
            usage_count = sum(
                1 for line in other_lines
                if re.search(r"\b" + re.escape(name) + r"\b", line)
            )
            if usage_count == 0:
                findings.append({
                    "file": rel_path,
                    "line": imp_lineno,
                    "severity": "MINOR",
                    "type": "CODE_SMELL",
                    "rule": "python:unused-import",
                    "message": f"Unused import: '{name}'",
                })

        # Function length and cyclomatic complexity
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_start = node.lineno
                func_end = getattr(node, "end_lineno", func_start)
                func_len = func_end - func_start + 1

                if func_len > 50:
                    findings.append({
                        "file": rel_path,
                        "line": func_start,
                        "severity": "MAJOR",
                        "type": "CODE_SMELL",
                        "rule": "python:function-too-long",
                        "message": (
                            f"Function '{node.name}' is {func_len} lines long "
                            f"(threshold: 50)"
                        ),
                    })

                # Rough cyclomatic complexity: count branching nodes
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(
                        child,
                        (
                            ast.If,
                            ast.For,
                            ast.While,
                            ast.ExceptHandler,
                            ast.With,
                            ast.Assert,
                            ast.comprehension,
                        ),
                    ):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1

                if complexity > 10:
                    findings.append({
                        "file": rel_path,
                        "line": func_start,
                        "severity": "MAJOR",
                        "type": "CODE_SMELL",
                        "rule": "python:cognitive-complexity",
                        "message": (
                            f"Function '{node.name}' has estimated cyclomatic "
                            f"complexity of {complexity} (threshold: 10)"
                        ),
                    })

    elapsed_ms = int((time.monotonic() - start) * 1000)

    bugs = sum(1 for f in findings if f["type"] == "BUG")
    vulnerabilities = sum(1 for f in findings if f["type"] == "VULNERABILITY")
    code_smells = sum(1 for f in findings if f["type"] == "CODE_SMELL")
    quality_gate = "PASSED" if (bugs == 0 and vulnerabilities == 0) else "FAILED"

    return {
        "scan_success": True,
        "findings": findings,
        "summary": {
            "bugs": bugs,
            "vulnerabilities": vulnerabilities,
            "code_smells": code_smells,
            "coverage_pct": None,
            "quality_gate": quality_gate,
        },
        "scan_duration_ms": elapsed_ms,
        "error": None,
        "api_used": False,
        "cli_ran": False,
    }


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def scan_and_report(
    project_root: str,
    modified_files: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full scan pipeline: detect -> scan -> categorize -> report.

    Execution strategy:
      1. Get config from env vars + defaults.
      2. Check API availability.
      3. If API available: fetch issues + measures via REST API (preferred).
      4. If API not available but CLI installed: run CLI scan.
      5. If neither: run run_basic_scan() fallback.
      6. Categorize all findings and return combined report.

    Args:
        project_root:   Absolute path to the project root directory.
        modified_files: Optional list of relative file paths to restrict scope.
        config:         Sonar config dict.  If None, calls get_sonar_config().

    Returns:
        Combined dict containing all keys from run_sonar_scan plus:
            sonar_installed (bool):   Whether sonar-scanner CLI was found.
            api_available (bool):     Whether the SonarQube API responded.
            scanner_used (str):       "sonarqube_api", "sonarqube_cli", or "basic".
            categories (dict):        Output of categorize_findings().
            measures (dict):          Output of get_project_measures() if available.
            quality_gate (dict):      Output of get_quality_gate_status() if available.
    """
    if config is None:
        config = get_sonar_config()

    install_info = detect_sonar_installation()
    sonar_installed = install_info["installed"]
    api_available = install_info["api_available"]

    project_key = config.get("project_key", "")
    # Try sonar-project.properties if env not set
    if not project_key:
        props_path = Path(project_root) / "sonar-project.properties"
        if props_path.exists():
            try:
                for raw_line in props_path.read_text(encoding="utf-8").splitlines():
                    if raw_line.startswith("sonar.projectKey"):
                        _, _, project_key = raw_line.partition("=")
                        project_key = project_key.strip()
                        break
            except Exception as exc:
                logger.debug("Could not read sonar-project.properties: %s", exc)
        if project_key:
            config = dict(config)
            config["project_key"] = project_key

    measures: Dict[str, Any] = {}
    quality_gate: Dict[str, Any] = {}
    scanner_used = "basic"

    if api_available and project_key:
        # API-first: fetch everything from the REST API
        scan_result = run_sonar_scan(project_root, modified_files, config=config)
        measures = get_project_measures(project_key=project_key, config=config)
        quality_gate = get_quality_gate_status(project_key=project_key, config=config)
        scanner_used = "sonarqube_api"
    elif sonar_installed:
        # CLI fallback: trigger a new scan, results from report-task.txt + API
        logger.debug(
            "SonarQube API not available; using CLI for %s", project_root
        )
        scan_result = run_sonar_scan(project_root, modified_files, config=config)
        scanner_used = "sonarqube_cli"
    else:
        # Basic fallback: no SonarQube at all
        logger.debug(
            "SonarQube not available; using lightweight basic scanner for %s",
            project_root,
        )
        scan_result = run_basic_scan(project_root, modified_files)
        scanner_used = "basic"

    findings = scan_result.get("findings", [])
    categories = categorize_findings(findings)

    return {
        **scan_result,
        "sonar_installed": sonar_installed,
        "api_available": api_available,
        "scanner_used": scanner_used,
        "categories": categories,
        "measures": measures,
        "quality_gate": quality_gate,
    }
