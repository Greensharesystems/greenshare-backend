from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.database import Base


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
	user_id_date: Mapped[str] = mapped_column(String(32), nullable=False)
	user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
	first_name: Mapped[str] = mapped_column(String(120), nullable=False)
	last_name: Mapped[str] = mapped_column(String(120), nullable=False)
	email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
	position: Mapped[str | None] = mapped_column(String(120), nullable=True)
	department: Mapped[str | None] = mapped_column(String(120), nullable=True)
	mobile_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
	company: Mapped[str] = mapped_column(String(255), nullable=False)
	role: Mapped[str] = mapped_column(String(32), nullable=False)
	customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	last_active: Mapped[str] = mapped_column(String(64), nullable=False)
	created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	customer_account: Mapped["Customer | None"] = relationship(
		"Customer",
		primaryjoin="foreign(User.customer_id) == Customer.customer_id",
		back_populates="linked_users",
	)
