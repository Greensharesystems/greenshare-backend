from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.env import load_environment


load_environment()

DEFAULT_SQLITE_URL = "sqlite:///./greenshare.db"

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
	DATABASE_URL = DEFAULT_SQLITE_URL

print("Using database:", DATABASE_URL.split("@")[-1])

engine = create_engine(
	DATABASE_URL,
	echo=True,
	pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
