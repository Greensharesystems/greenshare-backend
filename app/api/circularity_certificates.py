import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, get_current_principal, require_roles
from app.db.database import get_db
from app.schemas.circularity_certificate import (
	CircularityCertificateCreate,
	CircularityCertificateResponse,
	NextCircularityCertificateIdResponse,
)
from app.services import circularity_certificate_service


router = APIRouter(prefix="/circularity-certificates", tags=["circularity-certificates"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[CircularityCertificateResponse])
def list_circularity_certificates(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> list[CircularityCertificateResponse]:
	return circularity_certificate_service.list_circularity_certificates(db, current_user)


@router.get("/next-id", response_model=NextCircularityCertificateIdResponse)
def get_next_circularity_certificate_id(
	rcid: str = Query(...),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> NextCircularityCertificateIdResponse:
	try:
		return circularity_certificate_service.get_next_circularity_certificate_id(db, rcid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=CircularityCertificateResponse, status_code=status.HTTP_201_CREATED)
def create_circularity_certificate(
	payload: CircularityCertificateCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> CircularityCertificateResponse:
	try:
		return circularity_certificate_service.create_circularity_certificate(db, payload, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{circularity_certificate_reference}/pdf/view")
def view_circularity_certificate_pdf(
	circularity_certificate_reference: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_circularity_certificate_pdf_response(circularity_certificate_reference, "inline", db, current_user)


@router.get("/{circularity_certificate_reference}/pdf/download")
def download_circularity_certificate_pdf(
	circularity_certificate_reference: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_circularity_certificate_pdf_response(circularity_certificate_reference, "attachment", db, current_user)


def build_circularity_certificate_pdf_response(
	circularity_certificate_reference: int | str,
	content_disposition: str,
	db: Session,
	current_user: AuthPrincipal,
) -> Response:
	started_at = time.perf_counter()
	logger.info(
		"Circularity certificate PDF route hit: reference=%s disposition=%s user=%s",
		circularity_certificate_reference,
		content_disposition,
		current_user.identifier,
	)
	try:
		filename, pdf_bytes, cache_hit = circularity_certificate_service.generate_circularity_certificate_pdf_with_cache_status(
			db,
			circularity_certificate_reference,
			current_user,
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except RuntimeError as exc:
		logger.exception(
			"Circularity certificate PDF generation failed for '%s' with disposition '%s'",
			circularity_certificate_reference,
			content_disposition,
		)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to generate circularity certificate PDF.",
		) from exc

	logger.info(
		"circularity_certificate_pdf_served",
		extra={
			"certificate_id": str(circularity_certificate_reference),
			"pdf_filename": filename,
			"size_bytes": len(pdf_bytes),
			"disposition": content_disposition,
			"cache_hit": cache_hit,
			"pdf_regenerated": not cache_hit,
			"view_time_seconds": round(time.perf_counter() - started_at, 4) if content_disposition == "inline" else None,
			"download_time_seconds": round(time.perf_counter() - started_at, 4) if content_disposition == "attachment" else None,
		},
	)
	return Response(
		content=pdf_bytes,
		media_type="application/pdf",
		headers={
			"Content-Disposition": f'{content_disposition}; filename="{filename}"',
			"X-Certificate-PDF-Cache": "HIT" if cache_hit else "MISS",
			"X-Certificate-PDF-Regenerated": "No" if cache_hit else "Yes",
		},
	)


@router.delete("/{ccid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_circularity_certificate(
	ccid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> Response:
	try:
		circularity_certificate_service.delete_circularity_certificate(db, ccid, current_user)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
