from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
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
	referring_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
	project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	project_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
	project_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
	project_custom_fields: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
	waste_stream_quantity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_stream_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	waste_stream_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
	secondary_product: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	secondary_loop: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	issued_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	verification_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
	owner_identifier: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	owner_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="Issued")
	is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
	deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
