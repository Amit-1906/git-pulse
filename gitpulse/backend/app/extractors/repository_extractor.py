import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.extractors.base import BaseResourceExtractor, parse_gh_datetime

logger = logging.getLogger("gitpulse.extractor.repository")


class RepositoryExtractor(BaseResourceExtractor):
    """
    Extracts high-level repository metadata from GitHub REST API:
    - Repository ID, Name, Full Name, Description, Owner, Visibility, Primary Language,
      Stars, Forks, Open Issues Count, Created Timestamp, Updated Timestamp, Default Branch.
    """

    def extract_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        endpoint = f"repos/{owner}/{repo}"
        raw_data, _ = self.client.request("GET", endpoint)

        created_at_gh = parse_gh_datetime(raw_data.get("created_at"))
        updated_at_gh = parse_gh_datetime(raw_data.get("updated_at"))

        owner_login = raw_data.get("owner", {}).get("login") if isinstance(raw_data.get("owner"), dict) else owner

        return {
            "github_id": raw_data.get("id"),
            "name": raw_data.get("name"),
            "full_name": raw_data.get("full_name") or f"{owner}/{repo}",
            "description": raw_data.get("description"),
            "owner": owner_login,
            "visibility": raw_data.get("visibility", "public"),
            "html_url": raw_data.get("html_url"),
            "language": raw_data.get("language"),
            "stargazers_count": raw_data.get("stargazers_count", 0),
            "forks_count": raw_data.get("forks_count", 0),
            "open_issues_count": raw_data.get("open_issues_count", 0),
            "watchers_count": raw_data.get("watchers_count", 0),
            "default_branch": raw_data.get("default_branch", "main"),
            "created_at_gh": created_at_gh,
            "updated_at_gh": updated_at_gh,
            "raw_payload": raw_data,
        }

    def extract(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.extract_metadata(owner, repo)

