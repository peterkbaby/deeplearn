from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.users import User
from services.auth_service import _issue_and_store_tokens
from services.exceptions import GoogleUserInfoMissing


async def process_google_user(
    session: AsyncSession, user_info: dict | None
) -> tuple[str, str]:
    """Find or create a user from Google profile info and issue tokens.

    Returns (access_token, refresh_token).
    """
    if not user_info:
        raise GoogleUserInfoMissing("could not get user info from google")

    email = user_info.get("email")
    name = user_info.get("name", email.split("@")[0])

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, provider="google")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return await _issue_and_store_tokens(session, user.id)
