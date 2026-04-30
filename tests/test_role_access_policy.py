from types import SimpleNamespace

from app.core.auth import AuthPrincipal
from app.services import circularity_certificate_service, reception_certificate_service, reception_note_service


def test_employee_can_view_shared_reception_notes(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="UID-0002",
		accountType="user",
		role="employee",
		customerId=None,
	)
	shared_notes = [
		SimpleNamespace(rnid="RNID-0001-0001", customer_id="CID-0001"),
		SimpleNamespace(rnid="RNID-0002-0001", customer_id="CID-0002"),
	]

	monkeypatch.setattr(reception_note_service.reception_note_repository, "get_reception_notes", lambda db: shared_notes)

	assert reception_note_service.get_visible_reception_notes(db=None, principal=principal) == shared_notes


def test_customer_reception_note_access_stays_isolated() -> None:
	principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="UID-0003",
		accountType="user",
		role="customer",
		customerId="CID-0001",
	)
	owned_note = SimpleNamespace(customer_id="CID-0001")
	other_note = SimpleNamespace(customer_id="CID-0002")

	assert reception_note_service.can_access_reception_note(owned_note, principal) is True
	assert reception_note_service.can_access_reception_note(other_note, principal) is False


def test_employee_can_access_shared_reception_certificate_and_circularity_certificate() -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="UID-0002",
		accountType="user",
		role="employee",
		customerId=None,
	)
	reception_certificate = SimpleNamespace(customer_id="CID-0002")
	circularity_certificate = SimpleNamespace(cid="CID-0003")

	assert reception_certificate_service.can_access_reception_certificate(reception_certificate, principal) is True
	assert circularity_certificate_service.can_access_circularity_certificate(circularity_certificate, principal) is True