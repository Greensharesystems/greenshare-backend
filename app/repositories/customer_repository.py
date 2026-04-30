from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer


def get_customers(db: Session) -> list[Customer]:
	statement = select(Customer).order_by(Customer.created_at.desc(), Customer.id.desc())
	return list(db.scalars(statement).all())


def get_customer_ids(db: Session) -> list[str]:
	statement = select(Customer.customer_id)
	return [customer_id for customer_id in db.scalars(statement).all() if customer_id]


def get_customer_by_customer_id(db: Session, customer_id: str) -> Customer | None:
	statement = select(Customer).where(Customer.customer_id == customer_id)
	return db.scalar(statement)


def get_customer_by_contact_email(db: Session, email: str) -> Customer | None:
	statement = select(Customer).where(Customer.contact_person_email == email)
	return db.scalar(statement)


def create_customer(db: Session, customer: Customer) -> Customer:
	db.add(customer)
	db.commit()
	db.refresh(customer)
	return customer


def update_customer(db: Session, customer: Customer) -> Customer:
	db.add(customer)
	db.commit()
	db.refresh(customer)
	return customer


def delete_customer(db: Session, customer: Customer) -> None:
	db.delete(customer)
