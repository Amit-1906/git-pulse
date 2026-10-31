#!/usr/bin/env python3
"""
Lightweight, Zero-Dependency Database Migration Runner for GitPulse.

Features:
- Discovers SQL migration files in order (e.g. 001_..., 002_...).
- Records applied revisions in a `schema_migrations` tracking table.
- Executes migrations inside a database transaction.
- Dialect-adaptive: supports PostgreSQL (native JSONB/GIN) and SQLite (testing).
- CLI args: supports --db-url, --dry-run, and graceful offline detection.
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text

# Add backend directory to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import get_settings
from app.database import Base, check_db_health, create_db_engine, engine as default_engine


def run_migrations(target_engine=None, dry_run=False):
    engine = target_engine or default_engine
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))

    dialect_name = engine.dialect.name
    print("=" * 60)
    print(f"GitPulse Database Migration Engine")
    print(f"Target dialect: {dialect_name}")
    print(f"Target URL:     {engine.url}")
    print("=" * 60)

    # 1. Health check before attempting connection
    health = check_db_health(engine)
    if not health.get("connected"):
        print(f"\n[ERROR] Database is unreachable at {engine.url}")
        print(f"Details: {health.get('error', 'offline')}")
        print("Please start PostgreSQL (e.g., 'docker-compose up -d db') and rerun.")
        return False

    if dry_run:
        print(f"\n[DRY RUN] Discovered {len(sql_files)} migration files:")
        for f in sql_files:
            print(f"  - {f.name}")
        return True

    with engine.connect() as conn:
        # Create migrations tracking table if not present
        if dialect_name == "postgresql":
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) PRIMARY KEY,
                    applied_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
                );
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
        conn.commit()

        # Query applied revisions
        result = conn.execute(text("SELECT version FROM schema_migrations"))
        applied_versions = {row[0] for row in result.fetchall()}

        for sql_file in sql_files:
            version_name = sql_file.name
            if version_name in applied_versions:
                print(f"  [SKIPPED] {version_name} (already applied)")
                continue

            print(f"  [APPLYING] {version_name} ...")
            sql_content = sql_file.read_text(encoding="utf-8")

            # In SQLite test environments, convert PostgreSQL-specific syntax
            if dialect_name != "postgresql":
                # For non-Postgres, SQLAlchemy metadata creation is the safest path
                Base.metadata.create_all(bind=engine)
                conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:ver)"),
                    {"ver": version_name},
                )
                conn.commit()
                print(f"  [OK] {version_name} applied via SQLAlchemy metadata fallback.")
                continue

            # In PostgreSQL: execute exact SQL script in transaction
            trans = conn.begin()
            try:
                conn.execute(text(sql_content))
                conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:ver)"),
                    {"ver": version_name},
                )
                trans.commit()
                print(f"  [OK] {version_name} applied successfully.")
            except Exception as e:
                trans.rollback()
                print(f"  [ERROR] Migration {version_name} failed: {e}")
                raise e

    print("\n[OK] All pending migrations processed successfully.\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitPulse Database Migration Tool")
    parser.add_argument("--db-url", type=str, default=None, help="Custom database connection URL")
    parser.add_argument("--dry-run", action="store_true", help="List migrations without executing")
    args = parser.parse_args()

    custom_engine = create_db_engine(args.db_url) if args.db_url else None
    run_migrations(target_engine=custom_engine, dry_run=args.dry_run)
