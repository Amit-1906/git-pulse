import pytest
from app.api.v1.endpoints.repositories import (
    list_repositories,
    create_repository,
    get_repository,
    delete_repository,
)
from app.schemas.repository import RepositoryCreate
from app.core.exceptions import GitPulseException, EntityNotFoundException


def test_repository_endpoints_lifecycle(db_session):
    # 1. Create
    repo_in = RepositoryCreate(
        full_name="psf/requests",
        fetch_initial_metadata=False,
    )
    repo = create_repository(repo_in=repo_in, db=db_session)
    assert repo.owner == "psf"
    assert repo.name == "requests"
    assert repo.full_name == "psf/requests"
    repo_id = repo.id

    # 2. List
    repos = list_repositories(skip=0, limit=100, db=db_session)
    assert any(r.id == repo_id for r in repos)

    # 3. Get by ID
    fetched = get_repository(repository_id=repo_id, db=db_session)
    assert fetched.id == repo_id
    assert fetched.full_name == "psf/requests"

    # 4. Soft Delete
    deleted = delete_repository(repository_id=repo_id, db=db_session)
    assert deleted.is_active is False

    # 5. Invalid name format
    invalid_in = RepositoryCreate(full_name="invalidformat", fetch_initial_metadata=False)
    with pytest.raises(GitPulseException) as exc_info:
        create_repository(repo_in=invalid_in, db=db_session)
    assert exc_info.value.code == "INVALID_REPOSITORY_NAME"
