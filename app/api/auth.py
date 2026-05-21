import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging_config import fingerprint_identifier
from app.db.database import get_db
from app.schemas.auth_schema import LoginRequest, LoginResponse
from app.services.auth_service import login_with_user_account


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
	subject_fingerprint = fingerprint_identifier(payload.email)
	try:
		response = login_with_user_account(payload, db)
	except ValueError as exc:
		logger.warning(
			"auth_login_failed",
			extra={
				"subject_fingerprint": subject_fingerprint,
				"path": "/auth/login",
			},
		)
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

	logger.info(
		"auth_login_succeeded",
		extra={
			"subject_fingerprint": subject_fingerprint,
			"path": "/auth/login",
			"role": response.role,
		},
	)
	return response
