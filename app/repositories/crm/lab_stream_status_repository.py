from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm.lab_stream_status import LabStreamStatus


def get_by_stream_id(db: Session, lead_stream_id: int) -> LabStreamStatus | None:
	statement = select(LabStreamStatus).where(LabStreamStatus.lead_stream_id == lead_stream_id)
	return db.scalar(statement)


def create(db: Session, record: LabStreamStatus) -> LabStreamStatus:
	db.add(record)
	db.commit()
	db.refresh(record)
	return record


def update(db: Session, record: LabStreamStatus) -> LabStreamStatus:
	db.add(record)
	db.commit()
	db.refresh(record)
	return record
