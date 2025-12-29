# STL
import uuid

# external
from sqlalchemy import String, Boolean
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID

# Custom
from database.make_db import Base


class User(Base):
    __tablename__ = "user"
    id: Mapped[str] = mapped_column(
        __name_pos=UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
