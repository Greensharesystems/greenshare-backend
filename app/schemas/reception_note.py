from pydantic import BaseModel, ConfigDict, Field


class ReceptionNoteWasteStream(BaseModel):
	code: str
	name: str
	wasteClass: str
	physicalState: str
	quantity: str
	quantityUnit: str
	receptionDate: str
	collectionEmirate: str = ""
	collectionLocation: str = ""


class ReceptionNoteCreate(BaseModel):
	rnidDate: str
	rnid: str | None = None
	customerId: str
	weighBridgeSlipDate: str = ""
	weighBridgeBillNo: str = ""
	producingCompanyName: str
	producingCompanyEmirate: str = ""
	producingCompanyOfficeAddress: str = ""
	producingCompanyContactPerson: str = ""
	producingCompanyOfficePhone: str = ""
	producingCompanyEmail: str = ""
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	transportingCompanyName: str = ""
	transportingCompanyContactPerson: str = ""
	transportingCompanyOfficePhone: str = ""
	transportingCompanyEmail: str = ""
	wasteStreams: list[ReceptionNoteWasteStream] = Field(default_factory=list)
	vehiclePlateNo: str = ""
	driverName: str = ""
	wasteStreamName: str = ""
	wasteStreamQuantity: str = ""
	rnIssuedBy: str = ""
	status: str = "Issued"


class ReceptionNoteUpdate(BaseModel):
	rnidDate: str | None = None
	weighBridgeSlipDate: str | None = None
	weighBridgeBillNo: str | None = None
	producingCompanyName: str | None = None
	producingCompanyEmirate: str | None = None
	producingCompanyOfficeAddress: str | None = None
	producingCompanyContactPerson: str | None = None
	producingCompanyOfficePhone: str | None = None
	producingCompanyEmail: str | None = None
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	transportingCompanyName: str | None = None
	transportingCompanyContactPerson: str | None = None
	transportingCompanyOfficePhone: str | None = None
	transportingCompanyEmail: str | None = None
	wasteStreams: list[ReceptionNoteWasteStream] | None = None
	vehiclePlateNo: str | None = None
	driverName: str | None = None
	wasteStreamName: str | None = None
	wasteStreamQuantity: str | None = None
	rnIssuedBy: str | None = None
	status: str | None = None


class NextReceptionNoteIdResponse(BaseModel):
	rnid: str


class ReceptionNoteResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	rnidDate: str
	rnid: str
	customerId: str
	weighBridgeSlipDate: str
	weighBridgeBillNo: str
	producingCompanyName: str
	producingCompanyEmirate: str
	producingCompanyOfficeAddress: str
	producingCompanyContactPerson: str
	producingCompanyOfficePhone: str
	producingCompanyEmail: str
	referringCompany: str | None = None
	projectName: str | None = None
	projectNumber: str | None = None
	projectLocation: str | None = None
	projectCustomFields: list[dict[str, str]] | None = None
	transportingCompanyName: str
	transportingCompanyContactPerson: str
	transportingCompanyOfficePhone: str
	transportingCompanyEmail: str
	wasteStreams: list[ReceptionNoteWasteStream]
	vehiclePlateNo: str
	driverName: str
	wasteStreamName: str
	wasteStreamQuantity: str
	rnIssuedBy: str
	status: str
	isDeleted: bool = False
