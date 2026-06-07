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
		.where(Lead.deleted_at.is_(None))
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
		.where(Lead.deleted_at.is_(None))
	)
	return db.scalar(statement)


def lid_exists(db: Session, lid: str) -> bool:
	"""Check if a LID exists in the table, including soft-deleted rows."""
	statement = select(Lead.lid).where(Lead.lid == lid).limit(1)
	return db.scalar(statement) is not None


def get_lead_lids(db: Session) -> list[str]:
	"""Return all LIDs including soft-deleted, so next-ID generation skips used IDs."""
	statement = select(Lead.lid)
	return [lid for lid in db.scalars(statement).all() if lid]


def soft_delete_lead(db: Session, lead: Lead) -> None:
	from datetime import datetime, timezone
	lead.deleted_at = datetime.now(timezone.utc)
	db.commit()


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
