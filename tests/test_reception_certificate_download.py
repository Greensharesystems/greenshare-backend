from app.api.reception_certificates import download_reception_certificate_pdf, view_reception_certificate_pdf
from app.core.auth import AuthPrincipal
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

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_certificate_reference == "RCID-0001-0001"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf", fake_generate_reception_certificate_pdf)

	response = view_reception_certificate_pdf("RCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="RCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_download_reception_certificate_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_certificate_reference == "RCID-0001-0001"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf", fake_generate_reception_certificate_pdf)

	response = download_reception_certificate_pdf("RCID-0001-0001", db=None, current_user=principal)


def test_build_reception_certificate_pdf_response_accepts_numeric_id(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_reception_certificate_pdf(db, reception_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert reception_certificate_reference == "7"
		assert current_principal == principal
		return "RCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(reception_certificate_service, "generate_reception_certificate_pdf", fake_generate_reception_certificate_pdf)

	response = download_reception_certificate_pdf("7", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="RCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"