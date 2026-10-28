
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from openai import OpenAI

from app.agents.ai.openai_adapter import OpenAIAdapter
from app.agents.agent_executor import AgentExecutor
from app.agents.chat_context_builder import ChatContextBuilder
from app.agents.chatbot_orchestrator import ChatbotOrchestrator
from app.agents.tools.tool_call_handler import ToolCallHandler
from app.agents.tools.tool_history_validator import ToolHistoryValidator
from app.agents.utils.message_mapper import MessageMapper
from app.configs import config
from app.database.connection import DatabaseConnection
from app.database.repositories.product_repository import ProductRepository
from app.models.user import User
from app.services.authentication_service import AuthenticationService
from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService
from app.utils.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> User:
    """Decode the access token and return the authenticated user."""

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

    user = get_authentication_service().get_user_by_id(user_id)

    if user is None:
        raise unauthorized

    return user


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    """Create and cache the product service."""

    settings = config.get_settings()
    database = DatabaseConnection(settings.database_path)
    repository = ProductRepository(database)

    return ProductService(repository)


@lru_cache(maxsize=1)
def get_conversation_service() -> ConversationService:
    """Create and cache the conversation service."""

    return ConversationService()



@lru_cache(maxsize=1)
def get_ai_client() -> OpenAIAdapter:
    """Create and cache the OpenAI client adapter."""

    settings = config.get_settings()

    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value,
    )

    return OpenAIAdapter(
        client=client,
        model=settings.openai_model,
    )


@lru_cache(maxsize=1)
def get_chat_context_builder() -> ChatContextBuilder:
    """Create and cache the chat context builder."""

    return ChatContextBuilder(
        conversation_service=get_conversation_service(),
        message_mapper= MessageMapper()
    )


@lru_cache(maxsize=1)
def get_tool_call_handler() -> ToolCallHandler:
    """Create and cache the tool call handler."""

    return ToolCallHandler(
        product_service=get_product_service(),
        conversation_service=get_conversation_service(),
    )


@lru_cache(maxsize=1)
def get_tool_history_validator() -> ToolHistoryValidator:
    """Create and cache the tool history validator."""

    return ToolHistoryValidator()


@lru_cache(maxsize=1)
def get_agent_executor() -> AgentExecutor:
    """Create and cache the agent executor."""

    return AgentExecutor(
        ai_client=get_ai_client(),
        tool_call_handler=get_tool_call_handler(),
        tool_history_validator=get_tool_history_validator(),
    )



@lru_cache(maxsize=1)
def get_chatbot_orchestrator() -> ChatbotOrchestrator:
    """Create and cache the chatbot orchestrator."""

    return ChatbotOrchestrator(
        context_builder=get_chat_context_builder(),
        agent_executor=get_agent_executor(),
        conversation_service=get_conversation_service(),
    )


@lru_cache(maxsize=1)
def get_authentication_service() -> AuthenticationService:
    """Create and cache the authentication service."""

    return AuthenticationService()
