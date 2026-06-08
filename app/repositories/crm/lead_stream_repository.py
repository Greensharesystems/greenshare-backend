from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.crm.lead_stream import LeadStream


def get_streams_by_lead_id(db: Session, lead_id: int) -> list[LeadStream]:
	statement = (
		select(LeadStream)
		.options(selectinload(LeadStream.lab_status))
		.where(LeadStream.lead_id == lead_id)
		.order_by(LeadStream.stream_no)
	)
	return list(db.scalars(statement).all())


def get_stream(db: Session, lead_id: int, stream_no: str) -> LeadStream | None:
	statement = (
		select(LeadStream)
		.options(selectinload(LeadStream.lab_status))
		.where(LeadStream.lead_id == lead_id)
		.where(LeadStream.stream_no == stream_no)
	)
	return db.scalar(statement)


def create_stream(db: Session, stream: LeadStream) -> LeadStream:
	db.add(stream)
	db.commit()
	db.refresh(stream)
	return stream


def update_stream(db: Session, stream: LeadStream) -> LeadStream:
	db.add(stream)
	db.commit()
	db.refresh(stream)
	return stream


def delete_stream(db: Session, stream: LeadStream) -> None:
	db.delete(stream)
	db.commit()
