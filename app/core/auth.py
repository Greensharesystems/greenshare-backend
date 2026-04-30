from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import AUTH_ALGORITHM, AUTH_SECRET_KEY, AUTH_TOKEN_EXPIRE_MINUTES
from app.db.database import get_db
from app.repositories.customer_repository import get_customer_by_customer_id
from app.repositories.user_repository import get_user_by_user_id


class AuthPrincipal(BaseModel):
	email: str
	displayName: str
	identifier: str
	accountType: str
	role: str
	customerId: str | None = None


SHARED_PLATFORM_ROLES = frozenset({"admin", "employee"})


def get_customer_scope_id(principal: AuthPrincipal) -> str:
	return (principal.customerId or principal.identifier or "").strip().upper()


def has_role(principal: AuthPrincipal, *allowed_roles: str) -> bool:
	return principal.role in {role.strip().lower() for role in allowed_roles}


def has_shared_platform_access(principal: AuthPrincipal) -> bool:
	return principal.role in SHARED_PLATFORM_ROLES


def can_access_customer_data(principal: AuthPrincipal, customer_id: str | None) -> bool:
	if has_shared_platform_access(principal):
		return True

	normalized_customer_id = str(customer_id or "").strip().upper()
	return bool(normalized_customer_id) and normalized_customer_id == get_customer_scope_id(principal)


bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(principal: AuthPrincipal) -> str:
	payload = {
		"email": principal.email,
		"displayName": principal.displayName,
		"identifier": principal.identifier,
		"accountType": principal.accountType,
		"role": principal.role,
		"customerId": principal.customerId,
		"exp": datetime.now(timezone.utc) + timedelta(minutes=AUTH_TOKEN_EXPIRE_MINUTES),
	}
	return jwt.encode(payload, AUTH_SECRET_KEY, algorithm=AUTH_ALGORITHM)


def get_current_principal(
	credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
	access_token: str | None = Query(default=None, alias="access_token"),
	db: Session = Depends(get_db),
) -> AuthPrincipal:
	token = resolve_access_token(credentials, access_token)

	if token is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")

	payload = decode_access_token(token)
	account_type = str(payload.get("accountType", "")).strip().lower()
	identifier = str(payload.get("identifier", "")).strip().upper()
	role = str(payload.get("role", "")).strip().lower()
	email = str(payload.get("email", "")).strip().lower()
	token_customer_id = normalize_optional_identifier(payload.get("customerId"))

	if account_type != "user":
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is invalid.")

	user = get_user_by_user_id(db, identifier)
	principal = build_user_principal(db, user)

	if principal is None or principal.email != email or principal.role != role or principal.customerId != token_customer_id:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is invalid.")

	return principal


def build_user_principal(db: Session, user) -> AuthPrincipal | None:
	if user is None:
		return None

	identifier = normalize_required_identifier(getattr(user, "user_id", None))
	email = normalize_email(getattr(user, "email", None))
	role = normalize_role(getattr(user, "role", None))
	customer_id = normalize_optional_identifier(getattr(user, "customer_id", None))

	if identifier is None or email is None or role is None:
		return None

	if role == "customer":
		if customer_id is None or get_customer_by_customer_id(db, customer_id) is None:
			return None

	return AuthPrincipal(
		email=email,
		displayName=" ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part),
		identifier=identifier,
		accountType="user",
		role=role,
		customerId=customer_id,
	)


def resolve_access_token(
	credentials: HTTPAuthorizationCredentials | None,
	access_token: str | None,
) -> str | None:
	if credentials is not None and credentials.scheme.lower() == "bearer":
		return credentials.credentials

	if access_token:
		return access_token.strip()

	return None


def require_roles(*allowed_roles: str):
	normalized_roles = {role.strip().lower() for role in allowed_roles}

	def dependency(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
		if principal.role not in normalized_roles:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to perform that action.")

		return principal

	return dependency


def decode_access_token(token: str) -> dict[str, object]:
	try:
		payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[AUTH_ALGORITHM])
	except JWTError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is invalid.") from exc

	return payload


def normalize_email(value: object) -> str | None:
	normalized_value = str(value or "").strip().lower()
	return normalized_value or None


def normalize_optional_identifier(value: object) -> str | None:
	normalized_value = str(value or "").strip().upper()
	return normalized_value or None


def normalize_required_identifier(value: object) -> str | None:
	return normalize_optional_identifier(value)


def normalize_role(value: object) -> str | None:
	normalized_value = str(value or "").strip().lower()
	return normalized_value or None