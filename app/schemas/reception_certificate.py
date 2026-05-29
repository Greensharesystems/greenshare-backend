from pydantic import BaseModel, ConfigDict, Field


class ReceptionCertificateCreate(BaseModel):
	rcidDate: str
	rcid: str | None = None
	rnid: str = ""
	linkedRnids: list[str] = Field(default_factory=list)
	customerId: str = ""
	producingCompanyName: str = ""
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	verificationComments: str | None = None
	wasteStreamQuantity: str = ""
	rcIssuedBy: str = ""
	status: str = "Issued"


class ReceptionCertificateUpdate(BaseModel):
	rcidDate: str | None = None
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	verificationComments: str | None = None
	rcIssuedBy: str | None = None
	status: str | None = None


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
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	verificationComments: str | None = None
	wasteStreamQuantity: str
	wasteStreamName: str | None = None
	wasteStreamClass: str | None = None
	rcIssuedBy: str
	status: str
	isDeleted: bool = False
