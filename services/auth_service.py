import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from core.storage import delete_from_s3, upload_to_s3
from database.tokens import RefreshToken
from database.users import User
from schemas.user import UserCreate, UserLogin
from services.exceptions import (
    EmailAlreadyRegistered,
    FileTooLarge,
    InvalidCredentials,
    InvalidFileType,
    InvalidRefreshToken,
    OAuthProviderLogin,
    OnboardingAlreadyCompleted,
    RefreshTokenExpired,
    RefreshTokenMissing,
    RefreshTokenRevoked,
    UserNotFound,
    UsernameAlreadyExists,
)

DUMMY_PASSWORD_HASH = "$2b$12$6I0YrJcImqzrECuL2n/gvOUvCsiuUd0HJI.hpp9kXIjOVong842O."
REFRESH_TOKEN_TTL = timedelta(days=7)
ABSOLUTE_REFRESH_EXPIRY = timedelta(days=30)
MAX_PROFILE_PIC_SIZE = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/webp")
_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


async def register_user(session: AsyncSession, user_data: UserCreate) -> User:
    result = await session.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise EmailAlreadyRegistered("Email already registered")

    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
    )
    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise EmailAlreadyRegistered("Email already registered")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFound("User not found")
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFound("User not found")
    return user


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return list(result.scalars().all())


async def _issue_and_store_tokens(
    session: AsyncSession,
    user_id: uuid.UUID,
    absolute_expiry: datetime | None = None,
) -> tuple[str, str]:
    """Create access + refresh tokens and persist the refresh token. Returns (access, refresh)."""
    absolute_expiry = absolute_expiry or datetime.now(timezone.utc) + ABSOLUTE_REFRESH_EXPIRY
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)}, absolute_expiry=absolute_expiry)

    db_token = RefreshToken(
        user_id=user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        absolute_expires_at=absolute_expiry,
    )
    session.add(db_token)
    await session.commit()
    return access_token, refresh_token


async def login_user(session: AsyncSession, user_data: UserLogin) -> tuple[User, str, str]:
    """Authenticate and return (user, access_token, refresh_token)."""
    result = await session.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()
    if user is None:
        verify_password(user_data.password, DUMMY_PASSWORD_HASH)
        raise InvalidCredentials("Invalid email or password")
        
    if not user.password_hash:
        raise OAuthProviderLogin("Please login with your oauth provider")

    if not verify_password(user_data.password, user.password_hash):
        raise InvalidCredentials("Invalid email or password")

    access_token, refresh_token = await _issue_and_store_tokens(session, user.id)
    return user, access_token, refresh_token


async def refresh_access_token(session: AsyncSession, refresh_token: str | None) -> tuple[str, str]:
    """Validate the refresh token, rotate it, and return (new_access, new_refresh)."""
    if not refresh_token:
        raise RefreshTokenMissing("No refresh token provided")

    try:
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("sub")
    except JWTError:
        raise InvalidRefreshToken("Invalid refresh token")

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token == refresh_token).with_for_update()
    )
    db_token = result.scalar_one_or_none()
    if not db_token:
        raise InvalidRefreshToken("Invalid refresh token")
    if db_token.revoked:
        raise RefreshTokenRevoked("Refresh token has been revoked")
    if db_token.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenExpired("Refresh token has expired")

    db_token.revoked = True

    new_access_token = create_access_token(data={"sub": str(user_id)})
    new_refresh_token = create_refresh_token(
        data={"sub": str(user_id)}, absolute_expiry=db_token.absolute_expires_at
    )
    new_db_token = RefreshToken(
        user_id=uuid.UUID(user_id),
        token=new_refresh_token,
        expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        absolute_expires_at=db_token.absolute_expires_at,
    )
    session.add(new_db_token)
    await session.commit()
    return new_access_token, new_refresh_token


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    """Revoke the refresh token if present."""
    if not refresh_token:
        return
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token == refresh_token)
    )
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.revoked = True
        await session.commit()


async def complete_onboarding(session: AsyncSession, user: User, username: str) -> None:
    if user.onboarding:
        raise OnboardingAlreadyCompleted("User already completed onboarding")

    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise UsernameAlreadyExists("Username already exists")

    try:
        user.username = username
        user.onboarding = True
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise UsernameAlreadyExists("Username already exists")

async def upload_profile_picture(
    session: AsyncSession,
    user: User,
    contents: bytes,
    content_type: str,
) -> str:
    if len(contents) > MAX_PROFILE_PIC_SIZE:
        raise FileTooLarge("File size exceeds 2MB limit")
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise InvalidFileType("File must be a JPEG, PNG, or WebP image")

    ext = _IMAGE_EXTENSIONS[content_type]
    key = f"profiles/{user.id}.{ext}"
    profile_pic_url = await upload_to_s3(contents, key, content_type)
    user.profile_pic_url = profile_pic_url
    await session.commit()
    return profile_pic_url


async def delete_profile_picture(session: AsyncSession, user: User) -> None:
    """Remove all supported profile-photo variants and clear the user record."""
    for ext in ("jpg", "png", "webp"):
        await delete_from_s3(f"profiles/{user.id}.{ext}")
    user.profile_pic_url = None
    await session.commit()
