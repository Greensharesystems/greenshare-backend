from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.crm.lead_status_schema import LeadStatusCreateUpdate, LeadStatusResponse
from app.services.crm import lead_status_service


router = APIRouter(prefix="/crm/leads/{lid}/lead-status", tags=["crm-leads"])


@router.get("", response_model=LeadStatusResponse)
def get_lead_status(
	lid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadStatusResponse:
	try:
		return lead_status_service.get_lead_status(db, lid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("", response_model=LeadStatusResponse)
def update_lead_status(
	lid: str,
	payload: LeadStatusCreateUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadStatusResponse:
	try:
		return lead_status_service.update_lead_status(db, lid, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc
