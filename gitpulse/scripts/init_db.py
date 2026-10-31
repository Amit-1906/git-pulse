#!/usr/bin/env python3
"""
Database Initialization Script for GitPulse.
Creates relational tables and seeds initial starter repositories.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import app.models  # Registers all declarative tables on Base.metadata
from app.database import engine, Base, SessionLocal, check_db_health
from app.services.repository_service import repository_service
from app.schemas.repository import RepositoryCreate


def main():
    print("=" * 60)
    print("GitPulse Database Initialization Utility")
    print("=" * 60)

    # 1. Connectivity test
    health = check_db_health(engine)
    print(f"Connectivity status: {health['status']} ({health['dialect']})")

    # 2. Table Creation
    print("Creating tables in target database...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")

    # 3. Seed Starter Repositories if database is reachable
    if health.get("connected"):
        db = SessionLocal()
        try:
            starter_repos = [
                "tiangolo/fastapi",
                "streamlit/streamlit",
                "dbt-labs/dbt-core",
            ]
            print("\nSeeding starter repositories:")
            for repo_name in starter_repos:
                repo_in = RepositoryCreate(full_name=repo_name, fetch_initial_metadata=False)
                repo = repository_service.register_repository(db, repo_in)
                print(f"  [OK] {repo.full_name} (id={repo.id})")
            print("\n[OK] Database initialization completed successfully!")
        finally:
            db.close()
    else:
        print("\nNote: Database offline; schema declared and ready for PostgreSQL connection.")


if __name__ == "__main__":
    main()
