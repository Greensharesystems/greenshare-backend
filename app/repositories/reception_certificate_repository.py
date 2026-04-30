from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reception_certificate import ReceptionCertificate


def get_reception_certificates(db: Session) -> list[ReceptionCertificate]:
	statement = select(ReceptionCertificate).order_by(ReceptionCertificate.created_at.desc(), ReceptionCertificate.id.desc())
	return list(db.scalars(statement).all())


def get_reception_certificates_by_customer_id(db: Session, customer_id: str) -> list[ReceptionCertificate]:
	statement = (
		select(ReceptionCertificate)
		.where(ReceptionCertificate.customer_id == customer_id)
		.order_by(ReceptionCertificate.created_at.desc(), ReceptionCertificate.id.desc())
	)
	return list(db.scalars(statement).all())


def get_reception_certificates_by_owner_identifier(db: Session, owner_identifier: str) -> list[ReceptionCertificate]:
	statement = (
		select(ReceptionCertificate)
		.where(ReceptionCertificate.owner_identifier == owner_identifier)
		.order_by(ReceptionCertificate.created_at.desc(), ReceptionCertificate.id.desc())
	)
	return list(db.scalars(statement).all())


def get_reception_certificate_ids(db: Session) -> list[str]:
	statement = select(ReceptionCertificate.rcid)
	return [rcid for rcid in db.scalars(statement).all() if rcid]


def get_reception_certificate_by_rcid(db: Session, rcid: str) -> ReceptionCertificate | None:
	statement = select(ReceptionCertificate).where(ReceptionCertificate.rcid.in_(get_rcid_aliases(rcid)))
	return db.scalar(statement)


def get_reception_certificate_by_id(db: Session, reception_certificate_id: int) -> ReceptionCertificate | None:
	statement = select(ReceptionCertificate).where(ReceptionCertificate.id == reception_certificate_id)
	return db.scalar(statement)


def create_reception_certificate(db: Session, reception_certificate: ReceptionCertificate) -> ReceptionCertificate:
	db.add(reception_certificate)
	db.commit()
	db.refresh(reception_certificate)
	return reception_certificate


def delete_reception_certificate(db: Session, reception_certificate: ReceptionCertificate) -> None:
	db.delete(reception_certificate)


def get_rcid_aliases(rcid: str) -> list[str]:
	normalized_rcid = rcid.strip().upper()
	aliases = {normalized_rcid}

	if normalized_rcid.startswith("RCID-"):
		aliases.add(normalized_rcid.replace("RCID-", "RC-", 1))
	elif normalized_rcid.startswith("RC-"):
		aliases.add(normalized_rcid.replace("RC-", "RCID-", 1))

	parts = normalized_rcid.split("-")
	if len(parts) == 3 and parts[1].isdigit():
		padded_customer = f"{int(parts[1]):04d}"
		aliases.add(f"RCID-{padded_customer}-{parts[2]}")
		aliases.add(f"RC-{int(parts[1])}-{parts[2]}")

	if len(parts) == 4 and parts[1].isdigit():
		padded_customer = f"{int(parts[1]):04d}"
		aliases.add(f"RCID-{padded_customer}-{parts[2]}-{parts[3]}")
		aliases.add(f"RC-{int(parts[1])}-{parts[2]}-{parts[3]}")

	return list(aliases)
