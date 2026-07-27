"""Real container restart execution via the Docker Engine API.

This is the one remediation action that actually mutates infrastructure in
this project (see docs/eval.md and executor.py for the rest, which remain
stubs). Two independent safety gates apply before any restart can happen:

1. `settings.allow_compose_restart` must be true (existing config gate).
2. The requested logical service name must appear in
   `settings.restart_allowed_services` -- a hard allowlist enforced here in
   code. This exists so a bad or hallucinated RCA/remediation proposal can
   never reach infrastructure containers (postgres, redis, etc.) even if it
   somehow named them: only names on this list are ever looked up, and the
   lookup itself fails closed (unknown name -> ExecutionError, not "restart
   something similar").

Both gates sit behind the existing human-approval requirement in
api/routes.py (`require_approve`) -- this code only ever runs after an
authenticated operator/admin has explicitly approved the proposal.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)


class DockerExecutionError(Exception):
    pass


def _allowed_services(settings: Settings) -> set[str]:
    return {s.strip() for s in settings.restart_allowed_services.split(",") if s.strip()}


def restart_container(service: str, settings: Settings) -> dict[str, Any]:
    """Restart the real Docker container for `service`. Raises DockerExecutionError
    on any failure (unknown service, not on the allowlist, Docker API error)."""
    if service not in _allowed_services(settings):
        raise DockerExecutionError(
            f"'{service}' is not on the restart allowlist "
            f"({sorted(_allowed_services(settings))}); refusing to restart"
        )

    try:
        import docker
        from docker.errors import DockerException, NotFound
    except ImportError as exc:  # pragma: no cover
        raise DockerExecutionError("docker SDK not installed") from exc

    container_name = f"{settings.docker_container_prefix}{service}"
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        before_started_at = container.attrs.get("State", {}).get("StartedAt")
        container.restart(timeout=10)
        container.reload()
        after_started_at = container.attrs.get("State", {}).get("StartedAt")
        after_status = container.attrs.get("State", {}).get("Status")
    except NotFound as exc:
        raise DockerExecutionError(f"container '{container_name}' not found") from exc
    except DockerException as exc:
        raise DockerExecutionError(f"Docker API error restarting '{container_name}': {exc}") from exc

    logger.info(
        "container_restarted",
        service=service,
        container=container_name,
        before_started_at=before_started_at,
        after_started_at=after_started_at,
    )
    return {
        "dry_run": False,
        "action_type": "restart_service",
        "service": service,
        "container": container_name,
        "status": after_status,
        "restarted_at": after_started_at,
        "message": f"Restarted container '{container_name}'",
    }
