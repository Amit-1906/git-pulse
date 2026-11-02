"""
GitPulse Enterprise Seed Service
Ensures production and preview environments (Vercel, local SQLite, fresh PostgreSQL)
immediately have rich, verified data for all 9 dashboard pages.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.raw_events import Commit, PullRequest, Issue
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.models.pipeline_run import PipelineRun
from app.models.extraction_job import ExtractionJob
from app.models.checkpoint import ExtractionCheckpoint
from app.models.operational import DataQualityResult

logger = logging.getLogger("gitpulse.seed")


def auto_seed_if_empty(db: Session) -> bool:
    """
    Checks if the database has any repository records.
    If empty, populates a rich multi-repository analytical dataset.
    Returns True if seeding occurred, False if existing data was preserved.
    """
    repo_count = db.scalar(select(func.count(Repository.id))) or 0
    if repo_count > 0:
        logger.info("Database already contains %d repositories. Skipping auto-seed.", repo_count)
        return False

    logger.info("Database is empty. Populating rich GitPulse enterprise demo records...")

    now = datetime.utcnow()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Repositories (3 high-profile engineering codebases)
    # ──────────────────────────────────────────────────────────────────────────
    repos_spec = [
        {
            "github_id": 101,
            "owner": "tiangolo",
            "name": "fastapi",
            "full_name": "tiangolo/fastapi",
            "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
            "html_url": "https://github.com/tiangolo/fastapi",
            "stargazers_count": 78400,
            "forks_count": 6500,
            "open_issues_count": 210,
            "watchers_count": 78400,
            "language": "Python",
            "is_active": True,
            "last_synced_at": now - timedelta(minutes=12),
        },
        {
            "github_id": 102,
            "owner": "pydantic",
            "name": "pydantic",
            "full_name": "pydantic/pydantic",
            "description": "Data validation and settings management using Python type hints",
            "html_url": "https://github.com/pydantic/pydantic",
            "stargazers_count": 22100,
            "forks_count": 1950,
            "open_issues_count": 145,
            "watchers_count": 22100,
            "language": "Python",
            "is_active": True,
            "last_synced_at": now - timedelta(minutes=24),
        },
        {
            "github_id": 103,
            "owner": "encode",
            "name": "starlette",
            "full_name": "encode/starlette",
            "description": "The little ASGI framework that shines. High performance ASGI toolkit.",
            "html_url": "https://github.com/encode/starlette",
            "stargazers_count": 11200,
            "forks_count": 1100,
            "open_issues_count": 65,
            "watchers_count": 11200,
            "language": "Python",
            "is_active": True,
            "last_synced_at": now - timedelta(minutes=36),
        },
    ]

    created_repos: List[Repository] = []
    for r_spec in repos_spec:
        repo = Repository(**r_spec)
        db.add(repo)
        created_repos.append(repo)
    db.commit()
    for repo in created_repos:
        db.refresh(repo)

    r_fastapi, r_pydantic, r_starlette = created_repos[0], created_repos[1], created_repos[2]

    # Contributors pool
    authors = [
        ("tiangolo", "tiangolo@fastapi.tiangolo.com"),
        ("samuelcolvin", "samuel@pydantic.dev"),
        ("dmontagu", "dmontagu@users.noreply.github.com"),
        ("Kludex", "marcelotryle@gmail.com"),
        ("adriangb", "adrian@pydantic.dev"),
        ("tomchristie", "tom@encode.io"),
        ("florimondmanca", "florimond@encode.io"),
        ("graingert", "graingert@gmail.com"),
    ]

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Commits (80 total across 3 repos with realistic time curves)
    # ──────────────────────────────────────────────────────────────────────────
    commit_messages = [
        "feat(core): optimize routing lookup tree using radix dispatch",
        "fix(validation): resolve union discriminator serialization in nested models",
        "perf(asgi): reduce per-request context manager allocation overhead",
        "docs(security): clarify OAuth2 token refresh grant implementation",
        "refactor(middleware): streamline CORS preflight header validation",
        "test(integration): add concurrency benchmarks for streaming endpoints",
        "feat(openapi): support custom OpenAPI schema extensions via operation kwargs",
        "fix(responses): ensure Content-Length header is set on empty 204 responses",
        "chore(deps): bump starlette dependency to 0.36.0",
        "feat(params): support Annotated syntax with multiple validation constraints",
        "fix(json): handle NaN and Infinity in JSONResponse without crashing",
        "perf(lifespan): accelerate startup hooks execution using asyncio.gather",
        "docs(tutorial): add enterprise background task orchestration guide",
        "fix(client): address connection pool exhaustion during rapid retries",
        "feat(security): add HTTP Bearer security scheme with automatic documentation",
    ]

    commit_count = 0
    for repo_idx, repo in enumerate([r_fastapi, r_pydantic, r_starlette]):
        commits_for_repo = 32 if repo_idx == 0 else (28 if repo_idx == 1 else 20)
        for i in range(commits_for_repo):
            commit_count += 1
            days_ago = 45 - int((i / float(commits_for_repo)) * 45)
            c_date = now - timedelta(days=days_ago, hours=(i * 3) % 24, minutes=(i * 7) % 60)
            author = authors[(i + repo_idx * 2) % len(authors)]
            msg = commit_messages[(i + repo_idx * 5) % len(commit_messages)]
            sha = f"c{repo_idx}{i:03x}" + "f" * 34

            adds = 12 + (i * 13) % 120
            dels = 2 + (i * 5) % 40
            tot = adds + dels

            cmt = Commit(
                repository_id=repo.id,
                sha=sha,
                author_name=author[0],
                author_email=author[1],
                author_date=c_date,
                committer_name="GitHub",
                committer_date=c_date,
                message=f"{msg} (#{100 + i})",
                additions=adds,
                deletions=dels,
                total_changes=tot,
                raw_payload={"sha": sha, "author": author[0], "repo": repo.full_name},
            )
            db.add(cmt)

            # Bronze raw commit
            raw_c = RawCommit(
                repository_id=repo.id,
                commit_sha=sha,
                raw_payload={"sha": sha, "author": author[0], "repo": repo.full_name},
                extracted_at=c_date,
                source_updated_at=c_date,
            )
            db.add(raw_c)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Pull Requests (24 across all 3 repos)
    # ──────────────────────────────────────────────────────────────────────────
    pr_data = [
        # (title, repo, is_merged, hours_to_merge, state, base, head)
        ("Support dependency injection overrides in nested scopes", r_fastapi, True, 6.5, "closed", "master", "feat/nested-scopes"),
        ("Add validation benchmark suite for Pydantic v2 core", r_pydantic, True, 22.0, "closed", "main", "perf/benchmarks"),
        ("Fix typing annotations for response_model parameter", r_fastapi, True, 3.2, "closed", "master", "fix/typing-model"),
        ("Upgrade Starlette compatibility to latest v0.36.0", r_fastapi, True, 14.5, "closed", "master", "chore/starlette-bump"),
        ("Add async background task failure telemetry hooks", r_starlette, False, None, "open", "master", "feat/bg-telemetry"),
        ("Improve documentation for WebSocket security headers", r_starlette, True, 42.0, "closed", "master", "docs/ws-security"),
        ("Refactor lifespan context manager initialization", r_starlette, False, None, "open", "master", "refactor/lifespan"),
        ("Fix multipart form data memory leak on Windows servers", r_fastapi, True, 11.0, "closed", "master", "fix/multipart-leak"),
        ("Speed up BaseModel serialization by 28% with Rust codegen", r_pydantic, True, 36.0, "closed", "main", "perf/rust-core"),
        ("Support recursive self-referencing generic models", r_pydantic, False, None, "open", "main", "feat/generic-recursive"),
        ("Add strict mode for datetime timezone validation", r_pydantic, True, 8.0, "closed", "main", "feat/strict-tz"),
        ("Reject invalid regex patterns during compile time", r_pydantic, True, 5.5, "closed", "main", "fix/regex-compile"),
        ("Implement zero-copy request body buffering for ASGI", r_starlette, True, 19.0, "closed", "master", "perf/zero-copy"),
        ("Support HTTP/2 server push stream cancellation", r_starlette, False, None, "closed", "master", "feat/h2-push"),
        ("Add middleware timing metrics header to server responses", r_fastapi, True, 7.5, "closed", "master", "feat/timing-hdr"),
        ("Fix path parameter regex parsing when slashes are escaped", r_fastapi, True, 4.0, "closed", "master", "fix/path-escape"),
        ("Add support for custom JSON decoders in Request.json()", r_starlette, True, 12.0, "closed", "master", "feat/custom-decoder"),
        ("Implement frozen dataclass coercion to pydantic models", r_pydantic, False, None, "open", "main", "feat/dataclass-coerce"),
        ("Fix CORS preflight handler caching headers on Firefox", r_fastapi, True, 16.0, "closed", "master", "fix/cors-firefox"),
        ("Improve error message clarity for missing required query params", r_fastapi, True, 2.5, "closed", "master", "docs/query-err"),
        ("Add async file upload spooling to disk for large files", r_starlette, False, None, "open", "master", "feat/spooling"),
        ("Support computed_field decorators with custom serializers", r_pydantic, True, 28.0, "closed", "main", "feat/computed-field"),
        ("Fix cookie samesite=none attribute serialization", r_starlette, True, 9.0, "closed", "master", "fix/cookie-samesite"),
        ("Deprecate legacy regex query parameter validators gracefully", r_fastapi, False, None, "closed", "master", "chore/deprecate-regex"),
    ]

    for idx, (title, repo, is_merged, hrs_to_merge, state, base_b, head_b) in enumerate(pr_data):
        days_ago = 30 - idx
        created = now - timedelta(days=days_ago, hours=4)
        merged = created + timedelta(hours=hrs_to_merge) if is_merged and hrs_to_merge else None
        closed = merged if is_merged else (created + timedelta(days=2) if state == "closed" else None)
        author = authors[idx % len(authors)][0]

        pr = PullRequest(
            repository_id=repo.id,
            github_id=4000 + idx,
            number=600 + idx,
            title=title,
            body=f"Production PR resolving issue #{700 + idx}. Detailed engineering implementation included.",
            state=state,
            is_merged=is_merged,
            user_login=author,
            base_branch=base_b,
            head_branch=head_b,
            comments_count=2 + (idx * 3) % 11,
            additions=35 + (idx * 27) % 250,
            deletions=5 + (idx * 9) % 80,
            changed_files=1 + (idx % 6),
            created_at_gh=created,
            merged_at_gh=merged,
            closed_at_gh=closed,
            raw_payload={"number": 600 + idx, "title": title, "repo": repo.full_name},
        )
        db.add(pr)

        raw_pr = RawPullRequest(
            repository_id=repo.id,
            github_pr_id=4000 + idx,
            pr_number=600 + idx,
            raw_payload={"number": 600 + idx, "title": title, "repo": repo.full_name},
            extracted_at=created,
            source_updated_at=merged or closed or created,
        )
        db.add(raw_pr)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Issues (28 across all 3 repos with varied labels, categories, resolution times)
    # ──────────────────────────────────────────────────────────────────────────
    issues_data = [
        # (title, repo, state, res_days, labels, comments)
        ("Request body streaming timeout on slow satellite connections", r_fastapi, "closed", 3.2, ["bug", "network"], 5),
        ("Memory leak when using custom APIRoute subclass in nested routers", r_fastapi, "closed", 14.5, ["bug", "performance"], 12),
        ("OpenAPI schema missing custom response header definitions", r_fastapi, "open", None, ["enhancement", "openapi"], 4),
        ("Clarify exception handler precedence in multi-tenant documentation", r_fastapi, "closed", 1.8, ["documentation"], 2),
        ("Add support for unix domain sockets on Linux microservices", r_fastapi, "open", None, ["feature request", "platform"], 8),
        ("CORS preflight request failing on Safari 17 due to credential header", r_fastapi, "closed", 6.0, ["bug", "security"], 9),
        ("Field default factory executed multiple times during schema generation", r_pydantic, "closed", 2.4, ["bug", "core"], 7),
        ("Support recursive model validation without recursion depth limit crash", r_pydantic, "open", None, ["enhancement", "performance"], 15),
        ("Pydantic custom validator not called when field is None and Optional", r_pydantic, "closed", 0.9, ["bug", "validation"], 4),
        ("Improve JSON Schema generation for IPv4Network and IPv6Network fields", r_pydantic, "closed", 4.1, ["enhancement", "documentation"], 3),
        ("Performance regression in dict() serialization with 10k rows", r_pydantic, "closed", 8.5, ["performance", "bug"], 19),
        ("Support discriminators with nested tagged unions", r_pydantic, "open", None, ["feature request"], 11),
        ("WebSocket disconnect event not propagated to middleware cleanup stack", r_starlette, "closed", 2.1, ["bug", "websocket"], 6),
        ("StaticFiles directory traversal vulnerability on Windows drive roots", r_starlette, "closed", 0.7, ["security", "critical"], 14),
        ("Add HTTP/3 QUIC protocol listener experiment", r_starlette, "open", None, ["feature request", "network"], 22),
        ("BackgroundTasks exceptions swallowed silently without logging", r_starlette, "closed", 3.6, ["bug", "telemetry"], 8),
        ("SessionMiddleware cookie domain attribute ignored on localhost ports", r_starlette, "closed", 1.2, ["bug", "security"], 5),
        ("Support streaming response cancellation when client drops connection", r_starlette, "open", None, ["enhancement", "performance"], 10),
        ("Path parameter validation regex fails with non-ASCII characters", r_fastapi, "closed", 5.2, ["bug", "i18n"], 6),
        ("Support OAuth2 password flow with asymmetric RS256 token verification", r_fastapi, "open", None, ["security", "enhancement"], 13),
        ("Add auto-generated curl command examples in Swagger UI /docs", r_fastapi, "open", None, ["documentation", "ui"], 7),
        ("Generic model inheritance drops field description metadata", r_pydantic, "closed", 3.8, ["bug", "metadata"], 4),
        ("Validate Decimal fields with arbitrary precision without float cast", r_pydantic, "open", None, ["enhancement", "data-types"], 5),
        ("TypeAdapter.validate_json fails on raw byte arrays with UTF-16 BOM", r_pydantic, "closed", 1.5, ["bug", "encoding"], 3),
        ("GZipMiddleware fails to compress SSE EventSource text/event-stream", r_starlette, "closed", 4.8, ["bug", "streaming"], 8),
        ("UploadFile.seek(0) causes OSError on temporary spool files over 10MB", r_starlette, "open", None, ["bug", "storage"], 9),
        ("Add official OpenTelemetry span instrumentation middleware", r_fastapi, "open", None, ["enhancement", "telemetry"], 17),
        ("Dependency overrides in TestClient leak across concurrent async tests", r_fastapi, "closed", 2.9, ["bug", "testing"], 11),
    ]

    for idx, (title, repo, state, res_days, labels, comments) in enumerate(issues_data):
        days_ago = 40 - int((idx / float(len(issues_data))) * 40)
        created = now - timedelta(days=days_ago, hours=(idx * 2) % 18)
        closed = created + timedelta(days=res_days) if res_days and state == "closed" else None
        author = authors[(idx + 1) % len(authors)][0]

        iss = Issue(
            repository_id=repo.id,
            github_id=5000 + idx,
            number=700 + idx,
            title=title,
            body=f"Production issue report regarding {title}. Reproduction script provided by community.",
            state=state,
            user_login=author,
            comments_count=comments,
            labels=labels,
            created_at_gh=created,
            closed_at_gh=closed,
            raw_payload={"number": 700 + idx, "title": title, "repo": repo.full_name, "labels": labels},
        )
        db.add(iss)

        raw_iss = RawIssue(
            repository_id=repo.id,
            github_issue_id=5000 + idx,
            issue_number=700 + idx,
            raw_payload={"number": 700 + idx, "title": title, "repo": repo.full_name, "labels": labels},
            extracted_at=created,
            source_updated_at=closed or created,
        )
        db.add(raw_iss)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Pipeline Runs & Extraction Jobs
    # ──────────────────────────────────────────────────────────────────────────
    for idx, repo in enumerate([r_fastapi, r_pydantic, r_starlette]):
        for run_idx in range(4):
            started = now - timedelta(hours=(12 - run_idx * 3) + idx * 8)
            dur = 9.4 + (run_idx * 3.1) + (idx * 2.2)
            recs = 40 + (run_idx * 15) + (idx * 10)

            run = PipelineRun(
                repository_id=repo.id,
                pipeline_name=f"elt_{repo.name}_full_sync",
                stage="transform",
                status="completed",
                started_at=started,
                finished_at=started + timedelta(seconds=dur),
                duration_seconds=dur,
                records_extracted=recs,
                records_loaded=recs,
            )
            db.add(run)

            job = ExtractionJob(
                job_id=f"job_{repo.name}_{run_idx:02d}",
                repository_id=repo.id,
                repository_full_name=repo.full_name,
                status="COMPLETED",
                resources=["repository", "commits", "pull_requests", "issues"],
                incremental=run_idx > 0,
                records_extracted={"commits": 25, "pull_requests": 8, "issues": 9, "repository": 1},
                records_loaded={"commits": 25, "pull_requests": 8, "issues": 9, "repository": 1},
                started_at=started,
                finished_at=started + timedelta(seconds=dur),
                duration_seconds=dur,
            )
            db.add(job)

        cp = ExtractionCheckpoint(
            repository_id=repo.id,
            resource_type="commits",
            last_checkpoint_timestamp=now - timedelta(hours=2),
            last_record_id=f"c{idx}000" + "f" * 34,
        )
        db.add(cp)

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Data Quality Results (dbt test assertions)
    # ──────────────────────────────────────────────────────────────────────────
    quality_assertions = [
        ("unique:dim_repositories.full_name", "repositories", True, 0, r_fastapi),
        ("not_null:fct_commits.commit_sha", "commits", True, 0, r_fastapi),
        ("accepted_values:fct_pull_requests.state", "pull_requests", True, 0, r_fastapi),
        ("relationships:fct_issues.repository_id", "issues", True, 0, r_fastapi),
        ("not_null:dim_contributors.author_login", "contributors", True, 0, r_pydantic),
        ("unique:fct_pull_requests.github_pr_id", "pull_requests", True, 0, r_pydantic),
        ("assert_closed_timestamp_validity", "issues", True, 0, r_pydantic),
        ("assert_commit_changes_non_negative", "commits", True, 0, r_starlette),
        ("unique:fct_issues.github_issue_id", "issues", True, 0, r_starlette),
        ("accepted_values:fct_commits.repository_id", "commits", True, 0, r_starlette),
    ]

    for rule_name, res_type, passed, fails, target_repo in quality_assertions:
        dqr = DataQualityResult(
            repository_id=target_repo.id,
            job_id="dbt_test_suite",
            source="dbt",
            rule_name=rule_name,
            resource_type=res_type,
            passed=passed,
            severity="warn" if fails > 0 else "pass",
            failure_count=fails,
            evaluated_at=now - timedelta(hours=1),
        )
        db.add(dqr)

    db.commit()
    logger.info("Successfully seeded 3 repositories, 80 commits, 24 PRs, 28 issues, 12 runs, 10 quality checks!")
    return True

