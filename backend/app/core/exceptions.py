from typing import Any


class AppError(Exception):
    """Domain error mapped to a consistent JSON response.

    Chosen: one error envelope for every failure path so the frontend can
    render `error.message` without special-casing FastAPI's default shapes.
    Alternative: RFC 7807 problem+json. Tradeoff: more standard, but heavier
    for a SPA that just needs a code + message.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


def error_body(
    *,
    code: str,
    message: str,
    request_id: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }
