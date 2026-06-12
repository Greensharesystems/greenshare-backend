import pytest
from fastapi import HTTPException
from datetime import datetime

from app.api.reception_certificates import download_reception_certificate_pdf, view_reception_certificate_pdf
from app.core.auth import AuthPrincipal
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.services import reception_certificate_service


def test_view_reception_certificate_pdf_returns_inline_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert reception_certificate_reference == "RCID-0001-0001"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test", True

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf_with_cache_status", fake_generate_reception_certificate_pdf)

	response = view_reception_certificate_pdf("RCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="RCID-0001-0001.pdf"'
	assert response.headers["x-certificate-pdf-cache"] == "HIT"
	assert response.headers["x-certificate-pdf-regenerated"] == "No"
	assert response.body == b"%PDF-test"


def test_reception_certificate_pdf_cache_key_changes_when_pdf_content_changes() -> None:
	context = {
		"document_title": "RCID-0001-0001",
		"rcid": "RCID-0001-0001",
		"total_quantity": "100 Tons",
	}
	updated_context = {**context, "total_quantity": "101 Tons"}

	first_key = reception_certificate_service.build_reception_certificate_pdf_cache_key("RCID-0001-0001", context)
	second_key = reception_certificate_service.build_reception_certificate_pdf_cache_key("RCID-0001-0001", updated_context)

	assert first_key.startswith("RCID-0001-0001:")
	assert first_key != second_key


def test_download_reception_certificate_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert reception_certificate_reference == "RCID-0001-0001"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test", False

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf_with_cache_status", fake_generate_reception_certificate_pdf)

	response = download_reception_certificate_pdf("RCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RCID-0001-0001.pdf"'
	assert response.headers["x-certificate-pdf-cache"] == "MISS"
	assert response.headers["x-certificate-pdf-regenerated"] == "Yes"
	assert response.body == b"%PDF-test"


def test_build_reception_certificate_pdf_response_accepts_numeric_id(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert reception_certificate_reference == "7"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test", True

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf_with_cache_status", fake_generate_reception_certificate_pdf)

	response = download_reception_certificate_pdf("7", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_view_reception_certificate_pdf_returns_clean_internal_error(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		raise RuntimeError("sensitive traceback text")

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf_with_cache_status", fake_generate_reception_certificate_pdf)

	with pytest.raises(HTTPException) as exc_info:
		view_reception_certificate_pdf("RCID-0001-0001", db=None, current_user=principal)

	assert exc_info.value.status_code == 500
	assert exc_info.value.detail == "Failed to generate reception certificate PDF."


def test_reception_certificate_pdf_uses_persistent_cache_without_regeneration(monkeypatch, tmp_path) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)
	reception_certificate = ReceptionCertificate(
		id=9,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@example.com",
		waste_streams=[{"code": "WS-001", "name": "Mixed Plastic", "wasteClass": "Non-Hazardous", "physicalState": "Solid", "quantity": "1200", "quantityUnit": "kg"}],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Mixed Plastic",
		waste_stream_quantity="1200 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	class FakeDb:
		commit_count = 0

		def add(self, _value):
			return None

		def commit(self):
			self.commit_count += 1

	fake_db = FakeDb()
	render_calls = 0

	def fake_generate_pdf(*_args, **_kwargs):
		nonlocal render_calls
		render_calls += 1
		return b"%PDF-rendered-once"

	monkeypatch.setenv("CERTIFICATE_PDF_CACHE_DIR", str(tmp_path))
	monkeypatch.setattr(reception_certificate_service.reception_certificate_repository, "get_reception_certificate_by_rcid", lambda _db, _rcid: reception_certificate)
	monkeypatch.setattr(reception_certificate_service.reception_note_repository, "get_reception_note_by_rnid", lambda _db, _rnid: reception_note)
	monkeypatch.setattr(reception_certificate_service, "generate_pdf", fake_generate_pdf)

	first_filename, first_pdf, first_cache_hit = reception_certificate_service.generate_reception_certificate_pdf_with_cache_status(fake_db, "RCID-0001-0001", principal)
	second_filename, second_pdf, second_cache_hit = reception_certificate_service.generate_reception_certificate_pdf_with_cache_status(fake_db, "RCID-0001-0001", principal)

	assert first_filename == "RCID-0001-0001.pdf"
	assert second_filename == "RCID-0001-0001.pdf"
	assert first_pdf == b"%PDF-rendered-once"
	assert second_pdf == b"%PDF-rendered-once"
	assert first_cache_hit is False
	assert second_cache_hit is True
	assert render_calls == 1
	assert fake_db.commit_count == 1
	assert reception_certificate.pdf_file_path
	assert reception_certificate.pdf_cache_fingerprint

	restarted_certificate = ReceptionCertificate(
		id=9,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=reception_certificate.created_at,
	)
	restarted_certificate.pdf_file_path = reception_certificate.pdf_file_path
	restarted_certificate.pdf_cache_fingerprint = reception_certificate.pdf_cache_fingerprint
	restarted_certificate.pdf_generated_at = reception_certificate.pdf_generated_at

	monkeypatch.setattr(reception_certificate_service.reception_certificate_repository, "get_reception_certificate_by_rcid", lambda _db, _rcid: restarted_certificate)
	monkeypatch.setattr(reception_certificate_service, "generate_pdf", lambda *_args, **_kwargs: pytest.fail("stored PDF should survive restart without rendering"))

	restart_filename, restart_pdf, restart_cache_hit = reception_certificate_service.generate_reception_certificate_pdf_with_cache_status(fake_db, "RCID-0001-0001", principal)

	assert restart_filename == "RCID-0001-0001.pdf"
	assert restart_pdf == b"%PDF-rendered-once"
	assert restart_cache_hit is True
	assert fake_db.commit_count == 1