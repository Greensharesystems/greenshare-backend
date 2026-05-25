import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, can_access_customer_data, get_customer_scope_id, has_shared_platform_access
from app.core.date_utils import normalize_date_for_output, normalize_date_for_storage
from app.models.circularity_certificate import CircularityCertificate
from app.repositories import circularity_certificate_repository, reception_certificate_repository, reception_note_repository
from app.schemas.circularity_certificate import (
	CircularityCertificateCreate,
	CircularityCertificateResponse,
	NextCircularityCertificateIdResponse,
)
from app.services.pdf_generation_service import generate_pdf


RECEPTION_CERTIFICATE_ID_PATTERN = re.compile(r"(?:RCID|RC)-(\d+)-(\d+)")
LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN = re.compile(r"(?:RCID|RC)-(\d+)-(\d+)-(\d+)")
CIRCULARITY_CERTIFICATE_ID_PATTERN = re.compile(r"(?:CCID|CC)-(\d+)-(\d+)")
LEGACY_CIRCULARITY_CERTIFICATE_ID_PATTERN = re.compile(r"(?:CCID|CC)-(\d+)-(\d+)-(\d+)-(\d+)")
QUANTITY_WITH_UNIT_PATTERN = re.compile(r"^\s*([-+]?\d[\d,]*(?:\.\d+)?)\s+(.+?)\s*$")


def list_circularity_certificates(db: Session, principal: AuthPrincipal) -> list[CircularityCertificateResponse]:
	circularity_certificates = get_visible_circularity_certificates(db, principal)
	return [serialize_circularity_certificate(circularity_certificate) for circularity_certificate in circularity_certificates]


def get_next_circularity_certificate_id(db: Session, rcid: str) -> NextCircularityCertificateIdResponse:
	primary_rcid = normalize_rcid(rcid)
	return NextCircularityCertificateIdResponse(ccid=generate_next_circularity_certificate_id(db, get_customer_id_from_rcid(primary_rcid)))


def create_circularity_certificate(db: Session, payload: CircularityCertificateCreate, principal: AuthPrincipal) -> CircularityCertificateResponse:
	ccid_date = normalize_date_for_storage(payload.ccidDate, "Circularity Certificate ID Date")
	issued_by = payload.issuedBy.strip()
	linked_rcids = normalize_linked_rcids(payload.linkedRcids, payload.rcid)
	linked_reception_certificates = get_linked_reception_certificates(db, linked_rcids, principal)
	customer_ids = {certificate.customer_id for certificate in linked_reception_certificates}
	secondary_ecosystem_details = build_secondary_ecosystem_details(
		payload.secondaryEcosystemDetails,
		linked_reception_certificates,
		payload.secondaryProduct.strip(),
		payload.secondaryLoop.strip(),
	)
	secondary_summary = build_secondary_ecosystem_summary(secondary_ecosystem_details)
	secondary_product = secondary_summary["secondary_product"]
	secondary_loop = secondary_summary["secondary_loop"]

	if not ccid_date or not issued_by or not secondary_product or not secondary_loop:
		raise ValueError("All required circularity certificate fields must be provided.")

	if len(customer_ids) != 1:
		raise ValueError("All linked reception certificates must belong to the same customer.")

	ccid = generate_next_circularity_certificate_id(db, next(iter(customer_ids)))

	if circularity_certificate_repository.get_circularity_certificate_by_ccid(db, ccid):
		raise ValueError("That circularity certificate ID is already in use.")

	circularity_certificate = CircularityCertificate(
		ccid_date=ccid_date,
		ccid=ccid,
		rcid=", ".join(linked_rcids),
		linked_rcids=linked_rcids,
		cid=next(iter(customer_ids)),
		producing_company_name=linked_reception_certificates[0].producing_company_name,
		waste_stream_quantity=join_unique_values(
			[certificate.waste_stream_quantity for certificate in linked_reception_certificates if certificate.waste_stream_quantity.strip()],
		),
		secondary_ecosystem_details=secondary_ecosystem_details,
		secondary_product=secondary_product,
		secondary_loop=secondary_loop,
		issued_by=issued_by,
		owner_identifier=principal.identifier,
		owner_role=principal.role,
		status=normalize_status(payload.status),
	)

	created_circularity_certificate = circularity_certificate_repository.create_circularity_certificate(db, circularity_certificate)
	return serialize_circularity_certificate(created_circularity_certificate)


def delete_circularity_certificate(db: Session, ccid: str, principal: AuthPrincipal) -> None:
	normalized_ccid = normalize_ccid(ccid)
	circularity_certificate = circularity_certificate_repository.get_circularity_certificate_by_ccid(db, normalized_ccid)

	if circularity_certificate is None:
		raise ValueError("That circularity certificate could not be found.")

	if not can_access_circularity_certificate(circularity_certificate, principal):
		raise ValueError("That circularity certificate could not be found.")

	try:
		circularity_certificate_repository.delete_circularity_certificate(db, circularity_certificate)
		db.commit()
	except Exception:
		db.rollback()
		raise


def generate_circularity_certificate_pdf(
	db: Session,
	circularity_certificate_reference: int | str,
	principal: AuthPrincipal,
) -> tuple[str, bytes]:
	circularity_certificate = get_circularity_certificate_for_pdf(db, circularity_certificate_reference)

	if circularity_certificate is None or not can_access_circularity_certificate(circularity_certificate, principal):
		raise ValueError("That circularity certificate could not be found.")

	linked_reception_certificates = get_linked_reception_certificates(db, list(circularity_certificate.linked_rcids or []), principal)
	context = build_circularity_certificate_pdf_context(db, circularity_certificate, linked_reception_certificates)
	normalized_ccid = normalize_ccid(circularity_certificate.ccid)
	pdf_bytes = generate_pdf(
		"pdf/circularity_certificate.html",
		context,
		document_type="circularity-certificate",
		document_id=normalized_ccid,
		cache_key=normalized_ccid,
	)
	filename = f"{normalized_ccid}.pdf"
	return filename, pdf_bytes


def get_circularity_certificate_for_pdf(
	db: Session,
	circularity_certificate_reference: int | str,
) -> CircularityCertificate | None:
	if isinstance(circularity_certificate_reference, int):
		return circularity_certificate_repository.get_circularity_certificate_by_id(db, circularity_certificate_reference)

	trimmed_reference = str(circularity_certificate_reference).strip()

	if not trimmed_reference:
		return None

	if trimmed_reference.isdigit():
		return circularity_certificate_repository.get_circularity_certificate_by_id(db, int(trimmed_reference))

	return circularity_certificate_repository.get_circularity_certificate_by_ccid(db, trimmed_reference)


def generate_next_circularity_certificate_id(db: Session, customer_id: str) -> str:
	customer_segment = normalize_customer_segment(customer_id)
	max_number = max(
		(
			int(match.group(2))
			for ccid in circularity_certificate_repository.get_circularity_certificate_ids(db)
			for match in [CIRCULARITY_CERTIFICATE_ID_PATTERN.fullmatch(normalize_ccid(ccid))]
			if match is not None and int(match.group(1)) == int(customer_segment)
		),
		default=0,
	)
	return f"CCID-{customer_segment}-{max_number + 1:04d}"


def serialize_circularity_certificate(circularity_certificate: CircularityCertificate) -> CircularityCertificateResponse:
	return CircularityCertificateResponse(
		id=circularity_certificate.id,
		ccidDate=normalize_date_for_output(circularity_certificate.ccid_date),
		ccid=circularity_certificate.ccid,
		rcid=circularity_certificate.rcid,
		linkedRcids=list(circularity_certificate.linked_rcids or []),
		cid=circularity_certificate.cid,
		producingCompanyName=circularity_certificate.producing_company_name,
		wasteStreamQuantity=circularity_certificate.waste_stream_quantity,
		secondaryProduct=circularity_certificate.secondary_product,
		secondaryLoop=circularity_certificate.secondary_loop,
		secondaryEcosystemDetails=normalize_stored_secondary_ecosystem_details(
			circularity_certificate.secondary_ecosystem_details,
			circularity_certificate.secondary_product,
			circularity_certificate.secondary_loop,
		),
		issuedBy=circularity_certificate.issued_by,
		status=normalize_status(circularity_certificate.status),
	)


def get_linked_reception_certificates(db: Session, linked_rcids: list[str], principal: AuthPrincipal):
	reception_certificates = []

	for rcid in linked_rcids:
		reception_certificate = reception_certificate_repository.get_reception_certificate_by_rcid(db, rcid)

		if reception_certificate is None:
			raise ValueError(f"Reception certificate {rcid} could not be found.")

		if normalize_status(reception_certificate.status) != "Issued":
			raise ValueError(f"Reception certificate {rcid} must be issued before creating a circularity certificate.")

		if not can_access_reception_certificate(reception_certificate, principal):
			raise ValueError(f"Reception certificate {rcid} could not be found.")

		reception_certificates.append(reception_certificate)

	return reception_certificates


def get_visible_circularity_certificates(db: Session, principal: AuthPrincipal) -> list[CircularityCertificate]:
	if has_shared_platform_access(principal):
		return circularity_certificate_repository.get_circularity_certificates(db)

	return circularity_certificate_repository.get_circularity_certificates_by_customer_id(db, get_customer_scope_id(principal))


def can_access_reception_certificate(reception_certificate, principal: AuthPrincipal) -> bool:
	return can_access_customer_data(principal, reception_certificate.customer_id)


def can_access_circularity_certificate(circularity_certificate: CircularityCertificate, principal: AuthPrincipal) -> bool:
	return can_access_customer_data(principal, circularity_certificate.cid)


def normalize_linked_rcids(linked_rcids: list[str], rcid_summary: str) -> list[str]:
	raw_values = linked_rcids if linked_rcids else rcid_summary.split(",")
	normalized_values: list[str] = []
	seen_values: set[str] = set()

	for value in raw_values:
		trimmed_value = str(value).strip()

		if not trimmed_value:
			continue

		normalized_value = normalize_rcid(trimmed_value)

		if normalized_value in seen_values:
			continue

		seen_values.add(normalized_value)
		normalized_values.append(normalized_value)

	if not normalized_values:
		raise ValueError("At least one issued reception certificate is required.")

	return normalized_values


def normalize_rcid(rcid: str) -> str:
	normalized_rcid = rcid.strip().upper()

	matched_rcid = RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if matched_rcid is not None:
		return f"RCID-{int(matched_rcid.group(1)):04d}-{matched_rcid.group(2)}"

	legacy_match = LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if legacy_match is None:
		raise ValueError("A valid reception certificate ID is required.")

	return f"RCID-{int(legacy_match.group(1)):04d}-{legacy_match.group(2)}-{legacy_match.group(3)}"


def normalize_ccid(ccid: str) -> str:
	normalized_ccid = ccid.strip().upper()

	matched_ccid = CIRCULARITY_CERTIFICATE_ID_PATTERN.fullmatch(normalized_ccid)

	if matched_ccid is not None:
		return f"CCID-{int(matched_ccid.group(1)):04d}-{matched_ccid.group(2)}"

	legacy_match = LEGACY_CIRCULARITY_CERTIFICATE_ID_PATTERN.fullmatch(normalized_ccid)

	if legacy_match is None:
		raise ValueError("A valid circularity certificate ID is required.")

	return f"CCID-{int(legacy_match.group(1)):04d}-{legacy_match.group(2)}-{legacy_match.group(3)}-{legacy_match.group(4)}"


def parse_rcid_parts(rcid: str) -> tuple[str, str]:
	normalized_rcid = normalize_rcid(rcid)
	matched_rcid = RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if matched_rcid is not None:
		return matched_rcid.group(1), matched_rcid.group(2)

	legacy_match = LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if legacy_match is None:
		raise ValueError("A valid reception certificate ID is required.")

	return legacy_match.group(1), legacy_match.group(3)


def validate_circularity_certificate_id(ccid: str, rcid: str) -> None:
	matched_ccid = CIRCULARITY_CERTIFICATE_ID_PATTERN.fullmatch(normalize_ccid(ccid))
	rcid_parts = parse_rcid_parts(rcid)

	if matched_ccid is None or int(matched_ccid.group(1)) != int(rcid_parts[0]):
		raise ValueError("Circularity certificate ID does not match the selected reception certificate.")


def get_customer_id_from_rcid(rcid: str) -> str:
	return f"CID-{parse_rcid_parts(rcid)[0]}"


def normalize_customer_segment(customer_id: str) -> str:
	matched_customer_id = re.fullmatch(r"CID-(\d+)", customer_id.strip().upper())

	if matched_customer_id is not None:
		return f"{int(matched_customer_id.group(1)):04d}"

	matched_rcid = RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(customer_id.strip().upper())

	if matched_rcid is not None:
		return f"{int(matched_rcid.group(1)):04d}"

	legacy_match = LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(customer_id.strip().upper())

	if legacy_match is not None:
		return f"{int(legacy_match.group(1)):04d}"

	raise ValueError("A valid customer ID is required.")


def normalize_status(status: str) -> str:
	if status.strip().lower() == "draft":
		return "Draft"

	return "Issued"


def join_unique_values(values: list[str]) -> str:
	seen_values: list[str] = []

	for value in values:
		normalized_value = value.strip()

		if normalized_value and normalized_value not in seen_values:
			seen_values.append(normalized_value)

	return ", ".join(seen_values)


PDF_VERIFIED_BY = "Imran Gill"
PDF_VERIFIED_BY_POSITION = "CEO"
SECONDARY_ECOSYSTEM_SHARED_MODE = "shared"
SECONDARY_ECOSYSTEM_BY_RC_MODE = "by_rc"
SECONDARY_ECOSYSTEM_BY_RN_MODE = "by_rn"


def build_circularity_certificate_pdf_context(
	db: Session,
	circularity_certificate: CircularityCertificate,
	linked_reception_certificates: list,
) -> dict[str, object]:
	secondary_ecosystem_details = normalize_stored_secondary_ecosystem_details(
		circularity_certificate.secondary_ecosystem_details,
		circularity_certificate.secondary_product,
		circularity_certificate.secondary_loop,
	)
	linked_entries = [build_linked_reception_certificate_entry_context(db, certificate) for certificate in linked_reception_certificates]
	apply_secondary_ecosystem_to_linked_entries(linked_entries, secondary_ecosystem_details)
	primary_entry = linked_entries[0] if linked_entries else build_empty_linked_reception_certificate_entry_context()
	shared_producing_company = build_shared_producing_company_context(circularity_certificate, linked_entries)
	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(circularity_certificate.waste_stream_quantity)
	has_expanded_linked_notes = any(bool(entry["has_multiple_linked_notes"]) for entry in linked_entries)
	total_quantity = calculate_circularity_certificate_total_quantity(linked_entries)

	return {
		"ccid_date": normalize_date_for_output(circularity_certificate.ccid_date),
		"ccid": normalize_ccid(circularity_certificate.ccid),
		"customer_id": circularity_certificate.cid,
		"total_quantity": total_quantity or fallback_quantity,
		"linked_rcids": ", ".join(list(circularity_certificate.linked_rcids or [])) or circularity_certificate.rcid,
		"has_multiple_linked_entries": len(linked_entries) > 1,
		"has_expanded_linked_entries": len(linked_entries) > 1 or has_expanded_linked_notes,
		"linked_entries": linked_entries,
		"producing_company_name": shared_producing_company["name"],
		"producing_company_emirate": shared_producing_company["emirate"],
		"producing_company_office_address": shared_producing_company["office_address"],
		"producing_company_contact_person": shared_producing_company["contact_person"],
		"producing_company_office_phone": shared_producing_company["office_phone"],
		"producing_company_email": shared_producing_company["email"],
		"transporting_company_name": primary_entry["transporting_company"]["name"],
		"transporting_company_contact_person": primary_entry["transporting_company"]["contact_person"],
		"transporting_company_office_phone": primary_entry["transporting_company"]["office_phone"],
		"transporting_company_email": primary_entry["transporting_company"]["email"],
		"vehicle_plate_no": primary_entry["vehicle_details"]["vehicle_plate_no"],
		"driver_name": primary_entry["vehicle_details"]["driver_name"],
		"waste_stream_code": primary_entry["primary_waste_stream"]["code"],
		"waste_stream_name": primary_entry["primary_waste_stream"]["name"],
		"waste_stream_class": primary_entry["primary_waste_stream"]["waste_class"],
		"waste_stream_physical_state": primary_entry["primary_waste_stream"]["physical_state"],
		"waste_stream_quantity": primary_entry["primary_waste_stream"]["quantity"] or fallback_quantity,
		"waste_stream_quantity_unit": primary_entry["primary_waste_stream"]["quantity_unit"] or fallback_quantity_unit,
		"waste_stream_collection_emirate": primary_entry["primary_waste_stream"]["collection_emirate"],
		"waste_stream_collection_location": primary_entry["primary_waste_stream"]["collection_location"],
		"waste_stream_reception_date": normalize_date_for_output(primary_entry["primary_waste_stream"]["reception_date"]),
		"facilities_name": "Zero Waste - Circular Processing Facilities",
		"secondary_ecosystem_mode": secondary_ecosystem_details["mode"],
		"show_shared_secondary_ecosystem_section": secondary_ecosystem_details["mode"] == SECONDARY_ECOSYSTEM_SHARED_MODE,
		"secondary_ecosystem": {
			"secondary_product": secondary_ecosystem_details["shared"]["secondaryProduct"],
			"secondary_loop": secondary_ecosystem_details["shared"]["secondaryLoop"],
		},
		"secondary_product": circularity_certificate.secondary_product,
		"secondary_loop": circularity_certificate.secondary_loop,
		"issued_by": circularity_certificate.issued_by,
		"verified_by": PDF_VERIFIED_BY,
		"verified_by_position": PDF_VERIFIED_BY_POSITION,
		"status": normalize_status(circularity_certificate.status),
	}


def build_shared_producing_company_context(
	circularity_certificate: CircularityCertificate,
	linked_entries: list[dict[str, object]],
) -> dict[str, str]:
	if not linked_entries:
		return {
			"name": circularity_certificate.producing_company_name,
			"emirate": "",
			"office_address": "",
			"contact_person": "",
			"office_phone": "",
			"email": "",
		}

	return {
		"name": join_unique_values([str(entry["producing_company"]["name"]) for entry in linked_entries]) or circularity_certificate.producing_company_name,
		"emirate": join_unique_values([str(entry["producing_company"]["emirate"]) for entry in linked_entries]),
		"office_address": join_unique_values([str(entry["producing_company"]["office_address"]) for entry in linked_entries]),
		"contact_person": join_unique_values([str(entry["producing_company"]["contact_person"]) for entry in linked_entries]),
		"office_phone": join_unique_values([str(entry["producing_company"]["office_phone"]) for entry in linked_entries]),
		"email": join_unique_values([str(entry["producing_company"]["email"]) for entry in linked_entries]),
	}


def build_linked_reception_certificate_entry_context(db: Session, reception_certificate) -> dict[str, object]:
	upstream_context = build_reception_certificate_upstream_context(db, reception_certificate)
	linked_notes = build_linked_reception_note_contexts(db, reception_certificate)
	primary_waste_stream = {
		"code": upstream_context["waste_stream_code"],
		"name": upstream_context["waste_stream_name"],
		"waste_class": upstream_context["waste_stream_class"],
		"physical_state": upstream_context["waste_stream_physical_state"],
		"quantity": upstream_context["waste_stream_quantity"],
		"quantity_unit": upstream_context["waste_stream_quantity_unit"],
		"collection_emirate": upstream_context["waste_stream_collection_emirate"],
		"collection_location": upstream_context["waste_stream_collection_location"],
		"reception_date": upstream_context["waste_stream_reception_date"],
	}
	linked_rnids = get_linked_rnids_from_reception_certificate(reception_certificate)

	return {
		"rcid": normalize_rcid(reception_certificate.rcid),
		"linked_rnids_count": len(linked_rnids),
		"has_multiple_linked_notes": len(linked_rnids) > 1,
		"linked_notes": linked_notes,
		"secondary_product": "",
		"secondary_loop": "",
		"secondary_ecosystem": build_empty_secondary_ecosystem_context(),
		"producing_company": {
			"name": reception_certificate.producing_company_name,
			"emirate": upstream_context["producing_company_emirate"],
			"office_address": upstream_context["producing_company_office_address"],
			"contact_person": upstream_context["producing_company_contact_person"],
			"office_phone": upstream_context["producing_company_office_phone"],
			"email": upstream_context["producing_company_email"],
		},
		"transporting_company": {
			"name": upstream_context["transporting_company_name"],
			"contact_person": upstream_context["transporting_company_contact_person"],
			"office_phone": upstream_context["transporting_company_office_phone"],
			"email": upstream_context["transporting_company_email"],
		},
		"vehicle_details": {
			"vehicle_plate_no": upstream_context["vehicle_plate_no"],
			"driver_name": upstream_context["driver_name"],
		},
		"primary_waste_stream": primary_waste_stream,
		"waste_streams": [primary_waste_stream],
	}


def build_empty_linked_reception_certificate_entry_context() -> dict[str, object]:
	empty_waste_stream = build_empty_waste_stream_context()
	return {
		"rcid": "",
		"linked_rnids_count": 0,
		"has_multiple_linked_notes": False,
		"linked_notes": [],
		"secondary_product": "",
		"secondary_loop": "",
		"secondary_ecosystem": build_empty_secondary_ecosystem_context(),
		"producing_company": {
			"name": "",
			"emirate": "",
			"office_address": "",
			"contact_person": "",
			"office_phone": "",
			"email": "",
		},
		"transporting_company": {
			"name": "",
			"contact_person": "",
			"office_phone": "",
			"email": "",
		},
		"vehicle_details": {
			"vehicle_plate_no": "",
			"driver_name": "",
		},
		"primary_waste_stream": empty_waste_stream,
		"waste_streams": [empty_waste_stream],
	}


def build_linked_reception_note_contexts(db: Session, reception_certificate) -> list[dict[str, object]]:
	linked_notes: list[dict[str, object]] = []

	for rnid in get_linked_rnids_from_reception_certificate(reception_certificate):
		reception_note = reception_note_repository.get_reception_note_by_rnid(db, rnid)

		if reception_note is None:
			linked_notes.append(build_empty_linked_reception_note_entry_context(rnid))
			continue

		linked_notes.append(build_linked_reception_note_entry_context(reception_note))

	return linked_notes


def build_linked_reception_note_entry_context(reception_note) -> dict[str, object]:
	waste_streams = build_linked_reception_note_waste_streams_context(reception_note)
	primary_waste_stream = waste_streams[0] if waste_streams else build_empty_waste_stream_context()

	return {
		"rnid": reception_note.rnid,
		"secondary_ecosystem": build_empty_secondary_ecosystem_context(),
		"transporting_company": {
			"name": reception_note.transporting_company_name,
			"contact_person": reception_note.transporting_company_contact_person,
			"office_phone": reception_note.transporting_company_office_phone,
			"email": reception_note.transporting_company_email,
		},
		"vehicle_details": {
			"vehicle_plate_no": reception_note.vehicle_plate_no,
			"driver_name": reception_note.driver_name,
		},
		"primary_waste_stream": primary_waste_stream,
		"waste_streams": waste_streams,
	}


def build_empty_linked_reception_note_entry_context(rnid: str = "") -> dict[str, object]:
	empty_waste_stream = build_empty_waste_stream_context()

	return {
		"rnid": rnid,
		"secondary_ecosystem": build_empty_secondary_ecosystem_context(),
		"transporting_company": {
			"name": "",
			"contact_person": "",
			"office_phone": "",
			"email": "",
		},
		"vehicle_details": {
			"vehicle_plate_no": "",
			"driver_name": "",
		},
		"primary_waste_stream": empty_waste_stream,
		"waste_streams": [empty_waste_stream],
	}


def build_linked_reception_note_waste_streams_context(reception_note) -> list[dict[str, str]]:
	waste_streams = reception_note.waste_streams or []

	if waste_streams:
		return [build_waste_stream_context(stream) for stream in waste_streams]

	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(reception_note.waste_stream_quantity)
	return [
		{
			"code": "",
			"name": reception_note.waste_stream_name,
			"waste_class": "",
			"physical_state": "",
			"quantity": fallback_quantity,
			"quantity_unit": fallback_quantity_unit,
			"collection_emirate": "",
			"collection_location": "",
			"reception_date": "",
		}
	]


def build_waste_stream_context(waste_stream: dict[str, object]) -> dict[str, str]:
	quantity_value, quantity_unit = split_quantity_and_unit(
		str(waste_stream.get("quantity", "") or ""),
		str(waste_stream.get("quantityUnit", "") or ""),
	)

	return {
		"code": str(waste_stream.get("code", "") or ""),
		"name": str(waste_stream.get("name", "") or ""),
		"waste_class": str(waste_stream.get("wasteClass", "") or ""),
		"physical_state": str(waste_stream.get("physicalState", "") or ""),
		"quantity": quantity_value,
		"quantity_unit": quantity_unit,
		"collection_emirate": str(waste_stream.get("collectionEmirate", "") or ""),
		"collection_location": str(waste_stream.get("collectionLocation", "") or ""),
		"reception_date": normalize_date_for_output(str(waste_stream.get("receptionDate", "") or "")),
	}


def build_empty_waste_stream_context() -> dict[str, str]:
	return {
		"code": "",
		"name": "",
		"waste_class": "",
		"physical_state": "",
		"quantity": "",
		"quantity_unit": "",
		"collection_emirate": "",
		"collection_location": "",
		"reception_date": "",
	}


def calculate_circularity_certificate_total_quantity(linked_entries: list[dict[str, object]]) -> str:
	quantity_values: list[str] = []

	for entry in linked_entries:
		linked_notes = entry.get("linked_notes") or []

		if linked_notes:
			for note in linked_notes:
				for waste_stream in note.get("waste_streams") or []:
					quantity_values.append(str(waste_stream.get("quantity", "") or ""))
			continue

		primary_waste_stream = entry.get("primary_waste_stream") or {}
		quantity_values.append(str(primary_waste_stream.get("quantity", "") or ""))

	return sum_quantity_values(quantity_values)


def get_linked_rnids_from_reception_certificate(reception_certificate) -> list[str]:
	linked_rnid_values = list(reception_certificate.linked_rnids or [])

	if linked_rnid_values:
		return [str(value).strip() for value in linked_rnid_values if str(value).strip()]

	return [value.strip() for value in str(reception_certificate.rnid or "").split(",") if value.strip()]


def build_upstream_reception_context(db: Session, linked_reception_certificates: list) -> dict[str, str]:
	primary_reception_certificate = linked_reception_certificates[0] if linked_reception_certificates else None

	if primary_reception_certificate is None:
		return empty_upstream_reception_context()

	return build_reception_certificate_upstream_context(db, primary_reception_certificate)


def build_reception_certificate_upstream_context(db: Session, reception_certificate) -> dict[str, str]:
	primary_certificate_quantity = split_quantity_and_unit(reception_certificate.waste_stream_quantity)
	linked_rnid_values = list(reception_certificate.linked_rnids or [])

	if not linked_rnid_values:
		return empty_upstream_reception_context(
			waste_stream_quantity=primary_certificate_quantity[0],
			waste_stream_quantity_unit=primary_certificate_quantity[1],
		)

	from app.services import reception_certificate_service

	primary_reception_note = reception_note_repository.get_reception_note_by_rnid(db, linked_rnid_values[0])

	if primary_reception_note is None:
		return empty_upstream_reception_context(
			waste_stream_quantity=primary_certificate_quantity[0],
			waste_stream_quantity_unit=primary_certificate_quantity[1],
		)

	primary_waste_stream = reception_certificate_service.get_primary_waste_stream(primary_reception_note.waste_streams)
	return {
		"producing_company_emirate": primary_reception_note.producing_company_emirate,
		"producing_company_office_address": primary_reception_note.producing_company_office_address,
		"producing_company_contact_person": primary_reception_note.producing_company_contact_person,
		"producing_company_office_phone": primary_reception_note.producing_company_office_phone,
		"producing_company_email": primary_reception_note.producing_company_email,
		"transporting_company_name": primary_reception_note.transporting_company_name,
		"transporting_company_contact_person": primary_reception_note.transporting_company_contact_person,
		"transporting_company_office_phone": primary_reception_note.transporting_company_office_phone,
		"transporting_company_email": primary_reception_note.transporting_company_email,
		"vehicle_plate_no": primary_reception_note.vehicle_plate_no,
		"driver_name": primary_reception_note.driver_name,
		"waste_stream_code": primary_waste_stream["code"],
		"waste_stream_name": primary_waste_stream["name"] or primary_reception_note.waste_stream_name,
		"waste_stream_class": primary_waste_stream["wasteClass"],
		"waste_stream_physical_state": primary_waste_stream["physicalState"],
		"waste_stream_quantity": primary_waste_stream["quantity"] or primary_certificate_quantity[0],
		"waste_stream_quantity_unit": primary_waste_stream["quantityUnit"] or primary_certificate_quantity[1],
		"waste_stream_collection_emirate": primary_waste_stream["collectionEmirate"],
		"waste_stream_collection_location": primary_waste_stream["collectionLocation"],
		"waste_stream_reception_date": normalize_date_for_output(primary_waste_stream["receptionDate"]),
	}


def empty_upstream_reception_context(
	waste_stream_quantity: str = "",
	waste_stream_quantity_unit: str = "",
) -> dict[str, str]:
	return {
		"producing_company_emirate": "",
		"producing_company_office_address": "",
		"producing_company_contact_person": "",
		"producing_company_office_phone": "",
		"producing_company_email": "",
		"transporting_company_name": "",
		"transporting_company_contact_person": "",
		"transporting_company_office_phone": "",
		"transporting_company_email": "",
		"vehicle_plate_no": "",
		"driver_name": "",
		"waste_stream_code": "",
		"waste_stream_name": "",
		"waste_stream_class": "",
		"waste_stream_physical_state": "",
		"waste_stream_quantity": waste_stream_quantity,
		"waste_stream_quantity_unit": waste_stream_quantity_unit,
		"waste_stream_collection_emirate": "",
		"waste_stream_collection_location": "",
		"waste_stream_reception_date": "",
	}


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


def build_secondary_ecosystem_details(
	secondary_ecosystem_details,
	linked_reception_certificates: list,
	fallback_secondary_product: str,
	fallback_secondary_loop: str,
) -> dict[str, object]:
	expected_mode = determine_secondary_ecosystem_mode(linked_reception_certificates)

	if expected_mode == SECONDARY_ECOSYSTEM_SHARED_MODE:
		shared_value = build_secondary_ecosystem_value(
			getattr(getattr(secondary_ecosystem_details, "shared", None), "secondaryProduct", fallback_secondary_product),
			getattr(getattr(secondary_ecosystem_details, "shared", None), "secondaryLoop", fallback_secondary_loop),
		)

		if not is_secondary_ecosystem_complete(shared_value):
			raise ValueError("Secondary ecosystem details must be provided.")

		return {
			"mode": SECONDARY_ECOSYSTEM_SHARED_MODE,
			"shared": shared_value,
			"entries": [],
		}

	if expected_mode == SECONDARY_ECOSYSTEM_BY_RC_MODE:
		payload_entries = {
			normalize_rcid(entry.rcid): entry
			for entry in getattr(secondary_ecosystem_details, "entries", [])
			if str(getattr(entry, "rcid", "")).strip()
		}
		normalized_entries: list[dict[str, str]] = []

		for reception_certificate in linked_reception_certificates:
			rcid = normalize_rcid(reception_certificate.rcid)
			entry = payload_entries.get(rcid)
			secondary_value = build_secondary_ecosystem_value(
				getattr(entry, "secondaryProduct", ""),
				getattr(entry, "secondaryLoop", ""),
			)

			if not is_secondary_ecosystem_complete(secondary_value):
				raise ValueError(f"Secondary ecosystem details must be provided for {rcid}.")

			normalized_entries.append({
				"rcid": rcid,
				"rnid": "",
				**secondary_value,
			})

		return {
			"mode": SECONDARY_ECOSYSTEM_BY_RC_MODE,
			"shared": build_empty_secondary_ecosystem_value(),
			"entries": normalized_entries,
		}

	reception_certificate = linked_reception_certificates[0] if linked_reception_certificates else None
	if reception_certificate is None:
		raise ValueError("At least one issued reception certificate is required.")

	rcid = normalize_rcid(reception_certificate.rcid)
	payload_entries = {
		str(getattr(entry, "rnid", "")).strip(): entry
		for entry in getattr(secondary_ecosystem_details, "entries", [])
		if str(getattr(entry, "rnid", "")).strip()
	}
	normalized_entries = []

	for rnid in get_linked_rnids_from_reception_certificate(reception_certificate):
		entry = payload_entries.get(rnid)
		secondary_value = build_secondary_ecosystem_value(
			getattr(entry, "secondaryProduct", ""),
			getattr(entry, "secondaryLoop", ""),
		)

		if not is_secondary_ecosystem_complete(secondary_value):
			raise ValueError(f"Secondary ecosystem details must be provided for {rnid}.")

		normalized_entries.append({
			"rcid": rcid,
			"rnid": rnid,
			**secondary_value,
		})

	return {
		"mode": SECONDARY_ECOSYSTEM_BY_RN_MODE,
		"shared": build_empty_secondary_ecosystem_value(),
		"entries": normalized_entries,
	}


def determine_secondary_ecosystem_mode(linked_reception_certificates: list) -> str:
	if len(linked_reception_certificates) > 1:
		return SECONDARY_ECOSYSTEM_BY_RC_MODE

	primary_certificate = linked_reception_certificates[0] if linked_reception_certificates else None
	if primary_certificate is not None and len(get_linked_rnids_from_reception_certificate(primary_certificate)) > 1:
		return SECONDARY_ECOSYSTEM_BY_RN_MODE

	return SECONDARY_ECOSYSTEM_SHARED_MODE


def normalize_stored_secondary_ecosystem_details(
	secondary_ecosystem_details: object,
	fallback_secondary_product: str,
	fallback_secondary_loop: str,
) -> dict[str, object]:
	if not isinstance(secondary_ecosystem_details, dict):
		return build_fallback_shared_secondary_ecosystem_details(fallback_secondary_product, fallback_secondary_loop)

	mode = str(secondary_ecosystem_details.get("mode", "")).strip()
	if mode not in {
		SECONDARY_ECOSYSTEM_SHARED_MODE,
		SECONDARY_ECOSYSTEM_BY_RC_MODE,
		SECONDARY_ECOSYSTEM_BY_RN_MODE,
	}:
		return build_fallback_shared_secondary_ecosystem_details(fallback_secondary_product, fallback_secondary_loop)

	shared_value = secondary_ecosystem_details.get("shared") if isinstance(secondary_ecosystem_details.get("shared"), dict) else {}
	normalized_shared_value = build_secondary_ecosystem_value(
		str(shared_value.get("secondaryProduct", fallback_secondary_product)),
		str(shared_value.get("secondaryLoop", fallback_secondary_loop)),
	)
	normalized_entries = []

	for entry in secondary_ecosystem_details.get("entries", []):
		if not isinstance(entry, dict):
			continue

		raw_rcid = str(entry.get("rcid", "")).strip()
		normalized_entries.append({
			"rcid": normalize_rcid(raw_rcid) if raw_rcid else "",
			"rnid": str(entry.get("rnid", "")).strip(),
			"secondaryProduct": str(entry.get("secondaryProduct", "")).strip(),
			"secondaryLoop": str(entry.get("secondaryLoop", "")).strip(),
		})

	if mode != SECONDARY_ECOSYSTEM_SHARED_MODE and not normalized_entries:
		return build_fallback_shared_secondary_ecosystem_details(fallback_secondary_product, fallback_secondary_loop)

	return {
		"mode": mode,
		"shared": normalized_shared_value,
		"entries": normalized_entries,
	}


def build_fallback_shared_secondary_ecosystem_details(
	fallback_secondary_product: str,
	fallback_secondary_loop: str,
) -> dict[str, object]:
	return {
		"mode": SECONDARY_ECOSYSTEM_SHARED_MODE,
		"shared": build_secondary_ecosystem_value(fallback_secondary_product, fallback_secondary_loop),
		"entries": [],
	}


def build_secondary_ecosystem_summary(secondary_ecosystem_details: dict[str, object]) -> dict[str, str]:
	if secondary_ecosystem_details["mode"] == SECONDARY_ECOSYSTEM_SHARED_MODE:
		shared_value = secondary_ecosystem_details["shared"]
		return {
			"secondary_product": str(shared_value["secondaryProduct"]),
			"secondary_loop": str(shared_value["secondaryLoop"]),
		}

	return {
		"secondary_product": join_unique_values([
			str(entry.get("secondaryProduct", ""))
			for entry in secondary_ecosystem_details["entries"]
		]),
		"secondary_loop": join_unique_values([
			str(entry.get("secondaryLoop", ""))
			for entry in secondary_ecosystem_details["entries"]
		]),
	}


def apply_secondary_ecosystem_to_linked_entries(
	linked_entries: list[dict[str, object]],
	secondary_ecosystem_details: dict[str, object],
) -> None:
	if secondary_ecosystem_details["mode"] == SECONDARY_ECOSYSTEM_BY_RC_MODE:
		entry_lookup = {
			str(entry.get("rcid", "")): build_secondary_ecosystem_context(entry)
			for entry in secondary_ecosystem_details["entries"]
		}

		for linked_entry in linked_entries:
			secondary_context = entry_lookup.get(
				str(linked_entry.get("rcid", "")),
				build_empty_secondary_ecosystem_context(),
			)
			linked_entry["secondary_ecosystem"] = secondary_context
			linked_entry["secondary_product"] = secondary_context["secondary_product"]
			linked_entry["secondary_loop"] = secondary_context["secondary_loop"]

		return

	if secondary_ecosystem_details["mode"] == SECONDARY_ECOSYSTEM_BY_RN_MODE:
		note_lookup = {
			(str(entry.get("rcid", "")), str(entry.get("rnid", ""))): build_secondary_ecosystem_context(entry)
			for entry in secondary_ecosystem_details["entries"]
		}

		for linked_entry in linked_entries:
			for linked_note in linked_entry.get("linked_notes", []):
				linked_note["secondary_ecosystem"] = note_lookup.get(
					(str(linked_entry.get("rcid", "")), str(linked_note.get("rnid", ""))),
					build_empty_secondary_ecosystem_context(),
				)


def build_secondary_ecosystem_context(value: dict[str, object]) -> dict[str, str]:
	return {
		"secondary_product": str(value.get("secondaryProduct", "")).strip(),
		"secondary_loop": str(value.get("secondaryLoop", "")).strip(),
	}


def build_secondary_ecosystem_value(secondary_product: str, secondary_loop: str) -> dict[str, str]:
	return {
		"secondaryProduct": secondary_product.strip(),
		"secondaryLoop": secondary_loop.strip(),
	}


def build_empty_secondary_ecosystem_value() -> dict[str, str]:
	return {
		"secondaryProduct": "",
		"secondaryLoop": "",
	}


def build_empty_secondary_ecosystem_context() -> dict[str, str]:
	return {
		"secondary_product": "",
		"secondary_loop": "",
	}


def is_secondary_ecosystem_complete(secondary_ecosystem_value: dict[str, str]) -> bool:
	return bool(secondary_ecosystem_value["secondaryProduct"] and secondary_ecosystem_value["secondaryLoop"])
