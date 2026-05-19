import base64
import hashlib
import hmac
import os
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.env import load_environment


load_environment()


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

	database_url: str = Field(default="sqlite:///./greenshare.db", validation_alias="DATABASE_URL")
	secret_key: str = Field(
		default="greenshare-local-auth-secret",
		validation_alias=AliasChoices("SECRET_KEY", "GREENSHARE_AUTH_SECRET"),
	)
	algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")
	access_token_expire_minutes: int = Field(default=480, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()


DATABASE_URL = get_settings().database_url
DEFAULT_USER_PASSWORD = "greenshare"
PASSWORD_MIN_LENGTH = 8
PASSWORD_HASH_ITERATIONS = 100_000
AUTH_SECRET_KEY = get_settings().secret_key
AUTH_ALGORITHM = get_settings().algorithm
AUTH_TOKEN_EXPIRE_MINUTES = get_settings().access_token_expire_minutes


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
