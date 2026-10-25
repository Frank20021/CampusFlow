from fastapi import APIRouter
from sqlalchemy import text

from app.core.exceptions import AppError
from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            code="not_ready",
            message="Database unavailable",
            status_code=503,
        ) from exc
    return {"status": "ready"}
