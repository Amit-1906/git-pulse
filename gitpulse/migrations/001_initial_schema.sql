-- ============================================================================
-- Migration 001: Initial Core Schema
-- Tables: repositories, pipeline_runs, raw_events, commits, issues, pull_requests,
--         extraction_jobs, extraction_checkpoints
-- ============================================================================

-- Repositories Table
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    github_id INTEGER UNIQUE,
    owner VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) UNIQUE NOT NULL,
    description TEXT,
    html_url VARCHAR(255),
    default_branch VARCHAR(50) NOT NULL DEFAULT 'main',
    visibility VARCHAR(20) NOT NULL DEFAULT 'public',
    stargazers_count INTEGER NOT NULL DEFAULT 0,
    forks_count INTEGER NOT NULL DEFAULT 0,
    open_issues_count INTEGER NOT NULL DEFAULT 0,
    watchers_count INTEGER NOT NULL DEFAULT 0,
    language VARCHAR(50),
    created_at_gh TIMESTAMP WITHOUT TIME ZONE,
    updated_at_gh TIMESTAMP WITHOUT TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at TIMESTAMP WITHOUT TIME ZONE,
    repo_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_repositories_owner ON repositories(owner);
CREATE INDEX IF NOT EXISTS ix_repositories_name ON repositories(name);
CREATE INDEX IF NOT EXISTS ix_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS ix_repositories_is_active ON repositories(is_active);
CREATE INDEX IF NOT EXISTS ix_repositories_language ON repositories(language);

-- Pipeline Runs Table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    pipeline_name VARCHAR(100) NOT NULL DEFAULT 'github_elt_pipeline',
    stage VARCHAR(50) NOT NULL DEFAULT 'extract',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    finished_at TIMESTAMP WITHOUT TIME ZONE,
    duration_seconds FLOAT,
    records_extracted INTEGER NOT NULL DEFAULT 0,
    records_loaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    run_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_pipeline_runs_repo_id ON pipeline_runs(repository_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_started_at ON pipeline_runs(started_at DESC);

-- Extraction Jobs Table
CREATE TABLE IF NOT EXISTS extraction_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) UNIQUE NOT NULL,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    repository_full_name VARCHAR(200) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    resources JSONB NOT NULL DEFAULT '[]'::jsonb,
    incremental BOOLEAN NOT NULL DEFAULT TRUE,
    since TIMESTAMP WITHOUT TIME ZONE,
    until TIMESTAMP WITHOUT TIME ZONE,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    finished_at TIMESTAMP WITHOUT TIME ZONE,
    duration_seconds FLOAT,
    records_extracted JSONB NOT NULL DEFAULT '{}'::jsonb,
    records_loaded JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    error_details JSONB DEFAULT '{}'::jsonb,
    checkpoint JSONB DEFAULT '{}'::jsonb,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_extraction_jobs_job_id ON extraction_jobs(job_id);
CREATE INDEX IF NOT EXISTS ix_extraction_jobs_repo_full_name ON extraction_jobs(repository_full_name);
CREATE INDEX IF NOT EXISTS ix_extraction_jobs_status ON extraction_jobs(status);

-- Extraction Checkpoints Table
CREATE TABLE IF NOT EXISTS extraction_checkpoints (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    last_checkpoint_timestamp TIMESTAMP WITHOUT TIME ZONE,
    last_record_id VARCHAR(100),
    checkpoint_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_repo_resource_checkpoint UNIQUE (repository_id, resource_type)
);

CREATE INDEX IF NOT EXISTS ix_extraction_checkpoints_repo_id ON extraction_checkpoints(repository_id);
CREATE INDEX IF NOT EXISTS ix_extraction_checkpoints_resource ON extraction_checkpoints(resource_type);

-- Raw Events Table (Legacy Bronze Layer)
CREATE TABLE IF NOT EXISTS raw_events (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fetched_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    error_message TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_raw_events_repo_id ON raw_events(repository_id);
CREATE INDEX IF NOT EXISTS ix_raw_events_event_type ON raw_events(event_type);
CREATE INDEX IF NOT EXISTS ix_raw_events_status ON raw_events(status);
CREATE INDEX IF NOT EXISTS ix_raw_events_payload_gin ON raw_events USING gin (payload jsonb_path_ops);

-- Silver Commits Table
CREATE TABLE IF NOT EXISTS commits (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    sha VARCHAR(40) UNIQUE NOT NULL,
    author_name VARCHAR(100),
    author_email VARCHAR(150),
    author_date TIMESTAMP WITHOUT TIME ZONE,
    committer_name VARCHAR(100),
    committer_date TIMESTAMP WITHOUT TIME ZONE,
    message TEXT,
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    total_changes INTEGER NOT NULL DEFAULT 0,
    parent_shas JSONB DEFAULT '[]'::jsonb,
    raw_payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_commits_repo_id ON commits(repository_id);
CREATE INDEX IF NOT EXISTS ix_commits_sha ON commits(sha);
CREATE INDEX IF NOT EXISTS ix_commits_author_date ON commits(author_date DESC);
CREATE INDEX IF NOT EXISTS ix_commits_author_email ON commits(author_email);

-- Silver Pull Requests Table
CREATE TABLE IF NOT EXISTS pull_requests (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_id BIGINT UNIQUE NOT NULL,
    number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT,
    state VARCHAR(20) NOT NULL,
    is_merged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_gh TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at_gh TIMESTAMP WITHOUT TIME ZONE,
    closed_at_gh TIMESTAMP WITHOUT TIME ZONE,
    merged_at_gh TIMESTAMP WITHOUT TIME ZONE,
    user_login VARCHAR(100),
    base_branch VARCHAR(100),
    head_branch VARCHAR(100),
    comments_count INTEGER NOT NULL DEFAULT 0,
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    changed_files INTEGER NOT NULL DEFAULT 0,
    raw_payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_pull_requests_repo_id ON pull_requests(repository_id);
CREATE INDEX IF NOT EXISTS ix_pull_requests_github_id ON pull_requests(github_id);
CREATE INDEX IF NOT EXISTS ix_pull_requests_number ON pull_requests(number);
CREATE INDEX IF NOT EXISTS ix_pull_requests_state ON pull_requests(state);
CREATE INDEX IF NOT EXISTS ix_pull_requests_created_at_gh ON pull_requests(created_at_gh DESC);

-- Silver Issues Table
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_id BIGINT UNIQUE NOT NULL,
    number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT,
    state VARCHAR(20) NOT NULL,
    created_at_gh TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at_gh TIMESTAMP WITHOUT TIME ZONE,
    closed_at_gh TIMESTAMP WITHOUT TIME ZONE,
    user_login VARCHAR(100),
    assignees JSONB DEFAULT '[]'::jsonb,
    comments_count INTEGER NOT NULL DEFAULT 0,
    labels JSONB DEFAULT '[]'::jsonb,
    raw_payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_issues_repo_id ON issues(repository_id);
CREATE INDEX IF NOT EXISTS ix_issues_github_id ON issues(github_id);
CREATE INDEX IF NOT EXISTS ix_issues_number ON issues(number);
CREATE INDEX IF NOT EXISTS ix_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS ix_issues_created_at_gh ON issues(created_at_gh DESC);

