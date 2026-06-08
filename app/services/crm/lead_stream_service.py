import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crm.lab_stream_status import LabStreamStatus
from app.models.crm.lead_stream import LeadStream
from app.repositories.crm import lab_stream_status_repository, lead_stream_repository
from app.schemas.crm.lead_stream_schema import (
	LabStreamStatusCreateUpdate,
	LabStreamStatusResponse,
	LeadStreamCreate,
	LeadStreamResponse,
)
from app.services.crm import lead_service


SN_PATTERN = re.compile(r"SN-(\d+)")


def list_streams(db: Session, lid: str) -> list[LeadStreamResponse]:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	streams = lead_stream_repository.get_streams_by_lead_id(db, lead.id)
	return [_serialize_stream(s, lead.lead_date) for s in streams]


def add_stream(db: Session, lid: str, payload: LeadStreamCreate) -> LeadStreamResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	existing = lead_stream_repository.get_streams_by_lead_id(db, lead.id)
	stream_no = _next_stream_no([s.stream_no for s in existing])

	stream = LeadStream(
		lead_id=lead.id,
		lid=lead.lid,
		stream_no=stream_no,
		waste_stream_name=lead_service.normalize_required_string(payload.waste_stream_name, "Waste Stream Name"),
		est_qty=lead_service.normalize_quantity(payload.est_qty),
		unit=lead_service.normalize_required_string(payload.unit, "Unit"),
		unit_other=lead_service.normalize_optional_string(payload.unit_other),
		waste_class=lead_service.normalize_required_string(payload.waste_class, "Waste Class"),
		waste_class_other=lead_service.normalize_optional_string(payload.waste_class_other),
	)
	created = lead_stream_repository.create_stream(db, stream)
	return _serialize_stream(created, lead.lead_date)


def remove_stream(db: Session, lid: str, stream_no: str) -> None:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	stream = lead_stream_repository.get_stream(db, lead.id, stream_no.upper())

	if stream is None:
		raise ValueError(f"Stream {stream_no} not found for {lid}.")

	existing = lead_stream_repository.get_streams_by_lead_id(db, lead.id)
	if len(existing) <= 1:
		raise ValueError("A lead must have at least one stream.")

	lead_stream_repository.delete_stream(db, stream)


def get_lab_stream_status(db: Session, lid: str, stream_no: str) -> LabStreamStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	stream = lead_stream_repository.get_stream(db, lead.id, stream_no.upper())

	if stream is None:
		raise ValueError(f"Stream {stream_no} not found for {lid}.")

	if stream.lab_status is None:
		return LabStreamStatusResponse(
			id=0,
			lid=lead.lid,
			stream_no=stream.stream_no,
			decision="",
			decision_other=None,
			comments=None,
			chemist_name="",
		)

	lab = stream.lab_status
	return LabStreamStatusResponse(
		id=lab.id,
		lid=lab.lid,
		stream_no=lab.stream_no,
		decision=lab.decision,
		decision_other=lab.decision_other,
		comments=lab.comments,
		chemist_name=lab.chemist_name,
	)


def update_lab_stream_status(db: Session, lid: str, stream_no: str, payload: LabStreamStatusCreateUpdate) -> LabStreamStatusResponse:
	lead = lead_service.get_lead_model_by_lid(db, lid)
	stream = lead_stream_repository.get_stream(db, lead.id, stream_no.upper())

	if stream is None:
		raise ValueError(f"Stream {stream_no} not found for {lid}.")

	decision = lead_service.normalize_required_string(payload.decision, "Decision")
	decision_other = lead_service.normalize_optional_string(payload.decision_other)

	if decision == "Other" and not decision_other:
		raise ValueError("Other Decision is required when Decision is Other.")

	record = lab_stream_status_repository.get_by_stream_id(db, stream.id)
	if record is None:
		record = LabStreamStatus(
			lead_stream_id=stream.id,
			lead_id=lead.id,
			lid=lead.lid,
			stream_no=stream.stream_no,
			decision=decision,
			decision_other=decision_other,
			comments=lead_service.normalize_optional_string(payload.comments),
			chemist_name=lead_service.normalize_required_string(payload.chemist_name, "Chemist Name"),
			decision_date=datetime.now(timezone.utc),
		)
		record = lab_stream_status_repository.create(db, record)
	else:
		record.decision = decision
		record.decision_other = decision_other
		record.comments = lead_service.normalize_optional_string(payload.comments)
		record.chemist_name = lead_service.normalize_required_string(payload.chemist_name, "Chemist Name")
		record.decision_date = datetime.now(timezone.utc)
		record = lab_stream_status_repository.update(db, record)

	return LabStreamStatusResponse(
		id=record.id,
		lid=record.lid,
		stream_no=record.stream_no,
		decision=record.decision,
		decision_other=record.decision_other,
		comments=record.comments,
		chemist_name=record.chemist_name,
	)


def _serialize_stream(stream: LeadStream, lead_date: str) -> LeadStreamResponse:
	lab = stream.lab_status
	lab_decision = lab.decision if lab is not None and lab.decision else "Pending"
	lab_days = lead_service.calculate_elapsed_days(
		lead_date,
		lab.decision_date.date() if lab is not None and lab.decision_date is not None else None,
	)
	return LeadStreamResponse(
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


def _next_stream_no(existing: list[str]) -> str:
	max_num = max(
		(
			int(m.group(1))
			for sn in existing
			for m in [SN_PATTERN.fullmatch(sn.strip().upper())]
			if m is not None
		),
		default=0,
	)
	return f"SN-{max_num + 1:03d}"
