from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL, SQLALCHEMY_ECHO
from app.core.env import load_environment


load_environment()

DEFAULT_SQLITE_URL = "sqlite:///./greenshare.db"

engine = create_engine(
	DATABASE_URL or DEFAULT_SQLITE_URL,
	echo=SQLALCHEMY_ECHO,
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
