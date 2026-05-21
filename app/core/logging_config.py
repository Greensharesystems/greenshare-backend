import hashlib
import json
import logging
from logging.config import dictConfig
from typing import Any

from app.core.config import APP_ENVIRONMENT, BACKEND_LOG_LEVEL


STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


def fingerprint_identifier(value: str | None) -> str | None:
	if not value:
		return None

	normalized_value = value.strip().lower()
	if not normalized_value:
		return None

	return hashlib.sha256(normalized_value.encode("utf-8")).hexdigest()[:12]


class StructuredFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		payload: dict[str, Any] = {
			"level": record.levelname,
			"logger": record.name,
			"message": record.getMessage(),
			"environment": APP_ENVIRONMENT,
		}

		for key, value in record.__dict__.items():
			if key in STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
				continue
			if value is None:
				continue
			payload[key] = self._serialize(value)

		if record.exc_info:
			payload["exception"] = self.formatException(record.exc_info)

		return json.dumps(payload, separators=(",", ":"), default=str)

	def _serialize(self, value: Any) -> Any:
		if isinstance(value, (str, int, float, bool)):
			return value
		if isinstance(value, dict):
			return {str(key): self._serialize(item) for key, item in value.items()}
		if isinstance(value, (list, tuple, set)):
			return [self._serialize(item) for item in value]
		return str(value)


def configure_logging() -> None:
	dictConfig(
		{
			"version": 1,
			"disable_existing_loggers": False,
			"formatters": {
				"structured": {
					"()": "app.core.logging_config.StructuredFormatter",
				},
			},
			"handlers": {
				"default": {
					"class": "logging.StreamHandler",
					"formatter": "structured",
					"stream": "ext://sys.stdout",
				},
			},
			"root": {
				"level": BACKEND_LOG_LEVEL,
				"handlers": ["default"],
			},
			"loggers": {
				"gunicorn": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
				"gunicorn.error": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
				"gunicorn.access": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
				"uvicorn": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
				"uvicorn.error": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
				"uvicorn.access": {
					"level": BACKEND_LOG_LEVEL,
					"handlers": ["default"],
					"propagate": False,
				},
			},
		},
	)