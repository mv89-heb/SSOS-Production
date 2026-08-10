from typing import Optional

from sqlalchemy import select

from app.extensions import db
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = self._tenant_select().where(User.email == email.lower().strip())
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email_any_tenant(email: str) -> Optional[User]:
        """Used only at login time, before the tenant is known from a session."""
        stmt = select(User).where(User.email == email.lower().strip())
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_id_global(user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)
