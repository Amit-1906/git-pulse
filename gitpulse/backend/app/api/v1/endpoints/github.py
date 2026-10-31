from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.core.auth import github_auth_manager
from app.extractors.client import GitHubClient
from app.schemas.github import (
    GitHubConnectRequest,
    GitHubStatusResponse,
    GitHubRepoItem,
)

router = APIRouter(prefix="/github", tags=["GitHub Integration"])


@router.post("/connect", response_model=GitHubStatusResponse, summary="Connect and validate GitHub Personal Access Token")
def connect_github(request: GitHubConnectRequest):
    """
    Validates the provided Personal Access Token (or environment token if omitted)
    against GitHub /user and /rate_limit endpoints.
    Never exposes raw tokens in response.
    """
    if request.token:
        github_auth_manager.set_token(request.token)

    val_info = github_auth_manager.validate_token()
    return GitHubStatusResponse(
        authenticated=val_info["authenticated"],
        token_configured=True,
        token_masked=val_info["token_masked"],
        user=val_info["user"],
        scopes=val_info["scopes"],
        rate_limit=val_info["rate_limit"],
    )


@router.get("/status", response_model=GitHubStatusResponse, summary="Get current GitHub authentication and quota status")
def get_github_status():
    """
    Returns current authentication status, active user login, available OAuth scopes,
    and remaining rate-limit quota. Token is always masked.
    """
    status_info = github_auth_manager.get_status()
    return GitHubStatusResponse(
        authenticated=status_info.get("authenticated", False),
        token_configured=status_info.get("token_configured", False),
        token_masked=status_info.get("token_masked"),
        user=status_info.get("user"),
        scopes=status_info.get("scopes", []),
        rate_limit=status_info.get("rate_limit"),
    )


@router.get("/rate-limit", summary="Get detailed GitHub rate-limit metrics across resource categories")
def get_rate_limit():
    """
    Returns exact GitHub API rate limit breakdown for core, search, and graphql quotas.
    """
    client = GitHubClient()
    data, _ = client.request("GET", "rate_limit")
    return data


@router.get("/repositories", response_model=List[GitHubRepoItem], summary="List accessible repositories from GitHub")
def list_github_repositories(
    visibility: str = Query("all", description="all, public, or private"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    """
    Lists repositories accessible to the authenticated token (via /user/repos).
    If unauthenticated, queries top trending/starred public repositories.
    """
    client = GitHubClient()
    token = client.token

    if token:
        endpoint = "user/repos"
        params = {"visibility": visibility, "sort": "updated", "per_page": per_page, "page": page}
        data, _ = client.request("GET", endpoint, params=params)
    else:
        # Unauthenticated fallback: search popular repositories
        endpoint = "search/repositories"
        params = {"q": "stars:>1000", "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
        res, _ = client.request("GET", endpoint, params=params)
        data = res.get("items", [])

    results: List[GitHubRepoItem] = []
    for r in data:
        results.append(
            GitHubRepoItem(
                id=r.get("id"),
                name=r.get("name"),
                full_name=r.get("full_name"),
                private=r.get("private", False),
                html_url=r.get("html_url"),
                description=r.get("description"),
                stargazers_count=r.get("stargazers_count", 0),
                forks_count=r.get("forks_count", 0),
                open_issues_count=r.get("open_issues_count", 0),
                language=r.get("language"),
                default_branch=r.get("default_branch", "main"),
                updated_at=r.get("updated_at"),
            )
        )
    return results

