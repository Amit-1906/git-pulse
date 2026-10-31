import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.extractors.base import BaseResourceExtractor, parse_gh_datetime

logger = logging.getLogger("gitpulse.extractor.pull_requests")


class PullRequestsExtractor(BaseResourceExtractor):
    """
    Extracts pull requests for a repository with base/head branch tracking and merge state.
    Endpoint: GET /repos/{owner}/{repo}/pulls
    
    CRITICAL GITHUB API LIMITATION & STRATEGY:
    -------------------------------------------
    GitHub REST API v3 does NOT support a 'since' filter on the /pulls endpoint.
    To achieve efficient incremental extraction without downloading all historical PRs:
    1. We request PRs sorted by 'updated' in descending order ('direction=desc').
    2. During pagination, we compare each PR's 'updated_at' against the 'since' checkpoint.
    3. As soon as all PRs on a page are older than 'since', we terminate pagination early.
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
        endpoint = f"repos/{owner}/{repo}/pulls"
        params: Dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": min(per_page, 100),
        }

        extracted_prs: List[Dict[str, Any]] = []

        logger.info(
            "Extracting pull requests for %s/%s (incremental since=%s, until=%s)",
            owner,
            repo,
            since,
            until,
        )

        should_terminate_early = False

        for page in self.client.paginate(endpoint, params=params, max_pages=max_pages):
            if should_terminate_early:
                break

            page_older_than_since_count = 0

            for item in page:
                pr_id = item.get("id")
                if not pr_id:
                    continue

                created_at_gh = parse_gh_datetime(item.get("created_at"))
                updated_at_gh = parse_gh_datetime(item.get("updated_at"))
                closed_at_gh = parse_gh_datetime(item.get("closed_at"))
                merged_at_gh = parse_gh_datetime(item.get("merged_at"))

                # Incremental boundary check
                if since and updated_at_gh:
                    # If naive vs aware comparison, normalize
                    cmp_updated = updated_at_gh.replace(tzinfo=None) if updated_at_gh.tzinfo else updated_at_gh
                    cmp_since = since.replace(tzinfo=None) if since.tzinfo else since
                    if cmp_updated < cmp_since:
                        page_older_than_since_count += 1
                        continue

                # Filter by until if specified
                if until and created_at_gh:
                    cmp_created = created_at_gh.replace(tzinfo=None) if created_at_gh.tzinfo else created_at_gh
                    cmp_until = until.replace(tzinfo=None) if until.tzinfo else until
                    if cmp_created > cmp_until:
                        continue

                author_login = (item.get("user") or {}).get("login")
                base_branch = (item.get("base") or {}).get("ref")
                head_branch = (item.get("head") or {}).get("ref")
                is_merged = bool(merged_at_gh or item.get("merged") or False)

                record = {
                    "github_id": pr_id,
                    "number": item.get("number", 0),
                    "title": item.get("title", "")[:500],
                    "body": item.get("body"),
                    "state": item.get("state", "open"),
                    "user_login": author_login,
                    "base_branch": base_branch,
                    "head_branch": head_branch,
                    "is_merged": is_merged,
                    "comments_count": item.get("comments", 0),
                    "additions": item.get("additions", 0),
                    "deletions": item.get("deletions", 0),
                    "changed_files": item.get("changed_files", 0),
                    "created_at_gh": created_at_gh,
                    "updated_at_gh": updated_at_gh,
                    "closed_at_gh": closed_at_gh,
                    "merged_at_gh": merged_at_gh,
                    "raw_payload": item,
                }
                extracted_prs.append(record)

            # If all items on this sorted-desc page were older than 'since', terminate early
            if since and page_older_than_since_count == len(page):
                logger.info(
                    "All %d PRs on page are older than since checkpoint (%s). Terminating PR pagination early.",
                    len(page),
                    since,
                )
                should_terminate_early = True

        logger.info("Extracted %d pull requests for %s/%s", len(extracted_prs), owner, repo)
        return extracted_prs

