from datetime import datetime

from app.models.circularity_certificate import CircularityCertificate
from app.models.reception_certificate import ReceptionCertificate
from app.models.reception_note import ReceptionNote
from app.services import circularity_certificate_service, reception_certificate_service, reception_note_service


def test_build_reception_note_pdf_context_splits_combined_quantity_and_unit() -> None:
	reception_note = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="100 Tons",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = reception_note_service.build_reception_note_pdf_context(reception_note)

	assert context["total_quantity"] == "100"
	assert context["waste_stream_quantity"] == "100"
	assert context["waste_stream_quantity_unit"] == "Tons"


def test_build_reception_certificate_pdf_context_uses_primary_linked_reception_note() -> None:
	reception_note = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="999",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_certificate = ReceptionCertificate(
		id=9,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = reception_certificate_service.build_reception_certificate_pdf_context(reception_certificate, [reception_note])

	assert context["rcid"] == "RCID-0001-0001"
	assert context["linked_rnids"] == "RNID-0001-0001"
	assert context["total_quantity"] == "1200"
	assert context["has_multiple_linked_entries"] is False
	assert len(context["linked_entries"]) == 1
	assert context["linked_entries"][0]["rnid"] == "RNID-0001-0001"
	assert context["transporting_company_name"] == "Green Transport Co."
	assert context["waste_stream_code"] == "WS-001"
	assert context["waste_stream_quantity_unit"] == "kg"
	assert context["issued_by"] == "Greenshare Operations"
	assert context["verified_by"] == "Imran Gill"
	assert context["verified_by_position"] == "CEO"


def test_build_reception_certificate_pdf_context_creates_grouped_linked_entries() -> None:
	reception_note_one = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="999",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_two = ReceptionNote(
		id=8,
		rnid_date="2026-04-14",
		rnid="RNID-0001-0002",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Eco Haulers Ltd.",
		transporting_company_contact_person="Sara Noor",
		transporting_company_office_phone="+971 4 555 3434",
		transporting_company_email="ops@ecohaulers.example",
		waste_streams=[
			{
				"code": "WS-009",
				"name": "Metal Scrap",
				"wasteClass": "Recyclable",
				"physicalState": "Solid",
				"quantity": "25",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-14",
				"collectionLocation": "Jebel Ali",
			}
		],
		vehicle_plate_no="DXB-11772",
		driver_name="Faisal Ahmed",
		waste_stream_name="Metal Scrap",
		waste_stream_quantity="25 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_certificate = ReceptionCertificate(
		id=9,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001, RNID-0001-0002",
		linked_rnids=["RNID-0001-0001", "RNID-0001-0002"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = reception_certificate_service.build_reception_certificate_pdf_context(
		reception_certificate,
		[reception_note_one, reception_note_two],
	)

	assert context["has_multiple_linked_entries"] is True
	assert context["linked_rnids"] == "RNID-0001-0001, RNID-0001-0002"
	assert context["total_quantity"] == "1225"
	assert context["producing_company_name"] == "Acme Recycling LLC"
	assert len(context["linked_entries"]) == 2
	assert context["linked_entries"][0]["rnid"] == "RNID-0001-0001"
	assert context["linked_entries"][1]["transporting_company"]["name"] == "Eco Haulers Ltd."
	assert context["linked_entries"][1]["vehicle_details"]["vehicle_plate_no"] == "DXB-11772"
	assert context["linked_entries"][1]["waste_streams"][0]["quantity"] == "25"
	assert context["linked_entries"][1]["waste_streams"][0]["quantity_unit"] == "kg"


def test_build_circularity_certificate_pdf_context_uses_upstream_reception_note(monkeypatch) -> None:
	reception_certificate = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="999",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	def fake_get_reception_note_by_rnid(db, rnid: str):
		assert db == "db-session"
		assert rnid == "RNID-0001-0001"
		return reception_note

	monkeypatch.setattr(
		circularity_certificate_service.reception_note_repository,
		"get_reception_note_by_rnid",
		fake_get_reception_note_by_rnid,
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		"db-session",
		circularity_certificate,
		[reception_certificate],
	)

	assert context["ccid"] == "CCID-0001-0001"
	assert context["linked_rcids"] == "RCID-0001-0001"
	assert context["total_quantity"] == "1200"
	assert context["has_multiple_linked_entries"] is False
	assert context["has_expanded_linked_entries"] is False
	assert len(context["linked_entries"]) == 1
	assert context["linked_entries"][0]["rcid"] == "RCID-0001-0001"
	assert context["linked_entries"][0]["has_multiple_linked_notes"] is False
	assert context["producing_company_emirate"] == "Dubai"
	assert context["transporting_company_name"] == "Green Transport Co."
	assert context["waste_stream_code"] == "WS-001"
	assert context["secondary_ecosystem_mode"] == "shared"
	assert context["show_shared_secondary_ecosystem_section"] is True
	assert context["secondary_ecosystem"]["secondary_product"] == "Recycled Pellets"
	assert context["secondary_product"] == "Recycled Pellets"
	assert context["issued_by"] == "Greenshare Circularity Team"
	assert context["verified_by"] == "Imran Gill"
	assert context["verified_by_position"] == "CEO"


def test_build_circularity_certificate_pdf_context_falls_back_to_certificate_summary() -> None:
	reception_certificate = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="",
		linked_rnids=[],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="750 Tons",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Draft",
		created_at=datetime.now(),
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		None,
		circularity_certificate,
		[reception_certificate],
	)

	assert context["waste_stream_quantity"] == "1200"
	assert context["waste_stream_quantity_unit"] == "kg"
	assert context["waste_stream_code"] == ""
	assert context["total_quantity"] == "1200"
	assert context["status"] == "Draft"


def test_build_circularity_certificate_pdf_context_expands_linked_reception_notes_for_single_rc(monkeypatch) -> None:
	reception_certificate = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001, RNID-0001-0002",
		linked_rnids=["RNID-0001-0001", "RNID-0001-0002"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_one = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="1200 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_two = ReceptionNote(
		id=8,
		rnid_date="2026-04-14",
		rnid="RNID-0001-0002",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Eco Haulers Ltd.",
		transporting_company_contact_person="Sara Noor",
		transporting_company_office_phone="+971 4 555 3434",
		transporting_company_email="ops@ecohaulers.example",
		waste_streams=[
			{
				"code": "WS-009",
				"name": "Metal Scrap",
				"wasteClass": "Recyclable",
				"physicalState": "Solid",
				"quantity": "25",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-14",
				"collectionLocation": "Jebel Ali",
			}
		],
		vehicle_plate_no="DXB-11772",
		driver_name="Faisal Ahmed",
		waste_stream_name="Metal Scrap",
		waste_stream_quantity="25 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	def fake_get_reception_note_by_rnid(db, rnid: str):
		assert db == "db-session"
		return {
			"RNID-0001-0001": reception_note_one,
			"RNID-0001-0002": reception_note_two,
		}[rnid]

	monkeypatch.setattr(
		circularity_certificate_service.reception_note_repository,
		"get_reception_note_by_rnid",
		fake_get_reception_note_by_rnid,
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		"db-session",
		circularity_certificate,
		[reception_certificate],
	)

	assert context["has_multiple_linked_entries"] is False
	assert context["has_expanded_linked_entries"] is True
	assert context["total_quantity"] == "1225"
	assert context["secondary_ecosystem_mode"] == "shared"
	assert len(context["linked_entries"]) == 1
	assert context["linked_entries"][0]["has_multiple_linked_notes"] is True
	assert context["linked_entries"][0]["linked_rnids_count"] == 2
	assert len(context["linked_entries"][0]["linked_notes"]) == 2
	assert context["linked_entries"][0]["linked_notes"][0]["rnid"] == "RNID-0001-0001"
	assert context["linked_entries"][0]["linked_notes"][1]["transporting_company"]["name"] == "Eco Haulers Ltd."
	assert context["linked_entries"][0]["linked_notes"][1]["vehicle_details"]["driver_name"] == "Faisal Ahmed"
	assert context["linked_entries"][0]["linked_notes"][1]["waste_streams"][0]["quantity"] == "25"
	assert context["linked_entries"][0]["linked_notes"][1]["waste_streams"][0]["quantity_unit"] == "kg"


def test_build_circularity_certificate_pdf_context_creates_grouped_linked_entries(monkeypatch) -> None:
	reception_certificate_one = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_certificate_two = ReceptionCertificate(
		id=12,
		rcid_date="2026-04-15",
		rcid="RCID-0001-0002",
		rnid="RNID-0001-0002",
		linked_rnids=["RNID-0001-0002"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="25 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001, RCID-0001-0002",
		linked_rcids=["RCID-0001-0001", "RCID-0001-0002"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		secondary_product="Recycled Pellets",
		secondary_loop="Closed Loop",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_one = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="999",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_two = ReceptionNote(
		id=8,
		rnid_date="2026-04-14",
		rnid="RNID-0001-0002",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Eco Haulers Ltd.",
		transporting_company_contact_person="Sara Noor",
		transporting_company_office_phone="+971 4 555 3434",
		transporting_company_email="ops@ecohaulers.example",
		waste_streams=[
			{
				"code": "WS-009",
				"name": "Metal Scrap",
				"wasteClass": "Recyclable",
				"physicalState": "Solid",
				"quantity": "25",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-14",
				"collectionLocation": "Jebel Ali",
			}
		],
		vehicle_plate_no="DXB-11772",
		driver_name="Faisal Ahmed",
		waste_stream_name="Metal Scrap",
		waste_stream_quantity="25 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	def fake_get_reception_note_by_rnid(db, rnid: str):
		assert db == "db-session"
		return {
			"RNID-0001-0001": reception_note_one,
			"RNID-0001-0002": reception_note_two,
		}[rnid]

	monkeypatch.setattr(
		circularity_certificate_service.reception_note_repository,
		"get_reception_note_by_rnid",
		fake_get_reception_note_by_rnid,
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		"db-session",
		circularity_certificate,
		[reception_certificate_one, reception_certificate_two],
	)

	assert context["has_multiple_linked_entries"] is True
	assert context["has_expanded_linked_entries"] is True
	assert context["linked_rcids"] == "RCID-0001-0001, RCID-0001-0002"
	assert context["total_quantity"] == "1225"
	assert len(context["linked_entries"]) == 2
	assert context["linked_entries"][0]["rcid"] == "RCID-0001-0001"
	assert context["linked_entries"][0]["linked_notes"][0]["rnid"] == "RNID-0001-0001"
	assert context["linked_entries"][0]["has_multiple_linked_notes"] is False
	assert context["linked_entries"][1]["transporting_company"]["name"] == "Eco Haulers Ltd."
	assert context["linked_entries"][1]["vehicle_details"]["driver_name"] == "Faisal Ahmed"
	assert context["linked_entries"][1]["waste_streams"][0]["quantity"] == "25"
	assert context["linked_entries"][1]["waste_streams"][0]["quantity_unit"] == "kg"


def test_build_circularity_certificate_pdf_context_assigns_secondary_ecosystem_per_rc() -> None:
	reception_certificate_one = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="",
		linked_rnids=[],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1200 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_certificate_two = ReceptionCertificate(
		id=12,
		rcid_date="2026-04-15",
		rcid="RCID-0001-0002",
		rnid="",
		linked_rnids=[],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="25 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001, RCID-0001-0002",
		linked_rcids=["RCID-0001-0001", "RCID-0001-0002"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		secondary_ecosystem_details={
			"mode": "by_rc",
			"shared": {"secondaryProduct": "", "secondaryLoop": ""},
			"entries": [
				{
					"rcid": "RCID-0001-0001",
					"secondaryProduct": "Material",
					"secondaryLoop": "Manufacturer",
				},
				{
					"rcid": "RCID-0001-0002",
					"secondaryProduct": "Energy",
					"secondaryLoop": "Trader",
				},
			],
		},
		secondary_product="Material, Energy",
		secondary_loop="Manufacturer, Trader",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		None,
		circularity_certificate,
		[reception_certificate_one, reception_certificate_two],
	)

	assert context["secondary_ecosystem_mode"] == "by_rc"
	assert context["show_shared_secondary_ecosystem_section"] is False
	assert context["linked_entries"][0]["secondary_product"] == "Material"
	assert context["linked_entries"][1]["secondary_loop"] == "Trader"
	assert context["linked_entries"][0]["secondary_ecosystem"]["secondary_product"] == "Material"
	assert context["linked_entries"][1]["secondary_ecosystem"]["secondary_loop"] == "Trader"


def test_build_circularity_certificate_pdf_context_assigns_secondary_ecosystem_per_rn(monkeypatch) -> None:
	reception_certificate = ReceptionCertificate(
		id=11,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001, RNID-0001-0002",
		linked_rnids=["RNID-0001-0001", "RNID-0001-0002"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	circularity_certificate = CircularityCertificate(
		id=13,
		ccid_date="2026-04-15",
		ccid="CCID-0001-0001",
		rcid="RCID-0001-0001",
		linked_rcids=["RCID-0001-0001"],
		cid="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="1225 kg",
		secondary_ecosystem_details={
			"mode": "by_rn",
			"shared": {"secondaryProduct": "", "secondaryLoop": ""},
			"entries": [
				{
					"rcid": "RCID-0001-0001",
					"rnid": "RNID-0001-0001",
					"secondaryProduct": "Material",
					"secondaryLoop": "Manufacturer",
				},
				{
					"rcid": "RCID-0001-0001",
					"rnid": "RNID-0001-0002",
					"secondaryProduct": "Energy",
					"secondaryLoop": "Trader",
				},
			],
		},
		secondary_product="Material, Energy",
		secondary_loop="Manufacturer, Trader",
		issued_by="Greenshare Circularity Team",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_one = ReceptionNote(
		id=7,
		rnid_date="2026-04-13",
		rnid="RNID-0001-0001",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Green Transport Co.",
		transporting_company_contact_person="Omar Khan",
		transporting_company_office_phone="+971 4 555 1212",
		transporting_company_email="dispatch@greentransport.example",
		waste_streams=[
			{
				"code": "WS-001",
				"name": "Mixed Plastic",
				"wasteClass": "Non-Hazardous",
				"physicalState": "Solid",
				"quantity": "1200",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-13",
				"collectionLocation": "Al Quoz",
			}
		],
		vehicle_plate_no="DXB-48291",
		driver_name="Rahul Singh",
		waste_stream_name="Fallback Name",
		waste_stream_quantity="1200 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)
	reception_note_two = ReceptionNote(
		id=8,
		rnid_date="2026-04-14",
		rnid="RNID-0001-0002",
		customer_id="CID-0001",
		weigh_bridge_slip_date="",
		weigh_bridge_bill_no="",
		producing_company_name="Acme Recycling LLC",
		producing_company_emirate="Dubai",
		producing_company_office_address="Warehouse 12, Industrial Area, Dubai",
		producing_company_contact_person="Maya Patel",
		producing_company_office_phone="+971 4 123 4567",
		producing_company_email="maya.patel@example.com",
		transporting_company_name="Eco Haulers Ltd.",
		transporting_company_contact_person="Sara Noor",
		transporting_company_office_phone="+971 4 555 3434",
		transporting_company_email="ops@ecohaulers.example",
		waste_streams=[
			{
				"code": "WS-009",
				"name": "Metal Scrap",
				"wasteClass": "Recyclable",
				"physicalState": "Solid",
				"quantity": "25",
				"quantityUnit": "kg",
				"receptionDate": "2026-04-14",
				"collectionLocation": "Jebel Ali",
			}
		],
		vehicle_plate_no="DXB-11772",
		driver_name="Faisal Ahmed",
		waste_stream_name="Metal Scrap",
		waste_stream_quantity="25 kg",
		rn_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	def fake_get_reception_note_by_rnid(db, rnid: str):
		return {
			"RNID-0001-0001": reception_note_one,
			"RNID-0001-0002": reception_note_two,
		}[rnid]

	monkeypatch.setattr(
		circularity_certificate_service.reception_note_repository,
		"get_reception_note_by_rnid",
		fake_get_reception_note_by_rnid,
	)

	context = circularity_certificate_service.build_circularity_certificate_pdf_context(
		"db-session",
		circularity_certificate,
		[reception_certificate],
	)

	assert context["secondary_ecosystem_mode"] == "by_rn"
	assert context["show_shared_secondary_ecosystem_section"] is False
	assert context["linked_entries"][0]["linked_notes"][0]["secondary_ecosystem"]["secondary_product"] == "Material"
	assert context["linked_entries"][0]["linked_notes"][1]["secondary_ecosystem"]["secondary_loop"] == "Trader"


def test_build_reception_certificate_pdf_context_splits_combined_quantity_and_unit() -> None:
	reception_certificate = ReceptionCertificate(
		id=9,
		rcid_date="2026-04-14",
		rcid="RCID-0001-0001",
		rnid="RNID-0001-0001",
		linked_rnids=["RNID-0001-0001"],
		customer_id="CID-0001",
		producing_company_name="Acme Recycling LLC",
		waste_stream_quantity="25 kg",
		rc_issued_by="Greenshare Operations",
		owner_identifier="EMP-001",
		owner_role="employee",
		status="Issued",
		created_at=datetime.now(),
	)

	context = reception_certificate_service.build_reception_certificate_pdf_context(reception_certificate, [])

	assert context["waste_stream_quantity"] == "25"
	assert context["waste_stream_quantity_unit"] == "kg"