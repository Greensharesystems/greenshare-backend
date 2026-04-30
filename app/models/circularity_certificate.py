from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CircularityCertificate(Base):
	__tablename__ = "circularity_certificates"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	ccid_date: Mapped[str] = mapped_column(String(32), nullable=False)
	ccid: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
	rcid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	linked_rcids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
	secondary_ecosystem_details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
	cid: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="")
	producing_company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_stream_quantity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	secondary_product: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	secondary_loop: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	issued_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	owner_identifier: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	owner_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="Issued")
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
