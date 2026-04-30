import csv
from io import StringIO
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.customer import Customer
from app.models.circularity_certificate import CircularityCertificate
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.models.user import User
from app.repositories import customer_repository, user_repository
from app.schemas.customer import CustomerResponse, CustomerUpdate
from app.services import customer_service


def test_export_customers_csv_includes_exact_columns_in_order(monkeypatch) -> None:
	monkeypatch.setattr(
		customer_service,
		"list_customers",
		lambda db: [
			CustomerResponse(
				id=1,
				customerIdDate="2026-04-01",
				customerId="CID-0001",
				companyName="Acme Recycling",
				companyEmirate="Dubai",
				area="Jebel Ali",
				officeAddress="Plot 10",
				website="acme.example",
				sector="Recycling",
				contactPersonName="Jane Doe",
				contactPersonPosition="Manager",
				contactPersonDepartment="Operations",
				contactPersonEmail="jane@example.com",
				contactPersonOfficePhone="111",
				contactPersonMobilePhone="222",
				focalPersons=[],
				lastActive="Today, 10:30",
			),
		],
	)

	filename, csv_content = customer_service.export_customers_csv(db=None)
	reader = csv.DictReader(StringIO(csv_content))
	rows = list(reader)

	assert filename == "customers-export.csv"
	assert reader.fieldnames == customer_service.CUSTOMER_CSV_COLUMNS
	assert rows == [{
		"Company Name": "Acme Recycling",
		"Emirate": "Dubai",
		"Area": "Jebel Ali",
		"Office Location": "Plot 10",
		"Website": "acme.example",
		"Sector": "Recycling",
		"Contact Person": "Jane Doe",
		"Position": "Manager",
		"Department": "Operations",
		"Email": "jane@example.com",
		"Office Phone": "111",
		"Mobile Phone": "222",
	}]


def test_export_customers_csv_filters_and_preserves_requested_order(monkeypatch) -> None:
	monkeypatch.setattr(
		customer_service,
		"list_customers",
		lambda db: [
			CustomerResponse(
				id=1,
				customerIdDate="2026-04-01",
				customerId="CID-0001",
				companyName="Alpha",
				companyEmirate="Dubai",
				area="Area A",
				officeAddress="Office A",
				website="alpha.example",
				sector="Sector A",
				contactPersonName="Person A",
				contactPersonPosition="Lead",
				contactPersonDepartment="Ops",
				contactPersonEmail="a@example.com",
				contactPersonOfficePhone="111",
				contactPersonMobilePhone="222",
				focalPersons=[],
				lastActive="Today, 09:00",
			),
			CustomerResponse(
				id=2,
				customerIdDate="2026-04-02",
				customerId="CID-0002",
				companyName="Beta",
				companyEmirate="Abu Dhabi",
				area="Area B",
				officeAddress="Office B",
				website="beta.example",
				sector="Sector B",
				contactPersonName="Person B",
				contactPersonPosition="Head",
				contactPersonDepartment="Sales",
				contactPersonEmail="b@example.com",
				contactPersonOfficePhone="333",
				contactPersonMobilePhone="444",
				focalPersons=[],
				lastActive="Today, 09:30",
			),
		],
	)

	_, csv_content = customer_service.export_customers_csv(db=None, customer_ids=["CID-0002", "CID-0001"])
	reader = csv.DictReader(StringIO(csv_content))
	rows = list(reader)

	assert [row["Company Name"] for row in rows] == ["Beta", "Alpha"]


def test_get_customer_profile_returns_company_name_from_customer_record(monkeypatch) -> None:
	customer_record = SimpleNamespace(
		id=7,
		customer_id_date="2026-04-01",
		customer_id="CID-0007",
		company_name="CPCo3",
		company_emirate="Dubai",
		area="JAFZA",
		office_address="Office 7",
		website="cpco3.example",
		sector="Recycling",
		contact_person_name="Jane Doe",
		contact_person_position="Manager",
		contact_person_department="Operations",
		contact_person_email="jane@example.com",
		contact_person_office_phone="111",
		contact_person_mobile_phone="222",
		focal_persons_json="[]",
		last_active="Today, 09:00",
	)

	monkeypatch.setattr(
		customer_service.customer_repository,
		"get_customer_by_customer_id",
		lambda db, customer_id: customer_record if customer_id == "CID-0007" else None,
	)

	profile = customer_service.get_customer_profile(db=None, customer_id="cid-0007")

	assert profile.customerId == "CID-0007"
	assert profile.companyName == "CPCo3"
	assert profile.contactPersonName == "Jane Doe"
	assert len(profile.focalPersons) == 1
	assert profile.focalPersons[0].email == "jane@example.com"


def test_delete_customer_removes_customer_account_and_all_linked_records() -> None:
	engine = create_engine("sqlite:///:memory:")
	TestingSessionLocal = sessionmaker(bind=engine)
	Base.metadata.create_all(bind=engine)
	db: Session = TestingSessionLocal()

	customer = Customer(
		customer_id_date="2026-04-01",
		customer_id="CID-0001",
		company_name="Acme Recycling",
		company_emirate="Dubai",
		area="Jebel Ali",
		office_address="Plot 10",
		website="acme.example",
		sector="Recycling",
		contact_person_name="Jane Doe",
		contact_person_position="Manager",
		contact_person_department="Operations",
		contact_person_email="jane@example.com",
		contact_person_office_phone="111",
		contact_person_mobile_phone="222",
		focal_persons_json="[]",
		password_hash="hashed-customer",
		last_active="Today, 10:00",
	)
	linked_user = User(
		user_id_date="2026-04-01",
		user_id="UID-0001",
		first_name="Jane",
		last_name="Doe",
		email="jane@example.com",
		company="Acme Recycling",
		role="Customer",
		customer_id="CID-0001",
		password_hash="hashed-user",
		last_active="Today, 10:00",
	)
	reception_note = ReceptionNote(
		rnid_date="2026-04-02",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		producing_company_name="Acme Recycling",
	)
	reception_certificate = ReceptionCertificate(
		rcid_date="2026-04-03",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
	)
	circularity_certificate = CircularityCertificate(
		ccid_date="2026-04-04",
		ccid="CCID-0001-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		secondary_ecosystem_details={"shared": {"secondaryProduct": "Materials", "secondaryLoop": "Manufacturer"}, "entries": []},
		cid="CID-0001",
	)

	db.add_all([customer, linked_user, reception_note, reception_certificate, circularity_certificate])
	db.commit()

	customer_service.delete_customer(db, "cid-0001")

	assert customer_repository.get_customer_by_customer_id(db, "CID-0001") is None
	assert customer_repository.get_customer_by_contact_email(db, "jane@example.com") is None
	assert user_repository.get_user_by_user_id(db, "UID-0001") is None
	assert user_repository.get_user_by_email(db, "jane@example.com") is None
	assert db.scalar(select(ReceptionNote.id)) is None
	assert db.scalar(select(ReceptionCertificate.id)) is None
	assert db.scalar(select(CircularityCertificate.id)) is None

	db.close()
	Base.metadata.drop_all(bind=engine)


def test_delete_customer_rolls_back_when_delete_fails(monkeypatch) -> None:
	customer = SimpleNamespace(customer_id="CID-0001")
	rollback_calls = 0

	class FailingSession:
		def delete(self, value) -> None:
			raise RuntimeError("delete failed")

		def commit(self) -> None:
			raise AssertionError("commit should not run")

		def rollback(self) -> None:
			nonlocal rollback_calls
			rollback_calls += 1

	monkeypatch.setattr(
		customer_service.customer_repository,
		"get_customer_by_customer_id",
		lambda db, customer_id: customer if customer_id == "CID-0001" else None,
	)

	with pytest.raises(RuntimeError, match="delete failed"):
		customer_service.delete_customer(FailingSession(), "CID-0001")

	assert rollback_calls == 1


def test_update_customer_updates_primary_and_secondary_focal_people() -> None:
	engine = create_engine("sqlite:///:memory:")
	TestingSessionLocal = sessionmaker(bind=engine)
	Base.metadata.create_all(bind=engine)
	db: Session = TestingSessionLocal()

	customer = Customer(
		customer_id_date="2026-04-01",
		customer_id="CID-0001",
		company_name="Acme Recycling",
		company_emirate="Dubai",
		area="Jebel Ali",
		office_address="Plot 10",
		website="acme.example",
		sector="Recycling",
		contact_person_name="Jane Doe",
		contact_person_position="Manager",
		contact_person_department="Operations",
		contact_person_email="jane@example.com",
		contact_person_office_phone="111",
		contact_person_mobile_phone="222",
		focal_persons_json="[]",
		password_hash="hashed-customer",
		last_active="Today, 10:00",
	)
	linked_user = User(
		user_id_date="2026-04-01",
		user_id="UID-0001",
		first_name="Maya",
		last_name="Stone",
		email="maya@example.com",
		company="Acme Recycling",
		role="Customer",
		customer_id="CID-0001",
		password_hash="hashed-user",
		position="Lead",
		department="Sustainability",
		mobile_phone="555",
		last_active="Today, 10:00",
	)
	db.add_all([customer, linked_user])
	db.commit()

	updated_customer = customer_service.update_customer(
		db,
		"cid-0001",
		CustomerUpdate(
			companyName="Acme Recycling LLC",
			emirate="Dubai",
			area="Jebel Ali Free Zone",
			officeLocation="Plot 11",
			website="acme-llc.example",
			sector="Advanced Recycling",
			focalPersons=[
				{
					"name": "Maya Stone",
					"position": "Lead",
					"department": "Sustainability",
					"email": "maya@example.com",
					"officePhone": "123",
					"mobilePhone": "555",
				},
				{
					"name": "Omar Noor",
					"position": "Coordinator",
					"department": "Operations",
					"email": "omar@example.com",
					"officePhone": "456",
					"mobilePhone": "789",
				},
			],
		),
	)

	assert updated_customer.companyName == "Acme Recycling LLC"
	assert updated_customer.contactPersonName == "Maya Stone"
	assert len(updated_customer.focalPersons) == 2
	assert updated_customer.focalPersons[0].hasUserAccount is True
	assert updated_customer.focalPersons[1].hasUserAccount is False

	db.close()
	Base.metadata.drop_all(bind=engine)