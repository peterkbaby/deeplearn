import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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



def set_refresh_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=7 * 24 * 60 * 60,
        path="/user-service",
    )


@router.get("/google")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error("OAuth Error: %s", e)
        raise HTTPException(status_code=400, detail="Failed to authorize token")

    user_info = token.get("userinfo")
    access_token, refresh_token = await oauth_service.process_google_user(session, user_info)

    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    set_refresh_cookie(response, refresh_token)
    return response
