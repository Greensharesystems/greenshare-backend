from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ReceptionNote(Base):
	__tablename__ = "reception_notes"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	rnid_date: Mapped[str] = mapped_column(String(32), nullable=False)
	rnid: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	customer_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
	weigh_bridge_slip_date: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	weigh_bridge_bill_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	producing_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
	producing_company_emirate: Mapped[str] = mapped_column(String(128), nullable=False, default="")
	producing_company_office_address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	producing_company_contact_person: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	producing_company_office_phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	producing_company_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	referring_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
	transporting_company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	transporting_company_contact_person: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	transporting_company_office_phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	transporting_company_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_streams: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
	vehicle_plate_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	driver_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_stream_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	waste_stream_quantity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	rn_issued_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	project_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
	project_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
	project_custom_fields: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
	owner_identifier: Mapped[str] = mapped_column(String(64), nullable=False, default="")
	owner_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="Issued")
	is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
	deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
