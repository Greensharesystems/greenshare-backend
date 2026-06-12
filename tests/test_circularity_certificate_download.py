import pytest
from fastapi import HTTPException
from datetime import datetime

from app.api.circularity_certificates import download_circularity_certificate_pdf, view_circularity_certificate_pdf
from app.core.auth import AuthPrincipal
from app.models.circularity_certificate import CircularityCertificate
from app.models.reception_certificate import ReceptionCertificate
from app.services import circularity_certificate_service


def test_view_circularity_certificate_pdf_returns_inline_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert circularity_certificate_reference == "CCID-0001-0001"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test", True

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf_with_cache_status", fake_generate_circularity_certificate_pdf)

	response = view_circularity_certificate_pdf("CCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="CCID-0001-0001.pdf"'
	assert response.headers["x-certificate-pdf-cache"] == "HIT"
	assert response.headers["x-certificate-pdf-regenerated"] == "No"
	assert response.body == b"%PDF-test"


def test_circularity_certificate_pdf_cache_key_changes_when_pdf_content_changes() -> None:
	context = {
		"document_title": "CCID-0001-0001",
		"ccid": "CCID-0001-0001",
		"total_quantity": "100 Tons",
	}
	updated_context = {**context, "total_quantity": "101 Tons"}

	first_key = circularity_certificate_service.build_circularity_certificate_pdf_cache_key(
		"CCID-0001-0001",
		context,
		"2026-04-15T10:00:00Z",
	)
	second_key = circularity_certificate_service.build_circularity_certificate_pdf_cache_key(
		"CCID-0001-0001",
		updated_context,
		"2026-04-15T10:00:00Z",
	)

	assert first_key.startswith("CCID-0001-0001:2026-04-15T10:00:00Z:")
	assert first_key != second_key


def test_download_circularity_certificate_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert circularity_certificate_reference == "CCID-0001-0001"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test", False

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf_with_cache_status", fake_generate_circularity_certificate_pdf)

	response = download_circularity_certificate_pdf("CCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="CCID-0001-0001.pdf"'
	assert response.headers["x-certificate-pdf-cache"] == "MISS"
	assert response.headers["x-certificate-pdf-regenerated"] == "Yes"
	assert response.body == b"%PDF-test"


def test_view_circularity_certificate_pdf_returns_clean_internal_error(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		raise RuntimeError("sensitive traceback text")

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf_with_cache_status", fake_generate_circularity_certificate_pdf)

	with pytest.raises(HTTPException) as exc_info:
		view_circularity_certificate_pdf("CCID-0001-0001", db=None, current_user=principal)

	assert exc_info.value.status_code == 500
	assert exc_info.value.detail == "Failed to generate circularity certificate PDF."


def test_build_circularity_certificate_pdf_response_accepts_numeric_id(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes, bool]:
		assert db is None
		assert circularity_certificate_reference == "13"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test", True

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf_with_cache_status", fake_generate_circularity_certificate_pdf)

	response = download_circularity_certificate_pdf("13", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="CCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_circularity_certificate_pdf_uses_persistent_cache_without_regeneration(monkeypatch, tmp_path) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)
	reception_certificate = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="",
		linked_rnids=[],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		waste_stream_name="Mixed Plastic",
		waste_stream_class="Non-Hazardous",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
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
	monkeypatch.setattr(circularity_certificate_service.circularity_certificate_repository, "get_circularity_certificate_by_ccid", lambda _db, _ccid: circularity_certificate)
	monkeypatch.setattr(circularity_certificate_service.reception_certificate_repository, "get_reception_certificate_by_rcid", lambda _db, _rcid: reception_certificate)
	monkeypatch.setattr(circularity_certificate_service, "generate_pdf", fake_generate_pdf)

	first_filename, first_pdf, first_cache_hit = circularity_certificate_service.generate_circularity_certificate_pdf_with_cache_status(fake_db, "CCID-0001-0001", principal)
	second_filename, second_pdf, second_cache_hit = circularity_certificate_service.generate_circularity_certificate_pdf_with_cache_status(fake_db, "CCID-0001-0001", principal)

	assert first_filename == "CCID-0001-0001.pdf"
	assert second_filename == "CCID-0001-0001.pdf"
	assert first_pdf == b"%PDF-rendered-once"
	assert second_pdf == b"%PDF-rendered-once"
	assert first_cache_hit is False
	assert second_cache_hit is True
	assert render_calls == 1
	assert fake_db.commit_count == 1
	assert circularity_certificate.pdf_file_path
	assert circularity_certificate.pdf_cache_fingerprint

	restarted_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=circularity_certificate.created_at,
	)
	restarted_certificate.pdf_file_path = circularity_certificate.pdf_file_path
	restarted_certificate.pdf_cache_fingerprint = circularity_certificate.pdf_cache_fingerprint
	restarted_certificate.pdf_generated_at = circularity_certificate.pdf_generated_at

	monkeypatch.setattr(circularity_certificate_service.circularity_certificate_repository, "get_circularity_certificate_by_ccid", lambda _db, _ccid: restarted_certificate)
	monkeypatch.setattr(circularity_certificate_service, "generate_pdf", lambda *_args, **_kwargs: pytest.fail("stored PDF should survive restart without rendering"))

	restart_filename, restart_pdf, restart_cache_hit = circularity_certificate_service.generate_circularity_certificate_pdf_with_cache_status(fake_db, "CCID-0001-0001", principal)

	assert restart_filename == "CCID-0001-0001.pdf"
	assert restart_pdf == b"%PDF-rendered-once"
	assert restart_cache_hit is True
	assert fake_db.commit_count == 1