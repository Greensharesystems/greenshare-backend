from pydantic import BaseModel, ConfigDict, Field


class ReceptionCertificateCreate(BaseModel):
	rcidDate: str
	rcid: str | None = None
	rnid: str = ""
	linkedRnids: list[str] = Field(default_factory=list)
	customerId: str = ""
	producingCompanyName: str = ""
	wasteStreamQuantity: str = ""
	rcIssuedBy: str = ""
	status: str = "Issued"


class NextReceptionCertificateIdResponse(BaseModel):
	rcid: str


class ReceptionCertificateResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	rcidDate: str
	rcid: str
	rnid: str
	linkedRnids: list[str]
	customerId: str
	producingCompanyName: str
	wasteStreamQuantity: str
	rcIssuedBy: str
	status: str
