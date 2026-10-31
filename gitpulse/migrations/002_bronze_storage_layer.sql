-- ============================================================================
-- Migration 002: Bronze Raw Storage Layer & Operational Observability
-- Tables: raw_repositories, raw_commits, raw_issues, raw_pull_requests,
--         extraction_logs, data_quality_results
-- Includes: JSONB preservation, SHA-256 payload hashes, GIN indexing
-- ============================================================================

-- 1. Raw Repositories (Bronze)
CREATE TABLE IF NOT EXISTS raw_repositories (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE SET NULL,
    github_repo_id BIGINT UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    raw_payload JSONB NOT NULL,
    source_endpoint VARCHAR(255) NOT NULL DEFAULT '/repos/{owner}/{repo}',
    extracted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    source_updated_at TIMESTAMP WITHOUT TIME ZONE,
    payload_hash VARCHAR(64),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_raw_repositories_github_repo_id ON raw_repositories(github_repo_id);
CREATE INDEX IF NOT EXISTS ix_raw_repositories_full_name ON raw_repositories(full_name);
CREATE INDEX IF NOT EXISTS ix_raw_repositories_extracted_at ON raw_repositories(extracted_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_repositories_source_updated ON raw_repositories(source_updated_at);
CREATE INDEX IF NOT EXISTS ix_raw_repositories_payload_gin ON raw_repositories USING gin (raw_payload jsonb_path_ops);

-- 2. Raw Commits (Bronze)
CREATE TABLE IF NOT EXISTS raw_commits (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_sha VARCHAR(40) NOT NULL,
    raw_payload JSONB NOT NULL,
    source_endpoint VARCHAR(255) NOT NULL DEFAULT '/repos/{owner}/{repo}/commits',
    extracted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    source_updated_at TIMESTAMP WITHOUT TIME ZONE,
    payload_hash VARCHAR(64),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_raw_commits_repo_sha UNIQUE (repository_id, commit_sha)
);

CREATE INDEX IF NOT EXISTS ix_raw_commits_repo_id ON raw_commits(repository_id);
CREATE INDEX IF NOT EXISTS ix_raw_commits_sha ON raw_commits(commit_sha);
CREATE INDEX IF NOT EXISTS ix_raw_commits_extracted_at ON raw_commits(extracted_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_commits_source_updated ON raw_commits(source_updated_at);
CREATE INDEX IF NOT EXISTS ix_raw_commits_payload_gin ON raw_commits USING gin (raw_payload jsonb_path_ops);

-- 3. Raw Issues (Bronze)
CREATE TABLE IF NOT EXISTS raw_issues (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_issue_id BIGINT NOT NULL,
    issue_number INTEGER NOT NULL,
    raw_payload JSONB NOT NULL,
    source_endpoint VARCHAR(255) NOT NULL DEFAULT '/repos/{owner}/{repo}/issues',
    extracted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    source_updated_at TIMESTAMP WITHOUT TIME ZONE,
    payload_hash VARCHAR(64),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_raw_issues_repo_gh_id UNIQUE (repository_id, github_issue_id)
);

CREATE INDEX IF NOT EXISTS ix_raw_issues_repo_id ON raw_issues(repository_id);
CREATE INDEX IF NOT EXISTS ix_raw_issues_github_issue_id ON raw_issues(github_issue_id);
CREATE INDEX IF NOT EXISTS ix_raw_issues_repo_number ON raw_issues(repository_id, issue_number);
CREATE INDEX IF NOT EXISTS ix_raw_issues_extracted_at ON raw_issues(extracted_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_issues_source_updated ON raw_issues(source_updated_at);
CREATE INDEX IF NOT EXISTS ix_raw_issues_payload_gin ON raw_issues USING gin (raw_payload jsonb_path_ops);

-- 4. Raw Pull Requests (Bronze)
CREATE TABLE IF NOT EXISTS raw_pull_requests (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_pr_id BIGINT NOT NULL,
    pr_number INTEGER NOT NULL,
    raw_payload JSONB NOT NULL,
    source_endpoint VARCHAR(255) NOT NULL DEFAULT '/repos/{owner}/{repo}/pulls',
    extracted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    source_updated_at TIMESTAMP WITHOUT TIME ZONE,
    payload_hash VARCHAR(64),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_raw_pull_requests_repo_gh_id UNIQUE (repository_id, github_pr_id)
);

CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_repo_id ON raw_pull_requests(repository_id);
CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_github_pr_id ON raw_pull_requests(github_pr_id);
CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_repo_number ON raw_pull_requests(repository_id, pr_number);
CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_extracted_at ON raw_pull_requests(extracted_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_source_updated ON raw_pull_requests(source_updated_at);
CREATE INDEX IF NOT EXISTS ix_raw_pull_requests_payload_gin ON raw_pull_requests USING gin (raw_payload jsonb_path_ops);

-- 5. Extraction Logs (Operational)
CREATE TABLE IF NOT EXISTS extraction_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    repository_id INTEGER,
    repository_full_name VARCHAR(200) NOT NULL,
    level VARCHAR(10) NOT NULL DEFAULT 'INFO',
    resource_type VARCHAR(50),
    stage VARCHAR(50),
    message TEXT NOT NULL,
    details JSONB,
    records_processed INTEGER,
    duration_ms FLOAT,
    logged_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_extraction_logs_job_id ON extraction_logs(job_id);
CREATE INDEX IF NOT EXISTS ix_extraction_logs_job_level ON extraction_logs(job_id, level);
CREATE INDEX IF NOT EXISTS ix_extraction_logs_repo_logged ON extraction_logs(repository_id, logged_at);

-- 6. Data Quality Results (Operational)
CREATE TABLE IF NOT EXISTS data_quality_results (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER,
    repository_full_name VARCHAR(200),
    job_id VARCHAR(64),
    source VARCHAR(50) NOT NULL DEFAULT 'pipeline',
    rule_name VARCHAR(200) NOT NULL,
    resource_type VARCHAR(50),
    column_name VARCHAR(100),
    passed BOOLEAN NOT NULL,
    severity VARCHAR(10) NOT NULL DEFAULT 'warn',
    failure_count INTEGER DEFAULT 0,
    total_count INTEGER,
    failure_rate FLOAT,
    message TEXT,
    details JSONB,
    evaluated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_dqr_repo_rule ON data_quality_results(repository_id, rule_name);
CREATE INDEX IF NOT EXISTS ix_dqr_passed_evaluated ON data_quality_results(passed, evaluated_at);
CREATE INDEX IF NOT EXISTS ix_dqr_source_resource ON data_quality_results(source, resource_type);

