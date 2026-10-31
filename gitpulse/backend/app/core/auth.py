import logging
from typing import Optional, Dict, Any, List
import httpx

from app.config import get_settings
from app.core.exceptions import GitPulseException, GitHubRateLimitExceededException

logger = logging.getLogger("gitpulse.auth")


class GitHubAuthException(GitPulseException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=f"GitHub Authentication Failed: {message}",
            code="GITHUB_AUTH_FAILED",
            status_code=401,
            details=details,
        )


def mask_token(token: Optional[str]) -> Optional[str]:
    """
    Safely masks a GitHub token for display in logs or API responses.
    Never exposes full credentials.
    Example: 'ghp_1234567890abcdef1234567890abcdef123456' -> 'ghp_1234...3456'
    """
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    if len(token) <= 8:
        return "********"
    prefix = token[:8]
    suffix = token[-4:]
    return f"{prefix}...{suffix}"


class GitHubAuthManager:
    """
    Manages GitHub credentials and authentication lifecycle.
    Pulls from environment by default, with dynamic connection override support.
    """

    def __init__(self):
        self._custom_token: Optional[str] = None
        self._user_cache: Optional[Dict[str, Any]] = None
        self._scopes_cache: List[str] = []

    def get_token(self) -> Optional[str]:
        """Returns the active token (custom override or environment setting)."""
        if self._custom_token:
            return self._custom_token
        settings = get_settings()
        return settings.GITHUB_ACCESS_TOKEN or None

    def set_token(self, token: Optional[str]) -> None:
        """Dynamically updates active token in memory."""
        self._custom_token = token.strip() if token and token.strip() else None
        self._user_cache = None
        self._scopes_cache = []

    def clear_token(self) -> None:
        self._custom_token = None
        self._user_cache = None
        self._scopes_cache = []

    def validate_token(self, token: Optional[str] = None, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
        """
        Validates token against the GitHub REST API /user and /rate_limit endpoints.
        Returns user info, scopes, and quota.
        """
        active_token = token or self.get_token()
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitPulse-ELT/0.1.0",
        }
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"

        should_close = False
        if client is None:
            client = httpx.Client(timeout=10.0)
            should_close = True

        try:
            # 1. Test authentication against /user or /rate_limit
            if active_token:
                resp = client.get("https://api.github.com/user", headers=headers)
                if resp.status_code == 401:
                    logger.warning("Token validation failed with 401 Bad credentials (token: %s)", mask_token(active_token))
                    raise GitHubAuthException("Invalid or expired GitHub Personal Access Token.")
                elif resp.status_code in (403, 429) and "rate limit" in resp.text.lower():
                    reset_time = resp.headers.get("X-RateLimit-Reset")
                    reset_epoch = int(reset_time) if reset_time else None
                    raise GitHubRateLimitExceededException(reset_timestamp=reset_epoch)
                elif resp.status_code != 200:
                    raise GitHubAuthException(f"Validation endpoint returned {resp.status_code}: {resp.text}")

                user_data = resp.json()
                raw_scopes = resp.headers.get("X-OAuth-Scopes", "")
                scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]
            else:
                user_data = {"login": "anonymous", "name": "Unauthenticated Client", "type": "anonymous"}
                scopes = []

            # 2. Query rate limit quota
            rate_resp = client.get("https://api.github.com/rate_limit", headers=headers)
            rate_data = rate_resp.json() if rate_resp.status_code == 200 else {}
            core_rate = rate_data.get("resources", {}).get("core", {})

            validated_info = {
                "valid": True,
                "authenticated": active_token is not None,
                "token_masked": mask_token(active_token),
                "user": {
                    "login": user_data.get("login"),
                    "name": user_data.get("name"),
                    "avatar_url": user_data.get("avatar_url"),
                    "html_url": user_data.get("html_url"),
                    "type": user_data.get("type", "User"),
                },
                "scopes": scopes,
                "rate_limit": {
                    "limit": core_rate.get("limit", 60),
                    "remaining": core_rate.get("remaining", 60),
                    "reset_epoch": core_rate.get("reset"),
                    "used": core_rate.get("used", 0),
                },
            }
            self._user_cache = validated_info["user"]
            self._scopes_cache = scopes
            logger.info(
                "GitHub authentication validated for user '%s' (token: %s, remaining: %s/%s)",
                user_data.get("login"),
                mask_token(active_token),
                core_rate.get("remaining"),
                core_rate.get("limit"),
            )
            return validated_info
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.error("Network timeout during GitHub token validation: %s", exc)
            raise GitPulseException(
                message=f"Network error connecting to GitHub API: {exc}",
                code="GITHUB_NETWORK_ERROR",
                status_code=504,
            )
        finally:
            if should_close:
                client.close()

    def get_status(self, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
        """Returns the current cached or fresh authentication status."""
        active_token = self.get_token()
        if not active_token:
            return {
                "authenticated": False,
                "token_configured": False,
                "token_masked": None,
                "user": None,
                "scopes": [],
                "rate_limit": {"limit": 60, "remaining": 60, "reset_epoch": None, "used": 0},
            }
        try:
            val = self.validate_token(active_token, client=client)
            return {
                "authenticated": True,
                "token_configured": True,
                "token_masked": val["token_masked"],
                "user": val["user"],
                "scopes": val["scopes"],
                "rate_limit": val["rate_limit"],
            }
        except Exception as exc:
            return {
                "authenticated": False,
                "token_configured": True,
                "token_masked": mask_token(active_token),
                "error": str(exc),
                "scopes": [],
                "rate_limit": None,
            }


github_auth_manager = GitHubAuthManager()

