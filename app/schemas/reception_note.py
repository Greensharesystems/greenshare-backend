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
