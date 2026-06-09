from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class StreamCode(Base):
	__tablename__ = "crm_stream_codes"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	scid: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
	stream_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	category: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
	stream_name: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="Active")
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)
	deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
