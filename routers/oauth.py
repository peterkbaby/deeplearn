import logging
from urllib.parse import quote
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuthError

from core.config import settings
from core.oauth import oauth
from database.db import get_session
from services import oauth_service

router = APIRouter(prefix="/auth", tags=["OAuth"])
logger = logging.getLogger(__name__)


def frontend_origin() -> str:
    """Return the configured public frontend origin.

    OAuth redirect targets are deployment configuration, not request-derived
    values. In particular, a process bind address such as ``0.0.0.0:3000``
    must never become a browser redirect target.
    """
    return settings.frontend_url.rstrip("/").replace("://0.0.0.0", "://localhost")



def set_refresh_cookie(response: Response, token: str) -> None:
    # Migrate sessions created before password and OAuth flows shared a cookie
    # path. Keeping both paths produces duplicate Cookie header values.
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path="/user-service",
    )
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=7 * 24 * 60 * 60,
        # The Next.js callback needs to receive this cookie after OAuth redirects.
        # Keep the cookie HttpOnly; the frontend server relays it to FastAPI.
        path="/",
    )


@router.get("/google")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error("OAuth Error: %s", e)
        return RedirectResponse(f"{frontend_origin()}/login?oauth_error=1")

    user_info = token.get("userinfo")
    access_token, refresh_token = await oauth_service.process_google_user(session, user_info)

    # The fragment is never sent to Nginx or written to server access logs.
    # FastAPI owns the refresh cookie; the frontend only stores the short-lived
    # access token after this redirect.
    response = RedirectResponse(
        f"{frontend_origin()}/auth/complete#access_token={quote(access_token)}"
    )
    set_refresh_cookie(response, refresh_token)
    return response
