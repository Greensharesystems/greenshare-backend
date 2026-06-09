from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


StreamCodeCategory = Literal["Hazardous Stream", "Non-Hazardous Stream", "Recyclable Stream"]
StreamCodeStatus = Literal["Active", "Inactive"]


class NextStreamCodeResponse(BaseModel):
	next_stream_code: str


class StreamCodeCreate(BaseModel):
	stream_code: str
	category: StreamCodeCategory
	stream_name: str
	description: str | None = None
	status: StreamCodeStatus = "Active"
	scid: str | None = None

	@field_validator("stream_code", "stream_name", "status", "category", mode="before")
	@classmethod
	def strip_required_strings(cls, value: object) -> object:
		if isinstance(value, str):
			return value.strip()
		return value

	@field_validator("description", "scid", mode="before")
	@classmethod
	def normalize_optional_strings(cls, value: object) -> object:
		if value is None:
			return None
		if isinstance(value, str):
			return value.strip() or None
		return value


class StreamCodeUpdate(BaseModel):
	stream_code: str | None = None
	category: StreamCodeCategory | None = None
	stream_name: str | None = None
	description: str | None = None
	status: StreamCodeStatus | None = None
	scid: str | None = None

	@field_validator("stream_code", "stream_name", "status", "category", mode="before")
	@classmethod
	def strip_required_strings(cls, value: object) -> object:
		if isinstance(value, str):
			return value.strip()
		return value

	@field_validator("description", "scid", mode="before")
	@classmethod
	def normalize_optional_strings(cls, value: object) -> object:
		if value is None:
			return None
		if isinstance(value, str):
			return value.strip() or None
		return value


class StreamCodeResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	scid: str | None = None
	stream_code: str
	category: StreamCodeCategory
	stream_name: str
	description: str | None = None
	status: StreamCodeStatus
	created_at: datetime
	updated_at: datetime
