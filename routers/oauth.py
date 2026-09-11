import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuthError

from core.config import settings
from core.oauth import oauth
from database.db import get_session
from schemas.user import TokenResponse
from services import oauth_service

router = APIRouter(prefix="/auth", tags=["OAuth"])
logger = logging.getLogger(__name__)


def frontend_origin(request: Request) -> str:
    """Return a browser-reachable frontend origin for OAuth redirects.

    0.0.0.0 is useful for binding a server socket, but is not a valid public
    browser destination. This also protects local development when an env var
    was copied from the uvicorn bind address.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto", "https").split(",")[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    origin = settings.frontend_url.rstrip("/")
    return origin.replace("://0.0.0.0", "://localhost")



def set_refresh_cookie(response: JSONResponse, token: str) -> None:
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
) -> TokenResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error("OAuth Error: %s", e)
        return RedirectResponse(f"{frontend_origin(request)}/login?oauth_error=1")

    user_info = token.get("userinfo")
    access_token, refresh_token = await oauth_service.process_google_user(session, user_info)

    # The access token is short-lived and immediately consumed by the frontend
    # callback, which replaces the URL before rendering the authenticated app.
    response = RedirectResponse(
        f"{frontend_origin(request)}/auth/callback?access_token={access_token}"
    )
    set_refresh_cookie(response, refresh_token)
    return response
