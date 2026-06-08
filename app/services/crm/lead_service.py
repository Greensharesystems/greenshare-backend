import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.date_utils import format_display_date, normalize_date_for_output, normalize_date_for_storage, parse_supported_date
from app.models.crm.lead import Lead
from app.models.crm.lead_stream import LeadStream
from app.repositories.crm import lead_repository
from app.schemas.crm.lead_schema import LeadCreate, LeadListResponse, LeadResponse, LeadUpdate, NextLeadIdResponse
from app.schemas.crm.lead_stream_schema import LeadStreamResponse


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
	if lead_repository.lid_exists(db, lid):
		raise ValueError("That Lead ID already exists.")

	# Determine effective lead-level waste stream fields from streams or legacy fields
	if payload.streams:
		first = payload.streams[0]
		effective_waste_stream = normalize_required_string(first.waste_stream_name, "Waste Stream Name")
		effective_waste_class = normalize_required_string(first.waste_class, "Waste Class")
		effective_waste_class_other = normalize_optional_string(first.waste_class_other)
		effective_est_qty = normalize_quantity(first.est_qty)
		effective_unit = normalize_required_string(first.unit, "Unit")
		effective_unit_other = normalize_optional_string(first.unit_other)
	elif payload.waste_stream and payload.waste_class and payload.est_qty is not None and payload.unit:
		effective_waste_stream = normalize_required_string(payload.waste_stream, "Waste Stream")
		effective_waste_class = normalize_required_string(payload.waste_class, "Waste Class")
		effective_waste_class_other = normalize_optional_string(payload.waste_class_other)
		effective_est_qty = normalize_quantity(payload.est_qty)
		effective_unit = normalize_required_string(payload.unit, "Unit")
		effective_unit_other = normalize_optional_string(payload.unit_other)
	else:
		raise ValueError("Either streams or waste stream details are required.")

	lead = Lead(
		lid=lid,
		cid=normalize_required_string(payload.cid, "CID"),
		customer_name=normalize_required_string(payload.customer_name, "Customer Name"),
		source=normalize_required_string(payload.source, "Source"),
		source_detail=normalize_optional_string(payload.source_detail),
		assigned_to=normalize_required_string(payload.assigned_to, "Assigned To"),
		assigned_to_other=normalize_optional_string(payload.assigned_to_other),
		waste_stream=effective_waste_stream,
		waste_class=effective_waste_class,
		waste_class_other=effective_waste_class_other,
		est_qty=effective_est_qty,
		unit=effective_unit,
		unit_other=effective_unit_other,
		comments=normalize_optional_string(payload.comments),
		lead_date=normalize_date_for_storage(payload.lead_date, "Lead Date"),
	)

	created_lead = lead_repository.create_lead(db, lead)

	# Create stream records
	if payload.streams:
		for i, stream_data in enumerate(payload.streams):
			stream_no = f"SN-{i + 1:03d}"
			stream = LeadStream(
				lead_id=created_lead.id,
				lid=created_lead.lid,
				stream_no=stream_no,
				waste_stream_name=normalize_required_string(stream_data.waste_stream_name, "Waste Stream Name"),
				est_qty=normalize_quantity(stream_data.est_qty),
				unit=normalize_required_string(stream_data.unit, "Unit"),
				unit_other=normalize_optional_string(stream_data.unit_other),
				waste_class=normalize_required_string(stream_data.waste_class, "Waste Class"),
				waste_class_other=normalize_optional_string(stream_data.waste_class_other),
			)
			db.add(stream)
	else:
		# Create SN-001 from legacy lead fields
		stream = LeadStream(
			lead_id=created_lead.id,
			lid=created_lead.lid,
			stream_no="SN-001",
			waste_stream_name=effective_waste_stream,
			est_qty=effective_est_qty,
			unit=effective_unit,
			unit_other=effective_unit_other,
			waste_class=effective_waste_class,
			waste_class_other=effective_waste_class_other,
		)
		db.add(stream)

	db.commit()
	db.refresh(created_lead)
	return serialize_lead(created_lead)


def delete_lead(db: Session, lid: str) -> None:
	lead = get_lead_model_by_lid(db, lid)
	lead_repository.soft_delete_lead(db, lead)


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


def _serialize_streams(lead: Lead) -> list[LeadStreamResponse]:
	result: list[LeadStreamResponse] = []
	for stream in (lead.streams or []):
		lab = stream.lab_status
		lab_decision = lab.decision if lab is not None and lab.decision else "Pending"
		lab_days = calculate_elapsed_days(
			lead.lead_date,
			lab.decision_date.date() if lab is not None and lab.decision_date is not None else None,
		)
		result.append(
			LeadStreamResponse(
				id=stream.id,
				lid=stream.lid,
				stream_no=stream.stream_no,
				waste_stream_name=stream.waste_stream_name,
				est_qty=stream.est_qty,
				unit=stream.unit,
				unit_other=stream.unit_other,
				waste_class=stream.waste_class,
				waste_class_other=stream.waste_class_other,
				lab_decision=lab_decision,
				lab_decision_other=lab.decision_other if lab is not None else None,
				lab_comments=lab.comments if lab is not None else None,
				lab_chemist_name=lab.chemist_name if lab is not None else "",
				lab_status_days=lab_days,
			)
		)
	return result


def serialize_lead(lead: Lead) -> LeadResponse:
	lab_status_value = summarize_lab_status(lead.lab_status.decision if lead.lab_status is not None else None)
	proposal_status_value = summarize_proposal_status(lead.proposal_status.status if lead.proposal_status is not None else None)
	lead_status_value = summarize_lead_status(lead.lead_status.status if lead.lead_status is not None else None)
	default_date = normalize_date_for_output(lead.lead_date)
	lab_status_days = calculate_elapsed_days(lead.lead_date, resolve_lab_status_end_date(lead))
	proposal_status_days = calculate_elapsed_days(lead.lead_date, resolve_proposal_status_end_date(lead))
	lead_status_days = calculate_elapsed_days(lead.lead_date, resolve_lead_status_end_date(lead))

	wds = lead.wds_status
	wds_date_submitted = wds.date_submitted if wds is not None else None
	wds_date_approved = wds.date_approved if wds is not None else None
	wds_no = wds.wds_no if wds is not None else None
	wds_status_value = _derive_wds_status(wds_date_submitted, wds_date_approved)
	wds_days = _calculate_wds_days(wds_date_submitted, wds_date_approved)

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
		streams=_serialize_streams(lead),
		lab_id=lead.lab_status.lab_id if lead.lab_status is not None else None,
		lab_status=lab_status_value,
		lab_status_days=lab_status_days,
		lab_updated_at=format_timestamp_for_output(lead.lab_status.updated_at if lead.lab_status is not None else None, default_date),
		proposal_id=lead.proposal_status.pid if lead.proposal_status is not None else None,
		proposal_status=proposal_status_value,
		proposal_status_days=proposal_status_days,
		proposal_updated_at=format_timestamp_for_output(lead.proposal_status.updated_at if lead.proposal_status is not None else None, default_date),
		lead_status=lead_status_value,
		lead_status_days=lead_status_days,
		lead_status_updated_at=format_timestamp_for_output(lead.lead_status.updated_at if lead.lead_status is not None else None, default_date),
		wds_date_submitted=wds_date_submitted,
		wds_status=wds_status_value,
		wds_date_approved=wds_date_approved,
		wds_status_days=wds_days,
		wds_no=wds_no,
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
	return normalize_optional_string(decision) or "Pending"


def summarize_proposal_status(status: str | None) -> str:
	return normalize_optional_string(status) or "Pending"


def summarize_lead_status(status: str | None) -> str:
	return normalize_optional_string(status) or "Open"


def calculate_elapsed_days(start_date_value: str, end_date_value: date | None) -> int:
	start_date = parse_supported_date(start_date_value)
	if start_date is None:
		return 0

	resolved_end_date = end_date_value or get_current_date()
	return max(0, (resolved_end_date - start_date).days)


def resolve_lab_status_end_date(lead: Lead) -> date:
	if lead.lab_status is not None and lead.lab_status.decision_date is not None:
		return lead.lab_status.decision_date.date()

	return get_current_date()


def resolve_proposal_status_end_date(lead: Lead) -> date:
	if lead.proposal_status is not None and lead.proposal_status.status_date is not None:
		return lead.proposal_status.status_date.date()

	return get_current_date()


def resolve_lead_status_end_date(lead: Lead) -> date:
	status_value = normalize_optional_string(lead.lead_status.status if lead.lead_status is not None else None)
	if not status_value or status_value == "Open":
		return get_current_date()

	if lead.lead_status is not None and lead.lead_status.closed_date is not None:
		return lead.lead_status.closed_date.date()

	return get_current_date()


def get_current_date() -> date:
	return datetime.utcnow().date()


def _derive_wds_status(date_submitted: str | None, date_approved: str | None) -> str:
	if not date_submitted:
		return "N/A"
	if date_approved:
		return "Approved"
	return "Open"


def _calculate_wds_days(date_submitted: str | None, date_approved: str | None) -> int | None:
	if not date_submitted:
		return None
	start = parse_supported_date(date_submitted)
	if start is None:
		return None
	if date_approved:
		end = parse_supported_date(date_approved)
		return max(0, (end - start).days) if end is not None else None
	return max(0, (get_current_date() - start).days)
