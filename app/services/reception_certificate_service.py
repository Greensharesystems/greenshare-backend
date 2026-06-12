import hashlib
import json
import logging
import re
import time
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.auth import AuthPrincipal, can_access_customer_data, get_customer_scope_id, has_shared_platform_access
from app.core.date_utils import normalize_date_for_output, normalize_date_for_storage, normalize_optional_date_for_storage
from app.models.reception_certificate import ReceptionCertificate
from app.repositories import reception_certificate_repository, reception_note_repository
from app.schemas.reception_certificate import (
	NextReceptionCertificateIdResponse,
	ReceptionCertificateCreate,
	ReceptionCertificateResponse,
	ReceptionCertificateUpdate,
)
from app.services.pdf_generation_service import generate_pdf
from app.services.certificate_pdf_cache_service import (
	build_pdf_content_fingerprint,
	get_or_create_certificate_pdf,
	invalidate_certificate_pdf_cache,
)


RECEPTION_NOTE_ID_PATTERN = re.compile(r"(?:RNID|RN)-(\d+)-(\d+)")
RECEPTION_CERTIFICATE_ID_PATTERN = re.compile(r"(?:RCID|RC)-(\d+)-(\d+)")
LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN = re.compile(r"(?:RCID|RC)-(\d+)-(\d+)-(\d+)")
QUANTITY_WITH_UNIT_PATTERN = re.compile(r"^\s*([-+]?\d[\d,]*(?:\.\d+)?)\s+(.+?)\s*$")
logger = logging.getLogger(__name__)


def list_reception_certificates(db: Session, principal: AuthPrincipal) -> list[ReceptionCertificateResponse]:
	reception_certificates = get_visible_reception_certificates(db, principal)
	return [serialize_reception_certificate(reception_certificate) for reception_certificate in reception_certificates]


def get_next_reception_certificate_id(db: Session, rnid: str) -> NextReceptionCertificateIdResponse:
	primary_rnid = normalize_rnid(rnid)
	return NextReceptionCertificateIdResponse(rcid=generate_next_reception_certificate_id(db, get_customer_id_from_rnid(primary_rnid)))


def create_reception_certificate(db: Session, payload: ReceptionCertificateCreate, principal: AuthPrincipal) -> ReceptionCertificateResponse:
	rcid_date = normalize_date_for_storage(payload.rcidDate, "Reception Certificate ID Date")
	rc_issued_by = payload.rcIssuedBy.strip()
	linked_rnids = normalize_linked_rnids(payload.linkedRnids, payload.rnid)
	linked_reception_notes = get_linked_reception_notes(db, linked_rnids, principal)
	customer_ids = {note.customer_id for note in linked_reception_notes}

	if not rcid_date or not rc_issued_by:
		raise ValueError("All required reception certificate fields must be provided.")

	if len(customer_ids) != 1:
		raise ValueError("All linked reception notes must belong to the same customer.")

	rcid = generate_next_reception_certificate_id(db, next(iter(customer_ids)))

	if reception_certificate_repository.get_reception_certificate_by_rcid(db, rcid):
		raise ValueError("That reception certificate ID is already in use.")

	reception_certificate = ReceptionCertificate(
		rcid_date=rcid_date,
		rcid=rcid,
		rnid=", ".join(linked_rnids),
		linked_rnids=linked_rnids,
		customer_id=next(iter(customer_ids)),
		producing_company_name=linked_reception_notes[0].producing_company_name,
		referring_company=payload.referringCompany if payload.referringCompany is not None else (linked_reception_notes[0].referring_company or None),
		project_name=payload.projectName if payload.projectName is not None else (linked_reception_notes[0].project_name or None),
		project_number=payload.projectNumber if payload.projectNumber is not None else (linked_reception_notes[0].project_number or None),
		project_location=payload.projectLocation if payload.projectLocation is not None else (linked_reception_notes[0].project_location or None),
		project_custom_fields=payload.projectCustomFields if payload.projectCustomFields is not None else (linked_reception_notes[0].project_custom_fields or None),
		verification_comments=payload.verificationComments or None,
		waste_stream_quantity=join_unique_values(
			[note.waste_stream_quantity for note in linked_reception_notes if note.waste_stream_quantity.strip()],
		),
		waste_stream_name=get_primary_waste_stream_name(linked_reception_notes[0]),
		waste_stream_class=get_primary_waste_stream_class(linked_reception_notes[0]),
		rc_issued_by=rc_issued_by,
		owner_identifier=principal.identifier,
		owner_role=principal.role,
		status=normalize_status(payload.status),
	)

	created_reception_certificate = reception_certificate_repository.create_reception_certificate(db, reception_certificate)
	pre_generate_reception_certificate_pdf(db, created_reception_certificate, principal)
	return serialize_reception_certificate(created_reception_certificate)


def delete_reception_certificate(db: Session, rcid: str, principal: AuthPrincipal) -> None:
	normalized_rcid = normalize_rcid(rcid)
	reception_certificate = reception_certificate_repository.get_reception_certificate_by_rcid(db, normalized_rcid)

	if reception_certificate is None:
		raise ValueError("That reception certificate could not be found.")

	if not can_access_reception_certificate(reception_certificate, principal):
		raise ValueError("That reception certificate could not be found.")

	try:
		reception_certificate_repository.soft_delete_reception_certificate(db, reception_certificate, principal.identifier)
		db.commit()
	except Exception:
		db.rollback()
		raise


def update_reception_certificate(db: Session, rcid: str, payload: ReceptionCertificateUpdate, principal: AuthPrincipal) -> ReceptionCertificateResponse:
	normalized_rcid = normalize_rcid(rcid)
	reception_certificate = reception_certificate_repository.get_reception_certificate_by_rcid(db, normalized_rcid)

	if reception_certificate is None:
		raise ValueError("That reception certificate could not be found.")

	if not can_access_reception_certificate(reception_certificate, principal):
		raise ValueError("That reception certificate could not be found.")

	if payload.rcidDate is not None:
		reception_certificate.rcid_date = normalize_date_for_storage(payload.rcidDate, "Reception Certificate ID Date")
	if payload.referringCompany is not None:
		reception_certificate.referring_company = payload.referringCompany or None
	if payload.projectName is not None:
		reception_certificate.project_name = payload.projectName or None
	if payload.projectNumber is not None:
		reception_certificate.project_number = payload.projectNumber or None
	if payload.projectLocation is not None:
		reception_certificate.project_location = payload.projectLocation or None
	if payload.projectCustomFields is not None:
		reception_certificate.project_custom_fields = payload.projectCustomFields or None
	if payload.verificationComments is not None:
		reception_certificate.verification_comments = payload.verificationComments or None
	if payload.rcIssuedBy is not None:
		reception_certificate.rc_issued_by = payload.rcIssuedBy.strip()
	if payload.status is not None:
		reception_certificate.status = normalize_status(payload.status)
	invalidate_certificate_pdf_cache(reception_certificate)

	try:
		db.commit()
		db.refresh(reception_certificate)
	except Exception:
		db.rollback()
		raise

	pre_generate_reception_certificate_pdf(db, reception_certificate, principal)
	return serialize_reception_certificate(reception_certificate)


def generate_reception_certificate_pdf(
	db: Session,
	reception_certificate_reference: int | str,
	principal: AuthPrincipal,
) -> tuple[str, bytes]:
	filename, pdf_bytes, _cache_hit = generate_reception_certificate_pdf_with_cache_status(db, reception_certificate_reference, principal)
	return filename, pdf_bytes


def generate_reception_certificate_pdf_with_cache_status(
	db: Session,
	reception_certificate_reference: int | str,
	principal: AuthPrincipal,
) -> tuple[str, bytes, bool]:
	reception_certificate = get_reception_certificate_for_pdf(db, reception_certificate_reference)

	if reception_certificate is None or not can_access_reception_certificate(reception_certificate, principal):
		raise ValueError("That reception certificate could not be found.")

	linked_reception_notes = get_linked_reception_notes(db, list(reception_certificate.linked_rnids or []), principal)
	context = build_reception_certificate_pdf_context(reception_certificate, linked_reception_notes)
	normalized_rcid = normalize_rcid(reception_certificate.rcid)
	context["document_title"] = normalized_rcid
	fingerprint = build_reception_certificate_pdf_fingerprint(normalized_rcid, context)
	filename, pdf_bytes, _cache_hit = get_or_create_certificate_pdf(
		db,
		reception_certificate,
		certificate_id=normalized_rcid,
		certificate_type="reception-certificate",
		fingerprint=fingerprint,
		render_pdf=lambda: render_reception_certificate_pdf(normalized_rcid, context),
	)
	return filename, pdf_bytes, _cache_hit


def pre_generate_reception_certificate_pdf(db: Session, reception_certificate: ReceptionCertificate, principal: AuthPrincipal) -> None:
	if normalize_status(reception_certificate.status) != "Issued":
		return

	started_at = time.perf_counter()
	try:
		generate_reception_certificate_pdf(db, reception_certificate.rcid, principal)
	except Exception as exc:
		logger.warning(
			"reception_certificate_pdf_pregeneration_failed",
			extra={
				"certificate_id": reception_certificate.rcid,
				"error_type": type(exc).__name__,
				"generation_time_ms": round((time.perf_counter() - started_at) * 1000, 2),
			},
		)
	else:
		logger.info(
			"reception_certificate_pdf_pregenerated",
			extra={
				"certificate_id": reception_certificate.rcid,
				"generation_time_ms": round((time.perf_counter() - started_at) * 1000, 2),
			},
		)


def render_reception_certificate_pdf(normalized_rcid: str, context: dict[str, object]) -> bytes:
	cache_key = build_reception_certificate_pdf_cache_key(normalized_rcid, context)
	return generate_pdf(
		"pdf/reception_certificate.html",
		context,
		document_type="reception-certificate",
		document_id=normalized_rcid,
		cache_key=cache_key,
		cache_enabled=True,
	)


def build_reception_certificate_pdf_fingerprint(normalized_rcid: str, context: dict[str, object]) -> str:
	return build_pdf_content_fingerprint({"certificate_id": normalized_rcid, "context": context})


def build_reception_certificate_pdf_cache_key(normalized_rcid: str, context: dict[str, object]) -> str:
	serialized_context = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
	context_digest = hashlib.sha256(serialized_context.encode("utf-8")).hexdigest()
	return f"{normalized_rcid}:{context_digest}"


def get_reception_certificate_for_pdf(
	db: Session,
	reception_certificate_reference: int | str,
) -> ReceptionCertificate | None:
	if isinstance(reception_certificate_reference, int):
		return reception_certificate_repository.get_reception_certificate_by_id(db, reception_certificate_reference)

	trimmed_reference = str(reception_certificate_reference).strip()

	if not trimmed_reference:
		return None

	if trimmed_reference.isdigit():
		return reception_certificate_repository.get_reception_certificate_by_id(db, int(trimmed_reference))

	return reception_certificate_repository.get_reception_certificate_by_rcid(db, trimmed_reference)


def generate_next_reception_certificate_id(db: Session, customer_id: str) -> str:
	customer_segment = normalize_customer_segment(customer_id)
	max_number = max(
		(
			int(match.group(2))
			for rcid in reception_certificate_repository.get_reception_certificate_ids(db)
			for match in [RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalize_rcid(rcid))]
			if match is not None and int(match.group(1)) == int(customer_segment)
		),
		default=0,
	)
	return f"RCID-{customer_segment}-{max_number + 1:04d}"


def serialize_reception_certificate(reception_certificate: ReceptionCertificate) -> ReceptionCertificateResponse:
	return ReceptionCertificateResponse(
		id=reception_certificate.id,
		rcidDate=normalize_date_for_output(reception_certificate.rcid_date),
		rcid=reception_certificate.rcid,
		rnid=reception_certificate.rnid,
		linkedRnids=list(reception_certificate.linked_rnids or []),
		customerId=reception_certificate.customer_id,
		producingCompanyName=reception_certificate.producing_company_name,
		referringCompany=reception_certificate.referring_company,
		projectName=reception_certificate.project_name,
		projectNumber=reception_certificate.project_number,
		projectLocation=reception_certificate.project_location,
		projectCustomFields=reception_certificate.project_custom_fields,
		verificationComments=reception_certificate.verification_comments,
		wasteStreamQuantity=reception_certificate.waste_stream_quantity,
		wasteStreamName=reception_certificate.waste_stream_name,
		wasteStreamClass=reception_certificate.waste_stream_class,
		rcIssuedBy=reception_certificate.rc_issued_by,
		status=normalize_status(reception_certificate.status),
		isDeleted=bool(reception_certificate.is_deleted),
	)


def get_linked_reception_notes(db: Session, linked_rnids: list[str], principal: AuthPrincipal):
	reception_notes = []

	for rnid in linked_rnids:
		reception_note = reception_note_repository.get_reception_note_by_rnid(db, rnid)

		if reception_note is None:
			raise ValueError(f"Reception note {rnid} could not be found.")

		if normalize_status(reception_note.status) != "Issued":
			raise ValueError(f"Reception note {rnid} must be issued before creating a reception certificate.")

		if not can_access_reception_note(reception_note, principal):
			raise ValueError(f"Reception note {rnid} could not be found.")

		reception_notes.append(reception_note)

	return reception_notes


def get_visible_reception_certificates(db: Session, principal: AuthPrincipal) -> list[ReceptionCertificate]:
	if has_shared_platform_access(principal):
		return reception_certificate_repository.get_reception_certificates(db)

	return reception_certificate_repository.get_reception_certificates_by_customer_id(db, get_customer_scope_id(principal))


def can_access_reception_certificate(reception_certificate: ReceptionCertificate, principal: AuthPrincipal) -> bool:
	return can_access_customer_data(principal, reception_certificate.customer_id)


def can_access_reception_note(reception_note, principal: AuthPrincipal) -> bool:
	return can_access_customer_data(principal, reception_note.customer_id)


def normalize_linked_rnids(linked_rnids: list[str], rnid_summary: str) -> list[str]:
	raw_values = linked_rnids if linked_rnids else rnid_summary.split(",")
	normalized_values: list[str] = []
	seen_values: set[str] = set()

	for value in raw_values:
		trimmed_value = str(value).strip()

		if not trimmed_value:
			continue

		normalized_value = normalize_rnid(trimmed_value)

		if normalized_value in seen_values:
			continue

		seen_values.add(normalized_value)
		normalized_values.append(normalized_value)

	if not normalized_values:
		raise ValueError("At least one issued reception note is required.")

	return normalized_values


def normalize_rnid(rnid: str) -> str:
	normalized_rnid = rnid.strip().upper()

	if not RECEPTION_NOTE_ID_PATTERN.fullmatch(normalized_rnid):
		raise ValueError("A valid reception note ID is required.")

	matched_rnid = RECEPTION_NOTE_ID_PATTERN.fullmatch(normalized_rnid)
	return f"RNID-{int(matched_rnid.group(1)):04d}-{matched_rnid.group(2)}"


def normalize_rcid(rcid: str) -> str:
	normalized_rcid = rcid.strip().upper()

	matched_rcid = RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if matched_rcid is not None:
		return f"RCID-{int(matched_rcid.group(1)):04d}-{matched_rcid.group(2)}"

	legacy_match = LEGACY_RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalized_rcid)

	if legacy_match is None:
		raise ValueError("A valid reception certificate ID is required.")

	return f"RCID-{int(legacy_match.group(1)):04d}-{legacy_match.group(2)}-{legacy_match.group(3)}"


def parse_rnid_parts(rnid: str) -> tuple[str, str]:
	matched_rnid = RECEPTION_NOTE_ID_PATTERN.fullmatch(normalize_rnid(rnid))

	if matched_rnid is None:
		raise ValueError("A valid reception note ID is required.")

	return matched_rnid.group(1), matched_rnid.group(2)


def validate_reception_certificate_id(rcid: str, rnid: str) -> None:
	matched_rcid = RECEPTION_CERTIFICATE_ID_PATTERN.fullmatch(normalize_rcid(rcid))
	rnid_parts = parse_rnid_parts(rnid)

	if matched_rcid is None or int(matched_rcid.group(1)) != int(rnid_parts[0]):
		raise ValueError("Reception certificate ID does not match the selected reception note.")


def get_customer_id_from_rnid(rnid: str) -> str:
	return f"CID-{parse_rnid_parts(rnid)[0]}"


def normalize_customer_segment(customer_id: str) -> str:
	matched_customer_id = re.fullmatch(r"CID-(\d+)", customer_id.strip().upper())

	if matched_customer_id is not None:
		return f"{int(matched_customer_id.group(1)):04d}"

	matched_rnid = RECEPTION_NOTE_ID_PATTERN.fullmatch(customer_id.strip().upper())

	if matched_rnid is not None:
		return f"{int(matched_rnid.group(1)):04d}"

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


def get_primary_waste_stream_name(reception_note) -> str | None:
	streams = reception_note.waste_streams or []
	if not streams:
		return None
	return str(streams[0].get("name", "")).strip() or None


def get_primary_waste_stream_class(reception_note) -> str | None:
	streams = reception_note.waste_streams or []
	if not streams:
		return None
	return str(streams[0].get("wasteClass", "")).strip() or None


PDF_VERIFIED_BY = "Imran Gill"
PDF_VERIFIED_BY_POSITION = "CEO"


def build_reception_certificate_pdf_context(
	reception_certificate: ReceptionCertificate,
	linked_reception_notes: list,
) -> dict[str, object]:
	linked_entries = [build_linked_entry_context(reception_note) for reception_note in linked_reception_notes]
	primary_entry = linked_entries[0] if linked_entries else build_empty_linked_entry_context()
	shared_producing_company = build_shared_producing_company_context(reception_certificate, linked_reception_notes)
	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(reception_certificate.waste_stream_quantity)
	total_quantity = calculate_reception_certificate_total_quantity(linked_reception_notes)
	total_quantity_unit = get_reception_certificate_total_quantity_unit(linked_entries, fallback_quantity_unit)
	total_quantity_display = format_quantity_with_unit(total_quantity or fallback_quantity, total_quantity_unit)

	return {
		"rcid_date": normalize_date_for_output(reception_certificate.rcid_date),
		"rcid": normalize_rcid(reception_certificate.rcid),
		"customer_id": reception_certificate.customer_id,
		"total_quantity": total_quantity_display,
		"linked_rnids": ", ".join(list(reception_certificate.linked_rnids or [])) or reception_certificate.rnid,
		"has_multiple_linked_entries": len(linked_entries) > 1,
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
		"issued_by": reception_certificate.rc_issued_by,
		"verified_by": PDF_VERIFIED_BY,
		"verified_by_position": PDF_VERIFIED_BY_POSITION,
		"status": normalize_status(reception_certificate.status),
	}


def build_shared_producing_company_context(
	reception_certificate: ReceptionCertificate,
	linked_reception_notes: list,
) -> dict[str, str]:
	if not linked_reception_notes:
		return {
			"name": reception_certificate.producing_company_name,
			"emirate": "",
			"office_address": "",
			"contact_person": "",
			"office_phone": "",
			"email": "",
		}

	return {
		"name": join_unique_values([note.producing_company_name for note in linked_reception_notes]) or reception_certificate.producing_company_name,
		"emirate": join_unique_values([note.producing_company_emirate for note in linked_reception_notes]),
		"office_address": join_unique_values([note.producing_company_office_address for note in linked_reception_notes]),
		"contact_person": join_unique_values([note.producing_company_contact_person for note in linked_reception_notes]),
		"office_phone": join_unique_values([note.producing_company_office_phone for note in linked_reception_notes]),
		"email": join_unique_values([note.producing_company_email for note in linked_reception_notes]),
	}


def build_linked_entry_context(reception_note) -> dict[str, object]:
	waste_streams = build_linked_entry_waste_streams(reception_note)
	primary_waste_stream = waste_streams[0] if waste_streams else build_empty_linked_entry_waste_stream()

	return {
		"rnid": normalize_rnid(reception_note.rnid),
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


def build_linked_entry_waste_streams(reception_note) -> list[dict[str, str]]:
	if reception_note.waste_streams:
		return [map_waste_stream_for_pdf(normalize_waste_stream(waste_stream)) for waste_stream in reception_note.waste_streams]

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


def map_waste_stream_for_pdf(waste_stream: dict[str, str]) -> dict[str, str]:
	return {
		"code": waste_stream["code"],
		"name": waste_stream["name"],
		"waste_class": waste_stream["wasteClass"],
		"physical_state": waste_stream["physicalState"],
		"quantity": waste_stream["quantity"],
		"quantity_unit": waste_stream["quantityUnit"],
		"collection_emirate": waste_stream["collectionEmirate"],
		"collection_location": waste_stream["collectionLocation"],
		"reception_date": normalize_date_for_output(waste_stream["receptionDate"]),
	}


def build_empty_linked_entry_context() -> dict[str, object]:
	empty_waste_stream = build_empty_linked_entry_waste_stream()
	return {
		"rnid": "",
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
		"waste_streams": [],
	}


def build_empty_linked_entry_waste_stream() -> dict[str, str]:
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


def get_primary_waste_stream(waste_streams: list[dict[str, str]] | None) -> dict[str, str]:
	if not waste_streams:
		return normalize_waste_stream({})

	return normalize_waste_stream(waste_streams[0])


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


def calculate_reception_certificate_total_quantity(linked_reception_notes: list) -> str:
	return sum_quantity_values([calculate_reception_note_total_quantity(note) for note in linked_reception_notes])


def calculate_reception_note_total_quantity(reception_note) -> str:
	if reception_note.waste_streams:
		return sum_quantity_values(
			[
				normalize_waste_stream(waste_stream)["quantity"]
				for waste_stream in reception_note.waste_streams
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


def get_reception_certificate_total_quantity_unit(linked_entries: list[dict[str, object]], fallback_quantity_unit: str) -> str:
	if fallback_quantity_unit.strip():
		return fallback_quantity_unit.strip()

	units: list[str] = []
	for entry in linked_entries:
		for waste_stream in entry.get("waste_streams", []):
			if not isinstance(waste_stream, dict):
				continue

			quantity_unit = str(waste_stream.get("quantity_unit", "")).strip()
			if quantity_unit and quantity_unit not in units:
				units.append(quantity_unit)

	return join_unique_values(units)


def format_quantity_with_unit(quantity: str, quantity_unit: str) -> str:
	trimmed_quantity = str(quantity).strip()
	trimmed_unit = str(quantity_unit).strip()

	if not trimmed_quantity:
		return "N/A"

	if not trimmed_unit:
		return trimmed_quantity

	return f"{trimmed_quantity} {trimmed_unit}"


def sum_quantity_values(quantity_values: list[str]) -> str:
	total = Decimal("0")
	has_quantity = False

	for quantity_value in quantity_values:
		parsed_quantity = parse_decimal_quantity(quantity_value)

		if parsed_quantity is not None:
			has_quantity = True
			total += parsed_quantity

	if not has_quantity:
		return ""

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
