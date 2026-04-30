from app.api.circularity_certificates import download_circularity_certificate_pdf, view_circularity_certificate_pdf
from app.core.auth import AuthPrincipal
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

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert circularity_certificate_reference == "CCID-0001-0001"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf", fake_generate_circularity_certificate_pdf)

	response = view_circularity_certificate_pdf("CCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'inline; filename="CCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_download_circularity_certificate_pdf_returns_attachment_headers(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert circularity_certificate_reference == "CCID-0001-0001"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf", fake_generate_circularity_certificate_pdf)

	response = download_circularity_certificate_pdf("CCID-0001-0001", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="CCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"


def test_build_circularity_certificate_pdf_response_accepts_numeric_id(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)

	def fake_generate_circularity_certificate_pdf(db, circularity_certificate_reference: int | str, current_principal: AuthPrincipal) -> tuple[str, bytes]:
		assert db is None
		assert circularity_certificate_reference == "13"
		assert current_principal == principal
		return "CCID-0001-0001.pdf", b"%PDF-test"

	monkeypatch.setattr(circularity_certificate_service, "generate_circularity_certificate_pdf", fake_generate_circularity_certificate_pdf)

	response = download_circularity_certificate_pdf("13", db=None, current_user=principal)

	assert response.media_type == "application/pdf"
	assert response.headers["content-disposition"] == 'attachment; filename="CCID-0001-0001.pdf"'
	assert response.body == b"%PDF-test"