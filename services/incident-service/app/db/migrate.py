"""Database migration runner (Alembic)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    """Apply Alembic migrations to head using sync DB URL."""
    # migrate.py lives at <service_root>/app/db/migrate.py
    service_root = Path(__file__).resolve().parents[2]
    alembic_ini = service_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(service_root / "alembic"))
    command.upgrade(cfg, "head")
