from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.crm.lead_stream_schema import (
	LabStreamStatusCreateUpdate,
	LabStreamStatusResponse,
	LeadStreamCreate,
	LeadStreamResponse,
)
from app.services.crm import lead_stream_service


router = APIRouter(tags=["crm-leads"])


@router.get("/crm/leads/{lid}/streams", response_model=list[LeadStreamResponse])
def list_streams(
	lid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> list[LeadStreamResponse]:
	try:
		return lead_stream_service.list_streams(db, lid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/crm/leads/{lid}/streams", response_model=LeadStreamResponse, status_code=status.HTTP_201_CREATED)
def add_stream(
	lid: str,
	payload: LeadStreamCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadStreamResponse:
	try:
		return lead_stream_service.add_stream(db, lid, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/crm/leads/{lid}/streams/{stream_no}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stream(
	lid: str,
	stream_no: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> None:
	try:
		lead_stream_service.remove_stream(db, lid, stream_no)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/crm/leads/{lid}/streams/{stream_no}/lab-status", response_model=LabStreamStatusResponse)
def get_lab_stream_status(
	lid: str,
	stream_no: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LabStreamStatusResponse:
	try:
		return lead_stream_service.get_lab_stream_status(db, lid, stream_no)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/crm/leads/{lid}/streams/{stream_no}/lab-status", response_model=LabStreamStatusResponse)
def update_lab_stream_status(
	lid: str,
	stream_no: str,
	payload: LabStreamStatusCreateUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LabStreamStatusResponse:
	try:
		return lead_stream_service.update_lab_stream_status(db, lid, stream_no, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() or "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc
