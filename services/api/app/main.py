import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from app.core.db import DbContext, open_session
from app.core.errors import ProblemError, install_error_handlers
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.tenants.router import router as tenants_router
from app.modules.users.router import router as users_router

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
Handler = Callable[[Request], Awaitable[Response]]


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.environment == "development":
        logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="Persona Forge API", version="0.1.0",
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER],
    )

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next: Handler) -> Response:
        # Double-submit check: a cookie-authenticated, state-changing request must echo the
        # CSRF cookie in a header, which another site's page cannot read.
        has_session = ACCESS_COOKIE in request.cookies or REFRESH_COOKIE in request.cookies
        if request.method in UNSAFE_METHODS and has_session:
            cookie = request.cookies.get(CSRF_COOKIE, "")
            header = request.headers.get(CSRF_HEADER, "")
            if not cookie or not secrets.compare_digest(cookie, header):
                return await _problem_response(request, ProblemError(
                    403, "Forbidden", "Missing or invalid CSRF token."))
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Handler) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        async with open_session(DbContext("none")) as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}

    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(audit_router)
    api.include_router(tenants_router)
    app.include_router(api)
    return app


async def _problem_response(request: Request, exc: ProblemError) -> Response:
    handler = request.app.exception_handlers[ProblemError]
    return await handler(request, exc)


app = create_app()
