from datetime import datetime

from app.api.reception_notes import download_reception_note_pdf, view_reception_note_pdf
from app.core.auth import AuthPrincipal
from app.models.reception_note import ReceptionNote
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
	assert context["issued_by"] == "Greenshare Operations"


def test_view_reception_note_pdf_returns_inline_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: int, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_note_id == 7
		assert current_principal == principal
		return "RNID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	response = view_reception_note_pdf(7, db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="RNID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_download_reception_note_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_note_pdf(db, reception_note_id: int, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_note_id == 7
		assert current_principal == principal
		return "RNID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_note_service, "generate_reception_note_pdf", fake_generate_reception_note_pdf)

	response = download_reception_note_pdf(7, db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RNID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"