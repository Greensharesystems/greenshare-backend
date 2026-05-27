from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm.proposal_status import ProposalStatus


def get_by_lead_id(db: Session, lead_id: int) -> ProposalStatus | None:
	statement = select(ProposalStatus).where(ProposalStatus.lead_id == lead_id)
	return db.scalar(statement)


def create(db: Session, status_record: ProposalStatus) -> ProposalStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record


def update(db: Session, status_record: ProposalStatus) -> ProposalStatus:
	db.add(status_record)
	db.commit()
	db.refresh(status_record)
	return status_record
