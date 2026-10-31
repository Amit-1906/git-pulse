# GitPulse API Specification

Base URL: `/api/v1`

Interactive Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 1. Health & Probes

### `GET /api/v1/health`
Detailed platform health including database ping latency, uptime, environment, and version.

### `GET /api/v1/health/liveness`
Container liveness probe. Returns HTTP 200 `{"status": "alive"}`.

### `GET /api/v1/health/readiness`
Container readiness probe. Tests database reachability. Returns HTTP 200 if connected or HTTP 503 if unavailable.

---

## 2. GitHub Authentication & Status

### `POST /api/v1/github/connect`
Connects and validates a GitHub Personal Access Token (PAT).
- Validates token against `/user` and `/rate_limit`.
- Returns identity, OAuth scopes, and rate limit.
- **Never exposes raw tokens in responses or logs** (masked: `ghp_1234...5678`).
- Request Body:
```json
{
  "token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### `GET /api/v1/github/status`
Returns current GitHub authentication status, token presence (masked), user details, and quota.

### `GET /api/v1/github/rate-limit`
Returns exact GitHub rate limits across `core`, `search`, and `graphql` quotas with reset epochs.

### `GET /api/v1/github/repositories`
Lists repositories accessible to the configured credential or trending public repositories.

---

## 3. Data Extraction Engine

### `POST /api/v1/extraction/start`
Initializes and dispatches an asynchronous or synchronous extraction job.
- **Concurrency Protection**: Rejects overlapping duplicate jobs for the same repository with HTTP 409 (`DUPLICATE_JOB_IN_PROGRESS`).
- **Incremental Extraction**: Loads checkpoint high-water mark timestamp automatically unless `incremental=false`.
- **Query Parameters**: `run_sync` (boolean, default false).
- Request Body:
```json
{
  "repository_full_name": "tiangolo/fastapi",
  "resources": ["repository", "commits", "pull_requests", "issues"],
  "incremental": true,
  "since": "2026-10-01T00:00:00Z",
  "until": null,
  "max_pages": 10
}
```

### `GET /api/v1/extraction/status/{job_id}`
Returns real-time status (`PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL_SUCCESS`, `FAILED`, `CANCELLED`), duration, granular record counts, and error details per resource.

### `GET /api/v1/extraction/history`
Lists historical extraction jobs with optional filtering by `repository` and `status`.

### `POST /api/v1/extraction/retry`
Retries failed or partially successful extraction jobs.
- Request Body:
```json
{
  "job_id": "job_1234567890ab",
  "resources": ["issues"],
  "force_full_refresh": false
}
```

### `POST /api/v1/extraction/cancel/{job_id}`
Safely requests cancellation of an active extraction job.

---

## 4. Repositories

### `GET /api/v1/repositories`
List all monitored active repositories.
- Query parameters: `skip` (default 0), `limit` (default 100).

### `POST /api/v1/repositories`
Register a new repository to monitor.

### `GET /api/v1/repositories/{id}`
Retrieve repository record by internal ID.

### `DELETE /api/v1/repositories/{id}`
Soft-deletes a repository (`is_active = false`).

### `POST /api/v1/repositories/{id}/refresh`
Refreshes star count, open issues, and description from the live GitHub REST API.

---

## 5. Analytics

### `GET /api/v1/analytics/overview`
Aggregated system metrics across all repositories.

### `GET /api/v1/analytics/contributors`
Leaderboard of top authors by commit volume.
