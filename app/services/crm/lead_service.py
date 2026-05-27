import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.date_utils import format_display_date, normalize_date_for_output, normalize_date_for_storage
from app.models.crm.lead import Lead
from app.repositories.crm import lead_repository
from app.schemas.crm.lead_schema import LeadCreate, LeadListResponse, LeadResponse, LeadUpdate, NextLeadIdResponse


LEAD_ID_PATTERN = re.compile(r"LID-(\d+)")


def list_leads(db: Session) -> list[LeadListResponse]:
	return [serialize_lead(lead) for lead in lead_repository.get_leads(db)]


def get_next_lead_id(db: Session) -> NextLeadIdResponse:
	return NextLeadIdResponse(next_lid=generate_next_lead_id(db))


def get_lead_by_lid(db: Session, lid: str) -> LeadResponse:
	lead = lead_repository.get_lead_by_lid(db, normalize_lid(lid))

	if lead is None:
		raise ValueError("That lead could not be found.")

	return serialize_lead(lead)


def get_lead_model_by_lid(db: Session, lid: str) -> Lead:
	lead = lead_repository.get_lead_by_lid(db, normalize_lid(lid))

	if lead is None:
		raise ValueError("That lead could not be found.")

	return lead


def create_lead(db: Session, payload: LeadCreate) -> LeadResponse:
	lid = normalize_lid(payload.lid)
	if lead_repository.get_lead_by_lid(db, lid) is not None:
		raise ValueError("That Lead ID already exists.")

	lead = Lead(
		lid=lid,
		cid=normalize_required_string(payload.cid, "CID"),
		customer_name=normalize_required_string(payload.customer_name, "Customer Name"),
		source=normalize_required_string(payload.source, "Source"),
		source_detail=normalize_optional_string(payload.source_detail),
		assigned_to=normalize_required_string(payload.assigned_to, "Assigned To"),
		assigned_to_other=normalize_optional_string(payload.assigned_to_other),
		waste_stream=normalize_required_string(payload.waste_stream, "Waste Stream"),
		waste_class=normalize_required_string(payload.waste_class, "Waste Class"),
		waste_class_other=normalize_optional_string(payload.waste_class_other),
		est_qty=normalize_quantity(payload.est_qty),
		unit=normalize_required_string(payload.unit, "Unit"),
		unit_other=normalize_optional_string(payload.unit_other),
		comments=normalize_optional_string(payload.comments),
		lead_date=normalize_date_for_storage(payload.lead_date, "Lead Date"),
	)

	created_lead = lead_repository.create_lead(db, lead)
	return serialize_lead(created_lead)


def update_lead(db: Session, lid: str, payload: LeadUpdate) -> LeadResponse:
	lead = get_lead_model_by_lid(db, lid)

	if payload.cid is not None:
		lead.cid = normalize_required_string(payload.cid, "CID")
	if payload.customer_name is not None:
		lead.customer_name = normalize_required_string(payload.customer_name, "Customer Name")
	if payload.source is not None:
		lead.source = normalize_required_string(payload.source, "Source")
	if payload.source_detail is not None:
		lead.source_detail = normalize_optional_string(payload.source_detail)
	if payload.assigned_to is not None:
		lead.assigned_to = normalize_required_string(payload.assigned_to, "Assigned To")
	if payload.assigned_to_other is not None:
		lead.assigned_to_other = normalize_optional_string(payload.assigned_to_other)
	if payload.waste_stream is not None:
		lead.waste_stream = normalize_required_string(payload.waste_stream, "Waste Stream")
	if payload.waste_class is not None:
		lead.waste_class = normalize_required_string(payload.waste_class, "Waste Class")
	if payload.waste_class_other is not None:
		lead.waste_class_other = normalize_optional_string(payload.waste_class_other)
	if payload.est_qty is not None:
		lead.est_qty = normalize_quantity(payload.est_qty)
	if payload.unit is not None:
		lead.unit = normalize_required_string(payload.unit, "Unit")
	if payload.unit_other is not None:
		lead.unit_other = normalize_optional_string(payload.unit_other)
	if payload.comments is not None:
		lead.comments = normalize_optional_string(payload.comments)
	if payload.lead_date is not None:
		lead.lead_date = normalize_date_for_storage(payload.lead_date, "Lead Date")

	updated_lead = lead_repository.update_lead(db, lead)
	return serialize_lead(updated_lead)


def generate_next_lead_id(db: Session) -> str:
	max_number = max(
		(
			int(match.group(1))
			for lead_id in lead_repository.get_lead_lids(db)
			for match in [LEAD_ID_PATTERN.fullmatch(lead_id.strip().upper())]
			if match is not None
		),
		default=0,
	)
	return f"LID-{max_number + 1:04d}"


def serialize_lead(lead: Lead) -> LeadResponse:
	lab_status_value = summarize_lab_status(lead.lab_status.decision if lead.lab_status is not None else None)
	proposal_status_value = summarize_proposal_status(lead.proposal_status.status if lead.proposal_status is not None else None)
	lead_status_value = summarize_lead_status(lead.lead_status.status if lead.lead_status is not None else None)
	default_date = normalize_date_for_output(lead.lead_date)

	return LeadResponse(
		id=lead.id,
		lid=lead.lid,
		cid=lead.cid,
		customer_name=lead.customer_name,
		source=lead.source,
		source_detail=lead.source_detail,
		assigned_to=lead.assigned_to,
		assigned_to_other=lead.assigned_to_other,
		waste_stream=lead.waste_stream,
		waste_class=lead.waste_class,
		waste_class_other=lead.waste_class_other,
		est_qty=lead.est_qty,
		unit=lead.unit,
		unit_other=lead.unit_other,
		comments=lead.comments,
		lead_date=default_date,
		created_at=lead.created_at,
		updated_at=lead.updated_at,
		lab_id=lead.lab_status.lab_id if lead.lab_status is not None else None,
		lab_status=lab_status_value,
		lab_updated_at=format_timestamp_for_output(lead.lab_status.updated_at if lead.lab_status is not None else None, default_date),
		proposal_id=lead.proposal_status.pid if lead.proposal_status is not None else None,
		proposal_status=proposal_status_value,
		proposal_updated_at=format_timestamp_for_output(lead.proposal_status.updated_at if lead.proposal_status is not None else None, default_date),
		lead_status=lead_status_value,
		lead_status_updated_at=format_timestamp_for_output(lead.lead_status.updated_at if lead.lead_status is not None else None, default_date),
	)


def normalize_lid(lid: str) -> str:
	normalized_value = str(lid or "").strip().upper()
	if not normalized_value:
		raise ValueError("Lead ID is required.")
	return normalized_value


def normalize_required_string(value: str | None, field_label: str) -> str:
	normalized_value = str(value or "").strip()
	if not normalized_value:
		raise ValueError(f"{field_label} is required.")
	return normalized_value


def normalize_optional_string(value: str | None) -> str | None:
	normalized_value = str(value or "").strip()
	return normalized_value or None


def normalize_quantity(value: float | int) -> float:
	try:
		normalized_value = float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError("Estimated Quantity must be a valid number.") from exc

	if normalized_value < 0:
		raise ValueError("Estimated Quantity must be zero or greater.")

	return normalized_value


def format_timestamp_for_output(timestamp: datetime | None, fallback_date: str) -> str:
	if timestamp is None:
		return fallback_date
	return format_display_date(timestamp.date())


def summarize_lab_status(decision: str | None) -> str:
	if decision == "Accept":
		return "Approved"
	if decision == "Reject":
		return "Rejected"
	return "Pending"


def summarize_proposal_status(status: str | None) -> str:
	if status in {"Sent", "Under Review", "Not Sent"}:
		return status
	return "Draft"


def summarize_lead_status(status: str | None) -> str:
	if status in {"Open", "Won", "Lost"}:
		return status
	return "Open"
