import csv
import json
import re
from io import StringIO

from sqlalchemy.orm import Session

from app.core.date_utils import normalize_date_for_output, normalize_date_for_storage
from app.models.customer import Customer
from app.repositories import customer_repository
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate, FocalPersonInput, FocalPersonResponse, NextCustomerIdResponse


CUSTOMER_ID_PATTERN = re.compile(r"CID-(\d+)")
CUSTOMER_AUTH_DISABLED = "CUSTOMER_AUTH_DISABLED"
NO_CUSTOMER_USER_ACTIVITY = "No user access yet"
CUSTOMER_CSV_COLUMNS = [
	"Company Name",
	"Emirate",
	"Area",
	"Office Location",
	"Website",
	"Sector",
	"Contact Person",
	"Position",
	"Department",
	"Email",
	"Office Phone",
	"Mobile Phone",
]


def list_customers(db: Session) -> list[CustomerResponse]:
	customers = customer_repository.get_customers(db)
	return [serialize_customer(customer) for customer in customers]


def get_customer_profile(db: Session, customer_id: str) -> CustomerResponse:
	normalized_customer_id = customer_id.strip().upper()
	customer = customer_repository.get_customer_by_customer_id(db, normalized_customer_id)

	if customer is None:
		raise ValueError("That customer could not be found.")

	return serialize_customer(customer)


def get_customer_for_management(db: Session, customer_id: str) -> CustomerResponse:
	return get_customer_profile(db, customer_id)


def export_customers_csv(db: Session, customer_ids: list[str] | None = None) -> tuple[str, str]:
	customers = list_customers(db)
	filtered_customers = filter_customers_for_export(customers, customer_ids or [])
	buffer = StringIO()
	writer = csv.DictWriter(buffer, fieldnames=CUSTOMER_CSV_COLUMNS)
	writer.writeheader()
	writer.writerows([serialize_customer_csv_row(customer) for customer in filtered_customers])
	return "customers-export.csv", buffer.getvalue()


def get_next_customer_id(db: Session) -> NextCustomerIdResponse:
	return NextCustomerIdResponse(customerId=generate_next_customer_id(db))


def create_customer(db: Session, payload: CustomerCreate) -> CustomerResponse:
	company_name = payload.companyName.strip()
	company_emirate = payload.emirate.strip()
	area = payload.area.strip()
	office_address = payload.officeLocation.strip()
	website = payload.website.strip().lower()
	sector = payload.sector.strip()
	customer_id_date = normalize_date_for_storage(payload.customerIdDate, "Customer ID Date")
	customer_id = generate_next_customer_id(db)
	focal_people = normalize_focal_people(payload.focalPersons, payload)
	primary_focal_person = focal_people[0]

	if not all([
		company_name,
		company_emirate,
		area,
		office_address,
		website,
		sector,
		primary_focal_person.name,
		primary_focal_person.position,
		primary_focal_person.department,
		primary_focal_person.email,
		primary_focal_person.officePhone,
		primary_focal_person.mobilePhone,
		customer_id_date,
	]):
		raise ValueError("All required customer fields must be provided.")

	if customer_repository.get_customer_by_contact_email(db, primary_focal_person.email):
		raise ValueError("That contact email address is already in use.")

	customer = Customer(
		customer_id_date=customer_id_date,
		customer_id=customer_id,
		company_name=company_name,
		company_emirate=company_emirate,
		area=area,
		office_address=office_address,
		website=website,
		sector=sector,
		contact_person_name=primary_focal_person.name,
		contact_person_position=primary_focal_person.position,
		contact_person_department=primary_focal_person.department,
		contact_person_email=primary_focal_person.email,
		contact_person_office_phone=primary_focal_person.officePhone,
		contact_person_mobile_phone=primary_focal_person.mobilePhone,
		focal_persons_json=serialize_focal_people_json(focal_people),
		password_hash=CUSTOMER_AUTH_DISABLED,
		last_active=NO_CUSTOMER_USER_ACTIVITY,
	)

	created_customer = customer_repository.create_customer(db, customer)
	return serialize_customer(created_customer)


def update_customer(db: Session, customer_id: str, payload: CustomerUpdate) -> CustomerResponse:
	normalized_customer_id = customer_id.strip().upper()
	customer = customer_repository.get_customer_by_customer_id(db, normalized_customer_id)

	if customer is None:
		raise ValueError("That customer could not be found.")

	company_name = payload.companyName.strip()
	company_emirate = payload.emirate.strip()
	area = payload.area.strip()
	office_address = payload.officeLocation.strip()
	website = payload.website.strip().lower()
	sector = payload.sector.strip()
	focal_people = normalize_focal_people(payload.focalPersons)
	primary_focal_person = focal_people[0]

	if not all([
		company_name,
		company_emirate,
		area,
		office_address,
		website,
		sector,
		primary_focal_person.name,
		primary_focal_person.position,
		primary_focal_person.department,
		primary_focal_person.email,
		primary_focal_person.officePhone,
		primary_focal_person.mobilePhone,
	]):
		raise ValueError("All required customer fields must be provided.")

	existing_customer = customer_repository.get_customer_by_contact_email(db, primary_focal_person.email)
	if existing_customer is not None and existing_customer.customer_id != customer.customer_id:
		raise ValueError("That contact email address is already in use.")

	customer.company_name = company_name
	customer.company_emirate = company_emirate
	customer.area = area
	customer.office_address = office_address
	customer.website = website
	customer.sector = sector
	customer.contact_person_name = primary_focal_person.name
	customer.contact_person_position = primary_focal_person.position
	customer.contact_person_department = primary_focal_person.department
	customer.contact_person_email = primary_focal_person.email
	customer.contact_person_office_phone = primary_focal_person.officePhone
	customer.contact_person_mobile_phone = primary_focal_person.mobilePhone
	customer.focal_persons_json = serialize_focal_people_json(focal_people)

	updated_customer = customer_repository.update_customer(db, customer)
	return serialize_customer(updated_customer)


def delete_customer(db: Session, customer_id: str) -> None:
	normalized_customer_id = customer_id.strip().upper()
	customer = customer_repository.get_customer_by_customer_id(db, normalized_customer_id)

	if customer is None:
		raise ValueError("That customer could not be found.")

	try:
		db.delete(customer)
		db.commit()
	except Exception:
		db.rollback()
		raise


def generate_next_customer_id(db: Session) -> str:
	max_number = max(
		(
			int(match.group(1))
			for customer_id in customer_repository.get_customer_ids(db)
			for match in [CUSTOMER_ID_PATTERN.fullmatch(customer_id.strip().upper())]
			if match is not None
		),
		default=0,
	)
	return f"CID-{max_number + 1:04d}"


def serialize_customer(customer: Customer) -> CustomerResponse:
	focal_people = deserialize_focal_people(customer)
	linked_user_emails = {
		str(user.email or "").strip().lower()
		for user in list(getattr(customer, "linked_users", []) or [])
		if str(getattr(user, "role", "")).strip().lower() == "customer"
	}
	focal_people_response = [
		FocalPersonResponse(
			name=focal_person.name,
			position=focal_person.position,
			department=focal_person.department,
			email=focal_person.email,
			officePhone=focal_person.officePhone,
			mobilePhone=focal_person.mobilePhone,
			hasUserAccount=focal_person.email in linked_user_emails,
		)
		for focal_person in focal_people
	]
	primary_focal_person = focal_people[0]

	return CustomerResponse(
		id=customer.id,
		customerIdDate=normalize_date_for_output(customer.customer_id_date),
		customerId=customer.customer_id,
		companyName=customer.company_name,
		companyEmirate=customer.company_emirate,
		area=customer.area,
		officeAddress=customer.office_address,
		website=customer.website,
		sector=customer.sector,
		contactPersonName=primary_focal_person.name,
		contactPersonPosition=primary_focal_person.position,
		contactPersonDepartment=primary_focal_person.department,
		contactPersonEmail=primary_focal_person.email,
		contactPersonOfficePhone=primary_focal_person.officePhone,
		contactPersonMobilePhone=primary_focal_person.mobilePhone,
		focalPersons=focal_people_response,
		lastActive=customer.last_active,
	)


def filter_customers_for_export(
	customers: list[CustomerResponse],
	customer_ids: list[str],
) -> list[CustomerResponse]:
	normalized_customer_ids = [customer_id.strip().upper() for customer_id in customer_ids if customer_id.strip()]

	if not normalized_customer_ids:
		return customers

	customer_lookup = {customer.customerId.strip().upper(): customer for customer in customers}
	return [customer_lookup[customer_id] for customer_id in normalized_customer_ids if customer_id in customer_lookup]


def serialize_customer_csv_row(customer: CustomerResponse) -> dict[str, str]:
	return {
		"Company Name": customer.companyName,
		"Emirate": customer.companyEmirate,
		"Area": customer.area,
		"Office Location": customer.officeAddress,
		"Website": customer.website,
		"Sector": customer.sector,
		"Contact Person": customer.contactPersonName,
		"Position": customer.contactPersonPosition,
		"Department": customer.contactPersonDepartment,
		"Email": customer.contactPersonEmail,
		"Office Phone": customer.contactPersonOfficePhone,
		"Mobile Phone": customer.contactPersonMobilePhone,
	}


def normalize_focal_people(
	focal_people: list[FocalPersonInput],
	legacy_payload: CustomerCreate | None = None,
) -> list[FocalPersonInput]:
	if focal_people:
		normalized = [normalize_focal_person_input(focal_person) for focal_person in focal_people]
	else:
		if legacy_payload is None:
			raise ValueError("At least one focal person is required.")

		normalized = [
			FocalPersonInput(
				name=str(legacy_payload.contactName or "").strip(),
				position=str(legacy_payload.contactPosition or "").strip(),
				department=str(legacy_payload.contactDepartment or "").strip(),
				email=str(legacy_payload.contactEmail or "").strip().lower(),
				officePhone=str(legacy_payload.contactOfficePhone or "").strip(),
				mobilePhone=str(legacy_payload.contactMobilePhone or "").strip(),
			),
		]

	if not normalized:
		raise ValueError("At least one focal person is required.")

	emails_seen: set[str] = set()
	for focal_person in normalized:
		if not all([
			focal_person.name,
			focal_person.position,
			focal_person.department,
			focal_person.email,
			focal_person.officePhone,
			focal_person.mobilePhone,
		]):
			raise ValueError("Every focal person must include name, position, department, email, office phone, and mobile phone.")

		if focal_person.email in emails_seen:
			raise ValueError("Each focal person email must be unique within the customer record.")

		emails_seen.add(focal_person.email)

	return normalized


def normalize_focal_person_input(focal_person: FocalPersonInput) -> FocalPersonInput:
	return FocalPersonInput(
		name=focal_person.name.strip(),
		position=focal_person.position.strip(),
		department=focal_person.department.strip(),
		email=focal_person.email.strip().lower(),
		officePhone=focal_person.officePhone.strip(),
		mobilePhone=focal_person.mobilePhone.strip(),
	)


def serialize_focal_people_json(focal_people: list[FocalPersonInput]) -> str:
	return json.dumps([
		{
			"name": focal_person.name,
			"position": focal_person.position,
			"department": focal_person.department,
			"email": focal_person.email,
			"officePhone": focal_person.officePhone,
			"mobilePhone": focal_person.mobilePhone,
		}
		for focal_person in focal_people
	])


def deserialize_focal_people(customer: Customer) -> list[FocalPersonInput]:
	raw_value = str(getattr(customer, "focal_persons_json", "") or "").strip()
	if raw_value:
		try:
			payload = json.loads(raw_value)
			if isinstance(payload, list):
				normalized = [
					normalize_focal_person_input(FocalPersonInput(**item))
					for item in payload
					if isinstance(item, dict)
				]
				if normalized:
					return normalized
		except (TypeError, ValueError):
			pass

	return [
		FocalPersonInput(
			name=customer.contact_person_name,
			position=customer.contact_person_position,
			department=customer.contact_person_department,
			email=customer.contact_person_email,
			officePhone=customer.contact_person_office_phone,
			mobilePhone=customer.contact_person_mobile_phone,
		),
	]