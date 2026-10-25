"""HTTP Client for interacting with Jira Cloud REST API v3."""

import logging
from typing import Any
from urllib.parse import urlparse
import httpx

from backend.config import settings
from backend.integrations.jira.schemas import (
    JiraTestConnectionResponse,
)

logger = logging.getLogger(__name__)


def normalize_jira_base_url(url: str | None) -> str:
    """Normalize base URL so that it is strictly the Jira Cloud domain.
    E.g. 'https://company.atlassian.net/jira/software/...' -> 'https://company.atlassian.net'
    """
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = f"https://{clean}"
    try:
        parsed = urlparse(clean)
        if parsed.netloc:
            scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"
            return f"{scheme}://{parsed.netloc}".rstrip("/")
    except Exception:
        pass
    return clean.rstrip("/")


class JiraClientError(Exception):
    """Base exception for Jira Cloud client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class JiraCloudClient:
    """Client for official Jira Cloud REST API v3 using Basic Authentication."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        timeout: float = 12.0,
    ):
        raw_url = base_url if base_url is not None else settings.jira_base_url
        self.base_url = normalize_jira_base_url(raw_url)
        self.email = (email if email is not None else settings.jira_email).strip()
        self.api_token = (api_token if api_token is not None else settings.jira_api_token).strip()
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Verify whether all required credentials are set and non-empty."""
        return bool(self.base_url and self.email and self.api_token)

    def _get_auth(self) -> tuple[str, str]:
        if not self.is_configured:
            raise JiraClientError("Jira Cloud credentials are not configured. Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN.", 401)
        return (self.email, self.api_token)

    def _get_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _translate_error(self, exc: Exception) -> JiraClientError:
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            detail = ""
            try:
                err_json = exc.response.json()
                if "errorMessages" in err_json and err_json["errorMessages"]:
                    detail = "; ".join(err_json["errorMessages"])
                elif "message" in err_json:
                    detail = err_json["message"]
            except Exception:
                detail = exc.response.text[:200]

            if status == 401:
                return JiraClientError(f"Authentication failed (401): Invalid Jira email or API token. {detail}".strip(), 401)
            elif status == 403:
                return JiraClientError(f"Permission denied (403): User lacks required Jira permissions. {detail}".strip(), 403)
            elif status == 404:
                return JiraClientError(f"Not found (404): Specified Jira resource or project does not exist. {detail}".strip(), 404)
            elif status == 429:
                return JiraClientError("Rate limited (429): Jira Cloud API rate limit exceeded. Please retry later.", 429)
            else:
                return JiraClientError(f"Jira API error HTTP {status}: {detail or exc}", status)
        elif isinstance(exc, httpx.ConnectError):
            return JiraClientError(f"Could not connect to Jira Cloud host '{self.base_url}'. Check your internet connection or URL.", 503)
        elif isinstance(exc, httpx.TimeoutException):
            return JiraClientError(f"Jira Cloud API request timed out after {self.timeout}s.", 504)
        return JiraClientError(f"Jira request error: {str(exc)}")

    def test_connection(self, project_key: str | None = None) -> JiraTestConnectionResponse:
        """Verify Jira credentials against /rest/api/3/myself and validate project access."""
        if not self.is_configured:
            return JiraTestConnectionResponse(
                success=False,
                connected=False,
                provider="jira",
                error_message="Jira credentials are not fully configured. Please set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in .env.",
                base_url=self.base_url,
            )

        auth = self._get_auth()
        headers = self._get_headers()
        proj_key = (project_key or settings.jira_project_key or "KAN").strip().upper()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                # 1. Test myself
                res = client.get(f"{self.base_url}/rest/api/3/myself", auth=auth, headers=headers)
                res.raise_for_status()
                user_data = res.json()
                display_name = user_data.get("displayName", "")
                account_id = user_data.get("accountId", "")
                email = user_data.get("emailAddress", self.email)

                # 2. Test project if specified
                project_found = False
                project_name = ""
                if proj_key:
                    proj_res = client.get(f"{self.base_url}/rest/api/3/project/{proj_key}", auth=auth, headers=headers)
                    if proj_res.status_code == 200:
                        proj_data = proj_res.json()
                        project_found = True
                        project_name = proj_data.get("name", "")
                    else:
                        logger.warning("Jira test myself succeeded, but project '%s' returned HTTP %d", proj_key, proj_res.status_code)

                return JiraTestConnectionResponse(
                    success=True,
                    connected=True,
                    provider="jira",
                    user_display_name=display_name,
                    authenticated_user=display_name or email,
                    account_id=account_id,
                    email=email,
                    project_found=project_found,
                    project_key=proj_key,
                    project_name=project_name,
                    base_url=self.base_url,
                )
        except Exception as exc:
            err = self._translate_error(exc)
            logger.error("Jira connection test failed: %s", err)
            return JiraTestConnectionResponse(
                success=False,
                connected=False,
                provider="jira",
                base_url=self.base_url,
                error_message=str(err),
            )

    def get_project(self, project_key: str) -> dict[str, Any]:
        """Fetch project details from /rest/api/3/project/{project_key}."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/project/{project_key}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def get_all_projects(self) -> list[dict[str, Any]]:
        """Fetch all projects from /rest/api/3/project."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/project"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def search_issues(
        self,
        project_key: str,
        jql: str | None = None,
        start_at: int = 0,
        next_page_token: str | None = None,
        max_results: int = 50,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search issues using modern /rest/api/3/search/jql API with fallback to /rest/api/3/search."""
        auth = self._get_auth()
        headers = self._get_headers()
        query = jql if jql else f"project = '{project_key}' ORDER BY updated DESC"
        field_list = fields or [
            "summary",
            "description",
            "status",
            "priority",
            "assignee",
            "reporter",
            "duedate",
            "issuetype",
            "labels",
            "components",
            "parent",
            "customfield_10016",  # Story points in many Jira Cloud instances
            "created",
            "updated",
        ]

        params: dict[str, Any] = {
            "jql": query,
            "maxResults": max_results,
            "fields": ",".join(field_list),
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        elif start_at:
            params["startAt"] = start_at

        # Try modern /rest/api/3/search/jql first (Atlassian REST v3 replacement)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/rest/api/3/search/jql", params=params, auth=auth, headers=headers)
                if res.status_code == 200:
                    return res.json()
                elif res.status_code not in (404, 410):
                    res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (404, 410):
                raise self._translate_error(exc)
        except Exception as exc:
            logger.debug("search/jql request exception: %s", exc)

        # Fallback to /rest/api/3/search for older Jira versions
        url = f"{self.base_url}/rest/api/3/search"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def fetch_all_issues(
        self,
        project_key: str,
        jql: str | None = None,
        max_total: int = 500,
    ) -> list[dict[str, Any]]:
        """Paginate through search results and return all issues up to max_total using cursor/token or offset."""
        all_issues: list[dict[str, Any]] = []
        next_page_token = None
        start_at = 0
        batch_size = 50

        while len(all_issues) < max_total:
            data = self.search_issues(
                project_key=project_key,
                jql=jql,
                start_at=start_at,
                next_page_token=next_page_token,
                max_results=min(batch_size, max_total - len(all_issues)),
            )
            issues = data.get("issues", [])
            if not issues:
                break

            all_issues.extend(issues)
            next_page_token = data.get("nextPageToken")
            is_last = data.get("isLast")

            if is_last is True:
                break
            if not next_page_token:
                total = data.get("total", len(all_issues))
                start_at += len(issues)
                if start_at >= total:
                    break

        return all_issues

    def get_issue(self, issue_id_or_key: str) -> dict[str, Any]:
        """Fetch a single issue by ID or Key."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id_or_key}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def get_comments(self, issue_id_or_key: str) -> list[dict[str, Any]]:
        """Fetch comments for a given issue."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id_or_key}/comment"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, auth=auth, headers=headers)
                res.raise_for_status()
                data = res.json()
                return data.get("comments", [])
        except Exception as exc:
            raise self._translate_error(exc)

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "High",
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue/defect in Jira Cloud REST API v3."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/issue"

        # Atlassian Document Format for description
        desc_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description or summary}],
                }
            ],
        }

        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "description": desc_adf,
            "issuetype": {"name": issue_type},
        }
        if priority:
            fields["priority"] = {"name": priority}
        if extra_fields:
            fields.update(extra_fields)

        payload = {"fields": fields}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def add_comment(self, issue_id_or_key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue in Jira Cloud REST API v3."""
        auth = self._get_auth()
        headers = self._get_headers()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id_or_key}/comment"

        comment_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": body}],
                }
            ],
        }
        payload = {"body": comment_adf}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, auth=auth, headers=headers)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise self._translate_error(exc)

    def transition_issue(self, issue_id_or_key: str, transition_name_or_id: str) -> dict[str, Any]:
        """Perform a workflow transition on an issue in Jira Cloud REST API v3."""
        auth = self._get_auth()
        headers = self._get_headers()

        # 1. Fetch available transitions
        url_trans = f"{self.base_url}/rest/api/3/issue/{issue_id_or_key}/transitions"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url_trans, auth=auth, headers=headers)
                res.raise_for_status()
                data = res.json()
                transitions = data.get("transitions", [])

            target_id = None
            for t in transitions:
                if t.get("id") == str(transition_name_or_id) or t.get("name", "").lower() == str(transition_name_or_id).lower():
                    target_id = t.get("id")
                    break

            if not target_id and transitions:
                target_id = transitions[0].get("id")

            if not target_id:
                raise JiraClientError(f"No suitable workflow transition found matching '{transition_name_or_id}'", 400)

            # 2. Execute transition
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url_trans, json={"transition": {"id": target_id}}, auth=auth, headers=headers)
                res.raise_for_status()
                return {"status": "transitioned", "transition_id": target_id}
        except Exception as exc:
            raise self._translate_error(exc)

