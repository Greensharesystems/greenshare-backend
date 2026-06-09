from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.crm.stream_code import StreamCode


def list_stream_codes(db: Session) -> list[StreamCode]:
	statement = (
		select(StreamCode)
		.where(StreamCode.deleted_at.is_(None))
		.order_by(StreamCode.created_at.desc(), StreamCode.id.desc())
	)
	return list(db.scalars(statement).all())


def get_stream_code_by_identifier(db: Session, identifier: str) -> StreamCode | None:
	conditions = [StreamCode.stream_code == identifier]
	if identifier.isdigit():
		conditions.append(StreamCode.id == int(identifier))

	statement = (
		select(StreamCode)
		.where(StreamCode.deleted_at.is_(None))
		.where(or_(*conditions))
		.limit(1)
	)
	return db.scalar(statement)


def stream_code_exists(db: Session, stream_code: str, exclude_id: int | None = None) -> bool:
	statement = select(StreamCode.id).where(StreamCode.stream_code == stream_code)
	if exclude_id is not None:
		statement = statement.where(StreamCode.id != exclude_id)
	return db.scalar(statement.limit(1)) is not None


def get_stream_codes_for_category(db: Session, category: str) -> list[str]:
	statement = select(StreamCode.stream_code).where(StreamCode.category == category)
	return [code for code in db.scalars(statement).all() if code]


def create_stream_code(db: Session, stream_code: StreamCode) -> StreamCode:
	db.add(stream_code)
	db.commit()
	db.refresh(stream_code)
	return stream_code


def update_stream_code(db: Session, stream_code: StreamCode) -> StreamCode:
	db.add(stream_code)
	db.commit()
	db.refresh(stream_code)
	return stream_code


def soft_delete_stream_code(db: Session, stream_code: StreamCode) -> None:
	stream_code.deleted_at = datetime.now(timezone.utc)
	db.add(stream_code)
	db.commit()
