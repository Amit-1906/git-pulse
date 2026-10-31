#!/usr/bin/env python3
"""
CLI Utility to execute the GitPulse ELT pipeline for a repository.
"""
import argparse
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.repositories.repository_repo import repository_repo
from app.services.pipeline_service import pipeline_service
from app.schemas.pipeline import PipelineTriggerRequest


def main():
    parser = argparse.ArgumentParser(description="GitPulse Pipeline CLI Runner")
    parser.add_argument("--repo", required=True, help="Full repository name (e.g. tiangolo/fastapi) or ID")
    parser.add_argument("--max-commits", type=int, default=30, help="Max commits to extract")
    parser.add_argument("--max-pulls", type=int, default=30, help="Max PRs to extract")
    parser.add_argument("--max-issues", type=int, default=30, help="Max issues to extract")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Resolve target repo
        if args.repo.isdigit():
            repo = repository_repo.get(db, int(args.repo))
        else:
            repo = repository_repo.get_by_full_name(db, args.repo)

        if not repo:
            print(f"Error: Repository '{args.repo}' not found in database. Please register it first.")
            sys.exit(1)

        print(f"Executing ELT pipeline for: {repo.full_name} (id={repo.id})")
        req = PipelineTriggerRequest(
            repository_id=repo.id,
            max_commits=args.max_commits,
            max_pulls=args.max_pulls,
            max_issues=args.max_issues,
        )
        run = pipeline_service.run_pipeline(db, req)
        print(f"✓ Pipeline run #{run.id} finished with status: {run.status.upper()}")
        print(f"  Records extracted: {run.records_extracted}")
        print(f"  Records loaded:    {run.records_loaded}")
        print(f"  Duration:          {run.duration_seconds}s")
    except Exception as exc:
        print(f"Pipeline failed: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

