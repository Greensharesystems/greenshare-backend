from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_users(db: Session) -> list[User]:
	statement = select(User).order_by(User.created_at.desc(), User.id.desc())
	return list(db.scalars(statement).all())


def get_user_ids(db: Session) -> list[str]:
	statement = select(User.user_id)
	return [user_id for user_id in db.scalars(statement).all() if user_id]


def get_user_by_user_id(db: Session, user_id: str) -> User | None:
	statement = select(User).where(User.user_id == user_id)
	return db.scalar(statement)


def get_user_by_email(db: Session, email: str) -> User | None:
	statement = select(User).where(User.email == email)
	return db.scalar(statement)


def create_user(db: Session, user: User) -> User:
	db.add(user)
	db.commit()
	db.refresh(user)
	return user


def delete_user(db: Session, user: User) -> None:
	db.delete(user)
