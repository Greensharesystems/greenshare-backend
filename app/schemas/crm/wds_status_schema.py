from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WdsStatusCreateUpdate(BaseModel):
	date_submitted: str | None = None
	date_approved: str | None = None
	comments: str | None = None
	updated_by: str | None = None


class WdsStatusResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	lead_id: int
	lid: str
	date_submitted: str | None = None
	date_approved: str | None = None
	status: str
	days: int | None = None
	comments: str | None = None
	updated_by: str | None = None
	updated_at: datetime
