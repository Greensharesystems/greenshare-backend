from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, create_access_token
from app.schemas.auth_schema import LoginRequest, LoginResponse


TEST_LOGIN_ACCOUNTS = {
	"admin@greenshare.ae": {
		"password": "admin123",
		"role": "admin",
		"user_id": "UID-ADMIN-0001",
		"display_name": "Greenshare Admin",
		"cid": None,
		"geid": None,
	},
	"employee@greenshare.ae": {
		"password": "employee123",
		"role": "employee",
		"user_id": "UID-EMPLOYEE-0001",
		"display_name": "Greenshare Employee",
		"cid": None,
		"geid": "GEID-0001",
	},
	"customer@greenshare.ae": {
		"password": "customer123",
		"role": "customer",
		"user_id": "UID-CUSTOMER-0001",
		"display_name": "Greenshare Customer",
		"cid": "CID-0001",
		"geid": None,
	},
}


def login_with_test_account(payload: LoginRequest, db: Session) -> LoginResponse:
	del db
	normalized_email = payload.email.strip().lower()
	normalized_password = payload.password.strip()
	account = TEST_LOGIN_ACCOUNTS.get(normalized_email)

	if account is None or account["password"] != normalized_password:
		raise ValueError("Invalid username or password")

	principal = AuthPrincipal(
		email=normalized_email,
		displayName=str(account["display_name"]),
		identifier=str(account["user_id"]),
		accountType="user",
		role=str(account["role"]),
		customerId=account["cid"],
	)

	return LoginResponse(
		access_token=create_access_token(principal),
		role=str(account["role"]),
		user_id=str(account["user_id"]),
		cid=account["cid"],
		geid=account["geid"],
	)