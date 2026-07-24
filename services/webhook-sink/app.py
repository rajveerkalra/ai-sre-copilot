"""Phase 1 Alertmanager webhook sink.

Logs incoming alert payloads so the alert → webhook path can be validated
before the Incident Service exists (Phase 2).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Alert Webhook Sink", version="0.1.0")

_received: list[dict] = []


@app.get("/healthz")
@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "webhook-sink"}


@app.get("/livez")
async def live() -> dict:
    return {"status": "healthy", "service": "webhook-sink"}


@app.get("/readyz")
async def ready() -> dict:
    return {"status": "healthy", "service": "webhook-sink"}


@app.post("/webhooks/alertmanager")
async def alertmanager_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "status": payload.get("status"),
        "alert_count": len(payload.get("alerts", [])),
        "receiver": payload.get("receiver"),
        "payload": payload,
    }
    _received.append(entry)
    # Keep a bounded ring buffer for local debugging
    if len(_received) > 200:
        del _received[:100]
    print(json.dumps({"event": "alertmanager_webhook", **{k: entry[k] for k in ("received_at", "status", "alert_count", "receiver")}}), flush=True)
    return JSONResponse({"accepted": True, "alert_count": entry["alert_count"]})


@app.get("/webhooks/recent")
async def recent(limit: int = 20) -> dict:
    return {"count": len(_received), "recent": list(reversed(_received[-limit:]))}
