from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm.lab_status import LabStatus


def get_by_lead_id(db: Session, lead_id: int) -> LabStatus | None:
	statement = select(LabStatus).where(LabStatus.lead_id == lead_id)
	return db.scalar(statement)


def create(db: Session, status_record: LabStatus) -> LabStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record


def update(db: Session, status_record: LabStatus) -> LabStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record
