from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from app.db.database import Base
from app.models.circularity_certificate import CircularityCertificate
from app.models.customer import Customer
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from io import StringIO
import csv

from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service


def build_customer() -> Customer:
	return Customer(
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
		password_hash="CUSTOMER_AUTH_DISABLED",
		last_active="No user access yet",
	)


def test_create_customer_user_allows_same_email_as_customer_contact() -> None:
	engine = create_engine("sqlite:///:memory:")
	TestingSessionLocal = sessionmaker(bind=engine)
	Base.metadata.create_all(bind=engine)
	db: Session = TestingSessionLocal()

	db.add(build_customer())
	db.commit()

	created_user = user_service.create_user(
		db,
		UserCreate(
			userIdDate="09 Apr 2026",
			userId="UID-0001",
			firstName="Jane",
			lastName="Doe",
			email="jane@example.com",
			position="Sustainability Lead",
			department="Operations",
			mobile="0501234567",
			password="strong-pass-123",
			company="Acme Recycling",
			role="Customer",
			customerId="CID-0001",
		),
	)

	assert created_user.email == "jane@example.com"
	assert created_user.customerId == "CID-0001"
	assert created_user.position == "Sustainability Lead"
	assert created_user.department == "Operations"
	assert created_user.mobile == "0501234567"

	db.close()
	Base.metadata.drop_all(bind=engine)


def test_export_users_csv_includes_exact_columns_in_order(monkeypatch) -> None:
	monkeypatch.setattr(
		user_service,
		"list_users",
		lambda db: [
			UserResponse(
				id=1,
				userIdDate="09 Apr 2026",
				userId="UID-0001",
				userName="Jane Doe",
				company="Acme Recycling",
				role="Customer",
				lastActive="Today, 10:30",
				email="jane@example.com",
				position="Manager",
				department="Operations",
				mobile="0501234567",
				customerId="CID-0001",
			),
		],
	)

	filename, csv_content = user_service.export_users_csv(db=None)
	reader = csv.DictReader(StringIO(csv_content))
	rows = list(reader)

	assert filename == "users-export.csv"
	assert reader.fieldnames == user_service.USER_CSV_COLUMNS
	assert rows == [{
		"User ID Date": "09 Apr 2026",
		"User ID": "UID-0001",
		"User Name": "Jane Doe",
		"User Email": "jane@example.com",
		"Company": "Acme Recycling",
		"Role": "Customer",
		"Last Active": "Today, 10:30",
	}]


def test_export_users_csv_filters_and_preserves_requested_order(monkeypatch) -> None:
	monkeypatch.setattr(
		user_service,
		"list_users",
		lambda db: [
			UserResponse(
				id=1,
				userIdDate="09 Apr 2026",
				userId="UID-0001",
				userName="Alpha User",
				company="Zero Waste",
				role="Admin",
				lastActive="Today, 10:00",
				email="alpha@example.com",
			),
			UserResponse(
				id=2,
				userIdDate="10 Apr 2026",
				userId="UID-0002",
				userName="Beta User",
				company="Acme Recycling",
				role="Customer",
				lastActive="Today, 11:00",
				email="beta@example.com",
				customerId="CID-0001",
			),
		],
	)

	_, csv_content = user_service.export_users_csv(db=None, user_ids=["UID-0002", "UID-0001"])
	reader = csv.DictReader(StringIO(csv_content))
	rows = list(reader)

	assert [row["User ID"] for row in rows] == ["UID-0002", "UID-0001"]


def test_create_customer_user_requires_focal_person_fields() -> None:
	engine = create_engine("sqlite:///:memory:")
	TestingSessionLocal = sessionmaker(bind=engine)
	Base.metadata.create_all(bind=engine)
	db: Session = TestingSessionLocal()

	db.add(build_customer())
	db.commit()

	with pytest.raises(ValueError, match="Customer users must include position, department, and mobile details."):
		user_service.create_user(
			db,
			UserCreate(
				userIdDate="09 Apr 2026",
				userId="UID-0001",
				firstName="Jane",
				lastName="Doe",
				email="jane@example.com",
				position=None,
				department="Operations",
				mobile="",
				password="strong-pass-123",
				company="Acme Recycling",
				role="Customer",
				customerId="CID-0001",
			),
		)

	db.close()
	Base.metadata.drop_all(bind=engine)


def test_update_user_updates_customer_role_fields() -> None:
	engine = create_engine("sqlite:///:memory:")
	TestingSessionLocal = sessionmaker(bind=engine)
	Base.metadata.create_all(bind=engine)
	db: Session = TestingSessionLocal()

	db.add(build_customer())
	db.commit()

	created_user = user_service.create_user(
		db,
		UserCreate(
			userIdDate="09 Apr 2026",
			userId="UID-0001",
			firstName="Jane",
			lastName="Doe",
			email="jane@example.com",
			position="Sustainability Lead",
			department="Operations",
			mobile="0501234567",
			password="strong-pass-123",
			company="Acme Recycling",
			role="Customer",
			customerId="CID-0001",
		),
	)

	updated_user = user_service.update_user(
		db,
		created_user.userId,
		UserUpdate(
			firstName="Janet",
			lastName="Dover",
			email="janet@example.com",
			position="Director",
			department="Sustainability",
			mobile="0507654321",
			company="Acme Recycling",
			role="Customer",
			customerId="CID-0001",
		),
	)

	assert updated_user.userName == "Janet Dover"
	assert updated_user.email == "janet@example.com"
	assert updated_user.position == "Director"
	assert updated_user.department == "Sustainability"
	assert updated_user.mobile == "0507654321"

	db.close()
	Base.metadata.drop_all(bind=engine)