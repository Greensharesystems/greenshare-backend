from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class LeadStream(Base):
	__tablename__ = "crm_lead_streams"
	__table_args__ = (UniqueConstraint("lead_id", "stream_no", name="uq_crm_lead_stream"),)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True, nullable=False)
	lid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
	stream_no: Mapped[str] = mapped_column(String(16), nullable=False)
	waste_stream_name: Mapped[str] = mapped_column(String(255), nullable=False)
	est_qty: Mapped[float] = mapped_column(Float, nullable=False)
	unit: Mapped[str] = mapped_column(String(120), nullable=False)
	unit_other: Mapped[str | None] = mapped_column(String(120), nullable=True)
	waste_class: Mapped[str] = mapped_column(String(120), nullable=False)
	waste_class_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)

	lead: Mapped["Lead"] = relationship("Lead", back_populates="streams")
	lab_status: Mapped["LabStreamStatus | None"] = relationship(
		"LabStreamStatus",
		back_populates="stream",
		cascade="all, delete-orphan",
		uselist=False,
	)
