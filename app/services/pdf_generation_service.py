import atexit
import base64
from collections.abc import Mapping
from concurrent.futures import Future
from contextlib import nullcontext
from functools import lru_cache
import logging
import mimetypes
import os
import platform
from pathlib import Path
import queue
import re
import threading
import time
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape
from playwright.sync_api import sync_playwright


TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"
PDF_TEMPLATE_DIR = TEMPLATES_ROOT / "pdf"
PDF_SHARED_STYLESHEET = PDF_TEMPLATE_DIR / "styles.css"
PDF_STATIC_IMAGE_DIR = Path(__file__).resolve().parent.parent / "static" / "images"
PDF_IMAGE_ASSET_PATHS = {
	"greenshare_logo_src": "greensharelogo.png",
	"zero_waste_logo_src": "zerowastecolorlogo.png",
	"signature_stamp_src": "igsignaturezwstamp.png",
}
PDF_TEMPLATE_REQUIRED_IMAGE_ASSETS = {
	"reception_note.html": ("greenshare_logo_src", "zero_waste_logo_src"),
	"reception_certificate.html": (
		"greenshare_logo_src",
		"zero_waste_logo_src",
		"signature_stamp_src",
	),
	"circularity_certificate.html": (
		"greenshare_logo_src",
		"zero_waste_logo_src",
		"signature_stamp_src",
	),
}

logger = logging.getLogger(__name__)
PLAYWRIGHT_EXECUTABLE_ENV_VAR = "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"
PDF_MAX_CONCURRENT_PER_WORKER_ENV_VAR = "PDF_MAX_CONCURRENT_PER_WORKER"
PDF_TIMEOUT_RISK_MS_ENV_VAR = "PDF_TIMEOUT_RISK_MS"
PDF_CACHE_BUCKETS_BY_TEMPLATE = {
	"reception_note.html": "reception-notes",
	"reception_certificate.html": "reception-certificates",
	"circularity_certificate.html": "circularity-certificates",
}


@lru_cache(maxsize=1)
def load_css_content(stylesheet_path: Path) -> str:
	return stylesheet_path.read_text(encoding="utf-8")


@lru_cache(maxsize=len(PDF_IMAGE_ASSET_PATHS))
def load_image_as_base64(image_path: Path) -> str:
	mime_type, _ = mimetypes.guess_type(image_path.name)
	resolved_mime_type = mime_type or "application/octet-stream"
	encoded_bytes = base64.b64encode(image_path.read_bytes()).decode("ascii")
	return f"data:{resolved_mime_type};base64,{encoded_bytes}"


class PdfGenerationService:
	def __init__(
		self,
		templates_root: Path | None = None,
		shared_stylesheet: Path | None = None,
		static_image_dir: Path | None = None,
		environment: Environment | None = None,
	) -> None:
		self.templates_root = templates_root or TEMPLATES_ROOT
		self.template_dir = self.templates_root / "pdf"
		self.shared_stylesheet = shared_stylesheet or PDF_SHARED_STYLESHEET
		self.static_image_dir = static_image_dir or PDF_STATIC_IMAGE_DIR
		self.environment = environment or Environment(
			loader=FileSystemLoader(str(self.templates_root)),
			autoescape=select_autoescape(["html", "xml"]),
			undefined=StrictUndefined,
		)
		self._browser_lock = threading.RLock()
		self._shared_playwright: Any | None = None
		self._shared_browser: Any | None = None
		self._browser_generation = 0
		self._process_id = os.getpid()
		self._browser_thread: threading.Thread | None = None
		self._browser_thread_id: int | None = None
		self._browser_thread_ready = threading.Event()
		self._browser_task_queue: queue.Queue[tuple[Future[Any], Any | None]] = queue.Queue()
		self._pdf_timeout_risk_ms = self._read_positive_int_env(PDF_TIMEOUT_RISK_MS_ENV_VAR, 45_000)
		self._max_concurrent_renders = self._read_positive_int_env(PDF_MAX_CONCURRENT_PER_WORKER_ENV_VAR, 0)
		self._render_slots = (
			threading.BoundedSemaphore(self._max_concurrent_renders)
			if self._max_concurrent_renders > 0
			else None
		)

	def warm_up_browser(self) -> None:
		warmup_started_at = time.perf_counter()
		browser, acquisition_details = self._run_on_browser_thread(
			lambda: self._acquire_browser(template_name="worker_warmup")
		)
		logger.info(
			"pdf_browser_warmup_completed",
			extra={
				"process_id": self._process_id,
				"warmup_ms": round((time.perf_counter() - warmup_started_at) * 1000, 2),
				"browser_connected": self._is_browser_usable(browser),
				**acquisition_details,
			},
		)

	def generate_pdf(self, template_name: str, context: Mapping[str, Any]) -> bytes:
		request_started_at = time.perf_counter()
		template_filename = self._normalize_template_name(template_name)
		logger.info(
			"pdf_generation_requested",
			extra={
				"template_name": template_filename,
				"context_key_count": len(context),
				"process_id": self._process_id,
			},
		)
		logger.info(
			"pdf_cache_eligibility_assessed",
			extra=self._build_cache_eligibility_payload(template_filename),
		)
		template_path = self._get_template_path(template_filename)
		self._validate_assets(template_path)
		template_render_started_at = time.perf_counter()
		rendered_html = self.render_template(template_filename, context)
		template_render_ms = round((time.perf_counter() - template_render_started_at) * 1000, 2)
		html_prepare_started_at = time.perf_counter()
		prepared_html = self._prepare_html_document(rendered_html, template_path)
		html_prepare_ms = round((time.perf_counter() - html_prepare_started_at) * 1000, 2)
		return self._render_pdf_with_browser(
			prepared_html,
			template_path,
			request_started_at=request_started_at,
			template_render_ms=template_render_ms,
			html_prepare_ms=html_prepare_ms,
		)

	def render_template(self, template_name: str, context: Mapping[str, Any]) -> str:
		try:
			template = self.environment.get_template(template_name)
		except TemplateNotFound as exc:
			raise FileNotFoundError(f"PDF template '{template_name}' was not found.") from exc

		template_asset_context = self._build_template_asset_context(template_name)
		render_context = dict(context)
		render_context.update(template_asset_context)
		rendered_html = template.render(**render_context)
		logger.info(
			"template_render_completed",
			extra={
				"template_name": Path(template_name).name,
				"css_embedded": bool(template_asset_context["embedded_css"]),
				"logo_embedded": all(
					template_asset_context[asset_name].startswith("data:image/")
					for asset_name in ("greenshare_logo_src", "zero_waste_logo_src")
				),
				"process_id": self._process_id,
			},
		)
		return rendered_html

	def _normalize_template_name(self, template_name: str) -> str:
		normalized_template_name = template_name.strip().replace("\\", "/")

		if not normalized_template_name:
			raise ValueError("A PDF template name is required.")

		if not normalized_template_name.startswith("pdf/"):
			normalized_template_name = f"pdf/{normalized_template_name}"

		if not normalized_template_name.endswith(".html"):
			normalized_template_name = f"{normalized_template_name}.html"

		template_path = Path(normalized_template_name)
		if template_path.is_absolute() or ".." in template_path.parts:
			raise ValueError("PDF template names must resolve within the PDF templates directory.")

		return template_path.as_posix()

	def _get_template_path(self, template_name: str) -> Path:
		return (self.templates_root / template_name).resolve()

	def _validate_assets(self, template_path: Path) -> None:
		if not template_path.is_file():
			raise FileNotFoundError(f"PDF template was not found at '{template_path}'.")

		if not self.shared_stylesheet.is_file():
			raise FileNotFoundError(
				f"Shared PDF stylesheet was not found at '{self.shared_stylesheet}'."
			)

		for asset_name in self._required_image_assets(template_path.name):
			image_path = self.static_image_dir / PDF_IMAGE_ASSET_PATHS[asset_name]
			if not image_path.is_file():
				raise FileNotFoundError(f"PDF image asset was not found at '{image_path}'.")

	def _prepare_html_document(self, rendered_html: str, template_path: Path) -> str:
		prepared_html = self._inline_linked_stylesheets(rendered_html)
		prepared_html = self._embed_local_image_sources(prepared_html, template_path.parent, template_path.name)
		self._assert_self_contained_html(prepared_html, template_path.name)
		return prepared_html

	def _required_image_assets(self, template_name: str) -> tuple[str, ...]:
		return PDF_TEMPLATE_REQUIRED_IMAGE_ASSETS.get(template_name, ())

	def _build_template_asset_context(self, template_name: str) -> dict[str, str]:
		template_basename = Path(template_name).name
		try:
			asset_context = {
				"embedded_css": load_css_content(self.shared_stylesheet),
			}
			for asset_name in self._required_image_assets(template_basename):
				image_path = self.static_image_dir / PDF_IMAGE_ASSET_PATHS[asset_name]
				asset_context[asset_name] = load_image_as_base64(image_path)
			return asset_context
		except Exception as exc:
			self._log_asset_embed_failed(template_basename, exc)
			raise

	def _inline_linked_stylesheets(self, rendered_html: str) -> str:
		stylesheet_markup = f"<style>{load_css_content(self.shared_stylesheet)}</style>"
		return re.sub(
			r'<link[^>]+rel=["\']stylesheet["\'][^>]*>',
			stylesheet_markup,
			rendered_html,
			count=1,
			flags=re.IGNORECASE,
		)

	def _embed_local_image_sources(self, rendered_html: str, asset_base_dir: Path, template_name: str) -> str:
		def replace_source(match: re.Match[str]) -> str:
			prefix, source, suffix = match.groups()
			if source.startswith(("http://", "https://", "data:", "#")):
				return match.group(0)

			try:
				embedded_source = load_image_as_base64((asset_base_dir / source).resolve())
			except Exception as exc:
				self._log_asset_embed_failed(template_name, exc, source=source)
				raise

			return f"{prefix}{embedded_source}{suffix}"

		return re.sub(
			r'(<(?:img|source)[^>]+src=["\'])([^"\']+)(["\'][^>]*>)',
			replace_source,
			rendered_html,
			flags=re.IGNORECASE,
		)

	def _assert_self_contained_html(self, prepared_html: str, template_name: str) -> None:
		if re.search(r'<link[^>]+rel=["\']stylesheet["\']', prepared_html, flags=re.IGNORECASE):
			raise RuntimeError(
				f"Prepared PDF HTML for '{template_name}' still contains an external stylesheet reference."
			)

		if re.search(
			r'<(?:img|source)[^>]+src=["\'](?!https?://|data:|#)[^"\']+["\']',
			prepared_html,
			flags=re.IGNORECASE,
		):
			raise RuntimeError(
				f"Prepared PDF HTML for '{template_name}' still contains a non-embedded asset reference."
			)

	def _log_asset_embed_failed(self, template_name: str, exc: Exception, *, source: str | None = None) -> None:
		logger.exception(
			"asset_embed_failed",
			extra={
				"template_name": template_name,
				"asset_source": source or "service_asset_bundle",
				"error_type": type(exc).__name__,
				"process_id": self._process_id,
			},
		)

	def _render_pdf_with_browser(
		self,
		prepared_html: str,
		template_path: Path,
		*,
		request_started_at: float,
		template_render_ms: float,
		html_prepare_ms: float,
	) -> bytes:
		browser = None
		context = None
		page = None
		limiter_context = self._acquire_render_slot(template_name=template_path.name)
		with limiter_context as limiter_wait_ms:
			for attempt in range(2):
				acquisition_details = {
					"browser_reused": False,
					"browser_relaunched": False,
					"browser_generation": self._browser_generation,
				}

				try:
					render_result = self._run_on_browser_thread(
						lambda: self._render_pdf_job(template_path.name, prepared_html)
					)
					pdf_bytes = render_result["pdf_bytes"]
					browser_acquire_ms = render_result["browser_acquire_ms"]
					page_render_ms = render_result["page_render_ms"]
					pdf_generation_ms = render_result["pdf_generation_ms"]
					acquisition_details = render_result["acquisition_details"]
					total_request_ms = round((time.perf_counter() - request_started_at) * 1000, 2)

					completion_payload = {
						"template_name": template_path.name,
						"size_bytes": len(pdf_bytes),
						"template_render_ms": template_render_ms,
						"html_prepare_ms": html_prepare_ms,
						"limiter_wait_ms": limiter_wait_ms,
						"browser_acquire_ms": browser_acquire_ms,
						"page_render_ms": page_render_ms,
						"pdf_generation_ms": pdf_generation_ms,
						"total_request_ms": total_request_ms,
						"process_id": self._process_id,
						"timeout_risk": total_request_ms >= self._pdf_timeout_risk_ms,
						**acquisition_details,
					}
					logger.info("pdf_generation_succeeded", extra=completion_payload)
					logger.info("pdf_request_completed", extra=completion_payload)
					return pdf_bytes
				except Exception as exc:
					browser_acquire_ms = round((time.perf_counter() - request_started_at) * 1000, 2)
					failure_payload = {
						"template_name": template_path.name,
						"error_type": type(exc).__name__,
						"template_render_ms": template_render_ms,
						"html_prepare_ms": html_prepare_ms,
						"limiter_wait_ms": limiter_wait_ms,
						"browser_acquire_ms": browser_acquire_ms,
						"total_request_ms": round((time.perf_counter() - request_started_at) * 1000, 2),
						"process_id": self._process_id,
						**acquisition_details,
					}

					if attempt == 0 and self._should_retry_browser(exc):
						logger.warning(
							"pdf_browser_recovery_retry",
							extra={
								**failure_payload,
								"attempt": attempt + 1,
							},
						)
						self._run_on_browser_thread(
							lambda: self._invalidate_browser_locked(
								template_name=template_path.name,
								reason=f"{type(exc).__name__}:{exc}",
							)
						)
						continue

					logger.exception("pdf_generation_failed", extra=failure_payload)
					raise RuntimeError(
						f"Failed to generate PDF from template '{template_path.name}'. {exc}"
					) from exc

		raise RuntimeError(f"Failed to generate PDF from template '{template_path.name}'. Unknown browser error")

	def _render_pdf_job(self, template_name: str, prepared_html: str) -> dict[str, Any]:
		browser_acquire_started_at = time.perf_counter()
		browser, acquisition_details = self._acquire_browser(template_name)
		browser_acquire_ms = round((time.perf_counter() - browser_acquire_started_at) * 1000, 2)
		context = None
		page = None

		try:
			context = browser.new_context()
			page = context.new_page()

			page_render_started_at = time.perf_counter()
			page.set_content(prepared_html, wait_until="networkidle")
			page_render_ms = round((time.perf_counter() - page_render_started_at) * 1000, 2)

			pdf_generation_started_at = time.perf_counter()
			pdf_bytes = page.pdf(format="A4", print_background=True)
			pdf_generation_ms = round((time.perf_counter() - pdf_generation_started_at) * 1000, 2)
			return {
				"pdf_bytes": pdf_bytes,
				"browser_acquire_ms": browser_acquire_ms,
				"page_render_ms": page_render_ms,
				"pdf_generation_ms": pdf_generation_ms,
				"acquisition_details": acquisition_details,
			}
		finally:
			if page is not None:
				try:
					if not page.is_closed():
						page.close()
						logger.info(
							"pdf_page_closed",
							extra={
								"template_name": template_name,
								"process_id": self._process_id,
								"render_thread_id": self._browser_thread_id,
							},
						)
				except Exception:
					logger.exception("Failed to close Playwright page for template '%s'", template_name)

			if context is not None:
				try:
					context.close()
					logger.info(
						"pdf_browser_context_closed",
						extra={
							"template_name": template_name,
							"process_id": self._process_id,
							"render_thread_id": self._browser_thread_id,
						},
					)
				except Exception:
					logger.exception("Failed to close Playwright browser context for template '%s'", template_name)

	def _acquire_render_slot(self, template_name: str):
		if self._render_slots is None:
			return nullcontext(0.0)

		service = self

		class _RenderSlotContext:
			def __enter__(self) -> float:
				wait_started_at = time.perf_counter()
				service._render_slots.acquire()
				wait_ms = round((time.perf_counter() - wait_started_at) * 1000, 2)
				logger.info(
					"pdf_render_slot_acquired",
					extra={
						"template_name": template_name,
						"process_id": service._process_id,
						"limiter_wait_ms": wait_ms,
						"max_concurrent_per_worker": service._max_concurrent_renders,
					},
				)
				return wait_ms

			def __exit__(self, exc_type, exc, tb) -> None:
				service._render_slots.release()

		return _RenderSlotContext()

	def close_shared_browser(self) -> None:
		try:
			self._run_on_browser_thread(
				lambda: self._reset_browser_locked(template_name="shared-browser", reason="manual_cleanup")
			)
		finally:
			self._stop_browser_thread()

	def _acquire_browser(self, template_name: str) -> tuple[Any, dict[str, Any]]:
		with self._browser_lock:
			browser_reused = self._is_browser_usable(self._shared_browser)
			browser_relaunched = False

			if not browser_reused:
				if self._shared_browser is not None or self._shared_playwright is not None:
					browser_relaunched = True
					logger.warning(
						"pdf_browser_relaunch_requested",
						extra={
							"template_name": template_name,
							"browser_generation": self._browser_generation,
							"reason": "browser_unavailable",
							"process_id": self._process_id,
						},
					)
				self._reset_browser_locked(template_name=template_name, reason="browser_unavailable")
				self._launch_browser_locked(template_name)

			acquisition_details = {
				"browser_reused": browser_reused,
				"browser_relaunched": browser_relaunched,
				"browser_generation": self._browser_generation,
			}
			logger.info(
				"pdf_browser_acquired",
				extra={
					"template_name": template_name,
					"process_id": self._process_id,
					**acquisition_details,
				},
			)
			return self._shared_browser, acquisition_details

	def _launch_browser_locked(self, template_name: str) -> None:
		playwright_started = False

		try:
			if self._shared_playwright is None:
				self._shared_playwright = sync_playwright().start()
				playwright_started = True

			launch_options = self._build_browser_launch_options(self._shared_playwright.chromium)
			logger.info(
				"pdf_browser_launch_started",
				extra={
					"template_name": template_name,
					"process_id": self._process_id,
					"platform": platform.platform(),
					"site_name": os.getenv("WEBSITE_SITE_NAME", ""),
					"browsers_path": os.getenv("PLAYWRIGHT_BROWSERS_PATH", ""),
					"chromium_executable": Path(str(launch_options["executable_path"])).name,
				},
			)
			self._shared_browser = self._shared_playwright.chromium.launch(**launch_options)
			self._browser_generation += 1
			logger.info(
				"pdf_browser_launch_completed",
				extra={
					"template_name": template_name,
					"process_id": self._process_id,
					"browser_generation": self._browser_generation,
				},
			)
		except Exception:
			if self._shared_browser is not None:
				try:
					self._shared_browser.close()
				except Exception:
					logger.exception("Failed to close Playwright browser after launch failure")
				finally:
					self._shared_browser = None

			if playwright_started and self._shared_playwright is not None:
				try:
					self._shared_playwright.stop()
				except Exception:
					logger.exception("Failed to stop Playwright after launch failure")
				finally:
					self._shared_playwright = None
			raise

	def _invalidate_browser(self, template_name: str, reason: str) -> None:
		self._run_on_browser_thread(
			lambda: self._invalidate_browser_locked(template_name=template_name, reason=reason)
		)

	def _invalidate_browser_locked(self, *, template_name: str, reason: str) -> None:
		with self._browser_lock:
			self._reset_browser_locked(template_name=template_name, reason=reason)

	def _reset_browser_locked(self, *, template_name: str, reason: str) -> None:
		closed_browser = False
		closed_playwright = False

		if self._shared_browser is not None:
			try:
				self._shared_browser.close()
			except Exception:
				logger.exception("Failed to close shared Playwright browser")
			finally:
				self._shared_browser = None
				closed_browser = True

		if self._shared_playwright is not None:
			try:
				self._shared_playwright.stop()
			except Exception:
				logger.exception("Failed to stop shared Playwright manager")
			finally:
				self._shared_playwright = None
				closed_playwright = True

		if closed_browser or closed_playwright:
			logger.info(
				"pdf_browser_reset",
				extra={
					"template_name": template_name,
					"reason": reason,
					"process_id": self._process_id,
					"browser_generation": self._browser_generation,
					"closed_browser": closed_browser,
					"closed_playwright": closed_playwright,
				},
			)

	def _read_positive_int_env(self, env_var_name: str, default: int) -> int:
		raw_value = os.getenv(env_var_name, "").strip()
		if not raw_value:
			return default

		try:
			parsed_value = int(raw_value)
		except ValueError:
			logger.warning(
				"pdf_env_setting_invalid",
				extra={
					"process_id": self._process_id,
					"env_var_name": env_var_name,
					"env_var_value": raw_value,
					"default_value": default,
				},
			)
			return default

		return max(parsed_value, 0)

	def _is_browser_usable(self, browser: Any | None) -> bool:
		if browser is None:
			return False

		is_connected = getattr(browser, "is_connected", None)
		if not callable(is_connected):
			return True

		try:
			return bool(is_connected())
		except Exception:
			return False

	def _should_retry_browser(self, exc: Exception) -> bool:
		if not self._run_on_browser_thread(lambda: self._is_browser_usable(self._shared_browser)):
			return True

		error_message = str(exc).lower()
		return any(
			token in error_message
			for token in (
				"browser has been closed",
				"target page, context or browser has been closed",
				"connection closed",
				"browser closed",
				"pipe closed",
				"crash",
			)
		)

	def _build_cache_eligibility_payload(self, template_name: str) -> dict[str, Any]:
		template_basename = Path(template_name).name
		return {
			"template_name": template_name,
			"process_id": self._process_id,
			"cache_eligible": False,
			"cache_bucket": PDF_CACHE_BUCKETS_BY_TEMPLATE.get(template_basename, "pdf-documents"),
			"cache_reason": "blob_storage_not_enabled_phase2a",
		}

	def _build_browser_launch_options(self, browser_type: Any) -> dict[str, Any]:
		executable_path = os.getenv(PLAYWRIGHT_EXECUTABLE_ENV_VAR, "").strip() or browser_type.executable_path

		if platform.system() == "Linux":
			args = [
				"--no-sandbox",
				"--disable-setuid-sandbox",
				"--disable-dev-shm-usage",
				"--disable-gpu",
			]
		else:
			args = ["--disable-dev-shm-usage"]

		return {
			"headless": True,
			"executable_path": executable_path,
			"args": args,
		}

	def _to_directory_uri(self, path: Path) -> str:
		directory_uri = path.resolve().as_uri()
		return directory_uri if directory_uri.endswith("/") else f"{directory_uri}/"

	def _ensure_browser_thread(self) -> None:
		with self._browser_lock:
			if self._browser_thread is not None and self._browser_thread.is_alive():
				return

			self._browser_task_queue = queue.Queue()
			self._browser_thread_ready.clear()
			self._browser_thread = threading.Thread(
				target=self._browser_thread_main,
				name=f"pdf-browser-{self._process_id}",
				daemon=True,
			)
			self._browser_thread.start()

		if not self._browser_thread_ready.wait(timeout=10):
			raise RuntimeError("Timed out starting the PDF browser thread.")

	def _browser_thread_main(self) -> None:
		self._browser_thread_id = threading.get_ident()
		self._browser_thread_ready.set()

		while True:
			future, operation = self._browser_task_queue.get()
			if operation is None:
				future.set_result(None)
				return

			try:
				future.set_result(operation())
			except Exception as exc:
				future.set_exception(exc)

	def _run_on_browser_thread(self, operation):
		self._ensure_browser_thread()

		if threading.get_ident() == self._browser_thread_id:
			return operation()

		future: Future[Any] = Future()
		self._browser_task_queue.put((future, operation))
		return future.result()

	def _stop_browser_thread(self) -> None:
		with self._browser_lock:
			browser_thread = self._browser_thread

		if browser_thread is None or not browser_thread.is_alive():
			self._browser_thread = None
			self._browser_thread_id = None
			self._browser_thread_ready.clear()
			return

		future: Future[Any] = Future()
		self._browser_task_queue.put((future, None))
		future.result(timeout=5)
		browser_thread.join(timeout=5)

		with self._browser_lock:
			self._browser_thread = None
			self._browser_thread_id = None
			self._browser_thread_ready.clear()


pdf_generation_service = PdfGenerationService()
atexit.register(pdf_generation_service.close_shared_browser)


def generate_pdf(template_name: str, context: Mapping[str, Any]) -> bytes:
	return pdf_generation_service.generate_pdf(template_name, context)
