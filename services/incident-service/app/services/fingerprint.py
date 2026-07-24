"""Fingerprint and alert normalization helpers."""

from __future__ import annotations

import hashlib
from typing import Any

from app.schemas.alertmanager import AlertmanagerAlert, ParsedAlert


FINGERPRINT_KEYS = ("alertname", "namespace", "pod", "service", "instance")


def compute_fingerprint(
    *,
    alertname: str,
    namespace: str = "",
    pod: str = "",
    service: str = "",
    instance: str = "",
) -> str:
    """Stable SHA-256 fingerprint used for open-incident deduplication."""
    parts = [
        (alertname or "").strip().lower(),
        (namespace or "").strip().lower(),
        (pod or "").strip().lower(),
        (service or "").strip().lower(),
        (instance or "").strip().lower(),
    ]
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def parse_alert(alert: AlertmanagerAlert) -> ParsedAlert:
    labels = dict(alert.labels or {})
    annotations = dict(alert.annotations or {})

    alertname = labels.get("alertname") or "UnknownAlert"
    severity = (labels.get("severity") or "unknown").lower()
    namespace = labels.get("namespace") or labels.get("kubernetes_namespace") or ""
    pod = labels.get("pod") or labels.get("pod_name") or ""
    service = labels.get("service") or labels.get("job") or ""
    instance = labels.get("instance") or ""

    title = (
        annotations.get("summary")
        or annotations.get("title")
        or alertname
    )
    description = annotations.get("description") or annotations.get("message") or ""

    return ParsedAlert(
        alertname=alertname,
        severity=severity,
        namespace=namespace,
        pod=pod,
        service=service,
        instance=instance,
        status=(alert.status or "firing").lower(),
        starts_at=alert.startsAt,
        ends_at=alert.endsAt,
        labels=labels,
        annotations=annotations,
        title=title,
        description=description,
        am_fingerprint=alert.fingerprint,
        raw=alert.model_dump(mode="json"),
    )


def fingerprint_for_parsed(parsed: ParsedAlert) -> str:
    return compute_fingerprint(
        alertname=parsed.alertname,
        namespace=parsed.namespace,
        pod=parsed.pod,
        service=parsed.service,
        instance=parsed.instance,
    )


def severity_from_label(value: str) -> str:
    normalized = (value or "unknown").lower()
    if normalized in ("critical", "warning", "info", "unknown"):
        return normalized
    if normalized in ("error", "fatal", "page"):
        return "critical"
    return "unknown"


def alert_to_dict(parsed: ParsedAlert) -> dict[str, Any]:
    return parsed.model_dump(mode="json")
