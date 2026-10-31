import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.extractors.base import BaseResourceExtractor, parse_gh_datetime

logger = logging.getLogger("gitpulse.extractor.issues")


class IssuesExtractor(BaseResourceExtractor):
    """
    Extracts issues for a repository while explicitly excluding pull requests.
    Endpoint: GET /repos/{owner}/{repo}/issues
    Supported filters: 'state=all', 'since=ISO 8601', 'sort=updated', 'direction=asc'.
    """

    def extract(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        endpoint = f"repos/{owner}/{repo}/issues"
        params: Dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "asc",
            "per_page": min(per_page, 100),
        }

        if since:
            params["since"] = since.isoformat()

        extracted_issues: List[Dict[str, Any]] = []

        logger.info("Extracting issues for %s/%s (since=%s)", owner, repo, since)

        for page in self.client.paginate(endpoint, params=params, max_pages=max_pages):
            for item in page:
                # Crucial GitHub API detail: GitHub includes Pull Requests in issues endpoint!
                # If 'pull_request' key is present in issue dict, this is a PR, not an issue.
                if "pull_request" in item:
                    continue

                issue_id = item.get("id")
                if not issue_id:
                    continue

                created_at_gh = parse_gh_datetime(item.get("created_at"))
                updated_at_gh = parse_gh_datetime(item.get("updated_at"))
                closed_at_gh = parse_gh_datetime(item.get("closed_at"))

                # Filter by until if specified
                if until and created_at_gh and created_at_gh > until:
                    continue

                author_login = (item.get("user") or {}).get("login")

                # Extract assignees list
                raw_assignees = item.get("assignees") or []
                assignees = [
                    a.get("login") for a in raw_assignees if isinstance(a, dict) and a.get("login")
                ]
                if not assignees and item.get("assignee"):
                    assignees = [item["assignee"]["login"]]

                # Extract labels list
                raw_labels = item.get("labels") or []
                labels = [
                    l.get("name") if isinstance(l, dict) else str(l)
                    for l in raw_labels
                ]

                record = {
                    "github_id": issue_id,
                    "number": item.get("number", 0),
                    "title": item.get("title", "")[:500],
                    "body": item.get("body"),
                    "state": item.get("state", "open"),
                    "user_login": author_login,
                    "assignees": assignees,
                    "labels": labels,
                    "comments_count": item.get("comments", 0),
                    "created_at_gh": created_at_gh,
                    "updated_at_gh": updated_at_gh,
                    "closed_at_gh": closed_at_gh,
                    "raw_payload": item,
                }
                extracted_issues.append(record)

        logger.info("Extracted %d pure issues for %s/%s", len(extracted_issues), owner, repo)
        return extracted_issues

