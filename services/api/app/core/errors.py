"""Errors returned as RFC 9457 problem details."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemError(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None, **extra: Any):
        self.status = status
        self.title = title
        self.detail = detail
        self.extra = extra


def bad_request(detail: str) -> ProblemError:
    return ProblemError(400, "Bad request", detail)


def unauthorized(detail: str = "Authentication required.") -> ProblemError:
    return ProblemError(401, "Unauthorized", detail)


def forbidden(detail: str = "You don't have permission to do this.") -> ProblemError:
    return ProblemError(403, "Forbidden", detail)


def not_found(detail: str = "Not found.") -> ProblemError:
    return ProblemError(404, "Not found", detail)


def conflict(detail: str) -> ProblemError:
    return ProblemError(409, "Conflict", detail)


def too_many_requests(retry_after: int) -> ProblemError:
    return ProblemError(429, "Too many requests", "Try again later.", retry_after=retry_after)


def _problem(request: Request, status: int, title: str, detail: Any, **extra: Any) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
        **extra,
    }
    headers = {}
    if "retry_after" in extra:
        headers["Retry-After"] = str(extra["retry_after"])
    return JSONResponse(body, status_code=status, media_type="application/problem+json",
                        headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem_error(request: Request, exc: ProblemError) -> JSONResponse:
        return _problem(request, exc.status, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return _problem(request, 422, "Validation error", "Request body is invalid.",
                        errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(request, exc.status_code, str(exc.detail), None)
