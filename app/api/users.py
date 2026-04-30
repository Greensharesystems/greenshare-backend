from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.user import NextUserIdResponse, UserCreate, UserCsvExportRequest, UserPasswordUpdate, UserResponse, UserUpdate
from app.services import user_service


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> list[UserResponse]:
	return user_service.list_users(db)


@router.get("/next-id", response_model=NextUserIdResponse)
def get_next_user_id(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> NextUserIdResponse:
	return user_service.get_next_user_id(db)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
	payload: UserCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> UserResponse:
	try:
		return user_service.create_user(db, payload)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/export/csv")
def export_users_csv(
	payload: UserCsvExportRequest,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> Response:
	filename, csv_content = user_service.export_users_csv(db, payload.userIds)
	return Response(
		content=csv_content,
		media_type="text/csv; charset=utf-8",
		headers={"Content-Disposition": f'attachment; filename="{filename}"'},
	)


@router.get("/{user_id}", response_model=UserResponse)
def get_user_for_management(
	user_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> UserResponse:
	try:
		return user_service.get_user_for_management(db, user_id)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
	user_id: str,
	payload: UserUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> UserResponse:
	try:
		return user_service.update_user(db, user_id, payload)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
	user_id: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> Response:
	try:
		user_service.delete_user(db, user_id)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
	user_id: str,
	payload: UserPasswordUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> Response:
	try:
		user_service.reset_user_password(db, user_id, payload.password)
		return Response(status_code=status.HTTP_204_NO_CONTENT)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
