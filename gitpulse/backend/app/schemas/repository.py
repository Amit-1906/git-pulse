from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RepositoryBase(BaseModel):
    owner: str = Field(..., min_length=1, max_length=100, description="GitHub owner or organization")
    name: str = Field(..., min_length=1, max_length=100, description="GitHub repository name")
    description: Optional[str] = None
    default_branch: str = "main"
    language: Optional[str] = None


class RepositoryCreate(BaseModel):
    full_name: str = Field(
        ...,
        examples=["tiangolo/fastapi", "streamlit/streamlit"],
        description="Full repository name in 'owner/name' format",
    )
    fetch_initial_metadata: bool = Field(
        default=True,
        description="Whether to immediately query GitHub REST API for repository info upon registration",
    )


class RepositoryUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None
    default_branch: Optional[str] = None


class RepositoryRead(RepositoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: Optional[int] = None
    full_name: str
    html_url: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    watchers_count: int = 0
    is_active: bool = True
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    repo_metadata: Optional[Dict[str, Any]] = None

