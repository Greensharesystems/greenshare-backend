import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, can_access_customer_data, get_customer_scope_id, has_shared_platform_access
from app.core.date_utils import normalize_date_for_output, normalize_date_for_storage, normalize_optional_date_for_storage
from app.models.reception_note import ReceptionNote
from app.repositories import reception_note_repository
from app.schemas.reception_note import NextReceptionNoteIdResponse, ReceptionNoteCreate, ReceptionNoteResponse
from app.services.pdf_generation_service import generate_pdf


RECEPTION_NOTE_ID_PATTERN = re.compile(r"(?:RNID|RN)-(\d+)-(\d+)")
QUANTITY_WITH_UNIT_PATTERN = re.compile(r"^\s*([-+]?\d[\d,]*(?:\.\d+)?)\s+(.+?)\s*$")


def list_reception_notes(db: Session, principal: AuthPrincipal) -> list[ReceptionNoteResponse]:
	reception_notes = get_visible_reception_notes(db, principal)
	return [serialize_reception_note(reception_note) for reception_note in reception_notes]


def get_next_reception_note_id(db: Session, customer_id: str) -> NextReceptionNoteIdResponse:
	normalized_customer_id = normalize_customer_id(customer_id)
	return NextReceptionNoteIdResponse(rnid=generate_next_reception_note_id(db, normalized_customer_id))


def create_reception_note(db: Session, payload: ReceptionNoteCreate, principal: AuthPrincipal) -> ReceptionNoteResponse:
	normalized_customer_id = normalize_customer_id(payload.customerId)
	rnid_date = normalize_date_for_storage(payload.rnidDate, "Reception Note ID Date")
	producing_company_name = payload.producingCompanyName.strip()
	rn_issued_by = payload.rnIssuedBy.strip()
	waste_streams = [normalize_waste_stream(stream.model_dump()) for stream in payload.wasteStreams]

	if not rnid_date or not producing_company_name or not rn_issued_by or not waste_streams:
		raise ValueError("All required reception note fields must be provided.")

	rnid = generate_next_reception_note_id(db, normalized_customer_id)

	if reception_note_repository.get_reception_note_by_rnid(db, rnid):
		raise ValueError("That reception note ID is already in use.")

	reception_note = ReceptionNote(
		rnid_date=rnid_date,
		rnid=rnid,
		customer_id=normalized_customer_id,
		weigh_bridge_slip_date=normalize_optional_date_for_storage(payload.weighBridgeSlipDate, "Weigh Bridge Slip Date"),
		weigh_bridge_bill_no=payload.weighBridgeBillNo.strip(),
		producing_company_name=producing_company_name,
		producing_company_emirate=payload.producingCompanyEmirate.strip(),
		producing_company_office_address=payload.producingCompanyOfficeAddress.strip(),
		producing_company_contact_person=payload.producingCompanyContactPerson.strip(),
		producing_company_office_phone=payload.producingCompanyOfficePhone.strip(),
		producing_company_email=payload.producingCompanyEmail.strip(),
		transporting_company_name=payload.transportingCompanyName.strip(),
		transporting_company_contact_person=payload.transportingCompanyContactPerson.strip(),
		transporting_company_office_phone=payload.transportingCompanyOfficePhone.strip(),
		transporting_company_email=payload.transportingCompanyEmail.strip(),
		waste_streams=waste_streams,
		vehicle_plate_no=payload.vehiclePlateNo.strip(),
		driver_name=payload.driverName.strip(),
		waste_stream_name=payload.wasteStreamName.strip(),
		waste_stream_quantity=payload.wasteStreamQuantity.strip(),
		rn_issued_by=rn_issued_by,
		owner_identifier=principal.identifier,
		owner_role=principal.role,
		status=normalize_status(payload.status),
	)

	created_reception_note = reception_note_repository.create_reception_note(db, reception_note)
	return serialize_reception_note(created_reception_note)


def delete_reception_note(db: Session, rnid: str, principal: AuthPrincipal) -> None:
	normalized_rnid = normalize_rnid(rnid)
	reception_note = reception_note_repository.get_reception_note_by_rnid(db, normalized_rnid)

	if reception_note is None:
		raise ValueError("That reception note could not be found.")

	if not can_access_reception_note(reception_note, principal):
		raise ValueError("That reception note could not be found.")

	try:
		reception_note_repository.delete_reception_note(db, reception_note)
		db.commit()
	except Exception:
		db.rollback()
		raise


def generate_reception_note_pdf(db: Session, reception_note_reference: int | str, principal: AuthPrincipal) -> tuple[str, bytes]:
	if isinstance(reception_note_reference, str):
		normalized_rnid = normalize_rnid(reception_note_reference)
		reception_note = reception_note_repository.get_reception_note_by_rnid(db, normalized_rnid)
	else:
		reception_note = reception_note_repository.get_reception_note_by_id(db, reception_note_reference)

	if reception_note is None or not can_access_reception_note(reception_note, principal):
		raise ValueError("That reception note could not be found.")

	context = build_reception_note_pdf_context(reception_note)
	pdf_bytes = generate_pdf("pdf/reception_note.html", context)
	filename = f"{normalize_rnid(reception_note.rnid)}.pdf"
	return filename, pdf_bytes


def get_visible_reception_notes(db: Session, principal: AuthPrincipal) -> list[ReceptionNote]:
	if has_shared_platform_access(principal):
		return reception_note_repository.get_reception_notes(db)

	return reception_note_repository.get_reception_notes_by_customer_id(db, get_customer_scope_id(principal))


def can_access_reception_note(reception_note: ReceptionNote, principal: AuthPrincipal) -> bool:
	return can_access_customer_data(principal, reception_note.customer_id)


def generate_next_reception_note_id(db: Session, customer_id: str) -> str:
	customer_sequence = extract_customer_sequence_value(customer_id)
	max_number = max(
		(
			int(match.group(2))
			for rnid in reception_note_repository.get_reception_note_ids(db)
			for match in [RECEPTION_NOTE_ID_PATTERN.fullmatch(rnid.strip().upper())]
			if match is not None and int(match.group(1)) == int(customer_sequence)
		),
		default=0,
	)
	return f"RNID-{customer_sequence}-{max_number + 1:04d}"


def serialize_reception_note(reception_note: ReceptionNote) -> ReceptionNoteResponse:
	normalized_waste_streams = [normalize_waste_stream(waste_stream) for waste_stream in reception_note.waste_streams or []]

	return ReceptionNoteResponse(
		id=reception_note.id,
		rnidDate=normalize_date_for_output(reception_note.rnid_date),
		rnid=reception_note.rnid,
		customerId=reception_note.customer_id,
		weighBridgeSlipDate=normalize_date_for_output(reception_note.weigh_bridge_slip_date),
		weighBridgeBillNo=reception_note.weigh_bridge_bill_no,
		producingCompanyName=reception_note.producing_company_name,
		producingCompanyEmirate=reception_note.producing_company_emirate,
		producingCompanyOfficeAddress=reception_note.producing_company_office_address,
		producingCompanyContactPerson=reception_note.producing_company_contact_person,
		producingCompanyOfficePhone=reception_note.producing_company_office_phone,
		producingCompanyEmail=reception_note.producing_company_email,
		transportingCompanyName=reception_note.transporting_company_name,
		transportingCompanyContactPerson=reception_note.transporting_company_contact_person,
		transportingCompanyOfficePhone=reception_note.transporting_company_office_phone,
		transportingCompanyEmail=reception_note.transporting_company_email,
		wasteStreams=normalized_waste_streams,
		vehiclePlateNo=reception_note.vehicle_plate_no,
		driverName=reception_note.driver_name,
		wasteStreamName=reception_note.waste_stream_name,
		wasteStreamQuantity=reception_note.waste_stream_quantity,
		rnIssuedBy=reception_note.rn_issued_by,
		status=normalize_status(reception_note.status),
	)


def normalize_customer_id(customer_id: str) -> str:
	digits = re.sub(r"\D", "", customer_id)

	if not digits:
		raise ValueError("A valid customer ID is required.")

	return f"CID-{int(digits):04d}"


def extract_customer_sequence_value(customer_id: str) -> str:
	digits = re.sub(r"\D", "", customer_id)
	return f"{int(digits):04d}"


def normalize_rnid(rnid: str) -> str:
	normalized_rnid = rnid.strip().upper()

	if not RECEPTION_NOTE_ID_PATTERN.fullmatch(normalized_rnid):
		raise ValueError("A valid reception note ID is required.")

	matched_rnid = RECEPTION_NOTE_ID_PATTERN.fullmatch(normalized_rnid)
	return f"RNID-{int(matched_rnid.group(1)):04d}-{matched_rnid.group(2)}"


def validate_reception_note_id(rnid: str, customer_id: str) -> None:
	customer_sequence = extract_customer_sequence_value(customer_id)
	matched_rnid = RECEPTION_NOTE_ID_PATTERN.fullmatch(rnid)

	if matched_rnid is None or int(matched_rnid.group(1)) != int(customer_sequence):
		raise ValueError("Reception note ID does not match the selected customer ID.")


def normalize_status(status: str) -> str:
	if status.strip().lower() == "draft":
		return "Draft"

	return "Issued"


def normalize_waste_stream(waste_stream: dict[str, str]) -> dict[str, str]:
	quantity, quantity_unit = split_quantity_and_unit(
		str(waste_stream.get("quantity", "")).strip(),
		str(waste_stream.get("quantityUnit", "")).strip(),
	)

	return {
		"code": str(waste_stream.get("code", "")).strip(),
		"name": str(waste_stream.get("name", "")).strip(),
		"wasteClass": str(waste_stream.get("wasteClass", "")).strip(),
		"physicalState": str(waste_stream.get("physicalState", "")).strip(),
		"quantity": quantity,
		"quantityUnit": quantity_unit,
		"receptionDate": normalize_optional_date_for_storage(waste_stream.get("receptionDate", ""), "Reception Date"),
		"collectionEmirate": str(waste_stream.get("collectionEmirate", "")).strip(),
		"collectionLocation": str(waste_stream.get("collectionLocation", "")).strip(),
	}


def build_reception_note_pdf_context(reception_note: ReceptionNote) -> dict[str, str]:
	primary_waste_stream = get_primary_waste_stream(reception_note)
	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(reception_note.waste_stream_quantity)
	total_quantity = calculate_reception_note_total_quantity(reception_note)

	return {
		"rnid_date": normalize_date_for_output(reception_note.rnid_date),
		"rnid": normalize_rnid(reception_note.rnid),
		"customer_id": reception_note.customer_id,
		"total_quantity": total_quantity or fallback_quantity,
		"customer_name": reception_note.producing_company_name,
		"producing_company_emirate": reception_note.producing_company_emirate,
		"producing_company_office_address": reception_note.producing_company_office_address,
		"producing_company_contact_person": reception_note.producing_company_contact_person,
		"producing_company_office_phone": reception_note.producing_company_office_phone,
		"producing_company_email": reception_note.producing_company_email,
		"transporting_company_name": reception_note.transporting_company_name,
		"transporting_company_contact_person": reception_note.transporting_company_contact_person,
		"transporting_company_office_phone": reception_note.transporting_company_office_phone,
		"transporting_company_email": reception_note.transporting_company_email,
		"vehicle_number": reception_note.vehicle_plate_no,
		"vehicle_plate_no": reception_note.vehicle_plate_no,
		"driver_name": reception_note.driver_name,
		"waste_stream_code": primary_waste_stream["code"],
		"waste_stream_name": primary_waste_stream["name"] or reception_note.waste_stream_name,
		"waste_stream_class": primary_waste_stream["wasteClass"],
		"waste_stream_physical_state": primary_waste_stream["physicalState"],
		"waste_stream_quantity": primary_waste_stream["quantity"] or fallback_quantity,
		"waste_stream_quantity_unit": primary_waste_stream["quantityUnit"] or fallback_quantity_unit,
		"waste_stream_collection_emirate": primary_waste_stream["collectionEmirate"],
		"waste_stream_collection_location": primary_waste_stream["collectionLocation"],
		"waste_stream_reception_date": normalize_date_for_output(primary_waste_stream["receptionDate"]),
		"issued_by": reception_note.rn_issued_by,
	}


def get_primary_waste_stream(reception_note: ReceptionNote) -> dict[str, str]:
	waste_streams = reception_note.waste_streams or []
	if not waste_streams:
		return normalize_waste_stream({})

	return normalize_waste_stream(waste_streams[0])


def calculate_reception_note_total_quantity(reception_note: ReceptionNote) -> str:
	waste_streams = reception_note.waste_streams or []

	if waste_streams:
		return sum_quantity_values(
			[
				normalize_waste_stream(waste_stream)["quantity"]
				for waste_stream in waste_streams
			],
		)

	return sum_quantity_values([split_quantity_and_unit(reception_note.waste_stream_quantity)[0]])


def split_quantity_and_unit(quantity_value: str, quantity_unit: str = "") -> tuple[str, str]:
	trimmed_quantity = quantity_value.strip()
	trimmed_unit = quantity_unit.strip()

	if not trimmed_quantity:
		return "", trimmed_unit

	match = QUANTITY_WITH_UNIT_PATTERN.fullmatch(trimmed_quantity)
	if match is None:
		return trimmed_quantity, trimmed_unit

	parsed_quantity = match.group(1).strip()
	parsed_unit = match.group(2).strip()
	return parsed_quantity, trimmed_unit or parsed_unit


def sum_quantity_values(quantity_values: list[str]) -> str:
	total = Decimal("0")

	for quantity_value in quantity_values:
		parsed_quantity = parse_decimal_quantity(quantity_value)

		if parsed_quantity is not None:
			total += parsed_quantity

	return format_decimal_quantity(total)


def parse_decimal_quantity(quantity_value: str) -> Decimal | None:
	trimmed_quantity = str(quantity_value).strip().replace(",", "")

	if not trimmed_quantity:
		return None

	try:
		return Decimal(trimmed_quantity)
	except InvalidOperation:
		return None


def format_decimal_quantity(quantity_value: Decimal) -> str:
	if quantity_value == quantity_value.to_integral():
		return str(int(quantity_value))

	normalized_quantity = format(quantity_value.normalize(), "f")
	return normalized_quantity.rstrip("0").rstrip(".")
