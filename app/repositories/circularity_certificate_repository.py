from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circularity_certificate import CircularityCertificate


def get_circularity_certificates(db: Session) -> list[CircularityCertificate]:
	statement = select(CircularityCertificate).order_by(CircularityCertificate.created_at.desc(), CircularityCertificate.id.desc())
	return list(db.scalars(statement).all())


def get_circularity_certificates_by_customer_id(db: Session, customer_id: str) -> list[CircularityCertificate]:
	statement = (
		select(CircularityCertificate)
		.where(CircularityCertificate.cid == customer_id)
		.order_by(CircularityCertificate.created_at.desc(), CircularityCertificate.id.desc())
	)
	return list(db.scalars(statement).all())


def get_circularity_certificates_by_owner_identifier(db: Session, owner_identifier: str) -> list[CircularityCertificate]:
	statement = (
		select(CircularityCertificate)
		.where(CircularityCertificate.owner_identifier == owner_identifier)
		.order_by(CircularityCertificate.created_at.desc(), CircularityCertificate.id.desc())
	)
	return list(db.scalars(statement).all())


def get_circularity_certificate_ids(db: Session) -> list[str]:
	statement = select(CircularityCertificate.ccid)
	return [ccid for ccid in db.scalars(statement).all() if ccid]


def get_circularity_certificate_by_ccid(db: Session, ccid: str) -> CircularityCertificate | None:
	statement = select(CircularityCertificate).where(CircularityCertificate.ccid.in_(get_ccid_aliases(ccid)))
	return db.scalar(statement)


def get_circularity_certificate_by_id(db: Session, circularity_certificate_id: int) -> CircularityCertificate | None:
	statement = select(CircularityCertificate).where(CircularityCertificate.id == circularity_certificate_id)
	return db.scalar(statement)


def create_circularity_certificate(db: Session, circularity_certificate: CircularityCertificate) -> CircularityCertificate:
	db.add(circularity_certificate)
	db.commit()
	db.refresh(circularity_certificate)
	return circularity_certificate


def delete_circularity_certificate(db: Session, circularity_certificate: CircularityCertificate) -> None:
	db.delete(circularity_certificate)


def get_ccid_aliases(ccid: str) -> list[str]:
	normalized_ccid = ccid.strip().upper()
	aliases = {normalized_ccid}

	if normalized_ccid.startswith("CCID-"):
		aliases.add(normalized_ccid.replace("CCID-", "CC-", 1))
	elif normalized_ccid.startswith("CC-"):
		aliases.add(normalized_ccid.replace("CC-", "CCID-", 1))

	parts = normalized_ccid.split("-")
	if len(parts) == 3 and parts[1].isdigit():
		padded_customer = f"{int(parts[1]):04d}"
		aliases.add(f"CCID-{padded_customer}-{parts[2]}")
		aliases.add(f"CC-{int(parts[1])}-{parts[2]}")

	if len(parts) == 5 and parts[1].isdigit():
		padded_customer = f"{int(parts[1]):04d}"
		aliases.add(f"CCID-{padded_customer}-{parts[2]}-{parts[3]}-{parts[4]}")
		aliases.add(f"CC-{int(parts[1])}-{parts[2]}-{parts[3]}-{parts[4]}")

	return list(aliases)
