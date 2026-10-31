# GitPulse Architecture Overview

GitPulse is an enterprise-grade ELT (Extract, Load, Transform) platform designed to ingest, store, transform, and analyze GitHub activity across public and private repositories.

```
┌──────────────────────────────────────────────────────────────┐
│                    GitHub REST API v3                        │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP / JSON
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                      GitPulse Backend                        │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ GitHubClient (Link Header Paginator, Backoff, Quota) │   │
│   └──────────────────────────┬───────────────────────────┘   │
│                              ▼                               │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ ExtractionEngine (Checkpoints, Job Telemetry, Mutex) │   │
│   │   ├── RepositoryExtractor                            │   │
│   │   ├── CommitsExtractor (since/until, parent SHAs)    │   │
│   │   ├── IssuesExtractor (excludes PRs, assignees)      │   │
│   │   └── PullRequestsExtractor (early termination)      │   │
│   └──────────────────────────┬───────────────────────────┘   │
└──────────────────────────────┼───────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │                                     │
            ▼                                     ▼
 ┌──────────────────────┐             ┌──────────────────────┐
 │    Bronze Layer      │             │     Silver Layer     │
 │     raw_events       │             │   commits, issues,   │
 │   (Raw JSONB Data)   │             │    pull_requests     │
 └──────────┬───────────┘             └──────────┬───────────┘
            │                                    │
            └──────────────────┬─────────────────┘
                               │
                               ▼
            ┌────────────────────────────────────┐
            │        dbt Core (Gold Marts)       │
            │   - stg_github__*                  │
            │   - int_pr_cycle_times             │
            │   - fct_daily_repo_metrics         │
            │   - dim_repositories               │
            │   - dim_contributors               │
            └──────────────────┬─────────────────┘
                               │
                               ▼
            ┌────────────────────────────────────┐
            │         GitPulse Frontend          │
            │    Streamlit Multipage Platform    │
            │     Plotly Analytical Views        │
            └────────────────────────────────────┘
```

## Architectural Principles

1. **Bronze (Raw) Persistence**: All payloads from GitHub are preserved byte-for-byte in PostgreSQL using `JSONB`. This guarantees zero data loss and allows historical re-parsing at any time without consuming GitHub API quota.
2. **Silver (Entity) Promotion**: Clean relational entities (`Commit`, `PullRequest`, `Issue`, `Repository`) are extracted with normalized schemas and deduplicated with unique constraint safeguards.
3. **Gold (dbt Analytics Marts)**: Dimensional models (`dim_repositories`, `dim_contributors`) and fact tables (`fct_daily_repo_metrics`) provide fast aggregated analytical queries.
4. **Resilient Service & Repository Pattern**: Clean separation of concerns between HTTP routes, business logic services, and persistence repositories.
5. **FastAPI & Streamlit Separation**: Modern RESTful API decoupled from the interactive analytics dashboard, allowing both CLI and GUI orchestration.

---

## 🔍 Extraction Engine Strategies & Endpoint Limitations

GitHub's REST API endpoints exhibit fundamental differences in filtering and incremental capabilities. GitPulse applies resource-specific strategies:

| Resource | GitHub Endpoint | Incremental Filter Support | GitPulse Ingestion Strategy |
|---|---|---|---|
| **Repository** | `GET /repos/{owner}/{repo}` | None (Single object) | Full metadata refresh per extraction run. |
| **Commits** | `GET /repos/{owner}/{repo}/commits` | `since` (ISO 8601), `until` (ISO 8601) | Direct server-side filtering via `since=<last_checkpoint>`. Extracts parent commit SHA references. |
| **Issues** | `GET /repos/{owner}/{repo}/issues` | `since` (ISO 8601), `sort=updated`, `direction=asc` | Direct server-side filtering with `since=<last_checkpoint>`. **Crucial Detail**: GitHub API returns Pull Requests in the issues endpoint; GitPulse explicitly filters out items containing the `pull_request` key to prevent duplicate accounting. |
| **Pull Requests** | `GET /repos/{owner}/{repo}/pulls` | **NOT SUPPORTED** by GitHub API v3 | **Documented Limitation**: GitHub does not accept a `since` parameter on `/pulls`. GitPulse orders by `sort=updated` and `direction=desc`, comparing each PR's `updated_at` against the high-water mark and **terminating pagination early** once a page contains only records older than the checkpoint. |

---

## 🛡️ Concurrency & Partial Failure Guarantees

1. **Concurrency Lock**: To prevent duplicate extraction jobs and race conditions on the same repository, `ExtractionEngine.create_job` rejects overlapping runs with `HTTP 409 (DUPLICATE_JOB_IN_PROGRESS)` if a job is in `PENDING` or `RUNNING` status.
2. **Partial Failure Resilience**: If extraction of one resource fails (e.g. issues API responds with 404 or fails), previously loaded commits and pull requests are safely committed. The job is marked `PARTIAL_SUCCESS` with granular error details recorded in `error_details`.
3. **Token Security**: Tokens are configured via environment variables or dynamic authentication, masked on ingestion (`ghp_1234...5678`), and never echoed in raw format in logs, error traces, or API responses.
