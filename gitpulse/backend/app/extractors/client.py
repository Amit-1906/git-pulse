import logging
import re
import time
from typing import Dict, Any, List, Optional, Iterator, Tuple
import httpx

from app.config import get_settings
from app.core.auth import github_auth_manager, mask_token
from app.core.exceptions import (
    GitHubAPIException,
    GitHubRateLimitExceededException,
    EntityNotFoundException,
)

logger = logging.getLogger("gitpulse.extractor.client")


def parse_link_header(link_header: Optional[str]) -> Dict[str, str]:
    """
    Parses RFC 5988 Link headers from GitHub API responses.
    Example:
    '<https://api.github.com/repos/owner/name/commits?page=2>; rel="next", <...page=5>; rel="last"'
    Returns dict: {'next': 'https://api.github.com/repos/owner/name/commits?page=2', ...}
    """
    links: Dict[str, str] = {}
    if not link_header:
        return links

    pattern = r'<([^>]+)>;\s*rel="([^"]+)"'
    for match in re.finditer(pattern, link_header):
        url, rel = match.groups()
        links[rel] = url
    return links


class GitHubClient:
    """
    Resilient HTTP Client for GitHub REST API v3 with automatic RFC 5988 Link header pagination,
    exponential backoff retries with jitter, Retry-After handling, and rate-limit tracking.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        http_client: Optional[httpx.Client] = None,
    ):
        settings = get_settings()
        self.token = token or github_auth_manager.get_token()
        self.base_url = settings.GITHUB_API_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.GITHUB_API_TIMEOUT
        self.max_retries = max_retries
        self._external_client = http_client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitPulse-ELT/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _parse_retry_after(self, retry_after_header: Optional[str]) -> float:
        """Parses Retry-After header which can be an integer in seconds."""
        if not retry_after_header:
            return 1.0
        try:
            return max(float(retry_after_header), 1.0)
        except ValueError:
            return 2.0

    def request(
        self,
        method: str,
        endpoint_or_url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, httpx.Headers]:
        """
        Executes an HTTP request with exponential backoff and rate-limit handling.
        Returns a tuple of (parsed_json_body, response_headers).
        """
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            url = endpoint_or_url
        else:
            url = f"{self.base_url}/{endpoint_or_url.lstrip('/')}"

        headers = self._get_headers()
        masked_tok = mask_token(self.token) or "unauthenticated"
        delay = 1.0

        for attempt in range(1, self.max_retries + 1):
            client = self._external_client or httpx.Client(timeout=self.timeout)
            try:
                logger.debug(
                    "GitHub API %s %s [Token: %s, Attempt %d/%d]",
                    method,
                    url,
                    masked_tok,
                    attempt,
                    self.max_retries,
                )
                resp = client.request(method, url, headers=headers, params=params)

                # Track rate limit headers
                remaining = resp.headers.get("X-RateLimit-Remaining")
                reset_time = resp.headers.get("X-RateLimit-Reset")

                if remaining is not None and int(remaining) <= 0:
                    reset_epoch = int(reset_time) if reset_time else None
                    logger.warning("GitHub API rate limit exhausted. Resets at %s", reset_epoch)
                    raise GitHubRateLimitExceededException(reset_timestamp=reset_epoch)

                if resp.status_code == 200:
                    return resp.json(), resp.headers
                elif resp.status_code == 404:
                    raise EntityNotFoundException("GitHub Resource", url)
                elif resp.status_code in (403, 429):
                    if "rate limit" in resp.text.lower() or "secondary rate limit" in resp.text.lower():
                        retry_after = self._parse_retry_after(resp.headers.get("Retry-After"))
                        reset_epoch = int(reset_time) if reset_time else None
                        logger.warning(
                            "Rate limited by GitHub. Retry-After: %.1fs, Reset: %s",
                            retry_after,
                            reset_epoch,
                        )
                        if attempt < self.max_retries and retry_after <= 10.0:
                            time.sleep(retry_after)
                            continue
                        raise GitHubRateLimitExceededException(reset_timestamp=reset_epoch)
                    raise GitHubAPIException(
                        message=f"Access forbidden (403): {resp.text}",
                        status_code=403,
                    )
                elif resp.status_code >= 500:
                    logger.warning(
                        "GitHub server error %d at %s. Retrying in %.1fs...",
                        resp.status_code,
                        url,
                        delay,
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    raise GitHubAPIException(
                        message=f"GitHub API responded with {resp.status_code}: {resp.text}",
                        status_code=resp.status_code,
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(
                    "Network error during %s %s (attempt %d/%d): %s. Retrying in %.1fs...",
                    method,
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                if attempt == self.max_retries:
                    raise GitHubAPIException(
                        message=f"Network timeout / connectivity failure after {self.max_retries} attempts: {exc}",
                        status_code=504,
                    )
                time.sleep(delay)
                delay *= 2
            finally:
                if self._external_client is None:
                    client.close()

        raise GitHubAPIException(message=f"Max retries exceeded for {url}")

    def paginate(
        self,
        endpoint_or_url: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Paginates through GitHub API endpoints following RFC 5988 'Link' headers.
        Yields each page of results as a list of dictionaries.
        """
        next_url: Optional[str] = endpoint_or_url
        current_params = params.copy() if params else {}
        page_num = 0

        while next_url:
            page_num += 1
            if max_pages and page_num > max_pages:
                logger.debug("Reached max pages limit (%d). Terminating pagination.", max_pages)
                break

            data, headers = self.request("GET", next_url, params=current_params)
            
            # If data is a dict (e.g. rate limit or single resource), yield as single item list
            if isinstance(data, dict):
                yield [data]
                break

            if not isinstance(data, list):
                logger.warning("Unexpected non-list response in paginator: %s", type(data))
                break

            if not data:
                # Empty page returned, stop paginating
                break

            yield data

            # Extract 'next' URL from Link header
            link_header = headers.get("link") or headers.get("Link")
            links = parse_link_header(link_header)
            next_url = links.get("next")
            # Clear params because the next Link URL already includes full query parameters
            current_params = None

