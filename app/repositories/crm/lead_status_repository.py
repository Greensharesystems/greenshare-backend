from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm.lead_status import LeadStatus


def get_by_lead_id(db: Session, lead_id: int) -> LeadStatus | None:
	statement = select(LeadStatus).where(LeadStatus.lead_id == lead_id)
	return db.scalar(statement)


def create(db: Session, status_record: LeadStatus) -> LeadStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record


def update(db: Session, status_record: LeadStatus) -> LeadStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record
