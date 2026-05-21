from collections.abc import Mapping
import logging
import os
import platform
from pathlib import Path
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape
from playwright.sync_api import sync_playwright


TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"
PDF_TEMPLATE_DIR = TEMPLATES_ROOT / "pdf"
PDF_SHARED_STYLESHEET = PDF_TEMPLATE_DIR / "styles.css"

logger = logging.getLogger(__name__)
PLAYWRIGHT_EXECUTABLE_ENV_VAR = "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"


class PdfGenerationService:
	def __init__(
		self,
		templates_root: Path | None = None,
		shared_stylesheet: Path | None = None,
		environment: Environment | None = None,
	) -> None:
		self.templates_root = templates_root or TEMPLATES_ROOT
		self.template_dir = self.templates_root / "pdf"
		self.shared_stylesheet = shared_stylesheet or PDF_SHARED_STYLESHEET
		self.environment = environment or Environment(
			loader=FileSystemLoader(str(self.templates_root)),
			autoescape=select_autoescape(["html", "xml"]),
			undefined=StrictUndefined,
		)

	def generate_pdf(self, template_name: str, context: Mapping[str, Any]) -> bytes:
		template_filename = self._normalize_template_name(template_name)
		logger.info(
			"pdf_generation_requested",
			extra={
				"template_name": template_filename,
				"context_key_count": len(context),
			},
		)
		template_path = self._get_template_path(template_filename)
		self._validate_assets(template_path)
		rendered_html = self.render_template(template_filename, context)
		prepared_html = self._prepare_html_document(rendered_html, template_path)
		return self._render_pdf_with_browser(prepared_html, template_path)

	def render_template(self, template_name: str, context: Mapping[str, Any]) -> str:
		try:
			template = self.environment.get_template(template_name)
		except TemplateNotFound as exc:
			raise FileNotFoundError(f"PDF template '{template_name}' was not found.") from exc

		return template.render(**dict(context))

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

	def _prepare_html_document(self, rendered_html: str, template_path: Path) -> str:
		base_href = self._to_directory_uri(template_path.parent)
		prepared_html = self._set_base_href(rendered_html, base_href)
		prepared_html = self._replace_stylesheet_href(prepared_html)
		prepared_html = self._absolutize_asset_sources(prepared_html, template_path.parent)
		return prepared_html

	def _set_base_href(self, rendered_html: str, base_href: str) -> str:
		base_tag = f'<base href="{base_href}" />'

		if re.search(r"<base\s+href=", rendered_html, flags=re.IGNORECASE):
			return re.sub(r"<base\s+href=[^>]+>", base_tag, rendered_html, count=1, flags=re.IGNORECASE)

		if "</head>" in rendered_html:
			return rendered_html.replace("</head>", f"\t{base_tag}\n</head>", 1)

		return f"{base_tag}\n{rendered_html}"

	def _replace_stylesheet_href(self, rendered_html: str) -> str:
		stylesheet_uri = self.shared_stylesheet.resolve().as_uri()
		return re.sub(
			r'(<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\'])([^"\']+)(["\'][^>]*>)',
			rf'\1{stylesheet_uri}\3',
			rendered_html,
			count=1,
			flags=re.IGNORECASE,
		)

	def _absolutize_asset_sources(self, rendered_html: str, asset_base_dir: Path) -> str:
		def replace_source(match: re.Match[str]) -> str:
			prefix, source, suffix = match.groups()
			if source.startswith(("http://", "https://", "data:", "file://", "#")):
				return match.group(0)

			absolute_source = (asset_base_dir / source).resolve().as_uri()
			return f"{prefix}{absolute_source}{suffix}"

		return re.sub(r'(<(?:img|source)[^>]+src=["\'])([^"\']+)(["\'][^>]*>)', replace_source, rendered_html, flags=re.IGNORECASE)

	def _render_pdf_with_browser(self, prepared_html: str, template_path: Path) -> bytes:
		playwright = None
		browser = None
		context = None
		page = None

		try:
			playwright = sync_playwright().start()
			launch_options = self._build_browser_launch_options(playwright.chromium)
			logger.info(
				"pdf_browser_launch_started",
				extra={
					"template_name": template_path.name,
					"platform": platform.platform(),
					"site_name": os.getenv("WEBSITE_SITE_NAME", ""),
					"browsers_path": os.getenv("PLAYWRIGHT_BROWSERS_PATH", ""),
					"chromium_executable": Path(str(launch_options["executable_path"])).name,
				},
			)
			browser = playwright.chromium.launch(**launch_options)

			context = browser.new_context()
			page = context.new_page()
			page.set_content(prepared_html, wait_until="networkidle")

			pdf_bytes = page.pdf(format="A4", print_background=True)
			logger.info(
				"pdf_generation_succeeded",
				extra={
					"template_name": template_path.name,
					"size_bytes": len(pdf_bytes),
				},
			)
			return pdf_bytes
		except Exception as exc:
			logger.exception(
				"pdf_generation_failed",
				extra={
					"template_name": template_path.name,
					"error_type": type(exc).__name__,
				},
			)
			raise RuntimeError(
				f"Failed to generate PDF from template '{template_path.name}'. {exc}"
			) from exc
		finally:
			if page is not None:
				try:
					if not page.is_closed():
						page.close()
						logger.info("Playwright page closed for template '%s'", template_path.name)
				except Exception:
					logger.exception("Failed to close Playwright page for template '%s'", template_path.name)

			if context is not None:
				try:
					context.close()
					logger.info("Playwright browser context closed for template '%s'", template_path.name)
				except Exception:
					logger.exception("Failed to close Playwright browser context for template '%s'", template_path.name)

			if browser is not None:
				try:
					browser.close()
					logger.info("Playwright browser closed for template '%s'", template_path.name)
				except Exception:
					logger.exception("Failed to close Playwright browser for template '%s'", template_path.name)

			if playwright is not None:
				try:
					playwright.stop()
					logger.info("Playwright stopped for template '%s'", template_path.name)
				except Exception:
					logger.exception("Failed to stop Playwright for template '%s'", template_path.name)

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


pdf_generation_service = PdfGenerationService()


def generate_pdf(template_name: str, context: Mapping[str, Any]) -> bytes:
	return pdf_generation_service.generate_pdf(template_name, context)
