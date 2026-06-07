from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm.wds_status import WdsStatus


def get_by_lead_id(db: Session, lead_id: int) -> WdsStatus | None:
	statement = select(WdsStatus).where(WdsStatus.lead_id == lead_id)
	return db.scalar(statement)


def create(db: Session, status_record: WdsStatus) -> WdsStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record


def update(db: Session, status_record: WdsStatus) -> WdsStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record
