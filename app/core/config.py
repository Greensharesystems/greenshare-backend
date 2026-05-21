import base64
import hashlib
import hmac
import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.env import load_environment


load_environment()


DEFAULT_CORS_ORIGINS = (
	"https://witty-pond-0c214db00.7.azurestaticapps.net",
	"https://witty-pond-0c214db00-1.eastasia.7.azurestaticapps.net",
	"https://witty-pond-0c214db00-dev.eastasia.7.azurestaticapps.net",
	"https://www.greenshare.ae",
	"https://greenshare.ae",
	"http://localhost:3000",
	"http://127.0.0.1:3000",
)


def _normalize_origin(origin: str) -> str:
	normalized_origin = origin.strip().strip('"').strip("'")
	if not normalized_origin:
		return ""

	parsed_origin = urlparse(normalized_origin)
	if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc:
		return ""

	return f"{parsed_origin.scheme}://{parsed_origin.netloc}"


def parse_cors_origins(value: str | None, defaults: tuple[str, ...] = DEFAULT_CORS_ORIGINS) -> list[str]:
	combined_origins = [*defaults]
	if value:
		combined_origins.extend(value.split(","))

	normalized_origins: list[str] = []
	seen_origins: set[str] = set()
	for origin in combined_origins:
		normalized_origin = _normalize_origin(origin)
		if not normalized_origin or normalized_origin in seen_origins:
			continue
		seen_origins.add(normalized_origin)
		normalized_origins.append(normalized_origin)

	return normalized_origins


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

	database_url: str = Field(default="sqlite:///./greenshare.db", validation_alias="DATABASE_URL")
	app_environment: str = Field(
		default="development",
		validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT", "BACKEND_ENVIRONMENT"),
	)
	backend_log_level: str = Field(
		default="INFO",
		validation_alias=AliasChoices("LOG_LEVEL", "BACKEND_LOG_LEVEL"),
	)
	sqlalchemy_echo: bool = Field(
		default=False,
		validation_alias=AliasChoices("SQLALCHEMY_ECHO", "DB_ECHO"),
	)
	secret_key: str = Field(
		default="greenshare-local-auth-secret",
		validation_alias=AliasChoices("SECRET_KEY", "GREENSHARE_AUTH_SECRET"),
	)
	algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")
	access_token_expire_minutes: int = Field(default=480, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
	cors_allowed_origins: str = Field(
		default="",
		validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "ALLOWED_ORIGINS", "BACKEND_CORS_ORIGINS"),
	)
	cors_allow_origin_regex: str = Field(
		default=r"https://.*\.azurestaticapps\.net",
		validation_alias=AliasChoices("CORS_ALLOW_ORIGIN_REGEX", "ALLOWED_ORIGIN_REGEX"),
	)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()


DATABASE_URL = get_settings().database_url
APP_ENVIRONMENT = get_settings().app_environment
BACKEND_LOG_LEVEL = get_settings().backend_log_level.upper()
SQLALCHEMY_ECHO = get_settings().sqlalchemy_echo
DEFAULT_USER_PASSWORD = "greenshare"
PASSWORD_MIN_LENGTH = 8
PASSWORD_HASH_ITERATIONS = 100_000
AUTH_SECRET_KEY = get_settings().secret_key
AUTH_ALGORITHM = get_settings().algorithm
AUTH_TOKEN_EXPIRE_MINUTES = get_settings().access_token_expire_minutes
BACKEND_CORS_ORIGINS = parse_cors_origins(get_settings().cors_allowed_origins)
BACKEND_CORS_ORIGIN_REGEX = get_settings().cors_allow_origin_regex


def hash_password(password: str) -> str:
	normalized_password = password.strip()
	salt = os.urandom(16)
	digest = hashlib.pbkdf2_hmac(
		"sha256",
		normalized_password.encode("utf-8"),
		salt,
		PASSWORD_HASH_ITERATIONS,
	)
	encoded_salt = base64.b64encode(salt).decode("ascii")
	encoded_digest = base64.b64encode(digest).decode("ascii")
	return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, password_hash: str | None) -> bool:
	if not password_hash:
		return False

	try:
		algorithm, iterations, encoded_salt, encoded_digest = password_hash.split("$", maxsplit=3)
	except ValueError:
		return False

	if algorithm != "pbkdf2_sha256":
		return False

	salt = base64.b64decode(encoded_salt.encode("ascii"))
	stored_digest = base64.b64decode(encoded_digest.encode("ascii"))
	computed_digest = hashlib.pbkdf2_hmac(
		"sha256",
		password.strip().encode("utf-8"),
		salt,
		int(iterations),
	)
	return hmac.compare_digest(computed_digest, stored_digest)
