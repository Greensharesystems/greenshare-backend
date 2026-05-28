from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, get_customer_scope_id, require_roles
from app.db.database import get_db
from app.schemas.customer import CustomerCreate, CustomerCsvExportRequest, CustomerResponse, CustomerSearchResponse, CustomerUpdate, NextCustomerIdResponse
from app.services import customer_service


router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> list[CustomerResponse]:
	return customer_service.list_customers(db)


@router.get("/search", response_model=list[CustomerSearchResponse])
def search_customers(
	q: str = Query("", min_length=0),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> list[CustomerSearchResponse]:
	return customer_service.search_customers(db, q)


@router.get("/me", response_model=CustomerResponse)
def get_customer_profile(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("customer")),
) -> CustomerResponse:
	try:
		return customer_service.get_customer_profile(db, get_customer_scope_id(current_user))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/next-id", response_model=NextCustomerIdResponse)
def get_next_customer_id(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> NextCustomerIdResponse:
	return customer_service.get_next_customer_id(db)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer_for_management(
	customer_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin", "employee")),
) -> CustomerResponse:
	try:
		return customer_service.get_customer_for_management(db, customer_id)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/export/csv")
def export_customers_csv(
	payload: CustomerCsvExportRequest,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> Response:
	filename, csv_content = customer_service.export_customers_csv(db, payload.customerIds)
	return Response(
		content=csv_content,
		media_type="text/csv; charset=utf-8",
		headers={"Content-Disposition": f'attachment; filename="{filename}"'},
	)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
	payload: CustomerCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> CustomerResponse:
	try:
		return customer_service.create_customer(db, payload)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
	customer_id: str,
	payload: CustomerUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> CustomerResponse:
	try:
		return customer_service.update_customer(db, customer_id, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
	customer_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> Response:
	try:
		customer_service.delete_customer(db, customer_id)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
