import pytest
from datetime import datetime, timezone
import httpx
from unittest.mock import MagicMock

from app.extractors.client import GitHubClient, parse_link_header
from app.extractors.repository_extractor import RepositoryExtractor
from app.extractors.commits_extractor import CommitsExtractor
from app.extractors.issues_extractor import IssuesExtractor
from app.extractors.pull_requests_extractor import PullRequestsExtractor
from app.core.exceptions import GitHubAPIException, GitHubRateLimitExceededException


def test_parse_link_header():
    header = (
        '<https://api.github.com/repositories/1/commits?page=2>; rel="next", '
        '<https://api.github.com/repositories/1/commits?page=5>; rel="last", '
        '<https://api.github.com/repositories/1/commits?page=1>; rel="first"'
    )
    links = parse_link_header(header)
    assert links["next"] == "https://api.github.com/repositories/1/commits?page=2"
    assert links["last"] == "https://api.github.com/repositories/1/commits?page=5"
    assert links["first"] == "https://api.github.com/repositories/1/commits?page=1"

    assert parse_link_header(None) == {}
    assert parse_link_header("") == {}


def test_pagination_multipage():
    mock_client = MagicMock(spec=httpx.Client)

    # Page 1 response with 'next' Link header
    resp1 = MagicMock(spec=httpx.Response)
    resp1.status_code = 200
    resp1.json.return_value = [{"sha": "sha_page_1"}]
    resp1.headers = {
        "link": '<https://api.github.com/repos/test/repo/commits?page=2>; rel="next"'
    }

    # Page 2 response with no 'next' header
    resp2 = MagicMock(spec=httpx.Response)
    resp2.status_code = 200
    resp2.json.return_value = [{"sha": "sha_page_2"}]
    resp2.headers = {}

    mock_client.request.side_effect = [resp1, resp2]

    gh_client = GitHubClient(http_client=mock_client)
    pages = list(gh_client.paginate("repos/test/repo/commits"))

    assert len(pages) == 2
    assert pages[0][0]["sha"] == "sha_page_1"
    assert pages[1][0]["sha"] == "sha_page_2"


def test_client_exponential_backoff_retry_on_500():
    mock_client = MagicMock(spec=httpx.Client)

    # First attempt: 500 error, second attempt: 200 success
    err_resp = MagicMock(spec=httpx.Response)
    err_resp.status_code = 500
    err_resp.text = "Internal Server Error"
    err_resp.headers = {}

    ok_resp = MagicMock(spec=httpx.Response)
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"status": "ok"}
    ok_resp.headers = {}

    mock_client.request.side_effect = [err_resp, ok_resp]

    gh_client = GitHubClient(http_client=mock_client, max_retries=2)
    data, headers = gh_client.request("GET", "test/endpoint")
    assert data["status"] == "ok"
    assert mock_client.request.call_count == 2


def test_client_network_timeout_retry_failure():
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")

    gh_client = GitHubClient(http_client=mock_client, max_retries=2)
    with pytest.raises(GitHubAPIException) as exc_info:
        gh_client.request("GET", "test/endpoint")

    assert exc_info.value.status_code == 504
    assert "timeout" in exc_info.value.message.lower()


def test_client_rate_limit_403_handling():
    mock_client = MagicMock(spec=httpx.Client)
    err_resp = MagicMock(spec=httpx.Response)
    err_resp.status_code = 403
    err_resp.text = "API rate limit exceeded for IP"
    err_resp.headers = {"X-RateLimit-Reset": "1700000999", "Retry-After": "60"}

    mock_client.request.return_value = err_resp

    gh_client = GitHubClient(http_client=mock_client, max_retries=1)
    with pytest.raises(GitHubRateLimitExceededException) as exc_info:
        gh_client.request("GET", "test/endpoint")

    assert exc_info.value.status_code == 429
    assert exc_info.value.details["rate_limit_reset"] == 1700000999


def test_repository_extractor():
    mock_client = MagicMock(spec=httpx.Client)
    repo_resp = MagicMock(spec=httpx.Response)
    repo_resp.status_code = 200
    repo_resp.json.return_value = {
        "id": 12345,
        "name": "fastapi",
        "full_name": "tiangolo/fastapi",
        "description": "FastAPI framework",
        "owner": {"login": "tiangolo"},
        "visibility": "public",
        "language": "Python",
        "stargazers_count": 75000,
        "forks_count": 6000,
        "open_issues_count": 150,
        "created_at": "2018-12-08T08:00:00Z",
        "updated_at": "2026-10-31T12:00:00Z",
        "default_branch": "master",
    }
    repo_resp.headers = {}
    mock_client.request.return_value = repo_resp

    extractor = RepositoryExtractor(GitHubClient(http_client=mock_client))
    meta = extractor.extract_metadata("tiangolo", "fastapi")

    assert meta["github_id"] == 12345
    assert meta["name"] == "fastapi"
    assert meta["full_name"] == "tiangolo/fastapi"
    assert meta["owner"] == "tiangolo"
    assert meta["visibility"] == "public"
    assert meta["language"] == "Python"
    assert meta["stargazers_count"] == 75000
    assert meta["forks_count"] == 6000
    assert meta["created_at_gh"] is not None
    assert meta["updated_at_gh"] is not None


def test_commits_extractor_with_parent_shas():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = [
        {
            "sha": "c1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
            "commit": {
                "author": {"name": "Alice", "email": "alice@example.com", "date": "2026-10-30T10:00:00Z"},
                "committer": {"name": "Bob", "email": "bob@example.com", "date": "2026-10-30T10:05:00Z"},
                "message": "feat: add parent commit tracking",
            },
            "parents": [
                {"sha": "p111111111111111111111111111111111111111"},
                {"sha": "p222222222222222222222222222222222222222"},
            ],
            "stats": {"additions": 25, "deletions": 5, "total": 30},
        }
    ]
    resp.headers = {}
    mock_client.request.return_value = resp

    extractor = CommitsExtractor(GitHubClient(http_client=mock_client))
    commits = extractor.extract("owner", "repo", since=datetime(2026, 10, 1))

    assert len(commits) == 1
    c = commits[0]
    assert c["sha"] == "c1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
    assert c["author_name"] == "Alice"
    assert c["committer_name"] == "Bob"
    assert c["message"] == "feat: add parent commit tracking"
    assert len(c["parent_shas"]) == 2
    assert "p111111111111111111111111111111111111111" in c["parent_shas"]
    assert c["additions"] == 25
    assert c["deletions"] == 5


def test_issues_extractor_excludes_pull_requests():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = [
        # Pure issue
        {
            "id": 901,
            "number": 15,
            "title": "Bug in query param parsing",
            "body": "Details about bug",
            "state": "open",
            "user": {"login": "reporter_dev"},
            "assignees": [{"login": "assignee_1"}],
            "labels": [{"name": "bug"}, {"name": "high-priority"}],
            "comments": 3,
            "created_at": "2026-10-25T12:00:00Z",
            "updated_at": "2026-10-26T14:00:00Z",
            "closed_at": None,
        },
        # Pull Request returned by GitHub issues endpoint
        {
            "id": 902,
            "number": 16,
            "title": "Fix query param parsing",
            "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/16"},
            "user": {"login": "pr_author"},
        },
    ]
    resp.headers = {}
    mock_client.request.return_value = resp

    extractor = IssuesExtractor(GitHubClient(http_client=mock_client))
    issues = extractor.extract("owner", "repo")

    # The PR item (id 902) must be excluded!
    assert len(issues) == 1
    iss = issues[0]
    assert iss["github_id"] == 901
    assert iss["number"] == 15
    assert iss["title"] == "Bug in query param parsing"
    assert iss["user_login"] == "reporter_dev"
    assert iss["assignees"] == ["assignee_1"]
    assert iss["labels"] == ["bug", "high-priority"]


def test_pull_requests_extractor_with_branches_and_merge():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = [
        {
            "id": 771,
            "number": 42,
            "title": "Support Python 3.12 syntax",
            "body": "PR description",
            "state": "closed",
            "merged_at": "2026-10-28T16:00:00Z",
            "closed_at": "2026-10-28T16:00:00Z",
            "created_at": "2026-10-27T10:00:00Z",
            "updated_at": "2026-10-28T16:00:00Z",
            "user": {"login": "core_dev"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/py312"},
            "comments": 7,
            "additions": 150,
            "deletions": 20,
            "changed_files": 4,
        }
    ]
    resp.headers = {}
    mock_client.request.return_value = resp

    extractor = PullRequestsExtractor(GitHubClient(http_client=mock_client))
    prs = extractor.extract("owner", "repo")

    assert len(prs) == 1
    pr = prs[0]
    assert pr["github_id"] == 771
    assert pr["number"] == 42
    assert pr["base_branch"] == "main"
    assert pr["head_branch"] == "feature/py312"
    assert pr["is_merged"] is True
    assert pr["user_login"] == "core_dev"
    assert pr["additions"] == 150
    assert pr["deletions"] == 20


def test_empty_repository_handling():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = []
    resp.headers = {}
    mock_client.request.return_value = resp

    extractor = CommitsExtractor(GitHubClient(http_client=mock_client))
    commits = extractor.extract("owner", "empty-repo")
    assert commits == []

