# Database Migrations (Alembic)

GitPulse database migrations are managed via Alembic.

## Directory Structure
- `alembic.ini`: Configuration file containing database URL and formatting rules.
- `env.py`: Migration environment runner linked to SQLAlchemy declarative Base metadata.
- `versions/`: Timestamped revision scripts.

## Common Commands

Initialize a fresh migration revision:
```bash
alembic revision --autogenerate -m "add_columns"
```

Apply migrations to target database:
```bash
alembic upgrade head
```

Rollback the previous migration:
```bash
alembic downgrade -1
```

