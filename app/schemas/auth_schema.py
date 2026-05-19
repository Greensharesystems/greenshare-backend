from pydantic import BaseModel


class LoginRequest(BaseModel):
	email: str
	password: str


class LoginResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
	role: str
	user_id: str
	display_name: str
	cid: str | None = None
	geid: str | None = None