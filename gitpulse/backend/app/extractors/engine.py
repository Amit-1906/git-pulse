import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.exceptions import (
    GitPulseException,
    EntityNotFoundException,
    EntityAlreadyExistsException,
)
from app.extractors.client import GitHubClient
from app.extractors.repository_extractor import RepositoryExtractor
from app.extractors.commits_extractor import CommitsExtractor
from app.extractors.issues_extractor import IssuesExtractor
from app.extractors.pull_requests_extractor import PullRequestsExtractor
from app.models.repository import Repository
from app.models.raw_events import RawEvent, Commit, PullRequest, Issue
from app.models.extraction_job import ExtractionJob
from app.models.checkpoint import ExtractionCheckpoint

# Bronze raw-table repositories
from app.repositories.raw_storage_repo import (
    raw_repository_repo,
    raw_commit_repo,
    raw_issue_repo,
    raw_pull_request_repo,
)
from app.repositories.operational_repo import extraction_log_repo

logger = logging.getLogger("gitpulse.extractor.engine")


class ExtractionEngine:
    """
    Production-grade GitHub Extraction Engine orchestrating resource extractors,
    checkpoint management, job telemetry, concurrency locking, and partial failure recovery.
    """

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()
        self.repo_extractor = RepositoryExtractor(self.client)
        self.commits_extractor = CommitsExtractor(self.client)
        self.issues_extractor = IssuesExtractor(self.client)
        self.prs_extractor = PullRequestsExtractor(self.client)

    def _generate_job_id(self) -> str:
        return f"job_{uuid.uuid4().hex[:12]}"

    def create_job(
        self,
        db: Session,
        repository_full_name: str,
        resources: Optional[List[str]] = None,
        incremental: bool = True,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> ExtractionJob:
        full_name = repository_full_name.lower().strip()
        all_resources = ["repository", "commits", "pull_requests", "issues"]
        target_resources = [r for r in (resources or all_resources) if r in all_resources]

        # 1. Concurrency Check: Prevent overlapping duplicate running jobs for same repository
        active_job = db.scalar(
            select(ExtractionJob).where(
                ExtractionJob.repository_full_name == full_name,
                ExtractionJob.status.in_(["PENDING", "RUNNING"]),
            )
        )
        if active_job:
            raise GitPulseException(
                message=f"An active extraction job '{active_job.job_id}' is already running for {full_name}.",
                code="DUPLICATE_JOB_IN_PROGRESS",
                status_code=409,
                details={"active_job_id": active_job.job_id, "status": active_job.status},
            )

        # 2. Resolve repository entity if already tracked
        repo = db.scalar(select(Repository).where(Repository.full_name == full_name))

        job = ExtractionJob(
            job_id=self._generate_job_id(),
            repository_id=repo.id if repo else None,
            repository_full_name=full_name,
            status="PENDING",
            resources=target_resources,
            incremental=incremental,
            since=since,
            until=until,
            records_extracted={r: 0 for r in target_resources},
            records_loaded={r: 0 for r in target_resources},
            error_details={},
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info("Created extraction job %s for %s (resources: %s)", job.job_id, full_name, target_resources)
        return job

    def get_checkpoint(self, db: Session, repo_id: int, resource_type: str) -> Optional[ExtractionCheckpoint]:
        stmt = select(ExtractionCheckpoint).where(
            ExtractionCheckpoint.repository_id == repo_id,
            ExtractionCheckpoint.resource_type == resource_type,
        )
        return db.scalar(stmt)

    def set_checkpoint(
        self,
        db: Session,
        repo_id: int,
        resource_type: str,
        timestamp: datetime,
        last_id: Optional[str] = None,
    ) -> ExtractionCheckpoint:
        cp = self.get_checkpoint(db, repo_id, resource_type)
        if not cp:
            cp = ExtractionCheckpoint(
                repository_id=repo_id,
                resource_type=resource_type,
                last_checkpoint_timestamp=timestamp,
                last_record_id=last_id,
            )
            db.add(cp)
        else:
            if not cp.last_checkpoint_timestamp or timestamp > cp.last_checkpoint_timestamp:
                cp.last_checkpoint_timestamp = timestamp
            if last_id:
                cp.last_record_id = last_id
        db.commit()
        db.refresh(cp)
        return cp

    def cancel_job(self, db: Session, job_id: str) -> ExtractionJob:
        job = db.scalar(select(ExtractionJob).where(ExtractionJob.job_id == job_id))
        if not job:
            raise EntityNotFoundException("ExtractionJob", job_id)
        if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
            return job
        job.cancel_requested = True
        job.status = "CANCELLED"
        job.finished_at = datetime.utcnow()
        if job.started_at:
            job.duration_seconds = round((job.finished_at - job.started_at).total_seconds(), 2)
        db.commit()
        db.refresh(job)
        logger.info("Extraction job %s marked as CANCELLED", job_id)
        return job

    def run_job(self, db: Session, job_id: str, per_page: int = 100, max_pages: Optional[int] = None) -> ExtractionJob:
        job = db.scalar(select(ExtractionJob).where(ExtractionJob.job_id == job_id))
        if not job:
            raise EntityNotFoundException("ExtractionJob", job_id)

        job.status = "RUNNING"
        job.started_at = datetime.utcnow()
        db.commit()

        start_time = time.perf_counter()
        owner, repo_name = [p.strip() for p in job.repository_full_name.split("/") if p.strip()]

        records_extracted_map: Dict[str, int] = {}
        records_loaded_map: Dict[str, int] = {}
        error_details_map: Dict[str, str] = {}

        repo: Optional[Repository] = None
        if job.repository_id:
            repo = db.get(Repository, job.repository_id)

        try:
            # -------------------------------------------------------------
            # Stage A: Repository Information
            # -------------------------------------------------------------
            if "repository" in job.resources:
                if job.cancel_requested:
                    job.status = "CANCELLED"
                    db.commit()
                    return job
                try:
                    logger.info("[%s] Extracting repository metadata...", job.job_id)
                    repo_meta = self.repo_extractor.extract_metadata(owner, repo_name)
                    records_extracted_map["repository"] = 1

                    # Persist Bronze Raw Event
                    raw_event = RawEvent(
                        repository_id=repo.id if repo else 0,
                        event_type="repository",
                        payload=repo_meta["raw_payload"],
                        status="processed",
                    )

                    # ── Bronze: dedicated raw_repositories table ──────────
                    _src_updated = repo_meta.get("updated_at_gh")
                    raw_repository_repo.upsert(
                        db,
                        github_repo_id=repo_meta["github_id"],
                        full_name=repo_meta["full_name"],
                        raw_payload=repo_meta["raw_payload"],
                        source_endpoint="/repos/{owner}/{repo}",
                        extracted_at=datetime.utcnow(),
                        source_updated_at=_src_updated,
                        repository_id=repo.id if repo else None,
                    )

                    # Upsert Silver Repository
                    if not repo:
                        repo = db.scalar(select(Repository).where(Repository.full_name == job.repository_full_name))
                    if not repo:
                        repo = Repository(
                            github_id=repo_meta["github_id"],
                            owner=repo_meta["owner"],
                            name=repo_meta["name"],
                            full_name=repo_meta["full_name"],
                            description=repo_meta["description"],
                            html_url=repo_meta["html_url"],
                            default_branch=repo_meta["default_branch"],
                            visibility=repo_meta["visibility"],
                            stargazers_count=repo_meta["stargazers_count"],
                            forks_count=repo_meta["forks_count"],
                            open_issues_count=repo_meta["open_issues_count"],
                            watchers_count=repo_meta["watchers_count"],
                            language=repo_meta["language"],
                            created_at_gh=repo_meta["created_at_gh"],
                            updated_at_gh=repo_meta["updated_at_gh"],
                            last_synced_at=datetime.utcnow(),
                            repo_metadata=repo_meta["raw_payload"],
                        )
                        db.add(repo)
                        db.commit()
                        db.refresh(repo)
                        job.repository_id = repo.id
                    else:
                        repo.stargazers_count = repo_meta["stargazers_count"]
                        repo.forks_count = repo_meta["forks_count"]
                        repo.open_issues_count = repo_meta["open_issues_count"]
                        repo.watchers_count = repo_meta["watchers_count"]
                        repo.language = repo_meta["language"]
                        repo.visibility = repo_meta["visibility"]
                        repo.updated_at_gh = repo_meta["updated_at_gh"]
                        repo.last_synced_at = datetime.utcnow()
                        repo.repo_metadata = repo_meta["raw_payload"]
                        db.commit()

                    raw_event.repository_id = repo.id
                    db.add(raw_event)
                    db.commit()
                    records_loaded_map["repository"] = 1
                except Exception as exc:
                    logger.error("[%s] Repository extraction failed: %s", job.job_id, exc)
                    error_details_map["repository"] = str(exc)

            if not repo:
                repo = db.scalar(select(Repository).where(Repository.full_name == job.repository_full_name))
            if not repo:
                raise EntityNotFoundException("Repository", job.repository_full_name)

            # -------------------------------------------------------------
            # Stage B: Commits
            # -------------------------------------------------------------
            if "commits" in job.resources:
                if job.cancel_requested:
                    job.status = "CANCELLED"
                    db.commit()
                    return job
                try:
                    logger.info("[%s] Extracting commits...", job.job_id)
                    commits_since = job.since
                    if job.incremental and not commits_since:
                        cp = self.get_checkpoint(db, repo.id, "commits")
                        if cp and cp.last_checkpoint_timestamp:
                            commits_since = cp.last_checkpoint_timestamp

                    commits_data = self.commits_extractor.extract(
                        owner=owner,
                        repo=repo_name,
                        since=commits_since,
                        until=job.until,
                        per_page=per_page,
                        max_pages=max_pages,
                    )
                    records_extracted_map["commits"] = len(commits_data)

                    loaded_commits = 0
                    max_commit_date: Optional[datetime] = None
                    last_sha: Optional[str] = None

                    # Prepare Bronze batch records
                    bronze_commit_records: List[Dict[str, Any]] = []

                    for c in commits_data:
                        sha = c["sha"]
                        # Bronze Raw Event (legacy table)
                        db.add(
                            RawEvent(
                                repository_id=repo.id,
                                event_type="commit",
                                payload=c["raw_payload"],
                                status="processed",
                            )
                        )

                        # Bronze: dedicated raw_commits record
                        bronze_commit_records.append({
                            "commit_sha": sha,
                            "raw_payload": c["raw_payload"],
                            "source_updated_at": c.get("author_date") or c.get("committer_date"),
                        })

                        # Silver entity with duplicate prevention by SHA
                        existing = db.scalar(select(Commit).where(Commit.sha == sha))
                        if not existing:
                            commit_obj = Commit(
                                repository_id=repo.id,
                                sha=sha,
                                author_name=c["author_name"],
                                author_email=c["author_email"],
                                author_date=c["author_date"],
                                committer_name=c["committer_name"],
                                committer_date=c["committer_date"],
                                message=c["message"],
                                parent_shas=c["parent_shas"],
                                additions=c["additions"],
                                deletions=c["deletions"],
                                total_changes=c["total_changes"],
                                raw_payload=c["raw_payload"],
                            )
                            db.add(commit_obj)
                            loaded_commits += 1

                        c_date = c["author_date"] or c["committer_date"]
                        if c_date:
                            if not max_commit_date or c_date > max_commit_date:
                                max_commit_date = c_date
                                last_sha = sha

                    db.commit()
                    records_loaded_map["commits"] = loaded_commits

                    # Bronze batch upsert into raw_commits
                    if bronze_commit_records:
                        raw_commit_repo.bulk_upsert(
                            db,
                            repository_id=repo.id,
                            records=bronze_commit_records,
                            extracted_at=datetime.utcnow(),
                        )

                    if max_commit_date:
                        self.set_checkpoint(db, repo.id, "commits", max_commit_date, last_sha)
                except Exception as exc:
                    logger.error("[%s] Commits extraction failed: %s", job.job_id, exc)
                    error_details_map["commits"] = str(exc)

            # -------------------------------------------------------------
            # Stage C: Issues (excluding Pull Requests)
            # -------------------------------------------------------------
            if "issues" in job.resources:
                if job.cancel_requested:
                    job.status = "CANCELLED"
                    db.commit()
                    return job
                try:
                    logger.info("[%s] Extracting issues...", job.job_id)
                    issues_since = job.since
                    if job.incremental and not issues_since:
                        cp = self.get_checkpoint(db, repo.id, "issues")
                        if cp and cp.last_checkpoint_timestamp:
                            issues_since = cp.last_checkpoint_timestamp

                    issues_data = self.issues_extractor.extract(
                        owner=owner,
                        repo=repo_name,
                        since=issues_since,
                        until=job.until,
                        per_page=per_page,
                        max_pages=max_pages,
                    )
                    records_extracted_map["issues"] = len(issues_data)

                    loaded_issues = 0
                    max_issue_updated: Optional[datetime] = None

                    # Bronze batch records
                    bronze_issue_records: List[Dict[str, Any]] = []

                    for iss in issues_data:
                        gh_id = iss["github_id"]
                        # Bronze Raw Event
                        db.add(
                            RawEvent(
                                repository_id=repo.id,
                                event_type="issue",
                                payload=iss["raw_payload"],
                                status="processed",
                            )
                        )

                        # Bronze: dedicated raw_issues record
                        bronze_issue_records.append({
                            "github_issue_id": gh_id,
                            "issue_number": iss["number"],
                            "raw_payload": iss["raw_payload"],
                            "source_updated_at": iss.get("updated_at_gh"),
                        })

                        # Silver entity with duplicate prevention / upsert by github_id
                        existing_issue = db.scalar(select(Issue).where(Issue.github_id == gh_id))
                        if not existing_issue:
                            issue_obj = Issue(
                                repository_id=repo.id,
                                github_id=gh_id,
                                number=iss["number"],
                                title=iss["title"],
                                body=iss["body"],
                                state=iss["state"],
                                user_login=iss["user_login"],
                                assignees=iss["assignees"],
                                labels=iss["labels"],
                                comments_count=iss["comments_count"],
                                created_at_gh=iss["created_at_gh"] or datetime.utcnow(),
                                updated_at_gh=iss["updated_at_gh"],
                                closed_at_gh=iss["closed_at_gh"],
                                raw_payload=iss["raw_payload"],
                            )
                            db.add(issue_obj)
                            loaded_issues += 1
                        else:
                            existing_issue.title = iss["title"]
                            existing_issue.body = iss["body"]
                            existing_issue.state = iss["state"]
                            existing_issue.assignees = iss["assignees"]
                            existing_issue.labels = iss["labels"]
                            existing_issue.comments_count = iss["comments_count"]
                            existing_issue.updated_at_gh = iss["updated_at_gh"]
                            existing_issue.closed_at_gh = iss["closed_at_gh"]

                        if iss["updated_at_gh"]:
                            if not max_issue_updated or iss["updated_at_gh"] > max_issue_updated:
                                max_issue_updated = iss["updated_at_gh"]

                    db.commit()
                    records_loaded_map["issues"] = loaded_issues

                    # Bronze batch upsert into raw_issues
                    if bronze_issue_records:
                        raw_issue_repo.bulk_upsert(
                            db,
                            repository_id=repo.id,
                            records=bronze_issue_records,
                            extracted_at=datetime.utcnow(),
                        )

                    if max_issue_updated:
                        self.set_checkpoint(db, repo.id, "issues", max_issue_updated)
                except Exception as exc:
                    logger.error("[%s] Issues extraction failed: %s", job.job_id, exc)
                    error_details_map["issues"] = str(exc)

            # -------------------------------------------------------------
            # Stage D: Pull Requests
            # -------------------------------------------------------------
            if "pull_requests" in job.resources:
                if job.cancel_requested:
                    job.status = "CANCELLED"
                    db.commit()
                    return job
                try:
                    logger.info("[%s] Extracting pull requests...", job.job_id)
                    prs_since = job.since
                    if job.incremental and not prs_since:
                        cp = self.get_checkpoint(db, repo.id, "pull_requests")
                        if cp and cp.last_checkpoint_timestamp:
                            prs_since = cp.last_checkpoint_timestamp

                    prs_data = self.prs_extractor.extract(
                        owner=owner,
                        repo=repo_name,
                        since=prs_since,
                        until=job.until,
                        per_page=per_page,
                        max_pages=max_pages,
                    )
                    records_extracted_map["pull_requests"] = len(prs_data)

                    loaded_prs = 0
                    max_pr_updated: Optional[datetime] = None

                    # Bronze batch records
                    bronze_pr_records: List[Dict[str, Any]] = []

                    for pr in prs_data:
                        gh_id = pr["github_id"]
                        # Bronze Raw Event
                        db.add(
                            RawEvent(
                                repository_id=repo.id,
                                event_type="pull_request",
                                payload=pr["raw_payload"],
                                status="processed",
                            )
                        )

                        # Bronze: dedicated raw_pull_requests record
                        bronze_pr_records.append({
                            "github_pr_id": gh_id,
                            "pr_number": pr["number"],
                            "raw_payload": pr["raw_payload"],
                            "source_updated_at": pr.get("updated_at_gh"),
                        })

                        # Silver entity with duplicate prevention / upsert by github_id
                        existing_pr = db.scalar(select(PullRequest).where(PullRequest.github_id == gh_id))
                        if not existing_pr:
                            pr_obj = PullRequest(
                                repository_id=repo.id,
                                github_id=gh_id,
                                number=pr["number"],
                                title=pr["title"],
                                body=pr["body"],
                                state=pr["state"],
                                user_login=pr["user_login"],
                                base_branch=pr["base_branch"],
                                head_branch=pr["head_branch"],
                                is_merged=pr["is_merged"],
                                comments_count=pr["comments_count"],
                                additions=pr["additions"],
                                deletions=pr["deletions"],
                                changed_files=pr["changed_files"],
                                created_at_gh=pr["created_at_gh"] or datetime.utcnow(),
                                updated_at_gh=pr["updated_at_gh"],
                                closed_at_gh=pr["closed_at_gh"],
                                merged_at_gh=pr["merged_at_gh"],
                                raw_payload=pr["raw_payload"],
                            )
                            db.add(pr_obj)
                            loaded_prs += 1
                        else:
                            existing_pr.title = pr["title"]
                            existing_pr.body = pr["body"]
                            existing_pr.state = pr["state"]
                            existing_pr.is_merged = pr["is_merged"]
                            existing_pr.base_branch = pr["base_branch"]
                            existing_pr.head_branch = pr["head_branch"]
                            existing_pr.comments_count = pr["comments_count"]
                            existing_pr.updated_at_gh = pr["updated_at_gh"]
                            existing_pr.closed_at_gh = pr["closed_at_gh"]
                            existing_pr.merged_at_gh = pr["merged_at_gh"]

                        if pr["updated_at_gh"]:
                            if not max_pr_updated or pr["updated_at_gh"] > max_pr_updated:
                                max_pr_updated = pr["updated_at_gh"]

                    db.commit()
                    records_loaded_map["pull_requests"] = loaded_prs

                    # Bronze batch upsert into raw_pull_requests
                    if bronze_pr_records:
                        raw_pull_request_repo.bulk_upsert(
                            db,
                            repository_id=repo.id,
                            records=bronze_pr_records,
                            extracted_at=datetime.utcnow(),
                        )

                    if max_pr_updated:
                        self.set_checkpoint(db, repo.id, "pull_requests", max_pr_updated)
                except Exception as exc:
                    logger.error("[%s] Pull Requests extraction failed: %s", job.job_id, exc)
                    error_details_map["pull_requests"] = str(exc)

            # Finalize Job Telemetry and State
            job.finished_at = datetime.utcnow()
            job.duration_seconds = round((time.perf_counter() - start_time), 2)
            job.records_extracted = records_extracted_map
            job.records_loaded = records_loaded_map
            job.error_details = error_details_map

            total_requested = len(job.resources)
            failed_count = len(error_details_map)

            if failed_count == 0:
                job.status = "COMPLETED"
                job.error_message = None
            elif failed_count < total_requested:
                job.status = "PARTIAL_SUCCESS"
                job.error_message = f"Completed with partial errors in: {list(error_details_map.keys())}"
            else:
                job.status = "FAILED"
                job.error_message = "; ".join(f"{k}: {v}" for k, v in error_details_map.items())

            db.commit()
            db.refresh(job)
            logger.info("Extraction job %s ended with status %s in %.2fs", job.job_id, job.status, job.duration_seconds)
            return job

        except Exception as global_exc:
            db.rollback()
            job.status = "FAILED"
            job.finished_at = datetime.utcnow()
            job.duration_seconds = round((time.perf_counter() - start_time), 2)
            job.error_message = str(global_exc)
            db.commit()
            db.refresh(job)
            logger.error("Global failure during extraction job %s: %s", job.job_id, global_exc, exc_info=True)
            return job


extraction_engine = ExtractionEngine()

