from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.repositories.base import BaseRepository
from app.schemas.repository import RepositoryCreate, RepositoryUpdate


class RepositoryRepository(BaseRepository[Repository, RepositoryCreate, RepositoryUpdate]):
    def __init__(self):
        super().__init__(Repository)

    def get_by_full_name(self, db: Session, full_name: str) -> Optional[Repository]:
        stmt = select(Repository).where(Repository.full_name == full_name.lower().strip())
        return db.scalars(stmt).first()

    def get_by_github_id(self, db: Session, github_id: int) -> Optional[Repository]:
        stmt = select(Repository).where(Repository.github_id == github_id)
        return db.scalars(stmt).first()

    def get_active(self, db: Session, skip: int = 0, limit: int = 100) -> List[Repository]:
        stmt = (
            select(Repository)
            .where(Repository.is_active == True)
            .order_by(Repository.full_name.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


repository_repo = RepositoryRepository()

