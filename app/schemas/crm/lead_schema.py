from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeadCreate(BaseModel):
	lid: str
	cid: str
	customer_name: str
	source: str
	source_detail: str | None = None
	assigned_to: str
	assigned_to_other: str | None = None
	waste_stream: str
	waste_class: str
	waste_class_other: str | None = None
	est_qty: float
	unit: str
	unit_other: str | None = None
	comments: str | None = None
	lead_date: str


class LeadUpdate(BaseModel):
	cid: str | None = None
	customer_name: str | None = None
	source: str | None = None
	source_detail: str | None = None
	assigned_to: str | None = None
	assigned_to_other: str | None = None
	waste_stream: str | None = None
	waste_class: str | None = None
	waste_class_other: str | None = None
	est_qty: float | None = None
	unit: str | None = None
	unit_other: str | None = None
	comments: str | None = None
	lead_date: str | None = None


class LeadResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lid: str
	cid: str
	customer_name: str
	source: str
	source_detail: str | None = None
	assigned_to: str
	assigned_to_other: str | None = None
	waste_stream: str
	waste_class: str
	waste_class_other: str | None = None
	est_qty: float
	unit: str
	unit_other: str | None = None
	comments: str | None = None
	lead_date: str
	created_at: datetime
	updated_at: datetime
	lab_id: str | None = None
	lab_status: str
	lab_updated_at: str
	proposal_id: str | None = None
	proposal_status: str
	proposal_updated_at: str
	lead_status: str
	lead_status_updated_at: str


class LeadListResponse(LeadResponse):
	pass


class NextLeadIdResponse(BaseModel):
	next_lid: str
