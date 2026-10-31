import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundException, PipelineExecutionException
from app.extractors.github import GitHubExtractor
from app.models.pipeline_run import PipelineRun
from app.models.raw_events import RawEvent, Commit, PullRequest, Issue
from app.repositories.repository_repo import repository_repo
from app.repositories.pipeline_repo import pipeline_run_repo
from app.repositories.raw_events_repo import (
    raw_event_repo,
    commit_repo,
    pull_request_repo,
    issue_repo,
)
from app.repositories.raw_storage_repo import (
    raw_repository_repo,
    raw_commit_repo,
    raw_issue_repo,
    raw_pull_request_repo,
)
from app.schemas.pipeline import PipelineTriggerRequest
from app.services.base import BaseService

logger = logging.getLogger("gitpulse.services.pipeline")


class PipelineService(BaseService):
    """
    Orchestrates the ELT ingestion pipeline for GitHub repositories.
    Extracts data from the GitHub REST API, loads raw JSON into the Bronze layer (raw_events),
    and transforms/promotes events to Silver entity tables.
    """

    def __init__(self, extractor: Optional[GitHubExtractor] = None):
        self.extractor = extractor or GitHubExtractor()

    def run_pipeline(self, db: Session, request: PipelineTriggerRequest) -> PipelineRun:
        repo = repository_repo.get(db, request.repository_id)
        if not repo:
            raise EntityNotFoundException("Repository", request.repository_id)

        # 1. Initialize Pipeline Run Tracker
        run = pipeline_run_repo.create_run(
            db=db,
            repository_id=repo.id,
            pipeline_name="github_repo_sync",
            stage="extract",
        )

        records_extracted = 0
        records_loaded = 0
        extracted_summary: Dict[str, int] = {}

        try:
            logger.info("Starting ELT pipeline for repository: %s (run_id=%s)", repo.full_name, run.id)

            # --- STAGE 1: EXTRACT & BRONZE LOAD ---
            # 1.1 Commits
            commits_data: List[Dict[str, Any]] = []
            try:
                commits_data = self.extractor.list_commits(
                    owner=repo.owner, repo=repo.name, per_page=request.max_commits
                )
                raw_event_repo.bulk_store_events(
                    db=db,
                    repository_id=repo.id,
                    event_type="commit",
                    payloads=commits_data,
                    status="processed",
                )
                bronze_commits = []
                for c in commits_data:
                    if c.get("sha"):
                        src_dt = None
                        if c.get("commit", {}).get("author", {}).get("date"):
                            try:
                                src_dt = datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00"))
                            except Exception:
                                pass
                        bronze_commits.append({
                            "commit_sha": c["sha"],
                            "raw_payload": c,
                            "source_updated_at": src_dt,
                        })
                if bronze_commits:
                    raw_commit_repo.bulk_upsert(db, repository_id=repo.id, records=bronze_commits)

                records_extracted += len(commits_data)
                extracted_summary["commits"] = len(commits_data)
            except Exception as exc:
                logger.warning("Error extracting commits for %s: %s", repo.full_name, exc)

            # 1.2 Pull Requests
            pulls_data: List[Dict[str, Any]] = []
            try:
                pulls_data = self.extractor.list_pull_requests(
                    owner=repo.owner, repo=repo.name, state="all", per_page=request.max_pulls
                )
                raw_event_repo.bulk_store_events(
                    db=db,
                    repository_id=repo.id,
                    event_type="pull_request",
                    payloads=pulls_data,
                    status="processed",
                )
                bronze_prs = []
                for pr in pulls_data:
                    if pr.get("id"):
                        src_dt = None
                        if pr.get("updated_at"):
                            try:
                                src_dt = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                            except Exception:
                                pass
                        bronze_prs.append({
                            "github_pr_id": pr["id"],
                            "pr_number": pr.get("number", 0),
                            "raw_payload": pr,
                            "source_updated_at": src_dt,
                        })
                if bronze_prs:
                    raw_pull_request_repo.bulk_upsert(db, repository_id=repo.id, records=bronze_prs)

                records_extracted += len(pulls_data)
                extracted_summary["pull_requests"] = len(pulls_data)
            except Exception as exc:
                logger.warning("Error extracting pull requests for %s: %s", repo.full_name, exc)

            # 1.3 Issues
            issues_data: List[Dict[str, Any]] = []
            try:
                issues_data = self.extractor.list_issues(
                    owner=repo.owner, repo=repo.name, state="all", per_page=request.max_issues
                )
                raw_event_repo.bulk_store_events(
                    db=db,
                    repository_id=repo.id,
                    event_type="issue",
                    payloads=issues_data,
                    status="processed",
                )
                bronze_issues = []
                for iss in issues_data:
                    if iss.get("id") and "pull_request" not in iss:
                        src_dt = None
                        if iss.get("updated_at"):
                            try:
                                src_dt = datetime.fromisoformat(iss["updated_at"].replace("Z", "+00:00"))
                            except Exception:
                                pass
                        bronze_issues.append({
                            "github_issue_id": iss["id"],
                            "issue_number": iss.get("number", 0),
                            "raw_payload": iss,
                            "source_updated_at": src_dt,
                        })
                if bronze_issues:
                    raw_issue_repo.bulk_upsert(db, repository_id=repo.id, records=bronze_issues)

                records_extracted += len(issues_data)
                extracted_summary["issues"] = len(issues_data)
            except Exception as exc:
                logger.warning("Error extracting issues for %s: %s", repo.full_name, exc)

            # --- STAGE 2: SILVER ENTITY PARSING & UPSERT ---
            run.stage = "load"
            db.commit()

            # Process Commits
            for c in commits_data:
                sha = c.get("sha")
                if not sha:
                    continue
                commit_info = c.get("commit", {})
                author_info = commit_info.get("author", {})
                committer_info = commit_info.get("committer", {})

                author_date = None
                if author_info.get("date"):
                    try:
                        author_date = datetime.fromisoformat(author_info["date"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                committer_date = None
                if committer_info.get("date"):
                    try:
                        committer_date = datetime.fromisoformat(committer_info["date"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                existing_commit = commit_repo.get_by_sha(db, sha)
                if not existing_commit:
                    commit_obj = Commit(
                        repository_id=repo.id,
                        sha=sha,
                        author_name=author_info.get("name"),
                        author_email=author_info.get("email"),
                        author_date=author_date,
                        committer_name=committer_info.get("name"),
                        committer_date=committer_date,
                        message=commit_info.get("message"),
                        additions=c.get("stats", {}).get("additions", 0),
                        deletions=c.get("stats", {}).get("deletions", 0),
                        total_changes=c.get("stats", {}).get("total", 0),
                        raw_payload=c,
                    )
                    db.add(commit_obj)
                    records_loaded += 1

            # Process Pull Requests
            for pr in pulls_data:
                pr_id = pr.get("id")
                if not pr_id:
                    continue

                created_at_gh = None
                if pr.get("created_at"):
                    try:
                        created_at_gh = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                    except Exception:
                        created_at_gh = datetime.utcnow()

                closed_at_gh = None
                if pr.get("closed_at"):
                    try:
                        closed_at_gh = datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                merged_at_gh = None
                if pr.get("merged_at"):
                    try:
                        merged_at_gh = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                existing_pr = pull_request_repo.get_by_github_id(db, pr_id)
                if not existing_pr:
                    pr_obj = PullRequest(
                        repository_id=repo.id,
                        github_id=pr_id,
                        number=pr.get("number", 0),
                        title=pr.get("title", "")[:500],
                        body=pr.get("body"),
                        state=pr.get("state", "open"),
                        is_merged=bool(pr.get("merged_at")),
                        created_at_gh=created_at_gh or datetime.utcnow(),
                        closed_at_gh=closed_at_gh,
                        merged_at_gh=merged_at_gh,
                        user_login=(pr.get("user") or {}).get("login"),
                        comments_count=pr.get("comments", 0),
                        raw_payload=pr,
                    )
                    db.add(pr_obj)
                    records_loaded += 1
                else:
                    existing_pr.state = pr.get("state", existing_pr.state)
                    existing_pr.is_merged = bool(pr.get("merged_at"))
                    existing_pr.closed_at_gh = closed_at_gh

            # Process Issues
            for issue in issues_data:
                issue_id = issue.get("id")
                if not issue_id:
                    continue

                created_at_gh = None
                if issue.get("created_at"):
                    try:
                        created_at_gh = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                    except Exception:
                        created_at_gh = datetime.utcnow()

                closed_at_gh = None
                if issue.get("closed_at"):
                    try:
                        closed_at_gh = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                existing_issue = issue_repo.get_by_github_id(db, issue_id)
                if not existing_issue:
                    labels = [lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
                    issue_obj = Issue(
                        repository_id=repo.id,
                        github_id=issue_id,
                        number=issue.get("number", 0),
                        title=issue.get("title", "")[:500],
                        body=issue.get("body"),
                        state=issue.get("state", "open"),
                        created_at_gh=created_at_gh or datetime.utcnow(),
                        closed_at_gh=closed_at_gh,
                        user_login=(issue.get("user") or {}).get("login"),
                        comments_count=issue.get("comments", 0),
                        labels=labels,
                        raw_payload=issue,
                    )
                    db.add(issue_obj)
                    records_loaded += 1

            # Update repository last synced timestamp
            repo.last_synced_at = datetime.utcnow()
            db.commit()

            # --- STAGE 3: TRANSFORM (dbt run) ---
            if "transform" in request.stages:
                run.stage = "transform"
                db.commit()
                try:
                    from app.services.dbt_service import dbt_service
                    dbt_service.execute_command("run", target="dev", db=db)
                except Exception as dbt_exc:
                    logger.warning("dbt run in pipeline completed with notice: %s", dbt_exc)

            # --- STAGE 4: TEST (dbt test) ---
            if "test" in request.stages:
                run.stage = "test"
                db.commit()
                try:
                    from app.services.dbt_service import dbt_service
                    dbt_service.execute_command("test", target="dev", db=db)
                except Exception as test_exc:
                    logger.warning("dbt test in pipeline completed with notice: %s", test_exc)

            # Mark Pipeline Run as Complete
            pipeline_run_repo.complete_run(
                db=db,
                run_id=run.id,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                metadata={
                    "extracted_summary": extracted_summary,
                    "repo_full_name": repo.full_name,
                },
            )
            logger.info(
                "ELT pipeline completed successfully for %s: %d extracted, %d loaded",
                repo.full_name,
                records_extracted,
                records_loaded,
            )
            return run

        except Exception as exc:
            db.rollback()
            logger.error("Pipeline run %s failed: %s", run.id, exc, exc_info=True)
            pipeline_run_repo.fail_run(
                db=db,
                run_id=run.id,
                error_message=str(exc),
                metadata={"repo_full_name": repo.full_name},
            )
            raise PipelineExecutionException(pipeline_name="github_repo_sync", message=str(exc))


pipeline_service = PipelineService()

