from pydantic import BaseModel, ConfigDict, Field


class FocalPersonInput(BaseModel):
	name: str
	position: str
	department: str
	email: str
	officePhone: str
	mobilePhone: str


class FocalPersonResponse(FocalPersonInput):
	hasUserAccount: bool = False


class CustomerCreate(BaseModel):
	customerIdDate: str
	customerId: str | None = None
	companyName: str
	emirate: str
	area: str
	officeLocation: str
	website: str
	companyEmail: str | None = None
	sector: str
	contactName: str | None = None
	contactPosition: str | None = None
	contactDepartment: str | None = None
	contactEmail: str | None = None
	contactOfficePhone: str | None = None
	contactMobilePhone: str | None = None
	focalPersons: list[FocalPersonInput] = Field(default_factory=list)


class CustomerUpdate(BaseModel):
	companyName: str
	emirate: str
	area: str
	officeLocation: str
	website: str
	companyEmail: str | None = None
	sector: str
	focalPersons: list[FocalPersonInput] = Field(default_factory=list)


class CustomerCsvExportRequest(BaseModel):
	customerIds: list[str] = []


class CustomerResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	customerIdDate: str
	customerId: str
	companyName: str
	companyEmirate: str
	area: str
	officeAddress: str
	website: str
	companyEmail: str | None = None
	sector: str
	contactPersonName: str
	contactPersonPosition: str
	contactPersonDepartment: str
	contactPersonEmail: str
	contactPersonOfficePhone: str
	contactPersonMobilePhone: str
	focalPersons: list[FocalPersonResponse] = Field(default_factory=list)
	lastActive: str


class CustomerSearchResponse(BaseModel):
	cid: str
	customer_name: str


class NextCustomerIdResponse(BaseModel):
	customerId: str
