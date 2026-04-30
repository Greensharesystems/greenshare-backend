import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO

from sqlalchemy import func, select

from app.core.auth import AuthPrincipal, get_customer_scope_id
from app.core.date_utils import normalize_date_for_output, parse_supported_date
from app.models.circularity_certificate import CircularityCertificate
from app.models.customer import Customer
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.models.user import User
from app.schemas.dashboard import (
	CustomerDashboardCircularContributionResponse,
	CustomerDashboardCollectionSourceLocationResponse,
	CustomerDashboardEnvironmentalImpactResponse,
	CustomerDashboardMonthlyReceptionQuantitiesResponse,
	CustomerDashboardQuantityByClassResponse,
	CustomerDashboardResponse,
	CustomerDashboardSecondaryLoopFlowResponse,
	CustomerDashboardWasteStreamTrendPointResponse,
	CustomerDashboardWasteStreamTrendResponse,
	DashboardCardResponse,
	DashboardResponse,
	DashboardSectionResponse,
	DashboardStatResponse,
)
from app.services.reception_certificate_service import parse_decimal_quantity, split_quantity_and_unit
from app.repositories import circularity_certificate_repository, reception_certificate_repository, reception_note_repository


def get_customer_dashboard(db, customer_id: str) -> CustomerDashboardResponse:
	normalized_customer_id = customer_id.strip().upper()

	if not normalized_customer_id:
		raise ValueError("Customer ID is required.")

	return CustomerDashboardResponse(
		total_quantity_processed=calculate_total_quantity_processed(db, normalized_customer_id),
		quantity_by_class=calculate_quantity_by_class(db, normalized_customer_id),
		waste_stream_trend=calculate_waste_stream_trend(db, normalized_customer_id),
		monthly_reception_quantities=calculate_monthly_reception_quantities(db, normalized_customer_id),
		collection_source_locations=calculate_collection_source_locations(db, normalized_customer_id),
		secondary_loop_flow=calculate_secondary_loop_flow(db, normalized_customer_id),
		circular_contribution=calculate_circular_contribution(db, normalized_customer_id),
		environmental_impact=calculate_environmental_impact(db, normalized_customer_id),
	)


def export_customer_reports_csv(db, customer_id: str) -> tuple[str, str]:
	normalized_customer_id = customer_id.strip().upper()

	if not normalized_customer_id:
		raise ValueError("Customer ID is required.")

	rows = build_customer_report_rows(db, normalized_customer_id)
	buffer = StringIO()
	writer = csv.DictWriter(buffer, fieldnames=CUSTOMER_REPORT_CSV_COLUMNS)
	writer.writeheader()
	writer.writerows(rows)

	filename = f"{normalized_customer_id.lower()}-reports-export.csv"
	return filename, buffer.getvalue()


def get_dashboard(db, principal: AuthPrincipal) -> DashboardResponse:
	if principal.role == "admin":
		return build_admin_dashboard(db)

	if principal.role == "employee":
		return build_employee_dashboard(db)

	if principal.role == "customer":
		return build_customer_dashboard(db, get_customer_scope_id(principal))

	raise ValueError("Unsupported dashboard role.")


def build_admin_dashboard(db) -> DashboardResponse:
	total_users = count_rows(db, User)
	total_customers = count_rows(db, Customer)
	total_reception_notes = count_rows(db, ReceptionNote)
	total_reception_certificates = count_rows(db, ReceptionCertificate)
	total_circularity_certificates = count_rows(db, CircularityCertificate)
	total_certificates = total_reception_certificates + total_circularity_certificates
	total_employees = count_rows(db, User, User.role.ilike("Employee"))
	total_admins = count_rows(db, User, User.role.ilike("Admin"))

	return DashboardResponse(
		role="admin",
		title="Admin Dashboard",
		sections=[
			DashboardSectionResponse(cards=[
				kpi_card("Total Users", total_users, "Active user accounts across the platform."),
				kpi_card("Certificates", total_certificates, "Reception and circularity certificates issued in the system."),
				kpi_card("Reception Notes", total_reception_notes, "Reception notes currently tracked in operations."),
			]),
			DashboardSectionResponse(cards=[
				kpi_card("Customers", total_customers, "Customer organizations onboarded to the platform."),
				kpi_card("Employees", total_employees, "Employees currently active in operations."),
				kpi_card("Admins", total_admins, "Administrative accounts with platform oversight."),
			]),
		],
	)


def build_employee_dashboard(db) -> DashboardResponse:
	total_reception_notes = count_rows(db, ReceptionNote)
	issued_reception_notes = count_rows(db, ReceptionNote, ReceptionNote.status == "Issued")
	total_reception_certificates = count_rows(db, ReceptionCertificate)
	issued_reception_certificates = count_rows(db, ReceptionCertificate, ReceptionCertificate.status == "Issued")
	total_circularity_certificates = count_rows(db, CircularityCertificate)
	issued_circularity_certificates = count_rows(db, CircularityCertificate, CircularityCertificate.status == "Issued")
	total_customers = count_rows(db, Customer)
	today_notes = count_today(db, ReceptionNote)
	today_reception_certificates = count_today(db, ReceptionCertificate)
	today_circularity_certificates = count_today(db, CircularityCertificate)

	return DashboardResponse(
		role="employee",
		title="Employee Dashboard",
		sections=[
			DashboardSectionResponse(cards=[
				kpi_card("Reception Notes", total_reception_notes, "Shared reception notes available across employee operations."),
				kpi_card("Reception Certificates", total_reception_certificates, "Shared reception certificates available across employee operations."),
				kpi_card("Circularity Certificates", total_circularity_certificates, "Shared circularity certificates available across employee operations."),
			]),
			DashboardSectionResponse(cards=[
				kpi_card("Customers", total_customers, "Customer accounts supported by shared employee operations."),
				kpi_card("Issued Notes", issued_reception_notes, "Reception notes already issued and ready for certificate workflows."),
				kpi_card("Issued Certificates", issued_reception_certificates + issued_circularity_certificates, "Certificates already issued across both stages."),
			]),
		],
	)


def build_customer_dashboard(db, customer_id: str) -> DashboardResponse:
	reception_notes = count_rows(db, ReceptionNote, ReceptionNote.customer_id == customer_id)
	issued_reception_notes = count_rows(
		db,
		ReceptionNote,
		ReceptionNote.customer_id == customer_id,
		ReceptionNote.status == "Issued",
	)
	reception_certificates = count_rows(db, ReceptionCertificate, ReceptionCertificate.customer_id == customer_id)
	issued_reception_certificates = count_rows(
		db,
		ReceptionCertificate,
		ReceptionCertificate.customer_id == customer_id,
		ReceptionCertificate.status == "Issued",
	)
	circularity_certificates = count_rows(db, CircularityCertificate, CircularityCertificate.cid == customer_id)
	issued_circularity_certificates = count_rows(
		db,
		CircularityCertificate,
		CircularityCertificate.cid == customer_id,
		CircularityCertificate.status == "Issued",
	)
	today_reception_certificates = count_today(db, ReceptionCertificate, ReceptionCertificate.customer_id == customer_id)
	today_circularity_certificates = count_today(db, CircularityCertificate, CircularityCertificate.cid == customer_id)
	total_documents = reception_notes + reception_certificates + circularity_certificates

	return DashboardResponse(
		role="customer",
		title="Customer Dashboard",
		sections=[
			DashboardSectionResponse(cards=[
				kpi_card("Reception Certificates", reception_certificates, "Active reception certificates available for customer review."),
				kpi_card("Circularity Certificates", circularity_certificates, "Circularity certificates available across your account."),
				widget_card(
					"Activity Snapshot",
					"Track recent customer activity, issued documents, and current open document volume in one view.",
					[
						stat("Issued notes", issued_reception_notes),
						stat("Open documents", total_documents - issued_circularity_certificates),
						stat("Issued reception certificates", issued_reception_certificates),
						stat("Issued circularity certificates", issued_circularity_certificates),
					],
				),
			]),
			DashboardSectionResponse(cards=[
				widget_card(
					"Traceability Overview",
					"View the current movement of tracked materials and certificate milestones across your account.",
					[
						stat("Tracked reception notes", reception_notes),
						stat("Reception certificates", reception_certificates),
						stat("Circularity certificates", circularity_certificates),
						stat("Updated today", today_reception_certificates + today_circularity_certificates),
					],
				),
				widget_card(
					"Reporting Summary",
					"Review certificate readiness, recent issuance activity, and document health from one panel.",
					[
						stat("Ready reception certificates", issued_reception_certificates),
						stat("Ready circularity certificates", issued_circularity_certificates),
						stat("New certificates today", today_reception_certificates + today_circularity_certificates),
						stat("Total documents", total_documents),
					],
				),
			]),
			DashboardSectionResponse(cards=[
				widget_card(
					"Customer Summary",
					"Keep an eye on certificate availability, traceability updates, and overall document volume from one widget.",
					[
						stat("Reception notes", reception_notes),
						stat("Issued documents", issued_reception_notes + issued_reception_certificates + issued_circularity_certificates),
						stat("Certificates", reception_certificates + circularity_certificates),
						stat("Recent activity", today_reception_certificates + today_circularity_certificates),
					],
				),
				kpi_card("Issued Notes", issued_reception_notes, "Issued reception notes linked to your account."),
				kpi_card("Pending Reviews", max(reception_certificates - issued_reception_certificates, 0), "Items still pending final issuance or review."),
			]),
		],
	)


def kpi_card(title: str, value: int | str, description: str) -> DashboardCardResponse:
	return DashboardCardResponse(
		type="kpi",
		title=title,
		value=format_metric(value),
		description=description,
	)


def widget_card(title: str, description: str, stats: list[DashboardStatResponse]) -> DashboardCardResponse:
	return DashboardCardResponse(
		type="widget",
		title=title,
		description=description,
		stats=stats,
	)


def stat(label: str, value: int | str) -> DashboardStatResponse:
	return DashboardStatResponse(label=label, value=format_metric(value))


def format_metric(value: int | str) -> str:
	if isinstance(value, int):
		return f"{value:,}"

	return value


def count_rows(db, model, *conditions) -> int:
	statement = select(func.count()).select_from(model)

	for condition in conditions:
		statement = statement.where(condition)

	return int(db.scalar(statement) or 0)


def count_today(db, model, *conditions) -> int:
	start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
	return count_rows(db, model, *conditions, model.created_at >= start_of_day)


def calculate_total_quantity_processed(db, customer_id: str) -> int | float:
	total_quantity = Decimal("0")

	for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id):
		waste_streams = list(getattr(reception_note, "waste_streams", []) or [])

		if waste_streams:
			for waste_stream in waste_streams:
				numeric_quantity, quantity_unit = split_quantity_and_unit(
					str(waste_stream.get("quantity", "") or ""),
					str(waste_stream.get("quantityUnit", "") or ""),
				)
				parsed_quantity = parse_decimal_quantity(numeric_quantity)

				if parsed_quantity is not None:
					total_quantity += convert_quantity_to_kgs(parsed_quantity, quantity_unit)

			continue

		numeric_quantity, quantity_unit = split_quantity_and_unit(str(getattr(reception_note, "waste_stream_quantity", "") or ""))
		parsed_quantity = parse_decimal_quantity(numeric_quantity)

		if parsed_quantity is not None:
			total_quantity += convert_quantity_to_kgs(parsed_quantity, quantity_unit)

	if total_quantity == total_quantity.to_integral():
		return int(total_quantity)

	return float(total_quantity)


def convert_quantity_to_kgs(quantity: Decimal, quantity_unit: str) -> Decimal:
	normalized_unit = quantity_unit.strip().lower().replace(".", "")

	if normalized_unit in {"", "kg", "kgs", "kilogram", "kilograms", "liter", "liters", "litre", "litres", "l"}:
		return quantity

	if normalized_unit in {"ton", "tons", "tonne", "tonnes", "metric ton", "metric tons"}:
		return quantity * Decimal("1000")

	return quantity


def calculate_quantity_by_class(db, customer_id: str) -> CustomerDashboardQuantityByClassResponse:
	hazardous_total = Decimal("0")
	non_hazardous_total = Decimal("0")

	for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id):
		waste_streams = list(getattr(reception_note, "waste_streams", []) or [])

		if waste_streams:
			for waste_stream in waste_streams:
				quantity_value, quantity_unit = split_quantity_and_unit(
					str(waste_stream.get("quantity", "") or ""),
					str(waste_stream.get("quantityUnit", "") or ""),
				)
				parsed_quantity = parse_decimal_quantity(quantity_value)

				if parsed_quantity is None:
					continue

				quantity_in_kgs = convert_quantity_to_kgs(parsed_quantity, quantity_unit)

				if normalize_waste_class(str(waste_stream.get("wasteClass", "") or "")) == "hazardous":
					hazardous_total += quantity_in_kgs
				else:
					non_hazardous_total += quantity_in_kgs

			continue

		quantity_value, quantity_unit = split_quantity_and_unit(str(getattr(reception_note, "waste_stream_quantity", "") or ""))
		parsed_quantity = parse_decimal_quantity(quantity_value)

		if parsed_quantity is None:
			continue

		quantity_in_kgs = convert_quantity_to_kgs(parsed_quantity, quantity_unit)

		if normalize_waste_class(str(getattr(reception_note, "waste_stream_class", "") or "")) == "hazardous":
			hazardous_total += quantity_in_kgs
		else:
			non_hazardous_total += quantity_in_kgs

	return CustomerDashboardQuantityByClassResponse(
		hazardous=decimal_to_number(hazardous_total),
		non_hazardous=decimal_to_number(non_hazardous_total),
	)


def calculate_waste_stream_trend(db, customer_id: str) -> CustomerDashboardWasteStreamTrendResponse:
	month_totals: dict[str, dict[str, Decimal]] = {}
	stream_names: set[str] = set()

	for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id):
		for month_key, waste_stream_name, quantity_in_kgs in get_reception_note_trend_entries(reception_note):
			stream_names.add(waste_stream_name)
			month_bucket = month_totals.setdefault(month_key, {})
			month_bucket[waste_stream_name] = month_bucket.get(waste_stream_name, Decimal("0")) + quantity_in_kgs

	if not month_totals:
		return CustomerDashboardWasteStreamTrendResponse()

	sorted_months = sorted(month_totals.keys(), key=parse_month_key)
	sorted_stream_names = sorted(stream_names)
	points: list[CustomerDashboardWasteStreamTrendPointResponse] = []

	for month_key in sorted_months:
		month_bucket = month_totals[month_key]
		quantities_by_stream: dict[str, int | float] = {}

		for stream_name in sorted_stream_names:
			quantities_by_stream[stream_name] = decimal_to_number(month_bucket.get(stream_name, Decimal("0")))

		points.append(
			CustomerDashboardWasteStreamTrendPointResponse(
				month=month_key,
				quantities_by_stream=quantities_by_stream,
			),
		)

	return CustomerDashboardWasteStreamTrendResponse(waste_streams=sorted_stream_names, points=points)


def calculate_monthly_reception_quantities(db, customer_id: str) -> CustomerDashboardMonthlyReceptionQuantitiesResponse:
	monthly_totals: dict[str, Decimal] = {}

	for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id):
		for month_key, quantity_in_kgs in get_reception_note_monthly_quantity_entries(reception_note):
			monthly_totals[month_key] = monthly_totals.get(month_key, Decimal("0")) + quantity_in_kgs

	if not monthly_totals:
		return CustomerDashboardMonthlyReceptionQuantitiesResponse()

	sorted_months = sorted(monthly_totals.keys(), key=parse_month_key)

	return CustomerDashboardMonthlyReceptionQuantitiesResponse(
		months=sorted_months,
		values=[decimal_to_number(monthly_totals[month_key]) for month_key in sorted_months],
	)


def calculate_collection_source_locations(db, customer_id: str) -> list[CustomerDashboardCollectionSourceLocationResponse]:
	location_totals: dict[tuple[str, str, float, float], Decimal] = {}

	for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id):
		for emirate_name, area_name, quantity, coordinates in get_reception_note_collection_entries(reception_note):
			location_key = (emirate_name, area_name, coordinates[0], coordinates[1])
			location_totals[location_key] = location_totals.get(location_key, Decimal("0")) + quantity

	results: list[CustomerDashboardCollectionSourceLocationResponse] = []

	for (emirate_name, area_name, latitude, longitude), quantity in sorted(location_totals.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower())):
		results.append(
			CustomerDashboardCollectionSourceLocationResponse(
				emirate_name=emirate_name,
				area_name=area_name,
				location_name=area_name,
				quantity=decimal_to_number(quantity),
				latitude=latitude,
				longitude=longitude,
			),
		)

	return results


def calculate_secondary_loop_flow(db, customer_id: str) -> list[CustomerDashboardSecondaryLoopFlowResponse]:
	flow_totals = get_secondary_loop_flow_totals(db, customer_id)

	return [
		CustomerDashboardSecondaryLoopFlowResponse(
			waste_stream_name=waste_stream_name,
			secondary_product=secondary_product,
			secondary_loop=secondary_loop,
			quantity=decimal_to_number(quantity),
		)
		for (waste_stream_name, secondary_product, secondary_loop), quantity in sorted(
			flow_totals.items(),
			key=lambda item: (-item[1], item[0][0].lower(), item[0][1].lower(), item[0][2].lower()),
		)
	]


def calculate_circular_contribution(db, customer_id: str) -> CustomerDashboardCircularContributionResponse:
	totals_by_product = {
		"Materials": Decimal("0"),
		"Energy": Decimal("0"),
	}

	for (_, secondary_product, _), quantity in get_secondary_loop_flow_totals(db, customer_id).items():
		totals_by_product[secondary_product] = totals_by_product.get(secondary_product, Decimal("0")) + quantity

	total_contribution = totals_by_product.get("Materials", Decimal("0")) + totals_by_product.get("Energy", Decimal("0"))

	return CustomerDashboardCircularContributionResponse(
		total=decimal_to_number(total_contribution),
		materials=decimal_to_number(totals_by_product.get("Materials", Decimal("0"))),
		energy=decimal_to_number(totals_by_product.get("Energy", Decimal("0"))),
	)


def calculate_environmental_impact(db, customer_id: str) -> CustomerDashboardEnvironmentalImpactResponse:
	contribution = calculate_circular_contribution(db, customer_id)
	materials = Decimal(str(contribution.materials or 0))
	energy = Decimal(str(contribution.energy or 0))
	landfill_diversion_percent = Decimal("100")

	co2_reduced = (materials * ENVIRONMENTAL_IMPACT_FACTORS["materials_co2"]) + (energy * ENVIRONMENTAL_IMPACT_FACTORS["energy_co2"])
	ghg_emissions_reduced = (materials * ENVIRONMENTAL_IMPACT_FACTORS["materials_ghg"]) + (energy * ENVIRONMENTAL_IMPACT_FACTORS["energy_ghg"])
	trees_planted = co2_reduced / ENVIRONMENTAL_IMPACT_FACTORS["tree_co2_offset"] if co2_reduced > 0 else Decimal("0")
	homes_powered = energy / ENVIRONMENTAL_IMPACT_FACTORS["home_energy_equivalent"] if energy > 0 else Decimal("0")

	return CustomerDashboardEnvironmentalImpactResponse(
		landfill_diversion_percent=decimal_to_number(landfill_diversion_percent.quantize(Decimal("0.01"))),
		co2_reduced=decimal_to_number(co2_reduced.quantize(Decimal("0.01"))),
		ghg_emissions_reduced=decimal_to_number(ghg_emissions_reduced.quantize(Decimal("0.01"))),
		trees_planted=decimal_to_number(trees_planted.quantize(Decimal("0.01"))),
		homes_powered=decimal_to_number(homes_powered.quantize(Decimal("0.01"))),
	)


def build_customer_report_rows(db, customer_id: str) -> list[dict[str, str]]:
	reception_notes = [
		reception_note
		for reception_note in reception_note_repository.get_reception_notes_by_customer_id(db, customer_id)
		if normalize_identifier(getattr(reception_note, "customer_id", "") or "") == customer_id
	]
	reception_certificates = [
		reception_certificate
		for reception_certificate in reception_certificate_repository.get_reception_certificates_by_customer_id(db, customer_id)
		if normalize_identifier(getattr(reception_certificate, "customer_id", "") or "") == customer_id
	]
	circularity_certificates = [
		circularity_certificate
		for circularity_certificate in circularity_certificate_repository.get_circularity_certificates_by_customer_id(db, customer_id)
		if normalize_identifier(getattr(circularity_certificate, "cid", "") or "") == customer_id
	]

	rnid_to_reception_note = {normalize_identifier(reception_note.rnid): reception_note for reception_note in reception_notes if reception_note.rnid}
	rnid_to_reception_certificates: dict[str, list[ReceptionCertificate]] = {}
	rcid_to_circularity_certificates: dict[str, list[CircularityCertificate]] = {}
	existing_rcids = {
		normalize_identifier(reception_certificate.rcid)
		for reception_certificate in reception_certificates
		if reception_certificate.rcid
	}
	rows: list[dict[str, str]] = []

	for reception_certificate in reception_certificates:
		for rnid in get_linked_rnids_for_dashboard(reception_certificate):
			normalized_rnid = normalize_identifier(rnid)
			if not normalized_rnid:
				continue

			rnid_to_reception_certificates.setdefault(normalized_rnid, []).append(reception_certificate)

	for circularity_certificate in circularity_certificates:
		for rcid in get_linked_rcids_for_dashboard(circularity_certificate):
			normalized_rcid = normalize_identifier(rcid)
			if not normalized_rcid:
				continue

			rcid_to_circularity_certificates.setdefault(normalized_rcid, []).append(circularity_certificate)

	for reception_note in reception_notes:
		normalized_rnid = normalize_identifier(reception_note.rnid)
		linked_reception_certificates = rnid_to_reception_certificates.get(normalized_rnid) or [None]

		for waste_stream in get_customer_report_waste_streams(reception_note):
			for reception_certificate in linked_reception_certificates:
				linked_circularity_certificates = (
					rcid_to_circularity_certificates.get(normalize_identifier(reception_certificate.rcid))
					if reception_certificate is not None and reception_certificate.rcid
					else None
				) or [None]

				for circularity_certificate in linked_circularity_certificates:
					rows.append(
						build_customer_report_row(
							reception_note=reception_note,
							waste_stream=waste_stream,
							reception_certificate=reception_certificate,
							circularity_certificate=circularity_certificate,
						),
					)

	for reception_certificate in reception_certificates:
		linked_note_candidates = [
			rnid_to_reception_note.get(normalize_identifier(rnid))
			for rnid in get_linked_rnids_for_dashboard(reception_certificate)
		]
		linked_notes = [note for note in linked_note_candidates if note is not None]

		if linked_notes:
			continue

		linked_circularity_certificates = rcid_to_circularity_certificates.get(normalize_identifier(reception_certificate.rcid)) or [None]
		for circularity_certificate in linked_circularity_certificates:
			rows.append(
				build_customer_report_row(
					reception_note=None,
					waste_stream=empty_customer_report_waste_stream(),
					reception_certificate=reception_certificate,
					circularity_certificate=circularity_certificate,
				),
			)

	for circularity_certificate in circularity_certificates:
		has_linked_reception_certificate = any(
			normalize_identifier(rcid) in existing_rcids
			for rcid in get_linked_rcids_for_dashboard(circularity_certificate)
		)

		if has_linked_reception_certificate:
			continue

		rows.append(
			build_customer_report_row(
				reception_note=None,
				waste_stream=empty_customer_report_waste_stream(),
				reception_certificate=None,
				circularity_certificate=circularity_certificate,
			),
		)

	return rows


def build_customer_report_row(
	*,
	reception_note: ReceptionNote | None,
	waste_stream: dict[str, str],
	reception_certificate: ReceptionCertificate | None,
	circularity_certificate: CircularityCertificate | None,
) -> dict[str, str]:
	secondary_product = ""
	secondary_loop = ""

	if circularity_certificate is not None:
		resolved_secondary_flow = resolve_secondary_loop_bucket(
			build_secondary_loop_context(circularity_certificate),
			str(getattr(reception_certificate, "rcid", "") or "").strip(),
			str(getattr(reception_note, "rnid", "") or "").strip(),
		)

		if resolved_secondary_flow is not None:
			secondary_product, secondary_loop = resolved_secondary_flow
		else:
			secondary_product = str(getattr(circularity_certificate, "secondary_product", "") or "").strip()
			secondary_loop = str(getattr(circularity_certificate, "secondary_loop", "") or "").strip()

	return {
		"RNID Date": normalize_date_for_output(str(getattr(reception_note, "rnid_date", "") or "")),
		"RNID": str(getattr(reception_note, "rnid", "") or "").strip(),
		"RCID Date": normalize_date_for_output(str(getattr(reception_certificate, "rcid_date", "") or "")),
		"RCID": str(getattr(reception_certificate, "rcid", "") or "").strip(),
		"CCID Date": normalize_date_for_output(str(getattr(circularity_certificate, "ccid_date", "") or "")),
		"CCID": str(getattr(circularity_certificate, "ccid", "") or "").strip(),
		"Waste Stream Name": str(waste_stream.get("name", "") or "").strip(),
		"Quantity": str(waste_stream.get("quantity", "") or "").strip(),
		"Quantity Unit": str(waste_stream.get("quantityUnit", "") or "").strip(),
		"Reception Date": normalize_date_for_output(str(waste_stream.get("receptionDate", "") or "")),
		"Waste Reception Facilities": str(waste_stream.get("collectionLocation", "") or "").strip(),
		"Secondary Product": secondary_product,
		"Secondary Loop": secondary_loop,
		"Landfill Diversion": "100%",
	}


def get_customer_report_waste_streams(reception_note: ReceptionNote) -> list[dict[str, str]]:
	waste_streams = list(reception_note.waste_streams or [])

	if waste_streams:
		return [
			{
				"name": str(waste_stream.get("name", "") or "").strip(),
				"quantity": str(waste_stream.get("quantity", "") or "").strip(),
				"quantityUnit": str(waste_stream.get("quantityUnit", "") or "").strip(),
				"receptionDate": normalize_date_for_output(str(waste_stream.get("receptionDate", "") or "")),
				"collectionLocation": str(waste_stream.get("collectionLocation", "") or "").strip(),
			}
			for waste_stream in waste_streams
		]

	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(str(reception_note.waste_stream_quantity or ""))
	return [{
		"name": str(reception_note.waste_stream_name or "").strip(),
		"quantity": str(fallback_quantity or "").strip(),
		"quantityUnit": str(fallback_quantity_unit or "").strip(),
		"receptionDate": "",
		"collectionLocation": "",
	}]


def empty_customer_report_waste_stream() -> dict[str, str]:
	return {
		"name": "",
		"quantity": "",
		"quantityUnit": "",
		"receptionDate": "",
		"collectionLocation": "",
	}


def normalize_identifier(value: str) -> str:
	return value.strip().upper()


def dedupe_dashboard_identifiers(values: list[str]) -> list[str]:
	seen: set[str] = set()
	ordered_values: list[str] = []

	for value in values:
		normalized_value = normalize_identifier(value)

		if not normalized_value or normalized_value in seen:
			continue

		seen.add(normalized_value)
		ordered_values.append(value)

	return ordered_values


def get_secondary_loop_flow_totals(db, customer_id: str) -> dict[tuple[str, str, str], Decimal]:
	flow_totals: dict[tuple[str, str, str], Decimal] = {}
	circularity_certificates = circularity_certificate_repository.get_circularity_certificates_by_customer_id(db, customer_id)

	for certificate in circularity_certificates:
		secondary_loop_context = build_secondary_loop_context(certificate)
		processed_links: set[tuple[str, str, str, str]] = set()

		for rcid in get_linked_rcids_for_dashboard(certificate):
			normalized_rcid = normalize_identifier(str(rcid))
			reception_certificate = reception_certificate_repository.get_reception_certificate_by_rcid(db, str(rcid))

			if reception_certificate is None:
				continue

			for rnid in get_linked_rnids_for_dashboard(reception_certificate):
				normalized_rnid = normalize_identifier(str(rnid))
				reception_note = reception_note_repository.get_reception_note_by_rnid(db, str(rnid))

				if reception_note is None:
					continue

				secondary_flow = resolve_secondary_loop_bucket(secondary_loop_context, str(rcid), str(rnid))

				if secondary_flow is None:
					continue

				link_key = (normalized_rcid, normalized_rnid, secondary_flow[0], secondary_flow[1])

				if link_key in processed_links:
					continue

				processed_links.add(link_key)

				for waste_stream_name, parsed_quantity in get_reception_note_stream_quantities(reception_note):
					flow_key = (waste_stream_name, secondary_flow[0], secondary_flow[1])
					flow_totals[flow_key] = flow_totals.get(flow_key, Decimal("0")) + parsed_quantity

	return flow_totals


def get_linked_rcids_for_dashboard(certificate) -> list[str]:
	linked_rcids = dedupe_dashboard_identifiers([str(value).strip() for value in list(certificate.linked_rcids or []) if str(value).strip()])

	if linked_rcids:
		return linked_rcids

	return dedupe_dashboard_identifiers([value.strip() for value in str(certificate.rcid or "").split(",") if value.strip()])


def get_linked_rnids_for_dashboard(reception_certificate) -> list[str]:
	linked_rnids = dedupe_dashboard_identifiers([str(value).strip() for value in list(reception_certificate.linked_rnids or []) if str(value).strip()])

	if linked_rnids:
		return linked_rnids

	return dedupe_dashboard_identifiers([value.strip() for value in str(reception_certificate.rnid or "").split(",") if value.strip()])


def build_secondary_loop_context(certificate) -> dict[str, object]:
	secondary_ecosystem_details = getattr(certificate, "secondary_ecosystem_details", {}) or {}
	shared_value = secondary_ecosystem_details.get("shared") or {}
	shared_secondary_flow = build_secondary_flow_value(
		str(shared_value.get("secondaryProduct", "") or ""),
		str(shared_value.get("secondaryLoop", "") or ""),
	)

	if shared_secondary_flow is None:
		shared_secondary_flow = build_secondary_flow_value(
			str(getattr(certificate, "secondary_product", "") or ""),
			str(getattr(certificate, "secondary_loop", "") or ""),
		)

	by_rc: dict[str, tuple[str, str]] = {}
	by_rn: dict[tuple[str, str], tuple[str, str]] = {}
	by_rnid: dict[str, tuple[str, str]] = {}

	for entry in list(secondary_ecosystem_details.get("entries") or []):
		secondary_flow = build_secondary_flow_value(
			str(entry.get("secondaryProduct", "") or ""),
			str(entry.get("secondaryLoop", "") or ""),
		)

		if secondary_flow is None:
			continue

		rcid = str(entry.get("rcid", "") or "").strip()
		rnid = str(entry.get("rnid", "") or "").strip()

		if rcid and rnid:
			by_rn[(rcid, rnid)] = secondary_flow
		elif rnid:
			by_rnid[rnid] = secondary_flow
		elif rcid:
			by_rc[rcid] = secondary_flow

	return {
		"shared": shared_secondary_flow,
		"by_rc": by_rc,
		"by_rn": by_rn,
		"by_rnid": by_rnid,
	}


def resolve_secondary_loop_bucket(secondary_loop_context: dict[str, object], rcid: str, rnid: str) -> tuple[str, str] | None:
	by_rn = secondary_loop_context.get("by_rn")

	if isinstance(by_rn, dict):
		resolved_value = by_rn.get((rcid, rnid))

		if is_secondary_flow_value(resolved_value):
			return resolved_value

	by_rnid = secondary_loop_context.get("by_rnid")

	if isinstance(by_rnid, dict):
		resolved_value = by_rnid.get(rnid)

		if is_secondary_flow_value(resolved_value):
			return resolved_value

	by_rc = secondary_loop_context.get("by_rc")

	if isinstance(by_rc, dict):
		resolved_value = by_rc.get(rcid)

		if is_secondary_flow_value(resolved_value):
			return resolved_value

	shared_value = secondary_loop_context.get("shared")

	if is_secondary_flow_value(shared_value):
		return shared_value

	return None


def normalize_waste_class(waste_class: str) -> str:
	normalized_value = waste_class.strip().lower().replace("-", " ")

	if normalized_value == "hazardous":
		return "hazardous"

	return "non_hazardous"


def get_reception_note_stream_quantities(reception_note) -> list[tuple[str, Decimal]]:
	stream_quantities: list[tuple[str, Decimal]] = []
	waste_streams = list(reception_note.waste_streams or [])

	if waste_streams:
		for waste_stream in waste_streams:
			quantity_value, quantity_unit = split_quantity_and_unit(
				str(waste_stream.get("quantity", "") or ""),
				str(waste_stream.get("quantityUnit", "") or ""),
			)
			parsed_quantity = parse_decimal_quantity(quantity_value)

			if parsed_quantity is None:
				continue

			stream_quantities.append((
				normalize_waste_stream_name(str(waste_stream.get("name", "") or "")),
				convert_quantity_to_kgs(parsed_quantity, quantity_unit),
			))

		return stream_quantities

	fallback_quantity, fallback_quantity_unit = split_quantity_and_unit(str(reception_note.waste_stream_quantity or ""))
	parsed_quantity = parse_decimal_quantity(fallback_quantity)

	if parsed_quantity is None:
		return []

	return [(
		normalize_waste_stream_name(str(reception_note.waste_stream_name or "")),
		convert_quantity_to_kgs(parsed_quantity, fallback_quantity_unit),
	)]


def get_reception_note_trend_entries(reception_note) -> list[tuple[str, str, Decimal]]:
	trend_entries: list[tuple[str, str, Decimal]] = []
	waste_streams = list(getattr(reception_note, "waste_streams", []) or [])

	for waste_stream in waste_streams:
		reception_date = parse_supported_date(str(waste_stream.get("receptionDate", "") or ""))

		if reception_date is None:
			continue

		quantity_value, quantity_unit = split_quantity_and_unit(
			str(waste_stream.get("quantity", "") or ""),
			str(waste_stream.get("quantityUnit", "") or ""),
		)
		parsed_quantity = parse_decimal_quantity(quantity_value)

		if parsed_quantity is None:
			continue

		trend_entries.append((
			reception_date.strftime("%b"),
			normalize_waste_stream_name(str(waste_stream.get("name", "") or "")),
			convert_quantity_to_kgs(parsed_quantity, quantity_unit),
		))

	return trend_entries


def get_reception_note_monthly_quantity_entries(reception_note) -> list[tuple[str, Decimal]]:
	monthly_entries: list[tuple[str, Decimal]] = []
	waste_streams = list(getattr(reception_note, "waste_streams", []) or [])

	for waste_stream in waste_streams:
		reception_date = parse_supported_date(str(waste_stream.get("receptionDate", "") or ""))

		if reception_date is None:
			continue

		quantity_value, quantity_unit = split_quantity_and_unit(
			str(waste_stream.get("quantity", "") or ""),
			str(waste_stream.get("quantityUnit", "") or ""),
		)
		parsed_quantity = parse_decimal_quantity(quantity_value)

		if parsed_quantity is None:
			continue

		monthly_entries.append((
			reception_date.strftime("%b"),
			convert_quantity_to_kgs(parsed_quantity, quantity_unit),
		))

	return monthly_entries


def get_reception_note_collection_entries(reception_note) -> list[tuple[str, str, Decimal, tuple[float, float]]]:
	location_quantities: list[tuple[str, str, Decimal, tuple[float, float]]] = []
	waste_streams = list(reception_note.waste_streams or [])

	if waste_streams:
		for waste_stream in waste_streams:
			collection_emirate = str(waste_stream.get("collectionEmirate", "") or "")
			collection_location = str(waste_stream.get("collectionLocation", "") or "")
			quantity_value, quantity_unit = split_quantity_and_unit(
				str(waste_stream.get("quantity", "") or ""),
				str(waste_stream.get("quantityUnit", "") or ""),
			)
			parsed_quantity = parse_decimal_quantity(quantity_value)

			if parsed_quantity is None:
				continue

			coordinates = resolve_collection_source_location(collection_emirate, collection_location)

			if coordinates is None:
				continue

			display_emirate = normalize_collection_emirate_display(collection_emirate)
			display_location = normalize_collection_location_name(collection_location)

			if not display_emirate:
				display_emirate = infer_collection_emirate_from_location(collection_location)

			if not display_emirate:
				continue

			if not display_location:
				display_location = display_emirate

			location_quantities.append((
				display_emirate,
				display_location,
				convert_quantity_to_kgs(parsed_quantity, quantity_unit),
				coordinates,
			))

	return location_quantities


def sum_reception_note_quantity(reception_note) -> Decimal:
	return sum((quantity for _, quantity in get_reception_note_stream_quantities(reception_note)), Decimal("0"))


def normalize_waste_stream_name(waste_stream_name: str) -> str:
	normalized_value = waste_stream_name.strip()
	return normalized_value or "Unspecified"


def normalize_collection_location_name(location_name: str) -> str:
	return location_name.strip()


def normalize_collection_emirate_display(emirate_name: str) -> str:
	canonical_label = normalize_collection_emirate_name(emirate_name)

	if canonical_label:
		return canonical_label

	return emirate_name.strip()


def normalize_collection_emirate_name(emirate_name: str) -> str:
	normalized_value = emirate_name.strip().lower()

	for label, _, tokens in UAE_EMIRATE_MARKERS:
		if normalized_value and any(token in normalized_value for token in tokens):
			return label

	return ""


def infer_collection_emirate_from_location(collection_location: str) -> str:
	normalized_location = normalize_collection_location_name(collection_location).lower()

	if not normalized_location:
		return ""

	for emirate_label, _, tokens, _ in UAE_COLLECTION_SOURCE_MARKERS:
		if any(token in normalized_location for token in tokens):
			return emirate_label

	return ""


def resolve_collection_source_location(collection_emirate: str, collection_location: str) -> tuple[float, float] | None:
	normalized_emirate = normalize_collection_emirate_name(collection_emirate)
	normalized_location = normalize_collection_location_name(collection_location).lower()

	if normalized_location:
		for emirate_label, location_label, tokens, coordinates in UAE_COLLECTION_SOURCE_MARKERS:
			if normalized_emirate and emirate_label != normalized_emirate:
				continue

			if any(token in normalized_location for token in tokens):
				return coordinates

	if normalized_emirate:
		coordinates = get_collection_source_coordinates(normalized_emirate)

		if coordinates is not None:
			return coordinates

	if normalized_location:
		for emirate_label, location_label, tokens, coordinates in UAE_COLLECTION_SOURCE_MARKERS:
			if any(token in normalized_location for token in tokens):
				return coordinates

	return None


def build_secondary_flow_value(secondary_product_value: str, secondary_loop_value: str) -> tuple[str, str] | None:
	secondary_product = normalize_secondary_product_bucket(secondary_product_value)
	secondary_loop = normalize_secondary_loop_label(secondary_loop_value)

	if secondary_product is None or secondary_loop is None:
		return None

	return secondary_product, secondary_loop


def is_secondary_flow_value(value: object) -> bool:
	return isinstance(value, tuple) and len(value) == 2 and all(isinstance(item, str) and bool(item) for item in value)


def normalize_secondary_product_bucket(value: str) -> str | None:
	normalized_value = value.strip().lower()

	if not normalized_value:
		return None

	has_material = "material" in normalized_value
	has_energy = "energy" in normalized_value

	if has_material and not has_energy:
		return "Materials"

	if has_energy and not has_material:
		return "Energy"

	return None


def normalize_secondary_loop_label(value: str) -> str | None:
	normalized_value = value.strip().lower()

	if not normalized_value:
		return None

	if "manufacturer" in normalized_value:
		return "Manufacturer"

	if "trader" in normalized_value:
		return "Trader"

	return value.strip().title()


def get_collection_source_coordinates(location_name: str) -> tuple[float, float] | None:
	normalized_value = location_name.strip().lower()

	if not normalized_value:
		return None

	for label, coordinates, tokens in UAE_EMIRATE_MARKERS:
		if normalized_value == label.lower() or any(token in normalized_value for token in tokens):
			return coordinates

	for _, _, tokens, coordinates in UAE_COLLECTION_SOURCE_MARKERS:
		if any(token in normalized_value for token in tokens):
			return coordinates

	return None


def parse_month_key(month_key: str) -> int:
	return datetime.strptime(month_key, "%b").month


def decimal_to_number(value: Decimal) -> int | float:
	if value == value.to_integral():
		return int(value)

	return float(value)


UAE_EMIRATE_MARKERS: list[tuple[str, tuple[float, float], tuple[str, ...]]] = [
	("Dubai", (25.2048, 55.2708), ("dubai",)),
	("Abu Dhabi", (24.4539, 54.3773), ("abu dhabi", "abudhabi")),
	("Sharjah", (25.3463, 55.4209), ("sharjah",)),
	("Ajman", (25.4052, 55.5136), ("ajman",)),
	("Umm Al Quwain", (25.5647, 55.5552), ("umm al quwain", "uaq")),
	("Ras Al Khaimah", (25.8007, 55.9762), ("ras al khaimah", "rak")),
	("Fujairah", (25.1288, 56.3265), ("fujairah",)),
]

UAE_COLLECTION_SOURCE_MARKERS: list[tuple[str, str, tuple[str, ...], tuple[float, float]]] = [
	("Dubai", "Jafza", ("jafza", "jebel ali free zone", "jebel ali"), (24.9857, 55.0658)),
	("Dubai", "Dubai Industrial City", ("dubai industrial city",), (24.9667, 55.3860)),
	("Dubai", "Dubai Investment Park", ("dubai investment park", "dip"), (24.9853, 55.1590)),
	("Dubai", "Al Quoz", ("al quoz",), (25.1362, 55.2270)),
	("Abu Dhabi", "Mussafah", ("mussafah",), (24.3500, 54.5200)),
	("Abu Dhabi", "Khalifa Industrial", ("kizad", "khalifa industrial zone", "khalifa industrial"), (24.8222, 54.6622)),
	("Sharjah", "Sharjah Industrial Area", ("sharjah industrial area", "industrial area"), (25.3250, 55.4300)),
	("Sharjah", "Hamriyah", ("hamriyah free zone", "hamriyah"), (25.4875, 55.5303)),
	("Fujairah", "Dibba", ("dibba",), (25.6196, 56.2729)),
]


CUSTOMER_REPORT_CSV_COLUMNS = [
	"RNID Date",
	"RNID",
	"RCID Date",
	"RCID",
	"CCID Date",
	"CCID",
	"Waste Stream Name",
	"Quantity",
	"Quantity Unit",
	"Reception Date",
	"Waste Reception Facilities",
	"Secondary Product",
	"Secondary Loop",
	"Landfill Diversion",
]


ENVIRONMENTAL_IMPACT_FACTORS: dict[str, Decimal] = {
	"materials_co2": Decimal("1.85"),
	"energy_co2": Decimal("1.2"),
	"materials_ghg": Decimal("2.1"),
	"energy_ghg": Decimal("1.35"),
	"tree_co2_offset": Decimal("21.77"),
	"home_energy_equivalent": Decimal("900"),
}
