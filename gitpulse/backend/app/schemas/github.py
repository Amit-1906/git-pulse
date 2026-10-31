from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class GitHubConnectRequest(BaseModel):
    token: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token (PAT). If omitted, uses GITHUB_ACCESS_TOKEN from environment.",
    )


class GitHubUserInfo(BaseModel):
    login: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    type: str = "User"


class RateLimitDetail(BaseModel):
    limit: int = 60
    remaining: int = 60
    reset_epoch: Optional[int] = None
    used: int = 0


class GitHubStatusResponse(BaseModel):
    authenticated: bool
    token_configured: bool
    token_masked: Optional[str] = None
    user: Optional[GitHubUserInfo] = None
    scopes: List[str] = []
    rate_limit: Optional[RateLimitDetail] = None


class RateLimitResource(BaseModel):
    limit: int
    used: int
    remaining: int
    reset: int


class GitHubRateLimitFullResponse(BaseModel):
    resources: Dict[str, RateLimitResource]
    rate: RateLimitResource


class GitHubRepoItem(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: Optional[str] = None
    description: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    language: Optional[str] = None
    default_branch: str = "main"
    updated_at: Optional[str] = None

