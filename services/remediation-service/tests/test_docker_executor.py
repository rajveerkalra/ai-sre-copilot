"""Docker restart executor -- the allowlist is the safety boundary here.

No real Docker daemon is needed: the allowlist check happens before the
`docker` SDK is even imported (see docker_executor.py), and the SDK itself
is imported lazily inside the function, so a fake module injected into
sys.modules is picked up transparently for the success/error-path tests.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.config import Settings
from app.services.docker_executor import DockerExecutionError, restart_container


def _settings(**overrides) -> Settings:
    return Settings(
        restart_allowed_services=overrides.pop("restart_allowed_services", "sample-app"),
        docker_container_prefix=overrides.pop("docker_container_prefix", "ai-sre-"),
        **overrides,
    )


def test_disallowed_service_rejected_without_touching_docker():
    # postgres is never on the allowlist -- must fail closed before any
    # Docker SDK import/call is attempted.
    with pytest.raises(DockerExecutionError, match="not on the restart allowlist"):
        restart_container("postgres", _settings())


def test_unlisted_service_rejected_even_if_container_would_exist():
    with pytest.raises(DockerExecutionError, match="redis"):
        restart_container("redis", _settings(restart_allowed_services="sample-app,other-svc"))


class _FakeContainer:
    def __init__(self, name):
        self.name = name
        self._started_at = "2026-01-01T00:00:00Z"
        self.restarted = False

    @property
    def attrs(self):
        return {"State": {"StartedAt": self._started_at, "Status": "running"}}

    def restart(self, timeout=10):
        self.restarted = True
        self._started_at = "2026-01-01T00:05:00Z"  # simulate a real restart bump

    def reload(self):
        pass


def _install_fake_docker_module(container_map, raise_on_get=None):
    fake_docker = types.ModuleType("docker")
    fake_errors = types.ModuleType("docker.errors")

    class NotFound(Exception):
        pass

    class DockerException(Exception):
        pass

    fake_errors.NotFound = NotFound
    fake_errors.DockerException = DockerException

    class FakeContainers:
        def get(self, name):
            if raise_on_get:
                raise raise_on_get
            if name not in container_map:
                raise NotFound(f"no such container: {name}")
            return container_map[name]

    class FakeClient:
        def __init__(self):
            self.containers = FakeContainers()

    fake_docker.from_env = lambda: FakeClient()
    fake_docker.errors = fake_errors

    sys.modules["docker"] = fake_docker
    sys.modules["docker.errors"] = fake_errors
    return NotFound, DockerException


@pytest.fixture(autouse=True)
def _cleanup_fake_docker():
    yield
    sys.modules.pop("docker", None)
    sys.modules.pop("docker.errors", None)


def test_allowed_service_restarts_and_reports_real_timestamp_change():
    container = _FakeContainer("ai-sre-sample-app")
    _install_fake_docker_module({"ai-sre-sample-app": container})

    result = restart_container("sample-app", _settings())

    assert container.restarted is True
    assert result["container"] == "ai-sre-sample-app"
    assert result["restarted_at"] == "2026-01-01T00:05:00Z"
    assert result["status"] == "running"
    assert result["dry_run"] is False


def test_container_not_found_raises_execution_error():
    _install_fake_docker_module({})  # no containers registered

    with pytest.raises(DockerExecutionError, match="not found"):
        restart_container("sample-app", _settings())


def test_docker_api_error_wrapped_as_execution_error():
    _, DockerException = _install_fake_docker_module({}, raise_on_get=None)
    fake_docker = sys.modules["docker"]

    class BoomContainers:
        def get(self, name):
            raise sys.modules["docker.errors"].DockerException("daemon unreachable")

    fake_docker.from_env = lambda: types.SimpleNamespace(containers=BoomContainers())

    with pytest.raises(DockerExecutionError, match="Docker API error"):
        restart_container("sample-app", _settings())
