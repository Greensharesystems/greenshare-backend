from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Lead(Base):
	__tablename__ = "crm_leads"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	lid: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	cid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
	customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
	source: Mapped[str] = mapped_column(String(120), nullable=False)
	source_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
	assigned_to: Mapped[str] = mapped_column(String(255), nullable=False)
	assigned_to_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
	waste_stream: Mapped[str] = mapped_column(String(255), nullable=False)
	waste_class: Mapped[str] = mapped_column(String(120), nullable=False)
	waste_class_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
	est_qty: Mapped[float] = mapped_column(Float, nullable=False)
	unit: Mapped[str] = mapped_column(String(120), nullable=False)
	unit_other: Mapped[str | None] = mapped_column(String(120), nullable=True)
	comments: Mapped[str | None] = mapped_column(Text, nullable=True)
	lead_date: Mapped[str] = mapped_column(String(32), nullable=False)
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[DateTime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)
	deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

	lab_status: Mapped["LabStatus | None"] = relationship(
		"LabStatus",
		back_populates="lead",
		cascade="all, delete-orphan",
		uselist=False,
	)
	proposal_status: Mapped["ProposalStatus | None"] = relationship(
		"ProposalStatus",
		back_populates="lead",
		cascade="all, delete-orphan",
		uselist=False,
	)
	lead_status: Mapped["LeadStatus | None"] = relationship(
		"LeadStatus",
		back_populates="lead",
		cascade="all, delete-orphan",
		uselist=False,
	)
	wds_status: Mapped["WdsStatus | None"] = relationship(
		"WdsStatus",
		back_populates="lead",
		cascade="all, delete-orphan",
		uselist=False,
	)
