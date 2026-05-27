from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.crm.lead import Lead


def get_leads(db: Session) -> list[Lead]:
	statement = (
		select(Lead)
		.options(
			selectinload(Lead.lab_status),
			selectinload(Lead.proposal_status),
			selectinload(Lead.lead_status),
		)
		.order_by(Lead.created_at.desc(), Lead.id.desc())
	)
	return list(db.scalars(statement).all())


def get_lead_by_lid(db: Session, lid: str) -> Lead | None:
	statement = (
		select(Lead)
		.options(
			selectinload(Lead.lab_status),
			selectinload(Lead.proposal_status),
			selectinload(Lead.lead_status),
		)
		.where(Lead.lid == lid)
	)
	return db.scalar(statement)


def get_lead_lids(db: Session) -> list[str]:
	statement = select(Lead.lid)
	return [lid for lid in db.scalars(statement).all() if lid]


def create_lead(db: Session, lead: Lead) -> Lead:
	db.add(lead)
	db.commit()
	db.refresh(lead)
	return lead


def update_lead(db: Session, lead: Lead) -> Lead:
	db.add(lead)
	db.commit()
	db.refresh(lead)
	return lead
