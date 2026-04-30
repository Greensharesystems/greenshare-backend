from datetime import date, datetime


DISPLAY_DATE_FORMAT = "%d-%m-%Y"
SUPPORTED_DATE_INPUT_FORMATS = (
	DISPLAY_DATE_FORMAT,
	"%Y-%m-%d",
	"%d %b %Y",
	"%d %B %Y",
	"%d/%m/%Y",
	"%Y/%m/%d",
)


def format_display_date(value: date) -> str:
	return value.strftime(DISPLAY_DATE_FORMAT)


def parse_supported_date(value: str | None) -> date | None:
	trimmed_value = str(value or "").strip()

	if not trimmed_value:
		return None

	for input_format in SUPPORTED_DATE_INPUT_FORMATS:
		try:
			parsed_value = datetime.strptime(trimmed_value, input_format)
		except ValueError:
			continue

		return parsed_value.date()

	return None


def normalize_date_for_storage(value: str | None, field_label: str) -> str:
	trimmed_value = str(value or "").strip()

	if not trimmed_value:
		raise ValueError(f"{field_label} is required.")

	parsed_value = parse_supported_date(trimmed_value)

	if parsed_value is None:
		raise ValueError(f"{field_label} must use DD-MM-YYYY format.")

	return format_display_date(parsed_value)


def normalize_optional_date_for_storage(value: str | None, field_label: str = "Date") -> str:
	trimmed_value = str(value or "").strip()

	if not trimmed_value:
		return ""

	parsed_value = parse_supported_date(trimmed_value)

	if parsed_value is None:
		raise ValueError(f"{field_label} must use DD-MM-YYYY format.")

	return format_display_date(parsed_value)


def normalize_date_for_output(value: str | None) -> str:
	trimmed_value = str(value or "").strip()

	if not trimmed_value:
		return ""

	parsed_value = parse_supported_date(trimmed_value)

	if parsed_value is None:
		return trimmed_value

	return format_display_date(parsed_value)