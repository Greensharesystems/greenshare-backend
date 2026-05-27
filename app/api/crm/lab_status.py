from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.crm.lab_status_schema import LabStatusCreateUpdate, LabStatusResponse
from app.services.crm import lab_status_service


router = APIRouter(prefix="/crm/leads/{lid}/lab-status", tags=["crm-leads"])


@router.get("", response_model=LabStatusResponse)
def get_lab_status(
	lid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LabStatusResponse:
	try:
		return lab_status_service.get_lab_status(db, lid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("", response_model=LabStatusResponse)
def update_lab_status(
	lid: str,
	payload: LabStatusCreateUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LabStatusResponse:
	try:
		return lab_status_service.update_lab_status(db, lid, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc
