from pydantic import BaseModel, ConfigDict


class LeadStreamCreate(BaseModel):
	waste_stream_name: str
	est_qty: float
	unit: str
	unit_other: str | None = None
	waste_class: str
	waste_class_other: str | None = None


class LeadStreamResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lid: str
	stream_no: str
	waste_stream_name: str
	est_qty: float
	unit: str
	unit_other: str | None = None
	waste_class: str
	waste_class_other: str | None = None
	lab_decision: str
	lab_decision_other: str | None = None
	lab_comments: str | None = None
	lab_chemist_name: str
	lab_status_days: int


class LabStreamStatusCreateUpdate(BaseModel):
	decision: str
	decision_other: str | None = None
	comments: str | None = None
	chemist_name: str


class LabStreamStatusResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lid: str
	stream_no: str
	decision: str
	decision_other: str | None = None
	comments: str | None = None
	chemist_name: str
