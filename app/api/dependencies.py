from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.ai.chatbot_orchestrator import ChatbotOrchestrator
from app.configs import config
from app.database.connection import DatabaseConnection
from app.database.repositories.product_repository import ProductRepository
from app.models.user import User
from app.services.authentication_service import AuthenticationService
from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService
from app.utils.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not isinstance(user_id, str) or not user_id:
            raise unauthorized

    except InvalidTokenError:
        raise unauthorized from None

    service = get_authentication_service()
    user = service.get_user_by_id(user_id)

    if user is None:
        raise unauthorized

    return user


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    settings = config.get_settings()
    database = DatabaseConnection(settings.database_path)
    repository = ProductRepository(database)

    return ProductService(repository)


@lru_cache(maxsize=1)
def get_conversation_service() -> ConversationService:
    return ConversationService()


def get_conversation_store() -> ConversationService:
    """Backward-compatible alias for older imports/tests."""
    return get_conversation_service()


@lru_cache(maxsize=1)
def get_chatbot_orchestrator() -> ChatbotOrchestrator:
    return ChatbotOrchestrator(
        product_service=get_product_service(),
        conversation_service=get_conversation_service(),
    )


@lru_cache(maxsize=1)
def get_authentication_service() -> AuthenticationService:
    return AuthenticationService()
