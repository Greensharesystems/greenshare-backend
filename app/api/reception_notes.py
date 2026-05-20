import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, get_current_principal, require_roles
from app.db.database import get_db
from app.schemas.reception_note import NextReceptionNoteIdResponse, ReceptionNoteCreate, ReceptionNoteResponse
from app.services import reception_note_service


router = APIRouter(prefix="/reception-notes", tags=["reception-notes"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ReceptionNoteResponse])
def list_reception_notes(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> list[ReceptionNoteResponse]:
	return reception_note_service.list_reception_notes(db, current_user)


@router.get("/next-id", response_model=NextReceptionNoteIdResponse)
def get_next_reception_note_id(
	customerId: str = Query(...),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> NextReceptionNoteIdResponse:
	try:
		return reception_note_service.get_next_reception_note_id(db, customerId)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=ReceptionNoteResponse, status_code=status.HTTP_201_CREATED)
def create_reception_note(
	payload: ReceptionNoteCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> ReceptionNoteResponse:
	try:
		return reception_note_service.create_reception_note(db, payload, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{reception_note_id}/pdf/view")
def view_reception_note_pdf(
	reception_note_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_reception_note_pdf_response(reception_note_id, "inline", db, current_user)


@router.get("/{reception_note_id}/pdf/download")
def download_reception_note_pdf(
	reception_note_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> Response:
	return build_reception_note_pdf_response(reception_note_id, "attachment", db, current_user)


def build_reception_note_pdf_response(
	reception_note_id: str,
	content_disposition: str,
	db: Session,
	current_user: AuthPrincipal,
) -> Response:
	logger.info(
		"Reception note PDF route hit: reference=%s disposition=%s user=%s",
		reception_note_id,
		content_disposition,
		current_user.identifier,
	)
	try:
		filename, pdf_bytes = reception_note_service.generate_reception_note_pdf(db, reception_note_id, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except RuntimeError as exc:
		logger.exception("Reception note PDF generation failed for '%s'", reception_note_id)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to generate reception note PDF.",
		) from exc

	logger.info(
		"Reception note PDF generated successfully: reference=%s filename=%s bytes=%d disposition=%s",
		reception_note_id,
		filename,
		len(pdf_bytes),
		content_disposition,
	)
	return Response(
		content=pdf_bytes,
		media_type="application/pdf",
		headers={"Content-Disposition": f'{content_disposition}; filename="{filename}"'},
	)


@router.delete("/{rnid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reception_note(
	rnid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> Response:
	try:
		reception_note_service.delete_reception_note(db, rnid, current_user)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
