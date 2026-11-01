"""
GitPulse Cached API Service Layer
Prevents redundant HTTP queries, accelerates page navigation, and provides safe cache invalidation on mutations.
"""
from typing import Any, Dict, List, Optional
import streamlit as st
from services.api_client import api_client

# Default cache time-to-live in seconds
READ_CACHE_TTL = 45
HEALTH_CACHE_TTL = 15


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_repositories() -> List[Dict[str, Any]]:
    return api_client.get_repositories()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_repository_detail(repo_id: int) -> Optional[Dict[str, Any]]:
    return api_client.get_repository_detail(repo_id)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_overview_metrics(repository_id: Optional[int] = None) -> Dict[str, Any]:
    return api_client.get_overview_metrics(repository_id=repository_id)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_commits(
    repository_id: Optional[int] = None,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return api_client.get_commits(
        repository_id=repository_id, author=author, since=since, until=until, limit=limit
    )


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_pull_requests(
    repository_id: Optional[int] = None,
    state: Optional[str] = None,
    author: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return api_client.get_pull_requests(
        repository_id=repository_id, state=state, author=author, since=since, limit=limit
    )


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_issues(
    repository_id: Optional[int] = None,
    state: Optional[str] = None,
    author: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return api_client.get_issues(
        repository_id=repository_id, state=state, author=author, since=since, limit=limit
    )


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_contributors(repository_id: Optional[int] = None) -> List[Dict[str, Any]]:
    return api_client.get_contributors(repository_id=repository_id)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_pipeline_runs(repository_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    return api_client.get_pipeline_runs(repository_id=repository_id, limit=limit)


@st.cache_data(ttl=HEALTH_CACHE_TTL, show_spinner=False)
def check_health() -> Dict[str, Any]:
    return api_client.check_health()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_github_status() -> Dict[str, Any]:
    return api_client.get_github_status()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_github_rate_limit() -> Dict[str, Any]:
    return api_client.get_github_rate_limit()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def list_accessible_github_repos() -> List[Dict[str, Any]]:
    return api_client.list_accessible_github_repos()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def list_extraction_history(repository: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    return api_client.list_extraction_history(repository=repository, limit=limit)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_extraction_status(job_id: str) -> Optional[Dict[str, Any]]:
    return api_client.get_extraction_status(job_id)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_transformation_status() -> Dict[str, Any]:
    return api_client.get_transformation_status()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_quality_results() -> Dict[str, Any]:
    return api_client.get_quality_results()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_transformation_history(limit: int = 20) -> List[Dict[str, Any]]:
    return api_client.get_transformation_history(limit=limit)


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_data_lineage() -> Dict[str, Any]:
    return api_client.get_data_lineage()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_database_status() -> Dict[str, Any]:
    return api_client.get_database_status()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_database_statistics() -> Dict[str, Any]:
    return api_client.get_database_statistics()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_database_tables() -> List[Dict[str, Any]]:
    return api_client.get_database_tables()


@st.cache_data(ttl=READ_CACHE_TTL, show_spinner=False)
def get_storage_summary() -> Dict[str, Any]:
    return api_client.get_storage_summary()


# Cache management & mutations
def clear_all_caches() -> None:
    st.cache_data.clear()


def connect_github(token: str) -> Dict[str, Any]:
    res = api_client.connect_github(token)
    st.cache_data.clear()
    return res


def register_repository(full_name: str) -> Optional[Dict[str, Any]]:
    res = api_client.register_repository(full_name)
    get_repositories.clear()
    get_overview_metrics.clear()
    return res


def trigger_pipeline(repository_id: int) -> Optional[Dict[str, Any]]:
    res = api_client.trigger_pipeline(repository_id)
    get_pipeline_runs.clear()
    list_extraction_history.clear()
    get_overview_metrics.clear()
    return res


def start_extraction(
    repository_full_name: str,
    resources: Optional[List[str]] = None,
    incremental: bool = True,
    run_sync: bool = False,
) -> Optional[Dict[str, Any]]:
    res = api_client.start_extraction(
        repository_full_name=repository_full_name,
        resources=resources,
        incremental=incremental,
        run_sync=run_sync,
    )
    list_extraction_history.clear()
    get_pipeline_runs.clear()
    return res


def cancel_extraction(job_id: str) -> Dict[str, Any]:
    res = api_client.cancel_extraction(job_id)
    list_extraction_history.clear()
    return res


def retry_extraction(job_id: str) -> Optional[Dict[str, Any]]:
    res = api_client.retry_extraction(job_id)
    list_extraction_history.clear()
    return res


def run_transformation() -> Dict[str, Any]:
    res = api_client.run_transformation()
    get_transformation_status.clear()
    get_transformation_history.clear()
    get_quality_results.clear()
    return res


def test_transformation() -> Dict[str, Any]:
    res = api_client.test_transformation()
    get_quality_results.clear()
    get_transformation_status.clear()
    return res

