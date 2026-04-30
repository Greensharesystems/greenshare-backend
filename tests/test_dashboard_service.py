import csv
from io import StringIO
from types import SimpleNamespace

from app.services import dashboard_service


def test_calculate_secondary_loop_flow_aggregates_by_waste_stream_and_secondary_product(monkeypatch) -> None:
	circularity_certificate = SimpleNamespace(
		linked_rcids=["RCID-0001-0001", "RCID-0001-0001", "RCID-0001-0002"],
		rcid="RCID-0001-0001,RCID-0001-0001,RCID-0001-0002",
		secondary_product="Material, Energy",
		secondary_loop="Manufacturer, Trader",
		secondary_ecosystem_details={
			"mode": "by_rc",
			"shared": {"secondaryProduct": "", "secondaryLoop": ""},
			"entries": [
				{"rcid": "RCID-0001-0001", "secondaryProduct": "Material", "secondaryLoop": "Manufacturer"},
				{"rcid": "RCID-0001-0002", "secondaryProduct": "Energy", "secondaryLoop": "Trader"},
			],
		},
	)
	reception_certificates = {
		"RCID-0001-0001": SimpleNamespace(linked_rnids=["RNID-0001-0001", "RNID-0001-0001"], rnid="RNID-0001-0001"),
		"RCID-0001-0002": SimpleNamespace(linked_rnids=["RNID-0001-0002", "RNID-0001-0002"], rnid="RNID-0001-0002"),
	}
	reception_notes = {
		"RNID-0001-0001": SimpleNamespace(
			waste_streams=[
				{"name": "Metal Scrap", "quantity": "2", "quantityUnit": "Tons"},
				{"name": "Metal Scrap", "quantity": "500", "quantityUnit": "Kgs"},
			],
			waste_stream_quantity="",
			waste_stream_name="",
		),
		"RNID-0001-0002": SimpleNamespace(
			waste_streams=[
				{"name": "Sludge", "quantity": "80", "quantityUnit": "Liters"},
				{"name": "Sludge", "quantity": "1", "quantityUnit": "Metric Tons"},
			],
			waste_stream_quantity="",
			waste_stream_name="",
		),
		}

	monkeypatch.setattr(
		dashboard_service.circularity_certificate_repository,
		"get_circularity_certificates_by_customer_id",
		lambda db, customer_id: [circularity_certificate],
	)
	monkeypatch.setattr(
		dashboard_service.reception_certificate_repository,
		"get_reception_certificate_by_rcid",
		lambda db, rcid: reception_certificates.get(rcid),
	)
	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_note_by_rnid",
		lambda db, rnid: reception_notes.get(rnid),
	)

	results = dashboard_service.calculate_secondary_loop_flow(db=None, customer_id="CID-0001")
	flow_lookup = {(item.waste_stream_name, item.secondary_product, item.secondary_loop): item.quantity for item in results}

	assert flow_lookup == {
		("Metal Scrap", "Materials", "Manufacturer"): 2500,
		("Sludge", "Energy", "Trader"): 1080,
	}


def test_build_employee_dashboard_uses_shared_operational_totals(monkeypatch) -> None:
	counts = {
		dashboard_service.ReceptionNote: 12,
		dashboard_service.ReceptionCertificate: 7,
		dashboard_service.CircularityCertificate: 4,
		dashboard_service.Customer: 9,
	}
	today_counts = {
		dashboard_service.ReceptionNote: 3,
		dashboard_service.ReceptionCertificate: 2,
		dashboard_service.CircularityCertificate: 1,
	}

	def fake_count_rows(db, model, *conditions):
		if any(str(condition).endswith("status = :status_1") for condition in conditions):
			base_value = counts[model]
			return base_value - 1

		return counts[model]

	def fake_count_today(db, model, *conditions):
		return today_counts[model]

	monkeypatch.setattr(dashboard_service, "count_rows", fake_count_rows)
	monkeypatch.setattr(dashboard_service, "count_today", fake_count_today)

	response = dashboard_service.build_employee_dashboard(db=None)

	assert response.role == "employee"
	assert response.sections[0].cards[0].value == "12"
	assert response.sections[0].cards[1].value == "7"
	assert response.sections[0].cards[2].value == "4"
	assert response.sections[1].cards[0].value == "9"


def test_calculate_secondary_loop_flow_uses_shared_secondary_product_fallback(monkeypatch) -> None:
	circularity_certificate = SimpleNamespace(
		linked_rcids=["RCID-0001-0003"],
		rcid="RCID-0001-0003",
		secondary_product="Energy",
		secondary_loop="Trader",
		secondary_ecosystem_details={
			"mode": "shared",
			"shared": {"secondaryProduct": "Energy", "secondaryLoop": "Trader"},
			"entries": [],
		},
	)

	monkeypatch.setattr(
		dashboard_service.circularity_certificate_repository,
		"get_circularity_certificates_by_customer_id",
		lambda db, customer_id: [circularity_certificate],
	)
	monkeypatch.setattr(
		dashboard_service.reception_certificate_repository,
		"get_reception_certificate_by_rcid",
		lambda db, rcid: SimpleNamespace(linked_rnids=["RNID-0001-0003"], rnid="RNID-0001-0003"),
	)
	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_note_by_rnid",
		lambda db, rnid: SimpleNamespace(
			waste_streams=[{"name": "Filter Cake", "quantity": "25", "quantityUnit": "kg"}],
			waste_stream_quantity="",
			waste_stream_name="",
		),
	)

	results = dashboard_service.calculate_secondary_loop_flow(db=None, customer_id="CID-0001")

	assert len(results) == 1
	assert results[0].waste_stream_name == "Filter Cake"
	assert results[0].secondary_product == "Energy"
	assert results[0].secondary_loop == "Trader"
	assert results[0].quantity == 25


def test_calculate_secondary_loop_flow_uses_certificate_level_fallback_when_shared_context_is_missing(monkeypatch) -> None:
	circularity_certificate = SimpleNamespace(
		linked_rcids=["RCID-0001-0004"],
		rcid="RCID-0001-0004",
		secondary_product="Material",
		secondary_loop="Manufacturer",
		secondary_ecosystem_details={
			"mode": "shared",
			"shared": {"secondaryProduct": "", "secondaryLoop": ""},
			"entries": [],
		},
	)

	monkeypatch.setattr(
		dashboard_service.circularity_certificate_repository,
		"get_circularity_certificates_by_customer_id",
		lambda db, customer_id: [circularity_certificate],
	)
	monkeypatch.setattr(
		dashboard_service.reception_certificate_repository,
		"get_reception_certificate_by_rcid",
		lambda db, rcid: SimpleNamespace(linked_rnids=["RNID-0001-0004"], rnid="RNID-0001-0004"),
	)
	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_note_by_rnid",
		lambda db, rnid: SimpleNamespace(
			waste_streams=[{"name": "Paper Pulp", "quantity": "40", "quantityUnit": "kg"}],
			waste_stream_quantity="",
			waste_stream_name="",
		),
	)

	results = dashboard_service.calculate_secondary_loop_flow(db=None, customer_id="CID-0001")

	assert len(results) == 1
	assert results[0].secondary_product == "Materials"
	assert results[0].secondary_loop == "Manufacturer"
	assert results[0].quantity == 40


def test_calculate_circular_contribution_sums_materials_and_energy(monkeypatch) -> None:
	monkeypatch.setattr(
		dashboard_service,
		"get_secondary_loop_flow_totals",
		lambda db, customer_id: {
			("Metal Scrap", "Materials", "Manufacturer"): dashboard_service.Decimal("55"),
			("Plastic Flakes", "Materials", "Trader"): dashboard_service.Decimal("20"),
			("Sludge", "Energy", "Trader"): dashboard_service.Decimal("80"),
		},
	)

	result = dashboard_service.calculate_circular_contribution(db=None, customer_id="CID-0001")

	assert result.materials == 75
	assert result.energy == 80


def test_calculate_environmental_impact_uses_fixed_landfill_diversion(monkeypatch) -> None:
	monkeypatch.setattr(
		dashboard_service,
		"calculate_circular_contribution",
		lambda db, customer_id: dashboard_service.CustomerDashboardCircularContributionResponse(materials=90, energy=45),
	)
	monkeypatch.setattr(
		dashboard_service,
		"calculate_total_quantity_processed",
		lambda db, customer_id: 150,
	)

	result = dashboard_service.calculate_environmental_impact(db=None, customer_id="CID-0001")

	assert result.landfill_diversion_percent == 100
	assert result.co2_reduced == 220.5
	assert result.ghg_emissions_reduced == 249.75
	assert result.trees_planted == 10.13
	assert result.homes_powered == 0.05


def test_calculate_total_quantity_processed_converts_supported_units_to_kgs() -> None:
	class FakeDb:
		pass

	original_get_reception_notes = dashboard_service.reception_note_repository.get_reception_notes_by_customer_id
	try:
		dashboard_service.reception_note_repository.get_reception_notes_by_customer_id = lambda db, customer_id: [
			SimpleNamespace(
				waste_streams=[
					{"quantity": "2", "quantityUnit": "Tons"},
					{"quantity": "250", "quantityUnit": "Kgs"},
					{"quantity": "10", "quantityUnit": "Liters"},
				],
				waste_stream_quantity="",
			),
			SimpleNamespace(
				waste_streams=[],
				waste_stream_quantity="1.5 Metric Tons",
			),
		]

		result = dashboard_service.calculate_total_quantity_processed(FakeDb(), "CID-0001")
	finally:
		dashboard_service.reception_note_repository.get_reception_notes_by_customer_id = original_get_reception_notes


	assert result == 3760



def test_calculate_quantity_by_class_converts_supported_units_to_kgs(monkeypatch) -> None:
	reception_notes = [
		SimpleNamespace(
			waste_streams=[
				{"wasteClass": "Hazardous", "quantity": "50", "quantityUnit": "Tons"},
				{"wasteClass": "Non-Hazardous", "quantity": "200", "quantityUnit": "Kgs"},
			],
			waste_stream_quantity="",
		),
		SimpleNamespace(
			waste_streams=[
				{"wasteClass": "Hazardous", "quantity": "1.5", "quantityUnit": "Metric Tons"},
				{"wasteClass": "Non-Hazardous", "quantity": "40", "quantityUnit": "Liters"},
			],
			waste_stream_quantity="",
		),
		SimpleNamespace(
			waste_streams=[],
			waste_stream_quantity="10 Kgs",
			waste_stream_class="Non-Hazardous",
		),
	]

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: reception_notes,
	)

	result = dashboard_service.calculate_quantity_by_class(db=None, customer_id="CID-0001")

	assert result.hazardous == 51500
	assert result.non_hazardous == 250


def test_calculate_waste_stream_trend_uses_reception_date_and_converts_to_kgs(monkeypatch) -> None:
	reception_notes = [
		SimpleNamespace(
			waste_streams=[
				{
					"name": "Plastic",
					"quantity": "50",
					"quantityUnit": "Tons",
					"receptionDate": "02-04-2026",
				},
				{
					"name": "Plastic",
					"quantity": "10",
					"quantityUnit": "Kgs",
					"receptionDate": "15-05-2026",
				},
				{
					"name": "Oil Sludge",
					"quantity": "60",
					"quantityUnit": "Liters",
					"receptionDate": "18-04-2026",
				},
			],
			waste_stream_quantity="",
			rnid_date="01-01-2026",
		),
		SimpleNamespace(
			waste_streams=[
				{
					"name": "Plastic",
					"quantity": "1.5",
					"quantityUnit": "Metric Tons",
					"receptionDate": "05-06-2026",
				},
				{
					"name": "Ignored Stream",
					"quantity": "25",
					"quantityUnit": "Kgs",
					"receptionDate": "",
				},
			],
			waste_stream_quantity="100 Kgs",
			rnid_date="01-04-2026",
		),
	]

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: reception_notes,
	)

	result = dashboard_service.calculate_waste_stream_trend(db=None, customer_id="CID-0001")

	assert result.waste_streams == ["Oil Sludge", "Plastic"]
	assert [(point.month, point.quantities_by_stream) for point in result.points] == [
		("Apr", {"Oil Sludge": 60, "Plastic": 50000}),
		("May", {"Oil Sludge": 0, "Plastic": 10}),
		("Jun", {"Oil Sludge": 0, "Plastic": 1500}),
	]


def test_calculate_monthly_reception_quantities_uses_reception_date_and_converts_to_kgs(monkeypatch) -> None:
	reception_notes = [
		SimpleNamespace(
			waste_streams=[
				{
					"quantity": "50",
					"quantityUnit": "Tons",
					"receptionDate": "02-04-2026",
				},
				{
					"quantity": "60",
					"quantityUnit": "Liters",
					"receptionDate": "18-04-2026",
				},
				{
					"quantity": "10",
					"quantityUnit": "Kgs",
					"receptionDate": "15-05-2026",
				},
			],
			waste_stream_quantity="",
			rnid_date="01-01-2026",
		),
		SimpleNamespace(
			waste_streams=[
				{
					"quantity": "1.5",
					"quantityUnit": "Metric Tons",
					"receptionDate": "05-06-2026",
				},
				{
					"quantity": "25",
					"quantityUnit": "Kgs",
					"receptionDate": "",
				},
			],
			waste_stream_quantity="100 Kgs",
			rnid_date="01-04-2026",
		),
	]

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: reception_notes,
	)

	result = dashboard_service.calculate_monthly_reception_quantities(db=None, customer_id="CID-0001")

	assert result.months == ["Apr", "May", "Jun"]
	assert result.values == [50060, 10, 1500]


def test_calculate_collection_source_locations_uses_reception_note_emirate_and_location_labels(monkeypatch) -> None:
	reception_notes = [
		SimpleNamespace(
			waste_streams=[
				{
					"collectionEmirate": "Dubai",
					"collectionLocation": "Street 5 Jafza",
					"quantity": "50",
					"quantityUnit": "Tons",
				},
				{
					"collectionEmirate": "Dubai",
					"collectionLocation": "Warehouse 2 Jafza",
					"quantity": "20",
					"quantityUnit": "Tons",
				},
				{
					"collectionEmirate": "Dubai",
					"collectionLocation": "Jebel Ali Facility",
					"quantity": "100",
					"quantityUnit": "Kgs",
				},
				{
					"collectionEmirate": "Sharjah",
					"collectionLocation": "Unknown Yard",
					"quantity": "5",
					"quantityUnit": "Liters",
				},
			],
			waste_stream_quantity="",
		),
	]

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: reception_notes,
	)

	result = dashboard_service.calculate_collection_source_locations(db=None, customer_id="CID-0001")
	lookup = {
		(item.emirate_name, item.area_name): (item.quantity, item.latitude, item.longitude, item.location_name)
		for item in result
	}

	assert lookup == {
		("Dubai", "Jebel Ali Facility"): (100, 24.9857, 55.0658, "Jebel Ali Facility"),
		("Dubai", "Street 5 Jafza"): (50000, 24.9857, 55.0658, "Street 5 Jafza"),
		("Dubai", "Warehouse 2 Jafza"): (20000, 24.9857, 55.0658, "Warehouse 2 Jafza"),
		("Sharjah", "Unknown Yard"): (5, 25.3463, 55.4209, "Unknown Yard"),
	}


def test_calculate_collection_source_locations_recognizes_khalifa_industrial(monkeypatch) -> None:
	reception_notes = [
		SimpleNamespace(
			waste_streams=[
				{
					"collectionEmirate": "Abu Dhabi",
					"collectionLocation": "Khalifa Industrial",
					"quantity": "25",
					"quantityUnit": "Tons",
				},
			],
			waste_stream_quantity="",
		),
	]

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: reception_notes,
	)

	result = dashboard_service.calculate_collection_source_locations(db=None, customer_id="CID-0001")

	assert len(result) == 1
	assert result[0].emirate_name == "Abu Dhabi"
	assert result[0].area_name == "Khalifa Industrial"
	assert result[0].location_name == "Khalifa Industrial"
	assert result[0].latitude == 24.8222
	assert result[0].longitude == 54.6622
	assert result[0].quantity == 25000


def test_export_customer_reports_csv_includes_required_columns_and_linked_customer_data(monkeypatch) -> None:
	reception_note = SimpleNamespace(
		rnid_date="2026-04-01",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		waste_streams=[
			{
				"name": "Metal Scrap",
				"quantity": "125",
				"quantityUnit": "Kgs",
				"receptionDate": "2026-04-02",
				"collectionLocation": "Jebel Ali Facility",
			},
		],
		waste_stream_quantity="",
		waste_stream_name="",
	)
	reception_certificate = SimpleNamespace(
		rcid_date="2026-04-03",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
	)
	circularity_certificate = SimpleNamespace(
		ccid_date="2026-04-04",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		secondary_product="Materials",
		secondary_loop="Manufacturer",
		secondary_ecosystem_details={
			"shared": {"secondaryProduct": "Materials", "secondaryLoop": "Manufacturer"},
			"entries": [],
		},
	)

	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: [reception_note],
	)
	monkeypatch.setattr(
		dashboard_service.reception_certificate_repository,
		"get_reception_certificates_by_customer_id",
		lambda db, customer_id: [reception_certificate],
	)
	monkeypatch.setattr(
		dashboard_service.circularity_certificate_repository,
		"get_circularity_certificates_by_customer_id",
		lambda db, customer_id: [circularity_certificate],
	)

	filename, csv_content = dashboard_service.export_customer_reports_csv(db=None, customer_id="CID-0001")
	reader = csv.DictReader(StringIO(csv_content))
	rows = list(reader)

	assert filename == "cid-0001-reports-export.csv"
	assert reader.fieldnames == dashboard_service.CUSTOMER_REPORT_CSV_COLUMNS
	assert rows == [{
		"RNID Date": "01-04-2026",
		"RNID": "RNID-0001-0001",
		"RCID Date": "03-04-2026",
		"RCID": "RCID-0001-0001",
		"CCID Date": "04-04-2026",
		"CCID": "CCID-0001-0001",
		"Waste Stream Name": "Metal Scrap",
		"Quantity": "125",
		"Quantity Unit": "Kgs",
		"Reception Date": "02-04-2026",
		"Waste Reception Facilities": "Jebel Ali Facility",
		"Secondary Product": "Materials",
		"Secondary Loop": "Manufacturer",
		"Landfill Diversion": "100%",
	}]


def test_build_customer_report_rows_filters_out_other_customer_records(monkeypatch) -> None:
	monkeypatch.setattr(
		dashboard_service.reception_note_repository,
		"get_reception_notes_by_customer_id",
		lambda db, customer_id: [
			SimpleNamespace(
				rnid_date="2026-04-01",
				rnid="RNID-0001-0001",
				customer_id="CID-0001",
				waste_streams=[{"name": "Paper", "quantity": "50", "quantityUnit": "Kgs", "receptionDate": "2026-04-02", "collectionLocation": "Dubai"}],
				waste_stream_quantity="",
				waste_stream_name="",
			),
			SimpleNamespace(
				rnid_date="2026-04-05",
				rnid="RNID-0002-0001",
				customer_id="CID-0002",
				waste_streams=[{"name": "Glass", "quantity": "90", "quantityUnit": "Kgs", "receptionDate": "2026-04-06", "collectionLocation": "Sharjah"}],
				waste_stream_quantity="",
				waste_stream_name="",
			),
		],
	)
	monkeypatch.setattr(
		dashboard_service.reception_certificate_repository,
		"get_reception_certificates_by_customer_id",
		lambda db, customer_id: [
			SimpleNamespace(rcid_date="2026-04-03", rcid="RCID-0001-0001", rnid="RNID-0001-0001", linked_rnids=["RNID-0001-0001"], customer_id="CID-0001"),
			SimpleNamespace(rcid_date="2026-04-07", rcid="RCID-0002-0001", rnid="RNID-0002-0001", linked_rnids=["RNID-0002-0001"], customer_id="CID-0002"),
		],
	)
	monkeypatch.setattr(
		dashboard_service.circularity_certificate_repository,
		"get_circularity_certificates_by_customer_id",
		lambda db, customer_id: [
			SimpleNamespace(ccid_date="2026-04-04", ccid="CCID-0001-0001", rcid="RCID-0001-0001", linked_rcids=["RCID-0001-0001"], cid="CID-0001", secondary_product="Materials", secondary_loop="Manufacturer", secondary_ecosystem_details={"shared": {"secondaryProduct": "Materials", "secondaryLoop": "Manufacturer"}, "entries": []}),
			SimpleNamespace(ccid_date="2026-04-08", ccid="CCID-0002-0001", rcid="RCID-0002-0001", linked_rcids=["RCID-0002-0001"], cid="CID-0002", secondary_product="Energy", secondary_loop="Trader", secondary_ecosystem_details={"shared": {"secondaryProduct": "Energy", "secondaryLoop": "Trader"}, "entries": []}),
		],
	)

	rows = dashboard_service.build_customer_report_rows(db=None, customer_id="CID-0001")

	assert len(rows) == 1
	assert rows[0]["RNID"] == "RNID-0001-0001"
	assert rows[0]["RCID"] == "RCID-0001-0001"
	assert rows[0]["CCID"] == "CCID-0001-0001"