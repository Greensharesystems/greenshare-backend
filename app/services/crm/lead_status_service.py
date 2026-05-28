from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crm.lead_status import LeadStatus
from app.repositories.crm import lead_status_repository
from app.schemas.crm.lead_status_schema import LeadStatusCreateUpdate, LeadStatusResponse
from app.services.crm import lead_service


def get_lead_status(db: Session, lid: str) -> LeadStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	status_record = lead_status_repository.get_by_lead_id(db, lead.id)

	if status_record is None:
		return LeadStatusResponse(
			id=0,
			lead_id=lead.id,
			lid=lead.lid,
			status="Open",
			status_other=None,
			comments=None,
			updated_by="",
			updated_at=lead.updated_at,
		)

	return LeadStatusResponse.model_validate(status_record)


def update_lead_status(db: Session, lid: str, payload: LeadStatusCreateUpdate) -> LeadStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	status_value = normalize_required_string(payload.status, "Status")
	status_other = normalize_optional_string(payload.status_other)

	if status_value == "Other" and not status_other:
		raise ValueError("Other Status is required when Status is Other.")

	status_record = lead_status_repository.get_by_lead_id(db, lead.id)
	if status_record is None:
		status_record = LeadStatus(
			lead_id=lead.id,
			lid=lead.lid,
			status=status_value,
			status_other=status_other,
			comments=normalize_optional_string(payload.comments),
			updated_by=normalize_required_string(payload.updated_by, "Updated By"),
			closed_date=resolve_closed_date(status_value),
		)
		status_record = lead_status_repository.create(db, status_record)
	else:
		status_record.lid = lead.lid
		status_record.status = status_value
		status_record.status_other = status_other
		status_record.comments = normalize_optional_string(payload.comments)
		status_record.updated_by = normalize_required_string(payload.updated_by, "Updated By")
		status_record.closed_date = resolve_closed_date(status_value)
		status_record = lead_status_repository.update(db, status_record)

	return LeadStatusResponse.model_validate(status_record)


def normalize_required_string(value: str | None, field_label: str) -> str:
	normalized_value = str(value or "").strip()
	if not normalized_value:
		raise ValueError(f"{field_label} is required.")
	return normalized_value


def normalize_optional_string(value: str | None) -> str | None:
	normalized_value = str(value or "").strip()
	return normalized_value or None


def resolve_closed_date(status_value: str, existing_closed_date: datetime | None = None) -> datetime | None:
	if status_value == "Open":
		return None

	return existing_closed_date or datetime.now(timezone.utc)
