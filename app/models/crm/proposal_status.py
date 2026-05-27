from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProposalStatus(Base):
	__tablename__ = "crm_proposal_statuses"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
	lid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
	pid: Mapped[str] = mapped_column(String(32), nullable=False)
	status: Mapped[str] = mapped_column(String(120), nullable=False)
	status_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
	comments: Mapped[str | None] = mapped_column(Text, nullable=True)
	updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
	updated_at: Mapped[DateTime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)
	lead: Mapped["Lead"] = relationship("Lead", back_populates="proposal_status")
