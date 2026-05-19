import pytest

from app.services.pdf_generation_service import PDF_SHARED_STYLESHEET, PdfGenerationService, generate_pdf


def build_reception_note_pdf_context() -> dict[str, str]:
	return {
		"rnid_date": "2026-04-13",
		"rnid": "RNID-0001-0001",
		"customer_id": "CID-0001",
		"total_quantity": "1200",
		"customer_name": "Acme Recycling LLC",
		"producing_company_emirate": "Dubai",
		"producing_company_office_address": "Warehouse 12, Industrial Area, Dubai",
		"producing_company_contact_person": "Maya Patel",
		"producing_company_office_phone": "+971 4 123 4567",
		"producing_company_email": "maya.patel@example.com",
		"transporting_company_name": "Green Transport Co.",
		"transporting_company_contact_person": "Omar Khan",
		"transporting_company_office_phone": "+971 4 555 1212",
		"transporting_company_email": "dispatch@greentransport.example",
		"vehicle_number": "DXB-48291",
		"driver_name": "Rahul Singh",
		"waste_stream_code": "WS-001",
		"waste_stream_name": "Mixed Plastic",
		"waste_stream_class": "Non-Hazardous",
		"waste_stream_physical_state": "Solid",
		"waste_stream_quantity": "1200",
		"waste_stream_quantity_unit": "kg",
		"waste_stream_collection_emirate": "Dubai",
		"waste_stream_collection_location": "Al Quoz",
		"waste_stream_reception_date": "2026-04-13",
		"issued_by": "Greenshare Operations",
	}


def build_reception_certificate_multi_pdf_context() -> dict[str, object]:
	return {
		"rcid_date": "2026-04-14",
		"rcid": "RCID-0001-0001",
		"customer_id": "CID-0001",
		"total_quantity": "1225",
		"linked_rnids": "RNID-0001-0001, RNID-0001-0002",
		"has_multiple_linked_entries": True,
		"linked_entries": [
			{
				"rnid": "RNID-0001-0001",
				"transporting_company": {
					"name": "Green Transport Co.",
					"contact_person": "Omar Khan",
					"office_phone": "+971 4 555 1212",
					"email": "dispatch@greentransport.example",
				},
				"vehicle_details": {
					"vehicle_plate_no": "DXB-48291",
					"driver_name": "Rahul Singh",
				},
				"waste_streams": [
					{
						"code": "WS-001",
						"name": "Mixed Plastic",
						"waste_class": "Non-Hazardous",
						"physical_state": "Solid",
						"quantity": "1200",
						"quantity_unit": "kg",
						"collection_emirate": "Dubai",
						"collection_location": "Al Quoz",
						"reception_date": "2026-04-13",
					}
				],
			},
			{
				"rnid": "RNID-0001-0002",
				"transporting_company": {
					"name": "Eco Haulers Ltd.",
					"contact_person": "Sara Noor",
					"office_phone": "+971 4 555 3434",
					"email": "ops@ecohaulers.example",
				},
				"vehicle_details": {
					"vehicle_plate_no": "DXB-11772",
					"driver_name": "Faisal Ahmed",
				},
				"waste_streams": [
					{
						"code": "WS-009",
						"name": "Metal Scrap",
						"waste_class": "Recyclable",
						"physical_state": "Solid",
						"quantity": "25",
						"quantity_unit": "kg",
						"collection_emirate": "Dubai",
						"collection_location": "Jebel Ali",
						"reception_date": "2026-04-14",
					}
				],
			},
		],
		"producing_company_name": "Acme Recycling LLC",
		"producing_company_emirate": "Dubai",
		"producing_company_office_address": "Warehouse 12, Industrial Area, Dubai",
		"producing_company_contact_person": "Maya Patel",
		"producing_company_office_phone": "+971 4 123 4567",
		"producing_company_email": "maya.patel@example.com",
		"facilities_name": "Zero Waste - Circular Processing Facilities",
		"issued_by": "Greenshare Operations",
		"verified_by": "Imran Gill",
		"verified_by_position": "CEO",
	}


def build_circularity_certificate_multi_pdf_context() -> dict[str, object]:
	return {
		"ccid_date": "2026-04-15",
		"ccid": "CCID-0001-0001",
		"customer_id": "CID-0001",
		"total_quantity": "1525",
		"linked_rcids": "RCID-0001-0001, RCID-0001-0002",
		"has_multiple_linked_entries": True,
		"has_expanded_linked_entries": True,
		"linked_entries": [
			{
				"rcid": "RCID-0001-0001",
				"secondary_product": "Material",
				"secondary_loop": "Manufacturer",
				"secondary_ecosystem": {
					"secondary_product": "Material",
					"secondary_loop": "Manufacturer",
				},
				"linked_rnids_count": 2,
				"has_multiple_linked_notes": True,
				"linked_notes": [
					{
						"rnid": "RNID-0001-0001",
						"secondary_ecosystem": {
							"secondary_product": "",
							"secondary_loop": "",
						},
						"transporting_company": {
							"name": "Green Transport Co.",
							"contact_person": "Omar Khan",
							"office_phone": "+971 4 555 1212",
							"email": "dispatch@greentransport.example",
						},
						"vehicle_details": {
							"vehicle_plate_no": "DXB-48291",
							"driver_name": "Rahul Singh",
						},
						"waste_streams": [
							{
								"code": "WS-001",
								"name": "Mixed Plastic",
								"waste_class": "Non-Hazardous",
								"physical_state": "Solid",
								"quantity": "1200",
								"quantity_unit": "kg",
								"collection_emirate": "Dubai",
								"collection_location": "Al Quoz",
								"reception_date": "2026-04-13",
							}
						],
					},
					{
						"rnid": "RNID-0001-0003",
						"secondary_ecosystem": {
							"secondary_product": "",
							"secondary_loop": "",
						},
						"transporting_company": {
							"name": "Blue Route Logistics",
							"contact_person": "Hassan Ali",
							"office_phone": "+971 4 555 9898",
							"email": "control@blueroute.example",
						},
						"vehicle_details": {
							"vehicle_plate_no": "DXB-88301",
							"driver_name": "Nadia Yusuf",
						},
						"waste_streams": [
							{
								"code": "WS-014",
								"name": "Rigid Plastic",
								"waste_class": "Recyclable",
								"physical_state": "Solid",
								"quantity": "300",
								"quantity_unit": "kg",
								"collection_emirate": "Dubai",
								"collection_location": "Dubai South",
								"reception_date": "2026-04-14",
							}
						],
					},
				],
				"transporting_company": {
					"name": "Green Transport Co.",
					"contact_person": "Omar Khan",
					"office_phone": "+971 4 555 1212",
					"email": "dispatch@greentransport.example",
				},
				"vehicle_details": {
					"vehicle_plate_no": "DXB-48291",
					"driver_name": "Rahul Singh",
				},
				"waste_streams": [
					{
						"code": "WS-001",
						"name": "Mixed Plastic",
						"waste_class": "Non-Hazardous",
						"physical_state": "Solid",
						"quantity": "1200",
						"quantity_unit": "kg",
						"collection_emirate": "Dubai",
						"collection_location": "Al Quoz",
						"reception_date": "2026-04-13",
					}
				],
			},
			{
				"rcid": "RCID-0001-0002",
				"secondary_product": "Energy",
				"secondary_loop": "Trader",
				"secondary_ecosystem": {
					"secondary_product": "Energy",
					"secondary_loop": "Trader",
				},
				"linked_rnids_count": 1,
				"has_multiple_linked_notes": False,
				"linked_notes": [
					{
						"rnid": "RNID-0001-0002",
						"secondary_ecosystem": {
							"secondary_product": "",
							"secondary_loop": "",
						},
						"transporting_company": {
							"name": "Eco Haulers Ltd.",
							"contact_person": "Sara Noor",
							"office_phone": "+971 4 555 3434",
							"email": "ops@ecohaulers.example",
						},
						"vehicle_details": {
							"vehicle_plate_no": "DXB-11772",
							"driver_name": "Faisal Ahmed",
						},
						"waste_streams": [
							{
								"code": "WS-009",
								"name": "Metal Scrap",
								"waste_class": "Recyclable",
								"physical_state": "Solid",
								"quantity": "25",
								"quantity_unit": "kg",
								"collection_emirate": "Dubai",
								"collection_location": "Jebel Ali",
								"reception_date": "2026-04-14",
							}
						],
					},
				],
				"transporting_company": {
					"name": "Eco Haulers Ltd.",
					"contact_person": "Sara Noor",
					"office_phone": "+971 4 555 3434",
					"email": "ops@ecohaulers.example",
				},
				"vehicle_details": {
					"vehicle_plate_no": "DXB-11772",
					"driver_name": "Faisal Ahmed",
				},
				"waste_streams": [
					{
						"code": "WS-009",
						"name": "Metal Scrap",
						"waste_class": "Recyclable",
						"physical_state": "Solid",
						"quantity": "25",
						"quantity_unit": "kg",
						"collection_location": "Jebel Ali",
						"reception_date": "2026-04-14",
					}
				],
			},
		],
		"producing_company_name": "Acme Recycling LLC",
		"producing_company_emirate": "Dubai",
		"producing_company_office_address": "Warehouse 12, Industrial Area, Dubai",
		"producing_company_contact_person": "Maya Patel",
		"producing_company_office_phone": "+971 4 123 4567",
		"producing_company_email": "maya.patel@example.com",
		"transporting_company_name": "Green Transport Co.",
		"transporting_company_contact_person": "Omar Khan",
		"transporting_company_office_phone": "+971 4 555 1212",
		"transporting_company_email": "dispatch@greentransport.example",
		"vehicle_plate_no": "DXB-48291",
		"driver_name": "Rahul Singh",
		"waste_stream_code": "WS-001",
		"waste_stream_name": "Mixed Plastic",
		"waste_stream_class": "Non-Hazardous",
		"waste_stream_physical_state": "Solid",
		"waste_stream_quantity": "1200",
		"waste_stream_quantity_unit": "kg",
		"waste_stream_collection_location": "Al Quoz",
		"waste_stream_reception_date": "2026-04-13",
		"facilities_name": "Zero Waste - Circular Processing Facilities",
		"secondary_ecosystem_mode": "by_rc",
		"show_shared_secondary_ecosystem_section": False,
		"secondary_ecosystem": {
			"secondary_product": "",
			"secondary_loop": "",
		},
		"secondary_product": "Recycled Pellets",
		"secondary_loop": "Closed Loop",
		"issued_by": "Greenshare Circularity Team",
		"verified_by": "Imran Gill",
		"verified_by_position": "CEO",
	}



def test_prepare_html_document_uses_absolute_stylesheet_and_asset_paths() -> None:
	service = PdfGenerationService()
	template_name = service._normalize_template_name("pdf/reception_note.html")
	template_path = service._get_template_path(template_name)
	rendered_html = service.render_template(template_name, build_reception_note_pdf_context())
	prepared_html = service._prepare_html_document(rendered_html, template_path)

	assert f'<base href="{template_path.parent.as_uri()}/" />' in prepared_html
	assert f'href="{PDF_SHARED_STYLESHEET.resolve().as_uri()}"' in prepared_html
	assert "src=\"file:///" in prepared_html
	assert "greensharelogo.png" in prepared_html


def test_generate_reception_note_pdf_returns_pdf_bytes() -> None:
	pdf_bytes = generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())

	assert isinstance(pdf_bytes, bytes)
	assert pdf_bytes.startswith(b"%PDF")
	assert len(pdf_bytes) > 1_000


def test_render_reception_note_template_supports_total_quantity() -> None:
	service = PdfGenerationService()
	rendered_html = service.render_template("pdf/reception_note.html", build_reception_note_pdf_context())

	assert "Total Quantity" in rendered_html
	assert "1200" in rendered_html


def test_render_reception_certificate_template_supports_multi_linked_entries() -> None:
	service = PdfGenerationService()
	rendered_html = service.render_template("pdf/reception_certificate.html", build_reception_certificate_multi_pdf_context())

	assert "Linked Reception Notes" in rendered_html
	assert "Total Quantity" in rendered_html
	assert "Linked Reception Note 1" in rendered_html
	assert "Linked Reception Note 2" in rendered_html
	assert "RNID-0001-0002" in rendered_html
	assert "Eco Haulers Ltd." in rendered_html
	assert "Metal Scrap" in rendered_html


def test_render_circularity_certificate_template_supports_multi_linked_entries() -> None:
	service = PdfGenerationService()
	rendered_html = service.render_template("pdf/circularity_certificate.html", build_circularity_certificate_multi_pdf_context())

	assert "Linked Reception Certificates" in rendered_html
	assert "Total Quantity" in rendered_html
	assert "Linked Reception Certificate 1" in rendered_html
	assert "Linked Reception Certificate 2" in rendered_html
	assert "Linked Reception Notes" in rendered_html
	assert "Reception Note 1" in rendered_html
	assert "Reception Note 2" in rendered_html
	assert "RNID-0001-0003" in rendered_html
	assert "RCID-0001-0002" in rendered_html
	assert "Eco Haulers Ltd." in rendered_html
	assert "Metal Scrap" in rendered_html
	assert "Material" in rendered_html
	assert "Energy" in rendered_html


def test_pdf_generation_raises_on_playwright_launch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
	def failing_sync_playwright():
		raise RuntimeError("Playwright: Chromium executable does not exist at the given path.")

	monkeypatch.setattr("app.services.pdf_generation_service.sync_playwright", failing_sync_playwright)
	service = PdfGenerationService()

	with pytest.raises(RuntimeError, match="Failed to generate PDF"):
		service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())