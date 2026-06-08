from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class LabStreamStatus(Base):
	__tablename__ = "crm_lab_stream_statuses"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	lead_stream_id: Mapped[int] = mapped_column(ForeignKey("crm_lead_streams.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
	lead_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
	lid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
	stream_no: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
	decision: Mapped[str] = mapped_column(String(120), nullable=False)
	decision_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
	comments: Mapped[str | None] = mapped_column(Text, nullable=True)
	chemist_name: Mapped[str] = mapped_column(String(255), nullable=False)
	decision_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)

	stream: Mapped["LeadStream"] = relationship("LeadStream", back_populates="lab_status")
