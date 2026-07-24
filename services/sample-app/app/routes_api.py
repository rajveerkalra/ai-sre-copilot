"""Business API routes that generate realistic metrics and logs."""

from __future__ import annotations

import asyncio
import random
import time
import uuid

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.faults import fault_injector
from app.metrics import (
    BUSINESS_ORDERS_TOTAL,
    DEPENDENCY_CALLS_TOTAL,
    DEPENDENCY_LATENCY_SECONDS,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


class OrderRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(1, ge=1, le=100)


class OrderResponse(BaseModel):
    order_id: str
    sku: str
    quantity: int
    status: str


@router.get("/info")
async def info() -> dict:
    settings = get_settings()
    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.version,
        "description": "Demo e-commerce API used to generate SRE incidents",
    }


@router.get("/products")
async def list_products() -> dict:
    await fault_injector.maybe_inject_latency()
    if fault_injector.should_error():
        logger.error("products_list_failed", reason="error_storm")
        BUSINESS_ORDERS_TOTAL.labels(status="error").inc()
        raise HTTPException(status_code=500, detail="Simulated error storm")

    products = [
        {"sku": "SKU-100", "name": "Widget", "price": 19.99},
        {"sku": "SKU-200", "name": "Gadget", "price": 49.99},
        {"sku": "SKU-300", "name": "Doohickey", "price": 9.99},
    ]
    logger.info("products_listed", count=len(products))
    return {"products": products}


@router.post("/orders", response_model=OrderResponse)
async def create_order(body: OrderRequest) -> OrderResponse:
    await fault_injector.maybe_inject_latency()

    if fault_injector.should_error():
        logger.error(
            "order_create_failed",
            sku=body.sku,
            quantity=body.quantity,
            reason="error_storm",
        )
        BUSINESS_ORDERS_TOTAL.labels(status="error").inc()
        raise HTTPException(status_code=500, detail="Order processing failed")

    if fault_injector.should_dependency_timeout():
        await _call_dependency()

    # Simulate light work
    await asyncio.sleep(random.uniform(0.01, 0.05))

    order_id = str(uuid.uuid4())
    BUSINESS_ORDERS_TOTAL.labels(status="ok").inc()
    logger.info(
        "order_created",
        order_id=order_id,
        sku=body.sku,
        quantity=body.quantity,
    )
    return OrderResponse(
        order_id=order_id,
        sku=body.sku,
        quantity=body.quantity,
        status="accepted",
    )


@router.get("/orders/{order_id}")
async def get_order(order_id: str) -> dict:
    await fault_injector.maybe_inject_latency()
    if fault_injector.should_error():
        logger.error("order_get_failed", order_id=order_id, reason="error_storm")
        raise HTTPException(status_code=500, detail="Lookup failed")
    return {
        "order_id": order_id,
        "status": "accepted",
        "sku": "SKU-100",
        "quantity": 1,
    }


async def _call_dependency() -> None:
    settings = get_settings()
    dependency = "payments"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.dependency_timeout_seconds
        ) as client:
            await client.get(settings.dependency_url)
        DEPENDENCY_CALLS_TOTAL.labels(dependency=dependency, status="ok").inc()
    except Exception as exc:
        duration = time.perf_counter() - started
        DEPENDENCY_LATENCY_SECONDS.labels(dependency=dependency).observe(duration)
        DEPENDENCY_CALLS_TOTAL.labels(
            dependency=dependency, status="timeout"
        ).inc()
        logger.error(
            "dependency_timeout",
            dependency=dependency,
            url=settings.dependency_url,
            error=str(exc),
            duration_ms=round(duration * 1000, 2),
        )
        raise HTTPException(
            status_code=504,
            detail=f"Dependency '{dependency}' timed out",
        ) from exc
    else:
        duration = time.perf_counter() - started
        DEPENDENCY_LATENCY_SECONDS.labels(dependency=dependency).observe(duration)
