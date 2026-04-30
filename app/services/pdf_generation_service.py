from collections.abc import Mapping
import logging
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape


TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"
PDF_TEMPLATE_DIR = TEMPLATES_ROOT / "pdf"
PDF_SHARED_STYLESHEET = PDF_TEMPLATE_DIR / "styles.css"
BROWSER_CANDIDATES = (
	Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
	Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
	Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
	Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
)

logger = logging.getLogger(__name__)


class PdfGenerationService:
	def __init__(
		self,
		templates_root: Path | None = None,
		shared_stylesheet: Path | None = None,
		environment: Environment | None = None,
		browser_executable: Path | None = None,
	) -> None:
		self.templates_root = templates_root or TEMPLATES_ROOT
		self.template_dir = self.templates_root / "pdf"
		self.shared_stylesheet = shared_stylesheet or PDF_SHARED_STYLESHEET
		self.browser_executable = browser_executable or self._find_browser_executable()
		self.environment = environment or Environment(
			loader=FileSystemLoader(str(self.templates_root)),
			autoescape=select_autoescape(["html", "xml"]),
			undefined=StrictUndefined,
		)

	def generate_pdf(self, template_name: str, context: Mapping[str, Any]) -> bytes:
		template_filename = self._normalize_template_name(template_name)
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
		browser_executable = self._get_browser_executable()

		with tempfile.TemporaryDirectory(prefix="greenshare-pdf-") as temp_dir_name:
			temp_dir = Path(temp_dir_name)
			html_output_path = temp_dir / template_path.name
			pdf_output_path = temp_dir / f"{template_path.stem}.pdf"
			profile_dir = temp_dir / "browser-profile"
			profile_dir.mkdir(parents=True, exist_ok=True)

			html_output_path.write_text(prepared_html, encoding="utf-8")
			command = [
				str(browser_executable),
				"--headless=new",
				"--disable-gpu",
				"--no-first-run",
				"--no-default-browser-check",
				"--allow-file-access-from-files",
				"--disable-features=msEdgePdfOcr,msPdfAccessibility",
				f"--user-data-dir={profile_dir}",
				"--no-pdf-header-footer",
				f"--print-to-pdf={pdf_output_path}",
				html_output_path.resolve().as_uri(),
			]

			result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)

			if result.returncode != 0 or not pdf_output_path.is_file():
				raise RuntimeError(
					f"Failed to generate PDF from template '{template_path.name}'. {result.stderr.strip() or result.stdout.strip()}"
				)

			return pdf_output_path.read_bytes()

	def _get_browser_executable(self) -> Path:
		if self.browser_executable is None:
			self.browser_executable = self._find_browser_executable()

		if self.browser_executable is None:
			raise RuntimeError(
				"PDF generation requires a supported Edge or Chrome browser executable, but none was found. "
				"Install a supported browser or configure the PDF generation environment before calling this endpoint."
			)

		return self.browser_executable

	def _find_browser_executable(self) -> Path | None:
		for candidate in BROWSER_CANDIDATES:
			if candidate.is_file():
				logger.info("Using browser executable for PDF generation: %s", candidate)
				return candidate

		logger.warning(
			"No supported Edge or Chrome browser executable was found for PDF generation. "
			"PDF endpoints will return an error until a supported browser is available."
		)
		return None

	def _to_directory_uri(self, path: Path) -> str:
		directory_uri = path.resolve().as_uri()
		return directory_uri if directory_uri.endswith("/") else f"{directory_uri}/"


pdf_generation_service = PdfGenerationService()


def generate_pdf(template_name: str, context: Mapping[str, Any]) -> bytes:
	return pdf_generation_service.generate_pdf(template_name, context)
