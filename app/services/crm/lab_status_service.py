from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crm.lab_status import LabStatus
from app.repositories.crm import lab_status_repository
from app.schemas.crm.lab_status_schema import LabStatusCreateUpdate, LabStatusResponse
from app.services.crm import lead_service


def get_lab_status(db: Session, lid: str) -> LabStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	status_record = lab_status_repository.get_by_lead_id(db, lead.id)

	if status_record is None:
		return LabStatusResponse(
			id=0,
			lead_id=lead.id,
			lid=lead.lid,
			lab_id="",
			decision="",
			decision_other=None,
			comments=None,
			chemist_name="",
			updated_at=lead.updated_at,
		)

	return LabStatusResponse.model_validate(status_record)


def update_lab_status(db: Session, lid: str, payload: LabStatusCreateUpdate) -> LabStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	decision = normalize_required_string(payload.decision, "Decision")
	decision_other = normalize_optional_string(payload.decision_other)

	if decision == "Other" and not decision_other:
		raise ValueError("Other Decision is required when Decision is Other.")

	status_record = lab_status_repository.get_by_lead_id(db, lead.id)
	if status_record is None:
		status_record = LabStatus(
			lead_id=lead.id,
			lid=lead.lid,
			lab_id=normalize_required_string(payload.lab_id, "LAB ID"),
			decision=decision,
			decision_other=decision_other,
			comments=normalize_optional_string(payload.comments),
			chemist_name=normalize_required_string(payload.chemist_name, "Chemist Name"),
			decision_date=datetime.now(timezone.utc),
		)
		status_record = lab_status_repository.create(db, status_record)
	else:
		status_record.lid = lead.lid
		status_record.lab_id = normalize_required_string(payload.lab_id, "LAB ID")
		status_record.decision = decision
		status_record.decision_other = decision_other
		status_record.comments = normalize_optional_string(payload.comments)
		status_record.chemist_name = normalize_required_string(payload.chemist_name, "Chemist Name")
		if status_record.decision_date is None:
			status_record.decision_date = datetime.now(timezone.utc)
		status_record = lab_status_repository.update(db, status_record)

	return LabStatusResponse.model_validate(status_record)


def normalize_required_string(value: str | None, field_label: str) -> str:
	normalized_value = str(value or "").strip()
	if not normalized_value:
		raise ValueError(f"{field_label} is required.")
	return normalized_value


def normalize_optional_string(value: str | None) -> str | None:
	normalized_value = str(value or "").strip()
	return normalized_value or None
