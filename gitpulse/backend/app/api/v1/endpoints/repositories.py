from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import APIResponse
from app.schemas.repository import RepositoryCreate, RepositoryRead
from app.services.repository_service import repository_service

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=List[RepositoryRead], summary="List all active repositories")
def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return repository_service.list_repositories(db, skip=skip, limit=limit)


@router.post("", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED, summary="Track a new repository")
def create_repository(
    repo_in: RepositoryCreate,
    db: Session = Depends(get_db),
):
    return repository_service.register_repository(db, repo_in)


@router.get("/{repository_id}", response_model=RepositoryRead, summary="Get repository by ID")
def get_repository(
    repository_id: int,
    db: Session = Depends(get_db),
):
    return repository_service.get_repository(db, repository_id)


@router.delete("/{repository_id}", response_model=RepositoryRead, summary="Soft delete a repository")
def delete_repository(
    repository_id: int,
    db: Session = Depends(get_db),
):
    return repository_service.delete_repository(db, repository_id)


@router.post("/{repository_id}/refresh", response_model=RepositoryRead, summary="Refresh metadata from GitHub")
def refresh_repository_metadata(
    repository_id: int,
    db: Session = Depends(get_db),
):
    return repository_service.refresh_metadata(db, repository_id)

