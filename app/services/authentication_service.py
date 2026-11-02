from app.core.configs.config import get_settings
from app.database.connection import DatabaseConnection
from app.database.repositories.user_repository import UserRepository
from app.models.user import User
from app.utils.security import create_access_token, verify_password


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthenticationService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
    ) -> None:
        if user_repository is None:
            settings = get_settings()
            database = DatabaseConnection(settings.database_path)
            user_repository = UserRepository(database)

        self.users = user_repository

    def authenticate(
        self,
        email: str,
        password: str,
    ) -> User:
        user_data = self.users.get_by_email(email)

        if user_data is None:
            raise AuthenticationError(
                "Invalid email or password"
            )

        password_hash = self.users.get_password_hash_by_email(
            email
        )

        if (
            password_hash is None
            or not verify_password(password, password_hash)
        ):
            raise AuthenticationError(
                "Invalid email or password"
            )

        return User(**user_data)

    def login(
        self,
        email: str,
        password: str,
    ) -> tuple[User, str]:
        user = self.authenticate(email, password)

        access_token = create_access_token(
            subject=user.id,
        )

        return user, access_token

    def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        user_data = self.users.get_by_id(user_id)

        if user_data is None:
            return None

        return User(**user_data)
