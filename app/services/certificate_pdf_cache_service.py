import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)
SAFE_CERTIFICATE_ID_PATTERN = re.compile(r"[^A-Z0-9_.-]+")


def get_certificate_pdf_cache_root() -> Path:
	configured_root = os.getenv("CERTIFICATE_PDF_CACHE_DIR", "").strip()
	if configured_root:
		return Path(configured_root)

	if os.getenv("WEBSITE_SITE_NAME"):
		return Path("/home/site/data/certificate-pdfs")

	return Path(".certificate-pdf-cache")


def build_pdf_content_fingerprint(payload: object) -> str:
	serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
	return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def safe_certificate_pdf_filename(certificate_id: str) -> str:
	normalized_id = str(certificate_id).strip().upper()
	filename_stem = SAFE_CERTIFICATE_ID_PATTERN.sub("-", normalized_id).strip(".-")
	if not filename_stem:
		raise ValueError("A certificate ID is required for PDF caching.")
	return f"{filename_stem}.pdf"


def read_cached_certificate_pdf(
	certificate,
	*,
	certificate_id: str,
	certificate_type: str,
	fingerprint: str,
) -> tuple[str, bytes] | None:
	started_at = time.perf_counter()
	filename = safe_certificate_pdf_filename(certificate_id)
	stored_path = str(getattr(certificate, "pdf_file_path", "") or "").strip()
	stored_fingerprint = str(getattr(certificate, "pdf_cache_fingerprint", "") or "").strip()

	if not stored_path or stored_fingerprint != fingerprint:
		log_certificate_pdf_cache_event(
			"certificate_pdf_cache_miss",
			certificate_id=certificate_id,
			certificate_type=certificate_type,
			cache_hit=False,
			load_started_at=started_at,
			reason="missing_path" if not stored_path else "fingerprint_changed",
		)
		return None

	pdf_path = Path(stored_path)
	if not pdf_path.exists() or not pdf_path.is_file():
		log_certificate_pdf_cache_event(
			"certificate_pdf_cache_miss",
			certificate_id=certificate_id,
			certificate_type=certificate_type,
			cache_hit=False,
			load_started_at=started_at,
			reason="file_missing",
		)
		return None

	pdf_bytes = pdf_path.read_bytes()
	log_certificate_pdf_cache_event(
		"certificate_pdf_cache_hit",
		certificate_id=certificate_id,
		certificate_type=certificate_type,
		cache_hit=True,
		load_started_at=started_at,
		size_bytes=len(pdf_bytes),
	)
	return filename, pdf_bytes


def get_or_create_certificate_pdf(
	db: Session,
	certificate,
	*,
	certificate_id: str,
	certificate_type: str,
	fingerprint: str,
	render_pdf: Callable[[], bytes],
) -> tuple[str, bytes, bool]:
	cached_pdf = read_cached_certificate_pdf(
		certificate,
		certificate_id=certificate_id,
		certificate_type=certificate_type,
		fingerprint=fingerprint,
	)
	if cached_pdf is not None:
		filename, pdf_bytes = cached_pdf
		return filename, pdf_bytes, True

	started_at = time.perf_counter()
	filename = safe_certificate_pdf_filename(certificate_id)
	pdf_bytes = render_pdf()
	pdf_path = write_certificate_pdf(certificate_type, filename, pdf_bytes)
	certificate.pdf_file_path = str(pdf_path)
	certificate.pdf_cache_fingerprint = fingerprint
	certificate.pdf_generated_at = datetime.now(timezone.utc)
	db.add(certificate)
	db.commit()
	log_certificate_pdf_cache_event(
		"certificate_pdf_cache_written",
		certificate_id=certificate_id,
		certificate_type=certificate_type,
		cache_hit=False,
		load_started_at=started_at,
		size_bytes=len(pdf_bytes),
		path=str(pdf_path),
	)
	return filename, pdf_bytes, False


def write_certificate_pdf(certificate_type: str, filename: str, pdf_bytes: bytes) -> Path:
	root = get_certificate_pdf_cache_root()
	certificate_dir = root / certificate_type
	certificate_dir.mkdir(parents=True, exist_ok=True)
	pdf_path = certificate_dir / filename
	temporary_path = pdf_path.with_suffix(".pdf.tmp")
	temporary_path.write_bytes(pdf_bytes)
	temporary_path.replace(pdf_path)
	return pdf_path


def invalidate_certificate_pdf_cache(certificate) -> None:
	certificate.pdf_cache_fingerprint = None
	certificate.pdf_generated_at = None


def log_certificate_pdf_cache_event(
	message: str,
	*,
	certificate_id: str,
	certificate_type: str,
	cache_hit: bool,
	load_started_at: float,
	reason: str | None = None,
	size_bytes: int | None = None,
	path: str | None = None,
) -> None:
	load_time_seconds = round(time.perf_counter() - load_started_at, 4)
	logger.info(
		message,
		extra={
			"certificate_id": certificate_id,
			"certificate_type": certificate_type,
			"cache_hit": cache_hit,
			"cache_miss": not cache_hit,
			"load_time_seconds": load_time_seconds,
			"load_time_ms": round(load_time_seconds * 1000, 2),
			"reason": reason,
			"size_bytes": size_bytes,
			"path": path,
		},
	)
