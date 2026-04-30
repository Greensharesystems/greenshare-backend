from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reception_note import ReceptionNote


def get_reception_notes(db: Session) -> list[ReceptionNote]:
	statement = select(ReceptionNote).order_by(ReceptionNote.created_at.desc(), ReceptionNote.id.desc())
	return list(db.scalars(statement).all())


def get_reception_notes_by_customer_id(db: Session, customer_id: str) -> list[ReceptionNote]:
	statement = (
		select(ReceptionNote)
		.where(ReceptionNote.customer_id == customer_id)
		.order_by(ReceptionNote.created_at.desc(), ReceptionNote.id.desc())
	)
	return list(db.scalars(statement).all())


def get_reception_notes_by_owner_identifier(db: Session, owner_identifier: str) -> list[ReceptionNote]:
	statement = (
		select(ReceptionNote)
		.where(ReceptionNote.owner_identifier == owner_identifier)
		.order_by(ReceptionNote.created_at.desc(), ReceptionNote.id.desc())
	)
	return list(db.scalars(statement).all())


def get_reception_note_ids(db: Session) -> list[str]:
	statement = select(ReceptionNote.rnid)
	return [rnid for rnid in db.scalars(statement).all() if rnid]


def get_reception_note_by_rnid(db: Session, rnid: str) -> ReceptionNote | None:
	statement = select(ReceptionNote).where(ReceptionNote.rnid.in_(get_rnid_aliases(rnid)))
	return db.scalar(statement)


def get_reception_note_by_id(db: Session, reception_note_id: int) -> ReceptionNote | None:
	statement = select(ReceptionNote).where(ReceptionNote.id == reception_note_id)
	return db.scalar(statement)


def create_reception_note(db: Session, reception_note: ReceptionNote) -> ReceptionNote:
	db.add(reception_note)
	db.commit()
	db.refresh(reception_note)
	return reception_note


def delete_reception_note(db: Session, reception_note: ReceptionNote) -> None:
	db.delete(reception_note)


def get_rnid_aliases(rnid: str) -> list[str]:
	normalized_rnid = rnid.strip().upper()
	aliases = {normalized_rnid}

	if normalized_rnid.startswith("RNID-"):
		aliases.add(normalized_rnid.replace("RNID-", "RN-", 1))
	elif normalized_rnid.startswith("RN-"):
		aliases.add(normalized_rnid.replace("RN-", "RNID-", 1))

	parts = normalized_rnid.split("-")
	if len(parts) == 3 and parts[1].isdigit():
		padded_customer = f"{int(parts[1]):04d}"
		aliases.add(f"RNID-{padded_customer}-{parts[2]}")
		aliases.add(f"RN-{int(parts[1])}-{parts[2]}")

	return list(aliases)
