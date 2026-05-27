from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LabStatusCreateUpdate(BaseModel):
	lab_id: str
	decision: str
	decision_other: str | None = None
	comments: str | None = None
	chemist_name: str


class LabStatusResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lead_id: int
	lid: str
	lab_id: str
	decision: str
	decision_other: str | None = None
	comments: str | None = None
	chemist_name: str
	updated_at: datetime
