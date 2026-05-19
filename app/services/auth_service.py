from sqlalchemy.orm import Session

from app.core.auth import build_user_principal, create_access_token
from app.core.config import verify_password
from app.repositories.user_repository import get_user_by_email
from app.schemas.auth_schema import LoginRequest, LoginResponse

def login_with_user_account(payload: LoginRequest, db: Session) -> LoginResponse:
	normalized_email = payload.email.strip().lower()
	normalized_password = payload.password.strip()
	user = get_user_by_email(db, normalized_email)
	principal = build_user_principal(db, user)

	if principal is None or user is None or not verify_password(normalized_password, user.password_hash):
		raise ValueError("Invalid username or password")

	return LoginResponse(
		access_token=create_access_token(principal),
		role=principal.role,
		user_id=principal.identifier,
		display_name=principal.displayName,
		cid=principal.customerId,
		geid=None,
	)