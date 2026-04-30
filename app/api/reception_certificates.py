from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, get_current_principal, require_roles
from app.db.database import get_db
from app.schemas.reception_certificate import (
	NextReceptionCertificateIdResponse,
	ReceptionCertificateCreate,
	ReceptionCertificateResponse,
)
from app.services import reception_certificate_service


router = APIRouter(prefix="/reception-certificates", tags=["reception-certificates"])


@router.get("", response_model=list[ReceptionCertificateResponse])
def list_reception_certificates(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> list[ReceptionCertificateResponse]:
	return reception_certificate_service.list_reception_certificates(db, current_user)


@router.get("/next-id", response_model=NextReceptionCertificateIdResponse)
def get_next_reception_certificate_id(
	rnid: str = Query(...),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> NextReceptionCertificateIdResponse:
	try:
		return reception_certificate_service.get_next_reception_certificate_id(db, rnid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=ReceptionCertificateResponse, status_code=status.HTTP_201_CREATED)
def create_reception_certificate(
	payload: ReceptionCertificateCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> ReceptionCertificateResponse:
	try:
		return reception_certificate_service.create_reception_certificate(db, payload, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{reception_certificate_reference}/pdf/view")
def view_reception_certificate_pdf(
	reception_certificate_reference: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_reception_certificate_pdf_response(reception_certificate_reference, "inline", db, current_user)


@router.get("/{reception_certificate_reference}/pdf/download")
def download_reception_certificate_pdf(
	reception_certificate_reference: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_reception_certificate_pdf_response(reception_certificate_reference, "attachment", db, current_user)


def build_reception_certificate_pdf_response(
	reception_certificate_reference: int | str,
	content_disposition: str,
	db: Session,
	current_user: AuthPrincipal,
) -> Response:
	try:
		filename, pdf_bytes = reception_certificate_service.generate_reception_certificate_pdf(db, reception_certificate_reference, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

	return Response(
		content=pdf_bytes,
		media_type="application/pdf",
		headers={"Content-Disposition": f'{content_disposition}; filename="{filename}"'},
	)


@router.delete("/{rcid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reception_certificate(
	rcid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> Response:
	try:
		reception_certificate_service.delete_reception_certificate(db, rcid, current_user)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
