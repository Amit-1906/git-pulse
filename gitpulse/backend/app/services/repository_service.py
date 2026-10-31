import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, GitPulseException
from app.extractors.github import GitHubExtractor
from app.models.repository import Repository
from app.repositories.repository_repo import repository_repo
from app.schemas.repository import RepositoryCreate, RepositoryUpdate
from app.services.base import BaseService

logger = logging.getLogger("gitpulse.services.repository")


class RepositoryService(BaseService):
    """
    Handles registration, discovery, synchronization, and deletion of GitHub repositories.
    """

    def __init__(self, extractor: Optional[GitHubExtractor] = None):
        self.extractor = extractor or GitHubExtractor()

    def parse_full_name(self, full_name: str) -> Tuple[str, str]:
        parts = [p.strip() for p in full_name.strip().split("/") if p.strip()]
        if len(parts) != 2:
            raise GitPulseException(
                message=f"Invalid repository full name format '{full_name}'. Expected 'owner/repo'.",
                code="INVALID_REPOSITORY_NAME",
                status_code=400,
            )
        return parts[0], parts[1]

    def register_repository(self, db: Session, repo_in: RepositoryCreate) -> Repository:
        owner, name = self.parse_full_name(repo_in.full_name)
        full_name = f"{owner}/{name}".lower()

        existing = repository_repo.get_by_full_name(db, full_name)
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
            return existing

        gh_meta = {}
        if repo_in.fetch_initial_metadata:
            try:
                gh_meta = self.extractor.get_repository(owner, name)
            except Exception as exc:
                logger.warning(
                    "Could not fetch initial GitHub metadata for %s: %s. Creating record with defaults.",
                    full_name,
                    exc,
                )

        repo = Repository(
            github_id=gh_meta.get("id"),
            owner=owner,
            name=name,
            full_name=full_name,
            description=gh_meta.get("description"),
            html_url=gh_meta.get("html_url") or f"https://github.com/{owner}/{name}",
            default_branch=gh_meta.get("default_branch", "main"),
            stargazers_count=gh_meta.get("stargazers_count", 0),
            forks_count=gh_meta.get("forks_count", 0),
            open_issues_count=gh_meta.get("open_issues_count", 0),
            watchers_count=gh_meta.get("watchers_count", 0),
            language=gh_meta.get("language"),
            is_active=True,
            repo_metadata=gh_meta,
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        logger.info("Successfully registered repository: %s (id=%s)", full_name, repo.id)
        return repo

    def list_repositories(self, db: Session, skip: int = 0, limit: int = 100) -> List[Repository]:
        return repository_repo.get_active(db, skip=skip, limit=limit)

    def get_repository(self, db: Session, repository_id: int) -> Repository:
        repo = repository_repo.get(db, repository_id)
        if not repo:
            raise EntityNotFoundException("Repository", repository_id)
        return repo

    def delete_repository(self, db: Session, repository_id: int) -> Repository:
        repo = self.get_repository(db, repository_id)
        repo.is_active = False
        db.commit()
        db.refresh(repo)
        logger.info("Soft-deleted repository id=%s (%s)", repository_id, repo.full_name)
        return repo

    def refresh_metadata(self, db: Session, repository_id: int) -> Repository:
        repo = self.get_repository(db, repository_id)
        gh_meta = self.extractor.get_repository(repo.owner, repo.name)
        
        repo.github_id = gh_meta.get("id", repo.github_id)
        repo.description = gh_meta.get("description", repo.description)
        repo.stargazers_count = gh_meta.get("stargazers_count", repo.stargazers_count)
        repo.forks_count = gh_meta.get("forks_count", repo.forks_count)
        repo.open_issues_count = gh_meta.get("open_issues_count", repo.open_issues_count)
        repo.watchers_count = gh_meta.get("watchers_count", repo.watchers_count)
        repo.language = gh_meta.get("language", repo.language)
        repo.repo_metadata = gh_meta

        db.commit()
        db.refresh(repo)
        return repo


repository_service = RepositoryService()

