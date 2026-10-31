"""Session cookies: short-lived access JWT, rotating refresh token, CSRF token."""

import secrets

from fastapi import Response

from app.core.config import get_settings

ACCESS_COOKIE = "pf_access"
REFRESH_COOKIE = "pf_refresh"
CSRF_COOKIE = "pf_csrf"
CSRF_HEADER = "X-CSRF-Token"
REFRESH_PATH = "/api/v1/auth"


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.cookie_secure
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=settings.access_token_ttl_seconds,
                        httponly=True, secure=secure, samesite="lax", path="/api")
    response.set_cookie(REFRESH_COOKIE, refresh_token,
                        max_age=settings.refresh_token_ttl_seconds,
                        httponly=True, secure=secure, samesite="lax", path=REFRESH_PATH)
    # Readable by the web app, which echoes it in the CSRF header (double-submit).
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24),
                        max_age=settings.refresh_token_ttl_seconds,
                        httponly=False, secure=secure, samesite="lax", path="/")


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
