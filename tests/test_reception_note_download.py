from datetime import datetime

import pytest
from fastapi import HTTPException

from app.api.reception_notes import download_reception_note_pdf, get_reception_note, view_reception_note_pdf
from app.core.auth import AuthPrincipal
from app.models.circularity_certificate import CircularityCertificate
from app.models.customer import Customer
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.models.user import User
from app.services import reception_note_service


def test_build_reception_note_pdf_context_uses_primary_waste_stream() -> None:
	reception_note = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionEmirate": "Dubai",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="999",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = reception_note_service.build_reception_note_pdf_context(reception_note)

	assert context["customer_name"] == "Acme Recycling LLC"
	assert context["vehicle_number"] == "DXB-48291"
	assert context["waste_stream_code"] == "WS-001"
	assert context["waste_stream_name"] == "Mixed Plastic"
	assert context["waste_stream_reception_date"] == "13-04-2026"
	assert context["total_quantity"] == "1200"
	assert context["waste_stream_quantity_unit"] == "kg"
	assert context["issued_by"] == "Greenshare Operations"


def test_build_reception_note_pdf_context_handles_missing_pdf_fields() -> None:
	reception_note = ReceptionNote(
		id=8,
		rnid_date="2026-04-13",
		rnid="",
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_streams=[{"quantity": "", "quantityUnit": "Tons"}],
		waste_stream_quantity="",
		rn_issued_by="Greenshare Operations",
		created_at=datetime.now(),
	)

	context = reception_note_service.build_reception_note_pdf_context(reception_note)

	assert context["rnid"] == "N/A"
	assert context["total_quantity"] == "N/A"
	assert context["waste_stream_quantity_unit"] == ""


def test_reception_note_edit_is_blocked_after_reception_certificate_is_issued(monkeypatch) -> None:
	reception_note = ReceptionNote(
		id=9,
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
	)
	issued_certificate = ReceptionCertificate(
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		status="Issued",
	)

	monkeypatch.setattr(
		reception_note_service.reception_certificate_repository,
		"get_reception_certificates",
		lambda db: [issued_certificate],
	)

	assert reception_note_service.can_edit_reception_note(db=None, reception_note=reception_note) is False


def test_reception_note_edit_is_allowed_when_reception_certificate_is_pending(monkeypatch) -> None:
	reception_note = ReceptionNote(
		id=10,
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
	)
	pending_certificate = ReceptionCertificate(
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		status="Pending",
	)

	monkeypatch.setattr(
		reception_note_service.reception_certificate_repository,
		"get_reception_certificates",
		lambda db: [pending_certificate],
	)

	assert reception_note_service.can_edit_reception_note(db=None, reception_note=reception_note) is True


def test_view_reception_note_pdf_returns_inline_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_note_id == "RNID-0001-0001"
		assert current_principal == principal
		return "RNID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	response = view_reception_note_pdf("RNID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="RNID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_get_reception_note_returns_payload(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)
	expected = object()

	def fake_get_reception_note(db, rnid: str, current_principal: AuthPrincipal):
		assert db is None
		assert rnid == "RNID-0001-0001"
		assert current_principal == principal
		return expected

	monkeypatch.setattr(reception_note_service, "get_reception_note", fake_get_reception_note)

	assert get_reception_note("RNID-0001-0001", db=None, current_user=principal) is expected


def test_download_reception_note_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_note_id == "RNID-0001-0001"
		assert current_principal == principal
		return "RNID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	response = download_reception_note_pdf("RNID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RNID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_view_reception_note_pdf_returns_not_found_for_unknown_rnid(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		raise ValueError("That reception note could not be found.")

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	with pytest.raises(HTTPException) as exc_info:
		view_reception_note_pdf("RNID-9999-9999", db=None, current_user=principal)

	assert exc_info.value.status_code == 404
	assert exc_info.value.detail == "That reception note could not be found."


def test_view_reception_note_pdf_returns_clean_internal_error(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		raise RuntimeError("sensitive traceback text")

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	with pytest.raises(HTTPException) as exc_info:
		view_reception_note_pdf("RNID-0001-0001", db=None, current_user=principal)

	assert exc_info.value.status_code == 500
	assert exc_info.value.detail == "Failed to generate reception note PDF."