"""
GitPulse API Client
Communicates with the FastAPI backend. Falls back to empty structures when offline.
"""
import os
import requests
from typing import Any, Dict, List, Optional


class GitPulseAPIClient:
    """HTTP client for the GitPulse FastAPI backend with graceful offline fallbacks."""

    def __init__(self, base_url: Optional[str] = None):
        # Resolution order:
        #   1. Explicit base_url argument (tests / local override)
        #   2. BACKEND_URL — injected by Vercel service binding (base URL, no path)
        #      The binding provides the service root, so we append /api/v1 ourselves.
        #   3. API_BASE_URL — set manually in Streamlit Cloud / Railway / local .env
        #      Expected to already contain the full path (e.g. https://x.vercel.app/api/v1)
        #   4. Localhost default for local development
        if base_url:
            self.base_url = base_url
        elif os.getenv("BACKEND_URL"):
            # Strip any trailing slash then append the versioned API prefix
            self.base_url = os.getenv("BACKEND_URL", "").rstrip("/") + "/api/v1"
        else:
            self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        self.timeout = 5.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            r = requests.post(url, json=data, params=params, timeout=self.timeout)
            if r.status_code in (200, 201, 202):
                return r.json()
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def check_health(self) -> Dict[str, Any]:
        result = self._get("health")
        if result:
            return {"connected": True, "data": result}
        return {
            "connected": False,
            "data": {
                "status": "standby",
                "version": "0.1.0",
                "environment": "standalone-preview",
                "uptime_seconds": 0.0,
                "database": {"connected": False, "status": "standby", "dialect": "postgresql"},
            },
        }

    # ------------------------------------------------------------------
    # GitHub Authentication & Integration
    # ------------------------------------------------------------------
    def connect_github(self, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self._post("github/connect", {"token": token})

    def get_github_status(self) -> Dict[str, Any]:
        result = self._get("github/status")
        if result:
            return result
        return {
            "authenticated": False,
            "token_configured": False,
            "token_masked": None,
            "user": None,
            "scopes": [],
            "rate_limit": {"limit": 60, "remaining": 60, "used": 0},
        }

    def get_github_rate_limit(self) -> Optional[Dict[str, Any]]:
        return self._get("github/rate-limit")

    def list_accessible_github_repos(self) -> List[Dict[str, Any]]:
        result = self._get("github/repositories")
        return result if result is not None else []

    # ------------------------------------------------------------------
    # Extraction Engine & Jobs
    # ------------------------------------------------------------------
    def start_extraction(
        self,
        repository_full_name: str,
        resources: Optional[List[str]] = None,
        incremental: bool = True,
        run_sync: bool = False,
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "repository_full_name": repository_full_name,
            "resources": resources or ["repository", "commits", "pull_requests", "issues"],
            "incremental": incremental,
        }
        return self._post("extraction/start", payload, params={"run_sync": run_sync})

    def get_extraction_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._get(f"extraction/status/{job_id}")

    def list_extraction_history(
        self, repository: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if repository:
            params["repository"] = repository
        result = self._get("extraction/history", params=params)
        if result is not None:
            return result
        return self.get_pipeline_runs()

    def retry_extraction(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._post("extraction/retry", {"job_id": job_id})

    def cancel_extraction(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._post(f"extraction/cancel/{job_id}")

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------
    def get_repositories(self) -> List[Dict[str, Any]]:
        result = self._get("repositories")
        return result if result is not None else []

    def get_repository_detail(self, repo_id: int) -> Optional[Dict[str, Any]]:
        return self._get(f"repositories/{repo_id}")

    def register_repository(self, full_name: str) -> Optional[Dict[str, Any]]:
        return self._post("repositories", {"full_name": full_name, "fetch_initial_metadata": True})

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def trigger_pipeline(self, repository_id: int) -> Optional[Dict[str, Any]]:
        return self._post(
            "pipeline/trigger",
            {"repository_id": repository_id, "stages": ["extract", "load"]},
        )

    def get_pipeline_runs(
        self, repository_id: Optional[int] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if repository_id is not None:
            params["repository_id"] = repository_id
        result = self._get("pipeline/runs", params=params)
        return result if result is not None else []

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    def get_overview_metrics(
        self, repository_id: Optional[int] = None
    ) -> Dict[str, Any]:
        params = {"repository_id": repository_id} if repository_id is not None else None
        result = self._get("analytics/overview", params=params)
        if result:
            return result
        return {
            "total_repositories": 0,
            "active_repositories": 0,
            "total_commits_tracked": 0,
            "total_pull_requests": 0,
            "total_issues": 0,
            "total_contributors": 0,
            "total_pipeline_runs": 0,
            "pipeline_success_rate": 0.0,
        }

    def get_contributors(
        self, repository_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        params = {"repository_id": repository_id} if repository_id else None
        result = self._get("analytics/contributors", params=params)
        return result if result is not None else []

    def get_commits(
        self,
        repository_id: Optional[int] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if repository_id:
            params["repository_id"] = repository_id
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        result = self._get("analytics/commits", params=params)
        return result if result is not None else []

    def get_pull_requests(
        self,
        repository_id: Optional[int] = None,
        state: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if repository_id:
            params["repository_id"] = repository_id
        if state:
            params["state"] = state
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        result = self._get("analytics/pull-requests", params=params)
        return result if result is not None else []

    def get_issues(
        self,
        repository_id: Optional[int] = None,
        state: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if repository_id:
            params["repository_id"] = repository_id
        if state:
            params["state"] = state
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        result = self._get("analytics/issues", params=params)
        return result if result is not None else []

    # ------------------------------------------------------------------
    # Database & Storage Telemetry
    # ------------------------------------------------------------------
    def get_database_status(self) -> Dict[str, Any]:
        result = self._get("database/status")
        if result:
            return result
        return {
            "status": "standby",
            "connected": False,
            "dialect": "postgresql",
            "database_name": "gitpulse_db",
            "latency_ms": 0.0,
            "pool": {"pool_size": 10, "checked_in": 0, "checked_out": 0, "overflow": 0},
        }

    def get_database_statistics(self) -> Dict[str, Any]:
        result = self._get("database/statistics")
        if result:
            return result
        return {
            "total_tables": 0,
            "total_records": 0,
            "bronze_records": 0,
            "silver_records": 0,
            "operational_records": 0,
            "tables": [],
        }

    def get_database_tables(self) -> List[Dict[str, Any]]:
        result = self._get("database/tables")
        if result and "tables" in result:
            return result["tables"]
        return []

    def get_storage_summary(self) -> Dict[str, Any]:
        result = self._get("database/storage-summary")
        if result:
            return result
        return {
            "engine_dialect": "postgresql",
            "tiers": {
                "bronze": {"tier": "bronze", "table_count": 0, "total_rows": 0, "tables": []},
                "silver": {"tier": "silver", "table_count": 0, "total_rows": 0, "tables": []},
                "operational": {"tier": "operational", "table_count": 0, "total_rows": 0, "tables": []},
            },
            "total_raw_payloads": 0,
            "total_storage_rows": 0,
        }

    # ------------------------------------------------------------------
    # dbt Transformation & Data Quality
    # ------------------------------------------------------------------
    def get_transformation_status(self) -> Dict[str, Any]:
        result = self._get("transformation/status")
        if result:
            return result
        return {
            "dbt_installed": False,
            "dbt_version": None,
            "project_name": "gitpulse_transforms",
            "project_dir": "dbt",
            "active_target": "dev",
            "database_connected": False,
            "total_models": 0,
            "total_tests": 0,
            "total_sources": 0,
        }

    def run_transformation(
        self,
        command: str = "run",
        models: Optional[List[str]] = None,
        target: str = "dev",
        full_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        payload = {"command": command, "models": models, "target": target, "full_refresh": full_refresh}
        return self._post("transformation/run", payload)

    def test_transformation(
        self,
        models: Optional[List[str]] = None,
        target: str = "dev",
    ) -> Optional[Dict[str, Any]]:
        payload = {"command": "test", "models": models, "target": target}
        return self._post("transformation/test", payload)

    def get_transformation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        result = self._get("transformation/history", params={"limit": limit})
        return result if result is not None else []

    def get_data_lineage(self) -> Dict[str, Any]:
        result = self._get("transformation/lineage")
        if result:
            return result
        return {
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "pipeline_flow": (
                "GitHub API -> PostgreSQL Raw Tables -> dbt Staging "
                "-> Intermediate -> Facts & Dimensions -> Analytics Dashboard"
            ),
        }

    def get_quality_results(
        self,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if resource_type:
            params["resource_type"] = resource_type
        if status:
            params["status"] = status
        result = self._get("quality/results", params=params)
        if result:
            return result
        return {
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate_pct": 0.0,
            "results": [],
        }


api_client = GitPulseAPIClient()
