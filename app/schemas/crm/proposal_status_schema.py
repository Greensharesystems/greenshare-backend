from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProposalStatusCreateUpdate(BaseModel):
	pid: str
	status: str
	status_other: str | None = None
	comments: str | None = None
	updated_by: str


class ProposalStatusResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lead_id: int
	lid: str
	pid: str
	status: str
	status_other: str | None = None
	comments: str | None = None
	updated_by: str
	updated_at: datetime
