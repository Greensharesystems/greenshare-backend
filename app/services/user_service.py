import csv
from datetime import datetime
from io import StringIO

from sqlalchemy.orm import Session

from app.core.date_utils import normalize_date_for_output, normalize_date_for_storage
from app.core.config import PASSWORD_MIN_LENGTH, hash_password
from app.models.user import User
from app.repositories import customer_repository, user_repository
from app.schemas.user import NextUserIdResponse, UserCreate, UserResponse, UserUpdate


USER_CSV_COLUMNS = [
	"User ID Date",
	"User ID",
	"User Name",
	"User Email",
	"Company",
	"Role",
	"Last Active",
]


def list_users(db: Session) -> list[UserResponse]:
	users = user_repository.get_users(db)
	return [serialize_user(user) for user in users]


def get_next_user_id(db: Session) -> NextUserIdResponse:
	return NextUserIdResponse(userId=generate_next_user_id(db))


def export_users_csv(db: Session, user_ids: list[str] | None = None) -> tuple[str, str]:
	users = list_users(db)
	filtered_users = filter_users_for_export(users, user_ids or [])
	buffer = StringIO()
	writer = csv.DictWriter(buffer, fieldnames=USER_CSV_COLUMNS)
	writer.writeheader()
	writer.writerows([serialize_user_csv_row(user) for user in filtered_users])
	return "users-export.csv", buffer.getvalue()


def create_user(db: Session, payload: UserCreate) -> UserResponse:
	first_name = payload.firstName.strip()
	last_name = payload.lastName.strip()
	email = payload.email.strip().lower()
	position = normalize_optional_string(payload.position)
	department = normalize_optional_string(payload.department)
	mobile_phone = normalize_optional_string(payload.mobile)
	password = normalize_password(payload.password)
	role = normalize_role(payload.role)
	customer_id = normalize_optional_string(payload.customerId)
	company = normalize_company(db, payload.company, role, customer_id)
	user_id = generate_next_user_id(db)
	user_id_date = normalize_date_for_storage(payload.userIdDate, "User ID Date")

	if not first_name or not last_name or not email or not company or not role or not user_id_date:
		raise ValueError("All required user fields must be provided.")

	validate_customer_focal_person_fields(role, position, department, mobile_phone)

	if user_repository.get_user_by_email(db, email):
		raise ValueError("That email address is already in use.")

	user = User(
		user_id_date=user_id_date,
		user_id=user_id,
		first_name=first_name,
		last_name=last_name,
		email=email,
		position=position,
		department=department,
		mobile_phone=mobile_phone,
		company=company,
		role=role,
		customer_id=customer_id,
		password_hash=hash_password(password),
		last_active=format_last_active(datetime.now()),
	)

	created_user = user_repository.create_user(db, user)
	return serialize_user(created_user)


def get_user_for_management(db: Session, user_id: str) -> UserResponse:
	user = get_existing_user(db, user_id)
	return serialize_user(user)


def update_user(db: Session, user_id: str, payload: UserUpdate) -> UserResponse:
	user = get_existing_user(db, user_id)
	first_name = payload.firstName.strip()
	last_name = payload.lastName.strip()
	email = payload.email.strip().lower()
	position = normalize_optional_string(payload.position)
	department = normalize_optional_string(payload.department)
	mobile_phone = normalize_optional_string(payload.mobile)
	role = normalize_role(payload.role)
	customer_id = normalize_optional_string(payload.customerId)
	company = normalize_company(db, payload.company, role, customer_id)

	if not first_name or not last_name or not email or not company or not role:
		raise ValueError("All required user fields must be provided.")

	validate_customer_focal_person_fields(role, position, department, mobile_phone)

	existing_user_with_email = user_repository.get_user_by_email(db, email)
	if existing_user_with_email and existing_user_with_email.id != user.id:
		raise ValueError("That email address is already in use.")

	user.first_name = first_name
	user.last_name = last_name
	user.email = email
	user.position = position
	user.department = department
	user.mobile_phone = mobile_phone
	user.company = company
	user.role = role
	user.customer_id = customer_id
	db.commit()
	db.refresh(user)
	return serialize_user(user)


def delete_user(db: Session, user_id: str) -> None:
	user = get_existing_user(db, user_id)

	try:
		user_repository.delete_user(db, user)
		db.commit()
	except Exception:
		db.rollback()
		raise


def reset_user_password(db: Session, user_id: str, password: str) -> None:
	user = get_existing_user(db, user_id)

	user.password_hash = hash_password(normalize_password(password))
	db.commit()


def generate_next_user_id(db: Session) -> str:
	max_number = max(
		(
			int(match.group(1))
			for user_id in user_repository.get_user_ids(db)
			for match in [USER_ID_PATTERN.fullmatch(user_id.strip().upper())]
			if match is not None
		),
		default=0,
	)
	return f"UID-{max_number + 1:04d}"


def serialize_user(user: User) -> UserResponse:
	return UserResponse(
		id=user.id,
		userIdDate=normalize_date_for_output(user.user_id_date),
		userId=user.user_id,
		userName=" ".join(part for part in [user.first_name, user.last_name] if part),
		company=user.company,
		role=user.role,
		lastActive=user.last_active,
		email=user.email,
		position=user.position,
		department=user.department,
		mobile=user.mobile_phone,
		customerId=user.customer_id,
	)


def normalize_role(role: str) -> str:
	role_map = {
		"admin": "Admin",
		"employee": "Employee",
		"customer": "Customer",
	}
	return role_map.get(role.strip().lower(), role.strip())


def normalize_optional_string(value: str | None) -> str | None:
	if value is None:
		return None

	normalized = value.strip()
	return normalized or None


def normalize_password(password: str) -> str:
	normalized_password = password.strip()

	if len(normalized_password) < PASSWORD_MIN_LENGTH:
		raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")

	return normalized_password


def normalize_company(db: Session, company: str, role: str, customer_id: str | None) -> str:
	normalized_company = company.strip()

	if role == "Customer":
		if not customer_id:
			raise ValueError("Customer users must be linked to a customer ID.")

		linked_customer = customer_repository.get_customer_by_customer_id(db, customer_id.strip().upper())

		if linked_customer is None:
			raise ValueError("Customer users must be linked to an existing customer ID.")

		return linked_customer.company_name

	if customer_id:
		raise ValueError("Only customer users can be linked to a customer ID.")

	return normalized_company


def validate_customer_focal_person_fields(
	role: str,
	position: str | None,
	department: str | None,
	mobile_phone: str | None,
) -> None:
	if role != "Customer":
		return

	if not position or not department or not mobile_phone:
		raise ValueError("Customer users must include position, department, and mobile details.")


def format_last_active(value: datetime) -> str:
	return value.strftime("Today, %H:%M")


def get_existing_user(db: Session, user_id: str) -> User:
	normalized_user_id = user_id.strip().upper()
	user = user_repository.get_user_by_user_id(db, normalized_user_id)

	if user is None:
		raise ValueError("That user could not be found.")

	return user


def filter_users_for_export(users: list[UserResponse], user_ids: list[str]) -> list[UserResponse]:
	if not user_ids:
		return users

	users_by_id = {user.userId.upper(): user for user in users}
	return [
		users_by_id[normalized_user_id]
		for user_id in user_ids
		for normalized_user_id in [user_id.strip().upper()]
		if normalized_user_id in users_by_id
	]


def serialize_user_csv_row(user: UserResponse) -> dict[str, str]:
	return {
		"User ID Date": user.userIdDate,
		"User ID": user.userId,
		"User Name": user.userName,
		"User Email": user.email,
		"Company": user.company,
		"Role": user.role,
		"Last Active": user.lastActive,
	}


import re


USER_ID_PATTERN = re.compile(r"UID-(\d+)")
