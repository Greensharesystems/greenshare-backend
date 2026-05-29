from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
	__tablename__ = "customers"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	customer_id_date: Mapped[str] = mapped_column(String(32), nullable=False)
	customer_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	company_name: Mapped[str] = mapped_column(String(255), nullable=False)
	company_emirate: Mapped[str] = mapped_column(String(120), nullable=False)
	area: Mapped[str] = mapped_column(String(120), nullable=False)
	office_address: Mapped[str] = mapped_column(String(255), nullable=False)
	website: Mapped[str] = mapped_column(String(255), nullable=False)
	company_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
	sector: Mapped[str] = mapped_column(String(120), nullable=False)
	contact_person_name: Mapped[str] = mapped_column(String(255), nullable=False)
	contact_person_position: Mapped[str] = mapped_column(String(120), nullable=False)
	contact_person_department: Mapped[str] = mapped_column(String(120), nullable=False)
	contact_person_email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
	contact_person_office_phone: Mapped[str] = mapped_column(String(64), nullable=False)
	contact_person_mobile_phone: Mapped[str] = mapped_column(String(64), nullable=False)
	focal_persons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	last_active: Mapped[str] = mapped_column(String(64), nullable=False)
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	linked_users: Mapped[list["User"]] = relationship(
		"User",
		primaryjoin="Customer.customer_id == foreign(User.customer_id)",
		back_populates="customer_account",
		cascade="all, delete-orphan",
	)
	reception_notes: Mapped[list["ReceptionNote"]] = relationship(
		"ReceptionNote",
		primaryjoin="Customer.customer_id == foreign(ReceptionNote.customer_id)",
		cascade="all, delete-orphan",
	)
	reception_certificates: Mapped[list["ReceptionCertificate"]] = relationship(
		"ReceptionCertificate",
		primaryjoin="Customer.customer_id == foreign(ReceptionCertificate.customer_id)",
		cascade="all, delete-orphan",
	)
	circularity_certificates: Mapped[list["CircularityCertificate"]] = relationship(
		"CircularityCertificate",
		primaryjoin="Customer.customer_id == foreign(CircularityCertificate.cid)",
		cascade="all, delete-orphan",
	)
