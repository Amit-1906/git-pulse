import pytest
import httpx
from unittest.mock import MagicMock
from app.core.auth import mask_token, GitHubAuthManager, GitHubAuthException
from app.core.exceptions import GitHubRateLimitExceededException
from app.api.v1.endpoints.github import connect_github, get_github_status
from app.schemas.github import GitHubConnectRequest


def test_token_masking():
    # Long personal access token
    pat = "ghp_1234567890abcdef1234567890abcdef123456"
    masked = mask_token(pat)
    assert masked == "ghp_1234...3456"
    assert pat not in masked

    # None and empty
    assert mask_token(None) is None
    assert mask_token("") is None
    assert mask_token("short") == "********"


def test_validate_token_success():
    auth_mgr = GitHubAuthManager()

    mock_client = MagicMock(spec=httpx.Client)

    # Response for /user
    user_resp = MagicMock(spec=httpx.Response)
    user_resp.status_code = 200
    user_resp.json.return_value = {
        "login": "octocat",
        "name": "The Octocat",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "type": "User",
    }
    user_resp.headers = {"X-OAuth-Scopes": "repo, read:user"}

    # Response for /rate_limit
    rate_resp = MagicMock(spec=httpx.Response)
    rate_resp.status_code = 200
    rate_resp.json.return_value = {
        "resources": {
            "core": {"limit": 5000, "remaining": 4990, "reset": 1700000000, "used": 10}
        }
    }

    mock_client.get.side_effect = [user_resp, rate_resp]

    result = auth_mgr.validate_token("ghp_valid_mock_token_123456789", client=mock_client)
    assert result["valid"] is True
    assert result["authenticated"] is True
    assert result["user"]["login"] == "octocat"
    assert "repo" in result["scopes"]
    assert result["rate_limit"]["limit"] == 5000
    assert result["rate_limit"]["remaining"] == 4990

    # Ensure token is masked and raw token is not exposed
    assert "ghp_valid_mock_token_123456789" not in str(result)
    assert result["token_masked"] == "ghp_vali...6789"


def test_validate_token_invalid_credentials_401():
    auth_mgr = GitHubAuthManager()
    mock_client = MagicMock(spec=httpx.Client)

    err_resp = MagicMock(spec=httpx.Response)
    err_resp.status_code = 401
    err_resp.text = "Bad credentials"
    mock_client.get.return_value = err_resp

    with pytest.raises(GitHubAuthException) as exc_info:
        auth_mgr.validate_token("ghp_invalid_token_123456789", client=mock_client)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired" in exc_info.value.message


def test_validate_token_rate_limit_exceeded():
    auth_mgr = GitHubAuthManager()
    mock_client = MagicMock(spec=httpx.Client)

    err_resp = MagicMock(spec=httpx.Response)
    err_resp.status_code = 403
    err_resp.text = "API rate limit exceeded for user"
    err_resp.headers = {"X-RateLimit-Reset": "1700000500"}
    mock_client.get.return_value = err_resp

    with pytest.raises(GitHubRateLimitExceededException) as exc_info:
        auth_mgr.validate_token("ghp_token_rate_limited", client=mock_client)

    assert exc_info.value.status_code == 429
    assert exc_info.value.details["rate_limit_reset"] == 1700000500


def test_connect_endpoint_masks_token(monkeypatch):
    mock_client = MagicMock(spec=httpx.Client)
    user_resp = MagicMock(spec=httpx.Response)
    user_resp.status_code = 200
    user_resp.json.return_value = {"login": "testuser", "name": "Test User"}
    user_resp.headers = {"X-OAuth-Scopes": "repo"}

    rate_resp = MagicMock(spec=httpx.Response)
    rate_resp.status_code = 200
    rate_resp.json.return_value = {
        "resources": {"core": {"limit": 5000, "remaining": 5000, "reset": 1700000000, "used": 0}}
    }
    mock_client.get.side_effect = [user_resp, rate_resp]

    # Monkeypatch validate_token to use mock_client
    from app.core.auth import github_auth_manager
    orig_validate = github_auth_manager.validate_token
    monkeypatch.setattr(
        github_auth_manager,
        "validate_token",
        lambda token=None, client=None: orig_validate(token=token, client=mock_client),
    )

    req = GitHubConnectRequest(token="ghp_my_secret_token_12345678")
    resp = connect_github(req)

    assert resp.authenticated is True
    assert resp.user.login == "testuser"
    assert "ghp_my_secret_token_12345678" not in resp.model_dump_json()
    assert resp.token_masked == "ghp_my_s...5678"

