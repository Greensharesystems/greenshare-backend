from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, get_current_principal, require_roles
from app.db.database import get_db
from app.schemas.dashboard import CustomerDashboardResponse, DashboardResponse
from app.services import dashboard_service


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
customer_router = APIRouter(prefix="/customer", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
	role: str = Query(...),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(get_current_principal),
) -> DashboardResponse:
	try:
		if current_user.role != role.strip().lower():
			raise ValueError("You are not allowed to access that dashboard.")

		return dashboard_service.get_dashboard(db, current_user)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/admin", response_model=DashboardResponse)
def get_admin_dashboard(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> DashboardResponse:
	return dashboard_service.get_dashboard(db, current_user)


@router.get("/employee", response_model=DashboardResponse)
def get_employee_dashboard(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("employee")),
) -> DashboardResponse:
	return dashboard_service.get_dashboard(db, current_user)


@router.get("/customer", response_model=DashboardResponse)
def get_customer_dashboard(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("customer")),
) -> DashboardResponse:
	return dashboard_service.get_dashboard(db, current_user)


@customer_router.get("/dashboard", response_model=CustomerDashboardResponse)
def get_customer_dashboard_summary(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("customer")),
) -> CustomerDashboardResponse:
	try:
		return dashboard_service.get_customer_dashboard(db, current_user.customerId or current_user.identifier)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@customer_router.get("/reports/export/csv")
def export_customer_reports_csv(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("customer")),
) -> Response:
	try:
		filename, csv_content = dashboard_service.export_customer_reports_csv(
			db,
			current_user.customerId or current_user.identifier,
		)
		return Response(
			content=csv_content,
			media_type="text/csv; charset=utf-8",
			headers={"Content-Disposition": f'attachment; filename="{filename}"'},
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
