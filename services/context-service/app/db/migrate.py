"""Alembic migration runner."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    service_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(service_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(service_root / "alembic"))
    command.upgrade(cfg, "head")
