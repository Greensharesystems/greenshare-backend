from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthPrincipal, create_access_token
from app.core.config import hash_password
from app.db.database import Base, get_db
from app.models.crm.lab_status import LabStatus
from app.models.crm.lead import Lead
from app.models.crm.lead_status import LeadStatus
from app.models.crm.proposal_status import ProposalStatus
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


def create_lead(client: TestClient, lid: str = "LID-0001") -> dict[str, object]:
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
			"lead_date": "27-05-2026",
		},
	)

	assert response.status_code == 201
	return response.json()


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


def test_get_lead_by_lid_returns_created_lead(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client)

	response = test_client.get("/crm/leads/LID-0001", headers=auth_headers())

	assert response.status_code == 200
	assert response.json()["lid"] == "LID-0001"
	assert response.json()["lab_status"] == "Pending"
	assert response.json()["proposal_status"] == "Draft"
	assert response.json()["lead_status"] == "Open"


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
	assert lab_response.json()["decision"] == "Not Applicable"
	assert proposal_response.json()["pid"] == ""
	assert proposal_response.json()["status"] == "Not Sent"
	assert lead_status_response.json()["status"] == "Open"


def test_next_id_advances_after_create(client: tuple[TestClient, Session]) -> None:
	test_client, _db = client
	create_lead(test_client, "LID-0001")

	response = test_client.get("/crm/leads/next-id", headers=auth_headers())

	assert response.status_code == 200
	assert response.json() == {"next_lid": "LID-0002"}


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