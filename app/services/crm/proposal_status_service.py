from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crm.proposal_status import ProposalStatus
from app.repositories.crm import proposal_status_repository
from app.schemas.crm.proposal_status_schema import ProposalStatusCreateUpdate, ProposalStatusResponse
from app.services.crm import lead_service


def get_proposal_status(db: Session, lid: str) -> ProposalStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	status_record = proposal_status_repository.get_by_lead_id(db, lead.id)

	if status_record is None:
		return ProposalStatusResponse(
			id=0,
			lead_id=lead.id,
			lid=lead.lid,
			pid="",
			status="",
			status_other=None,
			comments=None,
			updated_by="",
			updated_at=lead.updated_at,
		)

	return ProposalStatusResponse.model_validate(status_record)


def update_proposal_status(db: Session, lid: str, payload: ProposalStatusCreateUpdate) -> ProposalStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	status_value = normalize_required_string(payload.status, "Status")
	status_other = normalize_optional_string(payload.status_other)

	if status_value == "Other" and not status_other:
		raise ValueError("Other Status is required when Status is Other.")

	status_record = proposal_status_repository.get_by_lead_id(db, lead.id)
	if status_record is None:
		status_record = ProposalStatus(
			lead_id=lead.id,
			lid=lead.lid,
			pid=normalize_required_string(payload.pid, "PID"),
			status=status_value,
			status_other=status_other,
			comments=normalize_optional_string(payload.comments),
			updated_by=normalize_required_string(payload.updated_by, "Updated By"),
			status_date=datetime.now(timezone.utc),
		)
		status_record = proposal_status_repository.create(db, status_record)
	else:
		status_record.lid = lead.lid
		status_record.pid = normalize_required_string(payload.pid, "PID")
		status_record.status = status_value
		status_record.status_other = status_other
		status_record.comments = normalize_optional_string(payload.comments)
		status_record.updated_by = normalize_required_string(payload.updated_by, "Updated By")
		if status_record.status_date is None:
			status_record.status_date = datetime.now(timezone.utc)
		status_record = proposal_status_repository.update(db, status_record)

	return ProposalStatusResponse.model_validate(status_record)


def normalize_required_string(value: str | None, field_label: str) -> str:
	normalized_value = str(value or "").strip()
	if not normalized_value:
		raise ValueError(f"{field_label} is required.")
	return normalized_value


def normalize_optional_string(value: str | None) -> str | None:
	normalized_value = str(value or "").strip()
	return normalized_value or None
