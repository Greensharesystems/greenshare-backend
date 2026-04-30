from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ReceptionCertificate(Base):
	__tablename__ = "reception_certificates"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	rcid_date: Mapped[str] = mapped_column(String(32), nullable=False)
	rcid: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	rnid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	linked_rnids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
	customer_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="")
	producing_company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_stream_quantity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	rc_issued_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	owner_identifier: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	owner_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="Issued")
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
