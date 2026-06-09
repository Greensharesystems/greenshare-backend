from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, require_roles
from app.db.database import get_db
from app.schemas.crm.stream_code_schema import (
	NextStreamCodeResponse,
	StreamCodeCreate,
	StreamCodeResponse,
	StreamCodeUpdate,
)
from app.services.crm import stream_code_service


router = APIRouter(prefix="/crm/stream-codes", tags=["crm-stream-codes"])


@router.get("", response_model=list[StreamCodeResponse])
def list_stream_codes(
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> list[StreamCodeResponse]:
	return stream_code_service.list_stream_codes(db)


@router.get("/next-code", response_model=NextStreamCodeResponse)
def get_next_stream_code(
	category: str = Query(...),
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> NextStreamCodeResponse:
	try:
		return NextStreamCodeResponse(next_stream_code=stream_code_service.get_next_stream_code(db, category))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=StreamCodeResponse, status_code=status.HTTP_201_CREATED)
def create_stream_code(
	payload: StreamCodeCreate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> StreamCodeResponse:
	try:
		return stream_code_service.create_stream_code(db, payload)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
	except IntegrityError:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Stream Code with that code already exists.") from None


@router.get("/{id_or_code}", response_model=StreamCodeResponse)
def get_stream_code(
	id_or_code: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> StreamCodeResponse:
	try:
		return stream_code_service.get_stream_code(db, id_or_code)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{id_or_code}", response_model=StreamCodeResponse)
def update_stream_code(
	id_or_code: str,
	payload: StreamCodeUpdate,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> StreamCodeResponse:
	try:
		return stream_code_service.update_stream_code(db, id_or_code, payload)
	except ValueError as exc:
		status_code = status.HTTP_404_NOT_FOUND if "could not be found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=status_code, detail=str(exc)) from exc
	except IntegrityError:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Stream Code with that code already exists.") from None


@router.delete("/{id_or_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stream_code(
	id_or_code: str,
	db: Session = Depends(get_db),
	current_user: AuthPrincipal = Depends(require_roles("admin")),
) -> None:
	try:
		stream_code_service.delete_stream_code(db, id_or_code)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
