import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import AppError, error_body
from app.core.logging import configure_logging
from app.core.middleware import InMemoryRateLimitMiddleware, RequestContextMiddleware
from app.realtime.broker import create_broker
from app.realtime.registry import get_broker, set_broker
import app.models  # noqa: F401  — register models with SQLAlchemy

import structlog

logger = structlog.get_logger("campusflow")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    set_broker(await create_broker(settings.redis_url))
    try:
        yield
    finally:
        await get_broker().close()
        set_broker(None)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        json_output=settings.is_production,
        level=logging.WARNING if settings.environment.lower() == "test" else logging.INFO,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(InMemoryRateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        # Last-Event-ID is not CORS-safelisted, so without it here the browser
        # preflight blocks every stream reconnect that tries to replay a gap.
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Last-Event-ID"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api")

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        logger.warning(
            "app_error",
            code=exc.code,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                details=exc.details,
            ),
            headers={"X-Request-ID": request_id or ""},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id(request)
        details = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            details.append({"field": loc or None, "message": error.get("msg")})
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="validation_error",
                message="Request validation failed",
                request_id=request_id,
                details=details,
            ),
            headers={"X-Request-ID": request_id or ""},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code="http_error",
                message=str(exc.detail),
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id or ""},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body(
                code="internal_error",
                message="An unexpected error occurred",
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id or ""},
        )

    return app


app = create_app()
