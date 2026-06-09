import re

from sqlalchemy.orm import Session

from app.models.crm.stream_code import StreamCode
from app.repositories.crm import stream_code_repository
from app.schemas.crm.stream_code_schema import StreamCodeCreate, StreamCodeResponse, StreamCodeUpdate


CATEGORY_PREFIXES = {
	"Hazardous Stream": "HS",
	"Non-Hazardous Stream": "NHS",
	"Recyclable Stream": "RS",
}

VALID_STATUSES = {"Active", "Inactive"}


def list_stream_codes(db: Session) -> list[StreamCodeResponse]:
	return [to_response(record) for record in stream_code_repository.list_stream_codes(db)]


def get_next_stream_code(db: Session, category: str) -> str:
	normalized_category = normalize_category(category)
	prefix = CATEGORY_PREFIXES[normalized_category]
	pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
	max_number = 0

	for stream_code in stream_code_repository.get_stream_codes_for_category(db, normalized_category):
		match = pattern.match(stream_code)
		if match:
			max_number = max(max_number, int(match.group(1)))

	return f"{prefix}-{max_number + 1}"


def get_stream_code(db: Session, identifier: str) -> StreamCodeResponse:
	return to_response(get_existing_stream_code(db, identifier))


def create_stream_code(db: Session, payload: StreamCodeCreate) -> StreamCodeResponse:
	normalized_code = normalize_stream_code(payload.stream_code)
	normalized_category = normalize_category(payload.category)
	normalized_status = normalize_status(payload.status)

	if stream_code_repository.stream_code_exists(db, normalized_code):
		raise ValueError("That Stream Code already exists.")

	stream_code = StreamCode(
		scid=payload.scid,
		stream_code=normalized_code,
		category=normalized_category,
		stream_name=normalize_required(payload.stream_name, "Stream Name"),
		description=payload.description,
		status=normalized_status,
	)
	return to_response(stream_code_repository.create_stream_code(db, stream_code))


def update_stream_code(db: Session, identifier: str, payload: StreamCodeUpdate) -> StreamCodeResponse:
	stream_code = get_existing_stream_code(db, identifier)

	if payload.stream_code is not None:
		normalized_code = normalize_stream_code(payload.stream_code)
		if stream_code_repository.stream_code_exists(db, normalized_code, exclude_id=stream_code.id):
			raise ValueError("That Stream Code already exists.")
		stream_code.stream_code = normalized_code

	if payload.category is not None:
		stream_code.category = normalize_category(payload.category)
	if payload.stream_name is not None:
		stream_code.stream_name = normalize_required(payload.stream_name, "Stream Name")
	if "description" in payload.model_fields_set:
		stream_code.description = payload.description
	if payload.status is not None:
		stream_code.status = normalize_status(payload.status)
	if "scid" in payload.model_fields_set:
		stream_code.scid = payload.scid

	return to_response(stream_code_repository.update_stream_code(db, stream_code))


def delete_stream_code(db: Session, identifier: str) -> None:
	stream_code_repository.soft_delete_stream_code(db, get_existing_stream_code(db, identifier))


def get_existing_stream_code(db: Session, identifier: str) -> StreamCode:
	stream_code = stream_code_repository.get_stream_code_by_identifier(db, identifier.strip())
	if stream_code is None:
		raise ValueError("Stream Code could not be found.")
	return stream_code


def normalize_stream_code(value: str) -> str:
	normalized = value.strip().upper()
	if not normalized:
		raise ValueError("Stream Code is required.")
	return normalized


def normalize_category(value: str) -> str:
	normalized = value.strip()
	if normalized not in CATEGORY_PREFIXES:
		raise ValueError("Unsupported Stream Code category.")
	return normalized


def normalize_status(value: str) -> str:
	normalized = value.strip()
	if normalized not in VALID_STATUSES:
		raise ValueError("Unsupported Stream Code status.")
	return normalized


def normalize_required(value: str, label: str) -> str:
	normalized = value.strip()
	if not normalized:
		raise ValueError(f"{label} is required.")
	return normalized


def to_response(stream_code: StreamCode) -> StreamCodeResponse:
	return StreamCodeResponse.model_validate(stream_code)
