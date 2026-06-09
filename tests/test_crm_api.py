from collections.abc import Generator
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthPrincipal, create_access_token
from app.core.config import hash_password
from app.db.database import Base, get_db
from app.models.customer import Customer
from app.models.crm.lab_status import LabStatus
from app.models.crm.lead import Lead
from app.models.crm.lead_status import LeadStatus
from app.models.crm.proposal_status import ProposalStatus
from app.services.crm import lead_service
from app.models.user import User
from main import app


TEST_ADMIN_EMAIL = "crm-admin@example.com"
TEST_ADMIN_PASSWORD = "greenshare"
TEST_ADMIN_ID = "UID-CRM-0001"


@pytest.fixture()
def client() -> Generator[tuple[TestClient, Session], None, None]:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
	Base.metadata.create_all(bind=engine)

	db = TestingSessionLocal()
	db.add(
		User(
			user_id_date="20260527",
			user_id=TEST_ADMIN_ID,
			first_name="CRM",
			last_name="Admin",
			email=TEST_ADMIN_EMAIL,
			position="Admin",
			department="CRM",
			mobile_phone="0000000000",
			company="Zero Waste",
			role="Admin",
			customer_id=None,
			password_hash=hash_password(TEST_ADMIN_PASSWORD),
			last_active="Today, 09:00",
		),
	)
	db.commit()

	def override_get_db() -> Generator[Session, None, None]:
		try:
			yield db
		finally:
			pass

	app.dependency_overrides[get_db] = override_get_db

	with TestClient(app) as test_client:
		yield test_client, db

	app.dependency_overrides.clear()
	db.close()
	Base.metadata.drop_all(bind=engine)
	engine.dispose()


def auth_headers() -> dict[str, str]:
	principal = AuthPrincipal(
		email=TEST_ADMIN_EMAIL,
		displayName="CRM Admin",
		identifier=TEST_ADMIN_ID,
		accountType="user",
		role="admin",
		customerId=None,
	)
	return {"Authorization": f"Bearer {create_access_token(principal)}"}


def employee_auth_headers(db: Session) -> dict[str, str]:
	employee_id = "UID-CRM-EMP1"
	employee_email = "crm-employee@example.com"
	db.add(
		User(
			user_id_date="20260527",
			user_id=employee_id,
			first_name="CRM",
			last_name="Employee",
			email=employee_email,
			position="Employee",
			department="CRM",
			mobile_phone="0000000000",
			company="Zero Waste",
			role="Employee",
			customer_id=None,
			password_hash=hash_password(TEST_ADMIN_PASSWORD),
			last_active="Today, 09:00",
		),
	)
	db.commit()
	principal = AuthPrincipal(
		email=employee_email,
		displayName="CRM Employee",
		identifier=employee_id,
		accountType="user",
		role="employee",
		customerId=None,
	)
	return {"Authorization": f"Bearer {create_access_token(principal)}"}


def create_lead(client: TestClient, lid: str = "LID-0001", lead_date: str = "27-05-2026") -> dict[str, object]:
	response = client.post(
		"/crm/leads",
		headers=auth_headers(),
		json={
			"lid": lid,
			"cid": "CID-0001",
			"customer_name": "Green Loop Trading LLC",
			"source": "Other",
			"source_detail": "CRM API Test",
			"assigned_to": "Other",
			"assigned_to_other": "API Tester",
			"waste_stream": "Plastic Recycling",
			"waste_class": "Others",
			"waste_class_other": "Mixed Recyclables",
			"est_qty": 25.0,
			"unit": "Others",
			"unit_other": "Bales",
			"comments": "Created from API test.",
			"lead_date": lead_date,
		},
	)

	assert response.status_code == 201
	return response.json()


def seed_customer(db: Session, customer_id: str = "CID-0001", company_name: str = "Green Loop Trading LLC") -> Customer:
	customer = Customer(
		customer_id_date="27-05-2026",
		customer_id=customer_id,
		company_name=company_name,
		company_emirate="Dubai",
		area="JAFZA",
		office_address="Unit 1",
		website="https://example.com",
		sector="Recycling",
		contact_person_name="Contact Person",
		contact_person_position="Manager",
		contact_person_department="Sales",
		contact_person_email=f"{customer_id.lower()}@example.com",
		contact_person_office_phone="0000000000",
		contact_person_mobile_phone="0000000001",
		focal_persons_json="[]",
		password_hash="disabled",
		last_active="No user access yet",
	)
	db.add(customer)
	db.commit()
	db.refresh(customer)
	return customer


def test_next_id_requires_authentication(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client

	response = test_client.get("/crm/leads/next-id")

	assert response.status_code == 401
	assert response.json() == {"detail": "Authentication is required."}


def test_next_id_returns_first_sequential_value_when_empty(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client

	response = test_client.get("/crm/leads/next-id", headers=auth_headers())

	assert response.status_code == 200
	assert response.json() == {"next_lid": "LID-0001"}


def test_create_and_list_leads(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	created_lead = create_lead(test_client)

	list_response = test_client.get("/crm/leads", headers=auth_headers())

	assert list_response.status_code == 200
	assert created_lead["lid"] == "LID-0001"
	assert list_response.json()[0]["lid"] == "LID-0001"
	assert list_response.json()[0]["customer_name"] == "Green Loop Trading LLC"


def test_get_lead_by_lid_returns_created_lead(monkeypatch: pytest.MonkeyPatch, client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	monkeypatch.setattr(lead_service, "get_current_date", lambda: date(2026, 5, 27))
	create_lead(test_client)

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lid"] == "LID-0001"
	assert response.json()["lab_status"] == "Pending"
	assert response.json()["proposal_status"] == "Pending"
	assert response.json()["lead_status"] == "Open"
	assert response.json()["lab_status_days"] == 0
	assert response.json()["proposal_status_days"] == 0
	assert response.json()["lead_status_days"] == 0


def test_get_status_endpoints_return_defaults_before_first_save(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client)

	lab_response = test_client.get("/crm/leads/LID-0001/lab-status", headers=auth_headers())
	proposal_response = test_client.get("/crm/leads/LID-0001/proposal-status", headers=auth_headers())
	lead_status_response = test_client.get("/crm/leads/LID-0001/lead-status", headers=auth_headers())

	assert lab_response.status_code == 200
	assert proposal_response.status_code == 200
	assert lead_status_response.status_code == 200
	assert lab_response.json()["lab_id"] == ""
	assert lab_response.json()["decision"] == ""
	assert proposal_response.json()["pid"] == ""
	assert proposal_response.json()["status"] == ""
	assert lead_status_response.json()["status"] == "Open"


def test_lead_response_uses_backend_day_calculations(monkeypatch: pytest.MonkeyPatch, client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	create_lead(test_client)
	monkeypatch.setattr(lead_service, "get_current_date", lambda: date(2026, 5, 30))

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lab_status"] == "Pending"
	assert response.json()["proposal_status"] == "Pending"
	assert response.json()["lead_status"] == "Open"
	assert response.json()["lab_status_days"] == 3
	assert response.json()["proposal_status_days"] == 3
	assert response.json()["lead_status_days"] == 3

	lead = db.query(Lead).filter(Lead.lid == "LID-0001").one()
	lead.lab_status = LabStatus(
		lead_id=lead.id,
		lid=lead.lid,
		lab_id="LAB-0001",
		decision="Accept",
		comments="Approved in test.",
		chemist_name="CRM Admin",
		decision_date=datetime(2026, 5, 29, tzinfo=timezone.utc),
	)
	lead.proposal_status = ProposalStatus(
		lead_id=lead.id,
		lid=lead.lid,
		pid="PID-0001",
		status="Sent",
		comments="Sent in test.",
		updated_by="CRM Admin",
		status_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
	)
	lead.lead_status = LeadStatus(
		lead_id=lead.id,
		lid=lead.lid,
		status="Won",
		comments="Won in test.",
		updated_by="CRM Admin",
		closed_date=datetime(2026, 6, 2, tzinfo=timezone.utc),
	)
	db.add(lead)
	db.commit()

	updated_response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert updated_response.status_code == 200
	assert updated_response.json()["lab_status"] == "Accept"
	assert updated_response.json()["proposal_status"] == "Sent"
	assert updated_response.json()["lead_status"] == "Won"
	assert updated_response.json()["lab_status_days"] == 2
	assert updated_response.json()["proposal_status_days"] == 4
	assert updated_response.json()["lead_status_days"] == 6


def test_customer_search_endpoint_returns_cid_and_name(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	seed_customer(db, customer_id="CID-0001", company_name="Green Loop Trading")
	seed_customer(db, customer_id="CID-0042", company_name="Loopback Metals")

	response = test_client.get("/customers/search?q=loop", headers=auth_headers())

	assert response.status_code == 200
	assert response.json() == [
		{"cid": "CID-0001", "customer_name": "Green Loop Trading"},
		{"cid": "CID-0042", "customer_name": "Loopback Metals"},
	]


def test_next_id_advances_after_create(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client, "LID-0001")

	response = test_client.get("/crm/leads/next-id", headers=auth_headers())

	assert response.status_code == 200
	assert response.json() == {"next_lid": "LID-0002"}


@pytest.mark.parametrize(
	("existing_lid", "expected_next"),
	[
		("LID-0001", "LID-0002"),
		("LID-0009", "LID-0010"),
		("LID-0099", "LID-0100"),
		("LID-0100", "LID-0101"),
		("LID-0999", "LID-1000"),
		("LID-1000", "LID-1001"),
		("LID-9999", "LID-10000"),
		("LID-10000", "LID-10001"),
	],
)
def test_next_id_keeps_minimum_four_digit_width(
	existing_lid: str,
	expected_next: str,
	client: tuple[TestClient, Session],
) -> None:
	# Lead IDs must be zero-padded to a minimum of 4 digits and grow naturally
	# beyond that (never forced to 5 digits from the start).
	test_client, _db = client
	create_lead(test_client, lid=existing_lid)

	response = test_client.get("/crm/leads/next-id", headers=auth_headers())

	assert response.status_code == 200
	assert response.json() == {"next_lid": expected_next}


def test_stream_lab_status_is_independent_per_stream(client: tuple[TestClient, Session]) -> None:
	# Lab decisions are stream level: updating SN-001 must never change SN-002.
	test_client, _db = client
	response = test_client.post(
		"/crm/leads",
		headers=auth_headers(),
		json={
			"lid": "LID-0011",
			"cid": "CID-0001",
			"customer_name": "Union Steel Processing",
			"source": "Sales Visit",
			"assigned_to": "Imran",
			"streams": [
				{"waste_stream_name": "Paint Cans", "waste_class": "Hazardous", "est_qty": 50, "unit": "Tons"},
				{"waste_stream_name": "Oily Paper", "waste_class": "Hazardous", "est_qty": 50, "unit": "Tons"},
			],
			"comments": None,
			"lead_date": "27-05-2026",
		},
	)
	assert response.status_code == 201
	assert [stream["stream_no"] for stream in response.json()["streams"]] == ["SN-001", "SN-002"]

	update = test_client.put(
		"/crm/leads/LID-0011/streams/SN-001/lab-status",
		headers=auth_headers(),
		json={"decision": "Accept", "decision_other": None, "comments": "Cleared", "chemist_name": "Lab Tech"},
	)
	assert update.status_code == 200
	assert update.json()["stream_no"] == "SN-001"
	assert update.json()["decision"] == "Accept"

	sn1 = test_client.get("/crm/leads/LID-0011/streams/SN-001/lab-status", headers=auth_headers())
	sn2 = test_client.get("/crm/leads/LID-0011/streams/SN-002/lab-status", headers=auth_headers())

	assert sn1.json()["decision"] == "Accept"
	assert sn2.json()["decision"] == ""


def test_stream_codes_generate_by_category_and_soft_delete(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client

	first_hs = test_client.get("/crm/stream-codes/next-code?category=Hazardous%20Stream", headers=auth_headers())
	assert first_hs.status_code == 200
	assert first_hs.json() == {"next_stream_code": "HS-1"}

	hs_create = test_client.post(
		"/crm/stream-codes",
		headers=auth_headers(),
		json={
			"stream_code": "HS-1",
			"category": "Hazardous Stream",
			"stream_name": "Paint Cans",
			"description": "Hazardous paint container waste",
			"status": "Active",
		},
	)
	assert hs_create.status_code == 201
	assert hs_create.json()["stream_code"] == "HS-1"
	assert hs_create.json()["category"] == "Hazardous Stream"

	next_hs = test_client.get("/crm/stream-codes/next-code?category=Hazardous%20Stream", headers=auth_headers())
	assert next_hs.status_code == 200
	assert next_hs.json() == {"next_stream_code": "HS-2"}

	nhs_create = test_client.post(
		"/crm/stream-codes",
		headers=auth_headers(),
		json={
			"stream_code": "NHS-1",
			"category": "Non-Hazardous Stream",
			"stream_name": "OCC",
			"description": None,
			"status": "Active",
		},
	)
	assert nhs_create.status_code == 201
	next_nhs = test_client.get("/crm/stream-codes/next-code?category=Non-Hazardous%20Stream", headers=auth_headers())
	assert next_nhs.status_code == 200
	assert next_nhs.json() == {"next_stream_code": "NHS-2"}

	rs_create = test_client.post(
		"/crm/stream-codes",
		headers=auth_headers(),
		json={
			"stream_code": "RS-1",
			"category": "Recyclable Stream",
			"stream_name": "Scrap Metal",
			"description": "Reusable metal stream",
			"status": "Active",
		},
	)
	assert rs_create.status_code == 201
	next_rs = test_client.get("/crm/stream-codes/next-code?category=Recyclable%20Stream", headers=auth_headers())
	assert next_rs.status_code == 200
	assert next_rs.json() == {"next_stream_code": "RS-2"}

	by_code = test_client.get("/crm/stream-codes/HS-1", headers=auth_headers())
	by_id = test_client.get(f"/crm/stream-codes/{hs_create.json()['id']}", headers=auth_headers())
	assert by_code.status_code == 200
	assert by_id.status_code == 200
	assert by_code.json()["id"] == by_id.json()["id"]

	update = test_client.put(
		"/crm/stream-codes/HS-1",
		headers=auth_headers(),
		json={"stream_name": "Paint Solids", "description": "Updated", "status": "Inactive"},
	)
	assert update.status_code == 200
	assert update.json()["stream_name"] == "Paint Solids"
	assert update.json()["status"] == "Inactive"

	delete = test_client.delete("/crm/stream-codes/HS-1", headers=auth_headers())
	assert delete.status_code == 204

	list_response = test_client.get("/crm/stream-codes", headers=auth_headers())
	assert list_response.status_code == 200
	assert {row["stream_code"] for row in list_response.json()} == {"NHS-1", "RS-1"}

	get_deleted = test_client.get("/crm/stream-codes/HS-1", headers=auth_headers())
	assert get_deleted.status_code == 404

	next_hs_after_delete = test_client.get("/crm/stream-codes/next-code?category=Hazardous%20Stream", headers=auth_headers())
	assert next_hs_after_delete.status_code == 200
	assert next_hs_after_delete.json() == {"next_stream_code": "HS-2"}


def test_stream_code_management_is_admin_only(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	employee_headers = employee_auth_headers(db)

	response = test_client.get("/crm/stream-codes", headers=employee_headers)
	assert response.status_code == 403

	create_response = test_client.post(
		"/crm/stream-codes",
		headers=employee_headers,
		json={
			"stream_code": "HS-1",
			"category": "Hazardous Stream",
			"stream_name": "Paint Cans",
			"status": "Active",
		},
	)
	assert create_response.status_code == 403


def test_update_and_get_lab_status(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client)

	update_response = test_client.put(
		"/crm/leads/LID-0001/lab-status",
		headers=auth_headers(),
		json={
			"lab_id": "LAB-0001",
			"decision": "Accept",
			"decision_other": None,
			"comments": "Approved in test.",
			"chemist_name": "CRM Admin",
		},
	)
	get_response = test_client.get("/crm/leads/LID-0001/lab-status", headers=auth_headers())

	assert update_response.status_code == 200
	assert get_response.status_code == 200
	assert get_response.json()["lab_id"] == "LAB-0001"
	assert get_response.json()["decision"] == "Accept"


def test_update_and_get_proposal_status(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client)

	update_response = test_client.put(
		"/crm/leads/LID-0001/proposal-status",
		headers=auth_headers(),
		json={
			"pid": "PID-0001",
			"status": "Sent",
			"status_other": None,
			"comments": "Proposal sent in test.",
			"updated_by": "CRM Admin",
		},
	)
	get_response = test_client.get("/crm/leads/LID-0001/proposal-status", headers=auth_headers())

	assert update_response.status_code == 200
	assert get_response.status_code == 200
	assert get_response.json()["pid"] == "PID-0001"
	assert get_response.json()["status"] == "Sent"


def test_update_and_get_lead_status(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client)

	update_response = test_client.put(
		"/crm/leads/LID-0001/lead-status",
		headers=auth_headers(),
		json={
			"status": "Won",
			"status_other": None,
			"comments": "Lead won in test.",
			"updated_by": "CRM Admin",
		},
	)
	get_response = test_client.get("/crm/leads/LID-0001/lead-status", headers=auth_headers())

	assert update_response.status_code == 200
	assert get_response.status_code == 200
	assert get_response.json()["status"] == "Won"


def test_invalid_lid_returns_clean_404s(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client

	lead_response = test_client.get("/crm/leads/LID-9999", headers=auth_headers())
	lab_response = test_client.get("/crm/leads/LID-9999/lab-status", headers=auth_headers())
	proposal_response = test_client.get("/crm/leads/LID-9999/proposal-status", headers=auth_headers())
	lead_status_response = test_client.get("/crm/leads/LID-9999/lead-status", headers=auth_headers())

	assert lead_response.status_code == 404
	assert lab_response.status_code == 404
	assert proposal_response.status_code == 404
	assert lead_status_response.status_code == 404
	assert lead_response.json() == {"detail": "That lead could not be found."}
	assert lab_response.json() == {"detail": "That lead could not be found."}
	assert proposal_response.json() == {"detail": "That lead could not be found."}
	assert lead_status_response.json() == {"detail": "That lead could not be found."}


def test_new_lead_today_has_zero_days(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	today_str = date.today().strftime("%d-%m-%Y")
	create_lead(test_client, lead_date=today_str)

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lab_status"] == "Pending"
	assert response.json()["proposal_status"] == "Pending"
	assert response.json()["lead_status"] == "Open"
	assert response.json()["lab_status_days"] == 0
	assert response.json()["proposal_status_days"] == 0
	assert response.json()["lead_status_days"] == 0


def test_historical_lead_days_count_to_today(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client, lead_date="01-03-2026")

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	expected_days = (date.today() - date(2026, 3, 1)).days
	assert response.status_code == 200
	assert response.json()["lab_status_days"] == expected_days
	assert response.json()["proposal_status_days"] == expected_days
	assert response.json()["lead_status_days"] == expected_days


def test_lab_decision_stops_days_at_decision_date(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	create_lead(test_client, lead_date="01-03-2026")

	lead = db.query(Lead).filter(Lead.lid == "LID-0001").one()
	lead.lab_status = LabStatus(
		lead_id=lead.id,
		lid=lead.lid,
		lab_id="LAB-0001",
		decision="Accept",
		chemist_name="Test Chemist",
		decision_date=datetime(2026, 3, 4, tzinfo=timezone.utc),
	)
	db.add(lead)
	db.commit()

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lab_status"] == "Accept"
	assert response.json()["lab_status_days"] == 3


def test_proposal_submission_stops_days_at_status_date(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	create_lead(test_client, lead_date="01-03-2026")

	lead = db.query(Lead).filter(Lead.lid == "LID-0001").one()
	lead.proposal_status = ProposalStatus(
		lead_id=lead.id,
		lid=lead.lid,
		pid="PID-0001",
		status="Sent",
		updated_by="Test User",
		status_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
	)
	db.add(lead)
	db.commit()

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["proposal_status"] == "Sent"
	assert response.json()["proposal_status_days"] == 5


def test_lead_status_closure_stops_days_at_closed_date(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	create_lead(test_client, lead_date="01-03-2026")

	lead = db.query(Lead).filter(Lead.lid == "LID-0001").one()
	lead.lead_status = LeadStatus(
		lead_id=lead.id,
		lid=lead.lid,
		status="Won",
		updated_by="Test User",
		closed_date=datetime(2026, 3, 30, tzinfo=timezone.utc),
	)
	db.add(lead)
	db.commit()

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lead_status"] == "Won"
	assert response.json()["lead_status_days"] == 29


def test_list_and_detail_endpoints_return_same_days(client: tuple[TestClient, Session]) -> None:
	test_client, db = client
	create_lead(test_client, lead_date="01-03-2026")

	lead = db.query(Lead).filter(Lead.lid == "LID-0001").one()
	lead.lab_status = LabStatus(
		lead_id=lead.id,
		lid=lead.lid,
		lab_id="LAB-0001",
		decision="Accept",
		chemist_name="Test Chemist",
		decision_date=datetime(2026, 3, 4, tzinfo=timezone.utc),
	)
	lead.proposal_status = ProposalStatus(
		lead_id=lead.id,
		lid=lead.lid,
		pid="PID-0001",
		status="Sent",
		updated_by="Test User",
		status_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
	)
	lead.lead_status = LeadStatus(
		lead_id=lead.id,
		lid=lead.lid,
		status="Won",
		updated_by="Test User",
		closed_date=datetime(2026, 3, 30, tzinfo=timezone.utc),
	)
	db.add(lead)
	db.commit()

	list_response = test_client.get("/crm/leads", headers=auth_headers())
	detail_response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert list_response.status_code == 200
	assert detail_response.status_code == 200

	list_lead = list_response.json()[0]
	detail_lead = detail_response.json()

	assert list_lead["lab_status_days"] == detail_lead["lab_status_days"] == 3
	assert list_lead["proposal_status_days"] == detail_lead["proposal_status_days"] == 5
	assert list_lead["lead_status_days"] == detail_lead["lead_status_days"] == 29