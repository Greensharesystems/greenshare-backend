from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CircularitySecondaryEcosystemValue(BaseModel):
	secondaryProduct: str = ""
	secondaryLoop: str = ""


class CircularitySecondaryEcosystemEntry(BaseModel):
	rcid: str = ""
	rnid: str = ""
	secondaryProduct: str = ""
	secondaryLoop: str = ""


class CircularitySecondaryEcosystemDetails(BaseModel):
	mode: Literal["shared", "by_rc", "by_rn"] = "shared"
	shared: CircularitySecondaryEcosystemValue = Field(default_factory=CircularitySecondaryEcosystemValue)
	entries: list[CircularitySecondaryEcosystemEntry] = Field(default_factory=list)


class CircularityCertificateCreate(BaseModel):
	ccidDate: str
	ccid: str | None = None
	rcid: str = ""
	linkedRcids: list[str] = Field(default_factory=list)
	cid: str = ""
	producingCompanyName: str = ""
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict] | None = None
	wasteStreamQuantity: str = ""
	secondaryProduct: str = ""
	secondaryLoop: str = ""
	secondaryEcosystemDetails: CircularitySecondaryEcosystemDetails = Field(default_factory=CircularitySecondaryEcosystemDetails)
	issuedBy: str = ""
	verificationComments: str | None = None
	status: str = "Issued"


class NextCircularityCertificateIdResponse(BaseModel):
	ccid: str


class CircularityCertificateResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	ccidDate: str
	ccid: str
	rcid: str
	linkedRcids: list[str]
	cid: str
	producingCompanyName: str
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict] | None = None
	wasteStreamQuantity: str
	wasteStreamName: str | None = None
	wasteStreamClass: str | None = None
	secondaryProduct: str
	secondaryLoop: str
	secondaryEcosystemDetails: CircularitySecondaryEcosystemDetails = Field(default_factory=CircularitySecondaryEcosystemDetails)
	issuedBy: str
	verificationComments: str | None = None
	status: str
