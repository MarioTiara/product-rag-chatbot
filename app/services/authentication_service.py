
from app.configs.config import get_settings
from app.utils.security import create_access_token, verify_password
from app.models.user import User


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthenticationService:
    def __init__(self) -> None:
        settings = get_settings()

        self._dev_user = User(
            id=settings.dev_user_id,
            username=settings.dev_username,
            hashed_password=(
                settings.dev_password_hash.get_secret_value()
            ),
            is_active=settings.dev_user_active,
        )

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> User:
        user = self._dev_user

        if (
            username != user.username
            or not verify_password(password, user.hashed_password)
            or not user.is_active
        ):
            raise AuthenticationError(
                "Invalid username or password"
            )

        return user

    def login(
        self,
        username: str,
        password: str,
    ) -> tuple[User, str]:
        user = self.authenticate(username, password)

        access_token = create_access_token(
            subject=user.id,
        )

        return user, access_token

    def get_user_by_id(self, user_id: str) -> User | None:
        user = self._dev_user

        if user.id != user_id or not user.is_active:
            return None

        return user
