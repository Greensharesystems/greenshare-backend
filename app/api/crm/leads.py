from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.crm.lead_schema import LeadCreate, LeadListResponse, LeadResponse, LeadUpdate, NextLeadIdResponse

from app.services.crm import lead_service


router = APIRouter(prefix="/crm/leads", tags=["crm-leads"])


@router.get("", response_model=list[LeadListResponse])
def list_leads(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> list[LeadListResponse]:
	return lead_service.list_leads(db)


@router.get("/next-id", response_model=NextLeadIdResponse)
def get_next_lead_id(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> NextLeadIdResponse:
	return lead_service.get_next_lead_id(db)


@router.get("/{lid}", response_model=LeadResponse)
def get_lead(
	lid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadResponse:
	try:
		return lead_service.get_lead_by_lid(db, lid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(
	payload: LeadCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadResponse:
	try:
		return lead_service.create_lead(db, payload)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{lid}", response_model=LeadResponse)
def update_lead(
	lid: str,
	payload: LeadUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> LeadResponse:
	try:
		return lead_service.update_lead(db, lid, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{lid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
	lid: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> None:
	try:
		lead_service.delete_lead(db, lid)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
