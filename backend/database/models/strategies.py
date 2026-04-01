# STL
import uuid
from datetime import datetime

# External
from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class Strategy(Base):
  __tablename__ = "strategies"

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
  )
  name: Mapped[str] = mapped_column(String(255), nullable=False)
  graph_json: Mapped[str] = mapped_column(Text, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=datetime.utcnow, nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
  )
