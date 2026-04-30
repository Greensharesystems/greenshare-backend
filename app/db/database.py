from collections.abc import Generator
import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)

engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

if settings.database_url.startswith("sqlite"):
	engine_kwargs["connect_args"] = {"check_same_thread": False}


engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _is_postgresql_url(database_url: str) -> bool:
	return make_url(database_url).get_backend_name().startswith("postgresql")


def _build_admin_database_url(target_url: URL) -> URL:
	return target_url.set(database="postgres")


def _validate_database_name(database_name: str) -> str:
	if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_name):
		raise RuntimeError(f"Unsupported PostgreSQL database name '{database_name}' for automatic creation.")

	return database_name


def ensure_database_exists() -> None:
	if not _is_postgresql_url(settings.database_url):
		return

	target_url = make_url(settings.database_url)
	target_database = target_url.database

	if not target_database or target_database == "postgres":
		return

	target_database = _validate_database_name(target_database)
	admin_engine = create_engine(_build_admin_database_url(target_url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)

	try:
		with admin_engine.connect() as connection:
			database_exists = connection.execute(
				text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
				{"database_name": target_database},
			).scalar()

			if database_exists:
				return

			logger.info("Creating PostgreSQL database '%s'.", target_database)
			connection.execute(text(f'CREATE DATABASE "{target_database}"'))
	except SQLAlchemyError as exc:
		logger.exception("Unable to verify or create PostgreSQL database '%s'.", target_database)
		raise RuntimeError(
			"Database provisioning failed. Verify the Azure PostgreSQL server is reachable, the firewall allows App Service access, and the DATABASE_URL uses sslmode=require."
		) from exc
	finally:
		admin_engine.dispose()


def initialize_database() -> None:
	try:
		ensure_database_exists()
		Base.metadata.create_all(bind=engine)
	except SQLAlchemyError as exc:
		logger.exception("Database initialization failed.")
		raise RuntimeError(
			"Database initialization failed. Verify DATABASE_URL, Azure PostgreSQL connectivity, and sslmode=require before starting the app."
		) from exc


def get_db() -> Generator:
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
