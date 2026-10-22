import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.emergency import router as emergency_router
from app.api.patients import router as patients_router
from app.api.reviews import router as reviews_router
from app.api.sync import router as sync_router
from app.api.visits import router as visits_router
from app.api.workers import router as workers_router
from app.config import Settings, get_settings
from app.db.session import check_database_connection, get_session_local
from app.observability import (
    HTTP_ERRORS,
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_PROGRESS,
    PROCESS_UPTIME,
    PROCESS_START_TIME,
)
from app.services.demo_accounts import count_active_demo_accounts

logger = logging.getLogger("herdoc.http")


def check_no_demo_accounts() -> None:
    """Refuse to serve production traffic while seeded demo accounts are active."""
    db = get_session_local()()
    try:
        count = count_active_demo_accounts(db)
    finally:
        db.close()
    if count:
        raise RuntimeError(
            f"Found {count} active demo account(s) (herdoc.local emails or seeded phones). "
            "Deactivate or delete them before starting in production; never run the seed script against production."
        )


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        check_database_connection()
        if settings.is_production:
            check_no_demo_accounts()
        yield

    docs_enabled = settings.api_docs_enabled
    app = FastAPI(
        title="HerDoc API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.WEB_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth_router)
    app.include_router(patients_router)
    app.include_router(visits_router)
    app.include_router(sync_router)
    app.include_router(dashboard_router)
    app.include_router(reviews_router)
    app.include_router(workers_router)
    app.include_router(emergency_router)

    @app.middleware("http")
    async def observe_http_requests(request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        HTTP_REQUESTS_IN_PROGRESS.inc()
        try:
            response = await call_next(request)
            status_code = response.status_code
            if request.url.path.startswith("/api/"):
                # Tokens and patient data must not be stored by browsers, proxies, or service workers.
                response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", "<unmatched>")
            method = request.method
            HTTP_REQUESTS.labels(method=method, path=path, status_code=str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
            if status_code >= 400:
                HTTP_ERRORS.labels(method=method, path=path, status_code=str(status_code)).inc()
            HTTP_REQUESTS_IN_PROGRESS.dec()
            level = logging.ERROR if status_code >= 500 else logging.INFO
            logger.log(
                level,
                "http_request method=%s path=%s status_code=%s duration_seconds=%.6f",
                method,
                path,
                status_code,
                elapsed,
            )

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        # Open in development (local Prometheus); token-protected or disabled in production.
        token = settings.METRICS_TOKEN.strip()
        if token:
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
                return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
        elif settings.is_production:
            return Response(status_code=404)
        PROCESS_UPTIME.set(time.monotonic() - PROCESS_START_TIME)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


settings = get_settings()
app = create_app(settings)
