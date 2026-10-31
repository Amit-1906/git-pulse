import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.extractors.base import BaseResourceExtractor, parse_gh_datetime

logger = logging.getLogger("gitpulse.extractor.commits")


class CommitsExtractor(BaseResourceExtractor):
    """
    Extracts git commits for a repository with incremental 'since' filtering and parent SHA tracking.
    Endpoint: GET /repos/{owner}/{repo}/commits
    Supported incremental filters: 'since' (ISO 8601), 'until' (ISO 8601).
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
        endpoint = f"repos/{owner}/{repo}/commits"
        params: Dict[str, Any] = {"per_page": min(per_page, 100)}

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        extracted_commits: List[Dict[str, Any]] = []

        logger.info(
            "Extracting commits for %s/%s (since=%s, until=%s)",
            owner,
            repo,
            since,
            until,
        )

        for page in self.client.paginate(endpoint, params=params, max_pages=max_pages):
            for item in page:
                sha = item.get("sha")
                if not sha:
                    continue

                commit_detail = item.get("commit", {})
                author_dict = commit_detail.get("author") or {}
                committer_dict = commit_detail.get("committer") or {}

                author_date = parse_gh_datetime(author_dict.get("date"))
                committer_date = parse_gh_datetime(committer_dict.get("date"))

                # Parent commit references
                raw_parents = item.get("parents") or []
                parent_shas = [p.get("sha") for p in raw_parents if isinstance(p, dict) and p.get("sha")]

                # Stats (if provided on commit detail)
                stats = item.get("stats") or {}
                additions = stats.get("additions", 0)
                deletions = stats.get("deletions", 0)
                total_changes = stats.get("total", additions + deletions)

                record = {
                    "sha": sha,
                    "author_name": author_dict.get("name"),
                    "author_email": author_dict.get("email"),
                    "author_date": author_date,
                    "committer_name": committer_dict.get("name"),
                    "committer_date": committer_date,
                    "message": commit_detail.get("message"),
                    "parent_shas": parent_shas,
                    "additions": additions,
                    "deletions": deletions,
                    "total_changes": total_changes,
                    "raw_payload": item,
                }
                extracted_commits.append(record)

        logger.info("Extracted %d commits for %s/%s", len(extracted_commits), owner, repo)
        return extracted_commits

