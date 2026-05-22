from concurrent.futures import ThreadPoolExecutor
import logging
import time

import pytest

from app.services.pdf_generation_service import PDF_SHARED_STYLESHEET, PdfGenerationService, generate_pdf, pdf_generation_service


@pytest.fixture(autouse=True)
def cleanup_shared_pdf_browser() -> None:
	yield
	pdf_generation_service.close_shared_browser()


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


def test_pdf_generation_uses_azure_safe_launch_and_closes_browser(monkeypatch: pytest.MonkeyPatch) -> None:
	launch_calls: list[dict[str, object]] = []
	page_calls: dict[str, object] = {}
	close_events: list[str] = []
	browser_closed = False
	context_closed = False
	playwright_stopped = False
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			page_calls["html"] = html
			page_calls["wait_until"] = wait_until

		def pdf(self, format: str, print_background: bool) -> bytes:
			page_calls["format"] = format
			page_calls["print_background"] = print_background
			return b"%PDF-test-bytes"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			self.closed = True
			close_events.append("page")

	class FakeContext:
		def new_page(self) -> FakePage:
			return FakePage()

		def close(self) -> None:
			nonlocal context_closed
			context_closed = True
			close_events.append("context")

	class FakeBrowser:
		def new_context(self) -> FakeContext:
			return FakeContext()

		def close(self) -> None:
			nonlocal browser_closed
			browser_closed = True
			close_events.append("browser")

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			launch_calls.append(kwargs)
			return FakeBrowser()

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			nonlocal playwright_stopped
			playwright_stopped = True
			close_events.append("playwright")

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)

	service = PdfGenerationService()
	pdf_bytes = service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())
	service.close_shared_browser()

	assert pdf_bytes == b"%PDF-test-bytes"
	assert launch_calls == [
		{
			"headless": True,
			"executable_path": "/playwright/chromium/chrome",
			"args": [
				"--no-sandbox",
				"--disable-setuid-sandbox",
				"--disable-dev-shm-usage",
				"--disable-gpu",
			],
		}
	]
	assert page_calls["wait_until"] == "networkidle"
	assert page_calls["format"] == "A4"
	assert page_calls["print_background"] is True
	assert isinstance(page_calls["html"], str)
	assert context_closed is True
	assert browser_closed is True
	assert playwright_stopped is True
	assert close_events == ["page", "context", "browser", "playwright"]


def test_pdf_generation_reuses_shared_browser_between_requests(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
	launch_calls: list[dict[str, object]] = []
	page_close_count = 0
	context_close_count = 0
	browser_close_count = 0
	playwright_stop_count = 0
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			return None

		def pdf(self, format: str, print_background: bool) -> bytes:
			return b"%PDF-test-bytes"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			nonlocal page_close_count
			self.closed = True
			page_close_count += 1

	class FakeContext:
		def new_page(self) -> FakePage:
			return FakePage()

		def close(self) -> None:
			nonlocal context_close_count
			context_close_count += 1

	class FakeBrowser:
		def is_connected(self) -> bool:
			return True

		def new_context(self) -> FakeContext:
			return FakeContext()

		def close(self) -> None:
			nonlocal browser_close_count
			browser_close_count += 1

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			launch_calls.append(kwargs)
			return FakeBrowser()

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			nonlocal playwright_stop_count
			playwright_stop_count += 1

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)
	caplog.set_level(logging.INFO, logger="app.services.pdf_generation_service")

	service = PdfGenerationService()
	first_pdf = service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())
	second_pdf = service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())
	service.close_shared_browser()

	assert first_pdf == b"%PDF-test-bytes"
	assert second_pdf == b"%PDF-test-bytes"
	assert len(launch_calls) == 1
	assert page_close_count == 2
	assert context_close_count == 2
	assert browser_close_count == 1
	assert playwright_stop_count == 1
	assert any(getattr(record, "browser_reused", None) is True for record in caplog.records)
	assert all(getattr(record, "process_id", None) for record in caplog.records if record.name == "app.services.pdf_generation_service")


def test_pdf_generation_applies_concurrency_limiter_and_logs_wait(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
	launch_calls = 0
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")
	monkeypatch.setenv("PDF_MAX_CONCURRENT_PER_WORKER", "1")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			time.sleep(0.05)

		def pdf(self, format: str, print_background: bool) -> bytes:
			time.sleep(0.05)
			return b"%PDF-test-bytes"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			self.closed = True

	class FakeContext:
		def new_page(self) -> FakePage:
			return FakePage()

		def close(self) -> None:
			return None

	class FakeBrowser:
		def is_connected(self) -> bool:
			return True

		def new_context(self) -> FakeContext:
			return FakeContext()

		def close(self) -> None:
			return None

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			nonlocal launch_calls
			launch_calls += 1
			return FakeBrowser()

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			return None

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)
	caplog.set_level(logging.INFO, logger="app.services.pdf_generation_service")

	service = PdfGenerationService()
	with ThreadPoolExecutor(max_workers=2) as executor:
		results = list(
			executor.map(
				lambda _: service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context()),
				range(2),
			)
		)
	service.close_shared_browser()

	assert results == [b"%PDF-test-bytes", b"%PDF-test-bytes"]
	assert launch_calls == 1
	wait_values = [
		getattr(record, "limiter_wait_ms", None)
		for record in caplog.records
		if record.message == "pdf_render_slot_acquired"
	]
	assert len(wait_values) == 2
	assert max(value for value in wait_values if value is not None) > 0


def test_pdf_generation_warmup_launches_browser_once(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
	launch_calls = 0
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")

	class FakeBrowser:
		def is_connected(self) -> bool:
			return True

		def close(self) -> None:
			return None

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			nonlocal launch_calls
			launch_calls += 1
			return FakeBrowser()

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			return None

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)
	caplog.set_level(logging.INFO, logger="app.services.pdf_generation_service")

	service = PdfGenerationService()
	service.warm_up_browser()
	service.warm_up_browser()
	service.close_shared_browser()

	assert launch_calls == 1
	warmup_records = [record for record in caplog.records if record.getMessage() == "pdf_browser_warmup_completed"]
	assert len(warmup_records) == 2
	assert all(getattr(record, "browser_generation", None) == 1 for record in warmup_records)


def test_pdf_generation_recovers_by_relaunching_browser(monkeypatch: pytest.MonkeyPatch) -> None:
	launch_count = 0
	browser_close_count = 0
	playwright_stop_count = 0
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			return None

		def pdf(self, format: str, print_background: bool) -> bytes:
			return b"%PDF-recovered"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			self.closed = True

	class FakeContext:
		def new_page(self) -> FakePage:
			return FakePage()

		def close(self) -> None:
			return None

	class RecoveringBrowser:
		def __init__(self, should_fail: bool) -> None:
			self.should_fail = should_fail
			self.closed = False

		def is_connected(self) -> bool:
			return not self.closed and not self.should_fail

		def new_context(self) -> FakeContext:
			if self.should_fail:
				self.closed = True
				raise RuntimeError("Browser has been closed")
			return FakeContext()

		def close(self) -> None:
			nonlocal browser_close_count
			self.closed = True
			browser_close_count += 1

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> RecoveringBrowser:
			nonlocal launch_count
			launch_count += 1
			return RecoveringBrowser(should_fail=launch_count == 1)

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			nonlocal playwright_stop_count
			playwright_stop_count += 1

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)

	service = PdfGenerationService()
	pdf_bytes = service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context())
	service.close_shared_browser()

	assert pdf_bytes == b"%PDF-recovered"
	assert launch_count == 2
	assert browser_close_count >= 2
	assert playwright_stop_count >= 2


def test_pdf_generation_supports_repeated_concurrent_requests_with_shared_browser(monkeypatch: pytest.MonkeyPatch) -> None:
	launch_count = 0
	context_count = 0
	page_count = 0
	import threading

	counters_lock = threading.Lock()
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			return None

		def pdf(self, format: str, print_background: bool) -> bytes:
			return b"%PDF-concurrent"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			self.closed = True

	class FakeContext:
		def new_page(self) -> FakePage:
			nonlocal page_count
			with counters_lock:
				page_count += 1
			return FakePage()

		def close(self) -> None:
			return None

	class FakeBrowser:
		def is_connected(self) -> bool:
			return True

		def new_context(self) -> FakeContext:
			nonlocal context_count
			with counters_lock:
				context_count += 1
			return FakeContext()

		def close(self) -> None:
			return None

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			nonlocal launch_count
			with counters_lock:
				launch_count += 1
			return FakeBrowser()

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			return None

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)

	service = PdfGenerationService()

	with ThreadPoolExecutor(max_workers=4) as executor:
		results = list(
			executor.map(
				lambda _: service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context()),
				range(8),
			)
		)

	service.close_shared_browser()

	assert results == [b"%PDF-concurrent"] * 8
	assert launch_count == 1
	assert context_count == 8
	assert page_count == 8


def test_pdf_generation_reuses_shared_browser_on_dedicated_render_thread(monkeypatch: pytest.MonkeyPatch) -> None:
	launch_thread_ids: list[int] = []
	render_thread_ids: list[int] = []
	monkeypatch.setattr("app.services.pdf_generation_service.platform.system", lambda: "Linux")
	monkeypatch.setenv("PDF_MAX_CONCURRENT_PER_WORKER", "1")

	class FakePage:
		def __init__(self) -> None:
			self.closed = False

		def set_content(self, html: str, wait_until: str) -> None:
			return None

		def pdf(self, format: str, print_background: bool) -> bytes:
			return b"%PDF-thread-safe"

		def is_closed(self) -> bool:
			return self.closed

		def close(self) -> None:
			self.closed = True

	class FakeContext:
		def new_page(self) -> FakePage:
			return FakePage()

		def close(self) -> None:
			return None

	class FakeBrowser:
		def __init__(self, launch_thread_id: int) -> None:
			self.launch_thread_id = launch_thread_id

		def is_connected(self) -> bool:
			return True

		def new_context(self) -> FakeContext:
			current_thread_id = threading.get_ident()
			render_thread_ids.append(current_thread_id)
			assert current_thread_id == self.launch_thread_id
			return FakeContext()

		def close(self) -> None:
			return None

	class FakeChromium:
		executable_path = "/playwright/chromium/chrome"

		def launch(self, **kwargs: object) -> FakeBrowser:
			launch_thread_id = threading.get_ident()
			launch_thread_ids.append(launch_thread_id)
			return FakeBrowser(launch_thread_id)

	class FakePlaywright:
		chromium = FakeChromium()

		def stop(self) -> None:
			return None

	monkeypatch.setattr(
		"app.services.pdf_generation_service.sync_playwright",
		lambda: type("FakePlaywrightManager", (), {"start": staticmethod(lambda: FakePlaywright())})(),
	)

	service = PdfGenerationService()

	with ThreadPoolExecutor(max_workers=2) as executor:
		results = list(
			executor.map(
				lambda _: service.generate_pdf("pdf/reception_note.html", build_reception_note_pdf_context()),
				range(2),
			)
		)

	service.close_shared_browser()

	assert results == [b"%PDF-thread-safe", b"%PDF-thread-safe"]
	assert len(set(launch_thread_ids)) == 1
	assert set(render_thread_ids) == set(launch_thread_ids)


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