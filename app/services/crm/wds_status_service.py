from sqlalchemy.orm import Session

from app.models.crm.wds_status import WdsStatus
from app.repositories.crm import wds_status_repository
from app.schemas.crm.wds_status_schema import WdsStatusCreateUpdate, WdsStatusResponse
from app.services.crm import lead_service
from app.services.crm.lead_service import (
	calculate_elapsed_days,
	get_current_date,
	normalize_optional_string,
)
from app.core.date_utils import parse_supported_date, normalize_date_for_storage, normalize_date_for_output


def calculate_wds_days(date_submitted: str | None, date_approved: str | None) -> int | None:
	if not date_submitted:
		return None

	start_date = parse_supported_date(date_submitted)
	if start_date is None:
		return None

	if date_approved:
		end_date = parse_supported_date(date_approved)
		if end_date is None:
			return None
		return max(0, (end_date - start_date).days)

	return max(0, (get_current_date() - start_date).days)


def derive_wds_status(date_submitted: str | None, date_approved: str | None) -> str:
	if not date_submitted:
		return "N/A"
	if date_approved:
		return "Approved"
	return "Open"


def get_wds_status(db: Session, lid: str) -> WdsStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	record = wds_status_repository.get_by_lead_id(db, lead.id)

	if record is None:
		return WdsStatusResponse(
			id=0,
			lead_id=lead.id,
			lid=lead.lid,
			wds_no=None,
			date_submitted=None,
			date_approved=None,
			status="N/A",
			days=None,
			comments=None,
			updated_by=None,
			updated_at=lead.updated_at,
		)

	status = derive_wds_status(record.date_submitted, record.date_approved)
	days = calculate_wds_days(record.date_submitted, record.date_approved)

	return WdsStatusResponse(
		id=record.id,
		lead_id=record.lead_id,
		lid=record.lid,
		wds_no=record.wds_no,
		date_submitted=record.date_submitted,
		date_approved=record.date_approved,
		status=status,
		days=days,
		comments=record.comments,
		updated_by=record.updated_by,
		updated_at=record.updated_at,
	)


def update_wds_status(db: Session, lid: str, payload: WdsStatusCreateUpdate) -> WdsStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)

	date_submitted: str | None = None
	date_approved: str | None = None

	if payload.date_submitted:
		normalized = normalize_date_for_storage(payload.date_submitted, "Date Submitted")
		date_submitted = normalize_date_for_output(normalized)

	if payload.date_approved:
		normalized = normalize_date_for_storage(payload.date_approved, "Date Approved")
		date_approved = normalize_date_for_output(normalized)

	record = wds_status_repository.get_by_lead_id(db, lead.id)

	if record is None:
		record = WdsStatus(
			lead_id=lead.id,
			lid=lead.lid,
			wds_no=normalize_optional_string(payload.wds_no),
			date_submitted=date_submitted,
			date_approved=date_approved,
			comments=normalize_optional_string(payload.comments),
			updated_by=normalize_optional_string(payload.updated_by),
		)
		record = wds_status_repository.create(db, record)
	else:
		record.lid = lead.lid
		record.wds_no = normalize_optional_string(payload.wds_no)
		record.date_submitted = date_submitted
		record.date_approved = date_approved
		record.comments = normalize_optional_string(payload.comments)
		record.updated_by = normalize_optional_string(payload.updated_by)
		record = wds_status_repository.update(db, record)

	status = derive_wds_status(record.date_submitted, record.date_approved)
	days = calculate_wds_days(record.date_submitted, record.date_approved)

	return WdsStatusResponse(
		id=record.id,
		lead_id=record.lead_id,
		lid=record.lid,
		wds_no=record.wds_no,
		date_submitted=record.date_submitted,
		date_approved=record.date_approved,
		status=status,
		days=days,
		comments=record.comments,
		updated_by=record.updated_by,
		updated_at=record.updated_at,
	)
