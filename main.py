import json
from datetime import datetime
import logging
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.circularity_certificates import router as circularity_certificates_router
from app.api.dashboard import customer_router as customer_dashboard_router, router as dashboard_router
from app.api.reception_certificates import router as reception_certificates_router
from app.api.reception_notes import router as reception_notes_router
from app.api.users import router as users_router
from app.core.config import DEFAULT_USER_PASSWORD, hash_password
from app.db.database import Base, SessionLocal, engine
from app.models.customer import Customer
from app.models.circularity_certificate import CircularityCertificate
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.models.user import User
from app.services.customer_service import CUSTOMER_AUTH_DISABLED, NO_CUSTOMER_USER_ACTIVITY


SEED_ADMIN_EMAIL = "imran.g@zerowaste.ae"
SEED_ADMIN_PASSWORD = "greenshare"

app = FastAPI()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://witty-pond-0c214db00.7.azurestaticapps.net",
        "https://witty-pond-0c214db00-1.eastasia.7.azurestaticapps.net",
        "https://www.greenshare.ae",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(customers_router)
app.include_router(reception_notes_router)
app.include_router(reception_certificates_router)
app.include_router(circularity_certificates_router)
app.include_router(dashboard_router)
app.include_router(customer_dashboard_router)


@app.get("/")
def read_root():
    return {"message": "Greenshare backend is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "greenshare-backend"}


@app.get("/health/db")
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed.")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Verify Azure PostgreSQL connectivity and DATABASE_URL.",
        ) from exc

    return {"status": "connected", "database": "azure_postgresql"}


@app.on_event("startup")
def startup_database() -> None:
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        ensure_password_schema()
        seed_admin_user()
    except Exception as exc:
        print("DB init warning:", exc)


def seed_admin_user() -> None:
    # Temporary Azure bootstrap seed; remove after the initial admin is provisioned.
    with SessionLocal() as db:
        existing_user = db.query(User).filter(User.email == SEED_ADMIN_EMAIL).first()

        if existing_user is not None:
            logger.info("Seed admin exists")
            return

        seed_user = User(
            user_id_date="20260430",
            user_id="UID-0001",
            first_name="Imran",
            last_name="Gill",
            email=SEED_ADMIN_EMAIL,
            position="Admin",
            department="Management",
            mobile_phone="0000000000",
            company="Zero Waste",
            role="Admin",
            customer_id="CID-ADMIN",
            password_hash=hash_password(SEED_ADMIN_PASSWORD),
            last_active=format_last_active(datetime.now()),
        )

        db.add(seed_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info("Seed admin exists")
            return
        logger.info("Seed admin created")


def format_last_active(value: datetime) -> str:
    return value.strftime("Today, %H:%M")


def ensure_password_schema() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "users" in existing_tables:
            user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
            if "password_hash" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            if "position" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN position VARCHAR(120)"))
            if "department" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(120)"))
            if "mobile_phone" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN mobile_phone VARCHAR(64)"))

        if "customers" in existing_tables:
            customer_columns = {column["name"] for column in inspect(engine).get_columns("customers")}
            if "password_hash" not in customer_columns:
                connection.execute(text("ALTER TABLE customers ADD COLUMN password_hash VARCHAR(255)"))
            if "focal_persons_json" not in customer_columns:
                connection.execute(text("ALTER TABLE customers ADD COLUMN focal_persons_json TEXT DEFAULT '[]'"))

        for table_name in ["reception_notes", "reception_certificates", "circularity_certificates"]:
            if table_name not in existing_tables:
                continue

            columns = {column["name"] for column in inspect(engine).get_columns(table_name)}

            if "owner_identifier" not in columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN owner_identifier VARCHAR(64) DEFAULT ''"))

            if "owner_role" not in columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN owner_role VARCHAR(32) DEFAULT ''"))

        if "circularity_certificates" in existing_tables:
            circularity_columns = {column["name"] for column in inspect(engine).get_columns("circularity_certificates")}

            if "secondary_ecosystem_details" not in circularity_columns:
                connection.execute(
                    text("ALTER TABLE circularity_certificates ADD COLUMN secondary_ecosystem_details JSON DEFAULT '{}'"),
                )

    with SessionLocal() as db:
        should_commit = False

        users_without_password = db.query(User).filter(or_(User.password_hash.is_(None), User.password_hash == "")).all()
        for user in users_without_password:
            user.password_hash = hash_password(DEFAULT_USER_PASSWORD)
            should_commit = True

        customers_without_password = db.query(Customer).filter(or_(Customer.password_hash.is_(None), Customer.password_hash == "")).all()
        for customer in customers_without_password:
            customer.password_hash = CUSTOMER_AUTH_DISABLED
            if not customer.last_active:
                customer.last_active = NO_CUSTOMER_USER_ACTIVITY
            should_commit = True

        customers_without_focal_people = db.query(Customer).filter(
            or_(Customer.focal_persons_json.is_(None), Customer.focal_persons_json == ""),
        ).all()

        for customer in customers_without_focal_people:
            customer.focal_persons_json = json.dumps([
                {
                    "name": customer.contact_person_name,
                    "position": customer.contact_person_position,
                    "department": customer.contact_person_department,
                    "email": customer.contact_person_email,
                    "officePhone": customer.contact_person_office_phone,
                    "mobilePhone": customer.contact_person_mobile_phone,
                },
            ])
            should_commit = True

        users_missing_profile_fields = db.query(User).filter(
            or_(User.position.is_(None), User.department.is_(None), User.mobile_phone.is_(None)),
        ).all()

        for user in users_missing_profile_fields:
            if user.position is None:
                user.position = "Customer Contact" if str(user.role or "").strip().lower() == "customer" else "N/A"
                should_commit = True

            if user.department is None:
                user.department = "Customer" if str(user.role or "").strip().lower() == "customer" else "N/A"
                should_commit = True

            if user.mobile_phone is None:
                user.mobile_phone = "N/A"
                should_commit = True

        customer_users_missing_links = db.query(User).filter(
            User.role.ilike("Customer"),
            or_(User.customer_id.is_(None), User.customer_id == ""),
        ).all()

        for user in customer_users_missing_links:
            linked_customer = db.query(Customer).filter(
                or_(
                    Customer.contact_person_email == user.email,
                    Customer.company_name == user.company,
                ),
            ).first()

            if linked_customer is None:
                linked_customer = Customer(
                    customer_id_date=user.user_id_date,
                    customer_id=generate_next_customer_id(db),
                    company_name=user.company,
                    company_emirate="Unknown",
                    area="Unknown",
                    office_address="Unknown",
                    website=build_placeholder_website(user.company),
                    sector="Unknown",
                    contact_person_name=" ".join(part for part in [user.first_name, user.last_name] if part),
                    contact_person_position="Customer Contact",
                    contact_person_department="Customer",
                    contact_person_email=user.email,
                    contact_person_office_phone="N/A",
                    contact_person_mobile_phone="N/A",
                    focal_persons_json=json.dumps([
                        {
                            "name": " ".join(part for part in [user.first_name, user.last_name] if part),
                            "position": user.position or "Customer Contact",
                            "department": user.department or "Customer",
                            "email": user.email,
                            "officePhone": "N/A",
                            "mobilePhone": user.mobile_phone or "N/A",
                        },
                    ]),
                    password_hash=CUSTOMER_AUTH_DISABLED,
                    last_active=user.last_active,
                )
                db.add(linked_customer)
                db.flush()

            user.customer_id = linked_customer.customer_id
            should_commit = True

        for reception_note in db.query(ReceptionNote).all():
            normalized_rnid = normalize_rnid_value(reception_note.rnid)

            if normalized_rnid != reception_note.rnid:
                reception_note.rnid = normalized_rnid
                should_commit = True

        reception_certificates = db.query(ReceptionCertificate).order_by(ReceptionCertificate.created_at.asc(), ReceptionCertificate.id.asc()).all()
        reception_certificate_id_map = assign_reception_certificate_ids(db, reception_certificates)

        for reception_certificate in reception_certificates:
            normalized_rnid_summary = ", ".join(normalize_rnid_value(value) for value in split_csv_values(reception_certificate.rnid))
            normalized_linked_rnids = [normalize_rnid_value(value) for value in (reception_certificate.linked_rnids or [])]
            target_rcid = reception_certificate_id_map.get(normalize_rcid_alias_value(reception_certificate.rcid), normalize_rcid_value(reception_certificate.rcid))

            if target_rcid != reception_certificate.rcid:
                reception_certificate.rcid = target_rcid
                should_commit = True

            if normalized_rnid_summary != reception_certificate.rnid:
                reception_certificate.rnid = normalized_rnid_summary
                should_commit = True

            if normalized_linked_rnids != list(reception_certificate.linked_rnids or []):
                reception_certificate.linked_rnids = normalized_linked_rnids
                should_commit = True

        circularity_certificates = db.query(CircularityCertificate).order_by(CircularityCertificate.created_at.asc(), CircularityCertificate.id.asc()).all()
        circularity_certificate_id_map = assign_circularity_certificate_ids(db, circularity_certificates)

        for circularity_certificate in circularity_certificates:
            normalized_linked_rcids = [
                reception_certificate_id_map.get(normalize_rcid_alias_value(value), normalize_rcid_value(value))
                for value in (circularity_certificate.linked_rcids or [])
            ]
            normalized_rcid_summary = ", ".join(
                reception_certificate_id_map.get(normalize_rcid_alias_value(value), normalize_rcid_value(value))
                for value in split_csv_values(circularity_certificate.rcid)
            )
            target_ccid = circularity_certificate_id_map.get(normalize_ccid_alias_value(circularity_certificate.ccid), normalize_ccid_value(circularity_certificate.ccid))

            if target_ccid != circularity_certificate.ccid:
                circularity_certificate.ccid = target_ccid
                should_commit = True

            if normalized_rcid_summary != circularity_certificate.rcid:
                circularity_certificate.rcid = normalized_rcid_summary
                should_commit = True

            if normalized_linked_rcids != list(circularity_certificate.linked_rcids or []):
                circularity_certificate.linked_rcids = normalized_linked_rcids
                should_commit = True

            secondary_ecosystem_details = getattr(circularity_certificate, "secondary_ecosystem_details", None)
            has_valid_secondary_ecosystem = (
                isinstance(secondary_ecosystem_details, dict)
                and secondary_ecosystem_details.get("mode") in {"shared", "by_rc", "by_rn"}
            )

            if not has_valid_secondary_ecosystem:
                circularity_certificate.secondary_ecosystem_details = {
                    "mode": "shared",
                    "shared": {
                        "secondaryProduct": circularity_certificate.secondary_product,
                        "secondaryLoop": circularity_certificate.secondary_loop,
                    },
                    "entries": [],
                }
                should_commit = True

        if should_commit:
            db.commit()


def generate_next_customer_id(db: Session) -> str:
    max_number = 0

    for result in db.query(Customer.customer_id).all():
        customer_id = result[0] if result else None
        if not customer_id:
            continue
        try:
            max_number = max(max_number, int(str(customer_id).split("-")[-1]))
        except ValueError:
            continue

    return f"CID-{max_number + 1:04d}"


def build_placeholder_website(company_name: str) -> str:
    base = "".join(character.lower() for character in company_name if character.isalnum()) or "customer"
    return f"{base}.local"


def split_csv_values(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def normalize_rnid_value(value: str) -> str:
    matched_value = re.fullmatch(r"(?:RNID|RN)-(\d+)-(\d+)", str(value).strip().upper())

    if matched_value is None:
        return str(value).strip().upper()

    return f"RNID-{int(matched_value.group(1)):04d}-{matched_value.group(2)}"


def normalize_rcid_value(value: str) -> str:
	canonical_value = normalize_rcid_alias_value(value)
	parts = canonical_value.split("-")

	if len(parts) == 3:
		return canonical_value

	return f"RCID-{parts[1]}-{parts[3]}"


def normalize_rcid_alias_value(value: str) -> str:
    matched_value = re.fullmatch(r"(?:RCID|RC)-(\d+)-(\d+)-(\d+)", str(value).strip().upper())

    if matched_value is not None:
        return f"RCID-{int(matched_value.group(1)):04d}-{matched_value.group(2)}-{matched_value.group(3)}"

    matched_new_value = re.fullmatch(r"(?:RCID|RC)-(\d+)-(\d+)", str(value).strip().upper())

    if matched_new_value is None:
        return str(value).strip().upper()

    return f"RCID-{int(matched_new_value.group(1)):04d}-{matched_new_value.group(2)}"


def normalize_ccid_value(value: str) -> str:
	canonical_value = normalize_ccid_alias_value(value)
	parts = canonical_value.split("-")

	if len(parts) == 3:
		return canonical_value

	return f"CCID-{parts[1]}-{parts[4]}"


def normalize_ccid_alias_value(value: str) -> str:
    matched_value = re.fullmatch(r"(?:CCID|CC)-(\d+)-(\d+)-(\d+)-(\d+)", str(value).strip().upper())

    if matched_value is not None:
        return f"CCID-{int(matched_value.group(1)):04d}-{matched_value.group(2)}-{matched_value.group(3)}-{matched_value.group(4)}"

    matched_new_value = re.fullmatch(r"(?:CCID|CC)-(\d+)-(\d+)", str(value).strip().upper())

    if matched_new_value is None:
        return str(value).strip().upper()

    return f"CCID-{int(matched_new_value.group(1)):04d}-{matched_new_value.group(2)}"


def assign_reception_certificate_ids(db: Session, reception_certificates: list[ReceptionCertificate]) -> dict[str, str]:
    sequence_by_customer: dict[str, int] = {}
    mapping: dict[str, str] = {}
    temporary_targets: list[tuple[ReceptionCertificate, str]] = []

    for reception_certificate in reception_certificates:
        customer_segment = get_customer_segment(reception_certificate.customer_id, reception_certificate.rcid)
        sequence_by_customer[customer_segment] = sequence_by_customer.get(customer_segment, 0) + 1
        next_rcid = f"RCID-{customer_segment}-{sequence_by_customer[customer_segment]:04d}"
        normalized_current_rcid = normalize_rcid_alias_value(reception_certificate.rcid)
        mapping[normalized_current_rcid] = next_rcid

        if reception_certificate.rcid != next_rcid:
            reception_certificate.rcid = f"TMP-RCID-{reception_certificate.id}"
            temporary_targets.append((reception_certificate, next_rcid))

    if temporary_targets:
        db.flush()

    for reception_certificate, next_rcid in temporary_targets:
        reception_certificate.rcid = next_rcid

    return mapping


def assign_circularity_certificate_ids(db: Session, circularity_certificates: list[CircularityCertificate]) -> dict[str, str]:
    sequence_by_customer: dict[str, int] = {}
    mapping: dict[str, str] = {}
    temporary_targets: list[tuple[CircularityCertificate, str]] = []

    for circularity_certificate in circularity_certificates:
        customer_segment = get_customer_segment(circularity_certificate.cid, circularity_certificate.ccid)
        sequence_by_customer[customer_segment] = sequence_by_customer.get(customer_segment, 0) + 1
        next_ccid = f"CCID-{customer_segment}-{sequence_by_customer[customer_segment]:04d}"
        normalized_current_ccid = normalize_ccid_alias_value(circularity_certificate.ccid)
        mapping[normalized_current_ccid] = next_ccid

        if circularity_certificate.ccid != next_ccid:
            circularity_certificate.ccid = f"TMP-CCID-{circularity_certificate.id}"
            temporary_targets.append((circularity_certificate, next_ccid))

    if temporary_targets:
        db.flush()

    for circularity_certificate, next_ccid in temporary_targets:
        circularity_certificate.ccid = next_ccid

    return mapping


def get_customer_segment(customer_id: str, fallback_identifier: str) -> str:
    matched_customer = re.fullmatch(r"CID-(\d+)", str(customer_id).strip().upper())

    if matched_customer is not None:
        return f"{int(matched_customer.group(1)):04d}"

    fallback_parts = str(fallback_identifier).strip().upper().split("-")
    if len(fallback_parts) >= 2 and fallback_parts[1].isdigit():
        return f"{int(fallback_parts[1]):04d}"

    return "0000"
