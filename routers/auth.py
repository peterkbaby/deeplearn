from uuid import UUID
from starlette.requests import Request
from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import get_current_user, require_role
from core.enums import Role
from database.db import get_session
from database.users import User
from schemas.user import (
    OnboardingRequest,
    ProfilePicResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from services import auth_service
from core.limiter import limiter

auth = APIRouter(prefix="/user-service", tags=["User Service"])


def set_refresh_cookie(response: JSONResponse, token: str) -> None:
    # Remove the old scoped cookie before setting the shared OAuth/password
    # cookie. Otherwise browsers can send two refresh_token values after an
    # upgrade and FastAPI may read the stale one.
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
        max_age=7 * 24 * 60 * 60,  # 7 days in seconds
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path="/",
    )
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path="/user-service",
    )


@auth.post("/register", response_model=UserResponse, status_code=201,
 summary="register a new user",
 description="Creates a user account. Password must be 6+ chars with upper, lower, digit.",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded (3/min)"},
    },
    )
@limiter.limit("3/minute")
async def create_user(
    request: Request,
    user: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    return await auth_service.register_user(session, user)


@auth.get("/email/{email}", response_model=UserResponse)
@limiter.limit("20/minute")
async def get_user_by_email(
    request: Request,
    email: str,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    return await auth_service.get_user_by_email(session, email)


@auth.get("/id/{user_id}", response_model=UserResponse)
@limiter.limit("20/minute")
async def get_user_by_id(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    return await auth_service.get_user_by_id(session, user_id)


@auth.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    user_data: UserLogin, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    _, access_token, refresh_token = await auth_service.login_user(session, user_data)
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    set_refresh_cookie(response, refresh_token)
    return response


@auth.get("/me", response_model=UserResponse)
@limiter.limit("10/minute")
async def get_me(request: Request, current_user: User = Depends(get_current_user)) -> UserResponse:
    return current_user


@auth.get("/all-users", response_model=list[UserResponse])
@limiter.limit("10/minute")
async def get_all_users(
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[UserResponse]:
    return await auth_service.get_all_users(session)


@auth.post("/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
async def refresh_token(
    request: Request,
    refresh_token: str | None = Cookie(None, alias=settings.refresh_token_cookie_name),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    new_access_token, new_refresh_token = await auth_service.refresh_access_token(
        session, refresh_token
    )
    response = JSONResponse(
        content={"access_token": new_access_token, "token_type": "bearer"}
    )
    set_refresh_cookie(response, new_refresh_token)
    return response


@auth.post("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None, alias=settings.refresh_token_cookie_name),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.logout(session, refresh_token)
    clear_refresh_cookie(response)
    return {"detail": "Logged out successfully"}


@auth.post("/onboarding")
@limiter.limit("10/minute")
async def onboarding(
    request: Request,
    data: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.complete_onboarding(session, current_user, data.username)
    return {"detail": "Onboarding completed successfully"}


@auth.post("/profile/upload-pic")
@limiter.limit("10/minute")
async def upload_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    contents = await file.read()
    profile_pic_url = await auth_service.upload_profile_picture(
        session, current_user, contents, file.content_type
    )
    return {"detail": "Profile picture uploaded successfully", "profile_pic_url": profile_pic_url}

@auth.get("/profile/pic", response_model=ProfilePicResponse)
@limiter.limit("20/minute")
async def get_profile_picture(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ProfilePicResponse:
    if not current_user.profile_pic_url:
        raise HTTPException(status_code=404, detail="No profile picture uploaded")
    return ProfilePicResponse(profile_pic_url=current_user.profile_pic_url)


@auth.delete("/profile/pic")
@limiter.limit("10/minute")
async def delete_profile_picture(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.delete_profile_picture(session, current_user)
    return {"detail": "Profile picture deleted successfully"}
