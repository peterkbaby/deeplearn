import uuid
from sqlalchemy import String, DateTime, func, Enum as SAEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.db import Base
from datetime import datetime

from core.enums import Role


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default= uuid.uuid4 )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(20), default="local")
    role: Mapped[str] = mapped_column(SAEnum(Role,
        name="user_role",
        native_enum=True,
        values_callable=lambda x: [e.value for e in x],
    ), default=Role.USER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    profile_pic_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    onboarding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    


