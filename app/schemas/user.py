from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
	userIdDate: str
	userId: str | None = None
	firstName: str
	lastName: str
	email: str
	position: str | None = None
	department: str | None = None
	mobile: str | None = None
	password: str
	company: str
	role: str
	customerId: str | None = None


class UserUpdate(BaseModel):
	firstName: str
	lastName: str
	email: str
	position: str | None = None
	department: str | None = None
	mobile: str | None = None
	company: str
	role: str
	customerId: str | None = None


class UserCsvExportRequest(BaseModel):
	userIds: list[str] = []


class UserPasswordUpdate(BaseModel):
	password: str


class NextUserIdResponse(BaseModel):
	userId: str


class UserResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	userIdDate: str
	userId: str
	userName: str
	company: str
	role: str
	lastActive: str
	email: str
	position: str | None = None
	department: str | None = None
	mobile: str | None = None
	customerId: str | None = None
