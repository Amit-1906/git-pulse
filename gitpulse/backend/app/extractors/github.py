import logging
import time
from typing import Dict, Any, List, Optional
import httpx

from app.config import get_settings
from app.core.exceptions import (
    GitHubAPIException,
    GitHubRateLimitExceededException,
    EntityNotFoundException,
)

logger = logging.getLogger("gitpulse.extractor.github")


class GitHubExtractor:
    """
    Authentic client for the GitHub REST API v3.
    Extracts repositories, commits, pull requests, and issues with rate-limit tracking and retries.
    """

    def __init__(self, token: Optional[str] = None):
        self.settings = get_settings()
        self.token = token or self.settings.GITHUB_ACCESS_TOKEN
        self.base_url = self.settings.GITHUB_API_BASE_URL.rstrip("/")
        self.timeout = self.settings.GITHUB_API_TIMEOUT

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"GitPulse-ELT/{self.settings.VERSION}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 3
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        backoff = 1.0
        for attempt in range(1, retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(method, url, headers=headers, params=params)

                # Check rate limit headers
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_time = response.headers.get("X-RateLimit-Reset")
                if remaining is not None and int(remaining) <= 0:
                    reset_epoch = int(reset_time) if reset_time else None
                    logger.warning("GitHub API rate limit exhausted. Resets at %s", reset_epoch)
                    raise GitHubRateLimitExceededException(reset_timestamp=reset_epoch)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    raise EntityNotFoundException("GitHub resource", endpoint)
                elif response.status_code in (403, 429) and "rate limit" in response.text.lower():
                    reset_epoch = int(reset_time) if reset_time else None
                    raise GitHubRateLimitExceededException(reset_timestamp=reset_epoch)
                elif response.status_code >= 500:
                    logger.warning(
                        "GitHub server error %s (attempt %d/%d). Retrying in %.1fs...",
                        response.status_code,
                        attempt,
                        retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    raise GitHubAPIException(
                        message=f"Request to {endpoint} returned {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(
                    "Network error querying %s (attempt %d/%d): %s. Retrying in %.1fs...",
                    endpoint,
                    attempt,
                    retries,
                    exc,
                    backoff,
                )
                if attempt == retries:
                    raise GitHubAPIException(
                        message=f"Failed to connect to GitHub API after {retries} attempts: {exc}",
                        status_code=504,
                    )
                time.sleep(backoff)
                backoff *= 2

        raise GitHubAPIException(message=f"Max retries exceeded for {endpoint}")

    def get_rate_limit(self) -> Dict[str, Any]:
        """Fetches current API quota limits and remaining calls."""
        return self._request("GET", "rate_limit")

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches repository metadata."""
        return self._request("GET", f"repos/{owner}/{repo}")

    def list_commits(
        self, owner: str, repo: str, per_page: int = 30, page: int = 1
    ) -> List[Dict[str, Any]]:
        """Lists recent commits for a repository."""
        return self._request(
            "GET",
            f"repos/{owner}/{repo}/commits",
            params={"per_page": min(per_page, 100), "page": page},
        )

    def list_pull_requests(
        self, owner: str, repo: str, state: str = "all", per_page: int = 30, page: int = 1
    ) -> List[Dict[str, Any]]:
        """Lists pull requests for a repository."""
        return self._request(
            "GET",
            f"repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": min(per_page, 100), "page": page},
        )

    def list_issues(
        self, owner: str, repo: str, state: str = "all", per_page: int = 30, page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Lists issues for a repository (GitHub API returns PRs in issues endpoint;
        we filter out items containing a 'pull_request' key).
        """
        raw_items = self._request(
            "GET",
            f"repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": min(per_page, 100), "page": page},
        )
        # Exclude pull requests which GitHub includes in issues endpoint
        return [item for item in raw_items if "pull_request" not in item]

