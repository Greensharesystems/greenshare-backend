from typing import Literal

from pydantic import BaseModel, Field


class DashboardStatResponse(BaseModel):
	label: str
	value: str


class DashboardCardResponse(BaseModel):
	type: Literal["kpi", "widget"]
	title: str
	value: str = ""
	description: str = ""
	stats: list[DashboardStatResponse] = Field(default_factory=list)


class DashboardSectionResponse(BaseModel):
	cards: list[DashboardCardResponse] = Field(default_factory=list)


class DashboardResponse(BaseModel):
	role: Literal["admin", "employee", "customer"]
	title: str
	sections: list[DashboardSectionResponse] = Field(default_factory=list)


class CustomerDashboardQuantityByClassResponse(BaseModel):
	hazardous: int | float
	non_hazardous: int | float


class CustomerDashboardWasteStreamTrendPointResponse(BaseModel):
	month: str
	quantities_by_stream: dict[str, int | float] = Field(default_factory=dict)


class CustomerDashboardWasteStreamTrendResponse(BaseModel):
	waste_streams: list[str] = Field(default_factory=list)
	points: list[CustomerDashboardWasteStreamTrendPointResponse] = Field(default_factory=list)


class CustomerDashboardMonthlyReceptionQuantitiesResponse(BaseModel):
	months: list[str] = Field(default_factory=list)
	values: list[int | float] = Field(default_factory=list)


class CustomerDashboardCollectionSourceLocationResponse(BaseModel):
	emirate_name: str
	area_name: str
	location_name: str
	quantity: int | float
	latitude: float
	longitude: float


class CustomerDashboardSecondaryLoopFlowResponse(BaseModel):
	waste_stream_name: str
	secondary_product: str
	secondary_loop: str
	quantity: int | float


class CustomerDashboardCircularContributionResponse(BaseModel):
	total: int | float = 0
	materials: int | float = 0
	energy: int | float = 0


class CustomerDashboardEnvironmentalImpactResponse(BaseModel):
	landfill_diversion_percent: int | float = 0
	co2_reduced: int | float = 0
	ghg_emissions_reduced: int | float = 0
	trees_planted: int | float = 0
	homes_powered: int | float = 0


class CustomerDashboardResponse(BaseModel):
	total_quantity_processed: int | float
	quantity_by_class: CustomerDashboardQuantityByClassResponse
	waste_stream_trend: CustomerDashboardWasteStreamTrendResponse
	monthly_reception_quantities: CustomerDashboardMonthlyReceptionQuantitiesResponse
	collection_source_locations: list[CustomerDashboardCollectionSourceLocationResponse] = Field(default_factory=list)
	secondary_loop_flow: list[CustomerDashboardSecondaryLoopFlowResponse] = Field(default_factory=list)
	circular_contribution: CustomerDashboardCircularContributionResponse = Field(default_factory=CustomerDashboardCircularContributionResponse)
	environmental_impact: CustomerDashboardEnvironmentalImpactResponse = Field(default_factory=CustomerDashboardEnvironmentalImpactResponse)
