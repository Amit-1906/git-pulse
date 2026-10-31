#!/usr/bin/env python3
"""
Seeds comprehensive realistic demo data for the GitPulse platform.
Ensures all 9 pages of the dashboard have rich, interconnected records.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import engine, Base, SessionLocal
from app.models.repository import Repository
from app.models.raw_events import Commit, PullRequest, Issue
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.models.raw_repositories import RawRepository
from app.models.pipeline_run import PipelineRun
from app.models.extraction_job import ExtractionJob
from app.models.checkpoint import ExtractionCheckpoint
from app.models.operational import DataQualityResult


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if already seeded with commits
        if db.query(Commit).count() > 10:
            print("Database already contains demo commits. Skipping seed.")
            return

        print("Seeding rich GitPulse demo records...")

        # Update repos
        fastapi_repo = db.query(Repository).filter_by(full_name="tiangolo/fastapi").first()
        if not fastapi_repo:
            fastapi_repo = Repository(
                github_id=101,
                owner="tiangolo",
                name="fastapi",
                full_name="tiangolo/fastapi",
                description="FastAPI framework, high performance, easy to learn, fast to code, ready for production",
                html_url="https://github.com/tiangolo/fastapi",
                stargazers_count=78400,
                forks_count=6500,
                open_issues_count=210,
                watchers_count=78400,
                language="Python",
                is_active=True,
                last_synced_at=datetime.utcnow() - timedelta(minutes=15),
            )
            db.add(fastapi_repo)
            db.commit()
            db.refresh(fastapi_repo)

        repo_id = fastapi_repo.id

        authors = [
            ("tiangolo", "tiangolo@example.com"),
            ("samuelcolvin", "samuel@example.com"),
            ("dmontagu", "dmontagu@example.com"),
            ("Kludex", "kludex@example.com"),
            ("adriangb", "adrian@example.com"),
        ]

        # Seed 40 commits across the past 30 days
        for i in range(40):
            days_ago = 30 - int((i / 40.0) * 30)
            c_date = datetime.utcnow() - timedelta(days=days_ago, hours=(i % 12))
            author = authors[i % len(authors)]
            sha = f"e{i:03d}" + "a" * 36
            commit = Commit(
                repository_id=repo_id,
                sha=sha,
                author_name=author[0],
                author_email=author[1],
                author_date=c_date,
                committer_name="GitHub",
                committer_date=c_date,
                message=f"feat(core): update internal handler #{i + 1}\n\nOptimizes request execution path.",
                additions=15 + (i * 7) % 80,
                deletions=2 + (i * 3) % 25,
                total_changes=17 + (i * 10) % 105,
                raw_payload={"sha": sha, "author": author[0]},
            )
            db.add(commit)

            # Bronze Raw Commit
            raw_c = RawCommit(
                repository_id=repo_id,
                commit_sha=sha,
                raw_payload={"sha": sha, "author": author[0]},
                extracted_at=c_date,
                source_updated_at=c_date,
            )
            db.add(raw_c)

        # Seed Pull Requests
        pr_titles = [
            ("Support dependency injection overrides in nested scopes", True, 8.5),
            ("Add validation benchmark suite for Pydantic v2", True, 24.2),
            ("Fix typing annotations for response_model parameter", True, 4.0),
            ("Upgrade Starlette compatibility to latest release", True, 18.0),
            ("Add async background task failure telemetry", False, None),
            ("Improve documentation for WebSocket security headers", True, 48.0),
            ("Refactor lifespan context manager initialization", False, None),
            ("Fix multipart form data memory leak on Windows", True, 12.5),
        ]

        for idx, (title, is_merged, hours_to_merge) in enumerate(pr_titles):
            days_ago = 20 - idx * 2
            created = datetime.utcnow() - timedelta(days=days_ago, hours=6)
            merged = created + timedelta(hours=hours_to_merge) if is_merged and hours_to_merge else None
            state = "closed" if is_merged else ("open" if idx % 2 == 0 else "closed")
            pr = PullRequest(
                repository_id=repo_id,
                github_id=2000 + idx,
                number=500 + idx,
                title=title,
                body=f"Detailed implementation notes for {title}",
                state=state,
                is_merged=is_merged,
                user_login=authors[idx % len(authors)][0],
                base_branch="master",
                head_branch=f"feature/pr-{idx}",
                comments_count=3 + idx * 2,
                additions=45 + idx * 30,
                deletions=10 + idx * 8,
                changed_files=1 + idx,
                created_at_gh=created,
                merged_at_gh=merged,
                closed_at_gh=merged if is_merged else (created + timedelta(days=2) if state == "closed" else None),
                raw_payload={"number": 500 + idx, "title": title},
            )
            db.add(pr)

            raw_pr = RawPullRequest(
                repository_id=repo_id,
                github_pr_id=2000 + idx,
                pr_number=500 + idx,
                raw_payload={"number": 500 + idx, "title": title},
                extracted_at=created,
                source_updated_at=merged or created,
            )
            db.add(raw_pr)

        # Seed Issues
        issue_titles = [
            ("Request body streaming timeout on slow connections", "closed", 3.2),
            ("Memory leak when using custom APIRoute subclass", "closed", 14.5),
            ("OpenAPI schema missing custom response headers", "open", None),
            ("Clarify exception handler precedence in documentation", "closed", 1.8),
            ("Add support for unix domain sockets on Linux", "open", None),
            ("CORS preflight request failing on safari browser", "closed", 6.0),
        ]

        for idx, (title, state, res_days) in enumerate(issue_titles):
            days_ago = 25 - idx * 3
            created = datetime.utcnow() - timedelta(days=days_ago)
            closed = created + timedelta(days=res_days) if res_days and state == "closed" else None
            issue = Issue(
                repository_id=repo_id,
                github_id=3000 + idx,
                number=800 + idx,
                title=title,
                body="Issue report description",
                state=state,
                user_login=authors[(idx + 2) % len(authors)][0],
                comments_count=2 + idx * 3,
                labels=["bug" if idx % 2 == 0 else "enhancement"],
                created_at_gh=created,
                closed_at_gh=closed,
                raw_payload={"number": 800 + idx, "title": title},
            )
            db.add(issue)

            raw_iss = RawIssue(
                repository_id=repo_id,
                github_issue_id=3000 + idx,
                issue_number=800 + idx,
                raw_payload={"number": 800 + idx, "title": title},
                extracted_at=created,
                source_updated_at=closed or created,
            )
            db.add(raw_iss)

        # Seed Pipeline Runs & Jobs
        for idx in range(5):
            started = datetime.utcnow() - timedelta(hours=(5 - idx) * 4)
            run = PipelineRun(
                repository_id=repo_id,
                pipeline_name="github_repo_sync",
                stage="load",
                status="completed",
                started_at=started,
                finished_at=started + timedelta(seconds=12 + idx * 2),
                duration_seconds=12.4 + idx * 2.1,
                records_extracted=35 + idx * 5,
                records_loaded=35 + idx * 5,
            )
            db.add(run)

            job = ExtractionJob(
                job_id=f"job_demo_{idx:03d}",
                repository_id=repo_id,
                repository_full_name="tiangolo/fastapi",
                status="COMPLETED",
                resources=["repository", "commits", "pull_requests", "issues"],
                incremental=idx > 0,
                records_extracted={"commits": 20, "pull_requests": 5, "issues": 5, "repository": 1},
                records_loaded={"commits": 20, "pull_requests": 5, "issues": 5, "repository": 1},
                started_at=started,
                finished_at=started + timedelta(seconds=12 + idx * 2),
                duration_seconds=12.4 + idx * 2.1,
            )
            db.add(job)

        # Seed Data Quality Assertions
        quality_rules = [
            ("unique:dim_repositories.full_name", "repositories", True, 0),
            ("not_null:fct_commits.commit_sha", "commits", True, 0),
            ("accepted_values:fct_pull_requests.standardized_status", "pull_requests", True, 0),
            ("relationships:fct_issues.repository_id", "issues", True, 0),
            ("not_null:dim_contributors.author_login", "contributors", True, 0),
            ("unique:fct_pull_requests.github_pr_id", "pull_requests", True, 0),
        ]
        for rule_name, res_type, passed, fails in quality_rules:
            dqr = DataQualityResult(
                repository_id=repo_id,
                job_id="dbt_test_run",
                source="dbt",
                rule_name=rule_name,
                resource_type=res_type,
                passed=passed,
                severity="warn",
                failure_count=fails,
                evaluated_at=datetime.utcnow(),
            )
            db.add(dqr)

        # Seed Checkpoint
        cp = ExtractionCheckpoint(
            repository_id=repo_id,
            resource_type="commits",
            last_checkpoint_timestamp=datetime.utcnow() - timedelta(hours=1),
            last_record_id="e039" + "a" * 36,
        )
        db.add(cp)

        db.commit()
        print("[OK] Successfully seeded rich GitPulse demo records!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
